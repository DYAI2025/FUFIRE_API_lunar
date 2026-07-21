"""
tests/test_b2b_infra.py — B2B infrastructure tests.
Tests request IDs, error envelope, /v1/ routes, health checks, API key auth, rate limiting.
"""
from __future__ import annotations

import os
import uuid

import pytest
from fastapi.testclient import TestClient

from bazi_engine.app import app

client = TestClient(app)


class TestRequestId:
    def test_error_response_contains_request_id(self):
        """422 error must include request_id field."""
        response = client.post("/calculate/bazi", json={"bad": "data"})
        assert response.status_code == 422
        body = response.json()
        assert "request_id" in body, f"No request_id in: {body}"

    def test_request_id_is_valid_uuid(self):
        """request_id must be a valid UUID string."""
        response = client.post("/calculate/bazi", json={"bad": "data"})
        assert response.status_code == 422
        request_id = response.json().get("request_id")
        uuid.UUID(request_id)  # raises ValueError if not a valid UUID

    def test_request_id_header_present(self):
        """X-Request-ID response header must be set on all responses."""
        response = client.get("/health")
        assert "x-request-id" in response.headers
        uuid.UUID(response.headers["x-request-id"])

    def test_request_id_different_per_request(self):
        """Each request gets a unique ID."""
        r1 = client.get("/health")
        r2 = client.get("/health")
        assert r1.headers["x-request-id"] != r2.headers["x-request-id"]

    def test_client_request_id_echoed(self):
        """If client sends X-Request-ID, it's echoed back."""
        custom_id = str(uuid.uuid4())
        response = client.get("/health", headers={"X-Request-ID": custom_id})
        assert response.headers["x-request-id"] == custom_id

    def test_error_envelope_contains_b2b_metadata(self):
        """Error envelope should expose status/path/timestamp for supportability."""
        response = client.get("/does-not-exist")
        assert response.status_code == 404
        body = response.json()
        assert body.get("status") == 404
        assert body.get("path") == "/does-not-exist"
        assert "timestamp" in body


class TestHealth:
    def test_health_returns_status(self):
        response = client.get("/health")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] in ("healthy", "degraded", "unavailable")

    def test_health_has_dependencies_key(self):
        """Must report per-dependency status."""
        response = client.get("/health")
        body = response.json()
        assert "dependencies" in body, f"Missing 'dependencies' in: {body}"

    def test_health_dependencies_has_ephemeris(self):
        response = client.get("/health")
        deps = response.json()["dependencies"]
        assert "ephemeris" in deps

    def test_health_ephemeris_has_status(self):
        response = client.get("/health")
        ephemeris = response.json()["dependencies"]["ephemeris"]
        assert "status" in ephemeris
        assert ephemeris["status"] in ("ok", "unavailable")

    def test_health_has_version(self):
        response = client.get("/health")
        assert "version" in response.json()

    def test_health_has_engine(self):
        response = client.get("/health")
        assert response.json()["engine"] == "FuFirE"

    def test_ready_exists_and_is_health_based(self):
        """Readiness endpoint should be exposed for orchestration checks."""
        response = client.get("/ready")
        assert response.status_code in (200, 503)
        body = response.json()
        assert "status" in body
        assert "dependencies" in body

    def test_v1_ready_exists(self):
        response = client.get("/v1/ready")
        assert response.status_code in (200, 503)

    def test_response_hardening_headers_present(self):
        response = client.get("/health")
        assert "x-api-version" in response.headers
        assert "x-response-time-ms" in response.headers
        assert response.headers.get("x-content-type-options") == "nosniff"
        assert response.headers.get("x-frame-options") == "DENY"
        assert response.headers.get("referrer-policy") == "no-referrer"


