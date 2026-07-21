# Sprint 3: Transparente Elemente — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make Wu-Xing vectors fully traceable — every element value points to its input data via a Contribution Ledger, with category tags and calibrated harmony in standard output.

**Architecture:** Extend existing Wu-Xing calculation functions to return per-contribution breakdowns alongside their aggregated vectors. No new endpoints — enrich existing `/calculate/fusion` and `/calculate/wuxing` responses with contribution_ledger, calibration, and category metadata. Mercury day/night logic gets explicit quality_flag instead of silent default.

**Tech Stack:** Python 3.10+, FastAPI, pyswisseph, pytest, frozen dataclasses

**Source Documents:**
- `spec/FuFirE_B2B_Sprint_Plan_v1.docx` (Sprint 3 tasks 3.1–3.6)

**Sprint 2 Delivered (dependencies met):**
- House quality flags (exact/fallback) in western+fusion responses
- Zodiac mode (tropical/sidereal) configurable per request
- Aspects (conjunction/opposition/trine/square/sextile) in /calculate/western
- BaZi ruleset externalized from JSON
- Pillar derivation trace in /calculate/bazi
- 21+ golden test cases

---

## Task 1: Western Planet Contribution Ledger (3.1)

Each planet shows: assigned element, weight, rationale, retrograde status. Contribution Ledger as part of the `/calculate/fusion` and `/calculate/wuxing` responses.

---

### Task 1.1: Write failing tests for Western contribution ledger

**Files:**
- Create: `tests/test_contribution_ledger.py`

**Step 1: Write the test file**

```python
"""Tests: Wu-Xing contribution ledger in fusion/wuxing responses."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from bazi_engine.app import app

client = TestClient(app)

PAYLOAD = {
    "date": "2024-02-10T14:30:00",
    "tz": "Europe/Berlin",
    "lon": 13.405,
    "lat": 52.52,
}


def _ephemeris_available() -> bool:
    r = client.post("/calculate/western", json=PAYLOAD)
    return r.status_code == 200


_HAS_EPHEMERIS = _ephemeris_available()
_skip_no_ephe = pytest.mark.skipif(
    not _HAS_EPHEMERIS,
    reason="Swiss Ephemeris files not available",
)


@_skip_no_ephe
class TestWesternContributionLedger:
    """Per-planet Wu-Xing contribution breakdown."""

    def test_fusion_has_contribution_ledger(self):
        r = client.post("/calculate/fusion", json=PAYLOAD)
        assert r.status_code == 200
        data = r.json()
        assert "contribution_ledger" in data

    def test_ledger_has_western_entries(self):
        r = client.post("/calculate/fusion", json=PAYLOAD)
        data = r.json()
        ledger = data["contribution_ledger"]
        assert "western" in ledger
        assert isinstance(ledger["western"], list)
        assert len(ledger["western"]) >= 5  # at least major planets

    def test_western_entry_structure(self):
        r = client.post("/calculate/fusion", json=PAYLOAD)
        data = r.json()
        entry = data["contribution_ledger"]["western"][0]
        assert "planet" in entry
        assert "element" in entry
        assert "weight" in entry
        assert "is_retrograde" in entry
        assert "category" in entry
        assert entry["element"] in ("Holz", "Feuer", "Erde", "Metall", "Wasser")
        assert entry["category"] in ("traditional", "modern_heuristic", "experimental")

    def test_mercury_shows_day_night_rationale(self):
        r = client.post("/calculate/fusion", json=PAYLOAD)
        data = r.json()
        mercury = [e for e in data["contribution_ledger"]["western"]
                   if e["planet"] == "Mercury"]
        assert len(mercury) == 1
        assert "rationale" in mercury[0]
        assert "chart" in mercury[0]["rationale"].lower()  # "day chart" or "night chart"

    def test_retrograde_weight_is_1_3(self):
        r = client.post("/calculate/fusion", json=PAYLOAD)
        data = r.json()
        for entry in data["contribution_ledger"]["western"]:
            if entry["is_retrograde"]:
                assert entry["weight"] == 1.3
            else:
                assert entry["weight"] == 1.0

    def test_wuxing_endpoint_has_contribution_ledger(self):
        r = client.post("/calculate/wuxing", json=PAYLOAD)
        assert r.status_code == 200
        data = r.json()
        assert "contribution_ledger" in data
        assert "western" in data["contribution_ledger"]
```

