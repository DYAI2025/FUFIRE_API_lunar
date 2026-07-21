# Security Review Fixes Implementation Plan

**Goal:** Fix all issues raised in the PR #64 code review, including the two previously-deferred audit findings (#4 server-side tier validation, #6 phantom RateLimit headers).

**Architecture:** Eight small, independent fixes. Each touches at most 2 files. All follow TDD. All commit separately.

**Tech Stack:** Python 3.12, FastAPI, slowapi (`limits` library underneath), `lru_cache`, `uv run python -m pytest`

---

## Context

Branch: `codex/refactoring`
Test runner: `uv run python -m pytest`
Full suite baseline: 1602 passed, 28 skipped

---

### Task 1: Remove `dev` tier from key-generation script (Important #1)

Generating `ff_dev_<token>` keys gives unlimited rate limits in production. Remove `dev` from the CLI choices.

**Files:**
- Modify: `scripts/generate_api_key.py`
- Test: `tests/test_b2b_infra.py` (add to existing `TestKeyGeneration`)

**Step 1: Write the failing test**

In `tests/test_b2b_infra.py`, find `class TestKeyGeneration` and add:

```python
def test_dev_tier_not_generatable(self):
    from scripts.generate_api_key import generate_key, VALID_TIERS
    assert "dev" not in VALID_TIERS
    with pytest.raises(ValueError):
        generate_key("dev")
```

**Step 2: Run test to verify it fails**

```bash
uv run python -m pytest tests/test_b2b_infra.py::TestKeyGeneration::test_dev_tier_not_generatable -v
```

Expected: FAIL — `generate_key("dev")` currently succeeds.

**Step 3: Implement**

In `scripts/generate_api_key.py`, change:

```python
# before
VALID_TIERS = {"dev", "free", "starter", "pro", "enterprise"}
```

```python
# after
VALID_TIERS = {"free", "starter", "pro", "enterprise"}
```

**Step 4: Run test to verify it passes**

```bash
uv run python -m pytest tests/test_b2b_infra.py::TestKeyGeneration -v
```

Expected: all pass.

**Step 5: Commit**

```bash
git add scripts/generate_api_key.py tests/test_b2b_infra.py
git commit -m "fix(security): remove dev tier from key generation script"
```

---

### Task 2: Fix webhook 401 to use structured error envelope (Important #2)

`webhooks.py` raises `HTTPException(status_code=401, detail="Invalid authentication")` — a raw string. Every other error in that file uses `{"error": ..., "message": ..., "detail": {}}`.

**Files:**
- Modify: `bazi_engine/routers/webhooks.py`
- Test: `tests/test_b2b_infra.py` (add to existing `TestWebhookErrorSanitization`)

**Step 1: Write the failing test**

In `class TestWebhookErrorSanitization`, add:

```python
def test_webhook_401_uses_structured_envelope(self, client):
    """Verify 401 response uses the error envelope, not a raw string."""
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
    # Must be a dict envelope, not a plain string
    assert isinstance(body.get("detail"), dict), (
        f"Expected structured detail dict, got: {body.get('detail')!r}"
    )
    assert body["detail"].get("error") == "unauthorized"
```

**Step 2: Run test to verify it fails**

```bash
uv run python -m pytest "tests/test_b2b_infra.py::TestWebhookErrorSanitization::test_webhook_401_uses_structured_envelope" -v
```

Expected: FAIL — `detail` is currently a string `"Invalid authentication"`.

**Step 3: Implement**

In `bazi_engine/routers/webhooks.py`, find the 401 raise after `verify_request_auth` and replace:

```python
# before
raise HTTPException(status_code=401, detail="Invalid authentication")
```

```python
# after
raise HTTPException(status_code=401, detail={
    "error": "unauthorized",
    "message": "Invalid webhook authentication",
    "detail": {},
})
```

**Step 4: Run test**

```bash
uv run python -m pytest tests/test_b2b_infra.py::TestWebhookErrorSanitization -v
```

Expected: all pass.

**Step 5: Commit**

```bash
git add bazi_engine/routers/webhooks.py tests/test_b2b_infra.py
git commit -m "fix(security): use structured error envelope for webhook 401"
```

---

### Task 3: Encapsulate private storage access behind a helper (Important #3)