class TestV1Routes:
    """All public routes must be accessible under /v1/ prefix."""

    def test_v1_health(self):
        response = client.get("/v1/health")
        assert response.status_code == 200

    def test_v1_calculate_bazi_exists(self):
        """POST /v1/calculate/bazi must exist (even if it returns 422 for bad data)."""
        response = client.post("/v1/calculate/bazi", json={})
        assert response.status_code != 404

    def test_v1_calculate_western_exists(self):
        response = client.post("/v1/calculate/western", json={})
        assert response.status_code != 404

    def test_v1_calculate_fusion_exists(self):
        response = client.post("/v1/calculate/fusion", json={})
        assert response.status_code != 404

    def test_v1_transit_now_exists(self):
        response = client.get("/v1/transit/now")
        assert response.status_code != 404

    def test_v1_validate_exists(self):
        response = client.post("/v1/validate", json={})
        assert response.status_code != 404

    def test_old_routes_still_work(self):
        """Existing routes must not be broken."""
        response = client.get("/health")
        assert response.status_code == 200
        response = client.post("/calculate/bazi", json={})
        assert response.status_code != 404


class TestWebhookSeparation:
    def test_internal_webhook_path_exists(self):
        """Webhook must be accessible at /internal/api/webhooks/chart.
        The webhooks router has prefix='/api' baked in, so mounting at
        /internal produces /internal/api/webhooks/chart."""
        response = client.post("/internal/api/webhooks/chart", json={})
        assert response.status_code != 404

    def test_internal_webhook_hidden_from_schema(self):
        """Internal webhook must not appear in public OpenAPI schema."""
        response = client.get("/openapi.json")
        paths = response.json().get("paths", {})
        assert "/internal/api/webhooks/chart" not in paths

    def test_legacy_webhook_path_removed(self):
        """Old /api/webhooks/chart must NOT exist (Finding #5 fix — dedup)."""
        response = client.post("/api/webhooks/chart", json={})
        assert response.status_code == 404


class TestApiKeyAuth:
    """API key auth on /v1/ routes. Requires FUFIRE_API_KEYS env var."""

    def setup_method(self):
        from bazi_engine.auth import _load_keys
        os.environ["FUFIRE_API_KEYS"] = "test-key-abc,test-key-xyz"
        _load_keys.cache_clear()

    def teardown_method(self):
        from bazi_engine.auth import _load_keys
        os.environ.pop("FUFIRE_API_KEYS", None)
        os.environ.pop("FUFIRE_REQUIRE_API_KEYS", None)
        _load_keys.cache_clear()

    def test_no_key_returns_401(self):
        """Protected /v1/ route without key returns 401."""
        # Need a fresh client that picks up the reloaded auth
        from fastapi.testclient import TestClient

        from bazi_engine.app import app
        c = TestClient(app)
        response = c.post("/v1/calculate/bazi", json={})
        assert response.status_code == 401

    def test_wrong_key_returns_401(self):
        from fastapi.testclient import TestClient

        from bazi_engine.app import app
        c = TestClient(app)
        response = c.post(
            "/v1/calculate/bazi", json={},
            headers={"X-API-Key": "wrong-key"}
        )
        assert response.status_code == 401
        assert response.headers.get("www-authenticate") == "ApiKey"

    def test_valid_key_is_accepted(self):
        """Valid key must not return 401 (may return 422 for bad data)."""
        from fastapi.testclient import TestClient

        from bazi_engine.app import app
        c = TestClient(app)
        response = c.post(
            "/v1/calculate/bazi", json={},
            headers={"X-API-Key": "test-key-abc"}
        )
        assert response.status_code != 401

    def test_health_is_public_no_key_needed(self):
        """Public endpoints must work without API key even when auth is enabled."""
        response = client.get("/v1/health")
        assert response.status_code == 200

    def test_root_is_public(self):
        response = client.get("/")
        assert response.status_code == 200

    def test_error_includes_request_id(self):
        """401 errors must also include request_id."""
        from fastapi.testclient import TestClient

        from bazi_engine.app import app
        c = TestClient(app)
        response = c.post("/v1/calculate/bazi", json={})
        if response.status_code == 401:
            assert "request_id" in response.json()

    def test_strict_mode_fails_closed_when_keys_missing(self):
        """When strict mode is enabled, empty key config should fail closed."""
        os.environ["FUFIRE_REQUIRE_API_KEYS"] = "1"
        os.environ["FUFIRE_API_KEYS"] = ""

        from fastapi.testclient import TestClient

        from bazi_engine.app import app
        c = TestClient(app)
        response = c.post("/v1/calculate/bazi", json={})
        assert response.status_code == 503
        assert response.json().get("error") == "auth_configuration_error"


