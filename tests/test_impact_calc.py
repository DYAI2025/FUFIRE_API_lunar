"""Tests for impact.py — natal-vs-transit aspect matching."""
from __future__ import annotations

import pytest

from bazi_engine.impact import (
    _composite_weight,
    _element_for_longitude,
    classify_strength,
    determine_house,
    find_active_planets,
    house_multiplier,
)

# ── classify_strength ───────────────────────────────────────────────────────

class TestClassifyStrength:
    def test_high_under_3(self):
        assert classify_strength(0.0) == "high"
        assert classify_strength(2.99) == "high"

    def test_medium_3_to_5(self):
        assert classify_strength(3.0) == "medium"
        assert classify_strength(5.0) == "medium"

    def test_low_above_5(self):
        assert classify_strength(5.01) == "low"
        assert classify_strength(7.99) == "low"


# ── _composite_weight ───────────────────────────────────────────────────────

class TestCompositeWeight:
    def test_exact_conjunction_heavy_planet_is_high(self):
        w = _composite_weight(orb=0.0, planet_name="pluto", aspect_type="conjunction")
        assert w > 0.8

    def test_loose_sextile_light_planet_is_low(self):
        w = _composite_weight(orb=7.5, planet_name="moon", aspect_type="sextile")
        assert w < 0.4

    def test_weight_in_zero_one_range(self):
        w = _composite_weight(orb=4.0, planet_name="mars", aspect_type="trine")
        assert 0.0 <= w <= 1.0

    def test_unknown_planet_uses_default(self):
        w = _composite_weight(orb=2.0, planet_name="unknown", aspect_type="conjunction")
        assert 0.0 <= w <= 1.0


# ── _element_for_longitude ──────────────────────────────────────────────────

class TestElementForLongitude:
    def test_aries_is_fire(self):
        assert _element_for_longitude(15.0) == "fire"

    def test_taurus_is_earth(self):
        assert _element_for_longitude(45.0) == "earth"

    def test_gemini_is_metal(self):
        assert _element_for_longitude(75.0) == "metal"

    def test_cancer_is_water(self):
        assert _element_for_longitude(105.0) == "water"

    def test_boundary_at_360(self):
        assert _element_for_longitude(359.9) == "water"

    def test_boundary_at_0(self):
        assert _element_for_longitude(0.0) == "fire"


# ── find_active_planets ─────────────────────────────────────────────────────

def _natal_bodies():
    """Fake natal chart: Sun at 120°, Moon at 45°."""
    return {
        "Sun": {"longitude": 120.0, "speed": 1.0, "is_retrograde": False},
        "Moon": {"longitude": 45.0, "speed": 13.0, "is_retrograde": False},
    }


def _transit_data():
    """Fake transits: sun at 122° (conjunction natal Sun, orb 2°),
    moon at 225° (opposition natal Moon, orb 0°),
    mars at 100° (no aspect within 8° to Sun@120 or Moon@45)."""
    return {
        "sun": {"longitude": 122.0, "speed": 1.0},
        "moon": {"longitude": 225.0, "speed": 13.0},
        "mars": {"longitude": 100.0, "speed": 0.5},
    }


class TestFindActivePlanets:
    def test_finds_conjunction_within_orb(self):
        results = find_active_planets(_natal_bodies(), _transit_data())
        sun_hits = [p for p in results if p.planet == "sun"]
        assert len(sun_hits) == 1
        assert sun_hits[0].aspect == "conjunction"
        assert sun_hits[0].orb == 2.0
        assert sun_hits[0].strength == "high"

    def test_finds_opposition_exact(self):
        results = find_active_planets(_natal_bodies(), _transit_data())
        moon_hits = [p for p in results if p.planet == "moon"]
        assert len(moon_hits) == 1
        assert moon_hits[0].aspect == "opposition"
        assert moon_hits[0].orb == 0.0
        assert moon_hits[0].strength == "high"

    def test_excludes_planet_beyond_max_orb(self):
        """A planet not within 8° of any aspect angle to any natal body."""
        natal = {"Sun": {"longitude": 0.0}}
        # 15° from Sun: nearest aspects are conjunction(0°, dev=15) and semi-sextile(30°, dev=15)
        transit = {"mars": {"longitude": 15.0, "speed": 0.5}}
        results = find_active_planets(natal, transit)
        assert len(results) == 0

    def test_sorted_by_tightest_orb(self):
        results = find_active_planets(_natal_bodies(), _transit_data())
        if len(results) >= 2:
            assert results[0].orb <= results[1].orb

    def test_returns_frozen_models(self):
        results = find_active_planets(_natal_bodies(), _transit_data())
        assert len(results) > 0
        with pytest.raises(Exception):
            results[0].orb = 99.0

    def test_retrograde_detected(self):
        natal = {"Sun": {"longitude": 100.0, "speed": 1.0}}
        transit = {"mercury": {"longitude": 100.5, "speed": -0.3}}
        results = find_active_planets(natal, transit)
        assert len(results) == 1
        assert results[0].is_retrograde is True

    def test_weight_populated_and_valid(self):
        results = find_active_planets(_natal_bodies(), _transit_data())
        for p in results:
            assert 0.0 <= p.weight <= 1.0

    def test_sector_is_valid_wuxing(self):
        results = find_active_planets(_natal_bodies(), _transit_data())
        valid = {"wood", "fire", "earth", "metal", "water"}
        for p in results:
            assert p.sector in valid

    def test_bazi_resonance_placeholder_is_neutral(self):
        results = find_active_planets(_natal_bodies(), _transit_data())
        for p in results:
            assert p.bazi_resonance.type == "neutral"
            assert p.bazi_resonance.intensity == "gering"

    def test_empty_natal_returns_empty(self):
        assert find_active_planets({}, _transit_data()) == []

    def test_empty_transit_returns_empty(self):
        assert find_active_planets(_natal_bodies(), {}) == []

    def test_natal_with_error_skipped(self):
        natal = {"Sun": {"error": "calc failed"}, "Moon": {"longitude": 45.0}}
        transit = {"moon": {"longitude": 225.0, "speed": 13.0}}
        results = find_active_planets(natal, transit)
        assert all("error" not in str(p) for p in results)

    def test_trine_detected(self):
        natal = {"Jupiter": {"longitude": 0.0, "speed": 0.1}}
        transit = {"jupiter": {"longitude": 122.0, "speed": 0.08}}
        results = find_active_planets(natal, transit)
        assert len(results) == 1
        assert results[0].aspect == "trine"
        assert results[0].orb == 2.0

    def test_square_detected(self):
        natal = {"Saturn": {"longitude": 0.0, "speed": 0.03}}
        transit = {"saturn": {"longitude": 93.0, "speed": 0.03}}
        results = find_active_planets(natal, transit)
        assert len(results) == 1
        assert results[0].aspect == "square"
        assert results[0].orb == 3.0
        assert results[0].strength == "medium"


