"""Tests for impact_resonance.py — BaZi resonance computation."""
from __future__ import annotations

import pytest

from bazi_engine.impact_resonance import (
    compute_bazi_resonance,
    day_master_element,
    determine_intensity,
    determine_resonance_type,
    enrich_active_planets,
    planet_element,
)
from bazi_engine.impact_types import ActivePlanet, BaziResonance

# ── day_master_element ──────────────────────────────────────────────────────

class TestDayMasterElement:
    def test_jia_is_wood(self):
        assert day_master_element("Jia") == "wood"

    def test_bing_is_fire(self):
        assert day_master_element("Bing") == "fire"

    def test_wu_is_earth(self):
        assert day_master_element("Wu") == "earth"

    def test_geng_is_metal(self):
        assert day_master_element("Geng") == "metal"

    def test_ren_is_water(self):
        assert day_master_element("Ren") == "water"

    def test_all_ten_stems_have_elements(self):
        from bazi_engine.constants import STEMS
        for stem in STEMS:
            elem = day_master_element(stem)
            assert elem in ("wood", "fire", "earth", "metal", "water")

    def test_unknown_stem_raises(self):
        with pytest.raises(ValueError, match="Unknown stem"):
            day_master_element("InvalidStem")


# ── planet_element ──────────────────────────────────────────────────────────

class TestPlanetElement:
    def test_sun_is_fire(self):
        assert planet_element("sun") == "fire"

    def test_moon_is_water(self):
        assert planet_element("moon") == "water"

    def test_jupiter_is_wood(self):
        assert planet_element("jupiter") == "wood"

    def test_venus_is_metal(self):
        assert planet_element("venus") == "metal"

    def test_saturn_is_earth(self):
        assert planet_element("saturn") == "earth"

    def test_mercury_returns_first_dual_element(self):
        # Mercury is ["Erde", "Metall"] → earth
        assert planet_element("mercury") == "earth"

    def test_unknown_planet_defaults_to_earth(self):
        assert planet_element("ceres") == "earth"


# ── determine_resonance_type ────────────────────────────────────────────────

class TestDetermineResonanceType:
    def test_same_element_is_gleichklang(self):
        assert determine_resonance_type("fire", "fire") == "gleichklang"

    def test_transit_nourishes_master_is_naehrung(self):
        # Wood generates Fire → wood nourishes fire (transit=wood, master=fire)
        assert determine_resonance_type("fire", "wood") == "naehrung"

    def test_master_produces_transit_is_naehrung(self):
        # Fire generates Earth → fire produces earth (master=fire, transit=earth)
        assert determine_resonance_type("fire", "earth") == "naehrung"

    def test_transit_controls_master_is_kontrolle(self):
        # Water controls Fire → water controls fire (transit=water, master=fire)
        assert determine_resonance_type("fire", "water") == "kontrolle"

    def test_master_controls_transit_is_kontrolle(self):
        # Fire controls Metal → fire controls metal (master=fire, transit=metal)
        assert determine_resonance_type("fire", "metal") == "kontrolle"

    def test_all_pairs_covered(self):
        """Every pair of elements should produce a non-neutral type."""
        elements = ["wood", "fire", "earth", "metal", "water"]
        for master in elements:
            for transit in elements:
                result = determine_resonance_type(master, transit)
                assert result in ("gleichklang", "naehrung", "kontrolle", "neutral")
                if master != transit:
                    assert result != "neutral", f"{master} vs {transit} should not be neutral"


# ── determine_intensity ─────────────────────────────────────────────────────

class TestDetermineIntensity:
    def test_tight_orb_high_weight_is_stark(self):
        assert determine_intensity(orb=0.5, weight=0.9) == "stark"

    def test_medium_orb_medium_weight_is_mittel(self):
        assert determine_intensity(orb=4.0, weight=0.5) == "mittel"

    def test_loose_orb_low_weight_is_gering(self):
        assert determine_intensity(orb=7.5, weight=0.2) == "gering"


