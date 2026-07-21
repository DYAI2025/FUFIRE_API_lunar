"""Tests for impact_harmony.py — harmony index, day mode, intensity, drivers."""
from __future__ import annotations

import pytest

from bazi_engine.impact_harmony import (
    _aspect_tightness_multiplier,
    _natal_wuxing_vector,
    _transit_wuxing_vector,
    build_evidence,
    build_resonance_badges,
    classify_day_mode,
    compute_drivers,
    compute_harmony_index,
    compute_intensity,
    find_top_sector,
)
from bazi_engine.impact_types import ActivePlanet, BaziResonance
from bazi_engine.wuxing.vector import WuXingVector

# ── Helpers ─────────────────────────────────────────────────────────────────

def _planet(element: str = "fire", weight: float = 0.8, rtype: str = "gleichklang") -> ActivePlanet:
    return ActivePlanet(
        planet="mars",
        aspect="conjunction",
        orb=2.0,
        strength="high",
        is_retrograde=False,
        natal_position=120.0,
        transit_position=122.0,
        sector="fire",
        weight=weight,
        bazi_resonance=BaziResonance(element=element, type=rtype, intensity="stark"),
    )


# ── _transit_wuxing_vector ──────────────────────────────────────────────────

class TestTransitWuxingVector:
    def test_single_fire_planet_amplified(self):
        vec = _transit_wuxing_vector([_planet("fire", weight=0.8)])
        # orb=2.0 → multiplier ~1.3125 → 0.8 * 1.3125 = 1.05
        assert vec.feuer > 0.8  # amplified by tightness
        assert vec.holz == 0.0

    def test_multiple_planets_sum_amplified_weights(self):
        planets = [_planet("fire", weight=0.5), _planet("fire", weight=0.3)]
        vec = _transit_wuxing_vector(planets)
        assert vec.feuer > 0.8  # amplified sum exceeds raw sum

    def test_empty_planets_gives_zero_vector(self):
        vec = _transit_wuxing_vector([])
        assert vec == WuXingVector.zero()

    def test_different_elements_amplified(self):
        planets = [_planet("wood", weight=0.4), _planet("water", weight=0.6)]
        vec = _transit_wuxing_vector(planets)
        assert vec.holz > 0.4  # amplified
        assert vec.wasser > 0.6  # amplified
        assert vec.feuer == 0.0


# ── _natal_wuxing_vector ────────────────────────────────────────────────────

class TestNatalWuxingVector:
    def test_no_sectors_gives_uniform(self):
        vec = _natal_wuxing_vector(None, None)
        assert vec.holz == pytest.approx(0.2)
        assert vec.feuer == pytest.approx(0.2)

    def test_soulprint_only(self):
        sp = {"wood": 0.3, "fire": 0.2, "earth": 0.2, "metal": 0.2, "water": 0.1}
        vec = _natal_wuxing_vector(sp, None)
        assert vec.holz == pytest.approx(0.3)
        assert vec.wasser == pytest.approx(0.1)

    def test_both_sectors_averaged(self):
        sp = {"wood": 0.4, "fire": 0.2, "earth": 0.2, "metal": 0.1, "water": 0.1}
        qz = {"wood": 0.2, "fire": 0.4, "earth": 0.2, "metal": 0.1, "water": 0.1}
        vec = _natal_wuxing_vector(sp, qz)
        assert vec.holz == pytest.approx(0.3)
        assert vec.feuer == pytest.approx(0.3)


# ── compute_harmony_index ───────────────────────────────────────────────────

class TestComputeHarmonyIndex:
    def test_identical_vectors_give_one(self):
        v = WuXingVector(0.3, 0.3, 0.2, 0.1, 0.1)
        assert compute_harmony_index(v, v) == pytest.approx(1.0, abs=0.001)

    def test_orthogonal_vectors_give_zero(self):
        a = WuXingVector(1.0, 0.0, 0.0, 0.0, 0.0)
        b = WuXingVector(0.0, 1.0, 0.0, 0.0, 0.0)
        assert compute_harmony_index(a, b) == pytest.approx(0.0, abs=0.001)

    def test_zero_vector_gives_zero(self):
        a = WuXingVector.zero()
        b = WuXingVector(0.3, 0.3, 0.2, 0.1, 0.1)
        assert compute_harmony_index(a, b) == 0.0

    def test_returns_between_zero_and_one(self):
        a = WuXingVector(0.5, 0.1, 0.2, 0.1, 0.1)
        b = WuXingVector(0.1, 0.5, 0.1, 0.2, 0.1)
        h = compute_harmony_index(a, b)
        assert 0.0 <= h <= 1.0


# ── compute_intensity ───────────────────────────────────────────────────────

class TestComputeIntensity:
    def test_all_max_gives_one(self):
        assert compute_intensity(1.0, 5, 1.0) == pytest.approx(1.0)

    def test_all_zero_gives_zero(self):
        assert compute_intensity(0.0, 0, 0.0) == pytest.approx(0.0)

    def test_range_bounded(self):
        i = compute_intensity(0.7, 3, 0.5)
        assert 0.0 <= i <= 1.0

    def test_high_planet_count_caps_at_five(self):
        i5 = compute_intensity(0.5, 5, 0.3)
        i10 = compute_intensity(0.5, 10, 0.3)
        assert i5 == i10  # capped at 5


# ── classify_day_mode ───────────────────────────────────────────────────────