**Step 2: Run tests to verify they fail**

Run: `python -c "import pytest; pytest.main(['-v', 'tests/test_contribution_ledger.py'])"`
Expected: FAIL — `contribution_ledger` key not in response

**Step 3: Commit**

```bash
git add tests/test_contribution_ledger.py
git commit -m "test: add Western contribution ledger tests (red)"
```

---

### Task 1.2: Implement Western contribution ledger in analysis.py

**Files:**
- Modify: `bazi_engine/wuxing/analysis.py:46-72` (calculate_wuxing_vector_from_planets)

**Step 1: Read current implementation**

Read `bazi_engine/wuxing/analysis.py` fully.

**Step 2: Add ledger return to calculate_wuxing_vector_from_planets**

The function currently returns only `WuXingVector`. Change it to also return a list of per-planet contribution entries. Since existing callers expect just a WuXingVector, add a separate function:

```python
def calculate_wuxing_vector_from_planets_with_ledger(
    bodies: Dict[str, Dict[str, Any]],
    use_retrograde_weight: bool = True,
) -> tuple[WuXingVector, list[dict[str, Any]]]:
    """Like calculate_wuxing_vector_from_planets but also returns per-planet ledger.

    Each ledger entry:
      planet, element, weight, is_retrograde, rationale, category
    """
    values = [0.0, 0.0, 0.0, 0.0, 0.0]
    ledger: list[dict[str, Any]] = []
    sun_data = bodies.get("Sun", {})
    sun_lon = sun_data.get("longitude", 0)
    asc = None  # Will be set if available from bodies
    night = is_night_chart(sun_lon, asc)

    for planet, data in bodies.items():
        if "error" in data:
            continue
        is_retrograde = data.get("is_retrograde", False)
        element = planet_to_wuxing(planet, night)
        weight = 1.3 if (use_retrograde_weight and is_retrograde) else 1.0
        values[WUXING_INDEX[element]] += weight

        # Rationale for Mercury's dual nature
        rationale = f"Classical rulership"
        if planet == "Mercury":
            chart_type = "night chart" if night else "day chart"
            rationale = f"Dual element — {element} ({chart_type})"

        # Category: traditional planets (Sun-Saturn), modern (Uranus-Pluto), experimental (nodes, lilith)
        traditional_planets = {"Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn"}
        modern_planets = {"Uranus", "Neptune", "Pluto"}
        if planet in traditional_planets:
            category = "traditional"
        elif planet in modern_planets:
            category = "modern_heuristic"
        else:
            category = "experimental"

        ledger.append({
            "planet": planet,
            "element": element,
            "weight": weight,
            "is_retrograde": is_retrograde,
            "rationale": rationale,
            "category": category,
        })

    return WuXingVector(*values), ledger
```

**Step 3: Run existing wuxing tests to check nothing breaks**

Run: `python -c "import pytest; pytest.main(['-q', 'tests/test_wuxing_analysis.py'])"`
Expected: ALL PASS (new function, existing one unchanged)

**Step 4: Commit**

```bash
git add bazi_engine/wuxing/analysis.py
git commit -m "feat: add calculate_wuxing_vector_from_planets_with_ledger function"
```

---

### Task 1.3: Wire Western ledger into fusion and wuxing responses

**Files:**
- Modify: `bazi_engine/wuxing/__init__.py` (re-export new function)
- Modify: `bazi_engine/fusion.py:22-33` (re-export new function)
- Modify: `bazi_engine/fusion.py:72-127` (compute_fusion_analysis — use _with_ledger, include in result)
- Modify: `bazi_engine/routers/fusion.py:49-57` (FusionResponse — add contribution_ledger field)
- Modify: `bazi_engine/routers/fusion.py:137-165` (wuxing endpoint — include ledger)

**Step 1: Re-export from wuxing/__init__.py and fusion.py**

Add `calculate_wuxing_vector_from_planets_with_ledger` to both `__init__.py` and `fusion.py` re-exports.

**Step 2: Use _with_ledger in compute_fusion_analysis**

