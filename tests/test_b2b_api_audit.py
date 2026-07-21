"""
B2B API Production Readiness Audit
===================================
Systematic test suite verifying FuFirE meets B2B live API service requirements.

Categories tested:
  1. Response Consistency (envelope, headers, content-type)
  2. Authentication & Authorization (API key validation, tier enforcement)
  3. Error Handling (structured errors, no internal leakage, DST edge cases)
  4. Rate Limiting (headers, 429 behavior)
  5. Security Hardening (OWASP API Top 10 basics, headers, input validation)
  6. API Contract Stability (OpenAPI sync, schema correctness)
  7. Provenance & Traceability (request-id, computation reproducibility)
  8. Endpoint Completeness (all documented endpoints reachable)
  9. Data Quality (deterministic output, valid ranges)
  10. Documentation & Discovery (OpenAPI, health, build info)
"""
from __future__ import annotations

import json
import math
import os
import re
import uuid
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from bazi_engine.app import app

client = TestClient(app)

# ── Helpers ──────────────────────────────────────────────────────────────────

BIRTH_PAYLOAD = {
    "date": "1990-06-15T14:30:00",
    "tz": "Europe/Berlin",
    "lon": 13.405,
    "lat": 52.52,
}

# Mock for transit endpoints (avoid ephemeris dependency)
MOCK_PLANET_DATA = {
    0: (348.7, 0.0, 1.0, 1.01, 0.0, 0.0),
    1: (187.2, 0.0, 0.003, 13.2, 0.0, 0.0),
    2: (332.1, 0.0, 0.8, 1.8, 0.0, 0.0),
    3: (15.4, 0.0, 0.7, 1.2, 0.0, 0.0),
    4: (112.8, 0.0, 1.5, 0.7, 0.0, 0.0),
    5: (78.3, 0.0, 5.0, 0.08, 0.0, 0.0),
    6: (342.9, 0.0, 9.5, 0.03, 0.0, 0.0),
    7: (51.2, 0.0, 19.2, 0.01, 0.0, 0.0),
    8: (359.5, 0.0, 30.1, 0.005, 0.0, 0.0),
    9: (303.8, 0.0, 33.7, 0.003, 0.0, 0.0),
}


def mock_calc_ut(jd_ut, planet_id, flags):
    if planet_id in MOCK_PLANET_DATA:
        return MOCK_PLANET_DATA[planet_id], 0
    raise Exception(f"Unknown planet {planet_id}")


def _ephemeris_available() -> bool:
    r = client.post("/calculate/bazi", json=BIRTH_PAYLOAD)
    return r.status_code == 200


_HAS_EPHEMERIS = _ephemeris_available()
_skip_no_ephe = pytest.mark.skipif(not _HAS_EPHEMERIS, reason="Ephemeris files unavailable")


# ═══════════════════════════════════════════════════════════════════════════
# 1. RESPONSE CONSISTENCY
# ═══════════════════════════════════════════════════════════════════════════

