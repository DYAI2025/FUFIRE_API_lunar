"""Negative tests for transit event detection edge cases."""
from __future__ import annotations

from bazi_engine.transit import _detect_events


# Minimal transit_now structure for testing _detect_events directly
def _make_transit(planets=None):
    if planets is None:
        planets = {
            "sun": {"sector": 0, "sign": "aries"},
            "moon": {"sector": 6, "sign": "libra"},
        }
    return {"planets": planets}


class TestResonanceJumpEdgeCases:
    """resonance_jump event detection edge cases."""

    def test_no_resonance_when_impact_below_threshold(self):
        """Impact < 0.18 should not trigger resonance_jump."""
        soulprint = [0.0] * 12
        soulprint[0] = 1.0  # peak sector 0
        impact = [0.17] + [0.0] * 11  # just below threshold
        transit = _make_transit({"sun": {"sector": 0, "sign": "aries"},
                                 "moon": {"sector": 6, "sign": "libra"}})
        events = _detect_events(transit, soulprint, impact)
        assert not any(e["type"] == "resonance_jump" for e in events)

    def test_resonance_when_impact_at_threshold(self):
        """Impact exactly 0.18 should trigger resonance_jump."""
        soulprint = [0.0] * 12
        soulprint[0] = 1.0
        impact = [0.18] + [0.0] * 11
        transit = _make_transit({"sun": {"sector": 0, "sign": "aries"},
                                 "moon": {"sector": 6, "sign": "libra"}})
        events = _detect_events(transit, soulprint, impact)
        assert any(e["type"] == "resonance_jump" for e in events)

    def test_no_resonance_when_planet_not_on_peak(self):
        """Planet on non-peak sector should not trigger resonance."""
        soulprint = [0.0] * 12
        soulprint[5] = 1.0  # peak at sector 5
        impact = [0.5] * 12  # high impact everywhere
        transit = _make_transit({"sun": {"sector": 0, "sign": "aries"},  # not on peak
                                 "moon": {"sector": 6, "sign": "libra"}})
        events = _detect_events(transit, soulprint, impact)
        resonances = [e for e in events if e["type"] == "resonance_jump"]
        assert len(resonances) == 0

    def test_multiple_planets_on_peak_generate_multiple_events(self):
        """Two planets on peak sector with sufficient impact."""
        soulprint = [0.0] * 12
        soulprint[3] = 1.0
        impact = [0.0] * 12
        impact[3] = 0.5
        transit = _make_transit({
            "sun": {"sector": 3, "sign": "cancer"},
            "moon": {"sector": 3, "sign": "cancer"},
            "mars": {"sector": 3, "sign": "cancer"},
        })
        events = _detect_events(transit, soulprint, impact)
        resonances = [e for e in events if e["type"] == "resonance_jump"]
        assert len(resonances) == 3


class TestMoonEventEdgeCases:
    """moon_event detection edge cases."""

    def test_moon_event_below_threshold(self):
        """Impact[moon_sector] < 0.5 should not trigger moon_event."""
        soulprint = [0.1] * 12
        impact = [0.49] * 12  # just below 0.5
        transit = _make_transit()  # moon at sector 6
        events = _detect_events(transit, soulprint, impact)
        assert not any(e["type"] == "moon_event" for e in events)

    def test_moon_event_at_threshold(self):
        """Impact[moon_sector] == 0.5 should trigger moon_event."""
        soulprint = [0.1] * 12
        impact = [0.0] * 12
        impact[6] = 0.5  # moon at sector 6
        transit = _make_transit()
        events = _detect_events(transit, soulprint, impact)
        assert any(e["type"] == "moon_event" for e in events)

    def test_moon_event_includes_sector_and_sign(self):
        soulprint = [0.1] * 12
        impact = [0.0] * 12
        impact[6] = 0.8
        transit = _make_transit()
        events = _detect_events(transit, soulprint, impact)
        moon_events = [e for e in events if e["type"] == "moon_event"]
        assert len(moon_events) == 1
        assert moon_events[0]["sector"] == 6
        assert moon_events[0]["trigger_planet"] == "moon"


class TestDominanceShiftRemoved:
    """dominance_shift was removed in v2 — verify it never fires."""

    def test_no_dominance_shift_event_type(self):
        """dominance_shift should never appear in events (removed in TRANSIT_STATE_v2)."""
        transit = _make_transit()
        soulprint = [0.1] * 12
        impact = [0.5] * 12
        ring = [0.5] + [0.1] * 11
        events = _detect_events(transit, soulprint, impact, ring_sectors=ring)
        assert not any(e["type"] == "dominance_shift" for e in events)

    def test_all_zeros_no_crash(self):
        """All-zero soulprint and impact should not crash."""
        transit = _make_transit()
        soulprint = [0.0] * 12
        impact = [0.0] * 12
        events = _detect_events(transit, soulprint, impact)
        # Should produce empty events (no resonance: max of all-zero is sector 0)
        assert isinstance(events, list)


class TestDetectEventsReturnStructure:
    """Verify event dicts have required keys."""

    def test_resonance_event_keys(self):
        soulprint = [0.0] * 12
        soulprint[0] = 1.0
        impact = [0.5] + [0.0] * 11
        transit = _make_transit({"sun": {"sector": 0, "sign": "aries"},
                                 "moon": {"sector": 6, "sign": "libra"}})
        events = _detect_events(transit, soulprint, impact)
        resonances = [e for e in events if e["type"] == "resonance_jump"]
        assert len(resonances) >= 1
        ev = resonances[0]
        assert "type" in ev
        assert "priority" in ev
        assert "sector" in ev
        assert "trigger_planet" in ev
        assert "description_de" in ev
        assert "personal_context" in ev
