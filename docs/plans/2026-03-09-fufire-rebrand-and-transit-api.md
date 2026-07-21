# FuFirE Rebranding + Transit API Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Rebrand BAFE to FuFirE (string literals only, no package rename) and build four new transit API endpoints powered by real Swiss Ephemeris data.

**Architecture:** The Python package stays `bazi_engine`. Only user-facing strings change (FastAPI title, /health, log messages, docs). Transit endpoints are a new router (`bazi_engine/routers/transit.py`) using existing `swisseph` + `ephemeris.py` infrastructure. Cache via `cachetools.TTLCache`. History store deferred to Phase B (Supabase).

**Tech Stack:** Python 3.10+, FastAPI, pyswisseph, cachetools, pytest, httpx

**Source Documents:**
- `spec/FuFirE_Rebranding_Dev_Brief_v1.md` (Phase 1 tasks R-01..R-12)
- `spec/FuFirE_Product_Roadmap_v1.md` (P0..P2 work packages)
- `spec/FuFirE_Addendum_v1.md` (ADR-1..7, corrections, GDPR)

**ADRs in effect (from Addendum):**
- ADR-1: Cache = `cachetools.TTLCache` (in-memory)
- ADR-2: History store = Supabase (deferred to later task)
- ADR-3: Narrative = sync template always, async Gemini optional
- ADR-4: `bazi_engine/bafe/` directory NOT renamed
- ADR-5: `/calculate/fusion` gets optional `correlations` field (null default)
- ADR-6: Feature flag `VITE_USE_REAL_TRANSITS` for frontend
- ADR-7: Static OG:image placeholder, no Puppeteer

---

## Iteration 1: Rebranding (R-02, R-05, R-07)

Engine-side rebranding. No feature changes. All existing tests must stay green.

---

### Task 1: Add rebranding regression test

**Files:**
- Create: `tests/test_rebrand.py`

**Step 1: Write the test file**

```python
"""Regression tests: FuFirE rebranding strings are correct."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from bazi_engine.app import app

client = TestClient(app)


class TestFuFireBranding:
    """Every user-facing string says FuFirE, not BAFE or bazi_engine_v2."""

    def test_root_service_name(self):
        r = client.get("/")
        assert r.status_code == 200
        data = r.json()
        assert data["service"] == "fufire"

    def test_health_returns_engine_name(self):
        r = client.get("/health")
        assert r.status_code == 200
        data = r.json()
        assert data["engine"] == "FuFirE"
        assert "version" in data

    def test_openapi_title_is_fufire(self):
        r = client.get("/openapi.json")
        assert r.status_code == 200
        data = r.json()
        assert "FuFirE" in data["info"]["title"]

    def test_openapi_description_mentions_fufire(self):
        r = client.get("/openapi.json")
        data = r.json()
        assert "FuFirE" in data["info"]["description"]
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/benjaminpoersch/Projects/SaaS/FuFirE/BAFE && python -m pytest tests/test_rebrand.py -v`
Expected: FAIL — `"bazi_engine_v2" != "fufire"`, missing `engine` key in /health, title says "BaZi Engine"

**Step 3: Commit the failing tests**

```bash
git add tests/test_rebrand.py
git commit -m "test: add FuFirE rebranding regression tests (red)"
```

---

### Task 2: Rebrand FastAPI app metadata

**Files:**
- Modify: `bazi_engine/app.py:22` (lifespan log message)
- Modify: `bazi_engine/app.py:26-28` (title, description)

**Step 1: Update app.py**

In `bazi_engine/app.py`, change:

```python
# Line 22: lifespan log
logging.getLogger("uvicorn").info(f"BAFE starting: {__version__}")
```
to:
```python
logging.getLogger("uvicorn").info(f"FuFirE starting: {__version__}")
```

```python
# Lines 26-28: FastAPI constructor
app = FastAPI(
    title="BaZi Engine v2 API",
    description="API for BaZi (Chinese Astrology) and Basic Western Astrology calculations.",
```
to:
```python
app = FastAPI(
    title="FuFirE — Fusion Firmament Engine",
    description="FuFirE: Deterministic astronomical calculation engine for BaZi (Chinese Astrology) and Western Astrology with Wu-Xing fusion.",
```

**Step 2: Run existing tests to check nothing breaks**

Run: `python -m pytest tests/test_endpoints.py -v -k "openapi or health or root or build"`
Expected: Some tests may need updating (see Task 3)

---

### Task 3: Rebrand info router responses

**Files:**
- Modify: `bazi_engine/routers/info.py:73` (root endpoint service name)
- Modify: `bazi_engine/routers/info.py:76-78` (health endpoint)

**Step 1: Update root endpoint**

In `bazi_engine/routers/info.py`, change line 73:

```python
return {"status": "ok", "service": "bazi_engine_v2", **_build_metadata()}
```
to:
```python
return {"status": "ok", "service": "fufire", **_build_metadata()}
```

**Step 2: Update health endpoint to include engine name and version**

Change the HealthResponse model (line 37-38):

```python
class HealthResponse(BaseModel):
    status: str
```
to:
```python
class HealthResponse(BaseModel):
    status: str
    engine: str = "FuFirE"
    version: str = ""
```

Change the health endpoint (lines 76-78):

```python
@router.get("/health", response_model=HealthResponse)
def health_check() -> Dict[str, str]:
    return {"status": "healthy"}
```
to:
```python
@router.get("/health", response_model=HealthResponse)
def health_check() -> Dict[str, Any]:
    return {"status": "healthy", "engine": "FuFirE", "version": _ENGINE_VERSION}
```