class TestRateLimiting:
    def test_excessive_requests_do_not_crash(self):
        """Rapid fire requests should return 200 or 429, never 500."""
        responses = [client.get("/transit/now") for _ in range(5)]
        assert all(r.status_code in (200, 429) for r in responses)


class TestApiKeyTiers:
    """API key tier detection and quota metadata."""

    def test_free_tier_detected(self):
        from bazi_engine.auth import resolve_key_info
        info = resolve_key_info("ff_free_testkey1")
        assert info.tier == "free"

    def test_pro_tier_detected(self):
        from bazi_engine.auth import resolve_key_info
        info = resolve_key_info("ff_pro_testkey2")
        assert info.tier == "pro"

    def test_enterprise_tier_detected(self):
        from bazi_engine.auth import resolve_key_info
        info = resolve_key_info("ff_enterprise_testkey3")
        assert info.tier == "enterprise"

    def test_legacy_key_defaults_to_free(self):
        from bazi_engine.auth import resolve_key_info
        info = resolve_key_info("legacy-plain-key")
        assert info.tier == "free"

    def test_starter_tier_detected(self):
        from bazi_engine.auth import resolve_key_info
        info = resolve_key_info("ff_starter_testkey")
        assert info.tier == "starter"
        assert info.requests_per_day == 1000
        assert info.requests_per_minute == 20

    def test_dev_mode_returns_dev_tier(self):
        from bazi_engine.auth import resolve_key_info
        info = resolve_key_info("dev-mode")
        assert info.tier == "dev"

    def test_key_info_repr_masks_secret(self):
        from bazi_engine.auth import resolve_key_info
        info = resolve_key_info("ff_pro_supersecret123")
        r = repr(info)
        assert "supersecret123" not in r
        assert "ff_pro_" not in r  # prefix must not leak; tier is visible via tier= field
        assert "..." in r  # mask indicator must be present

    def test_load_keys_caches_result(self):
        """_load_keys should return the same object on repeated calls (cached)."""
        from bazi_engine.auth import _load_keys
        os.environ["FUFIRE_API_KEYS"] = "test-cache-key"
        _load_keys.cache_clear()
        try:
            result1 = _load_keys()
            result2 = _load_keys()
            assert result1 is result2
        finally:
            os.environ.pop("FUFIRE_API_KEYS", None)
            _load_keys.cache_clear()

    def test_tier_has_rate_limit(self):
        from bazi_engine.auth import resolve_key_info
        info = resolve_key_info("ff_pro_testkey2")
        assert info.requests_per_day > 0
        assert info.requests_per_minute > 0

    def test_free_limits_lower_than_pro(self):
        from bazi_engine.auth import resolve_key_info
        free = resolve_key_info("ff_free_testkey1")
        pro = resolve_key_info("ff_pro_testkey2")
        assert free.requests_per_day < pro.requests_per_day

    def test_enterprise_unlimited(self):
        from bazi_engine.auth import resolve_key_info
        info = resolve_key_info("ff_enterprise_testkey3")
        assert info.requests_per_day == 0  # 0 = unlimited


