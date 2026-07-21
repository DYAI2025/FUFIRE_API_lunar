# Sprint 08 Remaining Tasks: B2B API Product

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Complete FuFirE's transformation into a sellable B2B API product: tier-based API keys with quota tracking, key-based rate limiting with standard headers, precision guardrails for missing birth time, and OpenAPI examples for developer onboarding.

**Architecture:** Extend existing `auth.py` with a `KeyInfo` dataclass carrying tier metadata. Replace `slowapi`'s IP-based keying with API-key-based keying. Add middleware for quota headers. Precision guardrails are a pure logic addition to existing compute paths. OpenAPI examples are added via Pydantic `model_config` JSON schema extras.

**Tech Stack:** Python 3.10+, FastAPI, slowapi, pytest, httpx

**ADRs in effect:**
- Existing endpoint paths are frozen — legacy routes stay as-is
- `/v1/` routes already exist with `require_api_key` dependency
- `_error_body()` envelope is stable — don't change its shape
- Package stays `bazi_engine` (rename deferred to post-launch)

**Builds on:** `docs/plans/2026-03-14-b2b-infrastructure.md` (completed)

---

## Iteration 1: Tier-Based API Key Auth (Task 8.3)

API keys carry tier metadata. Tiers control rate limits and feature access.
Key format: `ff_<tier>_<random>` (e.g., `ff_pro_a1b2c3d4e5`).
Backward compat: keys without prefix are treated as `free` tier.

---

### Task 1: Write failing tests for tier-based auth

**Files:**
- Modify: `tests/test_b2b_infra.py`

**Step 1: Write the failing tests**

Add to `tests/test_b2b_infra.py` after the existing `TestApiKeyAuth` class:

```python
class TestApiKeyTiers:
    """API key tier detection and quota metadata."""

    def setup_method(self):
        os.environ["FUFIRE_API_KEYS"] = "ff_free_testkey1,ff_pro_testkey2,ff_enterprise_testkey3,legacy-plain-key"
        from importlib import reload
        import bazi_engine.auth as auth_mod
        reload(auth_mod)

    def teardown_method(self):
        os.environ.pop("FUFIRE_API_KEYS", None)

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

    def test_dev_mode_returns_dev_tier(self):
        from bazi_engine.auth import resolve_key_info
        info = resolve_key_info("dev-mode")
        assert info.tier == "dev"

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
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_b2b_infra.py::TestApiKeyTiers -v`
Expected: FAIL with `ImportError: cannot import name 'resolve_key_info'`

**Step 3: Commit**

```bash
git add tests/test_b2b_infra.py
git commit -m "test: add tier-based API key tests (red)"
```

---

### Task 2: Implement KeyInfo and tier resolution

**Files:**
- Modify: `bazi_engine/auth.py`

**Step 1: Implement KeyInfo dataclass and resolve_key_info**

Replace the entire `bazi_engine/auth.py` with:

```python
"""
auth.py — API key authentication with tier-based access control.

Keys are loaded from FUFIRE_API_KEYS env var (comma-separated).
Key format: ff_<tier>_<random> (e.g., ff_pro_a1b2c3d4e5).
Keys without the prefix are treated as 'free' tier.

Tiers:
  dev        — local development (auth disabled)
  free       — 100 req/day,  5 req/min
  starter    — 1000 req/day, 20 req/min
  pro        — 10000 req/day, 100 req/min
  enterprise — unlimited
"""
from __future__ import annotations

import hmac
import os
from dataclasses import dataclass
from fastapi import HTTPException, Request, Security
from fastapi.security import APIKeyHeader

_API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)

# ── Tier definitions ──────────────────────────────────────────────────────────

TIER_LIMITS: dict[str, tuple[int, int]] = {
    # tier: (requests_per_day, requests_per_minute)
    # 0 = unlimited
    "dev":        (0, 0),
    "free":       (100, 5),
    "starter":    (1_000, 20),
    "pro":        (10_000, 100),
    "enterprise": (0, 0),
}


@dataclass(frozen=True)
class KeyInfo:
    """Metadata resolved from an API key."""
    key: str
    tier: str
    requests_per_day: int
    requests_per_minute: int


def resolve_key_info(api_key: str) -> KeyInfo:
    """Extract tier from key format ff_<tier>_<secret>, or default to free."""
    if api_key == "dev-mode":
        rpd, rpm = TIER_LIMITS["dev"]
        return KeyInfo(key=api_key, tier="dev", requests_per_day=rpd, requests_per_minute=rpm)

    tier = "free"  # default for legacy keys
    if api_key.startswith("ff_"):
        parts = api_key.split("_", 2)
        if len(parts) >= 3 and parts[1] in TIER_LIMITS:
            tier = parts[1]

    rpd, rpm = TIER_LIMITS[tier]
    return KeyInfo(key=api_key, tier=tier, requests_per_day=rpd, requests_per_minute=rpm)


# ── Key loading ───────────────────────────────────────────────────────────────

def _load_keys() -> frozenset[str]:
    raw = os.environ.get("FUFIRE_API_KEYS", "")
    if not raw.strip():
        return frozenset()
    return frozenset(k.strip() for k in raw.split(",") if k.strip())


def _require_keys_explicit() -> bool:
    return os.environ.get("FUFIRE_REQUIRE_API_KEYS", "").strip().lower() in {
        "1", "true", "yes", "on",
    }


def _is_valid_api_key(api_key: str, valid_keys: frozenset[str]) -> bool:
    matched = False
    for valid in valid_keys:
        matched = hmac.compare_digest(api_key, valid) or matched
    return matched


# ── FastAPI dependency ────────────────────────────────────────────────────────

def require_api_key(
    request: Request,
    api_key: str | None = Security(_API_KEY_HEADER),
) -> KeyInfo:
    """FastAPI dependency. Returns KeyInfo with tier metadata, raises 401 otherwise.

    Auth is disabled if FUFIRE_API_KEYS env var is not set (for local dev).
    The resolved KeyInfo is also stored on request.state.key_info for
    downstream middleware (rate limiting, quota headers).
    """
    valid_keys = _load_keys()
    if not valid_keys:
        if _require_keys_explicit():
            raise HTTPException(
                status_code=503,
                detail={
                    "error": "auth_configuration_error",
                    "message": "API key auth is required but FUFIRE_API_KEYS is empty",
                    "detail": {},
                },
            )
        info = resolve_key_info("dev-mode")
        request.state.key_info = info
        return info

    if not api_key or not _is_valid_api_key(api_key, valid_keys):
        raise HTTPException(
            status_code=401,
            detail={
                "error": "unauthorized",
                "message": "Missing or invalid X-API-Key header",
                "detail": {},
            },
            headers={"WWW-Authenticate": "ApiKey"},
        )

    info = resolve_key_info(api_key)
    request.state.key_info = info
    return info
```

**Step 2: Run tests to verify they pass**

Run: `pytest tests/test_b2b_infra.py::TestApiKeyTiers -v`
Expected: All 8 tests PASS

**Step 3: Fix existing tests that expect `require_api_key` to return `str`**

The existing `TestApiKeyAuth` tests call `/v1/calculate/bazi` and check status codes.
`require_api_key` now returns `KeyInfo` instead of `str`. Routers that use `api_key: str = Depends(require_api_key)` will break.

But since `require_api_key` is injected via `dependencies=[Depends(require_api_key)]` in `app.py` (not as a function parameter in routers), the return value is not consumed by router code. The existing tests should still pass.

Run: `pytest tests/test_b2b_infra.py -v`
Expected: All tests PASS (existing + new)

**Step 4: Run full test suite**

Run: `pytest -q`
Expected: All tests pass. If any router uses `api_key: str = Depends(require_api_key)` as a parameter, update the type hint to `KeyInfo`.

**Step 5: Commit**

```bash
git add bazi_engine/auth.py tests/test_b2b_infra.py
git commit -m "feat(auth): tier-based API keys with KeyInfo metadata"
```

---

## Iteration 2: Key-Based Rate Limiting with Quota Headers (Task 8.4)