`conftest.py` calls `limiter._storage.reset()` directly. `_storage` is a private attribute. Expose a `reset_storage()` helper in `bazi_engine/limiter.py` so tests don't reach into privates.

**Files:**
- Modify: `bazi_engine/limiter.py`
- Modify: `tests/conftest.py`

**Step 1: No new test needed** — the existing `reset_rate_limiter` autouse fixture is the test. We're just moving where the private access lives to a single place under our control.

**Step 2: Add helper to limiter.py**

In `bazi_engine/limiter.py`, after the `limiter = Limiter(...)` line, add:

```python
def reset_limiter_storage() -> None:
    """Reset in-memory rate limit counters. Call in test teardown only.

    Accesses limiter._storage (a limits.storage.MemoryStorage). The private
    attribute is isolated here so test code stays clean.
    """
    storage = limiter._storage  # noqa: SLF001
    if hasattr(storage, "reset"):
        storage.reset()
```

**Step 3: Update conftest.py**

Replace the fixture body in `tests/conftest.py`:

```python
# before
@pytest.fixture(autouse=True)
def reset_rate_limiter():
    """Reset slowapi in-memory rate limit counters between tests."""
    from bazi_engine.limiter import limiter
    limiter._storage.reset()
    yield
    limiter._storage.reset()
```

```python
# after
@pytest.fixture(autouse=True)
def reset_rate_limiter():
    """Reset slowapi in-memory rate limit counters between tests."""
    from bazi_engine.limiter import reset_limiter_storage
    reset_limiter_storage()
    yield
    reset_limiter_storage()
```

**Step 4: Run full suite to verify nothing broke**

```bash
uv run python -m pytest -q
```

Expected: 1602+ passed, 28 skipped.

**Step 5: Commit**

```bash
git add bazi_engine/limiter.py tests/conftest.py
git commit -m "refactor(test): encapsulate limiter storage reset in public helper"
```

---

### Task 4: Guard against `CORS_ALLOWED_ORIGINS=*` (Minor #4)

If the env var is set to `*`, `CORSMiddleware` passes it through as `allow_origins=["*"]`, opening CORS to all origins. Add a startup check.

**Files:**
- Modify: `bazi_engine/app.py`
- Test: `tests/test_b2b_infra.py` (add to `TestCORSHeaders`)

**Step 1: Write the failing test**

In `class TestCORSHeaders`, add:

```python
def test_wildcard_cors_rejected_at_startup(self, monkeypatch):
    """Setting CORS_ALLOWED_ORIGINS=* must raise at import time."""
    import importlib
    import bazi_engine.app as app_module
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "*")
    with pytest.raises((ValueError, RuntimeError)):
        importlib.reload(app_module)
```

**Step 2: Run test to verify it fails**

```bash
uv run python -m pytest "tests/test_b2b_infra.py::TestCORSHeaders::test_wildcard_cors_rejected_at_startup" -v
```

Expected: FAIL — wildcard currently passes through silently.

**Step 3: Add guard in app.py**

After the `_ALLOWED_ORIGINS` list comprehension in `bazi_engine/app.py`, add:

```python
if "*" in _ALLOWED_ORIGINS:
    raise RuntimeError(
        "CORS_ALLOWED_ORIGINS must not contain '*' — set explicit origins instead. "
        "Current value: " + _ALLOWED_ORIGINS_ENV
    )
```

**Step 4: Run test**

```bash
uv run python -m pytest tests/test_b2b_infra.py::TestCORSHeaders -v
```

Expected: all pass.

**Step 5: Commit**

```bash
git add bazi_engine/app.py tests/test_b2b_infra.py
git commit -m "fix(security): reject wildcard CORS_ALLOWED_ORIGINS at startup"
```

---

### Task 5: Server-side tier override (Finding #4 — Medium)

**Problem:** Tier is derived only from the key's name prefix (`ff_pro_…`). An operator mistake (e.g., listing a `ff_enterprise_` key in the wrong env var slot) silently grants the wrong tier. There is no server-side check.

**Solution:** Add `FUFIRE_KEY_TIER_OVERRIDES` env var — a comma-separated `key:tier` map. `resolve_key_info` checks this map first, before doing prefix parsing.

**Example:**
```
FUFIRE_KEY_TIER_OVERRIDES=ff_pro_abc123:starter,ff_free_xyz:pro
```