**Step 3: Run the rebranding tests**

Run: `python -m pytest tests/test_rebrand.py -v`
Expected: ALL PASS

**Step 4: Fix any broken existing tests**

The existing test `test_root_returns_ok` in `tests/test_endpoints.py` checks `data["status"] == "ok"` and `"service" in data` — this still passes.

The `test_health_returns_healthy` checks `r.json()["status"] == "healthy"` — still passes (field still present).

Run: `python -m pytest tests/test_endpoints.py -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add bazi_engine/app.py bazi_engine/routers/info.py
git commit -m "refactor: rebrand user-facing strings BAFE → FuFirE (ADR-4)"
```

---

### Task 4: Regenerate OpenAPI spec and verify

**Files:**
- Regenerate: `spec/openapi/openapi.json`

**Step 1: Regenerate**

Run: `cd /Users/benjaminpoersch/Projects/SaaS/FuFirE/BAFE && python scripts/export_openapi.py`
Expected: File updated with new title/description

**Step 2: Verify no drift**

Run: `python scripts/export_openapi.py --check`
Expected: PASS (no drift)

**Step 3: Run full test suite**

Run: `python -m pytest -q`
Expected: ALL PASS

**Step 4: Commit**

```bash
git add spec/openapi/openapi.json
git commit -m "chore: regenerate OpenAPI spec with FuFirE branding"
```

---

## Iteration 2: Transit Now Endpoint (T-01)

The foundation: real-time planetary positions via Swiss Ephemeris.

---

### Task 5: Add `cachetools` dependency

**Files:**
- Modify: `pyproject.toml`

**Step 1: Add cachetools to dependencies**

In `pyproject.toml`, in the `dependencies` list, add:

```
"cachetools>=5.3.0",
```

**Step 2: Install**

Run: `cd /Users/benjaminpoersch/Projects/SaaS/FuFirE/BAFE && pip install -e ".[dev]"`
Expected: cachetools installed

**Step 3: Commit**

```bash
git add pyproject.toml
git commit -m "deps: add cachetools for transit cache (ADR-1)"
```

---

### Task 6: Write failing tests for /transit/now

**Files:**
- Create: `tests/test_transit.py`

**Step 1: Write the test file**

```python
"""Tests for transit API endpoints."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch
from datetime import datetime, timezone

from bazi_engine.app import app

client = TestClient(app)

# Known planetary longitudes for a fixed date (mock data).
# We mock swe.calc_ut to return deterministic values.
MOCK_PLANET_DATA = {
    # (longitude, latitude, distance, speed_lon, speed_lat, speed_dist)
    0: (348.7, 0.0, 1.0, 1.01, 0.0, 0.0),   # Sun
    1: (187.2, 0.0, 0.003, 13.2, 0.0, 0.0),  # Moon
    2: (332.1, 0.0, 0.8, 1.8, 0.0, 0.0),     # Mercury
    3: (15.4, 0.0, 0.7, 1.2, 0.0, 0.0),      # Venus
    4: (112.8, 0.0, 1.5, 0.7, 0.0, 0.0),     # Mars
    5: (78.3, 0.0, 5.0, 0.08, 0.0, 0.0),     # Jupiter
    6: (342.9, 0.0, 9.5, 0.03, 0.0, 0.0),    # Saturn
}

ZODIAC_SIGNS = [
    "aries", "taurus", "gemini", "cancer", "leo", "virgo",
    "libra", "scorpio", "sagittarius", "capricorn", "aquarius", "pisces",
]


def mock_calc_ut(jd_ut, planet_id, flags):
    """Mock swe.calc_ut to return deterministic planet positions."""
    if planet_id in MOCK_PLANET_DATA:
        data = MOCK_PLANET_DATA[planet_id]
        return data, 0
    raise Exception(f"Unknown planet {planet_id}")


class TestTransitNow:
    """GET /transit/now — current planetary positions."""

    def test_returns_200(self):
        with patch("bazi_engine.transit.swe.calc_ut", side_effect=mock_calc_ut):
            r = client.get("/transit/now")
        assert r.status_code == 200

    def test_response_has_required_fields(self):
        with patch("bazi_engine.transit.swe.calc_ut", side_effect=mock_calc_ut):
            r = client.get("/transit/now")
        data = r.json()
        assert "computed_at" in data
        assert "planets" in data
        assert "sector_intensity" in data

    def test_planets_have_required_fields(self):
        with patch("bazi_engine.transit.swe.calc_ut", side_effect=mock_calc_ut):
            r = client.get("/transit/now")
        data = r.json()
        planets = data["planets"]
        required_planets = ["sun", "moon", "mercury", "venus", "mars", "jupiter", "saturn"]
        for name in required_planets:
            assert name in planets, f"Missing planet: {name}"
            p = planets[name]
            assert "longitude" in p
            assert "sector" in p
            assert "sign" in p
            assert "speed" in p

    def test_sector_is_longitude_divided_by_30(self):
        with patch("bazi_engine.transit.swe.calc_ut", side_effect=mock_calc_ut):
            r = client.get("/transit/now")
        data = r.json()
        sun = data["planets"]["sun"]
        # Sun at 348.7° → sector 11 (348.7 / 30 = 11.6)
        assert sun["sector"] == 11
        assert sun["sign"] == "pisces"

    def test_sector_intensity_has_12_elements(self):
        with patch("bazi_engine.transit.swe.calc_ut", side_effect=mock_calc_ut):
            r = client.get("/transit/now")
        data = r.json()
        assert len(data["sector_intensity"]) == 12

    def test_accepts_optional_datetime_param(self):
        with patch("bazi_engine.transit.swe.calc_ut", side_effect=mock_calc_ut):
            r = client.get("/transit/now?datetime=2026-03-09T12:00:00Z")
        assert r.status_code == 200

    def test_computed_at_is_iso_format(self):
        with patch("bazi_engine.transit.swe.calc_ut", side_effect=mock_calc_ut):
            r = client.get("/transit/now")
        data = r.json()
        # Should parse as ISO datetime
        dt = datetime.fromisoformat(data["computed_at"].replace("Z", "+00:00"))
        assert dt.tzinfo is not None
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_transit.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'bazi_engine.transit'`

