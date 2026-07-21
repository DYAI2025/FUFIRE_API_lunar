# Code Review Hardening Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix 3 High and 2 Medium code review findings (H1 key masking, H2 key caching, H3 OpenAPI method filtering, M3 test env leak, M5 missing starter test).

**Architecture:** All changes are 1–10 line surgical edits. No new abstractions. TDD where applicable.

**Tech Stack:** Python 3.10+, FastAPI, Pydantic v2, pytest

---

### Task 1: H1 — Mask API key in `KeyInfo.__repr__`

**Root cause:** `KeyInfo` is a frozen dataclass. Its default `repr` exposes the full API key in tracebacks, logs, and debug output.

**Files:**
- Modify: `bazi_engine/auth.py:38-44`
- Test: `tests/test_b2b_infra.py`

**Step 1: Write the failing test**

Add to `TestApiKeyTiers` in `tests/test_b2b_infra.py`:

```python
    def test_key_info_repr_masks_secret(self):
        from bazi_engine.auth import resolve_key_info
        info = resolve_key_info("ff_pro_supersecret123")
        r = repr(info)
        assert "supersecret123" not in r
        assert "ff_pro_" in r
```

**Step 2: Run test to verify it fails**

```bash
.venv/bin/python -m pytest tests/test_b2b_infra.py::TestApiKeyTiers::test_key_info_repr_masks_secret -v
```
Expected: FAIL (default repr includes the full key)

**Step 3: Add `__repr__` to `KeyInfo`**

In `bazi_engine/auth.py`, replace:

```python
@dataclass(frozen=True)
class KeyInfo:
    """Metadata resolved from an API key."""
    key: str
    tier: str
    requests_per_day: int
    requests_per_minute: int
```

With:

```python
@dataclass(frozen=True)
class KeyInfo:
    """Metadata resolved from an API key."""
    key: str
    tier: str
    requests_per_day: int
    requests_per_minute: int

    def __repr__(self) -> str:
        masked = self.key[:8] + "..." if len(self.key) > 8 else "***"
        return f"KeyInfo(key='{masked}', tier='{self.tier}', rpm={self.requests_per_minute})"
```

**Step 4: Run test to verify it passes**

```bash
.venv/bin/python -m pytest tests/test_b2b_infra.py::TestApiKeyTiers::test_key_info_repr_masks_secret -v
```
Expected: PASS

**Step 5: Commit**

```bash
git add bazi_engine/auth.py tests/test_b2b_infra.py
git commit -m "security(auth): mask API key in KeyInfo repr to prevent log exposure"
```

---

### Task 2: H2 — Cache `_load_keys()` to avoid per-request env parsing

**Root cause:** `_load_keys()` parses `FUFIRE_API_KEYS` on every authenticated request. In production, env vars don't change at runtime. The frozenset construction is wasted work.

**Files:**
- Modify: `bazi_engine/auth.py:65-69`
- Test: `tests/test_b2b_infra.py`

**Step 1: Write the test that verifies caching behavior**

Add to `TestApiKeyTiers` in `tests/test_b2b_infra.py`:

```python
    def test_load_keys_caches_result(self):
        """_load_keys should return the same object on repeated calls (cached)."""
        from bazi_engine.auth import _load_keys
        os.environ["FUFIRE_API_KEYS"] = "test-cache-key"
        try:
            result1 = _load_keys()
            result2 = _load_keys()
            assert result1 is result2  # same object = cached
        finally:
            os.environ.pop("FUFIRE_API_KEYS", None)
            _load_keys.cache_clear()
```

**Step 2: Run test to verify it fails**

```bash
.venv/bin/python -m pytest tests/test_b2b_infra.py::TestApiKeyTiers::test_load_keys_caches_result -v
```
Expected: FAIL — `_load_keys` has no `cache_clear` attribute

**Step 3: Add `lru_cache` to `_load_keys()`**

In `bazi_engine/auth.py`, add to imports:

```python
from functools import lru_cache
```

Replace `_load_keys`:

```python
@lru_cache(maxsize=1)
def _load_keys() -> frozenset[str]:
    raw = os.environ.get("FUFIRE_API_KEYS", "")
    if not raw.strip():
        return frozenset()
    return frozenset(k.strip() for k in raw.split(",") if k.strip())
```

**Important:** We also need tests that change env vars to call `_load_keys.cache_clear()` in teardown. The existing `TestApiKeyAuth.teardown_method` must call it:

In `tests/test_b2b_infra.py`, update `TestApiKeyAuth.teardown_method`:

```python
    def teardown_method(self):
        os.environ.pop("FUFIRE_API_KEYS", None)
        os.environ.pop("FUFIRE_REQUIRE_API_KEYS", None)
        from bazi_engine.auth import _load_keys
        _load_keys.cache_clear()
```

Also add cache clear to `test_v1_quota_headers_present` cleanup (in `TestTieredRateLimiting`):

Replace:
```python
        os.environ.pop("FUFIRE_API_KEYS", None)
```

