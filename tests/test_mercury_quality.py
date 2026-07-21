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
    def test_with_ascendant_returns_bool(self):
        result = is_night_chart(180.0, ascendant=90.0)
        assert isinstance(result, bool)

    def test_without_ascendant_defaults_day(self):
        result = is_night_chart(180.0, ascendant=None)
        assert result is False


@_skip_no_ephe
class TestMercuryQualityInLedger:
    def test_mercury_has_chart_type_quality(self):
        r = client.post("/calculate/fusion", json=PAYLOAD)
        data = r.json()
        mercury = [e for e in data["contribution_ledger"]["western"]
                   if e["planet"] == "Mercury"]
        assert len(mercury) == 1
        assert "chart_type_quality" in mercury[0]
        assert mercury[0]["chart_type_quality"] in ("exact", "assumed_day")

    def test_with_ascendant_quality_is_exact(self):
        r = client.post("/calculate/fusion", json=PAYLOAD)
        data = r.json()
        mercury = [e for e in data["contribution_ledger"]["western"]
                   if e["planet"] == "Mercury"][0]
        # Berlin at 52° — Placidus works, Ascendant available
        assert mercury["chart_type_quality"] == "exact"