In `fusion.py:compute_fusion_analysis()`, change:
```python
# Before:
western_wuxing = calculate_wuxing_vector_from_planets(western_bodies)

# After:
western_wuxing, western_ledger = calculate_wuxing_vector_from_planets_with_ledger(western_bodies)
```

Add `"contribution_ledger": {"western": western_ledger}` to the returned dict.

**Step 3: Add contribution_ledger to FusionResponse**

In `routers/fusion.py`:
```python
contribution_ledger: Optional[Dict[str, Any]] = None
```

Pass `fusion["contribution_ledger"]` through in the endpoint.

**Step 4: Add ledger to /calculate/wuxing endpoint**

In the wuxing endpoint, use the _with_ledger variant and include it in response. Add `contribution_ledger: Optional[Dict[str, Any]] = None` to WxResponse.

**Step 5: Run contribution ledger tests**

Run: `python -c "import pytest; pytest.main(['-v', 'tests/test_contribution_ledger.py'])"`
Expected: ALL PASS

**Step 6: Run full test suite**

Run: `python -c "import pytest; pytest.main(['-q', 'tests/'])"`
Expected: ALL PASS

**Step 7: Commit**

```bash
git add bazi_engine/wuxing/__init__.py bazi_engine/wuxing/analysis.py bazi_engine/fusion.py bazi_engine/routers/fusion.py
git commit -m "feat: wire Western contribution ledger into fusion and wuxing responses"
```

---

## Task 2: BaZi Pillar Contribution Ledger (3.2)

Stem contribution, Branch contribution, Hidden-Stem contributions — individually itemized.

---

### Task 2.1: Write failing tests for BaZi contribution ledger

**Files:**
- Modify: `tests/test_contribution_ledger.py` (add BaZi section)

**Step 1: Add BaZi ledger tests**

Append to `tests/test_contribution_ledger.py`:

```python
@_skip_no_ephe
class TestBaziContributionLedger:
    """Per-pillar Wu-Xing contribution breakdown."""

    def test_ledger_has_bazi_entries(self):
        r = client.post("/calculate/fusion", json=PAYLOAD)
        data = r.json()
        ledger = data["contribution_ledger"]
        assert "bazi" in ledger
        assert isinstance(ledger["bazi"], list)
        assert len(ledger["bazi"]) >= 4  # at least 4 pillars × 1 stem

    def test_bazi_entry_structure(self):
        r = client.post("/calculate/fusion", json=PAYLOAD)
        data = r.json()
        entry = data["contribution_ledger"]["bazi"][0]
        assert "pillar" in entry
        assert "source" in entry       # "stem", "hidden_main", "hidden_middle", "hidden_residual"
        assert "element" in entry
        assert "weight" in entry
        assert "category" in entry
        assert entry["pillar"] in ("year", "month", "day", "hour")
        assert entry["category"] == "traditional"

    def test_hidden_stems_have_qi_weights(self):
        r = client.post("/calculate/fusion", json=PAYLOAD)
        data = r.json()
        hidden = [e for e in data["contribution_ledger"]["bazi"] if e["source"].startswith("hidden")]
        assert len(hidden) >= 1
        for h in hidden:
            assert h["weight"] in (1.0, 0.5, 0.3)  # main/middle/residual Qi

    def test_stem_weight_is_1(self):
        r = client.post("/calculate/fusion", json=PAYLOAD)
        data = r.json()
        stems = [e for e in data["contribution_ledger"]["bazi"] if e["source"] == "stem"]
        assert len(stems) == 4  # one per pillar
        for s in stems:
            assert s["weight"] == 1.0
```

**Step 2: Run tests to verify they fail**

Run: `python -c "import pytest; pytest.main(['-v', 'tests/test_contribution_ledger.py::TestBaziContributionLedger'])"`
Expected: FAIL — no `bazi` key in contribution_ledger

**Step 3: Commit**

```bash
git add tests/test_contribution_ledger.py
git commit -m "test: add BaZi contribution ledger tests (red)"
```

---

### Task 2.2: Implement BaZi contribution ledger in analysis.py

**Files:**
- Modify: `bazi_engine/wuxing/analysis.py:101-122` (calculate_wuxing_from_bazi)

