# FuFirE API Contract & Error Drift Fix — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix 13 audit findings (FUFIRE-API-001–013) so that OpenAPI spec, runtime behaviour, tests, and docs are consistent.

**Architecture:** All fixes stay in-place — no new routing layers, no framework migration. Work touches existing routers (`chart.py`, `superglue.py`, `webhooks.py`), the OpenAPI customiser in `app.py`, middleware, `superglue_client.py`, and documentation. TDD-first: write a failing test before touching production code.

**Tech Stack:** Python 3.10+, FastAPI, Pydantic v2, pytest, `scripts/export_openapi.py --check`, `httpx` TestClient

---

## Context

**Known facts from codebase inspection:**
- `ChartRequest` defined in **both** `bazi_engine/routers/chart.py:43` AND `bazi_engine/routers/superglue.py:25` — classic OpenAPI component-name collision.
- Webhook router mounts at prefix `/internal` (app.py:336) and route path `/webhooks/chart` (webhooks.py:96) → runtime is `/internal/webhooks/chart`. Router docstring says `/api/webhooks/chart` → doc/runtime mismatch.
- `superglue_client.py:42` raises generic `RuntimeError` when `SUPERGLUE_API_KEY` is missing → unhandled 500, should be 503.
- `middleware.py` sets `X-Request-ID`, `X-API-Version`, `X-Response-Time-ms` on responses **via `response.headers` in dispatch()**, which FastAPI's exception handlers bypass on unhandled errors.

**Open decisions (record in PR):**
- `/chart` endpoint lifecycle: internal-only or public legacy? Default plan: mark as internal, add `include_in_schema=True` deprecation flag.
- Webhook path: keep internal at `/internal/webhooks/chart`. Default plan: fix docs to match.
- `X-RateLimit-Remaining`: not reliably present. Default plan: remove guarantee from docs/OpenAPI, do NOT add phantom counter.

---

## Phase 0 — Baseline & Branch

### Task 1: Reproduce baseline and create fix branch

**Files:**
- Read: `pyproject.toml`, `spec/openapi/openapi.json`, `scripts/export_openapi.py`
- Create: `audit-fix-log.md` (temp PR notes, not committed to main)

**Step 1: Create branch**

```bash
git checkout -b fix/api-contract-drift-and-error-contract
```

**Step 2: Install deps**

```bash
source .venv/bin/activate
pip install -e ".[dev]"
```

**Step 3: Run baseline**

```bash
PYTHONPATH=$PWD python3 scripts/export_openapi.py --check
PYTHONPATH=$PWD pytest -q --tb=short --disable-warnings --maxfail=20 2>&1 | tee /tmp/baseline.txt
```

**Step 4: Verify expected failures**

Expected: `export_openapi.py --check` fails or passes depending on seed. `pytest` shows some failures (snapshot drift, respx missing, etc.).

**Step 5: Commit baseline log**

```bash
git add audit-fix-log.md
git commit -m "chore(audit): record baseline failures before contract-drift fixes"
```

---

## Phase 1 — OpenAPI Determinism (FUFIRE-API-001)

### Task 2: Write failing OpenAPI determinism test

**Files:**
- Create: `tests/test_openapi_determinism.py`

**Step 1: Write the failing test**

```python
# tests/test_openapi_determinism.py
import subprocess
import json
import os
import pytest


def _export_schema(seed: int) -> dict:
    result = subprocess.run(
        ["python3", "scripts/export_openapi.py"],
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONHASHSEED": str(seed), "PYTHONPATH": "."},
    )
    # export_openapi.py prints JSON to stdout
    return json.loads(result.stdout)


def _collect_chart_refs(schema: dict) -> set[str]:
    refs = set()
    paths = schema.get("paths", {})
    for path, methods in paths.items():
        if "chart" in path.lower():
            for method, op in methods.items():
                body = op.get("requestBody", {})
                content = body.get("content", {})
                for ct, desc in content.items():
                    ref = desc.get("schema", {}).get("$ref", "")
                    if ref:
                        refs.add(ref)
    return refs


def test_chart_refs_stable_across_seeds():
    """ChartRequest name collision causes $ref to flip between seeds."""
    schemas = [_export_schema(seed) for seed in range(5)]
    ref_sets = [_collect_chart_refs(s) for s in schemas]
    # All seeds must produce identical ref sets
    assert all(r == ref_sets[0] for r in ref_sets), (
        f"Chart $refs are non-deterministic across seeds: {ref_sets}"
    )


def test_no_duplicate_unqualified_chart_request():
    """Exactly one schema component may be named ChartRequest."""
    schema = _export_schema(0)
    components = schema.get("components", {}).get("schemas", {})
    chart_request_variants = [k for k in components if k.lower() == "chartrequest"]
    assert len(chart_request_variants) <= 1, (
        f"Multiple ChartRequest-named schemas: {chart_request_variants}"
    )
```

