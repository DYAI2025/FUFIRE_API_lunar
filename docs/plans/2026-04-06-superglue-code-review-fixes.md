# Superglue Code Review Fixes Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix one critical and three important issues identified in the code review of the Superglue proxy router.

**Architecture:** All changes are confined to `bazi_engine/routers/superglue.py`, `bazi_engine/app.py`, and `tests/test_superglue_client.py`. No new files. No behaviour changes for valid requests — only tightening input validation and clarifying code intent.

**Tech Stack:** FastAPI `Path()` constraint, Python `NoReturn` type, pytest

---

## Issues Being Fixed

| Severity | Issue | File |
|---|---|---|
| 🔴 Critical | `user_id` path parameter has no validation — raw string flows into Superglue URL | `routers/superglue.py` |
| 🟡 Important | `_handle_httpx_error` return type is misleading — can raise OR return an HTTPException | `routers/superglue.py` |
| 🟡 Important | `/v1/api/profile/{user_id}` double-prefix — inconsistent with all other `/v1/` routes | `routers/superglue.py` + `app.py` |
| 🟡 Important | Unused `monkeypatch` parameter in `test_call_hook_success` | `tests/test_superglue_client.py` |

---

## Task 1: Add `user_id` path validation (Critical)

The three endpoint handlers accept any string for `user_id`. If Superglue interpolates it anywhere, a malformed value (`../`, very long strings, null bytes) could cause issues. FastAPI's `Path()` lets us enforce a pattern at the framework level — invalid values return 422 before any code runs.

**Valid `user_id` pattern:** `^[a-zA-Z0-9_\-]{1,128}$` — covers UUIDs (Supabase), short slugs, and alphanumeric IDs. Rejects slashes, dots, null bytes, and overlength strings.

**Files:**
- Modify: `bazi_engine/routers/superglue.py` (all three handlers)
- Modify: `tests/test_superglue_router.py` (add two validation tests)

**Step 1: Write the failing validation tests**

Add these two tests to the END of `tests/test_superglue_router.py`:

```python
def test_get_profile_rejects_invalid_user_id(client):
    """user_id with path traversal chars should return 422, not reach Superglue."""
    resp = client.get("/api/profile/../secret")
    assert resp.status_code == 422

def test_get_daily_rejects_overlength_user_id(client):
    """user_id longer than 128 chars should return 422."""
    resp = client.get(f"/api/daily/{'x' * 129}")
    assert resp.status_code == 422
```

**Step 2: Run to confirm they fail (currently 200 or 500, not 422)**

```bash
cd /Users/benjaminpoersch/Projects/codebase/FuFirE && \
  SUPERGLUE_API_KEY=test FUFIRE_REQUIRE_API_KEYS=false \
  .venv/bin/pytest tests/test_superglue_router.py::test_get_profile_rejects_invalid_user_id \
                   tests/test_superglue_router.py::test_get_daily_rejects_overlength_user_id -v 2>&1 | tail -10
```

Expected: FAIL (404 from FastAPI not matching the route pattern, or a non-422 response)

**Step 3: Add `Path()` constraint to all three handlers**

In `bazi_engine/routers/superglue.py`, update the import line:

```python
# Before:
from fastapi import APIRouter, HTTPException, Request

# After:
from fastapi import APIRouter, HTTPException, Path, Request
```

Then update all three handler signatures. The `Path()` parameter replaces the plain `user_id: str` annotation:

```python
# get_profile — before:
async def get_profile(user_id: str, request: Request) -> Dict[str, Any]:

# get_profile — after:
async def get_profile(
    user_id: str = Path(..., pattern=r"^[a-zA-Z0-9_\-]{1,128}$"),
    request: Request = ...,  # FastAPI resolves Request automatically
) -> Dict[str, Any]:
```

Wait — FastAPI doesn't support `request: Request = ...` as a keyword default. The correct signature when mixing `Path()` with `Request` is:

```python
async def get_profile(
    request: Request,
    user_id: str = Path(..., pattern=r"^[a-zA-Z0-9_\-]{1,128}$"),
) -> Dict[str, Any]:
```

Apply this pattern to all three handlers. Full updated handler signatures:

```python
@router.get("/profile/{user_id}")
@limiter.limit("30/minute")
async def get_profile(
    request: Request,
    user_id: str = Path(..., pattern=r"^[a-zA-Z0-9_\-]{1,128}$"),
) -> Dict[str, Any]:
    """Fetch ElevenLabs context for a user via Superglue bazodiac-elevenlabs-context hook."""
    try:
        return await call_hook("bazodiac-elevenlabs-context", {"user_id": user_id})
    except (httpx.HTTPStatusError, httpx.TimeoutException) as exc:
        raise _handle_httpx_error(exc)


@router.get("/daily/{user_id}")
@limiter.limit("30/minute")
async def get_daily(
    request: Request,
    user_id: str = Path(..., pattern=r"^[a-zA-Z0-9_\-]{1,128}$"),
) -> Dict[str, Any]:
    """Fetch daily transit horoscope for a user via Superglue bazodiac-daily-transit hook."""
    try:
        return await call_hook("bazodiac-daily-transit", {"user_id": user_id})
    except (httpx.HTTPStatusError, httpx.TimeoutException) as exc:
        raise _handle_httpx_error(exc)


@router.post("/profile/{user_id}/chart")
@limiter.limit("10/minute")
async def trigger_user_chart(
    request: Request,
    user_id: str = Path(..., pattern=r"^[a-zA-Z0-9_\-]{1,128}$"),
    body: ChartRequest = ...,
) -> Dict[str, Any]:
    """Trigger or refresh chart calculation for a user via Superglue bazodiac-user-chart hook."""
    try:
        return await call_hook(
            "bazodiac-user-chart",
            {"user_id": user_id, "force_recalculate": body.force_recalculate},
        )
    except (httpx.HTTPStatusError, httpx.TimeoutException) as exc:
        raise _handle_httpx_error(exc)
```

**IMPORTANT NOTE on `trigger_user_chart`:** FastAPI resolves `body: ChartRequest = ...` from the request JSON. Using `= ...` (Ellipsis) as default is valid FastAPI syntax for required body. If this causes issues, use `body: ChartRequest` without a default.

**Step 4: Run all router tests**

```bash
cd /Users/benjaminpoersch/Projects/codebase/FuFirE && \
  SUPERGLUE_API_KEY=test FUFIRE_REQUIRE_API_KEYS=false \
  .venv/bin/pytest tests/test_superglue_router.py -v 2>&1 | tail -20
```

Expected: all 7 tests PASS (5 original + 2 new validation tests).

**Step 5: Commit**

```bash
cd /Users/benjaminpoersch/Projects/codebase/FuFirE && \
  git add bazi_engine/routers/superglue.py tests/test_superglue_router.py && \
  git commit -m "fix: add user_id path validation to Superglue proxy endpoints"
```

---

## Task 2: Fix `_handle_httpx_error` to always raise (`NoReturn`)

Currently the function has return type `HTTPException` and a mix of `return HTTPException(...)` and `raise exc`. The call sites do `raise _handle_httpx_error(exc)`. When the helper re-raises via `raise exc`, the caller's `raise` is dead code — confusing and fragile.

The fix: the function should always raise internally (`NoReturn`). Call sites then call it without `raise`.

**Files:**
- Modify: `bazi_engine/routers/superglue.py`

No new tests needed — existing tests already cover all three paths. The behavior is identical; only the code structure improves.

**Step 1: Update the import to add `NoReturn`**

```python
# Before:
from typing import Any, Dict

# After:
from typing import Any, Dict, NoReturn
```

**Step 2: Rewrite `_handle_httpx_error`**

```python
# Before:
def _handle_httpx_error(exc: Exception) -> HTTPException:
    if isinstance(exc, httpx.HTTPStatusError):
        return HTTPException(
            status_code=exc.response.status_code,
            detail={"error": "superglue_upstream_error", "message": str(exc)},
        )
    if isinstance(exc, httpx.TimeoutException):
        return HTTPException(
            status_code=504,
            detail={"error": "superglue_timeout", "message": "Superglue hook timed out"},
        )
    raise exc

# After:
def _handle_httpx_error(exc: Exception) -> NoReturn:
    if isinstance(exc, httpx.HTTPStatusError):
        raise HTTPException(
            status_code=exc.response.status_code,
            detail={"error": "superglue_upstream_error", "message": str(exc)},
        )
    if isinstance(exc, httpx.TimeoutException):
        raise HTTPException(
            status_code=504,
            detail={"error": "superglue_timeout", "message": "Superglue hook timed out"},
        )
    raise exc
```

**Step 3: Update the three call sites — remove `raise`**

```python
# Before (in each handler):
except (httpx.HTTPStatusError, httpx.TimeoutException) as exc:
    raise _handle_httpx_error(exc)

# After:
except (httpx.HTTPStatusError, httpx.TimeoutException) as exc:
    _handle_httpx_error(exc)
```

**Step 4: Run all tests to confirm no behaviour change**

```bash
cd /Users/benjaminpoersch/Projects/codebase/FuFirE && \
  SUPERGLUE_API_KEY=test FUFIRE_REQUIRE_API_KEYS=false \
  .venv/bin/pytest tests/test_superglue_router.py tests/test_superglue_client.py -v 2>&1 | tail -15
```

Expected: all tests still pass (7 router + 3 client = 10 total).

**Step 5: Commit**