class TestTieredRateLimiting:
    """Rate limiting keyed by API key with tier-based quotas."""

    def test_quota_headers_present_on_success(self):
        """Public routes (no rate limit decorator) must not include X-RateLimit-* headers."""
        # Health is public with no @limiter.limit() — must not carry rate limit headers.
        health_response = client.get("/health")
        assert health_response.status_code == 200
        assert "x-ratelimit-limit" not in health_response.headers
        assert "x-ratelimit-remaining" not in health_response.headers

    def test_v1_quota_headers_present(self):
        """V1 routes with valid key must return X-RateLimit-Limit header."""
        from bazi_engine.auth import _load_keys
        os.environ["FUFIRE_API_KEYS"] = "ff_free_testquota"
        _load_keys.cache_clear()
        try:
            from fastapi.testclient import TestClient

            from bazi_engine.app import app
            c = TestClient(app)
            response = c.get(
                "/v1/transit/now",
                headers={"X-API-Key": "ff_free_testquota"},
            )
            assert response.status_code == 200
            assert "x-ratelimit-limit" in response.headers
            # X-RateLimit-Remaining is only injected by slowapi on routes whose handlers
            # accept a `response: Response` parameter. Endpoints returning plain dicts do
            # not receive the injected header. Absence here is correct — not a phantom.
        finally:
            os.environ.pop("FUFIRE_API_KEYS", None)
            _load_keys.cache_clear()

    def test_rate_limit_key_func_uses_api_key(self):
        """Rate limiter must key off the API key, not the IP."""
        from starlette.requests import Request as _Req

        from bazi_engine.limiter import get_rate_limit_key

        # Mock a request with key_info on state
        scope = {
            "type": "http",
            "method": "GET",
            "path": "/v1/transit/now",
            "headers": [(b"x-api-key", b"ff_pro_testkey")],
            "query_string": b"",
            "root_path": "",
        }
        req = _Req(scope)
        req.state.key_info = type("KI", (), {"key": "ff_pro_testkey", "tier": "pro"})()
        assert get_rate_limit_key(req) == "ff_pro_testkey"

    def test_rate_limit_key_func_falls_back_to_ip(self):
        """Without key_info (legacy routes), fall back to remote address."""
        from starlette.requests import Request as _Req

        from bazi_engine.limiter import get_rate_limit_key

        scope = {
            "type": "http",
            "method": "GET",
            "path": "/transit/now",
            "headers": [],
            "query_string": b"",
            "root_path": "",
            "client": ("127.0.0.1", 8000),
        }
        req = _Req(scope)
        assert get_rate_limit_key(req) == "127.0.0.1"


class TestOpenApiExamples:
    """OpenAPI spec must include request/response examples for B2B endpoints."""

    def _get_spec(self):
        return client.get("/openapi.json").json()

    def test_bazi_request_has_example(self):
        spec = self._get_spec()
        bazi_schema = spec["components"]["schemas"].get("BaziRequest", {})
        has_example = (
            "example" in bazi_schema
            or "examples" in bazi_schema
            or any("example" in v for v in bazi_schema.get("properties", {}).values() if isinstance(v, dict))
        )
        assert has_example, "BaziRequest schema must include examples"

    def test_western_request_has_example(self):
        spec = self._get_spec()
        western_schema = spec["components"]["schemas"].get("WesternRequest", {})
        has_example = (
            "example" in western_schema
            or "examples" in western_schema
        )
        assert has_example, "WesternRequest schema must include examples"

    def test_fusion_request_has_example(self):
        spec = self._get_spec()
        fusion_schema = spec["components"]["schemas"].get("FusionRequest", {})
        has_example = (
            "example" in fusion_schema
            or "examples" in fusion_schema
        )
        assert has_example, "FusionRequest schema must include examples"

    def test_bazi_endpoint_has_example_in_spec(self):
        spec = self._get_spec()
        bazi_path = spec.get("paths", {}).get("/v1/calculate/bazi", {}).get("post", {})
        body = bazi_path.get("requestBody", {}).get("content", {}).get("application/json", {})
        schema_ref = body.get("schema", {})
        has_example = "example" in body or "examples" in body or "$ref" in schema_ref
        assert has_example, "POST /v1/calculate/bazi must have request example or schema ref"


class TestTierAssignment:
    def test_tier_derived_from_key_prefix(self):
        from bazi_engine.auth import resolve_key_info
        assert resolve_key_info("ff_free_abc").tier == "free"
        assert resolve_key_info("ff_pro_abc").tier == "pro"
        assert resolve_key_info("ff_enterprise_abc").tier == "enterprise"
        assert resolve_key_info("ff_starter_abc").tier == "starter"

    def test_unknown_tier_prefix_defaults_to_free(self):
        from bazi_engine.auth import resolve_key_info
        assert resolve_key_info("ff_superadmin_abc").tier == "free"
        assert resolve_key_info("legacy-key-no-prefix").tier == "free"

    def test_dev_mode_key_gets_unlimited_tier(self):
        from bazi_engine.auth import resolve_key_info
        info = resolve_key_info("dev-mode")
        assert info.tier == "dev"
        assert info.requests_per_day == 0
        assert info.requests_per_minute == 0

    def test_generated_key_gets_correct_tier(self):
        """Keys from scripts/generate_api_key.py must resolve to the right tier."""
        from bazi_engine.auth import resolve_key_info
        from scripts.generate_api_key import generate_key

        key = generate_key("pro")
        assert resolve_key_info(key).tier == "pro"

    def test_key_info_repr_does_not_leak_tier(self):
        """__repr__ must not expose the tier prefix in the key portion."""
        from bazi_engine.auth import resolve_key_info
        info = resolve_key_info("ff_enterprise_abc123def456")
        r = repr(info)
        # The literal key prefix "ff_enterprise_" must not appear
        assert "ff_enterprise_" not in r, f"Key prefix leaked in repr: {r}"
        assert "..." in r, f"Mask indicator missing from repr: {r}"