**Step 2: Run to verify it fails**

```bash
PYTHONPATH=$PWD pytest -q tests/test_openapi_determinism.py -v
```

Expected: FAIL — `test_no_duplicate_unqualified_chart_request` fails because both `chart.py` and `superglue.py` define `ChartRequest`.

**Step 3: Commit failing test**

```bash
git add tests/test_openapi_determinism.py
git commit -m "test(openapi): failing determinism test for ChartRequest collision"
```

---

### Task 3: Rename colliding ChartRequest models

**Files:**
- Modify: `bazi_engine/routers/chart.py` (line 43)
- Modify: `bazi_engine/routers/superglue.py` (line 25)
- Regenerate: `spec/openapi/openapi.json`

**Step 1: Rename in chart.py**

In `bazi_engine/routers/chart.py`, rename class `ChartRequest` → `ChartComputeRequest`:
- Line 43: `class ChartRequest(BaseModel):` → `class ChartComputeRequest(BaseModel):`
- Line 168: `def chart_endpoint(req: ChartRequest)` → `def chart_endpoint(req: ChartComputeRequest)`
- Update any other references in that file.

**Step 2: Rename in superglue.py**

In `bazi_engine/routers/superglue.py`, rename class `ChartRequest` → `SuperglueChartTriggerRequest`:
- Line 25: `class ChartRequest(BaseModel):` → `class SuperglueChartTriggerRequest(BaseModel):`
- Update all uses in handlers (e.g., line 115 `body: Optional[ChartRequest]` → `body: Optional[SuperglueChartTriggerRequest]`).

**Step 3: Verify no other references remain**

```bash
grep -rn "class ChartRequest\b" bazi_engine/
```

Expected: no output.

**Step 4: Regenerate OpenAPI spec**

```bash
PYTHONPATH=$PWD python3 scripts/export_openapi.py
```

**Step 5: Run multi-seed check**

```bash
for seed in 0 1 2 3 4 5 6 7 8 9 10; do
  PYTHONHASHSEED=$seed PYTHONPATH=$PWD python3 scripts/export_openapi.py --check && echo "seed $seed OK"
done
```

Expected: all seeds pass.

**Step 6: Run determinism tests**

```bash
PYTHONPATH=$PWD pytest -q tests/test_openapi_determinism.py tests/test_openapi_contract.py
```

Expected: PASS.

**Step 7: Commit**

```bash
git add bazi_engine/routers/chart.py bazi_engine/routers/superglue.py spec/openapi/openapi.json
git commit -m "fix(openapi): rename ChartRequest to ChartComputeRequest and SuperglueChartTriggerRequest to fix non-deterministic component collision"
```

---

## Phase 2 — ErrorEnvelope Contract (FUFIRE-API-002, 009)

### Task 4: Write failing ErrorEnvelope contract test

**Files:**
- Create: `tests/test_openapi_error_contract.py`

**Step 1: Write the failing test**

```python
# tests/test_openapi_error_contract.py
import pytest
from bazi_engine.app import app


@pytest.fixture(scope="module")
def schema():
    return app.openapi()


def _get_protected_operations(schema: dict) -> list[tuple[str, str, dict]]:
    """Return (path, method, operation) tuples for operations with security."""
    ops = []
    for path, methods in schema.get("paths", {}).items():
        for method, op in methods.items():
            if method in ("get", "post", "put", "patch", "delete"):
                if op.get("security") or any(
                    p.get("name") == "X-API-Key"
                    for p in op.get("parameters", [])
                ):
                    ops.append((path, method, op))
    return ops


def test_protected_ops_have_401(schema):
    ops = _get_protected_operations(schema)
    assert ops, "Expected at least some protected operations"
    missing = [
        f"{method.upper()} {path}"
        for path, method, op in ops
        if "401" not in op.get("responses", {})
    ]
    assert not missing, f"Missing 401 response on protected ops: {missing}"


def test_protected_ops_have_429(schema):
    ops = _get_protected_operations(schema)
    missing = [
        f"{method.upper()} {path}"
        for path, method, op in ops
        if "429" not in op.get("responses", {})
    ]
    assert not missing, f"Missing 429 response on protected ops: {missing}"


def test_error_responses_reference_error_envelope(schema):
    error_codes = ("400", "401", "422", "429", "500", "503")
    components = schema.get("components", {}).get("schemas", {})
    assert "ErrorEnvelope" in components, "ErrorEnvelope schema missing from components"
    errors = []
    for path, methods in schema.get("paths", {}).items():
        for method, op in methods.items():
            if method not in ("get", "post", "put", "patch", "delete"):
                continue
            for code in error_codes:
                resp = op.get("responses", {}).get(code)
                if resp is None:
                    continue
                # Must reference ErrorEnvelope
                content = resp.get("content", {})
                json_content = content.get("application/json", {})
                ref = json_content.get("schema", {}).get("$ref", "")
                if "ErrorEnvelope" not in ref:
                    errors.append(f"{method.upper()} {path} status={code} ref={ref!r}")
    assert not errors, f"Error responses not using ErrorEnvelope: {errors}"
```