**Step 3: Commit failing tests**

```bash
git add tests/test_transit.py
git commit -m "test: add /transit/now endpoint tests (red)"
```

---

### Task 7: Implement transit module

**Files:**
- Create: `bazi_engine/transit.py`

This module computes real-time planetary positions. It reuses the same `swisseph` library already used in `western.py` but for arbitrary timestamps (not just birth charts).

**Step 1: Write the transit module**

```python
"""
transit.py — Real-time planetary transit calculations.

Computes current planetary positions using Swiss Ephemeris.
Cached per hour (ADR-1: cachetools.TTLCache).
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import swisseph as swe
from cachetools import TTLCache

from .ephemeris import SwissEphBackend, datetime_utc_to_jd_ut

# Planet IDs for transit calculation (7 classical + Sun/Moon)
TRANSIT_PLANETS = {
    "sun": swe.SUN,
    "moon": swe.MOON,
    "mercury": swe.MERCURY,
    "venus": swe.VENUS,
    "mars": swe.MARS,
    "jupiter": swe.JUPITER,
    "saturn": swe.SATURN,
}

ZODIAC_SIGNS = [
    "aries", "taurus", "gemini", "cancer", "leo", "virgo",
    "libra", "scorpio", "sagittarius", "capricorn", "aquarius", "pisces",
]

# Planet weights for sector intensity calculation.
# Outer planets move slower → higher weight per sector presence.
PLANET_WEIGHTS = {
    "sun": 1.0,
    "moon": 0.5,
    "mercury": 0.6,
    "venus": 0.7,
    "mars": 0.8,
    "jupiter": 1.2,
    "saturn": 1.5,
}

# Cache: 1 hour TTL, max 64 entries (keyed by truncated hour)
_transit_cache: TTLCache = TTLCache(maxsize=64, ttl=3600)


def _cache_key(dt: datetime) -> str:
    """Truncate to hour for cache key."""
    return dt.strftime("%Y-%m-%dT%H")


def compute_transit_now(
    dt_utc: Optional[datetime] = None,
    ephe_path: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Compute current planetary positions.

    Args:
        dt_utc: UTC datetime (default: now)
        ephe_path: Swiss Ephemeris file path override

    Returns:
        Dict with computed_at, planets, sector_intensity
    """
    if dt_utc is None:
        dt_utc = datetime.now(timezone.utc)

    key = _cache_key(dt_utc)
    if key in _transit_cache:
        return _transit_cache[key]

    backend = SwissEphBackend(ephe_path=ephe_path)
    jd_ut = datetime_utc_to_jd_ut(dt_utc)
    flags = backend.flags | swe.FLG_SPEED

    planets: Dict[str, Dict[str, Any]] = {}

    for name, pid in TRANSIT_PLANETS.items():
        (lon_deg, _lat, _dist, speed_lon, _, _), _ret = swe.calc_ut(jd_ut, pid, flags)
        sector = int(lon_deg // 30)
        planets[name] = {
            "longitude": round(lon_deg, 1),
            "sector": sector,
            "sign": ZODIAC_SIGNS[sector],
            "speed": round(speed_lon, 2),
        }

    # Sector intensity: weighted sum of planet presence per sector
    sector_intensity = [0.0] * 12
    for name, pdata in planets.items():
        weight = PLANET_WEIGHTS.get(name, 1.0)
        sector_intensity[pdata["sector"]] += weight

    # Normalize to 0-1 range
    max_val = max(sector_intensity) if max(sector_intensity) > 0 else 1.0
    sector_intensity = [round(v / max_val, 2) for v in sector_intensity]

    result = {
        "computed_at": dt_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "planets": planets,
        "sector_intensity": sector_intensity,
    }

    _transit_cache[key] = result
    return result
```

**Step 2: Run transit tests**

Run: `python -m pytest tests/test_transit.py -v`
Expected: Still FAIL — router not yet registered

---

### Task 8: Create transit router and register it

**Files:**
- Create: `bazi_engine/routers/transit.py`
- Modify: `bazi_engine/app.py:16` (import) and `bazi_engine/app.py:62` (include router)

**Step 1: Create the router**

```python
"""
routers/transit.py — Transit API endpoints.

GET /transit/now — Current planetary positions.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, Query

from ..transit import compute_transit_now

router = APIRouter(prefix="/transit", tags=["Transit"])


@router.get("/now")
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
        dt_utc = datetime.fromisoformat(
            datetime_param.replace("Z", "+00:00")
        ).astimezone(timezone.utc)
    return compute_transit_now(dt_utc=dt_utc)
```

**Step 2: Register router in app.py**