class TestClassifyDayMode:
    def test_high_intensity_is_pulse(self):
        assert classify_day_mode(0.8, 0.8) == "pulse"

    def test_high_harmony_low_intensity_is_calm(self):
        assert classify_day_mode(0.7, 0.3) == "calm"

    def test_low_harmony_is_tense(self):
        assert classify_day_mode(0.3, 0.5) == "tense"

    def test_mid_values_is_active(self):
        assert classify_day_mode(0.5, 0.5) == "active"


# ── compute_drivers ─────────────────────────────────────────────────────────

class TestComputeDrivers:
    def test_returns_exactly_four(self):
        drivers = compute_drivers(0.3, 2, 0.6)
        assert len(drivers) == 4
        names = {d.name for d in drivers}
        assert names == {"geomagnetic", "solar", "transit", "day_field"}

    def test_high_space_weather_makes_tense(self):
        drivers = compute_drivers(0.9, 0, 0.5)
        geo = next(d for d in drivers if d.name == "geomagnetic")
        assert geo.level == "tense"

    def test_calm_when_all_low(self):
        drivers = compute_drivers(0.1, 1, 0.8)
        for d in drivers:
            if d.name in ("geomagnetic", "solar"):
                assert d.level == "calm"

    def test_high_harmony_calms_day_field(self):
        drivers = compute_drivers(0.0, 0, 0.9)
        day_field = next(d for d in drivers if d.name == "day_field")
        assert day_field.level == "calm"  # 1.0 - 0.9 = 0.1 → calm


# ── find_top_sector ─────────────────────────────────────────────────────────

class TestFindTopSector:
    def test_single_planet(self):
        assert find_top_sector([_planet("fire")]) == "fire"

    def test_heaviest_element_wins(self):
        planets = [
            _planet("fire", weight=0.3),
            _planet("wood", weight=0.5),
            _planet("wood", weight=0.4),
        ]
        assert find_top_sector(planets) == "wood"

    def test_empty_list_returns_an_element(self):
        result = find_top_sector([])
        assert result in ("wood", "fire", "earth", "metal", "water")


# ── build_resonance_badges ──────────────────────────────────────────────────

class TestBuildResonanceBadges:
    def test_gleichklang_produces_badge(self):
        badges = build_resonance_badges([_planet("fire", rtype="gleichklang")])
        assert len(badges) == 1
        assert badges[0].label == "Feuer-Gleichklang"
        assert badges[0].source_planet == "mars"

    def test_neutral_skipped(self):
        badges = build_resonance_badges([_planet("fire", rtype="neutral")])
        assert len(badges) == 0

    def test_multiple_planets_multiple_badges(self):
        planets = [
            _planet("fire", rtype="gleichklang"),
            _planet("wood", rtype="naehrung"),
        ]
        badges = build_resonance_badges(planets)
        assert len(badges) == 2


# ── _aspect_tightness_multiplier ────────────────────────────────────────────

class TestAspectTightnessMultiplier:
    def test_exact_aspect_gets_max_boost(self):
        assert _aspect_tightness_multiplier(0.0) == 1.5

    def test_max_orb_gets_minimum(self):
        assert _aspect_tightness_multiplier(8.0) == 0.75

    def test_midpoint_is_about_one(self):
        mid = _aspect_tightness_multiplier(4.0)
        assert 1.0 <= mid <= 1.2

    def test_orb_beyond_max_clamped(self):
        assert _aspect_tightness_multiplier(10.0) == _aspect_tightness_multiplier(8.0)

    def test_monotonically_decreasing(self):
        values = [_aspect_tightness_multiplier(o) for o in range(9)]
        for i in range(len(values) - 1):
            assert values[i] >= values[i + 1]


class TestTransitVectorAmplification:
    def test_tight_aspect_contributes_more_than_loose(self):
        """A tight-orb planet should produce a higher element weight than a loose one."""
        tight_planet = ActivePlanet(
            planet="mars", aspect="conjunction", orb=0.5, strength="high",
            is_retrograde=False, natal_position=0, transit_position=0.5,
            sector="fire", weight=0.5,
            bazi_resonance=BaziResonance(element="fire", type="gleichklang", intensity="stark"),
        )
        loose_planet = ActivePlanet(
            planet="saturn", aspect="sextile", orb=7.5, strength="low",
            is_retrograde=False, natal_position=0, transit_position=60.0,
            sector="fire", weight=0.5,
            bazi_resonance=BaziResonance(element="fire", type="gleichklang", intensity="gering"),
        )
        vec_tight = _transit_wuxing_vector([tight_planet])
        vec_loose = _transit_wuxing_vector([loose_planet])
        assert vec_tight.feuer > vec_loose.feuer

    def test_amplification_preserves_element_assignment(self):
        """Amplification should not change which element a planet maps to."""
        planet = _planet("wood", weight=0.6)
        vec = _transit_wuxing_vector([planet])
        assert vec.holz > 0
        assert vec.feuer == 0


# ── build_evidence ──────────────────────────────────────────────────────────

class TestBuildEvidence:
    def test_contains_formula_and_params(self):
        natal = WuXingVector(0.3, 0.2, 0.2, 0.2, 0.1)
        transit = WuXingVector(0.1, 0.4, 0.2, 0.2, 0.1)
        ev = build_evidence(natal, transit, 0.72)
        assert "dot" in ev.resonance_formula
        assert ev.parameters["harmony_index"] == 0.72
        assert "natal_vector" in ev.parameters
        assert "transit_vector" in ev.parameters
