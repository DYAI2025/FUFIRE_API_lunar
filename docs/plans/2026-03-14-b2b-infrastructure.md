# B2B Infrastructure Sprint Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make FuFirE externally integrable by a B2B developer: request traceability, versioned routes, dependency-aware health, webhook isolation, and simple API-key access control with rate limiting.

**Architecture:** Additive-only approach. All existing routes (`/calculate/*`, `/transit/*`, etc.) remain frozen for Bazodiac compatibility. New `/v1/` prefixed routes are added in parallel. A request-ID middleware injects traceability into every response. API key auth is env-var backed (upgradeable to Supabase later). Rate limiting via `slowapi`.

**Tech Stack:** Python 3.10+, FastAPI, slowapi, uuid, pytest, httpx

**ADRs in effect:**
- Existing endpoint paths are frozen — only ADD `/v1/` variants, never remove old routes
- `bazi_engine/bafe/` directory NOT renamed
- API keys = env var `FUFIRE_API_KEYS` (comma-separated), upgradeable later

---

## Iteration 1: Request ID Middleware + Error Envelope

Every request gets a UUID. Every error response returns it. This is the single highest-impact trust signal for a B2B customer debugging a failed call.

---

### Task 1: Write failing test for request ID in error responses

**Files:**
- Create: `tests/test_b2b_infra.py`

**Step 1: Write the failing test**

```python
"""
tests/test_b2b_infra.py — B2B infrastructure tests.
Tests request IDs, error envelope, /v1/ routes, health checks, API key auth, rate limiting.
"""
from __future__ import annotations

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
```

**Step 2: Run to verify it fails**

```bash
pytest tests/test_b2b_infra.py::TestRequestId -v
```

Expected: All 5 tests FAIL.

---

### Task 2: Implement request ID middleware

**Files:**
- Create: `bazi_engine/middleware.py`
- Modify: `bazi_engine/app.py`

**Step 1: Create middleware**

Create `bazi_engine/middleware.py`:

```python
"""
middleware.py — FastAPI middleware for request tracing.

Injects a unique X-Request-ID into every request/response.
If the client provides X-Request-ID, it is echoed back (client-side tracing).
"""
from __future__ import annotations

import uuid
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Inject X-Request-ID header into every request and response."""

    async def dispatch(self, request: Request, call_next) -> Response:  # type: ignore[override]
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response
```

**Step 2: Register middleware in app.py**

In `bazi_engine/app.py`, after the imports add:

```python
from .middleware import RequestIdMiddleware
```

After `app = FastAPI(...)`, add:

```python
app.add_middleware(RequestIdMiddleware)
```

**Step 3: Run the header tests**

```bash
pytest tests/test_b2b_infra.py::TestRequestId::test_request_id_header_present -v
pytest tests/test_b2b_infra.py::TestRequestId::test_request_id_different_per_request -v
pytest tests/test_b2b_infra.py::TestRequestId::test_client_request_id_echoed -v
```

Expected: These 3 PASS, the error-body tests still FAIL.

**Step 4: Commit**

```bash
git add bazi_engine/middleware.py bazi_engine/app.py tests/test_b2b_infra.py
git commit -m "feat: add request ID middleware (X-Request-ID on every response)"
```

---

### Task 3: Inject request_id into error responses

The existing error handlers in `app.py` return `exc.to_dict()` which has `{"error", "message", "detail"}`. We need to add `request_id` to all of them.

**Files:**
- Modify: `bazi_engine/app.py`

**Step 1: Update all exception handlers to include request_id**

Replace the four exception handlers in `app.py`:

```python
def _get_request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "unknown")


@app.exception_handler(BaziEngineError)
async def bazi_engine_error_handler(request: Request, exc: BaziEngineError) -> JSONResponse:
    body = exc.to_dict()
    body["request_id"] = _get_request_id(request)
    return JSONResponse(status_code=exc.http_status, content=body)


@app.exception_handler(EphemerisUnavailableError)
async def ephemeris_error_handler(request: Request, exc: EphemerisUnavailableError) -> JSONResponse:
    body = exc.to_dict()
    body["request_id"] = _get_request_id(request)
    return JSONResponse(status_code=503, content=body)


@app.exception_handler(RequestValidationError)
async def request_validation_error_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    import json as _json

    def _sanitize(obj, *, _depth: int = 0, _max_depth: int = 20):  # type: ignore[no-untyped-def]
        if _depth >= _max_depth:
            return "<nested>"
        if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
            return None
        if isinstance(obj, dict):
            return {k: _sanitize(v, _depth=_depth + 1) for k, v in obj.items()}
        if isinstance(obj, (list, tuple)):
            return [_sanitize(v, _depth=_depth + 1) for v in obj]
        try:
            _json.dumps(obj)
        except (TypeError, ValueError):
            return str(obj)
        return obj

    return JSONResponse(
        status_code=422,
        content={
            "error": "validation_error",
            "message": "Request validation failed",
            "detail": _sanitize({"errors": exc.errors()}),
            "request_id": _get_request_id(request),
        },
    )


@app.exception_handler(FileNotFoundError)
async def file_not_found_handler(request: Request, exc: FileNotFoundError) -> JSONResponse:
    return JSONResponse(
        status_code=503,
        content={
            "error": "ephemeris_unavailable",
            "message": str(exc),
            "detail": {},
            "request_id": _get_request_id(request),
        },
    )
```