In `bazi_engine/app.py`, add to the imports (line 16):

```python
from .routers import info, bazi, western, fusion, validate, chart, webhooks, transit
```

Add after line 62:

```python
app.include_router(transit.router)
```

**Step 3: Run transit tests**

Run: `python -m pytest tests/test_transit.py -v`
Expected: ALL PASS (with mocked swe.calc_ut)

**Step 4: Run full test suite**

Run: `python -m pytest -q`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add bazi_engine/transit.py bazi_engine/routers/transit.py bazi_engine/app.py
git commit -m "feat: add /transit/now endpoint with real Swiss Ephemeris positions (T-01)"
```

---

## Iteration 3: Transit State Endpoint (T-02)

Personalized transit calculation: takes user's soulprint + quiz vectors, combines with current transits.

---

### Task 9: Write failing tests for /transit/state

**Files:**
- Modify: `tests/test_transit.py` (add new test class)

**Step 1: Add tests to test_transit.py**

Append to `tests/test_transit.py`:

```python
class TestTransitState:
    """POST /transit/state — personalized transit calculation."""

    SAMPLE_SOULPRINT = [0.42, 0.31, 0.55, 0.67, 0.28, 0.19, 0.48, 0.35, 0.22, 0.15, 0.20, 0.61]
    SAMPLE_QUIZ = [0.30, 0.25, 0.40, 0.35, 0.20, 0.15, 0.50, 0.30, 0.18, 0.10, 0.22, 0.45]

    def test_returns_200(self):
        with patch("bazi_engine.transit.swe.calc_ut", side_effect=mock_calc_ut):
            r = client.post("/transit/state", json={
                "soulprint_sectors": self.SAMPLE_SOULPRINT,
                "quiz_sectors": self.SAMPLE_QUIZ,
            })
        assert r.status_code == 200

    def test_response_has_schema_field(self):
        with patch("bazi_engine.transit.swe.calc_ut", side_effect=mock_calc_ut):
            r = client.post("/transit/state", json={
                "soulprint_sectors": self.SAMPLE_SOULPRINT,
                "quiz_sectors": self.SAMPLE_QUIZ,
            })
        data = r.json()
        assert data["schema"] == "TRANSIT_STATE_v1"

    def test_response_has_ring_sectors(self):
        with patch("bazi_engine.transit.swe.calc_ut", side_effect=mock_calc_ut):
            r = client.post("/transit/state", json={
                "soulprint_sectors": self.SAMPLE_SOULPRINT,
                "quiz_sectors": self.SAMPLE_QUIZ,
            })
        data = r.json()
        assert "ring" in data
        assert len(data["ring"]["sectors"]) == 12

    def test_response_has_transit_contribution(self):
        with patch("bazi_engine.transit.swe.calc_ut", side_effect=mock_calc_ut):
            r = client.post("/transit/state", json={
                "soulprint_sectors": self.SAMPLE_SOULPRINT,
                "quiz_sectors": self.SAMPLE_QUIZ,
            })
        data = r.json()
        assert "transit_contribution" in data
        assert len(data["transit_contribution"]["sectors"]) == 12
        assert "transit_intensity" in data["transit_contribution"]

    def test_response_has_delta_with_null_30day(self):
        """Before history store exists, vs_30day_avg should be null."""
        with patch("bazi_engine.transit.swe.calc_ut", side_effect=mock_calc_ut):
            r = client.post("/transit/state", json={
                "soulprint_sectors": self.SAMPLE_SOULPRINT,
                "quiz_sectors": self.SAMPLE_QUIZ,
            })
        data = r.json()
        assert "delta" in data
        assert data["delta"]["vs_30day_avg"] is None

    def test_validates_sector_array_length(self):
        """Must reject arrays that aren't exactly 12 elements."""
        r = client.post("/transit/state", json={
            "soulprint_sectors": [0.1, 0.2],  # too short
            "quiz_sectors": self.SAMPLE_QUIZ,
        })
        assert r.status_code == 422

    def test_events_is_list(self):
        with patch("bazi_engine.transit.swe.calc_ut", side_effect=mock_calc_ut):
            r = client.post("/transit/state", json={
                "soulprint_sectors": self.SAMPLE_SOULPRINT,
                "quiz_sectors": self.SAMPLE_QUIZ,
            })
        data = r.json()
        assert isinstance(data.get("events"), list)
