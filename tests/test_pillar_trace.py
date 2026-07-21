"""Tests: pillar derivation trace in /calculate/bazi response."""
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
    r = client.post("/calculate/bazi", json=PAYLOAD)
    return r.status_code == 200


_HAS_EPHEMERIS = _ephemeris_available()
_skip_no_ephe = pytest.mark.skipif(
    not _HAS_EPHEMERIS,
    reason="Swiss Ephemeris files not available",
)


@_skip_no_ephe
class TestPillarTrace:
    """Pillar derivation trace must be available."""

    def test_trace_key_exists(self):
        r = client.post("/calculate/bazi", json=PAYLOAD)
        assert r.status_code == 200
        data = r.json()
        assert "derivation_trace" in data

    def test_year_trace_has_lichun(self):
        r = client.post("/calculate/bazi", json=PAYLOAD)
        data = r.json()
        trace = data["derivation_trace"]
        assert "year" in trace
        assert "lichun_crossing_utc" in trace["year"]
        assert "is_before_lichun" in trace["year"]

    def test_month_trace_has_jieqi(self):
        r = client.post("/calculate/bazi", json=PAYLOAD)
        data = r.json()
        trace = data["derivation_trace"]
        assert "month" in trace
        assert "jieqi_crossing_utc" in trace["month"]
        assert "solar_longitude_deg" in trace["month"]

    def test_day_trace_has_jdn(self):
        r = client.post("/calculate/bazi", json=PAYLOAD)
        data = r.json()
        trace = data["derivation_trace"]
        assert "day" in trace
        assert "julian_day_number" in trace["day"]
        assert "sexagenary_index" in trace["day"]

    def test_hour_trace_has_branch(self):
        r = client.post("/calculate/bazi", json=PAYLOAD)
        data = r.json()
        trace = data["derivation_trace"]
        assert "hour" in trace
        assert "local_hour" in trace["hour"]
        assert "branch_index" in trace["hour"]

    def test_day_block_surfaces_day_master_stem(self):
        r = client.post("/calculate/bazi", json=PAYLOAD)
        day_trace = r.json()["derivation_trace"]["day"]
        # Day Master = Day Pillar Stem (FBP-02-008).
        # Cross-check against the top-level chinese.day_master.
        chinese_day_master = r.json()["chinese"]["day_master"]
        assert day_trace["day_master_stem"] == chinese_day_master

    def test_day_block_surfaces_anchor_evidence(self):
        r = client.post("/calculate/bazi", json=PAYLOAD)
        evidence = r.json()["derivation_trace"]["day"]["day_anchor_evidence"]
        # The four fields the engine reads from the ruleset:
        for key in ("ruleset_id", "ruleset_version", "anchor_jdn",
                    "anchor_sex_idx", "anchor_verification"):
            assert key in evidence, f"day_anchor_evidence missing {key!r}"
        # Sanity: the shipped ruleset id is standard_bazi_2026.
        assert evidence["ruleset_id"] == "standard_bazi_2026"

    def test_day_offset_used_matches_ruleset_not_constant(self):
        """FBP-02-008: the trace must report the ruleset-derived offset,
        not the bazi_engine.constants.DAY_OFFSET constant. Today they
        happen to be equal (both 49); when FBP-02-002 corrects the
        anchor, this test will fail unless the trace value follows the
        ruleset (which it must — see FBP-02-001).
        """
        from bazi_engine.bazi_rules import (
            day_offset_from_ruleset,
            load_default_ruleset,
        )
        r = client.post("/calculate/bazi", json=PAYLOAD)
        trace_offset = r.json()["derivation_trace"]["day"]["day_offset_used"]
        assert trace_offset == day_offset_from_ruleset(load_default_ruleset())