**Step 1: Add a _with_ledger variant**

```python
def calculate_wuxing_from_bazi_with_ledger(
    pillars: Dict[str, Dict[str, str]],
) -> tuple[WuXingVector, list[dict[str, Any]]]:
    """Extract Wu-Xing vector from BaZi pillars with per-contribution ledger."""
    values = [0.0, 0.0, 0.0, 0.0, 0.0]
    ledger: list[dict[str, Any]] = []

    _QI_LABELS = {1.0: "hidden_main", 0.5: "hidden_middle", 0.3: "hidden_residual"}

    for pillar_name, pillar_data in pillars.items():
        stem = pillar_data.get("stem", pillar_data.get("stamm", ""))
        branch = pillar_data.get("branch", pillar_data.get("zweig", ""))

        if stem in _STEM_TO_ELEMENT:
            element = _STEM_TO_ELEMENT[stem]
            values[WUXING_INDEX[element]] += 1.0
            ledger.append({
                "pillar": pillar_name,
                "source": "stem",
                "stem_name": stem,
                "element": element,
                "weight": 1.0,
                "category": "traditional",
            })

        for elem, weight in _BRANCH_HIDDEN.get(branch, []):
            values[WUXING_INDEX[elem]] += weight
            ledger.append({
                "pillar": pillar_name,
                "source": _QI_LABELS.get(weight, "hidden"),
                "branch_name": branch,
                "element": elem,
                "weight": weight,
                "category": "traditional",
            })

    return WuXingVector(*values), ledger
```

**Step 2: Run existing BaZi wuxing tests**

Run: `python -c "import pytest; pytest.main(['-q', 'tests/test_wuxing_analysis.py'])"`
Expected: ALL PASS

**Step 3: Commit**

```bash
git add bazi_engine/wuxing/analysis.py
git commit -m "feat: add calculate_wuxing_from_bazi_with_ledger function"
```

---

### Task 2.3: Wire BaZi ledger into fusion response

**Files:**
- Modify: `bazi_engine/wuxing/__init__.py` (re-export)
- Modify: `bazi_engine/fusion.py` (re-export + use in compute_fusion_analysis)

**Step 1: Re-export and use _with_ledger**

In `fusion.py:compute_fusion_analysis()`:
```python
# Before:
bazi_wuxing = calculate_wuxing_from_bazi(bazi_pillars)

# After:
bazi_wuxing, bazi_ledger = calculate_wuxing_from_bazi_with_ledger(bazi_pillars)
```

Add `"bazi": bazi_ledger` to the `"contribution_ledger"` dict.

**Step 2: Run all contribution ledger tests**

Run: `python -c "import pytest; pytest.main(['-v', 'tests/test_contribution_ledger.py'])"`
Expected: ALL PASS

**Step 3: Run full test suite**

Run: `python -c "import pytest; pytest.main(['-q', 'tests/'])"`
Expected: ALL PASS

**Step 4: Commit**

```bash
git add bazi_engine/wuxing/__init__.py bazi_engine/fusion.py
git commit -m "feat: wire BaZi contribution ledger into fusion response"
```

---

## Task 3: Mercury Day/Night Quality Flag (3.3)

No silent default to Day Chart if Ascendant is missing. Explicit quality_flag.

---

### Task 3.1: Write failing tests for Mercury quality flag

**Files:**
- Create: `tests/test_mercury_quality.py`

**Step 1: Write the test file**

