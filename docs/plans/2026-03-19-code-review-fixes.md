# Code Review + CI Fix Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix 6 code review issues and 2 CI failures (codegen + snapshot stability) and commit everything cleanly.

**Architecture:** All changes are surgical — no new abstractions. Most are 1–5 line edits. Snapshots must be regenerated because we added `precision` to BaziResponse.

**Tech Stack:** Python 3.10+, FastAPI, Pydantic v2, pytest, openapi-generator-cli (via CI)

---

## CI Failures

### Task 1: Fix codegen CI — SPDX license identifier missing

**Root cause:** `app.py` adds `license_info={"name": "Proprietary"}` to the OpenAPI spec. The `openapi-generator-cli` tool requires an SPDX `identifier` field alongside `name`. Without it, the Docker-based generator throws `SpecValidationException: attribute info.license.identifier is missing`.

**Files:**
- Modify: `bazi_engine/app.py` (the `_custom_openapi()` function)

**Step 1: Write the failing test (already failing in CI — verify locally)**

```bash
# Confirm the spec currently lacks an identifier
.venv/bin/python -c "
import json
spec = json.load(open('spec/openapi/openapi.json'))
print('license:', spec['info'].get('license'))
"
# Expected: {'name': 'Proprietary'} — no identifier key
```

**Step 2: Apply fix — add `identifier` to license in `_custom_openapi()`**

In `bazi_engine/app.py`, inside `_custom_openapi()`, replace:

```python
contact={"name": "FuFirE Support", "url": "https://github.com/DYAI2025/FuFirE"},
license_info={"name": "Proprietary"},
```

With:

```python
contact={"name": "FuFirE Support", "url": "https://github.com/DYAI2025/FuFirE"},
license_info={"name": "Proprietary", "identifier": "LicenseRef-proprietary"},
```

**Step 3: Regenerate the OpenAPI spec**

```bash
.venv/bin/python scripts/export_openapi.py
.venv/bin/python scripts/export_openapi.py --check
# Expected: OK: OpenAPI spec is up-to-date.
```

**Step 4: Verify spec has the identifier**

```bash
.venv/bin/python -c "
import json
spec = json.load(open('spec/openapi/openapi.json'))
print('license:', spec['info'].get('license'))
"
# Expected: {'name': 'Proprietary', 'identifier': 'LicenseRef-proprietary'}
```

**Step 5: Commit**

```bash
git add bazi_engine/app.py spec/openapi/openapi.json
git commit -m "fix(codegen): add SPDX identifier to license_info in OpenAPI spec"
```

---

### Task 2: Fix snapshot stability CI — regenerate bazi snapshots

**Root cause:** We added `precision: PrecisionBlock` to `BaziResponse` in Sprint 08. The stored `.json` snapshot files were created before this field existed. Now every bazi snapshot comparison fails because the response includes `{"birth_time_known": true, "provisional_fields": []}` but the snapshot file doesn't have a `precision` key.

Fix: regenerate all snapshots with `UPDATE_SNAPSHOTS=1`.

**Files:**
- Modify (regenerated): `tests/snapshots/*__bazi.json` — ~50 files updated automatically

**Step 1: Verify a snapshot currently lacks `precision`**

```bash
.venv/bin/python -c "
import json
from pathlib import Path
snap = json.loads(Path('tests/snapshots/std_1990_berlin__bazi.json').read_text())
print('has precision:', 'precision' in snap)
print('keys:', list(snap.keys()))
"
# Expected: has precision: False
```

**Step 2: Regenerate all snapshots**

```bash
UPDATE_SNAPSHOTS=1 .venv/bin/python -m pytest tests/test_snapshot_stability.py -q
# Expected: all tests pass (new snapshots written)
```

**Step 3: Verify snapshots now include `precision`**

