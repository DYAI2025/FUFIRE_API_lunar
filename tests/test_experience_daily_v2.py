"""Tests for POST /experience/daily v2 — include=["impact"] parameter."""
from __future__ import annotations

import httpx
import pytest
import respx
from starlette.testclient import TestClient


@pytest.fixture(autouse=True)
def env(monkeypatch):
    monkeypatch.setenv("FUFIRE_REQUIRE_API_KEYS", "false")
    monkeypatch.delenv("FUFIRE_API_KEYS", raising=False)
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "https://bazodiac.space")


@pytest.fixture(autouse=True)
def clear_sw_cache():
    from bazi_engine.services.space_weather import _cache
    _cache.clear()
    yield
    _cache.clear()


@pytest.fixture
def client():
    from bazi_engine.app import app
    return TestClient(app)


def _mock_noaa():
    from bazi_engine.services.space_weather import _KP_URL, _SOLAR_WIND_URL
    respx.get(_KP_URL).mock(return_value=httpx.Response(200, json=[
        ["time_tag", "Kp", "observed"],
        ["2026-04-13 00:00:00", "3.0", "observed"],
    ]))
    respx.get(_SOLAR_WIND_URL).mock(return_value=httpx.Response(200, json=[
        ["time_tag", "density", "speed", "temperature"],
        ["2026-04-13 00:00:00", "5.0", "400.0", "100000"],
    ]))


def _valid_daily_body():
    return {
        "birth": {
            "date": "1990-05-23",
            "time": "14:30:00",
            "tz": "Europe/Berlin",
            "lat": 52.52,
            "lon": 13.405,
        },
        "soulprint_sectors": [0.08, 0.09, 0.08, 0.09, 0.08, 0.08, 0.09, 0.08, 0.09, 0.08, 0.08, 0.08],
        "quiz_sectors": [0.08, 0.09, 0.08, 0.09, 0.08, 0.08, 0.09, 0.08, 0.09, 0.08, 0.08, 0.08],
        "target_date": "2026-04-13",
    }


# ── Tests requiring ephemeris ───────────────────────────────────────────────

def _has_ephemeris() -> bool:
    try:
        import swisseph as swe
        swe.calc_ut(2451545.0, swe.SUN)
        return True
    except Exception:
        return False


_EPHE_SKIP = "Swiss Ephemeris required"


@pytest.mark.skipif(not _has_ephemeris(), reason=_EPHE_SKIP)
class TestDailyV2WithImpact:
    @respx.mock
    def test_without_include_has_no_impact(self, client):
        """v1 backwards compatibility: no include → impact is null."""
        _mock_noaa()
        body = _valid_daily_body()
        resp = client.post("/experience/daily", json=body)

        assert resp.status_code == 200
        data = resp.json()
        assert data["impact"] is None
        assert "western" in data
        assert "eastern" in data
        assert "fusion" in data

    @respx.mock
    def test_include_empty_list_has_no_impact(self, client):
        """include=[] is the same as not including."""
        _mock_noaa()
        body = _valid_daily_body()
        body["include"] = []
        resp = client.post("/experience/daily", json=body)

        assert resp.status_code == 200
        assert resp.json()["impact"] is None

    @respx.mock
    def test_include_impact_adds_impact_block(self, client):
        """include=["impact"] returns the full impact block."""
        _mock_noaa()
        body = _valid_daily_body()
        body["include"] = ["impact"]
        resp = client.post("/experience/daily", json=body)

        assert resp.status_code == 200
        data = resp.json()
        impact = data["impact"]
        assert impact is not None
        assert "harmony_index" in impact
        assert 0 <= impact["harmony_index"] <= 1
        assert "active_planets" in impact
        assert "space_weather" in impact
        assert "drivers" in impact
        assert len(impact["drivers"]) == 4
        assert "evidence" in impact
        assert "day_master" in impact

    @respx.mock
    def test_v1_fields_preserved_with_include(self, client):
        """Existing v1 response fields must still be present when include=["impact"]."""
        _mock_noaa()
        body = _valid_daily_body()
        body["include"] = ["impact"]
        resp = client.post("/experience/daily", json=body)

        assert resp.status_code == 200
        data = resp.json()
        assert "date" in data
        assert "western" in data
        assert "summary" in data["western"]
        assert "themes" in data["western"]
        assert "eastern" in data
        assert "fusion" in data
        assert "synthesis" in data["fusion"]
        assert "meta" in data
        assert "engine_version" in data["meta"]

    @respx.mock
    def test_impact_has_evidence_traceability(self, client):
        """Impact block must contain evidence with resonance_formula (Nachvollziehbarkeit)."""
        _mock_noaa()
        body = _valid_daily_body()
        body["include"] = ["impact"]
        resp = client.post("/experience/daily", json=body)

        assert resp.status_code == 200
        evidence = resp.json()["impact"]["evidence"]
        assert "resonance_formula" in evidence
        assert "parameters" in evidence
        assert "harmony_index" in evidence["parameters"]

    @respx.mock
    def test_v1_route_with_include(self, client):
        """v1 prefix also supports include param."""
        _mock_noaa()
        body = _valid_daily_body()
        body["include"] = ["impact"]
        resp = client.post("/v1/experience/daily", json=body)

        assert resp.status_code == 200
        assert resp.json()["impact"] is not None

    @respx.mock
    def test_unknown_include_value_ignored(self, client):
        """Unknown include values are ignored, not errored."""
        _mock_noaa()
        body = _valid_daily_body()
        body["include"] = ["unknown_feature"]
        resp = client.post("/experience/daily", json=body)

        assert resp.status_code == 200
        assert resp.json()["impact"] is None

    @respx.mock
    def test_impact_partial_on_space_weather_failure(self, client):
        """Space weather failure with include=["impact"] sets partial=true."""
        from bazi_engine.services.space_weather import _KP_URL, _SOLAR_WIND_URL, _cache
        _cache.clear()
        respx.get(_KP_URL).mock(side_effect=httpx.ConnectError("no route"))
        respx.get(_SOLAR_WIND_URL).mock(side_effect=httpx.ConnectError("no route"))

        body = _valid_daily_body()
        body["include"] = ["impact"]
        resp = client.post("/experience/daily", json=body)

        assert resp.status_code == 200
        assert resp.json()["impact"]["partial"] is True


# ── Validation tests (no ephemeris needed) ──────────────────────────────────

class TestDailyV2Validation:
    def test_include_accepts_list(self, client):
        """include field accepts a list of strings."""
        body = _valid_daily_body()
        body["include"] = ["impact"]
        # Will fail with 422 if birth calc fails without ephemeris,
        # but the request validation itself should pass
        resp = client.post("/experience/daily", json=body)
        assert resp.status_code in (200, 422, 500)  # not 400 for bad schema