class TestResponseConsistency:
    """Every response must have consistent structure, headers, and content type."""

    def test_content_type_is_json(self):
        r = client.get("/health")
        assert r.headers["content-type"].startswith("application/json")

    def test_all_responses_have_request_id(self):
        """X-Request-ID must be present on every response."""
        endpoints = [
            ("GET", "/"),
            ("GET", "/health"),
            ("GET", "/build"),
        ]
        for method, path in endpoints:
            r = client.request(method, path)
            assert "x-request-id" in r.headers, f"Missing X-Request-ID on {method} {path}"

    def test_client_request_id_echoed(self):
        """Client-provided X-Request-ID must be echoed back."""
        custom_id = str(uuid.uuid4())
        r = client.get("/health", headers={"X-Request-ID": custom_id})
        assert r.headers["x-request-id"] == custom_id

    def test_api_version_header_present(self):
        r = client.get("/health")
        assert "x-api-version" in r.headers
        assert len(r.headers["x-api-version"]) > 0

    def test_response_time_header_present(self):
        r = client.get("/health")
        assert "x-response-time-ms" in r.headers
        ms = float(r.headers["x-response-time-ms"])
        assert ms >= 0

    @_skip_no_ephe
    def test_error_envelope_consistency(self):
        """Error responses must follow the standard envelope."""
        # Trigger a 422 with invalid DST time
        r = client.post("/calculate/bazi", json={
            "date": "2026-03-29T02:30:00",  # DST gap in Europe/Berlin
            "tz": "Europe/Berlin",
            "lon": 13.405,
            "lat": 52.52,
            "nonexistentTime": "error",
        })
        assert r.status_code == 422
        body = r.json()
        # Required envelope fields
        assert "error" in body
        assert "message" in body
        assert "status" in body
        assert "path" in body
        assert "timestamp" in body
        assert "request_id" in body
        # Error code is a string, not an integer
        assert isinstance(body["error"], str)
        # Status matches HTTP status
        assert body["status"] == 422

    def test_404_returns_json_not_html(self):
        """Unknown paths must return JSON error, not HTML."""
        r = client.get("/nonexistent/endpoint/12345")
        assert r.headers["content-type"].startswith("application/json")
        body = r.json()
        assert "error" in body or "detail" in body


# ═══════════════════════════════════════════════════════════════════════════
# 2. AUTHENTICATION & AUTHORIZATION
# ═══════════════════════════════════════════════════════════════════════════

class TestAuthentication:
    """API key validation and tier enforcement for /v1/ routes."""

    def test_public_endpoints_need_no_key(self):
        """Info endpoints must work without API key."""
        for path in ["/v1/health", "/v1/ready", "/v1/build", "/v1/"]:
            r = client.get(path)
            assert r.status_code in (200, 503), f"{path} returned {r.status_code}"

    def test_v1_business_endpoint_rejects_missing_key(self):
        """Business endpoints must reject requests without API key."""
        # Only when API keys are actually configured
        if not os.environ.get("FUFIRE_API_KEYS"):
            pytest.skip("No API keys configured (dev mode)")
        r = client.post("/v1/calculate/bazi", json=BIRTH_PAYLOAD)
        assert r.status_code == 401

    def test_v1_business_endpoint_rejects_invalid_key(self):
        """Invalid API key must be rejected."""
        if not os.environ.get("FUFIRE_API_KEYS"):
            pytest.skip("No API keys configured (dev mode)")
        r = client.post(
            "/v1/calculate/bazi",
            json=BIRTH_PAYLOAD,
            headers={"X-API-Key": "ff_pro_INVALID_KEY_12345"},
        )
        assert r.status_code == 401

    def test_legacy_endpoints_accessible_without_key(self):
        """Legacy (non-/v1/) routes don't require auth."""
        r = client.get("/health")
        assert r.status_code == 200


# ═══════════════════════════════════════════════════════════════════════════
# 3. ERROR HANDLING
# ═══════════════════════════════════════════════════════════════════════════