```bash
.venv/bin/python -c "
import json
from pathlib import Path
snap = json.loads(Path('tests/snapshots/std_1990_berlin__bazi.json').read_text())
print('has precision:', 'precision' in snap)
print('precision:', snap.get('precision'))
"
# Expected: has precision: True, precision: {'birth_time_known': True, 'provisional_fields': []}
```

**Step 4: Run snapshot tests without UPDATE flag to confirm pass**

```bash
.venv/bin/python -m pytest tests/test_snapshot_stability.py -q --tb=short
# Expected: all pass (or skip with ephemeris skip)
```

**Step 5: Commit**

```bash
git add tests/snapshots/
git commit -m "test: regenerate bazi snapshots to include precision block"
```

---

## Code Review Bug Fixes

### Task 3: Remove unnecessary `reload()` from test setup methods

**Root cause:** `_load_keys()` in `auth.py` reads `os.environ` on every call — it has no module-level cache. The `reload(auth_mod)` in `setup_method` has zero effect on the running `app` and misleads developers into thinking it's needed.

**Files:**
- Modify: `tests/test_b2b_infra.py:170–175` (TestApiKeyAuth.setup_method)
- Modify: `tests/test_b2b_infra.py:253–257` (TestApiKeyTiers.setup_method)

**Step 1: Remove the reload block from TestApiKeyAuth.setup_method**

Find:
```python
def setup_method(self):
    os.environ["FUFIRE_API_KEYS"] = "test-key-abc,test-key-xyz"
    # Reload auth module to pick up env change
    from importlib import reload
    import bazi_engine.auth as auth_mod
    reload(auth_mod)
```

Replace with:
```python
def setup_method(self):
    os.environ["FUFIRE_API_KEYS"] = "test-key-abc,test-key-xyz"
```

**Step 2: Remove the reload block from TestApiKeyTiers.setup_method**

Find:
```python
def setup_method(self):
    os.environ["FUFIRE_API_KEYS"] = "ff_free_testkey1,ff_pro_testkey2,ff_enterprise_testkey3,legacy-plain-key"
    from importlib import reload
    import bazi_engine.auth as auth_mod
    reload(auth_mod)
```

Replace with:
```python
def setup_method(self):
    os.environ["FUFIRE_API_KEYS"] = "ff_free_testkey1,ff_pro_testkey2,ff_enterprise_testkey3,legacy-plain-key"
```

**Step 3: Run affected tests**

```bash
.venv/bin/python -m pytest tests/test_b2b_infra.py::TestApiKeyAuth tests/test_b2b_infra.py::TestApiKeyTiers -q --tb=short
# Expected: all pass (same as before)
```

**Step 4: Commit**

```bash
git add tests/test_b2b_infra.py
git commit -m "test: remove unnecessary reload() from auth test setup_method"
```

---

### Task 4: Remove duplicate contact/license_info from FastAPI() constructor

**Root cause:** In `app.py`, `contact` and `license_info` are passed to both the `FastAPI()` constructor and the `get_openapi()` call inside `_custom_openapi()`. Since `_custom_openapi()` completely replaces the auto-generated schema, the constructor values are never served. The constructor args are dead code and confusing.

**Files:**
- Modify: `bazi_engine/app.py` (~line 64)

**Step 1: Remove `contact` and `license_info` from the `FastAPI()` constructor**

Find:
```python
app = FastAPI(
    title="FuFirE — Fusion Firmament Engine",
    description=_DESCRIPTION,
    version=__version__,
    lifespan=lifespan,
    contact={"name": "FuFirE Support", "url": "https://github.com/DYAI2025/FuFirE"},
    license_info={"name": "Proprietary"},
)
```

Replace with:
```python
app = FastAPI(
    title="FuFirE — Fusion Firmament Engine",
    description=_DESCRIPTION,
    version=__version__,
    lifespan=lifespan,
)
```

**Step 2: Regenerate and verify spec unchanged**