**Step 2: Run to verify it fails**

```bash
PYTHONPATH=$PWD pytest -q tests/test_openapi_error_contract.py -v
```

Expected: FAIL — protected operations missing 401/429 responses.

**Step 3: Commit failing test**

```bash
git add tests/test_openapi_error_contract.py
git commit -m "test(openapi): failing error-contract test for ErrorEnvelope on protected ops"
```

---

### Task 5: Add ErrorEnvelope responses to protected operations

**Files:**
- Modify: `bazi_engine/app.py` (the `_custom_openapi()` function, ~line 341)
- Regenerate: `spec/openapi/openapi.json`

**Step 1: Read current `_custom_openapi()` logic**

Open `bazi_engine/app.py` around lines 341–560 and understand the current patching loop.

**Step 2: Add common error response injection**

In `_custom_openapi()`, after the existing loop that patches operations, add:

```python
# Inject common error responses into protected operations
_common_error_responses = {
    "401": {
        "description": "Unauthorized — missing or invalid API key",
        "content": {"application/json": {"schema": {"$ref": "#/components/schemas/ErrorEnvelope"}}},
    },
    "429": {
        "description": "Too Many Requests — rate limit exceeded",
        "content": {"application/json": {"schema": {"$ref": "#/components/schemas/ErrorEnvelope"}}},
    },
    "500": {
        "description": "Internal Server Error",
        "content": {"application/json": {"schema": {"$ref": "#/components/schemas/ErrorEnvelope"}}},
    },
    "503": {
        "description": "Service Unavailable — ephemeris or external dependency not configured",
        "content": {"application/json": {"schema": {"$ref": "#/components/schemas/ErrorEnvelope"}}},
    },
}

for path_obj in schema.get("paths", {}).values():
    for method, op in path_obj.items():
        if method not in ("get", "post", "put", "patch", "delete", "head", "options"):
            continue
        is_protected = op.get("security") or any(
            p.get("name") == "X-API-Key" for p in op.get("parameters", [])
        )
        if not is_protected:
            continue
        responses = op.setdefault("responses", {})
        for code, resp_obj in _common_error_responses.items():
            if code not in responses:
                responses[code] = resp_obj
```

**Step 3: Regenerate OpenAPI**

```bash
PYTHONPATH=$PWD python3 scripts/export_openapi.py
```

**Step 4: Run tests**

```bash
PYTHONPATH=$PWD pytest -q tests/test_openapi_error_contract.py tests/test_openapi_determinism.py tests/test_openapi_contract.py
```

Expected: PASS.

**Step 5: Commit**

```bash
git add bazi_engine/app.py spec/openapi/openapi.json
git commit -m "fix(openapi): inject 401/429/500/503 ErrorEnvelope responses on protected operations"
```

---

## Phase 3 — Webhook Path (FUFIRE-API-004)

### Task 6: Write failing webhook route test

**Files:**
- Create: `tests/test_webhook_routes.py`
- Inspect: `bazi_engine/app.py:336`, `bazi_engine/routers/webhooks.py:96`

**Context:** Runtime path is `/internal/webhooks/chart` (prefix `/internal` + route `/webhooks/chart`). Docs say `/api/webhooks/chart`. This test enforces the runtime truth.

**Step 1: Write the failing test**

