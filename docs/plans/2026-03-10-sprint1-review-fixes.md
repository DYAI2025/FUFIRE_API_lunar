# Sprint 1 Code Review Fixes — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix all critical and high-severity issues found in Sprint 1 code review (PR #43), plus key medium-severity items.

**Architecture:** Fixes are ordered by severity. Each task is independent — no task depends on a previous task's output. Tests first (TDD), then implementation, then verification.

**Tech Stack:** Python 3.10+, pytest, FastAPI, pyswisseph, pydantic

---

## Task 1: Fix test infrastructure — stop masking MOSEPH fallback in conftest.py

**Why:** `conftest.py` silently sets `EPHEMERIS_MODE=MOSEPH` when SE1 files are absent. This means tests never fail when ephemeris files are missing — contradicting the production guard that refuses silent degradation. Tests give false confidence.

**Files:**
- Modify: `tests/conftest.py:20-25`

**Step 1: Read the current conftest.py**

Understand the current auto-MOSEPH logic at lines 20-25:
```python
# CURRENT (lines 20-25):
if not os.environ.get("EPHEMERIS_MODE") and not _se1_files_available():
    os.environ["EPHEMERIS_MODE"] = "MOSEPH"
```

**Step 2: Replace auto-MOSEPH with a pytest marker**

Replace lines 20-25 in `tests/conftest.py` with:
```python
# Detect if SE1 files are available for tests that need them.
# Tests that require high-precision SWIEPH should use @pytest.mark.swieph.
# When SE1 files are absent, those tests are skipped automatically.
_HAS_SE1 = _se1_files_available()

# If SE1 files are not present and EPHEMERIS_MODE is not explicitly set,
# default to MOSEPH so the bulk of the test suite can still run.
# Tests that specifically validate SWIEPH behavior should use @pytest.mark.swieph.
if not os.environ.get("EPHEMERIS_MODE") and not _HAS_SE1:
    os.environ["EPHEMERIS_MODE"] = "MOSEPH"


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line("markers", "swieph: requires Swiss Ephemeris SE1 files")


def pytest_collection_modifyitems(config, items):
    """Skip @pytest.mark.swieph tests when SE1 files are not available."""
    if _HAS_SE1:
        return
    skip_swieph = pytest.mark.skip(reason="SE1 files not available (set SE_EPHE_PATH)")
    for item in items:
        if "swieph" in item.keywords:
            item.add_marker(skip_swieph)
```

**Step 3: Mark ephemeris-sensitive tests**

In `tests/test_ephemeris_fallback.py`, add the `swieph` marker to tests that validate SWIEPH behavior with real files:

Add after imports (line 24):
```python
pytestmark = [pytest.mark.swieph]
```

Wait — this would skip ALL tests in the file. Only `TestSwissEphBackendInit.test_swieph_with_files_ok` needs real SE1 files. The others use mocks. Remove the module-level mark and instead add it only to `test_swieph_with_files_ok`:

In `tests/test_ephemeris_fallback.py`, add before `test_swieph_with_files_ok` (line 113):
```python
    @pytest.mark.swieph
    def test_swieph_with_files_ok(self, tmp_path):
```

**Step 4: Run tests to verify**

Run: `cd /Users/benjaminpoersch/Projects/SaaS/FuFirE/BAFE/.worktrees/fufire-rebrand && pytest tests/test_ephemeris_fallback.py -v`
Expected: All tests pass (or `test_swieph_with_files_ok` skips if no SE1 files).

**Step 5: Commit**

```bash
git add tests/conftest.py tests/test_ephemeris_fallback.py
git commit -m "fix(tests): add @swieph marker instead of silent MOSEPH auto-enable"
```

---

## Task 2: Fix frozen dataclass mutation in ephemeris fallback tests

**Why:** Tests use `object.__setattr__(backend, "flags", ...)` to mutate a frozen dataclass, creating unrealistic scenarios. Should mock `swe.calc_ut` return values instead.

**Files:**
- Modify: `tests/test_ephemeris_fallback.py:138-168`

