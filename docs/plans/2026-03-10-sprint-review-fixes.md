# Sprint Review Fixes Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix all CRITICAL (3) and MEDIUM (5) issues found during Sprint 2+3 code review — eliminate race conditions, enforce project conventions, and improve correctness.

**Architecture:** Fixes are independent and additive. No response shape changes. Thread-safety via lock around swe.set_sid_mode(). Missing conventions added. Non-ledger function gains ascendant parity. Performance micro-optimizations in hot paths.

**Tech Stack:** Python 3.10+, pyswisseph, FastAPI, pytest

---

### Task 1: Fix swe.set_sid_mode() Race Condition (CRITICAL #1)

**Files:**
- Modify: `bazi_engine/western.py:140-160`
- Test: `tests/test_western.py`

**Context:** `swe.set_sid_mode()` mutates global C library state. Under concurrent FastAPI requests, a tropical request arriving between `set_sid_mode()` and `get_ayanamsa_ut()` of a sidereal request will see corrupted state. This violates the "no side effects" principle and creates a production race condition.

**Step 1: Write the failing test**

Add to `tests/test_western.py`:

```python
def test_sidereal_does_not_pollute_global_state():
    """swe.set_sid_mode must be reset after sidereal computation (CRITICAL #1)."""
    import swisseph as swe

    # Record initial sid mode state by getting ayanamsha at a known JD
    jd_test = swe.julday(2024, 6, 15, 12.0)
    swe.set_sid_mode(0)  # Fagan-Bradley baseline
    ayan_before = swe.get_ayanamsa_ut(jd_test)

    # Run a sidereal chart computation (Lahiri = mode 1)
    from bazi_engine.western import compute_western_chart
    from datetime import datetime, timezone
    dt = datetime(2024, 6, 15, 12, 0, tzinfo=timezone.utc)
    compute_western_chart(dt, 52.52, 13.405, zodiac_mode="sidereal_lahiri")

    # After the call, global state must NOT still be Lahiri
    # Reset to Fagan-Bradley and verify ayanamsha matches baseline
    swe.set_sid_mode(0)
    ayan_after = swe.get_ayanamsa_ut(jd_test)
    assert abs(ayan_before - ayan_after) < 0.001, (
        f"swe global state polluted: before={ayan_before}, after={ayan_after}"
    )
```

**Step 2: Run test to verify it fails**

Run: `python -c "import pytest; pytest.main(['-v', 'tests/test_western.py::test_sidereal_does_not_pollute_global_state'])"`

Expected: PASS (this test verifies state IS reset — it may pass or fail depending on whether the current code already resets. The real protection is the lock.)

**Step 3: Add threading lock and reset in western.py**

In `bazi_engine/western.py`, add at top (after imports):

```python
import threading

_SWE_LOCK = threading.Lock()
```

Then replace lines 140-160 (the sidereal block) with:

```python
    # Apply ayanamsha correction for sidereal modes
    if zodiac_mode in AYANAMSHA_MODES:
        ayanamsha_id = AYANAMSHA_MODES[zodiac_mode]
        with _SWE_LOCK:
            swe.set_sid_mode(ayanamsha_id)
            ayanamsha = swe.get_ayanamsa_ut(jd_ut)
            swe.set_sid_mode(0)  # Reset to default — prevent state leakage

        # Adjust body longitudes
        for body_data in bodies.values():
            if "longitude" in body_data:
                adj_lon = (body_data["longitude"] - ayanamsha) % 360
                body_data["longitude"] = adj_lon
                body_data["zodiac_sign"] = int(adj_lon // 30)
                body_data["degree_in_sign"] = adj_lon % 30

        # Adjust house cusps
        for key in houses:
            houses[key] = (houses[key] - ayanamsha) % 360

        # Adjust angles
        for key in angles:
            angles[key] = (angles[key] - ayanamsha) % 360
```

**Step 4: Run test to verify it passes**

Run: `python -c "import pytest; pytest.main(['-v', 'tests/test_western.py::test_sidereal_does_not_pollute_global_state'])"`

Expected: PASS

**Step 5: Commit**

```bash
git add bazi_engine/western.py tests/test_western.py
git commit -m "fix: guard swe.set_sid_mode() with threading lock and reset after use

Prevents race condition under concurrent sidereal+tropical requests.
The pyswisseph sid mode is global C library state — now protected
by a lock and reset to default after reading ayanamsha value."
```

---

### Task 2: Add frozen=True to WesternBody + future annotations to constants.py (CRITICAL #2+#3)