With:
```python
        os.environ.pop("FUFIRE_API_KEYS", None)
        from bazi_engine.auth import _load_keys
        _load_keys.cache_clear()
```

And update `TestApiKeyAuth.setup_method` to clear cache before setting new env:

```python
    def setup_method(self):
        os.environ["FUFIRE_API_KEYS"] = "test-key-abc,test-key-xyz"
        from bazi_engine.auth import _load_keys
        _load_keys.cache_clear()
```

**Step 4: Run tests to verify all pass**

```bash
.venv/bin/python -m pytest tests/test_b2b_infra.py -q --tb=short
```
Expected: all pass

**Step 5: Commit**

```bash
git add bazi_engine/auth.py tests/test_b2b_infra.py
git commit -m "perf(auth): cache _load_keys() with lru_cache to avoid per-request env parsing"
```

---

### Task 3: H3 — Filter OpenAPI header injection to HTTP methods only

**Root cause:** The loop in `_custom_openapi()` iterates all keys in path items, which can include `"parameters"`, `"summary"`, etc. Calling `.get("responses", {})` on non-dict values won't crash but is semantically wrong and fragile.

**Files:**
- Modify: `bazi_engine/app.py:353-359`

**Step 1: Apply the fix**

In `bazi_engine/app.py`, replace:

```python
    for path, methods in schema.get("paths", {}).items():
        is_v1 = path.startswith("/v1/")
        for method, op in methods.items():
            for status_code, resp in op.get("responses", {}).items():
```

With:

```python
    _HTTP_METHODS = {"get", "put", "post", "delete", "options", "head", "patch", "trace"}
    for path, methods in schema.get("paths", {}).items():
        is_v1 = path.startswith("/v1/")
        for method, op in methods.items():
            if method not in _HTTP_METHODS:
                continue
            for status_code, resp in op.get("responses", {}).items():
```

**Step 2: Regenerate and verify spec unchanged**

```bash
.venv/bin/python scripts/export_openapi.py --check
```
Expected: OK: OpenAPI spec is up-to-date.

**Step 3: Run OpenAPI tests**

```bash
.venv/bin/python -m pytest tests/test_openapi_contract.py -q --tb=short
```
Expected: all pass

**Step 4: Commit**

```bash
git add bazi_engine/app.py
git commit -m "fix(openapi): filter path item iteration to HTTP methods only"
```

---

### Task 4: M3 — Fix env leak in `test_v1_quota_headers_present`

**Root cause:** The test sets `FUFIRE_API_KEYS` and cleans up inline. If the test fails before cleanup, the env var leaks to subsequent tests.

**Files:**
- Modify: `tests/test_b2b_infra.py` (~line 311-327)

**Step 1: Wrap test in try/finally**

Replace the full `test_v1_quota_headers_present` method:

```python
    def test_v1_quota_headers_present(self):
        """V1 routes with valid key must return quota headers."""
        os.environ["FUFIRE_API_KEYS"] = "ff_free_testquota"
        from bazi_engine.auth import _load_keys
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
            assert "x-ratelimit-remaining" in response.headers
        finally:
            os.environ.pop("FUFIRE_API_KEYS", None)
            _load_keys.cache_clear()
```

**Step 2: Run tests**

```bash
.venv/bin/python -m pytest tests/test_b2b_infra.py::TestTieredRateLimiting -q --tb=short
```
Expected: all pass

**Step 3: Commit**

```bash
git add tests/test_b2b_infra.py
git commit -m "test: fix env leak in test_v1_quota_headers_present with try/finally"
```

---

### Task 5: M5 — Add missing `starter` tier test

**Root cause:** `TIER_LIMITS` has a `starter` tier (1000 req/day, 20 req/min) and it's documented in the OpenAPI description, but no test covers tier detection for it.

**Files:**
- Modify: `tests/test_b2b_infra.py`

**Step 1: Add the test**

Add to `TestApiKeyTiers` (after `test_free_tier_detected`):

```python
    def test_starter_tier_detected(self):
        from bazi_engine.auth import resolve_key_info
        info = resolve_key_info("ff_starter_testkey")
        assert info.tier == "starter"
        assert info.requests_per_day == 1000
        assert info.requests_per_minute == 20
```

**Step 2: Run test to verify it passes**

```bash
.venv/bin/python -m pytest tests/test_b2b_infra.py::TestApiKeyTiers::test_starter_tier_detected -v
```
Expected: PASS (implementation already supports starter tier)

**Step 3: Commit**

```bash
git add tests/test_b2b_infra.py
git commit -m "test: add missing starter tier detection test"
```

---

### Task 6: Final verification and push

**Step 1: Run full test suite**

```bash
.venv/bin/python -m pytest -q --ignore=tests/test_snapshot_stability.py --tb=short
```
Expected: 1338+ passed, 28 skipped

```bash
.venv/bin/python -m pytest tests/test_snapshot_stability.py -q --tb=short
```
Expected: 200 passed

**Step 2: Push**

```bash
git push
```