# ── compute_bazi_resonance ──────────────────────────────────────────────────

class TestComputeBaziResonance:
    def test_mars_with_fire_master_is_gleichklang(self):
        res = compute_bazi_resonance("fire", "mars", orb=2.0, weight=0.8)
        assert res.element == "fire"
        assert res.type == "gleichklang"

    def test_jupiter_with_fire_master_is_naehrung(self):
        res = compute_bazi_resonance("fire", "jupiter", orb=3.0, weight=0.6)
        assert res.element == "wood"
        assert res.type == "naehrung"

    def test_moon_with_fire_master_is_kontrolle(self):
        res = compute_bazi_resonance("fire", "moon", orb=1.0, weight=0.7)
        assert res.element == "water"
        assert res.type == "kontrolle"

    def test_result_is_frozen(self):
        res = compute_bazi_resonance("fire", "mars", orb=2.0, weight=0.8)
        with pytest.raises(Exception):
            res.type = "neutral"


# ── enrich_active_planets ───────────────────────────────────────────────────

def _placeholder_planet() -> ActivePlanet:
    return ActivePlanet(
        planet="mars",
        aspect="conjunction",
        orb=2.0,
        strength="high",
        is_retrograde=False,
        natal_position=120.0,
        transit_position=122.0,
        sector="fire",
        weight=0.85,
        bazi_resonance=BaziResonance(element="fire", type="neutral", intensity="gering"),
    )


class TestEnrichActivePlanets:
    def test_replaces_placeholder_resonance(self):
        planets = [_placeholder_planet()]
        enriched = enrich_active_planets(planets, "fire")
        assert len(enriched) == 1
        assert enriched[0].bazi_resonance.type != "neutral" or enriched[0].bazi_resonance.element == "fire"
        # Mars is fire, day master is fire → gleichklang
        assert enriched[0].bazi_resonance.type == "gleichklang"

    def test_does_not_mutate_input(self):
        planets = [_placeholder_planet()]
        enriched = enrich_active_planets(planets, "fire")
        assert planets[0].bazi_resonance.type == "neutral"  # original unchanged
        assert enriched[0].bazi_resonance.type == "gleichklang"

    def test_empty_list_returns_empty(self):
        assert enrich_active_planets([], "wood") == []

    def test_multiple_planets_enriched(self):
        p1 = _placeholder_planet()
        p2 = ActivePlanet(
            planet="moon", aspect="opposition", orb=1.0, strength="high",
            is_retrograde=False, natal_position=45.0, transit_position=225.0,
            sector="water", weight=0.7,
            bazi_resonance=BaziResonance(element="water", type="neutral", intensity="gering"),
        )
        enriched = enrich_active_planets([p1, p2], "fire")
        assert enriched[0].bazi_resonance.type == "gleichklang"  # mars=fire, master=fire
        assert enriched[1].bazi_resonance.type == "kontrolle"    # moon=water controls fire

    def test_intensity_varies_by_orb_and_weight(self):
        tight = ActivePlanet(
            planet="mars", aspect="conjunction", orb=0.5, strength="high",
            is_retrograde=False, natal_position=0, transit_position=0.5,
            sector="fire", weight=0.9,
            bazi_resonance=BaziResonance(element="fire", type="neutral", intensity="gering"),
        )
        loose = ActivePlanet(
            planet="mars", aspect="sextile", orb=7.0, strength="low",
            is_retrograde=False, natal_position=0, transit_position=60.0,
            sector="fire", weight=0.3,
            bazi_resonance=BaziResonance(element="fire", type="neutral", intensity="gering"),
        )
        enriched = enrich_active_planets([tight, loose], "fire")
        assert enriched[0].bazi_resonance.intensity == "stark"
        assert enriched[1].bazi_resonance.intensity == "gering"