```bash
.venv/bin/python scripts/export_openapi.py --check
# Expected: OK: OpenAPI spec is up-to-date. (values come from _custom_openapi, not constructor)
```

**Step 3: Run tests**

```bash
.venv/bin/python -m pytest tests/test_openapi_contract.py tests/test_b2b_infra.py -q --tb=short
# Expected: all pass
```

**Step 4: Commit**

```bash
git add bazi_engine/app.py
git commit -m "refactor(app): remove redundant contact/license from FastAPI() constructor"
```

---

### Task 5: Fix X-RateLimit-Remaining header — clarify it's a ceiling not a counter

**Root cause:** `middleware.py` sets `X-RateLimit-Remaining` to the full limit (e.g., 5 for free tier) on every request. The name "Remaining" implies it decrements, but it never does until Redis-backed counters are implemented. A client implementing pre-emptive throttling will behave incorrectly.

**Fix:** Keep the header (removing it would break the test) but update the OpenAPI description to accurately say it's a per-window ceiling until persistent counters are implemented. Also add a comment in the middleware.

**Files:**
- Modify: `bazi_engine/middleware.py` (comment only)
- Modify: `bazi_engine/app.py` — `_quota_headers` description in `_custom_openapi()`

**Step 1: Clarify the comment in middleware.py**

Find:
```python
            # Remaining is a placeholder until Redis-backed counters are implemented.
            response.headers.setdefault("X-RateLimit-Remaining", str(key_info.requests_per_minute))
```

Replace with:
```python
            # X-RateLimit-Remaining is currently set to the full tier limit on every response.
            # It will reflect real remaining quota once Redis-backed counters are implemented.
            # setdefault: if slowapi already wrote a real counter, we don't overwrite it.
            response.headers.setdefault("X-RateLimit-Remaining", str(key_info.requests_per_minute))
```

**Step 2: Update the OpenAPI description for the header in `_custom_openapi()`**

Find:
```python
        "X-RateLimit-Remaining": {
            "description": "Remaining requests in the current rate-limit window.",
            "schema": {"type": "string"},
        },
```

Replace with:
```python
        "X-RateLimit-Remaining": {
            "description": "Remaining quota in the current window. Currently reflects the full tier limit (persistent per-key counters are not yet implemented).",
            "schema": {"type": "string"},
        },
```

**Step 3: Regenerate spec**

```bash
.venv/bin/python scripts/export_openapi.py
.venv/bin/python scripts/export_openapi.py --check
```

**Step 4: Run tests**

```bash
.venv/bin/python -m pytest tests/test_b2b_infra.py -q --tb=short
# Expected: all pass
```

**Step 5: Commit**

```bash
git add bazi_engine/middleware.py bazi_engine/app.py spec/openapi/openapi.json
git commit -m "docs(middleware): clarify X-RateLimit-Remaining is tier ceiling, not real counter"
```

---

### Task 6: Remove extra blank line in fusion.py

**Files:**
- Modify: `bazi_engine/routers/fusion.py` (~line 62)

**Step 1: Remove double blank line**

Find (two blank lines between the field and `class FusionResponse`):
```python
    bazi_pillars: Optional[Dict[str, Dict[str, str]]] = Field(
        None, description="BaZi pillars (auto-computed if omitted)"
    )


                       # ← extra blank line here

class FusionResponse(BaseModel):
```

Replace with single blank line between the end of `FusionRequest` and `FusionResponse`.

The exact text to replace:
```
    )



class FusionResponse(BaseModel):
```
With:
```
    )


class FusionResponse(BaseModel):
```

**Step 2: Run lint**

```bash
.venv/bin/python -m ruff check bazi_engine/routers/fusion.py
# Expected: no output (no lint errors)
```

**Step 3: Commit**

```bash
git add bazi_engine/routers/fusion.py
git commit -m "style: remove extra blank line in fusion.py FusionRequest"
```

---

### Task 7: Add `starter` tier to OpenAPI description

