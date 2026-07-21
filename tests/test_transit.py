"""Tests for transit API endpoints."""
from __future__ import annotations

from datetime import datetime
from unittest.mock import patch

from fastapi.testclient import TestClient

from bazi_engine.app import app

client = TestClient(app)

# Known planetary longitudes for a fixed date (mock data).
# We mock swe.calc_ut to return deterministic values.
# Keys are swisseph planet IDs: SUN=0, MOON=1, MERCURY=2, VENUS=3, MARS=4,
# JUPITER=5, SATURN=6, URANUS=7, NEPTUNE=8, PLUTO=9
MOCK_PLANET_DATA = {
    0: (348.7, 0.0, 1.0, 1.01, 0.0, 0.0),   # Sun → sector 11, pisces
    1: (187.2, 0.0, 0.003, 13.2, 0.0, 0.0),  # Moon → sector 6, libra
    2: (332.1, 0.0, 0.8, 1.8, 0.0, 0.0),     # Mercury → sector 11, pisces
    3: (15.4, 0.0, 0.7, 1.2, 0.0, 0.0),      # Venus → sector 0, aries
    4: (112.8, 0.0, 1.5, 0.7, 0.0, 0.0),     # Mars → sector 3, cancer
    5: (78.3, 0.0, 5.0, 0.08, 0.0, 0.0),     # Jupiter → sector 2, gemini
    6: (342.9, 0.0, 9.5, 0.03, 0.0, 0.0),    # Saturn → sector 11, pisces
    7: (51.2, 0.0, 19.2, 0.01, 0.0, 0.0),    # Uranus → sector 1, taurus
    8: (359.5, 0.0, 30.1, 0.005, 0.0, 0.0),  # Neptune → sector 11, pisces
    9: (303.8, 0.0, 33.7, 0.003, 0.0, 0.0),  # Pluto → sector 10, aquarius
}


def mock_calc_ut(jd_ut, planet_id, flags):
    """Mock swe.calc_ut to return deterministic planet positions."""
    if planet_id in MOCK_PLANET_DATA:
        return MOCK_PLANET_DATA[planet_id], 0
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
        dt = datetime.fromisoformat(data["computed_at"].replace("Z", "+00:00"))
        assert dt.tzinfo is not None


class TestTransitState:
    """POST /transit/state — personalized transit calculation."""

    SAMPLE_SOULPRINT = [0.42, 0.31, 0.55, 0.67, 0.28, 0.19, 0.48, 0.35, 0.22, 0.15, 0.20, 0.61]
    SAMPLE_QUIZ = [0.30, 0.25, 0.40, 0.35, 0.20, 0.15, 0.50, 0.30, 0.18, 0.10, 0.22, 0.45]

    def _post(self, soulprint=None, quiz=None):
        with patch("bazi_engine.transit.swe.calc_ut", side_effect=mock_calc_ut):
            return client.post("/transit/state", json={
                "soulprint_sectors": soulprint or self.SAMPLE_SOULPRINT,
                "quiz_sectors": quiz or self.SAMPLE_QUIZ,
            })

    def test_returns_200(self):
        assert self._post().status_code == 200

    def test_response_has_schema_field(self):
        data = self._post().json()
        assert data["schema"] == "TRANSIT_STATE_v2"

    def test_response_has_ring_sectors(self):
        data = self._post().json()
        assert "ring" in data
        assert len(data["ring"]["sectors"]) == 12

    def test_response_has_transit_contribution(self):
        data = self._post().json()
        assert "transit_contribution" in data
        assert len(data["transit_contribution"]["sectors"]) == 12
        assert "transit_intensity" in data["transit_contribution"]

    def test_response_has_no_delta_field(self):
        """v2 schema removes the always-null delta field."""
        data = self._post().json()
        assert "delta" not in data

    def test_validates_sector_array_length(self):
        """Must reject arrays that aren't exactly 12 elements."""
        r = client.post("/transit/state", json={
            "soulprint_sectors": [0.1, 0.2],
            "quiz_sectors": self.SAMPLE_QUIZ,
        })
        assert r.status_code == 422

    def test_events_is_list(self):
        data = self._post().json()
        assert isinstance(data.get("events"), list)

    def test_generated_at_is_present(self):
        data = self._post().json()
        assert "generated_at" in data


