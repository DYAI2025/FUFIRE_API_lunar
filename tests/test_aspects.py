"""Tests: planetary aspects in /calculate/western response."""
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
class TestAspects:
    """Aspects must appear in /calculate/western response."""

    def test_aspects_key_exists(self):
        r = client.post("/calculate/western", json=PAYLOAD)
        assert r.status_code == 200
        data = r.json()
        assert "aspects" in data
        assert isinstance(data["aspects"], list)

    def test_aspect_structure(self):
        r = client.post("/calculate/western", json=PAYLOAD)
        data = r.json()
        if data["aspects"]:
            aspect = data["aspects"][0]
            assert "planet1" in aspect
            assert "planet2" in aspect
            assert "type" in aspect
            assert "angle" in aspect
            assert "orb" in aspect
            assert aspect["type"] in (
                "conjunction", "semi-sextile", "sextile",
                "square", "trine", "quincunx", "opposition",
            )

    def test_aspect_orb_within_limit(self):
        r = client.post("/calculate/western", json=PAYLOAD)
        data = r.json()
        max_orb = 10.0  # degrees
        for aspect in data["aspects"]:
            assert abs(aspect["orb"]) <= max_orb

    def test_no_self_aspects(self):
        r = client.post("/calculate/western", json=PAYLOAD)
        data = r.json()
        for aspect in data["aspects"]:
            assert aspect["planet1"] != aspect["planet2"]

    def test_conjunction_near_zero(self):
        """A conjunction should have angle near 0°."""
        r = client.post("/calculate/western", json=PAYLOAD)
        data = r.json()
        conjunctions = [a for a in data["aspects"] if a["type"] == "conjunction"]
        for c in conjunctions:
            assert c["angle"] < 12  # within orb

    def test_at_least_some_aspects(self):
        """With 10 planets, there should be several aspects."""
        r = client.post("/calculate/western", json=PAYLOAD)
        data = r.json()
        assert len(data["aspects"]) >= 5


# ── Unit tests for minor aspects (no ephemeris needed) ──────────────────────

from bazi_engine.aspects import ASPECT_DEFS, compute_aspects


class TestMinorAspects:
    def test_aspect_defs_include_semi_sextile(self):
        names = [name for name, _, _ in ASPECT_DEFS]
        assert "semi-sextile" in names

    def test_aspect_defs_include_quincunx(self):
        names = [name for name, _, _ in ASPECT_DEFS]
        assert "quincunx" in names

    def test_semi_sextile_detected_at_30_degrees(self):
        bodies = {
            "Sun": {"longitude": 0.0},
            "Moon": {"longitude": 31.0},
        }
        aspects = compute_aspects(bodies, ["Sun", "Moon"])
        assert len(aspects) == 1
        assert aspects[0]["type"] == "semi-sextile"

    def test_quincunx_detected_at_150_degrees(self):
        bodies = {
            "Sun": {"longitude": 0.0},
            "Moon": {"longitude": 151.0},
        }
        aspects = compute_aspects(bodies, ["Sun", "Moon"])
        assert len(aspects) == 1
        assert aspects[0]["type"] == "quincunx"

    def test_semi_sextile_has_tight_orb(self):
        """Semi-sextile orb factor is 0.5, so effective orb is small."""
        bodies = {
            "Sun": {"longitude": 0.0},
            "Moon": {"longitude": 36.0},  # 6° off from 30°
        }
        aspects = compute_aspects(bodies, ["Sun", "Moon"])
        semi = [a for a in aspects if a["type"] == "semi-sextile"]
        assert len(semi) == 0  # 6° exceeds Sun-Moon semi-sextile orb (10+10)/2*0.5=5°

    def test_quincunx_orb_within_limit(self):
        bodies = {
            "Sun": {"longitude": 0.0},
            "Moon": {"longitude": 153.0},  # 3° off from 150°
        }
        aspects = compute_aspects(bodies, ["Sun", "Moon"])
        quinc = [a for a in aspects if a["type"] == "quincunx"]
        assert len(quinc) == 1
        assert quinc[0]["orb"] == 3.0

    def test_minor_aspect_does_not_override_major(self):
        """When a planet is near both 30° and 0°, conjunction (0°) should win."""
        bodies = {
            "Sun": {"longitude": 0.0},
            "Moon": {"longitude": 2.0},  # 2° from conjunction, 28° from semi-sextile
        }
        aspects = compute_aspects(bodies, ["Sun", "Moon"])
        assert len(aspects) == 1
        assert aspects[0]["type"] == "conjunction"

    def test_seven_aspect_types_total(self):
        assert len(ASPECT_DEFS) == 7