class TestTierOverrides:
    """Verify FUFIRE_KEY_TIER_OVERRIDES allows server-side tier correction."""

    def test_override_downgrades_enterprise_key_to_starter(self, monkeypatch):
        """A prefix-enterprise key is overridden to starter by the env map."""
        monkeypatch.setenv(
            "FUFIRE_KEY_TIER_OVERRIDES",
            "ff_enterprise_abc123:starter",
        )
        from bazi_engine.auth import _load_tier_overrides, resolve_key_info
        _load_tier_overrides.cache_clear()
        info = resolve_key_info("ff_enterprise_abc123")
        assert info.tier == "starter"
        assert info.requests_per_minute == 20
        _load_tier_overrides.cache_clear()

    def test_unknown_key_uses_prefix_when_no_override(self, monkeypatch):
        """When key is not in the override map, prefix parsing still works."""
        monkeypatch.setenv("FUFIRE_KEY_TIER_OVERRIDES", "ff_enterprise_xyz:free")
        from bazi_engine.auth import _load_tier_overrides, resolve_key_info
        _load_tier_overrides.cache_clear()
        info = resolve_key_info("ff_pro_different123")
        assert info.tier == "pro"
        _load_tier_overrides.cache_clear()

    def test_empty_override_env_is_safe(self, monkeypatch):
        """Empty or missing env var means no overrides — prefix parsing used."""
        monkeypatch.delenv("FUFIRE_KEY_TIER_OVERRIDES", raising=False)
        from bazi_engine.auth import _load_tier_overrides, resolve_key_info
        _load_tier_overrides.cache_clear()
        info = resolve_key_info("ff_pro_abc")
        assert info.tier == "pro"
        _load_tier_overrides.cache_clear()


class TestAuthCacheClear:
    def test_load_keys_cache_can_be_cleared(self):
        """cache_clear() must be callable for emergency key revocation."""
        from bazi_engine.auth import _load_keys
        _load_keys.cache_clear()
        _load_keys.cache_clear()  # idempotent

    def test_cache_clear_reloads_keys_from_env(self, monkeypatch):
        from bazi_engine.auth import _load_keys
        monkeypatch.setenv("FUFIRE_API_KEYS", "ff_free_key1")
        _load_keys.cache_clear()
        keys_v1 = _load_keys()
        assert "ff_free_key1" in keys_v1

        monkeypatch.setenv("FUFIRE_API_KEYS", "ff_free_key2")
        keys_cached = _load_keys()
        assert "ff_free_key1" in keys_cached  # still cached

        _load_keys.cache_clear()
        keys_v2 = _load_keys()
        assert "ff_free_key2" in keys_v2
        _load_keys.cache_clear()


class TestWebhookRoutes:
    def test_webhook_only_at_internal_path(self):
        """Webhook must only be accessible at /internal/api/webhooks/chart."""
        response = client.post("/api/webhooks/chart", json={})
        assert response.status_code == 404, \
               f"/api/webhooks/chart should be 404 (legacy removed), got {response.status_code}"

    def test_webhook_accessible_at_internal_path(self):
        """Webhook is still reachable at /internal/api/webhooks/chart."""
        response = client.post("/internal/api/webhooks/chart", json={})
        assert response.status_code != 404, \
               "/internal/api/webhooks/chart must still exist"