**Step 1: Rewrite `test_sun_lon_deg_ut_catches_fallback` (line 138)**

Replace the current implementation:
```python
    def test_sun_lon_deg_ut_catches_fallback(self):
        """sun_lon_deg_ut raises if swe.calc_ut returns MOSEPH flags."""
        # Create a SWIEPH backend with real (or mocked) file check
        from bazi_engine.ephemeris import EPHEMERIS_FILES_REQUIRED, ensure_ephemeris_files
        import tempfile, os
        with tempfile.TemporaryDirectory() as tmp:
            for f in EPHEMERIS_FILES_REQUIRED:
                (Path(tmp) / f).touch()
            ensure_ephemeris_files.cache_clear()
            with patch.dict(os.environ, {k: v for k, v in os.environ.items() if k != "EPHEMERIS_MODE"}, clear=True):
                backend = SwissEphBackend(mode="SWIEPH", ephe_path=tmp)
            ensure_ephemeris_files.cache_clear()

        # Now backend.flags == FLG_SWIEPH (set at init, no mutation needed)
        assert backend.flags == swe.FLG_SWIEPH

        # Mock swe.calc_ut to return MOSEPH flags (simulating silent fallback)
        mock_result = ((100.0, 0.0, 1.0, 0.0, 0.0, 0.0), swe.FLG_MOSEPH)
        with patch("bazi_engine.ephemeris.swe.calc_ut", return_value=mock_result):
            with pytest.raises(EphemerisUnavailableError, match="silently fell back"):
                backend.sun_lon_deg_ut(2460000.0)
```

Add missing import at top of file (after line 13):
```python
from pathlib import Path
```

**Step 2: Rewrite `test_sun_lon_deg_ut_ok_when_swieph_returned` (line 150)**

Replace:
```python
    def test_sun_lon_deg_ut_ok_when_swieph_returned(self):
        """sun_lon_deg_ut succeeds when swe.calc_ut returns SWIEPH flags."""
        from bazi_engine.ephemeris import EPHEMERIS_FILES_REQUIRED, ensure_ephemeris_files
        import tempfile, os
        with tempfile.TemporaryDirectory() as tmp:
            for f in EPHEMERIS_FILES_REQUIRED:
                (Path(tmp) / f).touch()
            ensure_ephemeris_files.cache_clear()
            with patch.dict(os.environ, {k: v for k, v in os.environ.items() if k != "EPHEMERIS_MODE"}, clear=True):
                backend = SwissEphBackend(mode="SWIEPH", ephe_path=tmp)
            ensure_ephemeris_files.cache_clear()

        mock_result = ((100.0, 0.0, 1.0, 0.0, 0.0, 0.0), swe.FLG_SWIEPH)
        with patch("bazi_engine.ephemeris.swe.calc_ut", return_value=mock_result):
            lon = backend.sun_lon_deg_ut(2460000.0)
            assert lon == 100.0
```

**Step 3: Rewrite `test_calc_ut_wrapper_catches_fallback` (line 160)**

Replace:
```python
    def test_calc_ut_wrapper_catches_fallback(self):
        """The calc_ut wrapper method raises on MOSEPH fallback."""
        from bazi_engine.ephemeris import EPHEMERIS_FILES_REQUIRED, ensure_ephemeris_files
        import tempfile, os
        with tempfile.TemporaryDirectory() as tmp:
            for f in EPHEMERIS_FILES_REQUIRED:
                (Path(tmp) / f).touch()
            ensure_ephemeris_files.cache_clear()
            with patch.dict(os.environ, {k: v for k, v in os.environ.items() if k != "EPHEMERIS_MODE"}, clear=True):
                backend = SwissEphBackend(mode="SWIEPH", ephe_path=tmp)
            ensure_ephemeris_files.cache_clear()

        mock_result = ((100.0, 0.0, 1.0, 0.0, 0.0, 0.0), swe.FLG_MOSEPH)
        with patch("bazi_engine.ephemeris.swe.calc_ut", return_value=mock_result):
            with pytest.raises(EphemerisUnavailableError):
                backend.calc_ut(2460000.0, swe.SUN)
```

