"""Tests: house system quality flags in /calculate/western responses."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from bazi_engine.app import app

client = TestClient(app)

# Mid-latitude: Placidus should work perfectly
BERLIN_PAYLOAD = {
    "date": "2024-02-10T14:30:00",
    "tz": "Europe/Berlin",
    "lon": 13.405,
    "lat": 52.52,
}

# High-latitude: Placidus will fall back
ARCTIC_PAYLOAD = {
    "date": "2024-06-21T12:00:00",
    "tz": "Arctic/Longyearbyen",
    "lon": 15.6,
    "lat": 78.22,
}


def _ephemeris_available() -> bool:
    r = client.post("/calculate/western", json=BERLIN_PAYLOAD)
    return r.status_code == 200


_HAS_EPHEMERIS = _ephemeris_available()
_skip_no_ephe = pytest.mark.skipif(
    not _HAS_EPHEMERIS,
    reason="Swiss Ephemeris files not available",
)


@_skip_no_ephe
class TestHouseQualityFlags:
    """House system quality flags must reflect actual computation method."""

    def test_mid_latitude_quality_exact(self):
        r = client.post("/calculate/western", json=BERLIN_PAYLOAD)
        assert r.status_code == 200
        data = r.json()
        assert "house_quality" in data
        assert data["house_quality"]["flag"] == "exact"
        assert data["house_quality"]["system"] == "placidus"

    def test_high_latitude_quality_fallback(self):
        r = client.post("/calculate/western", json=ARCTIC_PAYLOAD)
        assert r.status_code == 200
        data = r.json()
        assert "house_quality" in data
        assert data["house_quality"]["flag"] == "fallback"
        assert data["house_quality"]["system"] in ("porphyry", "whole_sign")
        assert "reason" in data["house_quality"]

    def test_quality_flag_in_fusion(self):
        r = client.post("/calculate/fusion", json=BERLIN_PAYLOAD)
        assert r.status_code == 200
        data = r.json()
        assert "house_quality" in data
        assert data["house_quality"]["flag"] in ("exact", "fallback", "estimated")

    def test_provenance_matches_quality(self):
        """provenance.house_system must agree with house_quality.system."""
        r = client.post("/calculate/western", json=ARCTIC_PAYLOAD)
        assert r.status_code == 200
        data = r.json()
        prov_hs = data["provenance"]["house_system"]
        quality_hs = data["house_quality"]["system"]
        assert prov_hs == quality_hs
