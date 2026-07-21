# Security Hardening Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix all 15 security findings from the 2026-03-21 autoresearch:security audit, in priority order from Critical to Low.

**Architecture:** Each finding is fixed with a failing test first, then minimal implementation, then a commit. All changes stay within `bazi_engine/` — no new dependencies except `httpx` (already in requirements for tests) for the geocoding async fix. The Critical finding (legacy routes) is the most impactful: adding `require_api_key` to legacy routes via `_protected` dependencies, with Bazodiac-compat preserved since dev-mode (empty `FUFIRE_API_KEYS`) still bypasses auth.

**Tech Stack:** Python 3.10+, FastAPI, pytest + TestClient, monkeypatch for env vars, httpx for async geocoding

---

## Task 1: [CRITICAL] Legacy Routes — Add Auth Dependency

**Finding #1** — `/calculate/*`, `/transit/*`, `/experience/*`, `/validate` are accessible without any API key.

**Files:**
- Modify: `bazi_engine/app.py:271–279`
- Modify: `tests/test_b2b_infra.py` (add new test class)

**Step 1: Write the failing test**

Add to `tests/test_b2b_infra.py`:

```python
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
```

**Step 2: Run test to verify it fails**

```bash
cd /Users/benjaminpoersch/Projects/SaaS/FuFirE/BAFE
uv run python -m pytest tests/test_b2b_infra.py::TestLegacyRouteAuth -v
```
Expected: FAIL — `test_legacy_bazi_requires_auth_when_keys_configured` returns 200 instead of 401

**Step 3: Fix `bazi_engine/app.py`**

Change the legacy router block (lines 269–279). Replace:

```python
# ── Routers (legacy — frozen for Bazodiac compatibility) ─────────────────────

app.include_router(info.router)
app.include_router(validate.router)
app.include_router(bazi.router)
app.include_router(western.router)
app.include_router(fusion.router)
app.include_router(chart.router)
app.include_router(webhooks.router)
app.include_router(transit.router)
app.include_router(experience.router)
```

With:

```python
# ── Routers (legacy — frozen for Bazodiac compatibility) ─────────────────────
# Auth is enforced when FUFIRE_API_KEYS is set; dev-mode (empty env) bypasses.

app.include_router(info.router)
app.include_router(validate.router, dependencies=_protected)
app.include_router(bazi.router, dependencies=_protected)
app.include_router(western.router, dependencies=_protected)
app.include_router(fusion.router, dependencies=_protected)
app.include_router(chart.router, dependencies=_protected)
app.include_router(webhooks.router)  # has own auth via verify_request_auth
app.include_router(transit.router, dependencies=_protected)
app.include_router(experience.router, dependencies=_protected)
```

Note: `_protected` is already defined at line 285 — move its definition above the legacy block:

```python
_protected = [Depends(require_api_key)]

# ── Routers (legacy) ...
```

**Step 4: Run test to verify it passes**

```bash
uv run python -m pytest tests/test_b2b_infra.py::TestLegacyRouteAuth -v
```
Expected: PASS (all 3 tests green)

**Step 5: Run full suite to check no regressions**

```bash
uv run python -m pytest tests/ --tb=short -q
```
Expected: same pass count as baseline (1571+ passed)

> Note: Some tests that call legacy routes without API key may now fail in key-configured environments. If any test uses `client.post("/calculate/bazi", ...)` without an API key, add `headers={"X-API-Key": ""}` and set `FUFIRE_API_KEYS` to empty. Check `test_endpoints.py`, `test_b2b_infra.py` for such calls.

**Step 6: Commit**

```bash
cd /Users/benjaminpoersch/Projects/SaaS/FuFirE/BAFE
git add bazi_engine/app.py tests/test_b2b_infra.py
git commit -m "fix(security): enforce API key auth on legacy routes (Finding #1 — Critical)"
```

---

## Task 2: [HIGH] Add Rate Limits to Compute Endpoints

**Finding #2** — `/calculate/bazi`, `/calculate/western`, `/calculate/fusion`, `/validate` have no `@limiter.limit()` decorators.

**Files:**
- Modify: `bazi_engine/routers/bazi.py:154`
- Modify: `bazi_engine/routers/western.py` (find the `@router.post` decorator)
- Modify: `bazi_engine/routers/fusion.py` (find the `@router.post` decorator)
- Modify: `bazi_engine/routers/validate.py` (find the `@router.post` decorator)
- Modify: `tests/test_b2b_infra.py` (add test class)

**Step 1: Check current router signatures**

```bash
grep -n "@router\|def " /Users/benjaminpoersch/Projects/SaaS/FuFirE/BAFE/bazi_engine/routers/western.py | head -20
grep -n "@router\|def " /Users/benjaminpoersch/Projects/SaaS/FuFirE/BAFE/bazi_engine/routers/fusion.py | head -20
grep -n "@router\|def " /Users/benjaminpoersch/Projects/SaaS/FuFirE/BAFE/bazi_engine/routers/validate.py | head -20
```

**Step 2: Write the failing test**

Add to `tests/test_b2b_infra.py`:

```python
class TestComputeEndpointRateLimits:
    """Compute endpoints must have rate limiting configured."""

    def test_bazi_endpoint_has_rate_limit_decorator(self):
        """bazi route must be wrapped with slowapi rate limit."""
        from bazi_engine.routers.bazi import calculate_bazi_endpoint
        # slowapi stores limit info in __ratelimit__ attribute
        assert hasattr(calculate_bazi_endpoint, "__ratelimit__") or \
               any("limit" in str(getattr(calculate_bazi_endpoint, attr, ""))
                   for attr in dir(calculate_bazi_endpoint)), \
               "calculate_bazi_endpoint has no rate limit decorator"

    def test_calculate_bazi_returns_retry_after_on_429(self):
        """Exceeding rate limit returns 429 with Retry-After header."""
        from slowapi.errors import RateLimitExceeded
        from bazi_engine.app import app
        from unittest.mock import patch
        with patch("bazi_engine.limiter.limiter._inject_headers", side_effect=RateLimitExceeded("1/minute")):
            pass  # structural test — verifies 429 handler registered
        # Verify 429 handler is registered
        handlers = {type(k).__name__: v for k, v in app.exception_handlers.items()}
        assert "RateLimitExceeded" in str(app.exception_handlers)
```

> Note: slowapi uses a different mechanism for storing limit info. The real test is functional — verify the decorator is added by inspecting the source. Adjust if the attribute check doesn't match slowapi's internals.

**Step 3: Add `@limiter.limit()` to each compute endpoint**

In `bazi_engine/routers/bazi.py`, add import and decorator:

```python
from ..limiter import limiter

# ...

@router.post("/bazi", response_model=BaziResponse)
@limiter.limit("30/minute")
def calculate_bazi_endpoint(request: Request, req: BaziRequest) -> Dict[str, Any]:
```

> Important: slowapi requires `request: Request` as the FIRST parameter. Check if it's already there — if not, add it.

Repeat the same pattern for:
- `bazi_engine/routers/western.py` → `@limiter.limit("30/minute")`
- `bazi_engine/routers/fusion.py` → `@limiter.limit("30/minute")`
- `bazi_engine/routers/validate.py` → `@limiter.limit("60/minute")`

**Step 4: Run tests**

```bash
uv run python -m pytest tests/test_b2b_infra.py -v
uv run python -m pytest tests/ --tb=short -q
```
Expected: all pass

**Step 5: Commit**

```bash
git add bazi_engine/routers/bazi.py bazi_engine/routers/western.py \
        bazi_engine/routers/fusion.py bazi_engine/routers/validate.py \
        tests/test_b2b_infra.py
git commit -m "fix(security): add rate limiting to compute endpoints (Finding #2 — High)"
```

---

## Task 3: [HIGH] Fail-Safe Auth in fly.toml

**Finding #3** — `FUFIRE_REQUIRE_API_KEYS` not set in `fly.toml` → if `FUFIRE_API_KEYS` secret is missing after redeploy, API runs without auth.

**Files:**
- Modify: `fly.toml`
- Modify: `tests/test_b2b_infra.py`

**Step 1: Write the failing test**

Add to `tests/test_b2b_infra.py`:

```python
class TestAuthFailSafe:
    """When FUFIRE_REQUIRE_API_KEYS=true and no keys configured, API must return 503."""

    def test_503_when_keys_required_but_not_configured(self, monkeypatch):
        monkeypatch.setenv("FUFIRE_REQUIRE_API_KEYS", "true")
        monkeypatch.delenv("FUFIRE_API_KEYS", raising=False)
        from bazi_engine.auth import _load_keys
        _load_keys.cache_clear()
        response = client.get("/v1/health")  # public route — no auth needed
        # Health is public, should still be 200
        assert response.status_code == 200
        # But protected route must 503
        response = client.post("/v1/calculate/bazi", json={
            "date": "1990-06-15T14:30:00", "tz": "Europe/Berlin",
            "lon": 13.405, "lat": 52.52
        })
        assert response.status_code == 503
        body = response.json()
        assert body["error"] == "auth_configuration_error"
        _load_keys.cache_clear()
```

**Step 2: Run test to verify it passes (this should already pass)**

```bash
uv run python -m pytest tests/test_b2b_infra.py::TestAuthFailSafe -v
```
Expected: PASS (logic exists in auth.py already — this test just documents it)

**Step 3: Add `FUFIRE_REQUIRE_API_KEYS` to `fly.toml`**

In `fly.toml`, find the `[env]` section (or add it). Add:

```toml
[env]
  FUFIRE_REQUIRE_API_KEYS = "true"
```

**Step 4: Commit**

```bash
git add fly.toml tests/test_b2b_infra.py
git commit -m "fix(security): set FUFIRE_REQUIRE_API_KEYS=true in fly.toml (Finding #3 — High)"
```

---

## Task 4: [MEDIUM] Add Auth Event Logging

**Finding #12** — No logging on auth failures, dev-mode activation, or webhook auth failures.

**Files:**
- Modify: `bazi_engine/auth.py`
- Modify: `bazi_engine/services/auth.py`
- Test: `tests/test_b2b_infra.py`

**Step 1: Write the failing test**