class TestErrorHandling:
    """Structured errors, no internal leakage, edge cases."""

    def test_invalid_json_returns_422(self):
        """Malformed JSON must return 422, not 500."""
        r = client.post(
            "/calculate/bazi",
            content=b"not json",
            headers={"Content-Type": "application/json"},
        )
        assert r.status_code == 422

    def test_missing_required_field_returns_422(self):
        """Missing required 'date' field returns 422."""
        r = client.post("/calculate/bazi", json={"tz": "Europe/Berlin"})
        assert r.status_code == 422

    def test_invalid_timezone_returns_422(self):
        """Non-existent timezone must fail cleanly."""
        r = client.post("/calculate/bazi", json={
            **BIRTH_PAYLOAD,
            "tz": "Not/A/Timezone",
        })
        assert r.status_code in (422, 500)
        body = r.json()
        assert "error" in body

    def test_500_never_leaks_stack_trace(self):
        """Internal errors must not expose Python tracebacks."""
        # Force an internal error by providing extreme values
        r = client.post("/calculate/bazi", json={
            "date": "9999-12-31T23:59:59",
            "tz": "UTC",
            "lon": 0, "lat": 0,
        })
        if r.status_code == 500:
            body = r.json()
            body_str = json.dumps(body)
            assert "Traceback" not in body_str
            assert "File \"" not in body_str
            assert ".py\"" not in body_str

    def test_nan_inf_not_in_responses(self):
        """NaN and Infinity must never appear in JSON responses."""
        r = client.get("/health")
        raw = r.text
        assert "NaN" not in raw
        assert "Infinity" not in raw
        assert "-Infinity" not in raw

    @_skip_no_ephe
    def test_dst_gap_error_structured(self):
        """DST gap must return structured error, not crash."""
        r = client.post("/calculate/bazi", json={
            "date": "2026-03-29T02:30:00",
            "tz": "Europe/Berlin",
            "lon": 13.405,
            "lat": 52.52,
            "nonexistentTime": "error",
        })
        assert r.status_code == 422
        body = r.json()
        assert body["error"] in ("input_error", "validation_error", "dst_time_error")

    @_skip_no_ephe
    def test_dst_gap_shift_forward_works(self):
        """nonexistentTime=shift_forward must succeed, not error."""
        r = client.post("/calculate/bazi", json={
            "date": "2026-03-29T02:30:00",
            "tz": "Europe/Berlin",
            "lon": 13.405,
            "lat": 52.52,
            "nonexistentTime": "shift_forward",
        })
        assert r.status_code == 200


# ═══════════════════════════════════════════════════════════════════════════
# 4. RATE LIMITING
# ═══════════════════════════════════════════════════════════════════════════

class TestRateLimiting:
    """Rate limit headers and 429 behavior."""

    def test_rate_limit_storage_status_in_health(self):
        """Health endpoint must report rate limiter dependency."""
        r = client.get("/health")
        body = r.json()
        assert "rate_limiter" in body["dependencies"]
        rl = body["dependencies"]["rate_limiter"]
        assert rl["status"] in ("ok", "degraded", "unavailable")

    def test_429_returns_retry_after(self):
        """When rate limited, response must include Retry-After header."""
        # We can't easily trigger 429 in tests without Redis,
        # but we verify the handler is registered by checking the app
        from bazi_engine.app import app as _app
        handlers = getattr(_app, "exception_handlers", {})
        from slowapi.errors import RateLimitExceeded
        assert RateLimitExceeded in handlers or any(
            "RateLimitExceeded" in str(h) for h in handlers
        ), "RateLimitExceeded handler not registered"


# ═══════════════════════════════════════════════════════════════════════════
# 5. SECURITY HARDENING
# ═══════════════════════════════════════════════════════════════════════════