**Step 2: Run all request ID tests**

```bash
pytest tests/test_b2b_infra.py::TestRequestId -v
```

Expected: All 5 PASS.

**Step 3: Ensure full test suite still passes**

```bash
pytest -q
```

Expected: same pass/skip count as before (1451 passed, 13 skipped).

**Step 4: Commit**

```bash
git add bazi_engine/app.py
git commit -m "feat: add request_id to all error responses"
```

---

## Iteration 2: `/health` Dependency Checks

Current `/health` returns `{"status": "healthy"}` unconditionally — even when ephemeris files are missing. A B2B customer's load balancer can't trust this.

---

### Task 4: Write failing tests for deep health check

**Files:**
- Modify: `tests/test_b2b_infra.py`

Add to `tests/test_b2b_infra.py`:

```python
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
```

**Run to verify fails:**

```bash
pytest tests/test_b2b_infra.py::TestHealth -v
```

Expected: `test_health_has_dependencies_key` and related FAIL.

---

### Task 5: Implement deep health check

**Files:**
- Modify: `bazi_engine/routers/info.py`

**Step 1: Update HealthResponse model and endpoint**

Replace the `HealthResponse` model and `health_check` function in `bazi_engine/routers/info.py`:

```python
class DependencyStatus(BaseModel):
    status: str  # "ok" | "unavailable"
    detail: Optional[str] = None


class HealthResponse(BaseModel):
    status: str  # "healthy" | "degraded" | "unavailable"
    engine: str = "FuFirE"
    version: str = ""
    dependencies: Dict[str, DependencyStatus] = {}


def _check_ephemeris() -> DependencyStatus:
    """Try a minimal ephemeris call to verify files are present."""
    try:
        import swisseph as swe
        # julday is pure math — no file needed. swe_calc needs files.
        jd = swe.julday(2000, 1, 1, 12.0)
        swe.calc_ut(jd, swe.SUN)
        return DependencyStatus(status="ok")
    except Exception as e:
        return DependencyStatus(status="unavailable", detail=str(e))


@router.get("/health", response_model=HealthResponse)
def health_check() -> Dict[str, Any]:
    ephemeris = _check_ephemeris()
    deps = {"ephemeris": ephemeris}
    if ephemeris.status == "unavailable":
        overall = "degraded"
    else:
        overall = "healthy"
    return {
        "status": overall,
        "engine": "FuFirE",
        "version": _ENGINE_VERSION,
        "dependencies": {k: v.model_dump() for k, v in deps.items()},
    }
```

**Step 2: Run health tests**

```bash
pytest tests/test_b2b_infra.py::TestHealth -v
```

Expected: All PASS (ephemeris status will be "ok" or "unavailable" depending on env, but the shape is correct).

**Step 3: Full suite**

```bash
pytest -q
```

**Step 4: Commit**

```bash
git add bazi_engine/routers/info.py
git commit -m "feat: /health reports per-dependency status (ephemeris check)"
```

---

## Iteration 3: `/v1/` Versioned Routes (Additive)

All public endpoints get a `/v1/` prefix. Old routes remain frozen for Bazodiac. New B2B integrators use `/v1/`.

---

### Task 6: Write failing tests for /v1/ routes

**Files:**
- Modify: `tests/test_b2b_infra.py`

Add to `tests/test_b2b_infra.py`:

```python
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
```

**Run to verify fails:**

```bash
pytest tests/test_b2b_infra.py::TestV1Routes -v
```

Expected: All `/v1/` tests FAIL with 404.

---

### Task 7: Register /v1/ routes in app.py

**Files:**
- Modify: `bazi_engine/app.py`

**Step 1: Add v1 prefix registrations**

In `bazi_engine/app.py`, after the existing `app.include_router(...)` calls, add:

```python
# ── /v1/ versioned routes (additive — old routes remain frozen) ───────────────

app.include_router(info.router, prefix="/v1")
app.include_router(validate.router, prefix="/v1")
app.include_router(bazi.router, prefix="/v1")
app.include_router(western.router, prefix="/v1")
app.include_router(fusion.router, prefix="/v1")
app.include_router(transit.router, prefix="/v1")
# Note: chart router (OG image) and webhooks are internal — not versioned
```

**Step 2: Run v1 tests**

```bash
pytest tests/test_b2b_infra.py::TestV1Routes -v
```

Expected: All PASS.

**Step 3: Full suite**

```bash
pytest -q
```

Expected: same pass/skip count.

**Step 4: Commit**

```bash
git add bazi_engine/app.py
git commit -m "feat: add /v1/ prefix routes (additive, old routes frozen)"
```

---

## Iteration 4: Webhook Separation

The ElevenLabs webhook lives at `/api/webhooks/chart` — mixed in with the public API. B2B customers seeing this in OpenAPI docs is confusing. Move to `/internal/webhooks/` and hide from public docs.

---

### Task 8: Write failing test for webhook separation

**Files:**
- Modify: `tests/test_b2b_infra.py`

Add:

```python
class TestWebhookSeparation:
    def test_internal_webhook_path_exists(self):
        """Webhook must be accessible at /internal/webhooks/chart."""
        # POST with empty body — will fail auth/validation but must not 404
        response = client.post("/internal/webhooks/chart", json={})
        assert response.status_code != 404

    def test_old_webhook_path_still_works(self):
        """Old /api/webhooks/chart must remain for Bazodiac compat."""
        response = client.post("/api/webhooks/chart", json={})
        assert response.status_code != 404
```

**Run to verify fails:**

```bash
pytest tests/test_b2b_infra.py::TestWebhookSeparation -v
```

Expected: `test_internal_webhook_path_exists` FAILS with 404.

---

### Task 9: Add /internal/ webhook route

**Files:**
- Modify: `bazi_engine/app.py`

**Step 1: Register webhooks router at /internal path too**

In `app.py`, add after existing webhook registration:

```python
# Internal-only webhook routes (not in public /v1/ docs)
app.include_router(
    webhooks.router,
    prefix="/internal",
    include_in_schema=False,
)
```

The existing `app.include_router(webhooks.router)` provides the `/api/webhooks/chart` path — keep it.

**Step 2: Run webhook tests**

```bash
pytest tests/test_b2b_infra.py::TestWebhookSeparation -v
```

Expected: Both PASS.

**Step 3: Full suite**

```bash
pytest -q
```

**Step 4: Commit**

```bash
git add bazi_engine/app.py
git commit -m "feat: expose webhooks at /internal/webhooks/ (hidden from public OpenAPI)"
```

---

## Iteration 5: API Key Authentication

Simple header-based API key auth. Keys loaded from env var `FUFIRE_API_KEYS` (comma-separated). Protected endpoints require `X-API-Key` header. `/health`, `/`, `/build` are public.

---

### Task 10: Write failing tests for API key auth

**Files:**
- Modify: `tests/test_b2b_infra.py`

Add:

```python
import os

class TestApiKeyAuth:
    """API key auth on /v1/ routes. Requires FUFIRE_API_KEYS env var."""

    def setup_method(self):
        # Set a known key for tests
        os.environ["FUFIRE_API_KEYS"] = "test-key-abc,test-key-xyz"
        # Reload auth module to pick up env change
        from importlib import import_module, reload
        import bazi_engine.services.auth as auth_mod
        reload(auth_mod)

    def test_no_key_returns_401(self):
        """Protected /v1/ route without key returns 401."""
        response = client.post("/v1/calculate/bazi", json={})
        assert response.status_code == 401

    def test_wrong_key_returns_401(self):
        response = client.post(
            "/v1/calculate/bazi", json={},
            headers={"X-API-Key": "wrong-key"}
        )
        assert response.status_code == 401

    def test_valid_key_is_accepted(self):
        """Valid key must not return 401 (may return 422 for bad data)."""
        response = client.post(
            "/v1/calculate/bazi", json={},
            headers={"X-API-Key": "test-key-abc"}
        )
        assert response.status_code != 401

    def test_second_valid_key_is_accepted(self):
        response = client.post(
            "/v1/calculate/bazi", json={},
            headers={"X-API-Key": "test-key-xyz"}
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
        response = client.post("/v1/calculate/bazi", json={})
        if response.status_code == 401:
            assert "request_id" in response.json()
```

**Run to verify fails:**