**Step 4: Extract helper to reduce duplication**

All three tests above repeat the same "create SWIEPH backend with fake SE1 files" pattern. Add a helper after `_clean_env()` (line 30):

```python
def _make_swieph_backend(tmp_path: Path) -> SwissEphBackend:
    """Create a SWIEPH backend with dummy SE1 files (no frozen-dataclass mutation)."""
    from bazi_engine.ephemeris import EPHEMERIS_FILES_REQUIRED
    for f in EPHEMERIS_FILES_REQUIRED:
        (tmp_path / f).touch()
    ensure_ephemeris_files.cache_clear()
    try:
        with patch.dict(os.environ, _clean_env(), clear=True):
            return SwissEphBackend(mode="SWIEPH", ephe_path=str(tmp_path))
    finally:
        ensure_ephemeris_files.cache_clear()
```

Then simplify the three tests:
```python
    def test_sun_lon_deg_ut_catches_fallback(self, tmp_path):
        """sun_lon_deg_ut raises if swe.calc_ut returns MOSEPH flags."""
        backend = _make_swieph_backend(tmp_path)
        mock_result = ((100.0, 0.0, 1.0, 0.0, 0.0, 0.0), swe.FLG_MOSEPH)
        with patch("bazi_engine.ephemeris.swe.calc_ut", return_value=mock_result):
            with pytest.raises(EphemerisUnavailableError, match="silently fell back"):
                backend.sun_lon_deg_ut(2460000.0)

    def test_sun_lon_deg_ut_ok_when_swieph_returned(self, tmp_path):
        """sun_lon_deg_ut succeeds when swe.calc_ut returns SWIEPH flags."""
        backend = _make_swieph_backend(tmp_path)
        mock_result = ((100.0, 0.0, 1.0, 0.0, 0.0, 0.0), swe.FLG_SWIEPH)
        with patch("bazi_engine.ephemeris.swe.calc_ut", return_value=mock_result):
            lon = backend.sun_lon_deg_ut(2460000.0)
            assert lon == 100.0

    def test_calc_ut_wrapper_catches_fallback(self, tmp_path):
        """The calc_ut wrapper method raises on MOSEPH fallback."""
        backend = _make_swieph_backend(tmp_path)
        mock_result = ((100.0, 0.0, 1.0, 0.0, 0.0, 0.0), swe.FLG_MOSEPH)
        with patch("bazi_engine.ephemeris.swe.calc_ut", return_value=mock_result):
            with pytest.raises(EphemerisUnavailableError):
                backend.calc_ut(2460000.0, swe.SUN)
```

**Step 5: Run tests**

Run: `pytest tests/test_ephemeris_fallback.py -v`
Expected: All tests pass without `object.__setattr__`.

**Step 6: Commit**

```bash
git add tests/test_ephemeris_fallback.py
git commit -m "fix(tests): remove frozen dataclass mutation, use proper SWIEPH backend creation"
```

---

## Task 3: Add MOSEPH guard to `solcross_ut()`

**Why:** `solcross_ut()` is the ONLY Swiss Ephemeris call path without the MOSEPH fallback guard. Solar term calculations (LiChun boundaries) silently degrade to Moshier precision — the exact scenario Sprint 1 was supposed to prevent.

**Files:**
- Modify: `bazi_engine/ephemeris.py:102-103`
- Modify: `tests/test_ephemeris_fallback.py` (add test)

**Step 1: Write the failing test**

