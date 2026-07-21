"""Integration tests for POST /impact/active endpoint."""
from __future__ import annotations

import httpx
import pytest
import respx
from starlette.testclient import TestClient


@pytest.fixture(autouse=True)
def env(monkeypatch):
    monkeypatch.setenv("FUFIRE_REQUIRE_API_KEYS", "false")
    monkeypatch.delenv("FUFIRE_API_KEYS", raising=False)
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "https://bazodiac.space,http://localhost:3000")


@pytest.fixture
def client():
    from bazi_engine.app import app
    return TestClient(app)


def _valid_body():
    return {
        "birth": {
            "date": "1990-05-23",
            "time": "14:30",
            "tz": "Europe/Berlin",
            "lat": 52.52,
            "lon": 13.405,
        },
    }


def _mock_noaa():
    """Set up NOAA mock responses."""
    from bazi_engine.services.space_weather import _KP_URL, _SOLAR_WIND_URL, _cache
    _cache.clear()
    respx.get(_KP_URL).mock(return_value=httpx.Response(200, json=[
        ["time_tag", "Kp", "observed"],
        ["2026-04-13 00:00:00", "3.0", "observed"],
    ]))
    respx.get(_SOLAR_WIND_URL).mock(return_value=httpx.Response(200, json=[
        ["time_tag", "density", "speed", "temperature"],
        ["2026-04-13 00:00:00", "5.0", "400.0", "100000"],
    ]))


# ── Tests requiring ephemeris ───────────────────────────────────────────────

_EPHE_SKIP = "Swiss Ephemeris files not available"


def _has_ephemeris() -> bool:
    try:
        import swisseph as swe
        swe.calc_ut(2451545.0, swe.SUN)
        return True
    except Exception:
        return False


@pytest.mark.skipif(not _has_ephemeris(), reason=_EPHE_SKIP)
class TestImpactActiveWithEphemeris:
    @respx.mock
    def test_full_response_structure(self, client):
        _mock_noaa()
        resp = client.post("/impact/active", json=_valid_body())

        assert resp.status_code == 200
        data = resp.json()
        assert "harmony_index" in data
        assert 0 <= data["harmony_index"] <= 1
        assert data["day_mode"] in ("calm", "active", "tense", "pulse")
        assert 0 <= data["intensity"] <= 1
        assert isinstance(data["active_planets"], list)
        assert "space_weather" in data
        assert "drivers" in data
        assert len(data["drivers"]) == 4
        assert data["day_master"] in ("wood", "fire", "earth", "metal", "water")
        assert data["top_sector"] in ("wood", "fire", "earth", "metal", "water")
        assert "evidence" in data
        assert "resonance_formula" in data["evidence"]

    @respx.mock
    def test_active_planet_fields(self, client):
        _mock_noaa()
        resp = client.post("/impact/active", json=_valid_body())

        assert resp.status_code == 200
        data = resp.json()
        for planet in data["active_planets"]:
            assert "planet" in planet
            assert "aspect" in planet
            assert "orb" in planet
            assert planet["strength"] in ("high", "medium", "low")
            assert "is_retrograde" in planet
            assert "natal_position" in planet
            assert "transit_position" in planet
            assert "sector" in planet
            assert "weight" in planet
            assert "bazi_resonance" in planet
            res = planet["bazi_resonance"]
            assert res["element"] in ("wood", "fire", "earth", "metal", "water")
            assert res["type"] in ("gleichklang", "naehrung", "kontrolle", "neutral")
            assert res["intensity"] in ("gering", "mittel", "stark")

    @respx.mock
    def test_with_target_date(self, client):
        _mock_noaa()
        body = _valid_body()
        body["target_date"] = "2026-04-13"
        resp = client.post("/impact/active", json=body)

        assert resp.status_code == 200

    @respx.mock
    def test_with_soulprint_sectors(self, client):
        _mock_noaa()
        body = _valid_body()
        body["soulprint_sectors"] = {"wood": 0.3, "fire": 0.2, "earth": 0.2, "metal": 0.2, "water": 0.1}
        resp = client.post("/impact/active", json=body)

        assert resp.status_code == 200

    @respx.mock
    def test_v1_route_works(self, client):
        _mock_noaa()
        resp = client.post("/v1/impact/active", json=_valid_body())

        assert resp.status_code == 200

    @respx.mock
    def test_space_weather_503_returns_partial(self, client):
        from bazi_engine.services.space_weather import _KP_URL, _cache
        _cache.clear()
        respx.get(_KP_URL).mock(return_value=httpx.Response(503))
        from bazi_engine.services.space_weather import _SOLAR_WIND_URL
        respx.get(_SOLAR_WIND_URL).mock(return_value=httpx.Response(503))

        resp = client.post("/impact/active", json=_valid_body())

        assert resp.status_code == 200
        data = resp.json()
        assert data["partial"] is True
        assert data["space_weather"]["source"] in ("default", "noaa_partial")


# ── Validation tests (no ephemeris needed) ──────────────────────────────────

class TestImpactActiveValidation:
    def test_missing_birth_returns_422(self, client):
        resp = client.post("/impact/active", json={})
        assert resp.status_code == 422

    def test_invalid_date_format_returns_422(self, client):
        body = _valid_body()
        body["birth"]["date"] = "23-05-1990"
        resp = client.post("/impact/active", json=body)
        assert resp.status_code == 422

    def test_invalid_timezone_returns_422(self, client):
        body = _valid_body()
        body["birth"]["tz"] = "Not/A/Timezone"
        resp = client.post("/impact/active", json=body)
        assert resp.status_code == 422

    def test_lat_out_of_range_returns_422(self, client):
        body = _valid_body()
        body["birth"]["lat"] = 91.0
        resp = client.post("/impact/active", json=body)
        assert resp.status_code == 422

    def test_invalid_sector_keys_returns_422(self, client):
        body = _valid_body()
        body["soulprint_sectors"] = {"plasma": 0.5, "fire": 0.5}
        resp = client.post("/impact/active", json=body)
        assert resp.status_code == 422

    def test_get_method_not_allowed(self, client):
        resp = client.get("/impact/active")
        assert resp.status_code == 405