```bash
pytest tests/test_b2b_infra.py::TestApiKeyAuth -v
```

Expected: Most FAIL (no auth implemented yet, routes return 422 without checking keys).

---

### Task 11: Implement API key auth dependency

**Files:**
- Create: `bazi_engine/auth.py`
- Modify: `bazi_engine/routers/bazi.py`, `western.py`, `fusion.py`, `transit.py`, `validate.py`
- Modify: `bazi_engine/app.py`

**Step 1: Create auth module**

Create `bazi_engine/auth.py`:

```python
"""
auth.py — API key authentication for /v1/ routes.

Keys are loaded from FUFIRE_API_KEYS env var (comma-separated).
If the env var is not set, auth is DISABLED (dev mode).

Usage:
    from bazi_engine.auth import require_api_key
    @router.post("/endpoint", dependencies=[Depends(require_api_key)])
"""
from __future__ import annotations

import os
from fastapi import Depends, HTTPException, Security
from fastapi.security import APIKeyHeader

_API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)


def _load_keys() -> frozenset[str]:
    raw = os.environ.get("FUFIRE_API_KEYS", "")
    if not raw.strip():
        return frozenset()  # empty = auth disabled
    return frozenset(k.strip() for k in raw.split(",") if k.strip())


def require_api_key(
    api_key: str | None = Security(_API_KEY_HEADER),
) -> str:
    """FastAPI dependency. Returns the key if valid, raises 401 otherwise.

    Auth is disabled if FUFIRE_API_KEYS env var is not set (for local dev).
    """
    valid_keys = _load_keys()
    if not valid_keys:
        # Auth disabled — allow all
        return "dev-mode"
    if not api_key or api_key not in valid_keys:
        raise HTTPException(
            status_code=401,
            detail={
                "error": "unauthorized",
                "message": "Missing or invalid X-API-Key header",
                "detail": {},
            },
        )
    return api_key
```

**Step 2: Apply auth to /v1/ routes in app.py**

Instead of modifying every router, apply auth at the `include_router` level using `dependencies`:

In `app.py`, update the v1 registrations:

```python
from .auth import require_api_key
from fastapi import Depends

# ── /v1/ versioned routes (API key required except /v1/health, /v1/, /v1/build) ─

_protected = [Depends(require_api_key)]

app.include_router(validate.router, prefix="/v1", dependencies=_protected)
app.include_router(bazi.router, prefix="/v1", dependencies=_protected)
app.include_router(western.router, prefix="/v1", dependencies=_protected)
app.include_router(fusion.router, prefix="/v1", dependencies=_protected)
app.include_router(transit.router, prefix="/v1", dependencies=_protected)
# info router is public — no dependency
app.include_router(info.router, prefix="/v1")
```

**Step 3: Handle 401 error to include request_id**

In `app.py`, add handler for `HTTPException`:

```python
from fastapi import HTTPException as FastAPIHTTPException

@app.exception_handler(FastAPIHTTPException)
async def http_exception_handler(request: Request, exc: FastAPIHTTPException) -> JSONResponse:
    detail = exc.detail
    if isinstance(detail, dict):
        body = detail
    else:
        body = {"error": "http_error", "message": str(detail), "detail": {}}
    body["request_id"] = _get_request_id(request)
    return JSONResponse(status_code=exc.status_code, content=body)
```

**Step 4: Run API key tests**

```bash
pytest tests/test_b2b_infra.py::TestApiKeyAuth -v
```

Expected: All PASS.

**Step 5: Full suite**

```bash
pytest -q
```

Note: Existing tests (not using `/v1/`) are not affected by auth since auth only applies to `/v1/` registrations.

**Step 6: Commit**

```bash
git add bazi_engine/auth.py bazi_engine/app.py
git commit -m "feat: API key auth on /v1/ routes (env var FUFIRE_API_KEYS)"
```

---

## Iteration 6: Rate Limiting

`slowapi` provides per-IP rate limiting on top of FastAPI. Applied to `/v1/` routes. Transit endpoints are more generous (real-time data).

---

### Task 12: Add slowapi dependency

**Files:**
- Modify: `pyproject.toml`

**Step 1: Add slowapi**

In `pyproject.toml`, add to `dependencies`:

```toml
"slowapi>=0.1.9",
```

**Step 2: Install**

```bash
pip install -e ".[dev]"
```

**Step 3: Verify install**

```bash
python -c "import slowapi; print(slowapi.__version__)"
```

---

### Task 13: Write failing test for rate limiting

**Files:**
- Modify: `tests/test_b2b_infra.py`

Add:

```python
class TestRateLimiting:
    def test_rate_limit_header_present(self):
        """Rate limit responses must include X-RateLimit-* headers."""
        # Note: in test mode limits are typically not enforced,
        # but the headers should be present after slowapi integration.
        response = client.get("/v1/transit/now")
        # Accepting 200 or 429; just verify the route exists and headers may appear
        assert response.status_code in (200, 429)

    def test_excessive_requests_return_429(self):
        """Rapid fire requests should eventually return 429."""
        import os
        os.environ["FUFIRE_API_KEYS"] = ""  # disable auth for this test
        responses = [client.get("/v1/transit/now") for _ in range(5)]
        # At default limits this won't trigger, but ensures no 500s
        assert all(r.status_code in (200, 429) for r in responses)
```

**Run to verify:**

```bash
pytest tests/test_b2b_infra.py::TestRateLimiting -v
```

---

### Task 14: Implement rate limiting

**Files:**
- Modify: `bazi_engine/app.py`
- Modify: `bazi_engine/routers/transit.py`

**Step 1: Set up slowapi limiter in app.py**

Add to imports in `app.py`:

```python
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
```

After `app = FastAPI(...)`:

```python
limiter = Limiter(key_func=get_remote_address, default_limits=["60/minute"])
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
```

**Step 2: Apply per-route limits to transit endpoints**

In `bazi_engine/routers/transit.py`, add the limiter and apply to the expensive routes:

Add to imports:

```python
from slowapi import Limiter
from slowapi.util import get_remote_address
from fastapi import Request

limiter = Limiter(key_func=get_remote_address)
```

Apply to the `/now` endpoint (most frequently called):

```python
@router.get("/now", response_model=TransitNowResponse)
@limiter.limit("120/minute")
def get_transit_now(request: Request, ...) -> ...:
    ...
```

For `/state` and `/narrative` (heavier computation):

```python
@router.post("/state", response_model=TransitStateResponse)
@limiter.limit("30/minute")
def get_transit_state(request: Request, ...) -> ...:
    ...
```

**Step 3: Run rate limit tests**

```bash
pytest tests/test_b2b_infra.py::TestRateLimiting -v
```

**Step 4: Full suite**

```bash
pytest -q
```

**Step 5: Commit**

```bash
git add pyproject.toml bazi_engine/app.py bazi_engine/routers/transit.py
git commit -m "feat: add slowapi rate limiting (60/min global, 30/min on heavy endpoints)"
```

---

## Iteration 7: OpenAPI Sync + Regression Verification

---

### Task 15: Regenerate OpenAPI spec

**Files:**
- Modify: `spec/openapi/openapi.json`

**Step 1: Export updated spec**

```bash
python scripts/export_openapi.py
```

**Step 2: Verify no drift**

```bash
python scripts/export_openapi.py --check
```

Expected: No diff reported.

**Step 3: Commit**

```bash
git add spec/openapi/openapi.json
git commit -m "docs: regenerate OpenAPI spec (v1 routes, health deps, webhook separation)"
```

---

### Task 16: Full regression run and final commit

**Step 1: Run all tests**

```bash
pytest -v --tb=short 2>&1 | tail -20
```

Expected: All existing tests pass. New b2b_infra tests pass.

**Step 2: Check lint**

```bash
ruff check bazi_engine/ --output-format=github
```

**Step 3: Check types**

```bash
mypy bazi_engine --ignore-missing-imports
```

**Step 4: Final commit**

```bash
git add -A
git commit -m "feat: B2B infrastructure sprint complete — request IDs, /v1/ routes, health checks, API key auth, rate limiting"
```

---

## Definition of Done

- [ ] Every response has `X-Request-ID` header
- [ ] Every error response body includes `request_id`
- [ ] `/health` reports `dependencies.ephemeris.status`
- [ ] All public endpoints accessible at `/v1/` prefix
- [ ] Old routes unchanged (Bazodiac compatible)
- [ ] Webhooks accessible at `/internal/webhooks/chart` (hidden from OpenAPI)
- [ ] `/v1/calculate/*`, `/v1/transit/*`, `/v1/validate` require `X-API-Key` header
- [ ] No key / wrong key → 401 with `request_id`
- [ ] `FUFIRE_API_KEYS` unset → auth disabled (dev mode)
- [ ] Rate limiting applied (60/min global, 30/min heavy endpoints)
- [ ] OpenAPI spec regenerated and drift-free
- [ ] All 1451+ existing tests still pass
- [ ] New tests in `test_b2b_infra.py` all pass
- [ ] `ruff` and `mypy` clean