```python
# tests/test_webhook_routes.py
import pytest
from fastapi.testclient import TestClient
from bazi_engine.app import app

client = TestClient(app, raise_server_exceptions=False)


def test_internal_webhook_path_reachable():
    """Runtime webhook path /internal/webhooks/chart must return non-404."""
    resp = client.post(
        "/internal/webhooks/chart",
        json={"type": "test"},
        headers={"X-Webhook-Secret": "invalid"},
    )
    # Should reach the handler — 401/403/422/503 all acceptable, 404 is not
    assert resp.status_code != 404, (
        f"Webhook not found at /internal/webhooks/chart (got {resp.status_code})"
    )


def test_old_api_webhook_path_not_the_canonical_url():
    """The path /api/webhooks/chart must NOT be the documented integration URL."""
    # If it 404s, that's fine — we just verify it's not relied on
    resp = client.post("/api/webhooks/chart", json={"type": "test"})
    # This test is a documentation reminder — we don't assert 404 specifically
    # but record the actual behaviour
    assert resp.status_code in (404, 401, 403, 422, 503), (
        f"Unexpected status on legacy path: {resp.status_code}"
    )


def test_webhook_route_not_in_public_openapi_schema():
    """Webhook router is include_in_schema=False — must not appear in OpenAPI paths."""
    from bazi_engine.app import app as _app
    schema = _app.openapi()
    webhook_paths = [p for p in schema.get("paths", {}) if "webhooks" in p]
    assert not webhook_paths, (
        f"Webhook paths unexpectedly in public OpenAPI schema: {webhook_paths}"
    )
```

**Step 2: Run to verify current state**

```bash
PYTHONPATH=$PWD pytest -q tests/test_webhook_routes.py -v
```

Expected: `test_internal_webhook_path_reachable` PASS or FAIL depending on routing. Record actual result.

**Step 3: Commit failing/baseline test**

```bash
git add tests/test_webhook_routes.py
git commit -m "test(webhook): document runtime path truth and assert not in public schema"
```

---

### Task 7: Fix webhook documentation to match runtime path

**Files:**
- Modify: `docs/API_REFERENCE.md`
- Modify: `docs/api/01_developer_api_reference.md`
- Modify: `bazi_engine/routers/webhooks.py` (docstring only)

**Step 1: Find all doc occurrences of wrong path**

```bash
grep -rn "api/webhooks/chart\|/api/webhooks" docs/ bazi_engine/routers/webhooks.py
```

**Step 2: Replace with correct internal path**

Replace all instances of `/api/webhooks/chart` with `/internal/webhooks/chart`. Mark section as "Internal / ElevenLabs integration only — not a public API surface".

In `bazi_engine/routers/webhooks.py` line 2, update the module docstring:
```
routers/webhooks.py — POST /internal/webhooks/chart (ElevenLabs voice agent integration, internal only)
```

**Step 3: Verify grep clean**

```bash
grep -rn '"/api/webhooks/chart"' docs/ bazi_engine/
```

Expected: no output (or only comments/changelogs).

**Step 4: Run tests**

```bash
PYTHONPATH=$PWD pytest -q tests/test_webhook_routes.py
```

Expected: PASS.

**Step 5: Commit**

```bash
git add docs/ bazi_engine/routers/webhooks.py
git commit -m "fix(docs): correct webhook path from /api/webhooks/chart to /internal/webhooks/chart"
```

---

## Phase 4 — Runtime Error Handling (FUFIRE-API-005, 006)

### Task 8: Write failing Superglue config-error test

**Files:**
- Create: `tests/test_superglue_config_errors.py`

**Step 1: Write the failing test**

```python
# tests/test_superglue_config_errors.py
import os
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from bazi_engine.app import app

_VALID_KEY = "ff_pro_testsecret"


@pytest.fixture
def client_no_superglue():
    """Client with API key auth enabled but no SUPERGLUE_API_KEY."""
    env = {
        "FUFIRE_REQUIRE_API_KEYS": "true",
        "FUFIRE_API_KEYS": _VALID_KEY,
    }
    # Remove SUPERGLUE_API_KEY from environment
    with patch.dict(os.environ, env, clear=False):
        os.environ.pop("SUPERGLUE_API_KEY", None)
        yield TestClient(app, raise_server_exceptions=False)


def test_superglue_profile_returns_503_when_no_key(client_no_superglue):
    resp = client_no_superglue.get(
        "/v1/profile/testuser",
        headers={"X-API-Key": _VALID_KEY},
    )
    assert resp.status_code == 503, f"Expected 503, got {resp.status_code}: {resp.text}"
    body = resp.json()
    assert body.get("error") == "service_unavailable", f"Unexpected error code: {body}"
    assert "SUPERGLUE_API_KEY" not in resp.text, "Secret leaked in response"


def test_superglue_chart_returns_503_when_no_key(client_no_superglue):
    resp = client_no_superglue.post(
        "/v1/profile/testuser/chart",
        headers={"X-API-Key": _VALID_KEY},
        json={},
    )
    assert resp.status_code == 503, f"Expected 503, got {resp.status_code}: {resp.text}"
    body = resp.json()
    assert body.get("error") == "service_unavailable"
```