**Files:**
- Modify: `bazi_engine/auth.py`
- Test: `tests/test_b2b_infra.py` (new class `TestTierOverrides`)

**Step 1: Write the failing test**

Add to `tests/test_b2b_infra.py`:

```python
class TestTierOverrides:
    """Verify FUFIRE_KEY_TIER_OVERRIDES allows server-side tier correction."""

    def test_override_downgrades_enterprise_key_to_starter(self, monkeypatch):
        """A prefix-enterprise key is overridden to starter by the env map."""
        monkeypatch.setenv(
            "FUFIRE_KEY_TIER_OVERRIDES",
            "ff_enterprise_abc123:starter",
        )
        from bazi_engine.auth import resolve_key_info, _load_tier_overrides
        _load_tier_overrides.cache_clear()
        info = resolve_key_info("ff_enterprise_abc123")
        assert info.tier == "starter"
        assert info.requests_per_minute == 20
        _load_tier_overrides.cache_clear()

    def test_unknown_key_uses_prefix_when_no_override(self, monkeypatch):
        """When key is not in the override map, prefix parsing still works."""
        monkeypatch.setenv("FUFIRE_KEY_TIER_OVERRIDES", "ff_enterprise_xyz:free")
        from bazi_engine.auth import resolve_key_info, _load_tier_overrides
        _load_tier_overrides.cache_clear()
        info = resolve_key_info("ff_pro_different123")
        assert info.tier == "pro"
        _load_tier_overrides.cache_clear()

    def test_empty_override_env_is_safe(self, monkeypatch):
        """Empty or missing env var means no overrides — prefix parsing used."""
        monkeypatch.delenv("FUFIRE_KEY_TIER_OVERRIDES", raising=False)
        from bazi_engine.auth import resolve_key_info, _load_tier_overrides
        _load_tier_overrides.cache_clear()
        info = resolve_key_info("ff_pro_abc")
        assert info.tier == "pro"
        _load_tier_overrides.cache_clear()
```

**Step 2: Run tests to verify they fail**

```bash
uv run python -m pytest tests/test_b2b_infra.py::TestTierOverrides -v
```

Expected: FAIL — `_load_tier_overrides` does not exist yet.

**Step 3: Implement in auth.py**

After `_load_keys()`, add:

```python
@lru_cache(maxsize=1)
def _load_tier_overrides() -> dict[str, str]:
    """Load server-side tier overrides from FUFIRE_KEY_TIER_OVERRIDES env var.

    Format: comma-separated ``key:tier`` pairs.
    Example: ``ff_enterprise_abc:starter,ff_free_xyz:pro``

    Overrides take precedence over prefix-based tier detection.
    Call ``_load_tier_overrides.cache_clear()`` to reload after env change.
    """
    raw = os.environ.get("FUFIRE_KEY_TIER_OVERRIDES", "").strip()
    if not raw:
        return {}
    result: dict[str, str] = {}
    for entry in raw.split(","):
        entry = entry.strip()
        if ":" not in entry:
            continue
        key, _, tier = entry.partition(":")
        key = key.strip()
        tier = tier.strip().lower()
        if key and tier in TIER_LIMITS:
            result[key] = tier
    return result
```

Then update `resolve_key_info` to check overrides first:

```python
def resolve_key_info(api_key: str) -> KeyInfo:
    """Extract tier from key format ff_<tier>_<secret>, or default to free.

    Server-side override (FUFIRE_KEY_TIER_OVERRIDES) takes precedence over
    the prefix-based tier detection.
    """
    if api_key == "dev-mode":
        rpd, rpm = TIER_LIMITS["dev"]
        return KeyInfo(key=api_key, tier="dev", requests_per_day=rpd, requests_per_minute=rpm)

    # Server-side override wins over key prefix
    overrides = _load_tier_overrides()
    tier = overrides.get(api_key)

    if tier is None:
        tier = "free"  # default for legacy keys
        if api_key.startswith("ff_"):
            parts = api_key.split("_", 2)
            if len(parts) >= 3 and parts[1] in TIER_LIMITS:
                tier = parts[1]

    rpd, rpm = TIER_LIMITS[tier]
    return KeyInfo(key=api_key, tier=tier, requests_per_day=rpd, requests_per_minute=rpm)
```