```python
"""Tests: Mercury day/night chart detection quality flag."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from bazi_engine.app import app
from bazi_engine.wuxing.analysis import is_night_chart

client = TestClient(app)

PAYLOAD = {
    "date": "2024-02-10T14:30:00",
    "tz": "Europe/Berlin",
    "lon": 13.405,
    "lat": 52.52,
}


def _ephemeris_available() -> bool:
    r = client.post("/calculate/western", json=PAYLOAD)
    return r.status_code == 200


_HAS_EPHEMERIS = _ephemeris_available()
_skip_no_ephe = pytest.mark.skipif(
    not _HAS_EPHEMERIS,
    reason="Swiss Ephemeris files not available",
)


class TestIsNightChartUnit:
    """Unit tests for is_night_chart function."""

    def test_with_ascendant_returns_bool(self):
        result = is_night_chart(180.0, ascendant=90.0)
        assert isinstance(result, bool)

    def test_without_ascendant_defaults_day(self):
        result = is_night_chart(180.0, ascendant=None)
        assert result is False


@_skip_no_ephe
class TestMercuryQualityInLedger:
    """Mercury ledger entry must show chart_type_quality."""

    def test_mercury_has_chart_type_quality(self):
        r = client.post("/calculate/fusion", json=PAYLOAD)
        data = r.json()
        mercury = [e for e in data["contribution_ledger"]["western"]
                   if e["planet"] == "Mercury"]
        assert len(mercury) == 1
        assert "chart_type_quality" in mercury[0]
        assert mercury[0]["chart_type_quality"] in ("exact", "assumed_day")

    def test_with_ascendant_quality_is_exact(self):
        """When house system computes successfully, Ascendant is known."""
        r = client.post("/calculate/fusion", json=PAYLOAD)
        data = r.json()
        # Berlin at 52° — Placidus should work, Ascendant available
        mercury = [e for e in data["contribution_ledger"]["western"]
                   if e["planet"] == "Mercury"][0]
        assert mercury["chart_type_quality"] == "exact"
```

**Step 2: Run tests**

Run: `python -c "import pytest; pytest.main(['-v', 'tests/test_mercury_quality.py'])"`
Expected: FAIL on `chart_type_quality` key

**Step 3: Commit**

```bash
git add tests/test_mercury_quality.py
git commit -m "test: add Mercury day/night quality flag tests (red)"
```

---

### Task 3.2: Implement Mercury quality flag

**Files:**
- Modify: `bazi_engine/wuxing/analysis.py` (in the _with_ledger function)

**Step 1: Pass Ascendant through and track quality**

In `calculate_wuxing_vector_from_planets_with_ledger`, check whether an Ascendant was available in the bodies or chart data. The western chart includes `angles` with `asc` when house system works.

Modify the function signature to accept `ascendant: Optional[float] = None`:

```python
def calculate_wuxing_vector_from_planets_with_ledger(
    bodies: Dict[str, Dict[str, Any]],
    use_retrograde_weight: bool = True,
    ascendant: Optional[float] = None,
) -> tuple[WuXingVector, list[dict[str, Any]]]:
```

Use Ascendant for night chart detection:
```python
night = is_night_chart(sun_lon, ascendant)
chart_type_quality = "exact" if ascendant is not None else "assumed_day"
```

Add `"chart_type_quality"` to Mercury's ledger entry (and optionally to all entries for consistency).

**Step 2: Pass Ascendant from compute_fusion_analysis**

In `fusion.py`, pass `ascendant=western_bodies.get("angles", {}).get("asc")` — but you need to check how the western chart result is structured. Read `bazi_engine/western.py` to find where angles are stored. The Ascendant may be at `western_chart["angles"]["asc"]` or similar.

In `routers/fusion.py`, pass `western_chart.get("angles", {}).get("asc")` through.

**Step 3: Run tests**

Run: `python -c "import pytest; pytest.main(['-v', 'tests/test_mercury_quality.py'])"`
Expected: ALL PASS

**Step 4: Run full test suite**