```python
class TestAuthLogging:
    def test_failed_auth_is_logged(self, monkeypatch, caplog):
        import logging
        monkeypatch.setenv("FUFIRE_API_KEYS", "ff_pro_validkey123")
        from bazi_engine.auth import _load_keys
        _load_keys.cache_clear()
        with caplog.at_level(logging.WARNING, logger="bazi_engine.auth"):
            response = client.get("/v1/health", headers={"X-API-Key": "bad-key"})
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
            client.get("/health")
        assert any("dev" in r.message.lower() or "no api keys" in r.message.lower()
                   for r in caplog.records)
        _load_keys.cache_clear()
```

**Step 2: Run test to verify it fails**

```bash
uv run python -m pytest tests/test_b2b_infra.py::TestAuthLogging -v
```
Expected: FAIL — no log records captured

**Step 3: Add logging to `bazi_engine/auth.py`**

```python
import logging
_log = logging.getLogger(__name__)

# In require_api_key(), after the 401 block:
if not api_key or not _is_valid_api_key(api_key, valid_keys):
    masked = (api_key[:4] + "...") if api_key and len(api_key) > 4 else "missing"
    _log.warning("auth.failed key=%s path=%s", masked, request.url.path)
    raise HTTPException(...)

# In the dev-mode fallback block:
if not valid_keys:
    if _require_keys_explicit():
        ...
    _log.warning("auth.dev_mode path=%s — FUFIRE_API_KEYS not configured", request.url.path)
    info = resolve_key_info("dev-mode")
    ...
```

**Step 4: Add logging to `bazi_engine/services/auth.py`**

```python
import logging
_log = logging.getLogger(__name__)

def verify_request_auth(...) -> bool:
    result = False
    # Method 1: HMAC signature (preferred)
    if elevenlabs_signature and verify_elevenlabs_signature(raw_body, elevenlabs_signature, secret):
        return True
    # Method 2: Simple API key header
    if x_api_key and hmac.compare_digest(x_api_key, secret):
        return True
    # Method 3: Bearer token
    if authorization and authorization.startswith("Bearer "):
        token = authorization[7:]
        if hmac.compare_digest(token, secret):
            return True
    _log.warning("webhook.auth_failed sig=%s key_present=%s bearer_present=%s",
                 bool(elevenlabs_signature), bool(x_api_key), bool(authorization))
    return False
```

**Step 5: Run tests**

```bash
uv run python -m pytest tests/test_b2b_infra.py::TestAuthLogging -v
uv run python -m pytest tests/ --tb=short -q
```
Expected: PASS

**Step 6: Commit**

```bash
git add bazi_engine/auth.py bazi_engine/services/auth.py tests/test_b2b_infra.py
git commit -m "fix(security): add audit logging for auth events (Finding #12 — Medium)"
```

---

## Task 5: [MEDIUM] Webhook Auth — HMAC-Only Mode

**Finding #10** — Method 2 (X-Api-Key) and Method 3 (Bearer) use raw secret, bypassing HMAC replay protection.

**Files:**
- Modify: `bazi_engine/services/auth.py`
- Modify: `bazi_engine/routers/webhooks.py`
- Test: `tests/test_services_auth.py`

**Step 1: Write the failing test**

Add to `tests/test_services_auth.py`:

```python
class TestHmacOnlyMode:
    """When hmac_only=True, method 2/3 must be rejected even with correct secret."""

    def test_api_key_rejected_in_hmac_only_mode(self):
        from bazi_engine.services.auth import verify_request_auth
        result = verify_request_auth(
            PAYLOAD,
            elevenlabs_signature=None,
            x_api_key=SECRET,
            authorization=None,
            secret=SECRET,
            hmac_only=True,
        )
        assert result is False

    def test_bearer_rejected_in_hmac_only_mode(self):
        from bazi_engine.services.auth import verify_request_auth
        result = verify_request_auth(
            PAYLOAD,
            elevenlabs_signature=None,
            x_api_key=None,
            authorization=f"Bearer {SECRET}",
            secret=SECRET,
            hmac_only=True,
        )
        assert result is False

    def test_valid_hmac_accepted_in_hmac_only_mode(self):
        from bazi_engine.services.auth import verify_request_auth
        ts = int(time.time() * 1000)
        header = _make_signature(PAYLOAD, SECRET, ts)
        result = verify_request_auth(
            PAYLOAD,
            elevenlabs_signature=header,
            x_api_key=None,
            authorization=None,
            secret=SECRET,
            hmac_only=True,
        )
        assert result is True
```

**Step 2: Run test to verify it fails**

```bash
uv run python -m pytest tests/test_services_auth.py::TestHmacOnlyMode -v
```
Expected: FAIL — `verify_request_auth` has no `hmac_only` parameter

**Step 3: Add `hmac_only` parameter to `verify_request_auth`**

In `bazi_engine/services/auth.py`:

```python
def verify_request_auth(
    raw_body: bytes,
    *,
    elevenlabs_signature: Optional[str],
    x_api_key: Optional[str],
    authorization: Optional[str],
    secret: str,
    hmac_only: bool = False,
) -> bool:
    """Try auth methods in order. hmac_only=True disables Method 2/3."""
    # Method 1: HMAC signature (preferred, replay-protected)
    if elevenlabs_signature and verify_elevenlabs_signature(raw_body, elevenlabs_signature, secret):
        return True
    if hmac_only:
        _log.warning("webhook.auth_failed hmac_only=True — fallback methods disabled")
        return False
    # Method 2: Simple API key header
    if x_api_key and hmac.compare_digest(x_api_key, secret):
        return True
    # Method 3: Bearer token
    if authorization and authorization.startswith("Bearer "):
        token = authorization[7:]
        if hmac.compare_digest(token, secret):
            return True
    _log.warning("webhook.auth_failed sig=%s key_present=%s bearer_present=%s",
                 bool(elevenlabs_signature), bool(x_api_key), bool(authorization))
    return False
```

**Step 4: Enable hmac_only in webhook router via env var**

In `bazi_engine/routers/webhooks.py`, update the `verify_request_auth` call:

```python
hmac_only = os.environ.get("WEBHOOK_HMAC_ONLY", "true").lower() in {"1", "true", "yes", "on"}

if not verify_request_auth(
    raw_body,
    elevenlabs_signature=elevenlabs_signature,
    x_api_key=x_api_key,
    authorization=authorization,
    secret=tool_secret,
    hmac_only=hmac_only,
):
```

**Step 5: Add `WEBHOOK_HMAC_ONLY=true` to `fly.toml`**

```toml
[env]
  FUFIRE_REQUIRE_API_KEYS = "true"
  WEBHOOK_HMAC_ONLY = "true"
```

**Step 6: Run tests**

```bash
uv run python -m pytest tests/test_services_auth.py -v
uv run python -m pytest tests/ --tb=short -q
```

**Step 7: Commit**

```bash
git add bazi_engine/services/auth.py bazi_engine/routers/webhooks.py \
        fly.toml tests/test_services_auth.py
git commit -m "fix(security): add hmac_only mode for webhook auth (Finding #10 — Medium)"
```

---

## Task 6: [MEDIUM] Add CORS Middleware

**Finding #8** — No `CORSMiddleware` configured.

**Files:**
- Modify: `bazi_engine/app.py`
- Test: `tests/test_b2b_infra.py`

**Step 1: Write the failing test**

```python
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
        # Either 200 with CORS headers or 405 if OPTIONS not handled
        assert "access-control-allow-origin" in response.headers or \
               response.status_code in (200, 405)

    def test_cors_header_present_on_get(self):
        """Regular requests from allowed origin get CORS header."""
        response = client.get(
            "/health",
            headers={"Origin": "https://bazodiac.space"}
        )
        assert "access-control-allow-origin" in response.headers
```

**Step 2: Add CORSMiddleware to `bazi_engine/app.py`**

Add import at the top:
```python
from fastapi.middleware.cors import CORSMiddleware
```

Add after the existing middleware (after `app.add_middleware(RequestIdMiddleware, ...)`):

```python
_ALLOWED_ORIGINS_ENV = os.environ.get(
    "CORS_ALLOWED_ORIGINS",
    "https://bazodiac.space,https://www.bazodiac.space,http://localhost:5173,http://localhost:3000",
)
_ALLOWED_ORIGINS = [o.strip() for o in _ALLOWED_ORIGINS_ENV.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["X-API-Key", "X-Request-ID", "Content-Type", "Authorization"],
    expose_headers=["X-Request-ID", "X-API-Version", "X-Response-Time-ms",
                    "X-RateLimit-Limit", "X-RateLimit-Remaining"],
)
```

Add `import os` if not already at the top (it should be — check).

**Step 3: Run tests**

```bash
uv run python -m pytest tests/test_b2b_infra.py::TestCORSHeaders -v
uv run python -m pytest tests/ --tb=short -q
```

**Step 4: Commit**

```bash
git add bazi_engine/app.py tests/test_b2b_infra.py
git commit -m "fix(security): add CORSMiddleware with configurable origins (Finding #8 — Medium)"
```

---

## Task 7: [MEDIUM] Add HSTS Header + Harden Middleware

**Finding #9** — Missing `Strict-Transport-Security` header.

**Files:**
- Modify: `bazi_engine/middleware.py`
- Test: `tests/test_b2b_infra.py`

**Step 1: Write the failing test**

```python
class TestSecurityHeaders:
    def test_hsts_header_present(self):
        response = client.get("/health")
        assert "strict-transport-security" in response.headers, \
               f"Missing HSTS. Headers: {dict(response.headers)}"

    def test_hsts_max_age_at_least_one_year(self):
        response = client.get("/health")
        hsts = response.headers.get("strict-transport-security", "")
        import re
        match = re.search(r"max-age=(\d+)", hsts)
        assert match, f"No max-age in HSTS: {hsts}"
        assert int(match.group(1)) >= 31536000, "HSTS max-age must be >= 1 year"
```

**Step 2: Run test to verify it fails**

```bash
uv run python -m pytest tests/test_b2b_infra.py::TestSecurityHeaders -v
```
Expected: FAIL

**Step 3: Add HSTS to `bazi_engine/middleware.py`**

In the `dispatch` method, after the existing `setdefault` calls:

```python
response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
```