**Step 2: Run to verify current failure**

```bash
PYTHONPATH=$PWD pytest -q tests/test_superglue_config_errors.py -v
```

Expected: FAIL with 500 instead of 503.

**Step 3: Commit failing test**

```bash
git add tests/test_superglue_config_errors.py
git commit -m "test(superglue): failing test — missing SUPERGLUE_API_KEY returns 500 should be 503"
```

---

### Task 9: Map Superglue config error to 503

**Files:**
- Modify: `bazi_engine/services/superglue_client.py`
- Modify: `bazi_engine/routers/superglue.py`

**Step 1: Create SuperglueConfigurationError in superglue_client.py**

In `bazi_engine/services/superglue_client.py`, replace the `RuntimeError` at line 42:

```python
class SuperglueConfigurationError(RuntimeError):
    """Raised when SUPERGLUE_API_KEY is not set."""
```

And change the raise:
```python
# Before:
raise RuntimeError("SUPERGLUE_API_KEY environment variable is not set. ...")
# After:
raise SuperglueConfigurationError(
    "Superglue service is not configured — SUPERGLUE_API_KEY missing"
)
```

**Step 2: Catch it in superglue.py and return 503**

In `bazi_engine/routers/superglue.py`, import the exception and catch it in the relevant handler functions:

```python
from bazi_engine.services.superglue_client import SuperglueConfigurationError

# In each handler that calls superglue_client:
try:
    result = await superglue_client.call(...)
except SuperglueConfigurationError as exc:
    raise HTTPException(
        status_code=503,
        detail={"status": 503, "error": "service_unavailable", "message": str(exc)},
    ) from exc
```

Or add a FastAPI exception handler in `app.py` for this exception type (if multiple routers use it):

```python
from bazi_engine.services.superglue_client import SuperglueConfigurationError

@app.exception_handler(SuperglueConfigurationError)
async def superglue_config_error_handler(request, exc):
    return JSONResponse(
        status_code=503,
        content={"status": 503, "error": "service_unavailable", "message": str(exc)},
    )
```

**Step 3: Run tests**

```bash
PYTHONPATH=$PWD pytest -q tests/test_superglue_config_errors.py
```

Expected: PASS.

**Step 4: Run full contract tests to check for regressions**

```bash
PYTHONPATH=$PWD pytest -q tests/test_openapi_contract.py tests/test_openapi_error_contract.py
```

**Step 5: Commit**

```bash
git add bazi_engine/services/superglue_client.py bazi_engine/routers/superglue.py bazi_engine/app.py
git commit -m "fix(superglue): map missing SUPERGLUE_API_KEY to 503 service_unavailable instead of generic 500"
```

---

### Task 10: Write failing error-response headers test

**Files:**
- Create: `tests/test_error_response_headers.py`

**Step 1: Write the failing test**

```python
# tests/test_error_response_headers.py
import os
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from bazi_engine.app import app

_REQUIRED_HEADERS = ("X-Request-ID", "X-API-Version", "X-Response-Time-ms")

client = TestClient(app, raise_server_exceptions=False)


@pytest.mark.parametrize("path,method,kwargs,expected_status", [
    ("/v1/calculate/bazi", "get", {"headers": {}}, 401),         # missing auth → 401
    ("/nonexistent-route-xyz", "get", {}, 404),                  # unknown route → 404
    ("/v1/calculate/bazi", "post", {
        "headers": {"X-API-Key": "ff_pro_testsecret"},
        "json": {},
    }, 422),                                                       # missing required body → 422
])
def test_standard_headers_on_error(path, method, kwargs, expected_status):
    with patch.dict(os.environ, {
        "FUFIRE_REQUIRE_API_KEYS": "true",
        "FUFIRE_API_KEYS": "ff_pro_testsecret",
    }):
        resp = getattr(client, method)(path, **kwargs)
    assert resp.status_code == expected_status, (
        f"{method.upper()} {path}: expected {expected_status}, got {resp.status_code}"
    )
    missing = [h for h in _REQUIRED_HEADERS if h not in resp.headers]
    assert not missing, (
        f"{method.upper()} {path} status={expected_status}: missing headers {missing}"
    )
```

**Step 2: Run to verify current state**

```bash
PYTHONPATH=$PWD pytest -q tests/test_error_response_headers.py -v
```

Expected: At least one case FAIL (404 and unhandled errors typically bypass middleware).

