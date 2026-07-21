"""Tests: quality_flags block on /v1/calculate/western response (Task 7).

Covers the new `quality_flags` object that surfaces house-system fallback
explicitly and exposes the active ephemeris backend mode.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from bazi_engine.app import app

client = TestClient(app)


# Mid-latitude: Placidus must succeed without fallback.
MIDLAT_PAYLOAD = {
    "date": "1990-06-15T12:00:00",
    "tz": "UTC",
    "lon": 0.0,
    "lat": 45.0,
}

# Extreme latitude: Placidus is undefined and the engine must report a fallback.
ARCTIC_PAYLOAD = {
    "date": "2024-06-21T12:00:00",
    "tz": "UTC",
    "lon": 15.6,
    "lat": 78.0,
}


def _ephemeris_available() -> bool:
    r = client.post("/v1/calculate/western", json=MIDLAT_PAYLOAD)
    return r.status_code == 200


_HAS_EPHEMERIS = _ephemeris_available()
_skip_no_ephe = pytest.mark.skipif(
    not _HAS_EPHEMERIS,
    reason="Swiss Ephemeris (or Moshier fallback) not available",
)


@_skip_no_ephe
def test_low_latitude_no_house_fallback() -> None:
    res = client.post("/v1/calculate/western", json=MIDLAT_PAYLOAD)
    assert res.status_code == 200, res.text
    data = res.json()
    assert "quality_flags" in data, "quality_flags block missing from response"
    qf = data["quality_flags"]
    assert qf["house_system_fallback"] is False
    assert qf["house_system_used"] == "placidus"
    assert qf["house_system_requested"] == "placidus"
    assert qf["ephemeris_mode"] in ("SWIEPH", "MOSEPH")


@_skip_no_ephe
def test_extreme_latitude_triggers_explicit_fallback() -> None:
    res = client.post("/v1/calculate/western", json=ARCTIC_PAYLOAD)
    assert res.status_code == 200, res.text
    data = res.json()
    qf = data["quality_flags"]
    assert qf["house_system_fallback"] is True
    assert qf["house_system_requested"] == "placidus"
    assert qf["house_system_used"] in ("porphyry", "whole_sign")
    assert qf["ephemeris_mode"] in ("SWIEPH", "MOSEPH")


@_skip_no_ephe
def test_quality_flags_consistent_with_house_quality() -> None:
    """quality_flags must agree with the legacy house_quality block."""
    res = client.post("/v1/calculate/western", json=ARCTIC_PAYLOAD)
    assert res.status_code == 200, res.text
    data = res.json()
    qf = data["quality_flags"]
    hq = data["house_quality"]
    assert qf["house_system_used"] == hq["system"]
    assert qf["house_system_requested"] == hq["requested"]
    # fallback flag mirrors hq.flag != "exact"
    assert qf["house_system_fallback"] is (hq["flag"] != "exact")