Run: `python -c "import pytest; pytest.main(['-q', 'tests/'])"`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add bazi_engine/wuxing/analysis.py bazi_engine/fusion.py bazi_engine/routers/fusion.py
git commit -m "feat: add chart_type_quality flag to Mercury contribution (no silent default)"
```

---

## Task 4: Parameter Set Versioning (3.4)

Retrograde weight and all magic numbers as named parameters in a versionable parameter_set.

---

### Task 4.1: Write failing tests for parameter_set

**Files:**
- Create: `tests/test_parameter_set.py`

**Step 1: Write the test file**

```python
"""Tests: Versionable parameter_set in Wu-Xing calculations."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from bazi_engine.app import app

client = TestClient(app)

PAYLOAD = {
    "date": "2024-02-10T14:30:00",
    "tz": "Europe/Berlin",
    "lon": 13.405,
    "lat": 52.52,
}


def _ephemeris_available() -> bool:
    r = client.post("/calculate/fusion", json=PAYLOAD)
    return r.status_code == 200


_HAS_EPHEMERIS = _ephemeris_available()
_skip_no_ephe = pytest.mark.skipif(
    not _HAS_EPHEMERIS,
    reason="Swiss Ephemeris files not available",
)


@_skip_no_ephe
class TestParameterSet:
    """parameter_set must be in provenance with all magic numbers."""

    def test_provenance_has_parameter_set(self):
        r = client.post("/calculate/fusion", json=PAYLOAD)
        data = r.json()
        assert "parameter_set" in data["provenance"]

    def test_parameter_set_has_version(self):
        r = client.post("/calculate/fusion", json=PAYLOAD)
        data = r.json()
        ps = data["provenance"]["parameter_set"]
        assert "version" in ps

    def test_parameter_set_has_retrograde_weight(self):
        r = client.post("/calculate/fusion", json=PAYLOAD)
        data = r.json()
        ps = data["provenance"]["parameter_set"]
        assert "retrograde_weight" in ps
        assert ps["retrograde_weight"] == 1.3

    def test_parameter_set_has_hidden_stem_weights(self):
        r = client.post("/calculate/fusion", json=PAYLOAD)
        data = r.json()
        ps = data["provenance"]["parameter_set"]
        assert "hidden_stem_main_qi" in ps
        assert ps["hidden_stem_main_qi"] == 1.0
        assert "hidden_stem_middle_qi" in ps
        assert ps["hidden_stem_middle_qi"] == 0.5
        assert "hidden_stem_residual_qi" in ps
        assert ps["hidden_stem_residual_qi"] == 0.3

    def test_parameter_set_in_wuxing_endpoint(self):
        r = client.post("/calculate/wuxing", json=PAYLOAD)
        data = r.json()
        assert "parameter_set" in data["provenance"]
```

**Step 2: Run tests**

Run: `python -c "import pytest; pytest.main(['-v', 'tests/test_parameter_set.py'])"`
Expected: FAIL — no `parameter_set` in provenance

**Step 3: Commit**

```bash
git add tests/test_parameter_set.py
git commit -m "test: add parameter_set versioning tests (red)"
```

---

### Task 4.2: Implement parameter_set in provenance

**Files:**
- Modify: `bazi_engine/provenance.py` (add parameter_set to build_provenance)

**Step 1: Read provenance.py**

Read `bazi_engine/provenance.py` to understand `build_provenance()`.

**Step 2: Add WUXING_PARAMETER_SET constant and include in provenance**

```python
WUXING_PARAMETER_SET = {
    "version": "1.0.0",
    "retrograde_weight": 1.3,
    "hidden_stem_main_qi": 1.0,
    "hidden_stem_middle_qi": 0.5,
    "hidden_stem_residual_qi": 0.3,
    "stem_weight": 1.0,
    "mercury_dual_rule": "earth_day_metal_night",
    "harmony_method": "dot_product",
}
```

Add `"parameter_set": WUXING_PARAMETER_SET` to the dict returned by `build_provenance()`.

**Step 3: Run tests**

Run: `python -c "import pytest; pytest.main(['-v', 'tests/test_parameter_set.py'])"`
Expected: ALL PASS

**Step 4: Run full test suite**

Run: `python -c "import pytest; pytest.main(['-q', 'tests/'])"`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add bazi_engine/provenance.py
git commit -m "feat: add versionable parameter_set to provenance with all magic numbers"
```

---

## Task 5: Category Tags on All Contributions (3.5)

Every Wu-Xing contribution is categorized as `traditional | modern_heuristic | experimental`.

---

### Task 5.1: Write failing tests for category consistency

**Files:**
- Modify: `tests/test_contribution_ledger.py` (add category section)

**Step 1: Add category validation tests**

Append to `tests/test_contribution_ledger.py`:

```python
@_skip_no_ephe
class TestCategoryTags:
    """Every contribution must have a valid category tag."""

    def test_all_western_have_category(self):
        r = client.post("/calculate/fusion", json=PAYLOAD)
        data = r.json()
        for entry in data["contribution_ledger"]["western"]:
            assert "category" in entry
            assert entry["category"] in ("traditional", "modern_heuristic", "experimental")

    def test_all_bazi_have_category(self):
        r = client.post("/calculate/fusion", json=PAYLOAD)
        data = r.json()
        for entry in data["contribution_ledger"]["bazi"]:
            assert "category" in entry
            assert entry["category"] == "traditional"  # all BaZi is traditional

    def test_sun_moon_are_traditional(self):
        r = client.post("/calculate/fusion", json=PAYLOAD)
        data = r.json()
        for entry in data["contribution_ledger"]["western"]:
            if entry["planet"] in ("Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn"):
                assert entry["category"] == "traditional"

    def test_uranus_neptune_pluto_are_modern(self):
        r = client.post("/calculate/fusion", json=PAYLOAD)
        data = r.json()
        for entry in data["contribution_ledger"]["western"]:
            if entry["planet"] in ("Uranus", "Neptune", "Pluto"):
                assert entry["category"] == "modern_heuristic"

    def test_nodes_lilith_are_experimental(self):
        r = client.post("/calculate/fusion", json=PAYLOAD)
        data = r.json()
        for entry in data["contribution_ledger"]["western"]:
            if entry["planet"] in ("Chiron", "Lilith", "NorthNode", "TrueNorthNode"):
                assert entry["category"] == "experimental"
```

**Step 2: Run tests**

Run: `python -c "import pytest; pytest.main(['-v', 'tests/test_contribution_ledger.py::TestCategoryTags'])"`
Expected: These should PASS if Task 1+2 already added category. If not, they'll fail and drive implementation.

**Step 3: Commit**

```bash
git add tests/test_contribution_ledger.py
git commit -m "test: add category tag validation tests"
```

NOTE: If categories were already implemented in Tasks 1+2 (they should be), these tests just validate the correctness. If any fail, fix the category assignments in `calculate_wuxing_vector_from_planets_with_ledger`.

---

## Task 6: H_calibrated in Standard Output (3.6)

H_calibrated alongside H_raw in standard response with quality metadata and interpretation band.

---

### Task 6.1: Write failing tests for H_calibrated

**Files:**
- Create: `tests/test_h_calibrated.py`

**Step 1: Write the test file**

```python
"""Tests: H_calibrated in /calculate/fusion standard response."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from bazi_engine.app import app