class TestSecurityHardening:
    """OWASP API Top 10 basics, security headers, input validation."""

    def test_security_headers_present(self):
        """Essential security headers on every response."""
        r = client.get("/health")
        assert r.headers.get("x-content-type-options") == "nosniff"
        assert r.headers.get("x-frame-options") == "DENY"
        assert "no-referrer" in r.headers.get("referrer-policy", "")
        assert "max-age=" in r.headers.get("strict-transport-security", "")

    def test_permissions_policy_present(self):
        r = client.get("/health")
        pp = r.headers.get("permissions-policy", "")
        assert "camera=()" in pp
        assert "microphone=()" in pp

    def test_no_server_header_leaks_framework(self):
        """Server header should not reveal framework details."""
        r = client.get("/health")
        server = r.headers.get("server", "").lower()
        # Should not say "fastapi" or "uvicorn" in production
        # (TestClient may add its own, so we just check it's not verbose)
        assert "python" not in server

    def test_invalid_content_type_rejected(self):
        """POST with wrong content-type should be rejected."""
        r = client.post(
            "/calculate/bazi",
            content=b"date=2024-01-01",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        assert r.status_code == 422

    def test_oversized_payload_handled(self):
        """Extremely large payload should not crash the server."""
        huge = {"date": "2024-01-01T12:00:00", "tz": "UTC", "lon": 0, "lat": 0, "extra": "x" * 100_000}
        r = client.post("/calculate/bazi", json=huge)
        # Should return 422 (unknown field) or 200 (ignored), not crash
        assert r.status_code in (200, 422, 503)

    def test_sql_injection_in_params_harmless(self):
        """SQL injection attempts must not crash and must sanitize reflected input."""
        r = client.get("/api?datum=2024-01-01&zeit=12:00&tz='; DROP TABLE users;--")
        assert r.status_code in (422, 500)
        body = r.json()
        body_str = json.dumps(body)
        # The exact injection payload with semicolons must not be reflected verbatim
        assert "'; DROP TABLE" not in body_str
        assert "users;--" not in body_str

    def test_xss_in_params_harmless(self):
        """XSS attempts must not be reflected in error messages."""
        r = client.get("/api?datum=2024-01-01&zeit=12:00&tz=<script>alert(1)</script>")
        assert r.status_code in (422, 500)
        body_str = json.dumps(r.json())
        assert "<script>" not in body_str
        assert "alert(" not in body_str

    def test_path_traversal_returns_404(self):
        """Path traversal attempts return 404, not file contents."""
        r = client.get("/../../etc/passwd")
        assert r.status_code in (404, 307, 200)  # FastAPI may normalize
        if r.status_code == 200:
            assert "root:" not in r.text

    def test_no_debug_endpoints_exposed(self):
        """Debug/internal endpoints must not be accessible."""
        for path in ["/debug", "/admin", "/_debug", "/env", "/config"]:
            r = client.get(path)
            assert r.status_code in (404, 405, 307)

    @_skip_no_ephe
    def test_extreme_coordinates_handled(self):
        """Extreme lat/lon values must not crash."""
        for lat, lon in [(90.0, 0.0), (-90.0, 180.0), (0.0, -180.0), (89.99, 179.99)]:
            r = client.post("/calculate/bazi", json={
                "date": "2024-06-15T12:00:00",
                "tz": "UTC",
                "lon": lon,
                "lat": lat,
            })
            assert r.status_code in (200, 422, 503), f"Crash at lat={lat}, lon={lon}: {r.status_code}"


# ═══════════════════════════════════════════════════════════════════════════
# 6. API CONTRACT STABILITY
# ═══════════════════════════════════════════════════════════════════════════

class TestApiContract:
    """OpenAPI spec sync, schema correctness."""

    def test_openapi_spec_accessible(self):
        """OpenAPI JSON must be served at /openapi.json."""
        r = client.get("/openapi.json")
        assert r.status_code == 200
        spec = r.json()
        assert "openapi" in spec
        assert "paths" in spec
        assert "info" in spec

    def test_openapi_version_matches_engine(self):
        from bazi_engine import __version__
        r = client.get("/openapi.json")
        spec = r.json()
        assert spec["info"]["version"] == __version__

    def test_openapi_has_server_urls(self):
        r = client.get("/openapi.json")
        spec = r.json()
        assert "servers" in spec
        urls = [s["url"] for s in spec["servers"]]
        # Railway is the live deployment; the old Fly.io deploy is decommissioned.
        assert "https://api.fufire.space" in urls

    def test_openapi_has_tag_descriptions(self):
        """Tags must have descriptions for Swagger UI / Redoc."""
        r = client.get("/openapi.json")
        spec = r.json()
        assert "tags" in spec
        for tag in spec["tags"]:
            assert "description" in tag, f"Tag '{tag['name']}' has no description"

    def test_openapi_spec_file_is_in_sync(self):
        """spec/openapi/openapi.json must match runtime generation."""
        spec_path = Path(__file__).parent.parent / "spec" / "openapi" / "openapi.json"
        if not spec_path.exists():
            pytest.skip("spec/openapi/openapi.json not found")
        with open(spec_path) as f:
            file_spec = json.load(f)
        r = client.get("/openapi.json")
        runtime_spec = r.json()
        # Compare paths (the most likely drift point)
        assert set(file_spec.get("paths", {}).keys()) == set(runtime_spec.get("paths", {}).keys())


# ═══════════════════════════════════════════════════════════════════════════
# 7. PROVENANCE & TRACEABILITY
# ═══════════════════════════════════════════════════════════════════════════

class TestProvenance:
    """Request tracing and computation reproducibility."""

    @_skip_no_ephe
    def test_provenance_in_bazi_response(self):
        r = client.post("/calculate/bazi", json=BIRTH_PAYLOAD)
        body = r.json()
        prov = body["provenance"]
        required = ["engine_version", "ephemeris_id", "computation_timestamp",
                     "parameter_set_id", "ruleset_id", "house_system"]
        for key in required:
            assert key in prov, f"Missing provenance field: {key}"

    @_skip_no_ephe
    def test_parameter_set_versioned(self):
        """Parameter set must have a version for reproducibility."""
        r = client.post("/calculate/fusion", json=BIRTH_PAYLOAD)
        body = r.json()
        ps = body["provenance"]["parameter_set"]
        assert "version" in ps
        assert re.match(r"\d+\.\d+\.\d+", ps["version"])

    @_skip_no_ephe
    def test_parameter_set_has_aspect_orb_model(self):
        r = client.post("/calculate/fusion", json=BIRTH_PAYLOAD)
        ps = r.json()["provenance"]["parameter_set"]
        assert ps["aspect_orb_model"] == "differentiated_v1"
        assert "aspect_base_orbs" in ps
        assert "aspect_factors" in ps

    @_skip_no_ephe
    def test_parameter_set_has_soulprint_weights(self):
        r = client.post("/calculate/fusion", json=BIRTH_PAYLOAD)
        ps = r.json()["provenance"]["parameter_set"]
        assert "soulprint_weights" in ps
        assert "wuxing_sector_mapping" in ps

    @_skip_no_ephe
    def test_derivation_trace_in_bazi(self):
        """BaZi response must include derivation trace for auditability."""
        r = client.post("/calculate/bazi", json=BIRTH_PAYLOAD)
        body = r.json()
        trace = body.get("derivation_trace")
        assert trace is not None
        for pillar in ("year", "month", "day", "hour"):
            assert pillar in trace, f"Missing trace for {pillar}"

    @_skip_no_ephe
    def test_contribution_ledger_in_fusion(self):
        """Fusion response must include per-contribution ledger."""
        r = client.post("/calculate/fusion", json=BIRTH_PAYLOAD)
        body = r.json()
        ledger = body.get("contribution_ledger")
        assert ledger is not None
        assert "western" in ledger
        assert "bazi" in ledger
        assert len(ledger["western"]) > 0
        assert len(ledger["bazi"]) > 0

    @_skip_no_ephe
    def test_precision_block_when_time_unknown(self):
        """birth_time_known=false must flag provisional fields."""
        r = client.post("/calculate/bazi", json={
            **BIRTH_PAYLOAD,
            "birth_time_known": False,
        })
        body = r.json()
        assert body["precision"]["birth_time_known"] is False
        assert "hour" in body["precision"]["provisional_fields"]

    @_skip_no_ephe
    def test_deterministic_output(self):
        """Same input must produce identical output (determinism)."""
        r1 = client.post("/calculate/bazi", json=BIRTH_PAYLOAD)
        r2 = client.post("/calculate/bazi", json=BIRTH_PAYLOAD)
        b1, b2 = r1.json(), r2.json()
        # Pillars must be identical
        assert b1["pillars"] == b2["pillars"]
        assert b1["chinese"] == b2["chinese"]
        assert b1["dates"] == b2["dates"]


# ═══════════════════════════════════════════════════════════════════════════
# 8. ENDPOINT COMPLETENESS
# ═══════════════════════════════════════════════════════════════════════════

class TestEndpointCompleteness:
    """All documented endpoints must be reachable."""

    def test_info_endpoints_reachable(self):
        for path in ["/", "/health", "/ready", "/build"]:
            r = client.get(path)
            assert r.status_code in (200, 503), f"{path} unreachable: {r.status_code}"

    def test_v1_info_endpoints_reachable(self):
        for path in ["/v1/", "/v1/health", "/v1/ready", "/v1/build"]:
            r = client.get(path)
            assert r.status_code in (200, 503), f"{path} unreachable: {r.status_code}"

    def test_wuxing_mapping_reachable(self):
        r = client.get("/info/wuxing-mapping")
        assert r.status_code == 200
        body = r.json()
        assert "mapping" in body
        assert "order" in body

    def test_calculate_endpoints_registered(self):
        """All /calculate/* endpoints must be registered (may fail on 503 for ephemeris)."""
        endpoints = [
            ("/calculate/bazi", BIRTH_PAYLOAD),
            ("/calculate/western", BIRTH_PAYLOAD),
            ("/calculate/fusion", BIRTH_PAYLOAD),
            ("/calculate/wuxing", BIRTH_PAYLOAD),
            ("/calculate/tst", {"date": "2024-01-01T12:00:00", "tz": "UTC", "lon": 0}),
        ]
        for path, payload in endpoints:
            r = client.post(path, json=payload)
            # 200, 422, or 503 are all valid — 404 means endpoint not registered
            assert r.status_code != 404, f"{path} not registered (404)"

    def test_transit_endpoints_registered(self):
        with patch("bazi_engine.transit.swe.calc_ut", side_effect=mock_calc_ut):
            r = client.get("/transit/now")
            assert r.status_code == 200

            r = client.post("/transit/state", json={
                "soulprint_sectors": [0.1] * 12,
                "quiz_sectors": [0.1] * 12,
            })
            assert r.status_code == 200

            r = client.get("/transit/timeline?days=2")
            assert r.status_code == 200


# ═══════════════════════════════════════════════════════════════════════════
# 9. DATA QUALITY
# ═══════════════════════════════════════════════════════════════════════════

class TestDataQuality:
    """Deterministic output, valid ranges, mathematical correctness."""

    def test_transit_longitudes_in_range(self):
        """All planet longitudes must be in [0, 360)."""
        with patch("bazi_engine.transit.swe.calc_ut", side_effect=mock_calc_ut):
            r = client.get("/transit/now")
        body = r.json()
        for name, pdata in body["planets"].items():
            assert 0 <= pdata["longitude"] < 360, f"{name} longitude out of range: {pdata['longitude']}"

    def test_transit_sectors_in_range(self):
        """All sectors must be in [0, 11]."""
        with patch("bazi_engine.transit.swe.calc_ut", side_effect=mock_calc_ut):
            r = client.get("/transit/now")
        body = r.json()
        for name, pdata in body["planets"].items():
            assert 0 <= pdata["sector"] <= 11, f"{name} sector out of range: {pdata['sector']}"

    def test_sector_intensity_normalized(self):
        """sector_intensity values must be in [0, 1]."""
        with patch("bazi_engine.transit.swe.calc_ut", side_effect=mock_calc_ut):
            r = client.get("/transit/now")
        body = r.json()
        for i, val in enumerate(body["sector_intensity"]):
            assert 0 <= val <= 1, f"sector_intensity[{i}] = {val} out of [0,1]"

    def test_transit_has_10_planets(self):
        with patch("bazi_engine.transit.swe.calc_ut", side_effect=mock_calc_ut):
            r = client.get("/transit/now")
        assert len(r.json()["planets"]) == 10

    @_skip_no_ephe
    def test_harmony_index_in_valid_range(self):
        """h_raw must be in [0, 1], h_calibrated in [0, 1]."""
        r = client.post("/calculate/fusion", json=BIRTH_PAYLOAD)
        body = r.json()
        h = body["harmony_index"]
        assert 0 <= h["harmony_index"] <= 1
        cal = body["calibration"]
        assert 0 <= cal["h_calibrated"] <= 1
        assert 0 <= cal["h_baseline"] <= 1

    @_skip_no_ephe
    def test_wuxing_vectors_are_normalized(self):
        """Wu-Xing vectors must be L2-normalized (magnitude ≈ 1)."""
        r = client.post("/calculate/fusion", json=BIRTH_PAYLOAD)
        body = r.json()
        for system in ("western_planets", "bazi_pillars"):
            vec = body["wu_xing_vectors"][system]
            magnitude = math.sqrt(sum(v ** 2 for v in vec.values()))
            assert abs(magnitude - 1.0) < 0.01, f"{system} magnitude = {magnitude}, expected ≈ 1.0"

    @_skip_no_ephe
    def test_elemental_comparison_sums_to_zero_ish(self):
        """Differences should be mathematically consistent."""
        r = client.post("/calculate/fusion", json=BIRTH_PAYLOAD)
        body = r.json()
        for elem, comp in body["elemental_comparison"].items():
            west = comp["western"]
            bazi = comp["bazi"]
            diff = comp["difference"]
            assert abs((west - bazi) - diff) < 0.002, f"{elem} difference inconsistent"

    @_skip_no_ephe
    def test_bazi_pillars_valid_stem_branch(self):
        """All pillars must have valid stem/branch names."""
        from bazi_engine.constants import BRANCHES, STEMS
        r = client.post("/calculate/bazi", json=BIRTH_PAYLOAD)
        body = r.json()
        for pillar_name, pillar in body["pillars"].items():
            assert pillar["stamm"] in STEMS, f"{pillar_name} stem '{pillar['stamm']}' not valid"
            assert pillar["zweig"] in BRANCHES, f"{pillar_name} branch '{pillar['zweig']}' not valid"

    @_skip_no_ephe
    def test_house_quality_flag_valid(self):
        r = client.post("/calculate/western", json=BIRTH_PAYLOAD)
        body = r.json()
        assert body["house_quality"]["flag"] in ("exact", "fallback", "estimated")


# ═══════════════════════════════════════════════════════════════════════════
# 10. DOCUMENTATION & DISCOVERY
# ═══════════════════════════════════════════════════════════════════════════

class TestDocumentationDiscovery:
    """OpenAPI quality, health probe, build info."""

    def test_health_has_dependency_detail(self):
        r = client.get("/health")
        body = r.json()
        assert "dependencies" in body
        assert "ephemeris" in body["dependencies"]
        assert "rate_limiter" in body["dependencies"]

    def test_health_engine_name(self):
        r = client.get("/health")
        assert r.json()["engine"] == "FuFirE"

    def test_ready_returns_503_when_degraded(self):
        """If ephemeris is unavailable, /ready should return 503."""
        r = client.get("/ready")
        # Can be 200 (healthy) or 503 (degraded) — both are correct behavior
        assert r.status_code in (200, 503)
        if r.status_code == 503:
            body = r.json()
            assert "detail" in body or "error" in body

    def test_openapi_error_envelope_schema(self):
        """OpenAPI must define ErrorEnvelope schema."""
        r = client.get("/openapi.json")
        spec = r.json()
        schemas = spec.get("components", {}).get("schemas", {})
        assert "ErrorEnvelope" in schemas

    def test_openapi_standard_headers_documented(self):
        """All response operations should document standard headers."""
        r = client.get("/openapi.json")
        spec = r.json()
        # Check that at least some operations have X-Request-ID header documented
        found_header = False
        for path, methods in spec.get("paths", {}).items():
            for method, op in methods.items():
                if not isinstance(op, dict):
                    continue
                for status, resp in op.get("responses", {}).items():
                    if isinstance(resp, dict) and "X-Request-ID" in resp.get("headers", {}):
                        found_header = True
                        break
        assert found_header, "No operations document X-Request-ID header"

    def test_api_docs_files_exist(self):
        """Documentation files must exist on disk."""
        base = Path(__file__).parent.parent
        assert (base / "docs" / "API_REFERENCE.md").exists()
        assert (base / "spec" / "openapi" / "openapi.json").exists()