**Root cause:** `TIER_LIMITS` in `auth.py` has a `starter` tier but it's not documented in the API description table. If a `ff_starter_xxx` key is issued to a customer, they won't find their tier documented.

**Files:**
- Modify: `bazi_engine/app.py` — `_DESCRIPTION` constant

**Step 1: Add starter row to the tier table in `_DESCRIPTION`**

Find:
```
| `ff_free_` | free | 100 | 5 |
| `ff_pro_` | pro | 10 000 | 100 |
| `ff_enterprise_` | enterprise | unlimited | unlimited |
```

Replace with:
```
| `ff_free_` | free | 100 | 5 |
| `ff_pro_` | pro | 10 000 | 100 |
| `ff_enterprise_` | enterprise | unlimited | unlimited |
```

Wait — check the current TIER_LIMITS first to verify limits:

```bash
.venv/bin/python -c "from bazi_engine.auth import TIER_LIMITS; print(TIER_LIMITS)"
# Expected: {'dev': (0, 0), 'free': (100, 5), 'starter': (1000, 20), 'pro': (10000, 100), 'enterprise': (0, 0)}
```

Then replace tier table with:
```
| `ff_free_` | free | 100 | 5 |
| `ff_starter_` | starter | 1 000 | 20 |
| `ff_pro_` | pro | 10 000 | 100 |
| `ff_enterprise_` | enterprise | unlimited | unlimited |
```

Also update the same table in `docs/api/01_developer_api_reference.md`.

**Step 2: Regenerate spec**

```bash
.venv/bin/python scripts/export_openapi.py
.venv/bin/python scripts/export_openapi.py --check
```

**Step 3: Run tests**

```bash
.venv/bin/python -m pytest tests/test_b2b_infra.py -q --tb=short
```

**Step 4: Commit**

```bash
git add bazi_engine/app.py spec/openapi/openapi.json docs/api/01_developer_api_reference.md
git commit -m "docs: add starter tier to OpenAPI description and developer reference"
```

---

### Task 8: Fix PrecisionBlock.provisional_fields to use Field(default_factory=list)

**Root cause:** `class PrecisionBlock(BaseModel): provisional_fields: list[str] = []` uses a mutable default. Pydantic v2 handles this correctly, but the canonical pattern uses `Field(default_factory=list)` to make the intent explicit and avoid confusion.

**Files:**
- Modify: `bazi_engine/routers/shared.py`

**Step 1: Update the field definition**

Find:
```python
class PrecisionBlock(BaseModel):
    birth_time_known: bool
    provisional_fields: list[str] = []
```

Replace with:
```python
class PrecisionBlock(BaseModel):
    birth_time_known: bool
    provisional_fields: list[str] = Field(default_factory=list)
```

Also add `Field` to the import if not already there. Check:

```bash
grep "from pydantic import" bazi_engine/routers/shared.py
```

`shared.py` currently imports `from pydantic import BaseModel` — add `Field`:
```python
from pydantic import BaseModel, Field
```

**Step 2: Run tests**

```bash
.venv/bin/python -m pytest tests/test_precision_guardrails.py tests/test_b2b_infra.py -q --tb=short
# Expected: all pass
```

**Step 3: Commit**

```bash
git add bazi_engine/routers/shared.py
git commit -m "refactor(shared): use Field(default_factory=list) for PrecisionBlock.provisional_fields"
```

---

### Task 9: Final push and CI verification

**Step 1: Run full test suite locally**

```bash
.venv/bin/python -m pytest -q --ignore=tests/test_snapshot_stability.py --tb=short
# Expected: 1335 passed, 28 skipped
.venv/bin/python -m pytest tests/test_snapshot_stability.py -q --tb=short
# Expected: all pass (after Task 2 regenerated snapshots)
```

**Step 2: Push**

```bash
git push
```

**Step 3: Wait for CI**

```bash
gh pr checks --watch
# Expected: all green
```