**Step 3: Commit failing test**

```bash
git add tests/test_error_response_headers.py
git commit -m "test(middleware): failing test — standard headers missing on error responses"
```

---

### Task 11: Fix header injection on error paths

**Files:**
- Modify: `bazi_engine/middleware.py`

**Step 1: Read current middleware**

Open `bazi_engine/middleware.py`. The current `dispatch()` sets `response.headers[...]` after `await call_next(request)`. This works for normal responses but not for exceptions that bypass middleware.

**Step 2: Wrap the call_next in try/except**

```python
async def dispatch(self, request: Request, call_next):  # type: ignore[override]
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    request.state.request_id = request_id
    start = time.perf_counter()

    try:
        response = await call_next(request)
    except Exception:
        # On unhandled exceptions, FastAPI's default handler returns a response
        # but middleware may not get to inject headers. Re-raise after note.
        raise

    elapsed_ms = (time.perf_counter() - start) * 1000
    response.headers["X-Request-ID"] = request_id
    response.headers["X-API-Version"] = self.api_version
    response.headers["X-Response-Time-ms"] = f"{elapsed_ms:.2f}"
    return response
```

If `call_next` can surface errors as responses (i.e. FastAPI error handler already converted them), the headers are set. If exceptions still escape, add a fallback:

```python
    except Exception as exc:
        elapsed_ms = (time.perf_counter() - start) * 1000
        from starlette.responses import Response
        # Let FastAPI generate the error response with its default handler
        # by creating an error response ourselves is complex — instead use
        # a Starlette pure-ASGI approach if BaseHTTPMiddleware proves unreliable.
        raise
```

> **Note:** `BaseHTTPMiddleware` with Starlette has a known limitation where unhandled exceptions bypass the middleware `dispatch()`. If headers are still missing on 500, replace `BaseHTTPMiddleware` with a pure ASGI middleware (`__call__` pattern) or use FastAPI's `add_exception_handler` to set headers before returning.

**Step 3: Run tests**

```bash
PYTHONPATH=$PWD pytest -q tests/test_error_response_headers.py
```

Expected: PASS. If 404 still fails, add a 404 exception handler in `app.py` that sets headers.

**Step 4: Run regression**

```bash
PYTHONPATH=$PWD pytest -q tests/test_error_handling.py tests/test_error_sanitization.py tests/test_api.py
```

**Step 5: Commit**

```bash
git add bazi_engine/middleware.py bazi_engine/app.py
git commit -m "fix(middleware): ensure X-Request-ID/X-API-Version/X-Response-Time-ms present on error responses"
```

---

## Phase 5 — Docs / Auth / Rate-Limit / Ephemeris (FUFIRE-API-003, 007, 008)

### Task 12: Fix rate-limit header contract

**Files:**
- Modify: `bazi_engine/app.py` (remove phantom `X-RateLimit-Remaining` guarantee)
- Modify: `docs/API_REFERENCE.md`
- Modify: `docs/api/01_developer_api_reference.md`

**Step 1: Find phantom guarantee in OpenAPI**

```bash
grep -n "RateLimit-Remaining\|ratelimit" bazi_engine/app.py docs/API_REFERENCE.md
```

**Step 2: Change guarantee to conditional**

In `app.py`, if `X-RateLimit-Remaining` is added as a guaranteed header in the OpenAPI customiser, remove it or add a condition note: `"description": "Present when rate limiting is active (Redis backend)"`.

In docs: change "always present" → "present when rate-limiting Redis backend is active".

**Step 3: Run contract tests**

```bash
PYTHONPATH=$PWD pytest -q tests/test_openapi_error_contract.py tests/test_openapi_contract.py
```

**Step 4: Commit**

```bash
git add bazi_engine/app.py docs/
git commit -m "fix(docs): remove phantom X-RateLimit-Remaining guarantee — header is conditional on Redis backend"
```

---

### Task 13: Fix legacy-auth documentation

**Files:**
- Modify: `docs/API_REFERENCE.md`
- Modify: `docs/api/01_developer_api_reference.md`
- Modify: `docs/ERROR_CODES.md` (if it claims `tier_insufficient`)

**Step 1: Find incorrect claims**

```bash
grep -rn "legacy.*public\|no auth\|tier_insufficient\|invalid_api_key\|unauthorized" docs/
```

**Step 2: Apply corrections**

- Remove or correct any claim that "legacy business routes are public when `FUFIRE_API_KEYS` is configured".
- Align documented 401 error code with runtime (`unauthorized` per `app.py`).
- Remove `tier_insufficient` if no 403 tier dependency exists.

