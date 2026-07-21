"""Tests: zodiac_mode configuration in requests and responses."""
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
class TestZodiacModeWestern:
    """zodiac_mode must be explicit in request and response."""

    def test_default_is_tropical(self):
        r = client.post("/calculate/western", json=PAYLOAD)
        assert r.status_code == 200
        data = r.json()
        assert data["provenance"]["zodiac_mode"] == "tropical"

    def test_explicit_tropical(self):
        payload = {**PAYLOAD, "zodiac_mode": "tropical"}
        r = client.post("/calculate/western", json=payload)
        assert r.status_code == 200
        data = r.json()
        assert data["provenance"]["zodiac_mode"] == "tropical"

    def test_sidereal_lahiri(self):
        payload = {**PAYLOAD, "zodiac_mode": "sidereal_lahiri"}
        r = client.post("/calculate/western", json=payload)
        assert r.status_code == 200
        data = r.json()
        assert data["provenance"]["zodiac_mode"] == "sidereal_lahiri"
        # Sidereal longitudes should be ~24 deg less than tropical
        sun_lon = data["bodies"]["Sun"]["longitude"]
        # Sun on 2024-02-10 is ~321 deg tropical, ~297 deg sidereal (Lahiri)
        assert sun_lon < 310  # rough sanity check

    def test_invalid_zodiac_mode_rejected(self):
        payload = {**PAYLOAD, "zodiac_mode": "invalid_mode"}
        r = client.post("/calculate/western", json=payload)
        assert r.status_code == 422
