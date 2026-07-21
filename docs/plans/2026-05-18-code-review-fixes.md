# Code-Review Findings Fix Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix all 7 findings from the FBP-03-001–005 code review (1 Critical, 3 Important, 3 Minor).

**Architecture:** Purely defensive fixes — no new features, no API shape changes. Each finding is one commit. All changes are in `bazi_engine/` and `tests/`. Tests use pytest + FastAPI TestClient; no new dependencies.

**Tech Stack:** Python 3.10+, Pydantic v2, FastAPI, pytest

---

## Context for the engineer

The codebase has just completed Phase 3 of BAZI-PRECISION-V2 (FBP-03-001 through FBP-03-005).
A code review surfaced 7 findings. Fix them in the order below — Critical first, then Important, then Minor.

Key files you will touch:
- `bazi_engine/app.py` — FastAPI app factory, OpenAPI customization
- `bazi_engine/routers/bazi.py` — BaZi calculation router, derivation trace models
- `bazi_engine/routers/shared.py` — Shared Pydantic models including `ErrorEnvelope`
- `bazi_engine/routers/validate.py` — POST /validate router
- `tests/test_error_envelope_schema.py` — FBP-03-005 tests (already passing)

Do NOT touch snapshot files manually. Do NOT run `UPDATE_SNAPSHOTS=1` unless a task says to.

---

## Task 1: Remove untracked `chart_ui` router from `app.py` (Critical)

`bazi_engine/routers/chart_ui.py` is untracked (not committed). It was accidentally included in `app.py`.
If left in, Railway auto-deploys it as a public endpoint with no review.

**Files:**
- Modify: `bazi_engine/app.py:30` (import line) and `bazi_engine/app.py:335–341` (include_router block)

**Step 1: Verify the problem**

```bash
git status | grep chart_ui
# Expected: ?? bazi_engine/routers/chart_ui.py
```

Confirms `chart_ui.py` is untracked — it should not be wired into the app.

**Step 2: Remove from import line**

In `bazi_engine/app.py`, line 30:
```python
# Before:
from .routers import info, bazi, western, fusion, validate, chart, webhooks, transit, experience, superglue, impact, chart_ui

# After:
from .routers import info, bazi, western, fusion, validate, chart, webhooks, transit, experience, superglue, impact
```

**Step 3: Remove include_router block**

In `bazi_engine/app.py`, delete these 3 lines (around line 335–341):
```python
# ── Chart UI (public, no API key, same-origin — no CORS issue) ────────────────
app.include_router(chart_ui.router)

```

**Step 4: Verify app still starts**

```bash
source .venv/bin/activate
uvicorn bazi_engine.app:app --port 8099 &
sleep 2
curl -s http://localhost:8099/health | python -m json.tool
kill %1
```

Expected: `{"status": "ok", ...}` with no import errors.

**Step 5: Run full test suite**

```bash
source .venv/bin/activate
pytest -q --tb=short 2>&1 | tail -5
```

Expected: same pass count as before (2263+), 0 failures.

**Step 6: Commit**

```bash
git add bazi_engine/app.py
git commit -m "fix(app): remove untracked chart_ui router from app factory

chart_ui.py is untracked and unreviewed. Including it would deploy an
unreviewed public endpoint via Railway's auto-deploy. Remove until the
file is committed and reviewed separately."
```

---

## Task 2: Add `extra="forbid"` to `ErrorEnvelope` (Important)

The JSON Schema `spec/schemas/ErrorEnvelope.schema.json` declares `"additionalProperties": false`.
The Pydantic model in `shared.py` does not enforce this — extra fields are silently dropped.

**Files:**
- Modify: `bazi_engine/routers/shared.py` (~line 46)
- Test: `tests/test_error_envelope_schema.py`

**Step 1: Write the failing test**

Add to `tests/test_error_envelope_schema.py` inside `TestPydanticModel`:

```python
def test_error_envelope_rejects_extra_fields(self):
    """ErrorEnvelope Pydantic model must enforce additionalProperties: false."""
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        ErrorEnvelope(
            error="x", message="y", request_id="z",
            status=422, path="/", timestamp="2026-01-01T00:00:00Z",
            extra_field="should_fail",
        )
```