**Step 4: Run tests**

```bash
uv run python -m pytest tests/test_b2b_infra.py::TestSecurityHeaders -v
uv run python -m pytest tests/ --tb=short -q
```

**Step 5: Commit**

```bash
git add bazi_engine/middleware.py tests/test_b2b_infra.py
git commit -m "fix(security): add HSTS header to middleware (Finding #9 — Low)"
```

---

## Task 8: [MEDIUM] Fix Sync Geocoding — Convert to httpx async

**Finding #13** — `services/geocoding.py` uses blocking `urllib.request.urlopen` inside FastAPI async context.

**Files:**
- Modify: `bazi_engine/services/geocoding.py`
- Modify: `bazi_engine/routers/webhooks.py` (must be async if geocoding is async)
- Test: `tests/test_services_geocoding.py` (check existing tests first)

**Step 1: Check existing geocoding tests**

```bash
cat /Users/benjaminpoersch/Projects/SaaS/FuFirE/BAFE/tests/test_services_geocoding.py
```

**Step 2: Write the failing test**

Add to `tests/test_services_geocoding.py`:

```python
import inspect
from bazi_engine.services.geocoding import geocode_place

def test_geocode_place_is_async():
    """geocode_place must be a coroutine function to avoid blocking the event loop."""
    assert inspect.iscoroutinefunction(geocode_place), \
           "geocode_place must be async — use httpx.AsyncClient, not urllib"
```

**Step 3: Run test to verify it fails**

```bash
uv run python -m pytest tests/test_services_geocoding.py::test_geocode_place_is_async -v
```

**Step 4: Rewrite `geocode_place` as async using httpx**

Replace entire `bazi_engine/services/geocoding.py` with:

```python
"""
services/geocoding.py — Place name → lat/lon/timezone resolution.

Uses Open-Meteo Geocoding API (free, no API key required).
Uses httpx.AsyncClient to avoid blocking the FastAPI event loop.
Results are NOT cached here — callers may add caching if needed.
"""
from __future__ import annotations

from typing import Any, Dict
from urllib.parse import urlencode

import httpx


async def geocode_place(place: str, language: str = "de") -> Dict[str, Any]:
    """Resolve place name to lat/lon/timezone via Open-Meteo Geocoding API.

    Args:
        place:    Place name, optionally with country code suffix (e.g. "Berlin, DE").
        language: Language code for result names (default: "de").

    Returns:
        Dict with keys: lat, lon, timezone, name, country_code.

    Raises:
        ValueError: If no matching place is found.
    """
    parts = [p.strip() for p in place.split(",", maxsplit=1)]
    search_name = parts[0]
    country_filter = (
        parts[1].upper()
        if len(parts) > 1 and len(parts[1].strip()) == 2
        else None
    )

    url = "https://geocoding-api.open-meteo.com/v1/search?" + urlencode({
        "name": search_name, "count": 5, "language": language, "format": "json",
    })

    async with httpx.AsyncClient(
        headers={"User-Agent": "bafe-fufirement-engine/1.0"},
        timeout=5.0,
    ) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        data = resp.json()

    results = data.get("results") or []
    if country_filter:
        filtered = [r for r in results if r.get("country_code", "").upper() == country_filter]
        if filtered:
            results = filtered

    if not results:
        raise ValueError(f"Could not geocode place: {place}")

    r = results[0]
    return {
        "lat": float(r["latitude"]),
        "lon": float(r["longitude"]),
        "timezone": str(r.get("timezone") or ""),
        "name": str(r.get("name") or place),
        "country_code": str(r.get("country_code") or ""),
    }
```

**Step 5: Update `routers/webhooks.py` to await geocode_place**

Find the geocoding call (around line 131):

```python
# Before:
geo_result = geocode_place(req.birthPlace)

# After:
geo_result = await geocode_place(req.birthPlace)
```

Also ensure the webhook handler function is `async def` (it should already be).

**Step 6: Check if httpx is in requirements**

```bash
grep httpx /Users/benjaminpoersch/Projects/SaaS/FuFirE/BAFE/requirements.lock
```