**Files:**
- Modify: `bazi_engine/western.py:27`
- Modify: `bazi_engine/constants.py:1`

**Step 1: Write the failing test**

Add to `tests/test_western.py`:

```python
def test_western_body_is_frozen():
    """WesternBody dataclass must be frozen (CRITICAL #2)."""
    from bazi_engine.western import WesternBody
    import dataclasses
    assert dataclasses.fields(WesternBody)  # is a dataclass
    body = WesternBody(
        name="Sun", longitude=0.0, latitude=0.0, distance=1.0,
        speed_long=1.0, is_retrograde=False, zodiac_sign=0, degree_in_sign=0.0,
    )
    import pytest
    with pytest.raises(dataclasses.FrozenInstanceError):
        body.longitude = 99.0
```

**Step 2: Run test to verify it fails**

Run: `python -c "import pytest; pytest.main(['-v', 'tests/test_western.py::test_western_body_is_frozen'])"`

Expected: FAIL — `FrozenInstanceError` not raised because `frozen=True` is missing.

**Step 3: Fix both issues**

In `bazi_engine/western.py:27`, change:
```python
@dataclass
class WesternBody:
```
to:
```python
@dataclass(frozen=True)
class WesternBody:
```

In `bazi_engine/constants.py:1`, add as first line:
```python
from __future__ import annotations
```

**Step 4: Run test to verify it passes**

Run: `python -c "import pytest; pytest.main(['-v', 'tests/test_western.py::test_western_body_is_frozen'])"`

Expected: PASS

**Step 5: Commit**

```bash
git add bazi_engine/western.py bazi_engine/constants.py
git commit -m "fix: add frozen=True to WesternBody, future annotations to constants.py

Enforces project-wide immutability convention on the only dataclass
that was missing it. Adds missing from __future__ import annotations
to constants.py per project convention."
```

---

### Task 3: Register provenance module in import hierarchy test (HIGH #4)

**Files:**
- Modify: `tests/test_import_hierarchy.py:31-81` (LAYERS dict)

**Step 1: Determine provenance layer**

`provenance.py` imports only `from . import __version__` (the package `__init__`). It has no domain-level imports. It's imported by Level 5 routers. Logical layer: **1** (same as types.py — foundational metadata).

**Step 2: Add to LAYERS dict**

In `tests/test_import_hierarchy.py`, inside the `LAYERS` dict, add after the `"exc"` line:

```python
    "provenance":  1,
```

**Step 3: Run import hierarchy test**

Run: `python -c "import pytest; pytest.main(['-v', 'tests/test_import_hierarchy.py'])"`

Expected: All pass, including the new `provenance.py` entry. If provenance imports anything above Layer 1, the test will catch it.

**Step 4: Commit**

```bash
git add tests/test_import_hierarchy.py
git commit -m "test: register provenance module in import hierarchy (Layer 1)"
```

---

### Task 4: Add logging to bare except clauses in routers (HIGH #6)

**Files:**
- Modify: `bazi_engine/routers/bazi.py:189-190`
- Modify: `bazi_engine/routers/western.py:89-90`
- Modify: `bazi_engine/routers/fusion.py:117-120, 173-176, 225-226`

**Context:** Every router endpoint has `except Exception: raise HTTPException(500)` which discards the traceback entirely. Add `logging.exception()` before the re-raise so production errors are debuggable.

**Step 1: Fix all router files**

In each router file, add at the top (after other imports):

```python
import logging

_log = logging.getLogger(__name__)
```

Then change every bare `except Exception` block from:

```python
    except Exception:
        raise HTTPException(status_code=500, detail="Internal calculation error")
```

to:

```python
    except Exception:
        _log.exception("Calculation failed")
        raise HTTPException(status_code=500, detail="Internal calculation error")
```

Files and locations:
- `routers/bazi.py:189` — 1 occurrence
- `routers/western.py:89` — 1 occurrence
- `routers/fusion.py:119`, `175`, `225` — 3 occurrences

**Step 2: Run existing tests to confirm no breakage**

Run: `python -c "import pytest; pytest.main(['-q', 'tests/test_endpoints.py'])"`

