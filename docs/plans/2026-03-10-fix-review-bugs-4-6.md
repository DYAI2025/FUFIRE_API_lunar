# Fix Review Bugs #4 and #6 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix two bugs found in code review: unbounded sector index in transit.py (#4) and KeyError on explicit planet list in aspects.py (#6).

**Architecture:** Two independent single-line fixes with existing regression tests that currently document the bugs. After fixing, the regression tests must be updated to expect correct behavior instead of errors.

**Tech Stack:** Python 3.10+, pytest

---

### Task 1: Fix unbounded sector index in transit.py (#4)

**Bug:** `sector = int(lon_deg // 30)` on line 88 produces sector >= 12 when `lon_deg >= 360` (e.g., ephemeris returns 360.0). This causes `IndexError: list index out of range` when used as `ZODIAC_SIGNS[sector]`.

**Files:**
- Modify: `bazi_engine/transit.py:88`
- Test: `tests/test_transit_cache.py` (existing test already triggers this)

**Step 1: Verify the bug exists — run the test that exposes it**

The test `test_different_hour_computes_fresh` in `tests/test_transit_cache.py` uses mock data with shifted longitudes. When longitudes exceed 360, the current code crashes.

Run: `pytest tests/test_transit_cache.py::TestTransitCacheHit::test_different_hour_computes_fresh -v`
Expected: Currently PASSES (mock data was already fixed with `% 360` in the test). We need a dedicated regression test.

**Step 2: Write a direct regression test for sector overflow**

Add to `tests/test_transit_cache.py`:

```python
class TestSectorBounds:
    """Verify sector index stays within 0-11."""

    def test_longitude_360_does_not_overflow(self):
        """lon_deg=360.0 should map to sector 0, not sector 12."""
        from bazi_engine.transit import ZODIAC_SIGNS
        mock_data = {
            0: (360.0, 0.0, 1.0, 1.0, 0.0, 0.0),   # lon=360 → sector should be 0
            1: (359.9, 0.0, 0.003, 13.2, 0.0, 0.0),
            2: (0.0, 0.0, 0.8, 1.8, 0.0, 0.0),
            3: (90.0, 0.0, 0.7, 1.2, 0.0, 0.0),
            4: (180.0, 0.0, 1.5, 0.7, 0.0, 0.0),
            5: (270.0, 0.0, 5.0, 0.08, 0.0, 0.0),
            6: (330.0, 0.0, 9.5, 0.03, 0.0, 0.0),
        }
        def mock_calc(jd, pid, flags):
            return mock_data[pid], 0

        dt = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        with patch("bazi_engine.transit.swe.calc_ut", side_effect=mock_calc):
            result = compute_transit_now(dt_utc=dt)
        # Should NOT raise IndexError
        assert result["planets"]["sun"]["sector"] == 0
        assert result["planets"]["sun"]["sign"] == "aries"
```

Run: `pytest tests/test_transit_cache.py::TestSectorBounds::test_longitude_360_does_not_overflow -v`
Expected: FAIL with `IndexError: list index out of range`

**Step 3: Fix the bug**

In `bazi_engine/transit.py`, change line 88 from:

```python
        sector = int(lon_deg // 30)
```

to:

```python
        sector = int(lon_deg // 30) % 12
```

**Step 4: Run the test to verify it passes**

Run: `pytest tests/test_transit_cache.py::TestSectorBounds -v`
Expected: PASS

**Step 5: Run full transit tests to verify no regressions**

Run: `pytest tests/test_transit_cache.py tests/test_transit.py tests/test_transit_validation.py tests/test_transit_events_negative.py -v`
Expected: All pass

**Step 6: Commit**

```bash
git add bazi_engine/transit.py tests/test_transit_cache.py
git commit -m "fix: guard sector index with modulo 12 to prevent IndexError on lon>=360"
```

---

### Task 2: Fix KeyError on explicit planet list in aspects.py (#6)

**Bug:** `compute_aspects(bodies, planets=["Sun", "Mars"])` raises `KeyError` when `"Mars"` is in the explicit `planets` list but not in `bodies`. Line 58: `lon1 = bodies[p1]["longitude"]` does not check if `p1` exists in `bodies`.

**Files:**
- Modify: `bazi_engine/aspects.py:56-59`
- Modify: `tests/test_aspects_negative.py` (update existing test expectation)

**Step 1: Verify the bug exists**

Run: `pytest tests/test_aspects_negative.py::TestComputeAspectsNegativeCases::test_explicit_planet_not_in_bodies_raises -v`
Expected: PASS (test currently expects `KeyError` — confirming the bug exists)

**Step 2: Update the test to expect correct behavior (no crash)**

In `tests/test_aspects_negative.py`, replace the existing test:

```python
    def test_explicit_planet_not_in_bodies_filtered(self):
        """Requesting planet not in bodies should skip it, not crash."""
        bodies = {"Sun": {"longitude": 100.0}}
        aspects = compute_aspects(bodies, planets=["Sun", "Mars"])
        # Mars not in bodies → only Sun left → no pairs → no aspects
        assert aspects == []
```

Run: `pytest tests/test_aspects_negative.py::TestComputeAspectsNegativeCases::test_explicit_planet_not_in_bodies_filtered -v`
Expected: FAIL with `KeyError: 'Mars'`

**Step 3: Fix the bug**

In `bazi_engine/aspects.py`, change lines 56-59 from:

```python
    for i, p1 in enumerate(planets):
        for p2 in planets[i + 1:]:
            lon1 = bodies[p1]["longitude"]
            lon2 = bodies[p2]["longitude"]
```

to:

```python
    for i, p1 in enumerate(planets):
        if p1 not in bodies or bodies[p1].get("longitude") is None:
            continue
        for p2 in planets[i + 1:]:
            if p2 not in bodies or bodies[p2].get("longitude") is None:
                continue
            lon1 = bodies[p1]["longitude"]
            lon2 = bodies[p2]["longitude"]
```

This also fixes the `None` longitude case (review item in test `test_planet_with_none_longitude_filtered_out` for the explicit planets path).

**Step 4: Run the test to verify it passes**

Run: `pytest tests/test_aspects_negative.py::TestComputeAspectsNegativeCases::test_explicit_planet_not_in_bodies_filtered -v`
Expected: PASS

**Step 5: Run full aspects tests to verify no regressions**

Run: `pytest tests/test_aspects_negative.py tests/test_aspects.py -v`
Expected: All pass

**Step 6: Run full test suite**

Run: `pytest -q --tb=short`
Expected: All pass (1450+ tests)

**Step 7: Commit**

```bash
git add bazi_engine/aspects.py tests/test_aspects_negative.py
git commit -m "fix: filter missing/null-longitude planets in compute_aspects to prevent KeyError"
```

---