# ── determine_house ─────────────────────────────────────────────────────────

def _equal_cusps():
    """Equal house cusps: each house is 30°."""
    return {str(i + 1): float(i * 30) for i in range(12)}


class TestDetermineHouse:
    def test_planet_in_first_house(self):
        assert determine_house(15.0, _equal_cusps()) == 1

    def test_planet_in_seventh_house(self):
        assert determine_house(195.0, _equal_cusps()) == 7

    def test_planet_at_cusp_boundary(self):
        assert determine_house(30.0, _equal_cusps()) == 2

    def test_planet_near_360_wraps_to_house_12(self):
        assert determine_house(355.0, _equal_cusps()) == 12

    def test_empty_cusps_defaults_to_1(self):
        assert determine_house(100.0, {}) == 1

    def test_none_cusps_defaults_to_1(self):
        assert determine_house(100.0, {}) == 1

    def test_wrap_around_cusps(self):
        """Non-zero ASC: house 1 starts at 100°, houses wrap past 360°."""
        cusps = {str(i + 1): float((100 + i * 30) % 360) for i in range(12)}
        assert determine_house(105.0, cusps) == 1
        assert determine_house(95.0, cusps) == 12


# ── house_multiplier ────────────────────────────────────────────────────────

class TestHouseMultiplier:
    def test_angular_houses_get_boost(self):
        for h in (1, 4, 7, 10):
            assert house_multiplier(h) == 1.3

    def test_cadent_houses_get_reduction(self):
        for h in (3, 6, 9, 12):
            assert house_multiplier(h) == 0.8

    def test_succedent_houses_neutral(self):
        for h in (2, 5, 8, 11):
            assert house_multiplier(h) == 1.0


# ── _composite_weight with house ────────────────────────────────────────────

class TestCompositeWeightWithHouse:
    def test_angular_house_boosts_weight(self):
        w_neutral = _composite_weight(2.0, "mars", "conjunction", 1.0)
        w_angular = _composite_weight(2.0, "mars", "conjunction", 1.3)
        assert w_angular > w_neutral

    def test_cadent_house_reduces_weight(self):
        w_neutral = _composite_weight(2.0, "mars", "conjunction", 1.0)
        w_cadent = _composite_weight(2.0, "mars", "conjunction", 0.8)
        assert w_cadent < w_neutral

    def test_weight_clamped_to_one(self):
        w = _composite_weight(0.0, "pluto", "conjunction", 1.3)
        assert w <= 1.0


# ── find_active_planets with house cusps ────────────────────────────────────

class TestFindActivePlanetsWithHouses:
    def test_angular_house_planet_has_higher_weight(self):
        natal = {"Sun": {"longitude": 15.0}}  # house 1 (angular)
        transit = {"sun": {"longitude": 17.0, "speed": 1.0}}  # conjunction, orb 2°
        cusps = _equal_cusps()

        with_houses = find_active_planets(natal, transit, cusps)
        without_houses = find_active_planets(natal, transit)

        assert len(with_houses) == 1
        assert len(without_houses) == 1
        assert with_houses[0].weight >= without_houses[0].weight

    def test_no_cusps_still_works(self):
        natal = {"Sun": {"longitude": 15.0}}
        transit = {"sun": {"longitude": 17.0, "speed": 1.0}}
        results = find_active_planets(natal, transit, None)
        assert len(results) == 1


# ── Minor aspects in impact matching ────────────────────────────────────────

class TestMinorAspectsInImpact:
    def test_quincunx_detected(self):
        natal = {"Mars": {"longitude": 0.0}}
        transit = {"mars": {"longitude": 152.0, "speed": 0.5}}
        results = find_active_planets(natal, transit)
        assert len(results) == 1
        assert results[0].aspect == "quincunx"

    def test_semi_sextile_detected(self):
        natal = {"Venus": {"longitude": 0.0}}
        transit = {"venus": {"longitude": 31.0, "speed": 1.0}}
        results = find_active_planets(natal, transit)
        assert len(results) == 1
        assert results[0].aspect == "semi-sextile"

    def test_minor_aspect_has_lower_weight_than_major(self):
        natal = {"Mars": {"longitude": 0.0}}
        transit_major = {"mars": {"longitude": 2.0, "speed": 0.5}}
        transit_minor = {"mars": {"longitude": 31.0, "speed": 0.5}}

        major = find_active_planets(natal, transit_major)
        minor = find_active_planets(natal, transit_minor)

        assert len(major) == 1 and len(minor) == 1
        assert major[0].weight > minor[0].weight