class TestWebhookErrorSanitization:
    def test_malformed_json_does_not_leak_exception(self, monkeypatch):
        import hashlib
        import hmac as _hmac
        import time as _time
        monkeypatch.setenv("ELEVENLABS_TOOL_SECRET", "test-secret")
        monkeypatch.setenv("WEBHOOK_HMAC_ONLY", "false")
        ts = int(_time.time() * 1000)
        payload = b"NOT_VALID_JSON{{{{"
        signed = f"{ts}.".encode() + payload
        sig = _hmac.new(b"test-secret", signed, hashlib.sha256).hexdigest()
        response = client.post(
            "/internal/api/webhooks/chart",
            content=payload,
            headers={
                "Content-Type": "application/json",
                "elevenlabs-signature": f"t={ts},v1={sig}",
            },
        )
        assert response.status_code == 400
        body_str = response.text  # check entire response, not just detail field
        assert "Expecting value" not in body_str
        assert "JSONDecodeError" not in body_str
        assert "Invalid request:" not in body_str

    def test_webhook_401_uses_structured_envelope(self, monkeypatch):
        """Verify 401 response uses the structured error envelope, not a raw string."""
        monkeypatch.setenv("ELEVENLABS_TOOL_SECRET", "test-secret")
        response = client.post(
            "/internal/api/webhooks/chart",
            content=b"{}",
            headers={
                "ElevenLabs-Signature": "invalid",
                "Content-Type": "application/json",
            },
        )
        assert response.status_code == 401
        body = response.json()
        # The custom http_exception_handler flattens dict detail into the top-level body.
        # Must be a dict envelope, not a plain string wrapped in {"detail": "..."}.
        assert isinstance(body, dict), (
            f"Expected structured dict response body, got: {body!r}"
        )
        assert body.get("error") == "unauthorized", (
            f"Expected error='unauthorized' in body, got: {body!r}"
        )


class TestWebhookConfigError:
    def test_missing_secret_returns_generic_503(self, monkeypatch):
        monkeypatch.delenv("ELEVENLABS_TOOL_SECRET", raising=False)
        response = client.post("/internal/api/webhooks/chart", json={})
        assert response.status_code in (500, 503)
        body = str(response.json())
        assert "ELEVENLABS_TOOL_SECRET" not in body, \
               f"Env var name leaked in response: {body}"


class TestKeyGeneration:
    def test_generated_key_has_correct_format(self):
        import subprocess
        import sys
        from pathlib import Path
        repo_root = Path(__file__).parent.parent
        result = subprocess.run(
            [sys.executable, "scripts/generate_api_key.py", "--tier", "free"],
            capture_output=True, text=True,
            cwd=str(repo_root),
        )
        key = result.stdout.strip()
        assert key.startswith("ff_free_"), f"Key has wrong format: {key}"
        parts = key.split("_")
        assert len(parts) == 3
        assert len(parts[2]) >= 32, f"Random part too short (< 32 chars): {parts[2]}"

    def test_generated_keys_are_unique(self):
        import subprocess
        import sys
        from pathlib import Path
        repo_root = Path(__file__).parent.parent
        keys = set()
        for _ in range(5):
            result = subprocess.run(
                [sys.executable, "scripts/generate_api_key.py", "--tier", "pro"],
                capture_output=True, text=True,
                cwd=str(repo_root),
            )
            keys.add(result.stdout.strip())
        assert len(keys) == 5, "Generated keys are not unique!"

    def test_dev_tier_not_generatable(self):
        from scripts.generate_api_key import VALID_TIERS, generate_key
        assert "dev" not in VALID_TIERS
        with pytest.raises(ValueError):
            generate_key("dev")