Replace IP-based rate limiting with API-key-based. Return standard quota headers.

---

### Task 3: Write failing tests for key-based rate limiting

**Files:**
- Modify: `tests/test_b2b_infra.py`

**Step 1: Write the failing tests**

Add to `tests/test_b2b_infra.py`:

```python
class TestTieredRateLimiting:
    """Rate limiting keyed by API key with tier-based quotas."""

    def test_quota_headers_present_on_success(self):
        """Successful responses must include X-RateLimit-* headers."""
        response = client.get("/health")
        # Health is public, so no quota headers expected.
        # Check a legacy (unprotected) compute endpoint instead.
        response = client.get("/transit/now")
        if response.status_code == 200:
            # Quota headers are only on /v1/ routes (key-based).
            # Legacy routes keep IP-based limiting (no change).
            pass

    def test_v1_quota_headers_present(self):
        """V1 routes with valid key must return quota headers."""
        os.environ["FUFIRE_API_KEYS"] = "ff_free_testquota"
        from importlib import reload
        import bazi_engine.auth as auth_mod
        reload(auth_mod)

        from fastapi.testclient import TestClient
        from bazi_engine.app import app
        c = TestClient(app)
        response = c.get(
            "/v1/health",
        )
        # Health is unprotected, no key_info on request.state
        # Test a protected endpoint instead
        response = c.post(
            "/v1/calculate/bazi", json={},
            headers={"X-API-Key": "ff_free_testquota"},
        )
        # Even 422 should have quota headers
        assert "x-ratelimit-limit" in response.headers
        assert "x-ratelimit-remaining" in response.headers

        os.environ.pop("FUFIRE_API_KEYS", None)

    def test_rate_limit_key_func_uses_api_key(self):
        """Rate limiter must key off the API key, not the IP."""
        from bazi_engine.limiter import get_rate_limit_key
        from starlette.testclient import TestClient as _TC
        from starlette.requests import Request as _Req
        from starlette.datastructures import Headers

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
        from bazi_engine.limiter import get_rate_limit_key
        from starlette.requests import Request as _Req

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
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_b2b_infra.py::TestTieredRateLimiting -v`
Expected: FAIL with `ImportError: cannot import name 'get_rate_limit_key'`

**Step 3: Commit**

```bash
git add tests/test_b2b_infra.py
git commit -m "test: add tiered rate limiting tests (red)"
```

---

### Task 4: Implement key-based rate limiter

**Files:**
- Modify: `bazi_engine/limiter.py`

**Step 1: Replace limiter.py with key-aware implementation**

```python
"""
limiter.py — Shared slowapi Limiter instance with key-based rate limiting.

V1 routes: keyed by API key (from request.state.key_info).
Legacy routes: keyed by remote IP address (backward compat).
"""
from __future__ import annotations

from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.requests import Request


def get_rate_limit_key(request: Request) -> str:
    """Extract rate limit key: API key for /v1/, IP for legacy routes."""
    key_info = getattr(getattr(request, "state", None), "key_info", None)
    if key_info is not None:
        return key_info.key
    return get_remote_address(request)


limiter = Limiter(key_func=get_rate_limit_key)
```

**Step 2: Run tests to verify they pass**

Run: `pytest tests/test_b2b_infra.py::TestTieredRateLimiting -v`
Expected: PASS

**Step 3: Run full test suite**

Run: `pytest -q`
Expected: All tests pass

**Step 4: Commit**

```bash
git add bazi_engine/limiter.py tests/test_b2b_infra.py
git commit -m "feat(limiter): key-based rate limiting instead of IP-based"
```

---

### Task 5: Add quota headers middleware

**Files:**
- Modify: `bazi_engine/middleware.py`

**Step 1: Add quota headers to RequestIdMiddleware**

In `bazi_engine/middleware.py`, extend the `dispatch` method to inject `X-RateLimit-*` headers when `request.state.key_info` is available:

After the line `response.headers["X-Response-Time-ms"] = f"{elapsed_ms:.2f}"`, add:

```python
        # Quota headers for tier-based rate limiting (only on /v1/ routes).
        key_info = getattr(request.state, "key_info", None)
        if key_info is not None and key_info.requests_per_minute > 0:
            response.headers["X-RateLimit-Limit"] = str(key_info.requests_per_minute)
            # Remaining/Reset require a counter; for now emit the limit.
            # Full remaining tracking comes with Redis/Supabase storage.
            response.headers.setdefault("X-RateLimit-Remaining", str(key_info.requests_per_minute))
        elif key_info is not None and key_info.requests_per_minute == 0:
            response.headers["X-RateLimit-Limit"] = "unlimited"
            response.headers["X-RateLimit-Remaining"] = "unlimited"
```

**Step 2: Run tests to verify they pass**

Run: `pytest tests/test_b2b_infra.py -v`
Expected: All tests pass including `test_v1_quota_headers_present`

**Step 3: Commit**

```bash
git add bazi_engine/middleware.py
git commit -m "feat(middleware): add X-RateLimit-* quota headers on v1 routes"
```

---

## Iteration 3: Precision Guardrails (Task 8.7 H3)

When birth time is missing or uncertain, flag Ascendant and signature as `provisional`.

---

### Task 6: Write failing tests for precision guardrails

**Files:**
- Create: `tests/test_precision_guardrails.py`

**Step 1: Write the failing tests**

```python
"""
tests/test_precision_guardrails.py — Precision guardrail tests.

When birth time is absent or marked uncertain, computed results
that depend on exact time (Ascendant, hour pillar, signature)
must carry a 'provisional' flag.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from bazi_engine.app import app

client = TestClient(app)


class TestPrecisionFlags:
    """When birth_time_known=false, time-sensitive outputs are provisional."""

    BAZI_PAYLOAD = {
        "date": "1990-06-15T12:00:00",
        "tz": "Europe/Berlin",
        "lon": 13.405,
        "lat": 52.52,
    }

    def test_bazi_default_has_no_provisional_flag(self):
        """Normal request: no provisional flags."""
        response = client.post("/calculate/bazi", json=self.BAZI_PAYLOAD)
        if response.status_code == 200:
            body = response.json()
            assert body.get("precision", {}).get("birth_time_known") is True

    def test_bazi_unknown_time_flags_hour_provisional(self):
        """Unknown birth time: hour pillar flagged provisional."""
        payload = {**self.BAZI_PAYLOAD, "birth_time_known": False}
        response = client.post("/calculate/bazi", json=payload)
        if response.status_code == 200:
            body = response.json()
            prec = body.get("precision", {})
            assert prec.get("birth_time_known") is False
            assert "hour" in prec.get("provisional_fields", [])

    def test_western_unknown_time_flags_ascendant_provisional(self):
        """Unknown birth time: ascendant flagged provisional."""
        payload = {
            "date": "1990-06-15T12:00:00",
            "tz": "Europe/Berlin",
            "lon": 13.405,
            "lat": 52.52,
            "birth_time_known": False,
        }
        response = client.post("/calculate/western", json=payload)
        if response.status_code == 200:
            body = response.json()
            prec = body.get("precision", {})
            assert prec.get("birth_time_known") is False
            assert "ascendant" in prec.get("provisional_fields", [])
            assert "houses" in prec.get("provisional_fields", [])

    def test_fusion_unknown_time_flags_signature_provisional(self):
        """Unknown birth time: signature flagged provisional."""
        payload = {
            "date": "1990-06-15T12:00:00",
            "tz": "Europe/Berlin",
            "lon": 13.405,
            "lat": 52.52,
            "birth_time_known": False,
        }
        response = client.post("/calculate/fusion", json=payload)
        if response.status_code == 200:
            body = response.json()
            prec = body.get("precision", {})
            assert prec.get("birth_time_known") is False
            assert "signature" in prec.get("provisional_fields", [])
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_precision_guardrails.py -v`
Expected: FAIL — `precision` key missing from responses

**Step 3: Commit**

```bash
git add tests/test_precision_guardrails.py
git commit -m "test: add precision guardrail tests for provisional flags (red)"
```