**Step 4: Run tests**

```bash
uv run python -m pytest tests/test_b2b_infra.py::TestTierOverrides -v
```

Expected: all 3 pass.

**Step 5: Run full suite to catch regressions**

```bash
uv run python -m pytest -q
```

Expected: 1605+ passed, 28 skipped.

**Step 6: Commit**

```bash
git add bazi_engine/auth.py tests/test_b2b_infra.py
git commit -m "feat(security): add FUFIRE_KEY_TIER_OVERRIDES for server-side tier correction (Finding #4)"
```

---

### Task 6: Fix phantom `X-RateLimit-Remaining` header (Finding #6 — Medium)

**Problem:** `middleware.py` always injects `X-RateLimit-Remaining: <full_quota>` via `setdefault`. On routes with no `@limiter.limit()` decorator (health, info, validate), this header always shows the full tier quota regardless of actual usage — misleading B2B clients.

**Solution:** Remove the `setdefault` fallback for `X-RateLimit-Remaining`. Only emit `X-RateLimit-Limit` from tier info (this is always accurate). `X-RateLimit-Remaining` is only written by slowapi on decorated routes (where it reflects the real MemoryStorage counter).

**Files:**
- Modify: `bazi_engine/middleware.py`
- Test: `tests/test_b2b_infra.py` (add to `TestSecurityHeaders`)

**Step 1: Write the failing test**

In `class TestSecurityHeaders`, add:

```python
def test_ratelimit_remaining_absent_on_info_route(self, client):
    """Info/health routes have no @limiter.limit() — Remaining header must be absent."""
    import os
    env = {**os.environ, "FUFIRE_API_KEYS": "ff_pro_testkey123"}
    # Use a real key so key_info is set
    with patch.dict(os.environ, {"FUFIRE_API_KEYS": "ff_pro_testkey123"}):
        from bazi_engine.auth import _load_keys
        _load_keys.cache_clear()
        response = client.get(
            "/v1/health",
            headers={"X-API-Key": "ff_pro_testkey123"},
        )
        _load_keys.cache_clear()
    # X-RateLimit-Limit is OK (accurate tier info)
    # X-RateLimit-Remaining must NOT be present (would be phantom/inaccurate)
    assert "x-ratelimit-remaining" not in response.headers, (
        f"Phantom remaining header found: {response.headers.get('x-ratelimit-remaining')}"
    )

def test_ratelimit_remaining_present_on_compute_route(self, client):
    """Compute routes have @limiter.limit() — slowapi sets Remaining accurately."""
    import os
    from unittest.mock import patch
    with patch.dict(os.environ, {"FUFIRE_API_KEYS": "ff_pro_testkey456"}):
        from bazi_engine.auth import _load_keys
        _load_keys.cache_clear()
        response = client.post(
            "/v1/calculate/bazi",
            headers={"X-API-Key": "ff_pro_testkey456", "Content-Type": "application/json"},
            json={"date": "1990-06-15T14:30:00", "tz": "Europe/Berlin", "lon": 13.4, "lat": 52.5},
        )
        _load_keys.cache_clear()
    if response.status_code == 200:
        # slowapi should have injected the real counter
        assert "x-ratelimit-remaining" in response.headers
```

**Step 2: Run tests to verify first test fails**

```bash
uv run python -m pytest "tests/test_b2b_infra.py::TestSecurityHeaders::test_ratelimit_remaining_absent_on_info_route" -v
```

Expected: FAIL — `x-ratelimit-remaining: 100` is currently set by the middleware fallback.

**Step 3: Remove phantom fallback from middleware.py**

In `bazi_engine/middleware.py`, replace the quota header block:

```python
# before
if key_info is not None and key_info.requests_per_minute > 0:
    response.headers["X-RateLimit-Limit"] = str(key_info.requests_per_minute)
    # X-RateLimit-Remaining is currently set to the full tier limit on every response.
    # It will reflect real remaining quota once Redis-backed counters are implemented.
    # setdefault: if slowapi already wrote a real counter, we don't overwrite it.
    response.headers.setdefault("X-RateLimit-Remaining", str(key_info.requests_per_minute))
elif key_info is not None and key_info.requests_per_minute == 0:
    response.headers["X-RateLimit-Limit"] = "unlimited"
    response.headers.setdefault("X-RateLimit-Remaining", "unlimited")
```

