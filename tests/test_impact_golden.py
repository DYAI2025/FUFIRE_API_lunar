"""Golden vector tests for /impact/active — deterministic correctness.

These tests verify that known birth data produces expected impact results
using real Swiss Ephemeris calculations. They skip gracefully if ephemeris
files are not available.
"""
from __future__ import annotations

import httpx
import pytest
import respx

from bazi_engine.ephemeris import ensure_ephemeris_files
from bazi_engine.exc import EphemerisUnavailableError

try:
    ensure_ephemeris_files(None)
except (FileNotFoundError, EphemerisUnavailableError):
    pytest.skip(
        "Impact golden tests require Swiss Ephemeris files. Set SE_EPHE_PATH to run.",
        allow_module_level=True,
    )

from starlette.testclient import TestClient

from bazi_engine.impact import find_active_planets
from bazi_engine.impact_resonance import day_master_element, enrich_active_planets
from bazi_engine.services.space_weather import _KP_URL, _SOLAR_WIND_URL, _cache

# ── Test fixtures ───────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def env(monkeypatch):
    monkeypatch.setenv("FUFIRE_REQUIRE_API_KEYS", "false")
    monkeypatch.delenv("FUFIRE_API_KEYS", raising=False)
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "https://bazodiac.space")


@pytest.fixture(autouse=True)
def clear_sw_cache():
    _cache.clear()
    yield
    _cache.clear()


@pytest.fixture
def client():
    from bazi_engine.app import app
    return TestClient(app)


def _mock_noaa():
    respx.get(_KP_URL).mock(return_value=httpx.Response(200, json=[
        ["time_tag", "Kp", "observed"],
        ["2026-04-13 00:00:00", "3.0", "observed"],
    ]))
    respx.get(_SOLAR_WIND_URL).mock(return_value=httpx.Response(200, json=[
        ["time_tag", "density", "speed", "temperature"],
        ["2026-04-13 00:00:00", "5.0", "400.0", "100000"],
    ]))


# ── Golden vector: Berlin 1990-05-23 ───────────────────────────────────────

BERLIN_BIRTH = {
    "birth": {
        "date": "1990-05-23",
        "time": "14:30",
        "tz": "Europe/Berlin",
        "lat": 52.52,
        "lon": 13.405,
    },
    "target_date": "2026-04-13",
}


class TestGoldenBerlin1990:
    """Golden vector: born 1990-05-23 14:30 Berlin, transit on 2026-04-13."""

    @respx.mock
    def test_response_is_deterministic(self, client):
        """Same input must produce identical output across runs."""
        _mock_noaa()
        r1 = client.post("/impact/active", json=BERLIN_BIRTH).json()
        _cache.clear()
        _mock_noaa()
        r2 = client.post("/impact/active", json=BERLIN_BIRTH).json()

        assert r1["harmony_index"] == r2["harmony_index"]
        assert r1["day_mode"] == r2["day_mode"]
        assert r1["day_master"] == r2["day_master"]
        assert len(r1["active_planets"]) == len(r2["active_planets"])
        for p1, p2 in zip(r1["active_planets"], r2["active_planets"]):
            assert p1["planet"] == p2["planet"]
            assert p1["orb"] == p2["orb"]
            assert p1["aspect"] == p2["aspect"]

    @respx.mock
    def test_day_master_is_valid_element(self, client):
        _mock_noaa()
        data = client.post("/impact/active", json=BERLIN_BIRTH).json()
        assert data["day_master"] in ("wood", "fire", "earth", "metal", "water")

    @respx.mock
    def test_active_planets_sorted_by_orb(self, client):
        _mock_noaa()
        data = client.post("/impact/active", json=BERLIN_BIRTH).json()
        orbs = [p["orb"] for p in data["active_planets"]]
        assert orbs == sorted(orbs)

    @respx.mock
    def test_all_active_planets_have_orb_within_8(self, client):
        _mock_noaa()
        data = client.post("/impact/active", json=BERLIN_BIRTH).json()
        for p in data["active_planets"]:
            assert p["orb"] <= 8.0, f"{p['planet']} has orb {p['orb']} > 8"

    @respx.mock
    def test_strength_matches_orb_classification(self, client):
        """PRD P0-3: high (<3°), medium (3–5°), low (5–8°)."""
        _mock_noaa()
        data = client.post("/impact/active", json=BERLIN_BIRTH).json()
        for p in data["active_planets"]:
            if p["orb"] < 3.0:
                assert p["strength"] == "high", f"{p['planet']}: orb {p['orb']} should be high"
            elif p["orb"] <= 5.0:
                assert p["strength"] == "medium", f"{p['planet']}: orb {p['orb']} should be medium"
            else:
                assert p["strength"] == "low", f"{p['planet']}: orb {p['orb']} should be low"

    @respx.mock
    def test_bazi_resonance_never_neutral_for_active_planets(self, client):
        """Active planets always have a real resonance (same or cycle relationship)."""
        _mock_noaa()
        data = client.post("/impact/active", json=BERLIN_BIRTH).json()
        for p in data["active_planets"]:
            assert p["bazi_resonance"]["type"] in ("gleichklang", "naehrung", "kontrolle"), (
                f"{p['planet']} has unexpected neutral resonance"
            )

    @respx.mock
    def test_evidence_contains_formula(self, client):
        _mock_noaa()
        data = client.post("/impact/active", json=BERLIN_BIRTH).json()
        assert "harmony" in data["evidence"]["resonance_formula"]
        assert "natal_vector" in data["evidence"]["parameters"]
        assert "transit_vector" in data["evidence"]["parameters"]

    @respx.mock
    def test_drivers_have_correct_names(self, client):
        _mock_noaa()
        data = client.post("/impact/active", json=BERLIN_BIRTH).json()
        names = {d["name"] for d in data["drivers"]}
        assert names == {"geomagnetic", "solar", "transit", "day_field"}


