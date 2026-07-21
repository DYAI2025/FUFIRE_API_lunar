"""Negative tests for aspects.py: edge cases, invalid inputs, boundary values."""
from __future__ import annotations

import pytest

from bazi_engine.aspects import (
    ASPECT_DEFS,
    _angular_distance,
    compute_aspects,
    effective_orb,
)


class TestAngularDistanceEdgeCases:
    """_angular_distance edge cases and boundary values."""

    def test_same_position_is_zero(self):
        assert _angular_distance(100.0, 100.0) == 0.0

    def test_exact_opposition(self):
        assert _angular_distance(0.0, 180.0) == 180.0

    def test_wraparound_near_zero(self):
        """359° and 1° should be 2° apart, not 358°."""
        assert _angular_distance(359.0, 1.0) == 2.0

    def test_wraparound_both_near_360(self):
        assert _angular_distance(350.0, 10.0) == 20.0

    def test_negative_longitude_modulo(self):
        """Negative input should still produce correct result via modulo."""
        # -10° is equivalent to 350°
        dist = _angular_distance(-10.0, 10.0)
        assert dist == pytest.approx(20.0, abs=0.01)

    def test_longitude_above_360(self):
        """Values above 360° should wrap correctly."""
        dist = _angular_distance(370.0, 10.0)
        assert dist == pytest.approx(0.0, abs=0.01)

    def test_large_negative(self):
        dist = _angular_distance(-350.0, 10.0)
        assert dist == pytest.approx(0.0, abs=0.01)

    def test_symmetry(self):
        """Distance should be symmetric."""
        assert _angular_distance(45.0, 135.0) == _angular_distance(135.0, 45.0)


class TestComputeAspectsNegativeCases:
    """compute_aspects with missing, empty, or malformed input."""

    def test_empty_bodies_returns_empty(self):
        aspects = compute_aspects({})
        assert aspects == []

    def test_single_planet_no_aspects(self):
        bodies = {"Sun": {"longitude": 100.0}}
        aspects = compute_aspects(bodies)
        assert aspects == []

    def test_planet_with_none_longitude_filtered_out(self):
        """Planets with None longitude should be excluded, not crash."""
        bodies = {
            "Sun": {"longitude": 100.0},
            "Moon": {"longitude": None},
            "Mars": {"longitude": 190.0},
        }
        # Should not raise TypeError
        aspects = compute_aspects(bodies)
        # Sun-Mars at 90° → square aspect
        assert all(a["planet1"] != "Moon" and a["planet2"] != "Moon" for a in aspects)

    def test_planet_missing_longitude_key(self):
        """Planet dict without 'longitude' key should be filtered out."""
        bodies = {
            "Sun": {"longitude": 100.0},
            "Moon": {"speed": 13.0},  # no longitude key
            "Mars": {"longitude": 190.0},
        }
        aspects = compute_aspects(bodies)
        assert all(a["planet1"] != "Moon" and a["planet2"] != "Moon" for a in aspects)

    def test_explicit_empty_planet_list(self):
        """Explicit empty planets list should return no aspects."""
        bodies = {"Sun": {"longitude": 100.0}, "Moon": {"longitude": 200.0}}
        aspects = compute_aspects(bodies, planets=[])
        assert aspects == []

    def test_explicit_planet_not_in_bodies_filtered(self):
        """Requesting planet not in bodies should skip it, not crash."""
        bodies = {"Sun": {"longitude": 100.0}}
        aspects = compute_aspects(bodies, planets=["Sun", "Mars"])
        # Mars not in bodies → only Sun left → no pairs → no aspects
        assert aspects == []

    def test_one_aspect_per_pair(self):
        """Even if multiple aspects match (e.g., tight orbs), only first should match."""
        # Two planets at exactly 0° — conjunction matches first in ASPECT_DEFS
        bodies = {
            "Sun": {"longitude": 100.0},
            "Moon": {"longitude": 100.0},
        }
        aspects = compute_aspects(bodies, planets=["Sun", "Moon"])
        assert len(aspects) == 1
        assert aspects[0]["type"] == "conjunction"


class TestAspectOrbs:
    """Verify orb boundaries."""

    def test_just_within_orb_detected(self):
        """Conjunction with deviation exactly at effective orb boundary."""
        # Sun-Moon effective conjunction orb = (10+10)/2 * 1.0 = 10.0°
        bodies = {
            "Sun": {"longitude": 100.0},
            "Moon": {"longitude": 110.0},  # exactly at effective orb
        }
        aspects = compute_aspects(bodies, planets=["Sun", "Moon"])
        assert len(aspects) == 1
        assert aspects[0]["type"] == "conjunction"

    def test_just_outside_orb_not_detected(self):
        """Deviation just beyond effective orb should not match."""
        # Sun-Moon conjunction effective orb = 10.0°
        bodies = {
            "Sun": {"longitude": 100.0},
            "Moon": {"longitude": 110.1},  # slightly beyond 10.0° effective orb
        }
        aspects = compute_aspects(bodies, planets=["Sun", "Moon"])
        assert len(aspects) == 0

    def test_narrow_body_tight_orb(self):
        """Chiron-Pluto conjunction should have a much tighter orb."""
        # Chiron(3°) + Pluto(5°) / 2 = 4.0°
        bodies = {
            "Chiron": {"longitude": 100.0},
            "Pluto": {"longitude": 105.0},  # 5° > 4° effective orb → no conjunction
        }
        aspects = compute_aspects(bodies, planets=["Chiron", "Pluto"])
        assert len(aspects) == 0

    def test_narrow_body_within_orb(self):
        """Chiron-Pluto within 4° should detect conjunction."""
        bodies = {
            "Chiron": {"longitude": 100.0},
            "Pluto": {"longitude": 103.5},  # 3.5° < 4° effective orb
        }
        aspects = compute_aspects(bodies, planets=["Chiron", "Pluto"])
        assert len(aspects) == 1
        assert aspects[0]["type"] == "conjunction"

    def test_effective_orb_calculation(self):
        """Verify effective_orb formula: (A + B) / 2 × factor."""
        # Sun(10) + Moon(10) conjunction(1.0) = 10.0
        assert effective_orb("Sun", "Moon", 1.0) == 10.0
        # Chiron(3) + Pluto(5) conjunction(1.0) = 4.0
        assert effective_orb("Chiron", "Pluto", 1.0) == 4.0
        # Sun(10) + Mars(7) sextile(0.75) = 6.375
        assert effective_orb("Sun", "Mars", 0.75) == pytest.approx(6.375)

    def test_all_aspect_types_detectable(self):
        """Verify each aspect type can be detected."""
        for name, exact_angle, factor in ASPECT_DEFS:
            bodies = {
                "Sun": {"longitude": 0.0},
                "Moon": {"longitude": exact_angle},
            }
            aspects = compute_aspects(bodies, planets=["Sun", "Moon"])
            assert len(aspects) == 1, f"{name} at {exact_angle}° not detected"
            assert aspects[0]["type"] == name

    def test_sorted_by_tightest_orb(self):
        """Aspects should be sorted by smallest orb first."""
        bodies = {
            "Sun": {"longitude": 0.0},
            "Moon": {"longitude": 5.0},       # conjunction, orb=5
            "Mars": {"longitude": 120.5},      # trine, orb=0.5
            "Venus": {"longitude": 89.0},      # square, orb=1.0
        }
        aspects = compute_aspects(bodies, planets=["Sun", "Moon", "Mars", "Venus"])
        orbs = [a["orb"] for a in aspects]
        assert orbs == sorted(orbs), "Aspects should be sorted by orb ascending"