```python
# after
if key_info is not None and key_info.requests_per_minute > 0:
    response.headers["X-RateLimit-Limit"] = str(key_info.requests_per_minute)
    # X-RateLimit-Remaining is written by slowapi on @limiter.limit() routes.
    # We do NOT set a fallback here — an absent header is more honest than a
    # phantom "full quota" value. Redis-backed per-key counters are tracked in
    # the roadmap for routes without a per-request decorator.
elif key_info is not None and key_info.requests_per_minute == 0:
    response.headers["X-RateLimit-Limit"] = "unlimited"
```

**Step 4: Run tests**

```bash
uv run python -m pytest tests/test_b2b_infra.py::TestSecurityHeaders -v
```

Expected: all pass.

**Step 5: Run full suite**

```bash
uv run python -m pytest -q
```

Expected: 1607+ passed, 28 skipped.

**Step 6: Commit**

```bash
git add bazi_engine/middleware.py tests/test_b2b_infra.py
git commit -m "fix(security): remove phantom X-RateLimit-Remaining fallback from middleware (Finding #6)"
```

---

### Task 7: Fix `KeyInfo.__repr__` masking (Minor #7)

`key[:8]` reveals the tier prefix (`ff_pro_a`). Mask only the last N chars of the random portion instead.

**Files:**
- Modify: `bazi_engine/auth.py`
- Test: `tests/test_b2b_infra.py` (add to `TestTierAssignment`)

**Step 1: Write the failing test**

In `class TestTierAssignment`, add:

```python
def test_key_info_repr_does_not_leak_tier(self):
    """__repr__ must not expose the tier prefix in the key portion."""
    from bazi_engine.auth import resolve_key_info
    info = resolve_key_info("ff_enterprise_abc123def456")
    r = repr(info)
    # tier is OK in repr (it's not secret) but key must be masked
    # The literal key value "ff_enterprise_" must not appear
    assert "ff_enterprise_" not in r, f"Key prefix leaked in repr: {r}"
    assert "..." in r, f"Mask indicator missing from repr: {r}"
```

**Step 2: Run test to verify it fails**

```bash
uv run python -m pytest "tests/test_b2b_infra.py::TestTierAssignment::test_key_info_repr_does_not_leak_tier" -v
```

Expected: FAIL — current `repr` exposes `ff_enter...`.

**Step 3: Fix `__repr__` in `KeyInfo`**

In `bazi_engine/auth.py`, update `KeyInfo.__repr__`:

```python
def __repr__(self) -> str:
    # Show only last 4 chars of key to confirm identity without leaking prefix/tier
    suffix = self.key[-4:] if len(self.key) > 4 else "***"
    return f"KeyInfo(key='...{suffix}', tier='{self.tier}', rpm={self.requests_per_minute})"
```

**Step 4: Run test**

```bash
uv run python -m pytest tests/test_b2b_infra.py::TestTierAssignment -v
```

Expected: all pass.

**Step 5: Commit**

```bash
git add bazi_engine/auth.py tests/test_b2b_infra.py
git commit -m "fix(security): mask key prefix in KeyInfo repr to avoid tier leakage in logs"
```

---

### Task 8: Final verification + push

**Step 1: Run full suite**

```bash
uv run python -m pytest -q
```

Expected: 1610+ passed, 28 skipped (baseline 1602 + ~8 new tests).

**Step 2: Run mypy**

```bash
uv run mypy bazi_engine --ignore-missing-imports
```

Expected: `Success: no issues found in 63 source files`

**Step 3: Run coverage**

```bash
uv run python -m pytest tests/ --cov=bazi_engine --cov-report=term-missing --cov-fail-under=75 -q
```

Expected: ≥75% (was 88.71%).

**Step 4: Push and update PR**

```bash
git push origin codex/refactoring
```

The existing PR #64 will update automatically.

**Step 5: Mark audit finding #6 as resolved**

Update `security/2026-03-21-1200-auth-ratelimit-webhook-audit/security-audit-results.tsv` — change finding #6's status from `deferred` to `resolved` and add commit reference.

```bash
git add security/
git commit -m "docs(security): mark Finding #6 resolved after phantom header fix"
git push origin codex/refactoring
```