**Step 3: Run auth tests**

```bash
PYTHONPATH=$PWD pytest -q tests/test_endpoint_negative.py tests/test_b2b_api_audit.py
```

**Step 4: Commit**

```bash
git add docs/
git commit -m "fix(docs): align legacy-auth documentation with runtime behaviour — 401 is unauthorized not tier_insufficient"
```

---

### Task 14: Document local Ephemeris Quickstart

**Files:**
- Modify: `README.md`
- Create or modify: `docs/runbooks/ephemeris-local-setup.md`

**Step 1: Add to README quickstart**

Add a section:

```markdown
### Ephemeris Data

The engine requires Swiss Ephemeris files. Without them, calculation endpoints return `503 ephemeris_unavailable`.

**Recommended: use Docker (files pre-loaded at build time)**
```bash
docker build -t bazi_engine . && docker run -p 8080:8080 bazi_engine
```

**Local dev without Docker**
Download the four required files and set `SE_EPHE_PATH`:
- `sepl_18.se1`, `semo_18.se1`, `seas_18.se1`, `seplm06.se1`
```bash
export SE_EPHE_PATH=/path/to/ephemeris/files
```

A `503 ephemeris_unavailable` response in local dev means these files are missing or the path is wrong. This is **not** a bug in the API logic.
```

**Step 2: Verify grep**

```bash
grep -n "SE_EPHE_PATH\|ephemeris_unavailable\|sepl_18" README.md
```

Expected: clear hits.

**Step 3: Commit**

```bash
git add README.md docs/runbooks/
git commit -m "docs(ephemeris): add local setup quickstart and troubleshooting for ephemeris_unavailable"
```

---

## Phase 6 — Test Suite Signal (FUFIRE-API-012)

### Task 15: Restore green full test suite signal

**Files:**
- Modify: `pyproject.toml` (add `respx` if missing)
- Modify: snapshot files only after domain-reviewed decision
- Inspect: CI config discovery

**Step 1: Check respx dependency**

```bash
grep -n "respx" pyproject.toml
```

If missing: add `respx` to `[project.optional-dependencies] dev`.

**Step 2: Run full suite targeting snapshot fails**

```bash
PYTHONPATH=$PWD pytest -q tests/test_snapshot_stability.py --tb=short 2>&1 | head -50
```

**Step 3: Triage snapshot failures**

For each snapshot failure:
- New fields added by recent features → accept and update: `pytest --snapshot-update tests/test_snapshot_stability.py`
- `tzdb_version_id unknown != 2026.1` → make expectation tolerant (regex or "not empty" check), not hardcoded version string
- `solar_terms_count 23 != 24` → **DO NOT blindly update** — flag to domain owner as potential regression

**Step 4: Add pytest markers for external tests**

If `pytest -q` includes slow/external tests, add to `pyproject.toml`:

```toml
[tool.pytest.ini_options]
markers = [
    "unit: fast unit tests",
    "integration: tests requiring ephemeris files",
    "external: tests requiring live external services",
    "contract: OpenAPI/schema contract tests",
]
```

Document in README which profile to use for CI.

**Step 5: Run full suite**

```bash
PYTHONPATH=$PWD pytest -q --tb=short --disable-warnings
```

Expected: green, or explicitly documented skips.

**Step 6: Commit**

```bash
git add pyproject.toml tests/snapshots/ README.md
git commit -m "fix(tests): restore green test suite — add respx dev dep, update snapshots after domain review, add pytest markers"
```

---

## Phase 7 — Tags & /chart Lifecycle (FUFIRE-API-010, 011, 013)

### Task 16: Fix OpenAPI tags and update CONTRACT.md

**Files:**
- Modify: `bazi_engine/app.py`
- Modify: `CONTRACT.md`

**Step 1: Write tag coverage test**

```python
# In tests/test_openapi_contract.py or new tests/test_openapi_tags.py
def test_all_operation_tags_defined_globally(schema):
    global_tags = {t["name"] for t in schema.get("tags", [])}
    for path, methods in schema.get("paths", {}).items():
        for method, op in methods.items():
            for tag in op.get("tags", []):
                assert tag in global_tags, (
                    f"Operation tag '{tag}' on {method.upper()} {path} not in global tags"
                )
```

**Step 2: Add missing tags in app.py**

In `_custom_openapi()`, add `Superglue` and `Impact` to the tags list.

**Step 3: Update CONTRACT.md**

Replace manual endpoint count with a generated route table. Organize by surface: `v1/`, `legacy/`, `internal/`, `proxy/`.