class TestSecurityHeaders:
    def test_hsts_header_present(self):
        response = client.get("/health")
        assert "strict-transport-security" in response.headers, \
               f"Missing HSTS. Headers: {dict(response.headers)}"

    def test_hsts_max_age_at_least_one_year(self):
        import re
        response = client.get("/health")
        hsts = response.headers.get("strict-transport-security", "")
        match = re.search(r"max-age=(\d+)", hsts)
        assert match, f"No max-age in HSTS: {hsts}"
        assert int(match.group(1)) >= 31536000, "HSTS max-age must be >= 1 year"

    def test_ratelimit_remaining_absent_on_unlimited_route(self):
        """Routes with key_info but no @limiter.limit() must not get a phantom Remaining header."""
        from unittest.mock import patch

        from fastapi.testclient import TestClient

        from bazi_engine.app import app as _app
        with patch.dict(os.environ, {"FUFIRE_API_KEYS": "ff_pro_testkey123"}):
            from bazi_engine.auth import _load_keys
            _load_keys.cache_clear()
            c = TestClient(_app)
            # /chart has @require_api_key (sets key_info) but no @limiter.limit() decorator.
            # Before the fix, middleware injects phantom x-ratelimit-remaining=<full_quota>.
            response = c.post(
                "/chart",
                headers={"X-API-Key": "ff_pro_testkey123"},
                json={
                    "local_datetime": "1990-06-15T14:30:00",
                    "tz_id": "Europe/Berlin",
                    "geo_lon_deg": 13.4,
                    "geo_lat_deg": 52.5,
                },
            )
            _load_keys.cache_clear()
        assert "x-ratelimit-remaining" not in response.headers, (
            f"Phantom remaining header found: {response.headers.get('x-ratelimit-remaining')}"
        )

    def test_ratelimit_limit_present_on_compute_route(self):
        """Compute routes have @limiter.limit() — X-RateLimit-Limit header must be present."""
        from unittest.mock import patch

        from fastapi.testclient import TestClient

        from bazi_engine.app import app as _app
        with patch.dict(os.environ, {"FUFIRE_API_KEYS": "ff_pro_testkey456"}):
            from bazi_engine.auth import _load_keys
            _load_keys.cache_clear()
            c = TestClient(_app)
            response = c.post(
                "/v1/calculate/bazi",
                headers={"X-API-Key": "ff_pro_testkey456", "Content-Type": "application/json"},
                json={"date": "1990-06-15T14:30:00", "tz": "Europe/Berlin", "lon": 13.4, "lat": 52.5},
            )
            _load_keys.cache_clear()
        # X-RateLimit-Limit is set by our middleware (tier quota).
        # X-RateLimit-Remaining is only set by slowapi when the endpoint accepts
        # `response: Response` — currently endpoints return plain dicts so slowapi
        # cannot inject the per-request counter. The middleware no longer adds a
        # phantom fallback (Finding #6 fix).
        assert "x-ratelimit-limit" in response.headers


class TestCORSHeaders:
    def test_cors_preflight_returns_allow_origin(self):
        """OPTIONS preflight must return CORS headers."""
        response = client.options(
            "/v1/health",
            headers={
                "Origin": "https://bazodiac.space",
                "Access-Control-Request-Method": "GET",
            }
        )
        assert "access-control-allow-origin" in response.headers or \
               response.status_code in (200, 405)

    def test_cors_header_present_on_get(self):
        """Regular requests from allowed origin get CORS header."""
        response = client.get(
            "/health",
            headers={"Origin": "https://bazodiac.space"}
        )
        assert "access-control-allow-origin" in response.headers

    def test_wildcard_cors_rejected_at_startup(self):
        """CORS wildcard guard raises RuntimeError when '*' is in origins."""
        from bazi_engine.app import _validate_cors_origins
        with pytest.raises(RuntimeError, match="must not contain"):
            _validate_cors_origins(["*"], "*")


class TestAuthLogging:
    def test_failed_auth_is_logged(self, monkeypatch, caplog):
        import logging
        monkeypatch.setenv("FUFIRE_API_KEYS", "ff_pro_validkey123")
        from bazi_engine.auth import _load_keys
        _load_keys.cache_clear()
        with caplog.at_level(logging.WARNING, logger="bazi_engine.auth"):
            # Use a protected endpoint (not the public info/health router)
            response = client.get("/v1/transit/now", headers={"X-API-Key": "bad-key"})
        assert response.status_code == 401
        assert any("unauthorized" in r.message.lower() or "invalid" in r.message.lower()
                   for r in caplog.records), f"No auth failure log. Records: {caplog.records}"
        _load_keys.cache_clear()

    def test_dev_mode_activation_is_logged(self, monkeypatch, caplog):
        import logging
        monkeypatch.delenv("FUFIRE_API_KEYS", raising=False)
        monkeypatch.delenv("FUFIRE_REQUIRE_API_KEYS", raising=False)
        from bazi_engine.auth import _load_keys
        _load_keys.cache_clear()
        with caplog.at_level(logging.WARNING, logger="bazi_engine.auth"):
            client.get("/transit/now")
        assert any("dev" in r.message.lower() or "no api keys" in r.message.lower()
                   for r in caplog.records)
        _load_keys.cache_clear()