client = TestClient(app)

PAYLOAD = {
    "date": "2024-02-10T14:30:00",
    "tz": "Europe/Berlin",
    "lon": 13.405,
    "lat": 52.52,
}


def _ephemeris_available() -> bool:
    r = client.post("/calculate/fusion", json=PAYLOAD)
    return r.status_code == 200


_HAS_EPHEMERIS = _ephemeris_available()
_skip_no_ephe = pytest.mark.skipif(
    not _HAS_EPHEMERIS,
    reason="Swiss Ephemeris files not available",
)


@_skip_no_ephe
class TestHCalibrated:
    """H_calibrated must be in fusion response alongside H_raw."""

    def test_calibration_key_exists(self):
        r = client.post("/calculate/fusion", json=PAYLOAD)
        assert r.status_code == 200
        data = r.json()
        assert "calibration" in data

    def test_calibration_structure(self):
        r = client.post("/calculate/fusion", json=PAYLOAD)
        data = r.json()
        cal = data["calibration"]
        assert "h_raw" in cal
        assert "h_calibrated" in cal
        assert "h_baseline" in cal
        assert "h_sigma" in cal
        assert "sigma_above" in cal
        assert "quality" in cal
        assert "interpretation_band" in cal

    def test_h_calibrated_in_0_1_range(self):
        r = client.post("/calculate/fusion", json=PAYLOAD)
        data = r.json()
        h_cal = data["calibration"]["h_calibrated"]
        assert 0.0 <= h_cal <= 1.0

    def test_quality_is_valid_flag(self):
        r = client.post("/calculate/fusion", json=PAYLOAD)
        data = r.json()
        assert data["calibration"]["quality"] in ("ok", "sparse", "degenerate")

    def test_interpretation_band_present(self):
        r = client.post("/calculate/fusion", json=PAYLOAD)
        data = r.json()
        band = data["calibration"]["interpretation_band"]
        assert isinstance(band, str)
        assert len(band) > 0
