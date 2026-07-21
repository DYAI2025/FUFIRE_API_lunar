"""Negative tests for narrative.py: edge cases, missing fields, empty input."""
from __future__ import annotations

from bazi_engine.narrative import ZODIAC_SIGNS_DE, generate_narrative


class TestNarrativeNoEvents:
    """Behavior when transit_state has no events."""

    def test_empty_events_returns_default(self):
        state = {"events": []}
        result = generate_narrative(state)
        assert result["pushworthy"] is False
        assert result["push_text"] is None
        assert len(result["headline"]) > 0
        assert len(result["body"]) > 0
        assert len(result["advice"]) > 0

    def test_missing_events_key_returns_default(self):
        """Transit state with no 'events' key should use default template."""
        state = {}
        result = generate_narrative(state)
        assert result["pushworthy"] is False
        assert len(result["headline"]) > 0


class TestNarrativeEdgeCases:
    """Edge cases in event processing."""

    def test_unknown_event_type_uses_default_template(self):
        """Event with unrecognized type should fall back to default template."""
        state = {
            "events": [{
                "type": "unknown_event_type",
                "priority": 1,
                "sector": 0,
                "trigger_planet": "mars",
                "personal_context": "test",
            }]
        }
        result = generate_narrative(state)
        assert len(result["headline"]) > 0
        # Should not crash, uses default template
        assert result["pushworthy"] is True  # priority <= 1

    def test_empty_trigger_planet(self):
        """Empty trigger_planet should not crash but may produce odd text."""
        state = {
            "events": [{
                "type": "resonance_jump",
                "priority": 1,
                "sector": 5,
                "trigger_planet": "",
                "personal_context": "context here",
            }]
        }
        result = generate_narrative(state)
        # Should not crash
        assert isinstance(result["headline"], str)
        assert isinstance(result["body"], str)

    def test_sector_out_of_range_uses_fallback(self):
        """Sector >= 12 should not crash (narrative.py has guard)."""
        state = {
            "events": [{
                "type": "moon_event",
                "priority": 2,
                "sector": 15,  # out of range
                "trigger_planet": "moon",
                "personal_context": "test",
            }]
        }
        result = generate_narrative(state)
        # Line 95: sector >= 12 falls back to "aries"
        assert isinstance(result["headline"], str)

    def test_negative_sector_uses_fallback(self):
        state = {
            "events": [{
                "type": "moon_event",
                "priority": 2,
                "sector": -1,
                "trigger_planet": "moon",
                "personal_context": "test",
            }]
        }
        result = generate_narrative(state)
        assert isinstance(result["headline"], str)

    def test_missing_priority_defaults_to_99(self):
        """Event without priority key should default to 99 (not pushworthy)."""
        state = {
            "events": [{
                "type": "resonance_jump",
                "sector": 0,
                "trigger_planet": "saturn",
                "personal_context": "test",
                # no "priority" key
            }]
        }
        result = generate_narrative(state)
        assert result["pushworthy"] is False
        assert result["push_text"] is None

    def test_missing_personal_context(self):
        state = {
            "events": [{
                "type": "resonance_jump",
                "priority": 1,
                "sector": 3,
                "trigger_planet": "venus",
                # no personal_context
            }]
        }
        result = generate_narrative(state)
        assert isinstance(result["body"], str)


class TestNarrativePriority:
    """Priority-based event selection."""

    def test_highest_priority_event_selected(self):
        """With multiple events, lowest priority number wins."""
        state = {
            "events": [
                {
                    "type": "moon_event",
                    "priority": 5,
                    "sector": 6,
                    "trigger_planet": "moon",
                    "personal_context": "low priority",
                },
                {
                    "type": "resonance_jump",
                    "priority": 1,
                    "sector": 3,
                    "trigger_planet": "saturn",
                    "personal_context": "high priority",
                },
            ]
        }
        result = generate_narrative(state)
        # resonance_jump template should be used (priority 1)
        assert result["pushworthy"] is True

    def test_priority_2_not_pushworthy(self):
        state = {
            "events": [{
                "type": "moon_event",
                "priority": 2,
                "sector": 0,
                "trigger_planet": "moon",
                "personal_context": "test",
            }]
        }
        result = generate_narrative(state)
        assert result["pushworthy"] is False


class TestNarrativeTemplateSubstitution:
    """Verify template variables are correctly substituted."""

    def test_all_zodiac_signs_produce_german(self):
        """Each sector should produce a German zodiac name."""
        for sector_idx in range(12):
            state = {
                "events": [{
                    "type": "moon_event",
                    "priority": 2,
                    "sector": sector_idx,
                    "trigger_planet": "moon",
                    "personal_context": "test context",
                }]
            }
            result = generate_narrative(state)
            # The headline should contain the German sign name
            expected_signs = list(ZODIAC_SIGNS_DE.values())
            assert expected_signs[sector_idx] in result["headline"], (
                f"Sector {sector_idx} should produce '{expected_signs[sector_idx]}' in headline"
            )

    def test_dominance_shift_template(self):
        state = {
            "events": [{
                "type": "dominance_shift",
                "priority": 1,
                "sector": 9,
                "trigger_planet": "",
                "personal_context": "Sektor 9 übernimmt",
            }]
        }
        result = generate_narrative(state)
        assert "Steinbock" in result["headline"] or "verschiebt" in result["headline"]