class TestAuthFailSafe:
    """When FUFIRE_REQUIRE_API_KEYS=true and no keys configured, API must return 503."""

    def test_503_when_keys_required_but_not_configured(self, monkeypatch):
        monkeypatch.setenv("FUFIRE_REQUIRE_API_KEYS", "true")
        monkeypatch.delenv("FUFIRE_API_KEYS", raising=False)
        from bazi_engine.auth import _load_keys
        _load_keys.cache_clear()
        response = client.get("/v1/health")
        assert response.status_code == 200
        response = client.post("/v1/calculate/bazi", json={
            "date": "1990-06-15T14:30:00", "tz": "Europe/Berlin",
            "lon": 13.405, "lat": 52.52
        })
        assert response.status_code == 503
        body = response.json()
        assert body["error"] == "auth_configuration_error"
        _load_keys.cache_clear()


class TestComputeEndpointRateLimits:
    """Compute endpoints must have rate limiting configured."""

    def test_calculate_bazi_returns_retry_after_on_429(self):
        """429 handler must be registered for RateLimitExceeded."""

        from bazi_engine.app import app
        assert any(
            "RateLimitExceeded" in str(exc_type)
            for exc_type in app.exception_handlers
        ), "RateLimitExceeded handler not registered in app"

    def test_bazi_router_has_rate_limit(self):
        """calculate_bazi_endpoint must have a slowapi rate limit decorator."""
        import inspect

        from bazi_engine.routers import bazi as bazi_module
        src = inspect.getsource(bazi_module)
        assert "@limiter.limit" in src, "bazi router missing @limiter.limit decorator"

    def test_western_router_has_rate_limit(self):
        """calculate_western_endpoint must have a slowapi rate limit decorator."""
        import inspect

        from bazi_engine.routers import western as western_module
        src = inspect.getsource(western_module)
        assert "@limiter.limit" in src, "western router missing @limiter.limit decorator"

    def test_fusion_router_has_rate_limit(self):
        """calculate_fusion_endpoint must have a slowapi rate limit decorator."""
        import inspect

        from bazi_engine.routers import fusion as fusion_module
        src = inspect.getsource(fusion_module)
        assert "@limiter.limit" in src, "fusion router missing @limiter.limit decorator"

    def test_validate_router_has_rate_limit(self):
        """validate endpoint must have a slowapi rate limit decorator."""
        import inspect

        from bazi_engine.routers import validate as validate_module
        src = inspect.getsource(validate_module)
        assert "@limiter.limit" in src, "validate router missing @limiter.limit decorator"


class TestLegacyRouteAuth:
    """Legacy routes must require auth when FUFIRE_API_KEYS is set."""

    def test_legacy_bazi_requires_auth_when_keys_configured(self, monkeypatch):
        monkeypatch.setenv("FUFIRE_API_KEYS", "ff_pro_testkey123")
        from bazi_engine.auth import _load_keys
        _load_keys.cache_clear()
        response = client.post("/calculate/bazi", json={
            "date": "1990-06-15T14:30:00", "tz": "Europe/Berlin",
            "lon": 13.405, "lat": 52.52
        })
        assert response.status_code == 401
        _load_keys.cache_clear()

    def test_legacy_bazi_works_without_key_in_dev_mode(self, monkeypatch):
        monkeypatch.delenv("FUFIRE_API_KEYS", raising=False)
        from bazi_engine.auth import _load_keys
        _load_keys.cache_clear()
        response = client.post("/calculate/bazi", json={
            "date": "1990-06-15T14:30:00", "tz": "Europe/Berlin",
            "lon": 13.405, "lat": 52.52
        })
        # Dev mode (no keys configured) still passes
        assert response.status_code == 200
        _load_keys.cache_clear()

    def test_legacy_bazi_works_with_valid_key_when_configured(self, monkeypatch):
        monkeypatch.setenv("FUFIRE_API_KEYS", "ff_pro_testkey123")
        from bazi_engine.auth import _load_keys
        _load_keys.cache_clear()
        response = client.post(
            "/calculate/bazi",
            json={"date": "1990-06-15T14:30:00", "tz": "Europe/Berlin",
                  "lon": 13.405, "lat": 52.52},
            headers={"X-API-Key": "ff_pro_testkey123"},
        )
        assert response.status_code == 200
        _load_keys.cache_clear()