class TestTransitNarrative:
    """POST /transit/narrative — text generation from transit state."""

    SAMPLE_STATE = {
        "schema": "TRANSIT_STATE_v2",
        "generated_at": "2026-03-09T06:00:00Z",
        "ring": {"sectors": [0.42, 0.31, 0.55, 0.67, 0.28, 0.19, 0.48, 0.35, 0.22, 0.15, 0.20, 0.61]},
        "transit_contribution": {
            "sectors": [0.02, 0.01, 0.05, 0.08, 0.01, 0.0, 0.12, 0.03, 0.01, 0.0, 0.01, 0.15],
            "transit_intensity": 0.42,
        },
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
        assert len(data["headline"]) > 0
        assert len(data["body"]) > 0

    def test_pushworthy_event_sets_push_text(self):
        """Priority <= 1 event should be pushworthy with headline as push_text."""
        r = client.post("/transit/narrative", json={"transit_state": self.SAMPLE_STATE})
        data = r.json()
        assert data["pushworthy"] is True
        assert data["push_text"] == data["headline"]
        assert len(data["push_text"]) > 0

    def test_no_events_still_generates_text(self):
        state = {**self.SAMPLE_STATE, "events": []}
        r = client.post("/transit/narrative", json={"transit_state": state})
        assert r.status_code == 200
        data = r.json()
        assert len(data["headline"]) > 0
        assert data["pushworthy"] is False


class TestTransitTimeline:
    """GET /transit/timeline — multi-day transit forecast."""

    def test_returns_200(self):
        with patch("bazi_engine.transit.swe.calc_ut", side_effect=mock_calc_ut):
            r = client.get("/transit/timeline")
        assert r.status_code == 200

    def test_default_7_days(self):
        with patch("bazi_engine.transit.swe.calc_ut", side_effect=mock_calc_ut):
            r = client.get("/transit/timeline")
        data = r.json()
        assert len(data["days"]) == 7

    def test_returns_requested_days(self):
        with patch("bazi_engine.transit.swe.calc_ut", side_effect=mock_calc_ut):
            r = client.get("/transit/timeline?days=3")
        data = r.json()
        assert len(data["days"]) == 3

    def test_each_day_has_planets_and_date(self):
        with patch("bazi_engine.transit.swe.calc_ut", side_effect=mock_calc_ut):
            r = client.get("/transit/timeline?days=2")
        data = r.json()
        for day in data["days"]:
            assert "date" in day
            assert "planets" in day
            assert "sector_intensity" in day

    def test_rejects_invalid_days(self):
        r = client.get("/transit/timeline?days=0")
        assert r.status_code == 422
        r = client.get("/transit/timeline?days=31")
        assert r.status_code == 422


class TestOuterPlanetsInTransit:
    """Verify outer planets (Uranus, Neptune, Pluto) are included."""

    def test_outer_planets_in_response(self):
        with patch("bazi_engine.transit.swe.calc_ut", side_effect=mock_calc_ut):
            r = client.get("/transit/now")
        data = r.json()
        planets = data["planets"]
        for name in ["uranus", "neptune", "pluto"]:
            assert name in planets, f"Missing outer planet: {name}"
            p = planets[name]
            assert "longitude" in p
            assert "sector" in p
            assert "sign" in p
            assert "speed" in p

    def test_outer_planet_sectors_correct(self):
        with patch("bazi_engine.transit.swe.calc_ut", side_effect=mock_calc_ut):
            r = client.get("/transit/now")
        data = r.json()
        # Uranus at 51.2° → sector 1 (taurus)
        assert data["planets"]["uranus"]["sector"] == 1
        assert data["planets"]["uranus"]["sign"] == "taurus"
        # Neptune at 359.5° → sector 11 (pisces)
        assert data["planets"]["neptune"]["sector"] == 11
        # Pluto at 303.8° → sector 10 (aquarius)
        assert data["planets"]["pluto"]["sector"] == 10

    def test_outer_planet_weights_affect_intensity(self):
        """Outer planets with high weights should boost sector intensity."""
        with patch("bazi_engine.transit.swe.calc_ut", side_effect=mock_calc_ut):
            r = client.get("/transit/now")
        data = r.json()
        # Sector 10 has only Pluto (weight 2.0) — should have non-zero intensity
        assert data["sector_intensity"][10] > 0

    def test_total_planet_count_is_10(self):
        with patch("bazi_engine.transit.swe.calc_ut", side_effect=mock_calc_ut):
            r = client.get("/transit/now")
        data = r.json()
        assert len(data["planets"]) == 10