**Step 2: Run to verify it fails**

```bash
source .venv/bin/activate
pytest tests/test_error_envelope_schema.py::TestPydanticModel::test_error_envelope_rejects_extra_fields -v
```

Expected: FAIL — `ValidationError` not raised because `extra` defaults to `"ignore"`.

**Step 3: Add `model_config` to `ErrorEnvelope`**

In `bazi_engine/routers/shared.py`, update `ErrorEnvelope`:

```python
class ErrorEnvelope(BaseModel):
    """Standard error response envelope for all /v1/* and legacy endpoints.

    Canonical JSON Schema: spec/schemas/ErrorEnvelope.schema.json
    See FBP-03-006 for the planned RFC 9457 migration in /v2.
    """
    model_config = ConfigDict(extra="forbid")

    error: str
    message: str
    detail: Dict[str, Any] = {}
    status: int
    path: str
    timestamp: str
    request_id: str
```

`ConfigDict` is already imported in `shared.py` (it's used by `QualityFlags`).

**Step 4: Run test to verify it passes**

```bash
source .venv/bin/activate
pytest tests/test_error_envelope_schema.py -v --tb=short
```

Expected: all 16 tests pass (15 old + 1 new).

**Step 5: Run full suite to catch regressions**

```bash
pytest -q --tb=short 2>&1 | tail -5
```

Expected: same count, 0 failures.

**Step 6: Commit**

```bash
git add bazi_engine/routers/shared.py tests/test_error_envelope_schema.py
git commit -m "fix(shared): enforce extra='forbid' on ErrorEnvelope

JSON Schema declares additionalProperties: false; Pydantic model must
match. Adds regression test."
```

---

## Task 3: Add `extra="forbid"` to all 6 new derivation trace models (Important)

Six new models in `bazi_engine/routers/bazi.py` have fixed shapes but no `extra="forbid"`:
`DayAnchorEvidence`, `YearDerivationTrace`, `MonthDerivationTrace`, `DayDerivationTrace`,
`HourDerivationTrace`, `TimeResolutionTrace`, `ProvenanceIds`.

`QualityFlags` in the same codebase sets the correct precedent.

**Files:**
- Modify: `bazi_engine/routers/bazi.py` (7 model classes)
- Test: `tests/test_bazi_derivation_trace_typed.py`

**Step 1: Write the failing tests**

Add to `tests/test_bazi_derivation_trace_typed.py` inside `TestDerivationTraceModelsExist`:

```python
def test_derivation_trace_models_reject_extra_fields(self):
    """All derivation trace models must have extra='forbid'."""
    from pydantic import ValidationError
    from bazi_engine.routers.bazi import (
        DayAnchorEvidence, YearDerivationTrace, MonthDerivationTrace,
        DayDerivationTrace, HourDerivationTrace, TimeResolutionTrace,
        ProvenanceIds,
    )
    # DayAnchorEvidence
    with pytest.raises(ValidationError):
        DayAnchorEvidence(
            ruleset_id="x", ruleset_version="1", anchor_verification="ok",
            unexpected="bad",
        )
    # YearDerivationTrace
    with pytest.raises(ValidationError):
        YearDerivationTrace(
            lichun_crossing_utc="2024-02-04T02:00:00Z",
            is_before_lichun=False,
            solar_longitude_lichun=315.0,
            unexpected="bad",
        )
    # TimeResolutionTrace
    with pytest.raises(ValidationError):
        TimeResolutionTrace(
            civil_local="2024-02-10T14:30:00+01:00",
            utc="2024-02-10T13:30:00+00:00",
            lmt="2024-02-10T14:23:37+00:53",
            tlst_hours=14.3,
            eot_minutes=-14.2,
            tz_offset_minutes=60,
            effective_standard="CIVIL",
            unexpected="bad",
        )
    # ProvenanceIds
    with pytest.raises(ValidationError):
        ProvenanceIds(
            ruleset_id="standard_bazi_2026",
            ruleset_version="1.0.0",
            time_policy_id="civil_midnight",
            day_anchor_id="standard_bazi_2026:jdn_2451545_verified",
            vector_model_id="wuxing_v1.1.0",
            unexpected="bad",
        )
```

**Step 2: Run to verify tests fail**

```bash
source .venv/bin/activate
pytest tests/test_bazi_derivation_trace_typed.py::TestDerivationTraceModelsExist::test_derivation_trace_models_reject_extra_fields -v
```

Expected: FAIL — `ValidationError` not raised.

**Step 3: Add `model_config = ConfigDict(extra="forbid")` to all 7 models**

In `bazi_engine/routers/bazi.py`, add `model_config = ConfigDict(extra="forbid")` as the first class body line to each of:

```python
class DayAnchorEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ruleset_id: str
    ...

class YearDerivationTrace(BaseModel):
    model_config = ConfigDict(extra="forbid")
    lichun_crossing_utc: str
    ...

class MonthDerivationTrace(BaseModel):
    model_config = ConfigDict(extra="forbid")
    jieqi_crossing_utc: str
    ...

class DayDerivationTrace(BaseModel):
    model_config = ConfigDict(extra="forbid")
    julian_day_number: int
    ...

class HourDerivationTrace(BaseModel):
    model_config = ConfigDict(extra="forbid")
    local_hour: int
    ...

class ProvenanceIds(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ruleset_id: str
    ...

class TimeResolutionTrace(BaseModel):
    model_config = ConfigDict(extra="forbid")
    civil_local: str
    ...
```

`ConfigDict` is already imported at line 12 of `bazi.py`.

**Step 4: Run tests**

```bash
source .venv/bin/activate
pytest tests/test_bazi_derivation_trace_typed.py -v --tb=short
```

Expected: all tests pass including the new one.

**Step 5: Run full suite**

```bash
pytest -q --tb=short 2>&1 | tail -5
```

Expected: same count, 0 failures.

**Step 6: Commit**

```bash
git add bazi_engine/routers/bazi.py tests/test_bazi_derivation_trace_typed.py
git commit -m "fix(bazi): enforce extra='forbid' on all derivation trace models

Response models with fixed shapes should reject unexpected fields.
Matches the QualityFlags pattern already in the codebase."
```

---

## Task 4: Refactor `_day_anchor_evidence` to accept a `ruleset` argument (Important)

`_day_anchor_evidence()` calls `load_default_ruleset()` independently, even though its only
caller (`_build_derivation_trace`) already has `ruleset` in scope. This double call is benign
(lru_cache) but creates an implicit dependency and is inconsistent with the refactor intent.

**Files:**
- Modify: `bazi_engine/routers/bazi.py` — `_day_anchor_evidence` signature and its call site

**Step 1: Write a behavioral test (no mocking)**

The output of `_build_derivation_trace` must be identical before and after the refactor.
Add to `tests/test_bazi_derivation_trace_typed.py`:

```python
def test_day_anchor_evidence_consistent_with_derivation_trace(self):
    """day_anchor_evidence inside trace must use same ruleset as provenance_ids."""
    from fastapi.testclient import TestClient
    from bazi_engine.app import app
    client = TestClient(app)
    r = client.post("/calculate/bazi", json={
        "date": "2024-02-10T14:30:00", "tz": "Europe/Berlin",
        "lon": 13.405, "lat": 52.52,
    })
    if r.status_code != 200:
        pytest.skip("ephemeris unavailable")
    trace = r.json()["derivation_trace"]
    day_anchor = trace["day"]["day_anchor_evidence"]
    prov = trace["provenance_ids"]
    # The ruleset_id in day_anchor_evidence must match provenance_ids.ruleset_id
    assert day_anchor["ruleset_id"] == prov["ruleset_id"]
    assert day_anchor["ruleset_version"] == prov["ruleset_version"]
```

**Step 2: Run to verify test passes already (behavioral, not structural)**

```bash
source .venv/bin/activate
pytest tests/test_bazi_derivation_trace_typed.py::TestDerivationTraceModelsExist::test_day_anchor_evidence_consistent_with_derivation_trace -v
```

Expected: PASS or SKIP (if no ephemeris). This test guards against regression during refactor.

**Step 3: Refactor `_day_anchor_evidence` to accept `ruleset`**

In `bazi_engine/routers/bazi.py`, change the function signature:

```python
# Before:
def _day_anchor_evidence() -> DayAnchorEvidence:
    ruleset = load_default_ruleset()
    anchor = ruleset.get("day_cycle_anchor", {}) or {}
    return DayAnchorEvidence(
        ruleset_id=ruleset.get("ruleset_id", "MISSING"),
        ruleset_version=ruleset.get("ruleset_version", "MISSING"),
        anchor_jdn=anchor.get("anchor_jdn"),
        anchor_sex_idx=anchor.get("anchor_sexagenary_index_0based"),
        anchor_verification=anchor.get("anchor_verification", "MISSING"),
    )

# After:
def _day_anchor_evidence(ruleset: dict) -> DayAnchorEvidence:
    anchor = (ruleset or {}).get("day_cycle_anchor", {}) or {}
    return DayAnchorEvidence(
        ruleset_id=ruleset.get("ruleset_id", "MISSING"),
        ruleset_version=ruleset.get("ruleset_version", "MISSING"),
        anchor_jdn=anchor.get("anchor_jdn"),
        anchor_sex_idx=anchor.get("anchor_sexagenary_index_0based"),
        anchor_verification=anchor.get("anchor_verification", "MISSING"),
    )
```

In `_build_derivation_trace`, update the call site (already has `ruleset` in scope):

```python
# Before:
day_offset_used=day_offset_from_ruleset(ruleset),
day_master_stem=STEMS[res.pillars.day.stem_index],
day_anchor_evidence=_day_anchor_evidence(),

# After:
day_offset_used=day_offset_from_ruleset(ruleset),
day_master_stem=STEMS[res.pillars.day.stem_index],
day_anchor_evidence=_day_anchor_evidence(ruleset),
```

**Step 4: Run tests**

```bash
source .venv/bin/activate
pytest tests/test_bazi_derivation_trace_typed.py -v --tb=short 2>&1 | tail -15
```

Expected: all pass.

**Step 5: Run full suite**

```bash
pytest -q --tb=short 2>&1 | tail -5
```

Expected: same count, 0 failures.

**Step 6: Commit**

```bash
git add bazi_engine/routers/bazi.py tests/test_bazi_derivation_trace_typed.py
git commit -m "refactor(bazi): pass ruleset into _day_anchor_evidence instead of re-fetching

Eliminates implicit dependency on load_default_ruleset() inside the
helper. The caller already holds the ruleset; pass it down explicitly."
```

---

## Task 5: Fix double blank line in `validate.py` (Minor)

After removing the inline `ErrorEnvelope` class in FBP-03-005, a double blank line
remains before `@router.post`. PEP 8 requires exactly two blank lines between top-level
definitions, but this is between a class and a decorator — one blank line is correct.

**Files:**
- Modify: `bazi_engine/routers/validate.py` (~line 39)

**Step 1: Locate the issue**

```bash
grep -n "^$" bazi_engine/routers/validate.py | head -20
```

Look for two consecutive blank lines before `@router.post`.

**Step 2: Fix**

In `bazi_engine/routers/validate.py`, find the section after `ValidateResponse` and before
`@router.post`. Replace any double blank line with a single blank line:

```python
class ValidateResponse(BaseModel):
    """..."""
    model_config = ConfigDict(extra="allow")

                    ← one blank line here, not two

@router.post(
```

**Step 3: Verify ruff is happy**

```bash
source .venv/bin/activate
ruff check bazi_engine/routers/validate.py
```

Expected: no output (no errors).

**Step 4: Commit**

```bash
git add bazi_engine/routers/validate.py
git commit -m "style(validate): remove extra blank line after inline ErrorEnvelope removal"
```

---

## Task 6: Preserve `ErrorEnvelope` example in OpenAPI schema (Minor)

**Root cause:** `_custom_openapi()` in `app.py` runs in this order:
1. Lines 528–530: inject `"example"` into `all_schemas["ErrorEnvelope"]`
2. Lines 532–539: **overwrite** `all_schemas["ErrorEnvelope"]` with `_err_raw` from file

Step 2 discards the example injected in step 1. Fix by carrying the example into `_err_raw`
before the assignment.

**Files:**
- Modify: `bazi_engine/app.py` (lines 532–539)
- Test: `tests/test_error_envelope_schema.py`

**Step 1: Write the failing test**

Add to `tests/test_error_envelope_schema.py` inside `TestOpenApiSpec`:

```python
def test_openapi_error_envelope_has_example(self):
    """ErrorEnvelope in OpenAPI spec must have an 'example' for Swagger UI."""
    spec = client.get("/openapi.json").json()
    ee = spec["components"]["schemas"]["ErrorEnvelope"]
    assert "example" in ee, "ErrorEnvelope schema missing 'example' field"
    assert ee["example"]["error"] == "validation_error"
    assert "request_id" in ee["example"]
```

**Step 2: Run to verify it fails**

```bash
source .venv/bin/activate
pytest tests/test_error_envelope_schema.py::TestOpenApiSpec::test_openapi_error_envelope_has_example -v
```

Expected: FAIL — `"example"` not in schema (overwritten by file load).

**Step 3: Fix the overwrite in `app.py`**

In `bazi_engine/app.py`, the FBP-03-005 block (currently lines 532–539):

```python
# Before:
_err_path = spec_dir / "ErrorEnvelope.schema.json"
if _err_path.exists():
    _err_raw = json.loads(_err_path.read_text(encoding="utf-8"))
    _err_raw.pop("$schema", None)
    _err_raw.pop("$id", None)
    _err_raw.pop("examples", None)
    schema.setdefault("components", {}).setdefault("schemas", {})["ErrorEnvelope"] = _err_raw

# After:
_err_path = spec_dir / "ErrorEnvelope.schema.json"
if _err_path.exists():
    _err_raw = json.loads(_err_path.read_text(encoding="utf-8"))
    _err_raw.pop("$schema", None)
    _err_raw.pop("$id", None)
    _err_raw.pop("examples", None)  # JSON Schema "examples" array → not used in OpenAPI
    # Carry over the OpenAPI-style "example" (singular) if already injected above.
    _existing = all_schemas.get("ErrorEnvelope", {})
    if "example" in _existing:
        _err_raw["example"] = _existing["example"]
    schema.setdefault("components", {}).setdefault("schemas", {})["ErrorEnvelope"] = _err_raw
```

**Step 4: Run test**

```bash
source .venv/bin/activate
pytest tests/test_error_envelope_schema.py -v --tb=short
```

Expected: all 17 tests pass (16 old + 1 new).

**Step 5: Regenerate OpenAPI spec**

```bash
source .venv/bin/activate
python scripts/export_openapi.py
```

Expected: `Written: .../spec/openapi/openapi.json`

**Step 6: Verify the example appears in the spec**

```bash
python -c "
import json
spec = json.load(open('spec/openapi/openapi.json'))
ee = spec['components']['schemas']['ErrorEnvelope']
print('example' in ee, ee.get('example', {}).get('error'))
"
```

Expected: `True validation_error`

**Step 7: Run full suite**

```bash
pytest -q --tb=short 2>&1 | tail -5
```

Expected: same count, 0 failures.

**Step 8: Commit**

```bash
git add bazi_engine/app.py tests/test_error_envelope_schema.py spec/openapi/openapi.json
git commit -m "fix(app): preserve ErrorEnvelope example when loading schema from file

The file-load block was overwriting all_schemas['ErrorEnvelope'] after
the example had been injected, silently dropping it. Now the example
is carried into _err_raw before assignment."
```

---

## Final verification

After all 6 tasks:

```bash
source .venv/bin/activate
pytest -q --tb=short 2>&1 | tail -5
python scripts/export_openapi.py --check
```

Both must pass cleanly. No snapshot regeneration should be needed (these fixes do not change
derivation trace output shapes, only model validation config and OpenAPI metadata).