```bash
cd /Users/benjaminpoersch/Projects/codebase/FuFirE && \
  git add bazi_engine/routers/superglue.py && \
  git commit -m "refactor: _handle_httpx_error always raises (NoReturn)"
```

---

## Task 3: Fix double `/v1/api/` prefix

Currently `superglue.router` has `prefix="/api"` and is also registered with `prefix="/v1"` in `app.py`, producing `/v1/api/profile/{user_id}`. Every other v1 route is `/v1/<resource>/...` (no `/api/` segment). These are new endpoints not yet deployed, so fixing the path is safe.

**Fix:** Remove `prefix="/api"` from the router definition. Register explicitly with `prefix="/api"` for the legacy path and `prefix="/v1"` for the v1 path (which gives `/v1/profile/{user_id}` — consistent with all other v1 routes).

**Files:**
- Modify: `bazi_engine/routers/superglue.py:22`
- Modify: `bazi_engine/app.py:317`

**Step 1: Remove prefix from router definition**

In `bazi_engine/routers/superglue.py`, line 22:

```python
# Before:
router = APIRouter(prefix="/api", tags=["Superglue"])

# After:
router = APIRouter(tags=["Superglue"])
```

**Step 2: Add explicit `/api` prefix to the legacy registration in app.py**

In `bazi_engine/app.py`, find line 317:

```python
# Before:
app.include_router(superglue.router, dependencies=_protected)

# After:
app.include_router(superglue.router, prefix="/api", dependencies=_protected)
```

The v1 registration on line 330 already has `prefix="/v1"`, so after this change the v1 routes will be at `/v1/profile/{user_id}` and `/v1/daily/{user_id}` — which is the correct pattern.

**Step 3: Update router tests that use the legacy `/api/` paths**

The existing tests use `/api/profile/...` and `/api/daily/...`. These are the legacy routes registered WITHOUT the `/v1` prefix. They stay at the same path — no test changes needed for them.

However, also add a quick sanity test that the v1 path works correctly now:

Add to `tests/test_superglue_router.py`:

```python
@respx.mock
def test_v1_profile_path_works(client):
    """v1 route is at /v1/profile/{user_id}, not /v1/api/profile/{user_id}."""
    respx.post(
        "https://api.superglue.ai/v1/hooks/bazodiac-elevenlabs-context?token=tok_test"
    ).mock(return_value=httpx.Response(200, json={"ok": True}))

    resp = client.get("/v1/profile/u_1")
    assert resp.status_code == 200

def test_v1_api_double_prefix_is_gone(client):
    """The old /v1/api/ double-prefix path must NOT exist."""
    resp = client.get("/v1/api/profile/u_1")
    assert resp.status_code == 404
```

**Step 4: Run all tests**

```bash
cd /Users/benjaminpoersch/Projects/codebase/FuFirE && \
  SUPERGLUE_API_KEY=test FUFIRE_REQUIRE_API_KEYS=false \
  .venv/bin/pytest tests/test_superglue_router.py -v 2>&1 | tail -20
```

Expected: all 9 tests pass.

**Step 5: Commit**

```bash
cd /Users/benjaminpoersch/Projects/codebase/FuFirE && \
  git add bazi_engine/routers/superglue.py bazi_engine/app.py tests/test_superglue_router.py && \
  git commit -m "fix: remove /v1/api double-prefix — v1 routes now at /v1/profile and /v1/daily"
```

---

## Task 4: Remove unused `monkeypatch` parameter

One-liner. `test_call_hook_success` declares `monkeypatch` but the autouse fixture handles the env var — `monkeypatch` is never used in the function body.

**Files:**
- Modify: `tests/test_superglue_client.py`

**Step 1: Remove the parameter**

```python
# Before:
def test_call_hook_success(monkeypatch):

# After:
def test_call_hook_success():
```

**Step 2: Verify tests still pass**

```bash
cd /Users/benjaminpoersch/Projects/codebase/FuFirE && \
  SUPERGLUE_API_KEY=test FUFIRE_REQUIRE_API_KEYS=false \
  .venv/bin/pytest tests/test_superglue_client.py -v 2>&1 | tail -10
```

Expected: 3 passed.

**Step 3: Commit**

```bash
cd /Users/benjaminpoersch/Projects/codebase/FuFirE && \
  git add tests/test_superglue_client.py && \
  git commit -m "fix: remove unused monkeypatch param in test_call_hook_success"
```

---

## Final verification

Run the full Superglue test suite:

```bash
cd /Users/benjaminpoersch/Projects/codebase/FuFirE && \
  SUPERGLUE_API_KEY=test FUFIRE_REQUIRE_API_KEYS=false \
  .venv/bin/pytest tests/test_superglue_router.py tests/test_superglue_client.py -v 2>&1
```

Expected: **12 tests pass** (9 router + 3 client).