# ── Golden vector: Tokyo 2000-01-01 (millennium baby) ──────────────────────

TOKYO_BIRTH = {
    "birth": {
        "date": "2000-01-01",
        "time": "00:00",
        "tz": "Asia/Tokyo",
        "lat": 35.6762,
        "lon": 139.6503,
    },
    "target_date": "2026-04-13",
}


class TestGoldenTokyo2000:
    @respx.mock
    def test_midnight_birth_produces_valid_response(self, client):
        _mock_noaa()
        resp = client.post("/impact/active", json=TOKYO_BIRTH)
        assert resp.status_code == 200
        data = resp.json()
        assert 0 <= data["harmony_index"] <= 1
        assert data["day_master"] in ("wood", "fire", "earth", "metal", "water")

    @respx.mock
    def test_different_birth_gives_different_day_master(self, client):
        """Two different births should (with high probability) differ in day_master or planets."""
        _mock_noaa()
        berlin = client.post("/impact/active", json=BERLIN_BIRTH).json()
        _cache.clear()
        _mock_noaa()
        tokyo = client.post("/impact/active", json=TOKYO_BIRTH).json()
        differs = (
            berlin["day_master"] != tokyo["day_master"]
            or berlin["harmony_index"] != tokyo["harmony_index"]
            or len(berlin["active_planets"]) != len(tokyo["active_planets"])
        )
        assert differs, "Two different births should produce different impacts"


# ── Edge cases ──────────────────────────────────────────────────────────────

class TestImpactEdgeCases:
    @respx.mock
    def test_noon_default_when_time_omitted(self, client):
        """Birth time defaults to 12:00 per PRD rule."""
        _mock_noaa()
        body = {
            "birth": {
                "date": "1990-05-23",
                "tz": "Europe/Berlin",
                "lat": 52.52,
                "lon": 13.405,
            },
            "target_date": "2026-04-13",
        }
        resp = client.post("/impact/active", json=body)
        assert resp.status_code == 200

    @respx.mock
    def test_with_both_sector_inputs(self, client):
        _mock_noaa()
        body = {
            **BERLIN_BIRTH,
            "soulprint_sectors": {"wood": 0.3, "fire": 0.2, "earth": 0.2, "metal": 0.2, "water": 0.1},
            "quiz_sectors": {"wood": 0.2, "fire": 0.3, "earth": 0.2, "metal": 0.1, "water": 0.2},
        }
        resp = client.post("/impact/active", json=body)
        assert resp.status_code == 200
        data = resp.json()
        assert data["harmony_index"] >= 0

    @respx.mock
    def test_response_json_serializable(self, client):
        """Full response must serialize to valid JSON without NaN/Inf."""
        import json
        _mock_noaa()
        resp = client.post("/impact/active", json=BERLIN_BIRTH)
        text = resp.text
        json.loads(text)  # response must be valid JSON
        assert "NaN" not in text
        assert "Infinity" not in text


# ── Unit-level golden vectors (no HTTP, direct function calls) ──────────────

class TestImpactCalcGolden:
    def test_find_active_planets_returns_frozen_models(self):
        from datetime import datetime, timezone

        from bazi_engine.bazi import compute_bazi
        from bazi_engine.transit import compute_transit_now
        from bazi_engine.types import BaziInput
        from bazi_engine.western import compute_western_chart

        inp = BaziInput(
            birth_local="1990-05-23T14:30:00",
            timezone="Europe/Berlin",
            longitude_deg=13.405,
            latitude_deg=52.52,
        )
        bazi_result = compute_bazi(inp)
        western = compute_western_chart(bazi_result.birth_utc_dt, 52.52, 13.405)
        transit = compute_transit_now(dt_utc=datetime(2026, 4, 13, 12, 0, 0, tzinfo=timezone.utc))

        active = find_active_planets(western["bodies"], transit["planets"])
        master = day_master_element(
            ["Jia", "Yi", "Bing", "Ding", "Wu", "Ji", "Geng", "Xin", "Ren", "Gui"][
                bazi_result.pillars.day.stem_index
            ]
        )
        enriched = enrich_active_planets(active, master)

        for p in enriched:
            assert p.orb <= 8.0
            assert p.bazi_resonance.type in ("gleichklang", "naehrung", "kontrolle", "neutral")
            assert p.weight >= 0 and p.weight <= 1
            with pytest.raises(Exception):
                p.orb = 0  # frozen