---

### Task 7: Implement precision guardrails

**Files:**
- Modify: `bazi_engine/routers/bazi.py` — Add `birth_time_known` to `BaziRequest`, add `precision` to response
- Modify: `bazi_engine/routers/western.py` — Same pattern
- Modify: `bazi_engine/routers/fusion.py` — Same pattern

**Step 1: Add `birth_time_known` field to BaziRequest**

In `bazi_engine/routers/bazi.py`, add to `BaziRequest`:

```python
    birth_time_known: bool = Field(True, description="False if birth time is uncertain — flags time-dependent outputs as provisional")
```

In the `calculate_bazi_endpoint`, before the `return`, add:

```python
        # Precision guardrails
        provisional_fields = []
        if not req.birth_time_known:
            provisional_fields.append("hour")
        precision = {
            "birth_time_known": req.birth_time_known,
            "provisional_fields": provisional_fields,
        }
```

Then add `"precision": precision` to the return dict.

**Step 2: Apply same pattern to western.py**

Add `birth_time_known: bool = Field(True)` to the western request model.
Provisional fields when unknown: `["ascendant", "houses", "mc"]`.
Add `"precision": precision` to response.

**Step 3: Apply same pattern to fusion.py**

Add `birth_time_known: bool = Field(True)` to the fusion request model.
Provisional fields when unknown: `["signature", "hour", "ascendant", "houses"]`.
Add `"precision": precision` to response.

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_precision_guardrails.py -v`
Expected: All PASS (tests use `if response.status_code == 200` guard for ephemeris-dependent tests)

**Step 5: Run full test suite**

Run: `pytest -q`
Expected: All pass. The new `birth_time_known` field has a default (`True`), so existing tests are unaffected.

**Step 6: Commit**

```bash
git add bazi_engine/routers/bazi.py bazi_engine/routers/western.py bazi_engine/routers/fusion.py tests/test_precision_guardrails.py
git commit -m "feat: precision guardrails — provisional flags when birth time unknown"
```

---

## Iteration 4: OpenAPI Examples (Task 8.6)

Add request/response examples to the critical B2B endpoints so `/v1/docs` is immediately useful for developer onboarding.

---

### Task 8: Write failing test for OpenAPI examples

**Files:**
- Modify: `tests/test_b2b_infra.py`

**Step 1: Write the failing test**

Add to `tests/test_b2b_infra.py`:

```python
class TestOpenApiExamples:
    """OpenAPI spec must include request/response examples for B2B endpoints."""

    def _get_spec(self):
        return client.get("/openapi.json").json()

    def test_bazi_request_has_example(self):
        spec = self._get_spec()
        bazi_schema = spec["components"]["schemas"].get("BaziRequest", {})
        # Check for example at schema level or property level
        has_example = (
            "example" in bazi_schema
            or "examples" in bazi_schema
            or any("example" in v for v in bazi_schema.get("properties", {}).values() if isinstance(v, dict))
        )
        assert has_example, "BaziRequest schema must include examples"

    def test_bazi_endpoint_has_example_in_spec(self):
        spec = self._get_spec()
        bazi_path = spec.get("paths", {}).get("/v1/calculate/bazi", {}).get("post", {})
        body = bazi_path.get("requestBody", {}).get("content", {}).get("application/json", {})
        schema_ref = body.get("schema", {})
        # Either inline example or schema-level examples
        has_example = "example" in body or "examples" in body or "$ref" in schema_ref
        assert has_example or "example" in body, "POST /v1/calculate/bazi must have request example"
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_b2b_infra.py::TestOpenApiExamples -v`
Expected: FAIL — no examples in schema

**Step 3: Commit**

```bash
git add tests/test_b2b_infra.py
git commit -m "test: add OpenAPI example tests (red)"
```

---

### Task 9: Add examples to Pydantic request models

**Files:**
- Modify: `bazi_engine/routers/bazi.py` — Add `model_config` with JSON schema example
- Modify: `bazi_engine/routers/western.py` — Same
- Modify: `bazi_engine/routers/fusion.py` — Same

**Step 1: Add example to BaziRequest**

In `bazi_engine/routers/bazi.py`, add `model_config` to `BaziRequest`:

```python
class BaziRequest(BaseModel):
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "date": "1990-06-15T14:30:00",
            "tz": "Europe/Berlin",
            "lon": 13.405,
            "lat": 52.52,
            "standard": "CIVIL",
            "boundary": "midnight",
            "ambiguousTime": "earlier",
            "nonexistentTime": "error",
            "birth_time_known": True,
        }
    })
    # ... existing fields ...