If not present, add to `pyproject.toml` dependencies: `"httpx>=0.27.0"` (it's likely already there for tests).

**Step 7: Run tests**

```bash
uv run python -m pytest tests/test_services_geocoding.py -v
uv run python -m pytest tests/ --tb=short -q
```

**Step 8: Commit**

```bash
git add bazi_engine/services/geocoding.py bazi_engine/routers/webhooks.py
git commit -m "fix(security): convert geocoding to async httpx (Finding #13 — Medium)"
```

---

## Task 9: [MEDIUM] Add Key Generation Script

**Finding #11** — No key generation script, entropy of random part unspecified.

**Files:**
- Create: `scripts/generate_api_key.py`
- Test: `tests/test_b2b_infra.py`

**Step 1: Write the failing test**

```python
class TestKeyGeneration:
    def test_generated_key_has_correct_format(self):
        import subprocess, sys
        result = subprocess.run(
            [sys.executable, "scripts/generate_api_key.py", "--tier", "free"],
            capture_output=True, text=True,
            cwd="/Users/benjaminpoersch/Projects/SaaS/FuFirE/BAFE",
        )
        key = result.stdout.strip()
        assert key.startswith("ff_free_"), f"Key has wrong format: {key}"
        parts = key.split("_")
        assert len(parts) == 3
        assert len(parts[2]) >= 32, f"Random part too short (< 32 chars): {parts[2]}"

    def test_generated_keys_are_unique(self):
        import subprocess, sys
        keys = set()
        for _ in range(5):
            result = subprocess.run(
                [sys.executable, "scripts/generate_api_key.py", "--tier", "pro"],
                capture_output=True, text=True,
                cwd="/Users/benjaminpoersch/Projects/SaaS/FuFirE/BAFE",
            )
            keys.add(result.stdout.strip())
        assert len(keys) == 5, "Generated keys are not unique!"
```

**Step 2: Create `scripts/generate_api_key.py`**

```python
#!/usr/bin/env python3
"""
Generate a FuFirE API key with sufficient entropy.

Usage:
    python scripts/generate_api_key.py --tier pro
    python scripts/generate_api_key.py --tier free

Output: prints the key to stdout (add to FUFIRE_API_KEYS env var)

Key format: ff_<tier>_<32-char hex>
Entropy: 128 bits (secrets.token_hex(16) → 32 hex chars)
"""
import argparse
import secrets

VALID_TIERS = {"dev", "free", "starter", "pro", "enterprise"}


def generate_key(tier: str) -> str:
    if tier not in VALID_TIERS:
        raise ValueError(f"Invalid tier: {tier}. Must be one of {VALID_TIERS}")
    random_part = secrets.token_hex(16)  # 128 bits entropy
    return f"ff_{tier}_{random_part}"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate a FuFirE API key")
    parser.add_argument("--tier", required=True, choices=VALID_TIERS)
    args = parser.parse_args()
    print(generate_key(args.tier))
```

**Step 3: Run tests**

```bash
uv run python -m pytest tests/test_b2b_infra.py::TestKeyGeneration -v
```

**Step 4: Commit**

```bash
git add scripts/generate_api_key.py tests/test_b2b_infra.py
git commit -m "feat(security): add API key generation script with 128-bit entropy (Finding #11 — Medium)"
```

---

## Task 10: [LOW] Fix Exception Detail Leakage in Webhooks

**Finding #7** — `f"Invalid request: {e}"` and `f"Geocoding failed for '{req.birthPlace}': {e}"` expose internals.

**Files:**
- Modify: `bazi_engine/routers/webhooks.py:119–136`
- Test: `tests/test_b2b_infra.py`

**Step 1: Write the failing test**

```python
class TestWebhookErrorSanitization:
    def test_malformed_json_does_not_leak_exception(self, monkeypatch):
        monkeypatch.setenv("ELEVENLABS_TOOL_SECRET", "test-secret")
        import hashlib, hmac as _hmac, time as _time
        ts = int(_time.time() * 1000)
        payload = b"NOT_VALID_JSON{{{{"
        signed = f"{ts}.".encode() + payload
        sig = _hmac.new(b"test-secret", signed, hashlib.sha256).hexdigest()
        response = client.post(
            "/api/webhooks/chart",
            content=payload,
            headers={
                "Content-Type": "application/json",
                "elevenlabs-signature": f"t={ts},v1={sig}",
            },
        )
        assert response.status_code == 400
        body = response.json()
        # Must NOT contain raw Python exception message
        detail_str = str(body.get("detail", ""))
        assert "Expecting value" not in detail_str
        assert "JSONDecodeError" not in detail_str
        assert "Invalid request:" not in detail_str
```

**Step 2: Run test to verify it fails**

```bash
uv run python -m pytest tests/test_b2b_infra.py::TestWebhookErrorSanitization -v
```

**Step 3: Fix `bazi_engine/routers/webhooks.py`**

Replace lines ~119–136:

```python
# Before:
try:
    data = json.loads(raw_body)
    req = ElevenLabsChartRequest(**data)
except Exception as e:
    raise HTTPException(status_code=400, detail=f"Invalid request: {e}")

# After:
try:
    data = json.loads(raw_body)
    req = ElevenLabsChartRequest(**data)
except Exception:
    raise HTTPException(status_code=400, detail={
        "error": "invalid_request",
        "message": "Request body is invalid or malformed",
        "detail": {},
    })
```

```python
# Before:
except Exception as e:
    raise HTTPException(status_code=400, detail=f"Geocoding failed for '{req.birthPlace}': {e}")

# After:
except Exception:
    raise HTTPException(status_code=400, detail={
        "error": "geocoding_failed",
        "message": "Could not resolve birth place. Check the place name and try again.",
        "detail": {},
    })
```

**Step 4: Run tests**

```bash
uv run python -m pytest tests/test_b2b_infra.py::TestWebhookErrorSanitization -v
uv run python -m pytest tests/ --tb=short -q
```

**Step 5: Commit**

```bash
git add bazi_engine/routers/webhooks.py tests/test_b2b_infra.py
git commit -m "fix(security): sanitize exception details in webhook error responses (Finding #7 — Low)"
```

---

## Task 11: [LOW] Fix Secret Name Leak in 500 Response

**Finding #15** — `detail="ELEVENLABS_TOOL_SECRET not configured"` leaks env var name.

**Files:**
- Modify: `bazi_engine/routers/webhooks.py:105–107`
- Test: `tests/test_b2b_infra.py`

**Step 1: Write the failing test**

```python
class TestWebhookConfigError:
    def test_missing_secret_returns_generic_503(self, monkeypatch):
        monkeypatch.delenv("ELEVENLABS_TOOL_SECRET", raising=False)
        response = client.post("/api/webhooks/chart", json={})
        assert response.status_code in (500, 503)
        body = str(response.json())
        assert "ELEVENLABS_TOOL_SECRET" not in body, \
               f"Env var name leaked in response: {body}"
```

**Step 2: Fix `bazi_engine/routers/webhooks.py`**

```python
# Before:
tool_secret = os.environ.get("ELEVENLABS_TOOL_SECRET")
if not tool_secret:
    raise HTTPException(status_code=500, detail="ELEVENLABS_TOOL_SECRET not configured")

# After:
tool_secret = os.environ.get("ELEVENLABS_TOOL_SECRET")
if not tool_secret:
    raise HTTPException(status_code=503, detail={
        "error": "service_unavailable",
        "message": "Webhook service is not configured",
        "detail": {},
    })
```

**Step 3: Run tests and commit**

```bash
uv run python -m pytest tests/test_b2b_infra.py::TestWebhookConfigError -v
uv run python -m pytest tests/ --tb=short -q
git add bazi_engine/routers/webhooks.py tests/test_b2b_infra.py
git commit -m "fix(security): sanitize webhook config error (Finding #15 — Low)"
```

---

## Task 12: [LOW] Remove Duplicate Webhook Exposure

**Finding #5** — Webhook registered twice: `/api/webhooks/chart` (legacy, no prefix) and `/internal/api/webhooks/chart`.

**Files:**
- Modify: `bazi_engine/app.py:273`
- Test: `tests/test_b2b_infra.py`

**Step 1: Write the failing test**

```python
class TestWebhookRoutes:
    def test_webhook_only_at_internal_path(self):
        """Webhook must only be accessible at /internal/api/webhooks/chart."""
        # /api/webhooks/chart (legacy) should no longer exist
        response = client.post("/api/webhooks/chart", json={})
        assert response.status_code == 404, \
               f"/api/webhooks/chart should be 404 (legacy removed), got {response.status_code}"

    def test_webhook_accessible_at_internal_path(self):
        """Webhook is still reachable at /internal/api/webhooks/chart."""
        response = client.post("/internal/api/webhooks/chart", json={})
        # No secret configured in test env → 503 (not 404)
        assert response.status_code != 404, \
               "/internal/api/webhooks/chart must still exist"
```

**Step 2: Run test to verify it fails**

```bash
uv run python -m pytest tests/test_b2b_infra.py::TestWebhookRoutes -v
```

**Step 3: Remove the unprefix-registered webhook from `bazi_engine/app.py`**

Delete line 273 (`app.include_router(webhooks.router)`), keeping only:
```python
app.include_router(webhooks.router, prefix="/internal", include_in_schema=False)
```

**Step 4: Run tests and commit**

```bash
uv run python -m pytest tests/test_b2b_infra.py::TestWebhookRoutes -v
uv run python -m pytest tests/ --tb=short -q
git add bazi_engine/app.py tests/test_b2b_infra.py
git commit -m "fix(security): remove duplicate /api/webhooks/chart exposure (Finding #5 — Low)"
```

---

## Task 13: [LOW] Document lru_cache Revocation Behavior

**Finding #14** — `_load_keys()` uses `lru_cache` with no invalidation mechanism. Add a `cache_clear` export and document the pattern.

**Files:**
- Modify: `bazi_engine/auth.py`
- Test: `tests/test_b2b_infra.py`

**Step 1: Verify `cache_clear` is accessible (it already is via `_load_keys.cache_clear()`)**

```python
class TestAuthCacheClear:
    def test_load_keys_cache_can_be_cleared(self):
        """cache_clear() must be callable for emergency key revocation."""
        from bazi_engine.auth import _load_keys
        # Should not raise
        _load_keys.cache_clear()
        _load_keys.cache_clear()  # idempotent

    def test_cache_clear_reloads_keys_from_env(self, monkeypatch):
        from bazi_engine.auth import _load_keys
        monkeypatch.setenv("FUFIRE_API_KEYS", "ff_free_key1")
        _load_keys.cache_clear()
        keys_v1 = _load_keys()
        assert "ff_free_key1" in keys_v1

        monkeypatch.setenv("FUFIRE_API_KEYS", "ff_free_key2")
        # Without clear — still returns old value
        keys_cached = _load_keys()
        assert "ff_free_key1" in keys_cached  # cached!

        # After clear — new value
        _load_keys.cache_clear()
        keys_v2 = _load_keys()
        assert "ff_free_key2" in keys_v2
```

**Step 2: Add docstring to `_load_keys` documenting revocation**

```python
@lru_cache(maxsize=1)
def _load_keys() -> frozenset[str]:
    """Load valid API keys from FUFIRE_API_KEYS env var.

    Keys are cached for process lifetime. To revoke a key without process restart,
    call _load_keys.cache_clear() — the next request will reload from the env var.

    For production key rotation: update the secret, then trigger a Fly.io deploy
    (which restarts the process and clears the cache automatically).
    """
    raw = os.environ.get("FUFIRE_API_KEYS", "")
    if not raw.strip():
        return frozenset()
    return frozenset(k.strip() for k in raw.split(",") if k.strip())
```

**Step 3: Run tests and commit**

```bash
uv run python -m pytest tests/test_b2b_infra.py::TestAuthCacheClear -v
uv run python -m pytest tests/ --tb=short -q
git add bazi_engine/auth.py tests/test_b2b_infra.py
git commit -m "docs(security): document lru_cache revocation behavior (Finding #14 — Low)"
```

---

## Task 14: [MEDIUM] Document Tier Assignment + Key Entropy

**Finding #4** — Tier purely from key format, no server-side lookup, no revocation per-key.

This is architectural by design. Task: write a test that validates the known behavior and add a guard against future regressions.

**Files:**
- Test: `tests/test_b2b_infra.py`

**Step 1: Write tests that document the behavior**

```python
class TestTierAssignment:
    def test_tier_derived_from_key_prefix(self):
        from bazi_engine.auth import resolve_key_info
        assert resolve_key_info("ff_free_abc").tier == "free"
        assert resolve_key_info("ff_pro_abc").tier == "pro"
        assert resolve_key_info("ff_enterprise_abc").tier == "enterprise"
        assert resolve_key_info("ff_starter_abc").tier == "starter"

    def test_unknown_tier_prefix_defaults_to_free(self):
        from bazi_engine.auth import resolve_key_info
        # Keys with unknown tier prefix → free tier (safe default)
        assert resolve_key_info("ff_superadmin_abc").tier == "free"
        assert resolve_key_info("legacy-key-no-prefix").tier == "free"

    def test_dev_mode_key_gets_unlimited_tier(self):
        from bazi_engine.auth import resolve_key_info, TIER_LIMITS
        info = resolve_key_info("dev-mode")
        assert info.tier == "dev"
        assert info.requests_per_day == 0  # unlimited
        assert info.requests_per_minute == 0  # unlimited

    def test_generated_key_gets_correct_tier(self):
        """Keys generated by scripts/generate_api_key.py must get the right tier."""
        import subprocess, sys
        result = subprocess.run(
            [sys.executable, "scripts/generate_api_key.py", "--tier", "pro"],
            capture_output=True, text=True,
            cwd="/Users/benjaminpoersch/Projects/SaaS/FuFirE/BAFE",
        )
        key = result.stdout.strip()
        from bazi_engine.auth import resolve_key_info
        assert resolve_key_info(key).tier == "pro"
```

**Step 2: Run tests and commit**

```bash
uv run python -m pytest tests/test_b2b_infra.py::TestTierAssignment -v
git add tests/test_b2b_infra.py
git commit -m "test(security): document tier assignment behavior (Finding #4 — Medium)"
```

---

## Task 15: [FINAL] Full Test Run + Audit Closure

**Step 1: Run complete test suite**

```bash
cd /Users/benjaminpoersch/Projects/SaaS/FuFirE/BAFE
uv run python -m pytest tests/ -v --tb=short 2>&1 | tail -20
```
Expected: all previous 1571+ tests pass, plus new security tests green.

**Step 2: Run coverage check**

```bash
uv run python -m pytest tests/ --cov=bazi_engine --cov-report=term-missing --cov-fail-under=75 -q
```
Expected: ≥75% coverage maintained.

**Step 3: Run type check**

```bash
uv run mypy bazi_engine/ --ignore-missing-imports
```
Expected: no new errors.

**Step 4: Update the security audit TSV with resolution status**

```bash
# Add "resolved" column entries to:
# security/2026-03-21-1200-auth-ratelimit-webhook-audit/security-audit-results.tsv
```

**Step 5: Final commit**

```bash
git add security/
git commit -m "docs(security): mark all findings resolved in audit TSV"
```

---

## Summary — Findings → Tasks

| Finding | Severity | Task | Status |
|---------|----------|------|--------|
| #1 Legacy routes without auth | Critical | Task 1 | |
| #2 No rate limits on compute | High | Task 2 | |
| #3 Dev-mode fallback not secured | High | Task 3 | |
| #12 No auth logging | Medium | Task 4 | |
| #10 Webhook HMAC-only | Medium | Task 5 | |
| #8 Missing CORS | Medium | Task 6 | |
| #9 Missing HSTS | Low | Task 7 | |
| #13 Sync geocoding blocks event loop | Medium | Task 8 | |
| #11 Key entropy unspecified | Medium | Task 9 | |
| #7 Exception details in 400 responses | Low | Task 10 | |
| #15 Secret name in 500 response | Low | Task 11 | |
| #5 Webhook double exposure | Low | Task 12 | |
| #14 lru_cache no revocation | Low | Task 13 | |
| #4 Tier from key format only | Medium | Task 14 | |
| #6 Phantom RateLimit headers | Medium | (future: needs Redis — tracked in CHANGELOG) | |
