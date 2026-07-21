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