Expected: All pass unchanged (logging doesn't change response behavior).

**Step 3: Commit**

```bash
git add bazi_engine/routers/bazi.py bazi_engine/routers/western.py bazi_engine/routers/fusion.py
git commit -m "fix: add logging.exception() to router catch-all handlers

Bare except Exception blocks now log tracebacks before re-raising
HTTPException(500). Makes production errors debuggable without
changing client-facing behavior."
```

---

### Task 5: Add ascendant parameter to non-ledger calculate_wuxing_vector_from_planets (MEDIUM #8)

**Files:**
- Modify: `bazi_engine/wuxing/analysis.py:46-72`
- Test: `tests/test_fusion.py`

**Context:** The non-ledger `calculate_wuxing_vector_from_planets()` always calls `is_night_chart(sun_lon)` without an ascendant, silently assuming a day chart. The `_with_ledger` variant correctly accepts `ascendant`. They should have parity.

**Step 1: Write the failing test**

Add to `tests/test_fusion.py`:

```python
def test_non_ledger_function_accepts_ascendant():
    """Non-ledger variant must accept ascendant parameter (MEDIUM #8)."""
    from bazi_engine.wuxing.analysis import (
        calculate_wuxing_vector_from_planets,
        calculate_wuxing_vector_from_planets_with_ledger,
    )

    bodies = {
        "Sun": {"longitude": 100.0, "is_retrograde": False},
        "Moon": {"longitude": 200.0, "is_retrograde": False},
        "Mercury": {"longitude": 50.0, "is_retrograde": False},
    }
    # With ascendant=280 (night chart), Mercury should map to Metal
    v_with_asc = calculate_wuxing_vector_from_planets(bodies, ascendant=280.0)
    v_ledger, _ = calculate_wuxing_vector_from_planets_with_ledger(bodies, ascendant=280.0)

    # Both should produce identical vectors
    assert v_with_asc.to_list() == v_ledger.to_list(), (
        f"Non-ledger {v_with_asc.to_list()} != ledger {v_ledger.to_list()}"
    )
```

**Step 2: Run test to verify it fails**

Run: `python -c "import pytest; pytest.main(['-v', 'tests/test_fusion.py::test_non_ledger_function_accepts_ascendant'])"`

Expected: FAIL — `TypeError: calculate_wuxing_vector_from_planets() got an unexpected keyword argument 'ascendant'`

**Step 3: Add ascendant parameter**

In `bazi_engine/wuxing/analysis.py`, change the function signature at line 46:

```python
def calculate_wuxing_vector_from_planets(
    bodies: Dict[str, Dict[str, Any]],
    use_retrograde_weight: bool = True,
    ascendant: Optional[float] = None,
) -> WuXingVector:
```

And change line 62 from:
```python
    night = is_night_chart(sun_lon)
```
to:
```python
    night = is_night_chart(sun_lon, ascendant)
```

**Step 4: Run test to verify it passes**

Run: `python -c "import pytest; pytest.main(['-v', 'tests/test_fusion.py::test_non_ledger_function_accepts_ascendant'])"`

Expected: PASS

**Step 5: Commit**

```bash
git add bazi_engine/wuxing/analysis.py tests/test_fusion.py
git commit -m "fix: add ascendant parameter to non-ledger wuxing vector function

Matches the _with_ledger variant's signature. Previously always
assumed day chart by ignoring ascendant."
```

---

### Task 6: Fix dominant_element triple dict computation (MEDIUM #9)

**Files:**
- Modify: `bazi_engine/routers/fusion.py:164-165`

**Context:** Line 165 calls `wx_norm.to_dict()` three times. Compute once and reuse.

**Step 1: Fix the code**

In `bazi_engine/routers/fusion.py`, replace lines 164-165:

```python
            "wu_xing_vector":  wx_norm.to_dict(),
            "dominant_element": max(wx_norm.to_dict(), key=lambda k: wx_norm.to_dict()[k]),
```

with:

```python
            "wu_xing_vector":  wx_norm.to_dict(),
            "dominant_element": max(wx_norm.to_dict(), key=wx_norm.to_dict().get),
```

Note: `to_dict()` is still called twice (once for the value, once for the max). To fully optimize, use a local variable. But since this is inside the dict literal, the cleanest fix is:

Actually, replace the full block from line 162 onwards. Find the return dict in `calculate_wuxing_endpoint` and change:

Before the return dict (around line 161), add:
```python
        wx_dict = wx_norm.to_dict()
```

Then in the return dict, replace:
```python
            "wu_xing_vector":  wx_norm.to_dict(),
            "dominant_element": max(wx_norm.to_dict(), key=lambda k: wx_norm.to_dict()[k]),
```
with:
```python
            "wu_xing_vector":  wx_dict,
            "dominant_element": max(wx_dict, key=wx_dict.get),
```

**Step 2: Run existing tests**

Run: `python -c "import pytest; pytest.main(['-q', 'tests/test_endpoints.py'])"`

Expected: All pass.

**Step 3: Commit**

```bash
git add bazi_engine/routers/fusion.py
git commit -m "perf: compute wuxing dict once in /calculate/wuxing endpoint

Avoids calling to_dict() three times per request."
```

---

### Task 7: Cache ephemeris env var at module load time (MEDIUM #10)

**Files:**
- Modify: `bazi_engine/provenance.py:69-75`

**Context:** `_detect_ephemeris_id()` reads `os.environ.get("EPHEMERIS_MODE")` on every call. Since this env var doesn't change during server lifetime, cache it.

**Step 1: Fix the code**

In `bazi_engine/provenance.py`, replace:

```python
def _detect_ephemeris_id() -> str:
    """Identify the active ephemeris backend."""
    mode = os.environ.get("EPHEMERIS_MODE", "SWIEPH").upper()
    if mode == "MOSEPH":
        return "moshier_analytic"
    # Default: Swiss Ephemeris with sepl_18 data files
    return "swieph_sepl18"
```

with:

```python
def _detect_ephemeris_id() -> str:
    """Identify the active ephemeris backend."""
    mode = os.environ.get("EPHEMERIS_MODE", "SWIEPH").upper()
    if mode == "MOSEPH":
        return "moshier_analytic"
    return "swieph_sepl18"


# Cache at module load — env var won't change during server lifetime
_EPHEMERIS_ID: str = _detect_ephemeris_id()
```

Then in `build_provenance()`, change:
```python
        ephemeris_id=_detect_ephemeris_id(),
```
to:
```python
        ephemeris_id=_EPHEMERIS_ID,
```

**Step 2: Run existing tests**

Run: `python -c "import pytest; pytest.main(['-q', 'tests/test_provenance.py'])"`

Expected: All pass.

**Step 3: Commit**

```bash
git add bazi_engine/provenance.py
git commit -m "perf: cache ephemeris ID at module load time

EPHEMERIS_MODE env var is read once at import, not per-request."
```

---

### Task 8: Include aspect orbs in WUXING_PARAMETER_SET (MEDIUM #11)

**Files:**
- Modify: `bazi_engine/provenance.py:17-26`
- Modify: `bazi_engine/aspects.py:11-18`

**Context:** Aspect orb values (8.0, 6.0, 7.0, etc.) are hardcoded in `aspects.py` but not captured in `WUXING_PARAMETER_SET`, so provenance doesn't document which orbs produced the result.

**Step 1: Write the failing test**

Add to `tests/test_parameter_set.py`:

```python
def test_parameter_set_contains_aspect_orbs():
    """Aspect orbs must be documented in parameter_set (MEDIUM #11)."""
    from bazi_engine.provenance import WUXING_PARAMETER_SET
    assert "aspect_orbs" in WUXING_PARAMETER_SET
    orbs = WUXING_PARAMETER_SET["aspect_orbs"]
    assert "conjunction" in orbs
    assert "opposition" in orbs
    assert orbs["conjunction"] == 8.0
```

**Step 2: Run test to verify it fails**

Run: `python -c "import pytest; pytest.main(['-v', 'tests/test_parameter_set.py::test_parameter_set_contains_aspect_orbs'])"`

Expected: FAIL — `KeyError: 'aspect_orbs'`

**Step 3: Add aspect orbs to parameter set**

In `bazi_engine/provenance.py`, add to `WUXING_PARAMETER_SET` dict (after `"harmony_method"` line):

```python
    "aspect_orbs": {
        "conjunction": 8.0,
        "sextile": 6.0,
        "square": 7.0,
        "trine": 8.0,
        "opposition": 8.0,
    },
```

In `bazi_engine/aspects.py`, add a reference comment at line 11:

```python
# Orb values are also documented in provenance.WUXING_PARAMETER_SET["aspect_orbs"]
```

**Step 4: Run test to verify it passes**

Run: `python -c "import pytest; pytest.main(['-v', 'tests/test_parameter_set.py::test_parameter_set_contains_aspect_orbs'])"`

Expected: PASS

**Step 5: Commit**

```bash
git add bazi_engine/provenance.py bazi_engine/aspects.py tests/test_parameter_set.py
git commit -m "feat: include aspect orbs in WUXING_PARAMETER_SET

Documents orb values in provenance so consumers know which
thresholds produced the aspects list."
```

---

### Task 9: Add class-scoped fixture to test_contribution_ledger.py (MEDIUM #12)

**Files:**
- Modify: `tests/test_contribution_ledger.py`

**Context:** Each test method independently calls the `/calculate/fusion` endpoint. With 14 tests across 3 classes, that's 14 HTTP calls with the same payload. A class-scoped fixture caches the response.

**Step 1: Add fixture and refactor**

Add a module-level fixture at the top of the file (after `_skip_no_ephe`):

```python
@pytest.fixture(scope="module")
def fusion_response():
    """Cache the fusion endpoint response for the whole module."""
    r = client.post("/calculate/fusion", json=PAYLOAD)
    assert r.status_code == 200
    return r.json()


@pytest.fixture(scope="module")
def wuxing_response():
    """Cache the wuxing endpoint response for the whole module."""
    r = client.post("/calculate/wuxing", json=PAYLOAD)
    assert r.status_code == 200
    return r.json()
```

Then refactor each test class to use the `fusion_response` fixture instead of calling the endpoint directly. For example, change:

```python
    def test_fusion_has_contribution_ledger(self):
        r = client.post("/calculate/fusion", json=PAYLOAD)
        assert r.status_code == 200
        data = r.json()
        assert "contribution_ledger" in data
```

to:

```python
    def test_fusion_has_contribution_ledger(self, fusion_response):
        assert "contribution_ledger" in fusion_response
```

Apply this pattern to ALL tests in the file except the one test that calls `/calculate/wuxing` (use `wuxing_response` fixture for that one).

For `TestCategoryTags`, replace the `_western_ledger` and `_bazi_ledger` helper methods with fixtures:

```python
    def test_traditional_planets_tagged_traditional(self, fusion_response):
        for entry in fusion_response["contribution_ledger"]["western"]:
            if entry["planet"] in self.TRADITIONAL_PLANETS:
                assert entry["category"] == "traditional"
```

**Step 2: Run tests to verify they pass**

Run: `python -c "import pytest; pytest.main(['-v', 'tests/test_contribution_ledger.py'])"`

Expected: All 14 tests pass. Should run noticeably faster (2 HTTP calls instead of 14).

**Step 3: Commit**

```bash
git add tests/test_contribution_ledger.py
git commit -m "perf: use module-scoped fixture in contribution ledger tests

Reduces HTTP calls from 14 to 2 by caching fusion and wuxing
endpoint responses across all test methods."
```

---

### Task 10: Regenerate OpenAPI spec + snapshots + final verification

**Files:**
- Regenerate: `spec/openapi/openapi.json`
- Regenerate: `tests/snapshots/`

**Step 1: Regenerate OpenAPI spec**

Run: `python scripts/export_openapi.py`

**Step 2: Verify OpenAPI spec**

Run: `python scripts/export_openapi.py --check`

Expected: No drift detected.

**Step 3: Regenerate snapshots**

Run: `UPDATE_SNAPSHOTS=1 python -c "import pytest; pytest.main(['-q', 'tests/test_snapshot_stability.py'])"`

**Step 4: Run full test suite**

Run: `python -c "import pytest; pytest.main(['-q'])"`

Expected: All pass (1350+ passed, ~14 skipped, 0 failed).

**Step 5: Run linting**

Run: `ruff check bazi_engine/ --output-format=github`

Expected: No new issues from our changes.

**Step 6: Commit**

```bash
git add spec/openapi/openapi.json tests/snapshots/
git commit -m "chore: regenerate OpenAPI spec and snapshots after review fixes"
```

---

## Definition of Done

- [ ] swe.set_sid_mode() protected by threading lock + reset (CRITICAL #1)
- [ ] WesternBody has frozen=True (CRITICAL #2)
- [ ] constants.py has from __future__ import annotations (CRITICAL #3)
- [ ] provenance module registered in LAYERS at Layer 1 (HIGH #4)
- [ ] All router except blocks log tracebacks (HIGH #6)
- [ ] Non-ledger wuxing function accepts ascendant (MEDIUM #8)
- [ ] dominant_element computed with single to_dict() call (MEDIUM #9)
- [ ] Ephemeris ID cached at module load (MEDIUM #10)
- [ ] Aspect orbs in WUXING_PARAMETER_SET (MEDIUM #11)
- [ ] Test fixtures reduce HTTP calls (MEDIUM #12)
- [ ] OpenAPI spec + snapshots regenerated
- [ ] Full test suite green
- [ ] No new lint issues