```

**Step 2: Run to verify failure**

Run: `python -m pytest tests/test_transit.py::TestTransitState -v`
Expected: FAIL — 404 (endpoint doesn't exist yet)

**Step 3: Commit**

```bash
git add tests/test_transit.py
git commit -m "test: add /transit/state endpoint tests (red)"
```

---

### Task 10: Implement transit state computation

**Files:**
- Modify: `bazi_engine/transit.py` (add compute_transit_state function)

**Step 1: Add to bazi_engine/transit.py**

Append the following to `bazi_engine/transit.py`:

```python
def compute_transit_state(
    soulprint_sectors: List[float],
    quiz_sectors: List[float],
    dt_utc: Optional[datetime] = None,
    ephe_path: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Compute personalized transit state.

    Combines current planetary transits with user's soulprint and quiz vectors
    to produce a personal impact assessment.

    Args:
        soulprint_sectors: 12-element user soulprint vector
        quiz_sectors: 12-element quiz result vector
        dt_utc: UTC datetime (default: now)

    Returns:
        Transit State JSON conforming to TRANSIT_STATE_v1 schema
    """
    transit_now = compute_transit_now(dt_utc=dt_utc, ephe_path=ephe_path)
    if dt_utc is None:
        dt_utc = datetime.now(timezone.utc)

    # Transit contribution per sector: weighted planet presence
    transit_sectors = transit_now["sector_intensity"]

    # Personal impact: transit_strength × (soulprint + quiz)
    impact = [0.0] * 12
    for s in range(12):
        personal = soulprint_sectors[s] + quiz_sectors[s]
        impact[s] = round(transit_sectors[s] * personal, 2)

    # Transit intensity: mean of non-zero impacts
    non_zero = [v for v in impact if v > 0]
    transit_intensity = round(sum(non_zero) / len(non_zero), 2) if non_zero else 0.0

    # Ring sectors: soulprint + quiz + transit contribution
    ring_sectors = [
        round(soulprint_sectors[s] + quiz_sectors[s] * 0.5 + impact[s] * 0.3, 2)
        for s in range(12)
    ]

    # Detect events
    events = _detect_events(transit_now, soulprint_sectors, impact)

    return {
        "schema": "TRANSIT_STATE_v1",
        "generated_at": dt_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "ring": {"sectors": ring_sectors},
        "transit_contribution": {
            "sectors": [round(v, 2) for v in transit_sectors],
            "transit_intensity": transit_intensity,
        },
        "delta": {
            "vs_previous": None,  # In-memory delta computed when history available
            "vs_30day_avg": None,  # Null until history store exists (ADR-2, Addendum 3.4)
        },
        "events": events,
    }


def _detect_events(
    transit_now: Dict[str, Any],
    soulprint: List[float],
    impact: List[float],
) -> List[Dict[str, Any]]:
    """
    Detect transit events: resonance jumps, dominance shifts.

    Returns list of event dicts.
    """
    events: List[Dict[str, Any]] = []

    # Find peak soulprint sector
    peak_sector = max(range(12), key=lambda s: soulprint[s])

    # Check each planet: if it sits on or near the user's peak sector
    for name, pdata in transit_now["planets"].items():
        sector = pdata["sector"]
        if sector == peak_sector and impact[sector] >= 0.18:
            events.append({
                "type": "resonance_jump",
                "priority": 1,
                "sector": sector,
                "trigger_planet": name,
                "description_de": f"{name.capitalize()} aktiviert dein {ZODIAC_SIGNS[sector].capitalize()}-Feld",
                "personal_context": f"Dein stärkstes Feld wird von {name.capitalize()} berührt",
            })

    # Moon event: if moon is on a high-impact sector
    moon_sector = transit_now["planets"]["moon"]["sector"]
    if impact[moon_sector] >= 0.5:
        events.append({
            "type": "moon_event",
            "priority": 2,
            "sector": moon_sector,
            "trigger_planet": "moon",
            "description_de": f"Mond verstärkt dein {ZODIAC_SIGNS[moon_sector].capitalize()}-Feld",
            "personal_context": "Emotionale Resonanz heute besonders stark",
        })

    return events
```

**Step 2: Run transit state tests**

Run: `python -m pytest tests/test_transit.py::TestTransitState -v`
Expected: Still FAIL — router endpoint not added yet

---

### Task 11: Add /transit/state router endpoint

**Files:**
- Modify: `bazi_engine/routers/transit.py`

**Step 1: Add Pydantic model and endpoint**

Replace `bazi_engine/routers/transit.py` with:

```python
"""
routers/transit.py — Transit API endpoints.

GET  /transit/now   — Current planetary positions.
POST /transit/state — Personalized transit state.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field, field_validator

from ..transit import compute_transit_now, compute_transit_state

router = APIRouter(prefix="/transit", tags=["Transit"])


@router.get("/now")
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
        dt_utc = datetime.fromisoformat(
            datetime_param.replace("Z", "+00:00")
        ).astimezone(timezone.utc)
    return compute_transit_now(dt_utc=dt_utc)


class TransitStateRequest(BaseModel):
    soulprint_sectors: List[float] = Field(..., min_length=12, max_length=12)
    quiz_sectors: List[float] = Field(..., min_length=12, max_length=12)

    @field_validator("soulprint_sectors", "quiz_sectors")
    @classmethod
    def validate_length(cls, v: List[float]) -> List[float]:
        if len(v) != 12:
            raise ValueError("Must have exactly 12 sectors")
        return v


@router.post("/state")
def transit_state(body: TransitStateRequest) -> Dict[str, Any]:
    """Personalized transit state combining current transits with user profile."""
    return compute_transit_state(
        soulprint_sectors=body.soulprint_sectors,
        quiz_sectors=body.quiz_sectors,
    )
```

**Step 2: Run tests**

Run: `python -m pytest tests/test_transit.py -v`
Expected: ALL PASS

**Step 3: Run full suite**

Run: `python -m pytest -q`
Expected: ALL PASS

**Step 4: Commit**

```bash
git add bazi_engine/transit.py bazi_engine/routers/transit.py
git commit -m "feat: add /transit/state endpoint with personalized transit computation (T-02)"
```

---

## Iteration 4: Transit Narrative Endpoint (T-04)

Template-based text generation. Sync always, no LLM in request path (ADR-3).

---

### Task 12: Write failing tests for /transit/narrative

**Files:**
- Modify: `tests/test_transit.py`

**Step 1: Add test class**

Append to `tests/test_transit.py`:

```python
class TestTransitNarrative:
    """POST /transit/narrative — text generation from transit state."""

    SAMPLE_STATE = {
        "schema": "TRANSIT_STATE_v1",
        "generated_at": "2026-03-09T06:00:00Z",
        "ring": {"sectors": [0.42, 0.31, 0.55, 0.67, 0.28, 0.19, 0.48, 0.35, 0.22, 0.15, 0.20, 0.61]},
        "transit_contribution": {
            "sectors": [0.02, 0.01, 0.05, 0.08, 0.01, 0.0, 0.12, 0.03, 0.01, 0.0, 0.01, 0.15],
            "transit_intensity": 0.42,
        },
        "delta": {"vs_previous": None, "vs_30day_avg": None},
        "events": [
            {
                "type": "resonance_jump",
                "priority": 1,
                "sector": 11,
                "trigger_planet": "saturn",
                "description_de": "Saturn aktiviert dein Fische-Feld",
                "personal_context": "Dein stärkstes Feld wird von Saturn berührt",
            }
        ],
    }

    def test_returns_200(self):
        r = client.post("/transit/narrative", json={"transit_state": self.SAMPLE_STATE})
        assert r.status_code == 200

    def test_response_has_headline_and_body(self):
        r = client.post("/transit/narrative", json={"transit_state": self.SAMPLE_STATE})
        data = r.json()
        assert "headline" in data
        assert "body" in data
        assert "advice" in data
        assert isinstance(data["pushworthy"], bool)

    def test_narrative_uses_event_data(self):
        r = client.post("/transit/narrative", json={"transit_state": self.SAMPLE_STATE})
        data = r.json()
        # Headline should reference the event's planet
        assert len(data["headline"]) > 0
        assert len(data["body"]) > 0

    def test_no_events_still_generates_text(self):
        state = {**self.SAMPLE_STATE, "events": []}
        r = client.post("/transit/narrative", json={"transit_state": state})
        assert r.status_code == 200
        data = r.json()
        assert len(data["headline"]) > 0
        assert data["pushworthy"] is False
```

**Step 2: Run to verify failure**

Run: `python -m pytest tests/test_transit.py::TestTransitNarrative -v`
Expected: FAIL — 404/405

**Step 3: Commit**

```bash
git add tests/test_transit.py
git commit -m "test: add /transit/narrative endpoint tests (red)"
```

---

### Task 13: Implement narrative template engine

**Files:**
- Create: `bazi_engine/narrative.py`

**Step 1: Write the narrative module**

```python
"""
narrative.py — Template-based transit narrative generation.

ADR-3: Sync template always. No LLM in request path.
Gemini async enrichment is a future enhancement.
"""
from __future__ import annotations

from typing import Any, Dict, List

# German narrative templates keyed by event type
_TEMPLATES = {
    "resonance_jump": {
        "headline": "{planet} trifft dein {sign}-Feld",
        "body": (
            "{planet} steht aktuell in deinem Sektor {sector} ({sign}). "
            "Das ist einer deiner stärksten Bereiche — {personal_context}. "
            "Diese Konstellation bringt Energie und Aufmerksamkeit in dieses Feld."
        ),
        "advice": (
            "Nutze die {planet}-Energie heute bewusst. "
            "Dein {sign}-Feld ist aktiviert — ein guter Moment für Entscheidungen in diesem Bereich."
        ),
    },
    "moon_event": {
        "headline": "Mond-Resonanz in deinem {sign}-Feld",
        "body": (
            "Der Mond durchquert gerade deinen Sektor {sector} ({sign}). "
            "{personal_context}. "
            "Emotionale Themen in diesem Bereich treten heute stärker hervor."
        ),
        "advice": (
            "Achte heute besonders auf deine emotionalen Reaktionen. "
            "Der Mond verstärkt die Sensibilität in deinem {sign}-Bereich."
        ),
    },
    "dominance_shift": {
        "headline": "Dein Schwerpunkt verschiebt sich",
        "body": (
            "Eine neue dominante Energie entsteht in Sektor {sector} ({sign}). "
            "{personal_context}."
        ),
        "advice": "Beobachte, welche neuen Themen sich heute zeigen.",
    },
}

_DEFAULT_TEMPLATE = {
    "headline": "Dein kosmisches Wetter heute",
    "body": (
        "Die aktuelle Planetenkonstellation ist ruhig. "
        "Keine besonderen Transite aktivieren deine starken Felder. "
        "Ein guter Tag für Routine und Reflexion."
    ),
    "advice": "Nutze die Ruhe für innere Arbeit und Planung.",
}

ZODIAC_SIGNS_DE = {
    "aries": "Widder", "taurus": "Stier", "gemini": "Zwillinge",
    "cancer": "Krebs", "leo": "Löwe", "virgo": "Jungfrau",
    "libra": "Waage", "scorpio": "Skorpion", "sagittarius": "Schütze",
    "capricorn": "Steinbock", "aquarius": "Wassermann", "pisces": "Fische",
}

ZODIAC_SIGNS = [
    "aries", "taurus", "gemini", "cancer", "leo", "virgo",
    "libra", "scorpio", "sagittarius", "capricorn", "aquarius", "pisces",
]


def generate_narrative(transit_state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate narrative text from a transit state.

    Uses template engine (sync, <50ms).
    Returns headline, body, advice, pushworthy, push_text.
    """
    events: List[Dict[str, Any]] = transit_state.get("events", [])

    if not events:
        return {
            "headline": _DEFAULT_TEMPLATE["headline"],
            "body": _DEFAULT_TEMPLATE["body"],
            "advice": _DEFAULT_TEMPLATE["advice"],
            "pushworthy": False,
            "push_text": None,
        }

    # Use highest-priority event for narrative
    primary = sorted(events, key=lambda e: e.get("priority", 99))[0]
    event_type = primary.get("type", "")
    template = _TEMPLATES.get(event_type, _DEFAULT_TEMPLATE)

    sector = primary.get("sector", 0)
    sign_en = ZODIAC_SIGNS[sector] if 0 <= sector < 12 else "aries"
    sign_de = ZODIAC_SIGNS_DE.get(sign_en, sign_en)
    planet = primary.get("trigger_planet", "").capitalize()
    personal_context = primary.get("personal_context", "")

    fmt = {
        "planet": planet,
        "sign": sign_de,
        "sector": sector,
        "personal_context": personal_context,
    }

    headline = template["headline"].format(**fmt)
    body = template["body"].format(**fmt)
    advice = template["advice"].format(**fmt)

    pushworthy = primary.get("priority", 99) <= 1

    return {
        "headline": headline,
        "body": body,
        "advice": advice,
        "pushworthy": pushworthy,
        "push_text": headline if pushworthy else None,
    }
```

**Step 2: Add endpoint to transit router**

In `bazi_engine/routers/transit.py`, add import and endpoint:

Add to imports:
```python
from ..narrative import generate_narrative
```

Add endpoint:
```python
class NarrativeRequest(BaseModel):
    transit_state: Dict[str, Any]


@router.post("/narrative")
def transit_narrative(body: NarrativeRequest) -> Dict[str, Any]:
    """Generate narrative text from transit state. Template-based, <50ms."""
    return generate_narrative(body.transit_state)
```

**Step 3: Run tests**

Run: `python -m pytest tests/test_transit.py -v`
Expected: ALL PASS

**Step 4: Commit**

```bash
git add bazi_engine/narrative.py bazi_engine/routers/transit.py
git commit -m "feat: add /transit/narrative endpoint with template engine (T-04, ADR-3)"
```

---

## Iteration 5: Transit Timeline Endpoint (T-05)

Bulk pre-computation for 7/14/30 days.

---

### Task 14: Write failing tests for /transit/timeline

**Files:**
- Modify: `tests/test_transit.py`

**Step 1: Add test class**

Append to `tests/test_transit.py`:

```python
class TestTransitTimeline:
    """GET /transit/timeline — multi-day transit forecast."""

    def test_returns_200(self):
        with patch("bazi_engine.transit.swe.calc_ut", side_effect=mock_calc_ut):
            r = client.get("/transit/timeline?days=7")
        assert r.status_code == 200

    def test_default_is_7_days(self):
        with patch("bazi_engine.transit.swe.calc_ut", side_effect=mock_calc_ut):
            r = client.get("/transit/timeline")
        data = r.json()
        assert len(data["timeline"]) == 7

    def test_returns_requested_days(self):
        with patch("bazi_engine.transit.swe.calc_ut", side_effect=mock_calc_ut):
            r = client.get("/transit/timeline?days=14")
        data = r.json()
        assert len(data["timeline"]) == 14

    def test_each_day_has_planets_and_date(self):
        with patch("bazi_engine.transit.swe.calc_ut", side_effect=mock_calc_ut):
            r = client.get("/transit/timeline?days=3")
        data = r.json()
        for day in data["timeline"]:
            assert "date" in day
            assert "planets" in day
            assert "sector_intensity" in day

    def test_rejects_invalid_days(self):
        r = client.get("/transit/timeline?days=60")
        assert r.status_code == 422
```

**Step 2: Run to verify failure**

Run: `python -m pytest tests/test_transit.py::TestTransitTimeline -v`
Expected: FAIL — 404

**Step 3: Commit**

```bash
git add tests/test_transit.py
git commit -m "test: add /transit/timeline endpoint tests (red)"
```

---

### Task 15: Implement /transit/timeline

**Files:**
- Modify: `bazi_engine/transit.py` (add compute_transit_timeline)
- Modify: `bazi_engine/routers/transit.py` (add endpoint)

**Step 1: Add to bazi_engine/transit.py**

Append:

```python
# Timeline cache: 24h TTL (ADR-1), keyed by (start_date, days)
_timeline_cache: TTLCache = TTLCache(maxsize=16, ttl=86400)


def compute_transit_timeline(
    days: int = 7,
    start_utc: Optional[datetime] = None,
    ephe_path: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Compute transit positions for multiple days.

    Bulk computation using Swiss Ephemeris. Transits are the same for everyone —
    personalization happens client-side via the Masterformel.

    Args:
        days: Number of days (7, 14, or 30)
        start_utc: Start date (default: today at noon UTC)

    Returns:
        List of daily transit snapshots
    """
    if start_utc is None:
        now = datetime.now(timezone.utc)
        start_utc = now.replace(hour=12, minute=0, second=0, microsecond=0)

    cache_key = f"{start_utc.strftime('%Y-%m-%d')}:{days}"
    if cache_key in _timeline_cache:
        return _timeline_cache[cache_key]

    from datetime import timedelta

    timeline = []
    for d in range(days):
        dt = start_utc + timedelta(days=d)
        snap = compute_transit_now(dt_utc=dt, ephe_path=ephe_path)
        timeline.append({
            "date": dt.strftime("%Y-%m-%d"),
            "planets": snap["planets"],
            "sector_intensity": snap["sector_intensity"],
        })

    _timeline_cache[cache_key] = timeline
    return timeline
```

**Step 2: Add endpoint to router**

In `bazi_engine/routers/transit.py`, add:

```python
from ..transit import compute_transit_now, compute_transit_state, compute_transit_timeline
```

```python
@router.get("/timeline")
def transit_timeline(
    days: int = Query(7, ge=1, le=30, description="Number of days (1-30)"),
) -> Dict[str, Any]:
    """Multi-day transit forecast. Cached 24h. Not personalized."""
    return {"timeline": compute_transit_timeline(days=days)}
```

**Step 3: Run tests**

Run: `python -m pytest tests/test_transit.py -v`
Expected: ALL PASS

**Step 4: Run full suite**

Run: `python -m pytest -q`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add bazi_engine/transit.py bazi_engine/routers/transit.py
git commit -m "feat: add /transit/timeline endpoint for multi-day forecasts (T-05)"
```

---

## Iteration 6: OpenAPI + CI Verification

---

### Task 16: Regenerate OpenAPI and update CI

**Files:**
- Regenerate: `spec/openapi/openapi.json`
- Verify: `.github/workflows/ci.yml`

**Step 1: Regenerate OpenAPI**

Run: `python scripts/export_openapi.py`

**Step 2: Verify new endpoints appear**

Run: `python -c "import json; d=json.load(open('spec/openapi/openapi.json')); print([p for p in d['paths'] if 'transit' in p])"`
Expected: `['/transit/now', '/transit/state', '/transit/narrative', '/transit/timeline']`

**Step 3: Verify CI check passes**

Run: `python scripts/export_openapi.py --check`
Expected: PASS

**Step 4: Run full test suite one final time**

Run: `python -m pytest -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add spec/openapi/openapi.json
git commit -m "chore: regenerate OpenAPI spec with transit endpoints"
```

---

### Task 17: Add transit-specific golden test (validation against known positions)

**Files:**
- Create: `tests/test_transit_golden.py`

This test validates against known planetary positions. When Swiss Ephemeris is available, it verifies real calculations. When not (CI without SE files), it skips gracefully.

**Step 1: Write golden test**

```python
"""Golden vector tests for transit calculations.

Validates Swiss Ephemeris positions against known reference data.
Skips gracefully if SE files are not available.
"""
from __future__ import annotations

import os
import pytest
from datetime import datetime, timezone

# Skip entire module if no ephemeris files
pytestmark = pytest.mark.skipif(
    not os.environ.get("SE_EPHE_PATH"),
    reason="SE_EPHE_PATH not set — no ephemeris files available",
)


class TestTransitGoldenVectors:
    """Known planetary positions for specific dates.

    Reference: These values can be cross-checked against
    NASA JPL Horizons (ssd.jpl.nasa.gov/horizons).
    Tolerance: ±0.5° ecliptic longitude.
    """

    def test_sun_at_vernal_equinox_2024(self):
        """Sun should be at ~0° (Aries point) at vernal equinox."""
        from bazi_engine.transit import compute_transit_now

        # 2024-03-20 03:06 UTC — vernal equinox
        dt = datetime(2024, 3, 20, 3, 6, 0, tzinfo=timezone.utc)
        result = compute_transit_now(dt_utc=dt)
        sun_lon = result["planets"]["sun"]["longitude"]
        # Sun should be within 0.5° of 0° (or 360°)
        assert sun_lon < 0.5 or sun_lon > 359.5, f"Sun at equinox: {sun_lon}°, expected ~0°"

    def test_known_date_2026_03_09(self):
        """Cross-reference date from Dev Brief — smoke test."""
        from bazi_engine.transit import compute_transit_now

        dt = datetime(2026, 3, 9, 6, 0, 0, tzinfo=timezone.utc)
        result = compute_transit_now(dt_utc=dt)
        # Just verify structure and reasonable ranges
        for name in ["sun", "moon", "mercury", "venus", "mars", "jupiter", "saturn"]:
            p = result["planets"][name]
            assert 0 <= p["longitude"] < 360
            assert 0 <= p["sector"] <= 11
```

**Step 2: Run (will skip if no SE_EPHE_PATH)**

Run: `python -m pytest tests/test_transit_golden.py -v`
Expected: SKIPPED (unless SE_EPHE_PATH is set)

**Step 3: Commit**

```bash
git add tests/test_transit_golden.py
git commit -m "test: add transit golden vector tests for ephemeris validation"
```

---

## Summary

| Iteration | Tasks | What's Delivered | Commits |
|-----------|-------|-----------------|---------|
| 1 | 1-4 | Rebranding: all user-facing strings say FuFirE | 4 |
| 2 | 5-8 | `GET /transit/now` — real planetary positions | 3 |
| 3 | 9-11 | `POST /transit/state` — personalized transit | 2 |
| 4 | 12-13 | `POST /transit/narrative` — template text gen | 2 |
| 5 | 14-15 | `GET /transit/timeline` — multi-day forecast | 2 |
| 6 | 16-17 | OpenAPI regen + golden validation tests | 2 |

**Total: 17 tasks, ~15 commits, all TDD (red-green-commit)**

### What's NOT in this plan (deferred per Addendum):
- T-03: History Store (Supabase) — Phase B
- T-06: `/calculate/fusion` correlations field — Phase B
- F-01..F-06: Frontend integration — separate Astro-Noctum plan
- P-01..P-06: Route split — separate frontend plan
- Gemini async enrichment — after template engine is proven
- Push notifications / Morning Mail — Phase 4