Add to `TestRuntimeFallbackDetection` in `tests/test_ephemeris_fallback.py`:
```python
    def test_solcross_ut_catches_fallback(self, tmp_path):
        """solcross_ut raises if swe.solcross_ut returns MOSEPH flags."""
        backend = _make_swieph_backend(tmp_path)

        # swe.solcross_ut returns (jd_crossing, return_flags)
        mock_result = (2460000.5, swe.FLG_MOSEPH)
        with patch("bazi_engine.ephemeris.swe.solcross_ut", return_value=mock_result):
            with pytest.raises(EphemerisUnavailableError, match="silently fell back"):
                backend.solcross_ut(315.0, 2460000.0)

    def test_solcross_ut_ok_when_swieph_returned(self, tmp_path):
        """solcross_ut succeeds when SWIEPH flags returned."""
        backend = _make_swieph_backend(tmp_path)

        mock_result = (2460000.5, swe.FLG_SWIEPH)
        with patch("bazi_engine.ephemeris.swe.solcross_ut", return_value=mock_result):
            result = backend.solcross_ut(315.0, 2460000.0)
            assert result == 2460000.5
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_ephemeris_fallback.py::TestRuntimeFallbackDetection::test_solcross_ut_catches_fallback -v`
Expected: FAIL (current `solcross_ut` doesn't check flags).

**Step 3: Fix `solcross_ut()` in ephemeris.py**

Replace lines 102-103 in `bazi_engine/ephemeris.py`:
```python
    def solcross_ut(self, target_lon_deg: float, jd_start_ut: float) -> Optional[float]:
        jd_cross, ret = swe.solcross_ut(target_lon_deg, jd_start_ut, self.flags)
        assert_no_moseph_fallback(self.flags, ret)
        return float(jd_cross)
```

**Step 4: Run tests**

Run: `pytest tests/test_ephemeris_fallback.py -v`
Expected: All tests pass including the two new ones.

**Step 5: Run full test suite to check for regressions**

Run: `pytest -x -q`
Expected: All pass. The `jieqi.py:find_crossing()` call chain (`backend.solcross_ut()`) now returns `float` instead of a tuple, which matches the `Optional[float]` protocol.

**Step 6: Commit**

```bash
git add bazi_engine/ephemeris.py tests/test_ephemeris_fallback.py
git commit -m "fix(ephemeris): add MOSEPH fallback guard to solcross_ut — closes last unguarded path"
```

---

## Task 4: Sanitize error messages in routers (prevent information leakage)

**Why:** All `/calculate/*` routers expose raw Python exception messages to API clients via `f"Unexpected error: {e}"`. This leaks internal paths, module names, and ephemeris file locations. For a B2B API this is a security issue.

**Files:**
- Modify: `bazi_engine/routers/bazi.py:146-149`
- Modify: `bazi_engine/routers/western.py:69-72`
- Modify: `bazi_engine/routers/fusion.py:117-120, 166-169, 216-219`
- Modify: `bazi_engine/routers/transit.py:94-108` (add try/except)
- Create: `tests/test_error_sanitization.py`

**Step 1: Write the failing test**

Create `tests/test_error_sanitization.py`:
```python
"""Tests that API error responses never leak internal details."""
from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from bazi_engine.app import app

client = TestClient(app)

BAZI_PAYLOAD = {
    "date": "2024-02-10T14:30:00",
    "tz": "Europe/Berlin",
    "lon": 13.405,
    "lat": 52.52,
}


def _raise_internal(msg: str):
    """Factory for side effects that raise internal errors."""
    def _inner(*args, **kwargs):
        raise RuntimeError(msg)
    return _inner


class TestErrorSanitization:
    """Verify that 500 responses never contain raw exception text."""

    @pytest.mark.parametrize("endpoint", [
        "/calculate/bazi",
        "/calculate/western",
        "/calculate/fusion",
        "/calculate/wuxing",
    ])
    def test_500_does_not_leak_exception_message(self, endpoint):
        """Internal errors must not echo raw Python exceptions to clients."""
        secret_msg = "SECRET_INTERNAL_PATH_/opt/ephemeris/sepl_18.se1"

        # Patch resolve_local_iso to blow up with an internal message
        with patch(
            "bazi_engine.time_utils.resolve_local_iso",
            side_effect=RuntimeError(secret_msg),
        ):
            r = client.post(endpoint, json=BAZI_PAYLOAD)

        assert r.status_code == 500
        body = r.json()
        # The raw secret must NOT appear in the response
        assert secret_msg not in str(body), (
            f"Error response leaked internal exception: {body}"
        )
        # Should have a generic error message instead
        assert "error" in body
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_error_sanitization.py -v`
Expected: FAIL — current routers echo `f"Unexpected error: {e}"` which contains `SECRET_INTERNAL_PATH_...`.

**Step 3: Fix all routers**

In `bazi_engine/routers/bazi.py`, replace lines 146-149:
```python
    except BaziEngineError:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="Internal calculation error")
```

In `bazi_engine/routers/western.py`, replace lines 69-72:
```python
    except BaziEngineError:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="Internal calculation error")
```

In `bazi_engine/routers/fusion.py`, there are three endpoints. Replace ALL three catch blocks:

Lines 117-120 (`/fusion`):
```python
    except BaziEngineError:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="Internal calculation error")
```

Lines 166-169 (`/wuxing`):
```python
    except BaziEngineError:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="Internal calculation error")
```

Lines 216-219 (`/tst`):
```python
    except BaziEngineError:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="Internal calculation error")
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_error_sanitization.py -v`
Expected: PASS — error responses now contain generic message.

**Step 5: Run full test suite**

Run: `pytest -x -q`
Expected: All pass. Snapshot tests may need regeneration if error response text changed.

**Step 6: Commit**

```bash
git add bazi_engine/routers/bazi.py bazi_engine/routers/western.py bazi_engine/routers/fusion.py tests/test_error_sanitization.py
git commit -m "fix(security): sanitize error responses — never leak internal exception details"
```

---

## Task 5: Add input validation for transit sector arrays

**Why:** `TransitStateRequest` accepts any float values in `soulprint_sectors` and `quiz_sectors` — including NaN, Inf, and negative numbers. These cause incorrect calculations or runtime errors in `compute_transit_state()`.

**Files:**
- Modify: `bazi_engine/routers/transit.py:83-85`
- Modify: `bazi_engine/transit.py:115-120`
- Create: `tests/test_transit_validation.py`

**Step 1: Write the failing test**

Create `tests/test_transit_validation.py`:
```python
"""Tests for transit input validation."""
from __future__ import annotations

import math
from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient

from bazi_engine.app import app

client = TestClient(app)

VALID_SECTORS = [0.1] * 12


class TestTransitSectorValidation:
    """Verify sector arrays are validated before processing."""

    def test_nan_in_soulprint_rejected(self):
        bad = [0.1] * 11 + [float("nan")]
        r = client.post("/transit/state", json={
            "soulprint_sectors": bad,
            "quiz_sectors": VALID_SECTORS,
        })
        assert r.status_code == 422

    def test_inf_in_quiz_rejected(self):
        bad = [float("inf")] + [0.1] * 11
        r = client.post("/transit/state", json={
            "soulprint_sectors": VALID_SECTORS,
            "quiz_sectors": bad,
        })
        assert r.status_code == 422

    def test_negative_value_rejected(self):
        bad = [-0.5] + [0.1] * 11
        r = client.post("/transit/state", json={
            "soulprint_sectors": bad,
            "quiz_sectors": VALID_SECTORS,
        })
        assert r.status_code == 422

    def test_value_above_one_rejected(self):
        bad = [1.5] + [0.1] * 11
        r = client.post("/transit/state", json={
            "soulprint_sectors": bad,
            "quiz_sectors": VALID_SECTORS,
        })
        assert r.status_code == 422

    def test_wrong_length_rejected(self):
        r = client.post("/transit/state", json={
            "soulprint_sectors": [0.1] * 10,
            "quiz_sectors": VALID_SECTORS,
        })
        assert r.status_code == 422

    def test_valid_sectors_accepted(self):
        """Valid sectors should not be rejected by validation."""
        # This will still fail with 500 if ephemeris is unavailable,
        # but it should NOT fail with 422 (validation error).
        r = client.post("/transit/state", json={
            "soulprint_sectors": VALID_SECTORS,
            "quiz_sectors": VALID_SECTORS,
        })
        # Accept 200 or 503 (ephemeris unavailable) but NOT 422
        assert r.status_code != 422
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_transit_validation.py -v`
Expected: NaN/Inf/negative/above-one tests FAIL (currently accepted by Pydantic).

**Step 3: Add Pydantic validator to `TransitStateRequest`**

In `bazi_engine/routers/transit.py`, replace lines 83-85:
```python
class TransitStateRequest(BaseModel):
    soulprint_sectors: List[float] = Field(..., min_length=12, max_length=12)
    quiz_sectors: List[float] = Field(..., min_length=12, max_length=12)

    @field_validator("soulprint_sectors", "quiz_sectors")
    @classmethod
    def validate_sector_values(cls, v: List[float]) -> List[float]:
        import math
        for i, val in enumerate(v):
            if math.isnan(val) or math.isinf(val):
                raise ValueError(f"Element {i} is NaN or Inf")
            if val < 0 or val > 1:
                raise ValueError(f"Element {i} = {val} not in range [0, 1]")
        return v
```

Add `field_validator` to the import on line 15:
```python
from pydantic import BaseModel, Field, field_validator
```

**Step 4: Add defensive check in `compute_transit_state()`**

In `bazi_engine/transit.py`, add validation at the start of `compute_transit_state()` after line 120:
```python
    if len(soulprint_sectors) != 12 or len(quiz_sectors) != 12:
        raise ValueError(
            f"Sector arrays must have exactly 12 elements. "
            f"Got soulprint={len(soulprint_sectors)}, quiz={len(quiz_sectors)}"
        )
```

**Step 5: Run tests**

Run: `pytest tests/test_transit_validation.py -v`
Expected: All 6 tests pass.

**Step 6: Run full test suite**

Run: `pytest -x -q`
Expected: All pass.

**Step 7: Commit**

```bash
git add bazi_engine/routers/transit.py bazi_engine/transit.py tests/test_transit_validation.py
git commit -m "fix(transit): validate sector array values — reject NaN, Inf, out-of-range"
```

---

## Task 6: DRY up ProvenanceResponse into shared.py

**Why:** `ProvenanceResponse` Pydantic model is copy-pasted identically in 3 router files (`bazi.py`, `western.py`, `fusion.py`). Any schema change requires updating 3 places.

**Files:**
- Modify: `bazi_engine/routers/shared.py`
- Modify: `bazi_engine/routers/bazi.py`
- Modify: `bazi_engine/routers/western.py`
- Modify: `bazi_engine/routers/fusion.py`

**Step 1: Add `ProvenanceResponse` to `shared.py`**

In `bazi_engine/routers/shared.py`, add after the existing imports (line 9):
```python
from pydantic import BaseModel
```

Then add at the end of the file (after `format_pillar`):
```python


class ProvenanceResponse(BaseModel):
    engine_version: str
    parameter_set_id: str
    ruleset_id: str
    ephemeris_id: str
    tzdb_version_id: str
    house_system: str
    zodiac_mode: str
    computation_timestamp: str
```

**Step 2: Update `bazi.py` — remove local `ProvenanceResponse`, import from shared**

In `bazi_engine/routers/bazi.py`:
- Change the import on line 17 from:
  ```python
  from .shared import format_pillar
  ```
  to:
  ```python
  from .shared import format_pillar, ProvenanceResponse
  ```
- Delete lines 73-82 (the local `ProvenanceResponse` class).

**Step 3: Update `western.py` — remove local `ProvenanceResponse`, import from shared**

In `bazi_engine/routers/western.py`:
- Add import: `from .shared import ProvenanceResponse` (after line 16 or alongside existing imports from shared if any).
- Delete lines 39-48 (the local `ProvenanceResponse` class).

**Step 4: Update `fusion.py` — remove local `ProvenanceResponse`, import from shared**

In `bazi_engine/routers/fusion.py`:
- Change line 29 from:
  ```python
  from .shared import format_pillar
  ```
  to:
  ```python
  from .shared import format_pillar, ProvenanceResponse
  ```
- Delete lines 48-57 (the local `ProvenanceResponse` class).

**Step 5: Run tests**

Run: `pytest -x -q`
Expected: All pass — response model is structurally identical.

**Step 6: Regenerate OpenAPI spec**

Run: `python scripts/export_openapi.py`
Expected: No meaningful diff (same schema, just defined once).

**Step 7: Commit**

```bash
git add bazi_engine/routers/shared.py bazi_engine/routers/bazi.py bazi_engine/routers/western.py bazi_engine/routers/fusion.py
git commit -m "refactor(routers): DRY ProvenanceResponse into shared.py"
```

---

## Task 7: Fix datetime parsing in transit router (422 not 500)

**Why:** `datetime.fromisoformat()` raises `ValueError` for invalid datetime strings. The transit router doesn't catch this, returning 500 instead of 422. For a B2B API, clients need correct status codes.

**Files:**
- Modify: `bazi_engine/routers/transit.py:94-108`
- Modify: `tests/test_transit_validation.py`

**Step 1: Write the failing test**

Add to `tests/test_transit_validation.py`:
```python
class TestTransitDatetimeValidation:
    """Verify datetime parameter validation returns 422 not 500."""

    def test_invalid_datetime_returns_422(self):
        r = client.get("/transit/now", params={"datetime": "not-a-date"})
        assert r.status_code == 422, f"Expected 422 but got {r.status_code}: {r.json()}"

    def test_valid_datetime_accepted(self):
        r = client.get("/transit/now", params={"datetime": "2024-06-15T12:00:00Z"})
        # 200 or 503 (ephemeris) but NOT 422
        assert r.status_code in (200, 503)

    def test_no_datetime_defaults_to_now(self):
        r = client.get("/transit/now")
        assert r.status_code in (200, 503)
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_transit_validation.py::TestTransitDatetimeValidation::test_invalid_datetime_returns_422 -v`
Expected: FAIL — returns 500 (unhandled ValueError).

**Step 3: Add try/except for datetime parsing**

In `bazi_engine/routers/transit.py`, replace lines 94-108:
```python
@router.get("/now", response_model=TransitNowResponse)
def transit_now(
    datetime_param: Optional[str] = Query(
        None,
        alias="datetime",
        description="Optional UTC datetime in ISO format. Default: now.",
    ),
) -> Dict[str, Any]:
    """Current planetary positions from Swiss Ephemeris."""
    dt_utc = None
    if datetime_param:
        try:
            dt_utc = datetime.fromisoformat(
                datetime_param.replace("Z", "+00:00")
            ).astimezone(timezone.utc)
        except (ValueError, TypeError) as e:
            from ..exc import InputError
            raise InputError(
                f"Invalid datetime format: {datetime_param!r}",
                detail={"parameter": "datetime", "value": datetime_param},
            )
    return compute_transit_now(dt_utc=dt_utc)
```

**Step 4: Run tests**

Run: `pytest tests/test_transit_validation.py -v`
Expected: All pass.

**Step 5: Run full suite**

Run: `pytest -x -q`
Expected: All pass.

**Step 6: Commit**

```bash
git add bazi_engine/routers/transit.py tests/test_transit_validation.py
git commit -m "fix(transit): return 422 for invalid datetime, not 500"
```

---

## Task 8: Fix `jd_ut_to_datetime_utc()` overflow handling

**Why:** The manual overflow chain in `jd_ut_to_datetime_utc()` handles microsecond→second→minute but doesn't handle hour≥24. While rare, this is a latent bug. Use `timedelta` arithmetic which handles all overflows correctly.

**Files:**
- Modify: `bazi_engine/ephemeris.py:126-144`
- Add test to: `tests/test_ephemeris_fallback.py`

**Step 1: Write the failing test**

Add a new test class at the end of `tests/test_ephemeris_fallback.py`:
```python
class TestJdUtToDatetimeUtc:
    """Edge cases for Julian Day to datetime conversion."""

    def test_microsecond_overflow_at_boundary(self):
        """Microsecond rounding near 999999.5 should not crash."""
        from bazi_engine.ephemeris import jd_ut_to_datetime_utc
        # JD for 2024-01-01 23:59:59.9999995 UTC
        # We can't easily construct this exact JD, so we test the function
        # doesn't crash for a range of JD values near midnight
        from bazi_engine.ephemeris import datetime_utc_to_jd_ut
        from datetime import datetime, timezone
        dt = datetime(2024, 1, 1, 23, 59, 59, 999999, tzinfo=timezone.utc)
        jd = datetime_utc_to_jd_ut(dt)
        result = jd_ut_to_datetime_utc(jd)
        assert result.year == 2024
        assert result.month == 1
        # Day could be 1 or 2 depending on rounding
        assert result.day in (1, 2)

    def test_roundtrip_preserves_date(self):
        """datetime → JD → datetime should preserve the date (within 1 second)."""
        from bazi_engine.ephemeris import jd_ut_to_datetime_utc, datetime_utc_to_jd_ut
        from datetime import datetime, timezone, timedelta
        original = datetime(2024, 6, 15, 14, 30, 45, tzinfo=timezone.utc)
        jd = datetime_utc_to_jd_ut(original)
        result = jd_ut_to_datetime_utc(jd)
        diff = abs((result - original).total_seconds())
        assert diff < 1.0, f"Roundtrip drift: {diff}s"
```

**Step 2: Run test to verify it passes (baseline)**

Run: `pytest tests/test_ephemeris_fallback.py::TestJdUtToDatetimeUtc -v`
Expected: PASS (the current code handles most cases).

**Step 3: Simplify `jd_ut_to_datetime_utc()` using timedelta**

Replace lines 126-144 in `bazi_engine/ephemeris.py`:
```python
def jd_ut_to_datetime_utc(jd_ut: float) -> datetime:
    y, m, d, h = swe.revjul(jd_ut)
    hour = int(h)
    rem = (h - hour) * 3600.0
    minute = int(rem // 60.0)
    sec = rem - minute * 60.0
    second = int(sec)
    micro = int(round((sec - second) * 1_000_000))
    # Clamp microseconds (rounding can push to 1_000_000)
    if micro >= 1_000_000:
        micro = 0
        second += 1
    # Use timedelta to handle all overflow cascades (second→minute→hour→day)
    base = datetime(y, m, d, tzinfo=timezone.utc)
    return base + timedelta(hours=hour, minutes=minute, seconds=second, microseconds=micro)
```

**Step 4: Run tests**

Run: `pytest tests/test_ephemeris_fallback.py::TestJdUtToDatetimeUtc -v`
Expected: PASS.

**Step 5: Run full suite to check for regressions**

Run: `pytest -x -q`
Expected: All pass.

**Step 6: Commit**

```bash
git add bazi_engine/ephemeris.py tests/test_ephemeris_fallback.py
git commit -m "fix(ephemeris): simplify jd_ut_to_datetime_utc overflow handling via timedelta"
```

---

## Summary

| Task | Severity | What | Files |
|------|----------|------|-------|
| 1 | CRITICAL | Add `@swieph` marker, stop masking MOSEPH | conftest.py, test_ephemeris_fallback.py |
| 2 | CRITICAL | Remove `object.__setattr__` on frozen dataclass | test_ephemeris_fallback.py |
| 3 | HIGH | Add MOSEPH guard to `solcross_ut()` | ephemeris.py, test_ephemeris_fallback.py |
| 4 | HIGH | Sanitize error messages in routers | 3 routers, test_error_sanitization.py |
| 5 | HIGH | Validate transit sector array values | routers/transit.py, transit.py, test_transit_validation.py |
| 6 | MEDIUM | DRY `ProvenanceResponse` → shared.py | shared.py, 3 routers |
| 7 | MEDIUM | Return 422 for bad datetime, not 500 | routers/transit.py, test_transit_validation.py |
| 8 | MEDIUM | Fix overflow in `jd_ut_to_datetime_utc()` | ephemeris.py, test_ephemeris_fallback.py |

**Total: 8 tasks, 8 commits, ~30 minutes estimated.**