```

**Step 2: Run tests**

Run: `python -c "import pytest; pytest.main(['-v', 'tests/test_h_calibrated.py'])"`
Expected: FAIL — no `calibration` key in fusion response

**Step 3: Commit**

```bash
git add tests/test_h_calibrated.py
git commit -m "test: add H_calibrated tests (red)"
```

---

### Task 6.2: Wire H_calibrated into fusion response

**Files:**
- Modify: `bazi_engine/fusion.py:72-127` (call calibrate_harmony, include result)
- Modify: `bazi_engine/routers/fusion.py` (add calibration field to FusionResponse)

**Step 1: Import calibrate_harmony in fusion.py**

```python
from .wuxing.calibration import calibrate_harmony
```

**Step 2: Call calibrate_harmony in compute_fusion_analysis**

After computing harmony:
```python
harmony = calculate_harmony_index(western_wuxing, bazi_wuxing)

cal = calibrate_harmony(
    h_raw=harmony["harmony_index"],
    western_bodies=western_bodies,
    bazi_pillars=bazi_pillars,
    western_vector=western_wuxing,
    bazi_vector=bazi_wuxing,
)

calibration_dict = {
    "h_raw": cal.h_raw,
    "h_calibrated": cal.h_calibrated,
    "h_baseline": cal.h_baseline,
    "h_sigma": cal.h_sigma,
    "sigma_above": cal.sigma_above,
    "quality": cal.quality,
    "interpretation_band": cal.interpretation_band,
    "n_west": cal.n_west,
    "n_bazi_contributions": cal.n_bazi_contributions,
}
```

Add `"calibration": calibration_dict` to the returned dict.

**Step 3: Add calibration to FusionResponse**

In `routers/fusion.py`:
```python
calibration: Optional[Dict[str, Any]] = None
```

Pass `fusion["calibration"]` through in the endpoint.

**Step 4: Run tests**

Run: `python -c "import pytest; pytest.main(['-v', 'tests/test_h_calibrated.py'])"`
Expected: ALL PASS

**Step 5: Run full test suite**

Run: `python -c "import pytest; pytest.main(['-q', 'tests/'])"`
Expected: ALL PASS

**Step 6: Commit**

```bash
git add bazi_engine/fusion.py bazi_engine/routers/fusion.py
git commit -m "feat: add H_calibrated with quality metadata to fusion standard response"
```

---

## Task 7: Regenerate OpenAPI + Snapshots + Final Verification

---

### Task 7.1: Regenerate OpenAPI spec

**Files:**
- Regenerate: `spec/openapi/openapi.json`

**Step 1: Regenerate**

Run: `python scripts/export_openapi.py`

**Step 2: Verify no drift**

Run: `python scripts/export_openapi.py --check`
Expected: OK

**Step 3: Regenerate snapshots**

Run: `UPDATE_SNAPSHOTS=1 python -c "import pytest; pytest.main(['-q', 'tests/test_snapshot_stability.py'])"`

**Step 4: Run full test suite**

Run: `python -c "import pytest; pytest.main(['-q', 'tests/'])"`
Expected: ALL PASS, 0 failures

**Step 5: Commit**

```bash
git add spec/openapi/openapi.json tests/snapshots/
git commit -m "chore: regenerate OpenAPI spec and snapshots for Sprint 3 changes"
```

---

## Sprint 3 Definition of Done

- [ ] Per-planet contribution ledger (element, weight, retrograde, rationale) in `/calculate/fusion` and `/calculate/wuxing`
- [ ] Per-pillar BaZi contribution ledger (stem, hidden_main/middle/residual with Qi weights) in `/calculate/fusion`
- [ ] Mercury day/night quality flag (`exact`/`assumed_day`) — no silent default
- [ ] All magic numbers in versionable `parameter_set` in provenance
- [ ] Every contribution tagged `traditional | modern_heuristic | experimental`
- [ ] `H_calibrated` alongside `H_raw` in fusion response with `quality`, `h_baseline`, `sigma_above`, `interpretation_band`
- [ ] All tests pass (0 failures)
- [ ] OpenAPI spec in sync
- [ ] No breaking changes to existing response structures (additive only)