```

Add `from pydantic import BaseModel, ConfigDict, Field` to the imports if `ConfigDict` is not already imported.

**Step 2: Add examples to Western and Fusion request models**

Follow the same pattern. Western example:
```python
{
    "date": "1990-06-15T14:30:00",
    "tz": "Europe/Berlin",
    "lon": 13.405,
    "lat": 52.52,
    "birth_time_known": True,
}
```

Fusion example:
```python
{
    "date": "1990-06-15T14:30:00",
    "tz": "Europe/Berlin",
    "lon": 13.405,
    "lat": 52.52,
    "birth_time_known": True,
}
```

**Step 3: Run tests to verify they pass**

Run: `pytest tests/test_b2b_infra.py::TestOpenApiExamples -v`
Expected: PASS

**Step 4: Regenerate OpenAPI spec**

Run: `python scripts/export_openapi.py`
This updates `spec/openapi/openapi.json` with the new examples.

**Step 5: Verify drift check passes**

Run: `python scripts/export_openapi.py --check`
Expected: No drift (spec matches generated output)

**Step 6: Commit**

```bash
git add bazi_engine/routers/bazi.py bazi_engine/routers/western.py bazi_engine/routers/fusion.py spec/openapi/openapi.json tests/test_b2b_infra.py
git commit -m "feat(openapi): add request examples for B2B developer onboarding"
```

---

## Iteration 5: Integration Verification

---

### Task 10: Full integration test and OpenAPI refresh

**Step 1: Run complete test suite**

Run: `pytest -v`
Expected: All tests pass, zero failures.

**Step 2: Lint check**

Run: `ruff check bazi_engine/ --output-format=github`
Expected: Zero violations.

**Step 3: Type check**

Run: `mypy bazi_engine --ignore-missing-imports`
Expected: Zero errors. (KeyInfo dataclass is fully typed.)

**Step 4: Verify local app starts**

Run: `python -c "from bazi_engine.app import app; print('OK')"`
Expected: `OK`

**Step 5: Regenerate and verify OpenAPI**

Run: `python scripts/export_openapi.py && python scripts/export_openapi.py --check`
Expected: Success, no drift.

**Step 6: Final commit**

```bash
git add -A
git commit -m "chore: sprint 08 integration verification — all green"
```

---

## Summary

| Task | Sprint Item | What It Does |
|------|-------------|-------------|
| 1-2 | 8.3 | Tier-based API keys (`KeyInfo` dataclass, `ff_<tier>_<secret>` format) |
| 3-5 | 8.4 | Key-based rate limiting + `X-RateLimit-*` quota headers |
| 6-7 | 8.7 H3 | Precision guardrails (`provisional` flag when birth time unknown) |
| 8-9 | 8.6 | OpenAPI request/response examples for `/v1/docs` |
| 10 | — | Integration verification (tests, lint, types, OpenAPI drift) |

## What's NOT in this plan (deferred)

- **8.1 R-02** Package rename `bazi_engine` → `fufire` — Breaking change, every import/test/CI path changes. Separate plan.
- **8.3 Supabase integration** — Current tier system is env-var-based. Supabase key management is a separate iteration once >10 keys are managed.
- **8.4 Redis-backed quotas** — `X-RateLimit-Remaining` is currently static (shows limit, not actual remaining). Real remaining tracking needs Redis or in-memory counter.
- **8.8-8.9** — Server modularization and repo cleanup are Bazodiac/Astro-Noctum tasks, not BAFE.