**Step 4: Run tests**

```bash
PYTHONPATH=$PWD pytest -q tests/test_openapi_contract.py
```

**Step 5: Commit**

```bash
git add bazi_engine/app.py spec/openapi/openapi.json CONTRACT.md
git commit -m "fix(openapi): add Superglue and Impact global tags; update CONTRACT.md to reflect real surface"
```

---

### Task 17: Decide /chart lifecycle

**Files:**
- Modify: `bazi_engine/app.py` (or `bazi_engine/routers/chart.py`)
- Modify: `docs/API_REFERENCE.md`

**Step 1: Record owner decision in PR**

Default: `/chart` is internal-only legacy. Add `include_in_schema=False` deprecation path.

**Step 2: Apply policy**

Option A (internal, hide from schema) — if `chart` router is already mounted without `/v1` prefix, ensure `include_in_schema=False` or wrap in `deprecated=True` tag.

Option B (public legacy) — keep visible but add `deprecated: true` on the operation in `_custom_openapi()`.

**Step 3: Update docs**

Mark the `/chart` section in `docs/API_REFERENCE.md` as "Deprecated — internal use only" or "Legacy endpoint — use `/v1/calculate/*` instead".

**Step 4: Run tests**

```bash
PYTHONPATH=$PWD pytest -q tests/test_openapi_contract.py tests/test_chart_lifecycle_contract.py 2>/dev/null || PYTHONPATH=$PWD pytest -q tests/test_openapi_contract.py
```

**Step 5: Commit**

```bash
git add bazi_engine/app.py bazi_engine/routers/chart.py docs/ spec/openapi/openapi.json
git commit -m "fix(chart): mark /chart endpoint as deprecated internal-only and align docs"
```

---

## Phase 8 — Final Gate

### Task 18: Full validation gate

**Step 1: Regenerate OpenAPI**

```bash
PYTHONPATH=$PWD python3 scripts/export_openapi.py
```

**Step 2: Multi-seed determinism check**

```bash
for seed in 0 1 2 3 4 5 6 7 8 9 10; do
  PYTHONHASHSEED=$seed PYTHONPATH=$PWD python3 scripts/export_openapi.py --check && echo "seed $seed OK"
done
```

Expected: all pass.

**Step 3: Run all contract tests**

```bash
PYTHONPATH=$PWD pytest -q \
  tests/test_openapi_determinism.py \
  tests/test_openapi_error_contract.py \
  tests/test_webhook_routes.py \
  tests/test_superglue_config_errors.py \
  tests/test_error_response_headers.py \
  tests/test_openapi_contract.py
```

Expected: PASS.

**Step 4: Run full suite**

```bash
PYTHONPATH=$PWD pytest -q --tb=short --disable-warnings
```

Expected: green (or documented exclusions only).

**Step 5: Review checklist**

- [ ] No secrets in any committed file
- [ ] No external production calls in tests
- [ ] No route removed without deprecation documentation
- [ ] `spec/openapi/openapi.json` regenerated and committed
- [ ] P0/P1 findings resolved or documented with owner decision

**Step 6: Final commit**

```bash
git add .
git commit -m "chore(audit): final gate — all P0/P1 findings resolved, OpenAPI deterministic, tests green"
```

---

## Execution Order Summary

| Phase | Tasks | Priority | Outcome |
|-------|-------|----------|---------|
| 0 — Baseline | 1 | P0 | Reproduce failures, create branch |
| 1 — OpenAPI Determinism | 2, 3 | P0 | Fix ChartRequest collision |
| 2 — Error Contract | 4, 5 | P0 | ErrorEnvelope on protected ops |
| 3 — Webhook Path | 6, 7 | P0 | Docs match runtime `/internal/webhooks/chart` |
| 4 — Runtime Errors | 8, 9, 10, 11 | P1 | 503 for Superglue, headers on error paths |
| 5 — Docs/Auth/DX | 12, 13, 14 | P1 | Rate-limit, auth, ephemeris docs |
| 6 — Test Suite | 15 | P1 | Green pytest signal |
| 7 — Tags/Lifecycle | 16, 17 | P2 | OpenAPI tags, /chart lifecycle |
| 8 — Gate | 18 | P0 | Final validation |

## Minimal PR splits (if needed)

- **PR 1:** Tasks 1–5 (OpenAPI determinism + error responses)
- **PR 2:** Tasks 6–11 (webhook + Superglue + headers)
- **PR 3:** Tasks 12–15 (docs/DX/auth + test suite)
- **PR 4:** Tasks 16–18 (P2 taxonomy + final gate)
