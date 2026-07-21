"""
test_wuxing_constants.py — Unit tests for bazi_engine/wuxing/constants.py

Tests domain invariants of the Wu-Xing element mapping:
  - Completeness (all known planets covered)
  - Type consistency (all values str or List[str])
  - WUXING_ORDER covers exactly 5 elements
  - WUXING_INDEX is the inverse of WUXING_ORDER
  - All element names in mappings are valid Wu-Xing elements
"""
from __future__ import annotations

import pytest

from bazi_engine.wuxing.constants import PLANET_TO_WUXING, WUXING_INDEX, WUXING_ORDER

VALID_ELEMENTS = {"Holz", "Feuer", "Erde", "Metall", "Wasser"}

CANONICAL_PLANETS = [
    "Sun", "Moon", "Mercury", "Venus", "Mars",
    "Jupiter", "Saturn", "Uranus", "Neptune", "Pluto",
    "Chiron", "Lilith", "NorthNode", "TrueNorthNode",
]


class TestWuxingOrder:
    def test_exactly_five_elements(self):
        assert len(WUXING_ORDER) == 5

    def test_all_five_elements_present(self):
        assert set(WUXING_ORDER) == VALID_ELEMENTS

    def test_generative_cycle_order(self):
        """Wu Xing generative cycle: Holz → Feuer → Erde → Metall → Wasser."""
        assert WUXING_ORDER == ["Holz", "Feuer", "Erde", "Metall", "Wasser"]

    def test_no_duplicates(self):
        assert len(WUXING_ORDER) == len(set(WUXING_ORDER))


class TestWuxingIndex:
    def test_is_inverse_of_order(self):
        for i, elem in enumerate(WUXING_ORDER):
            assert WUXING_INDEX[elem] == i

    def test_size_matches_order(self):
        assert len(WUXING_INDEX) == len(WUXING_ORDER)

    def test_indices_are_0_to_4(self):
        assert set(WUXING_INDEX.values()) == {0, 1, 2, 3, 4}

    def test_holz_is_0(self):
        assert WUXING_INDEX["Holz"] == 0

    def test_wasser_is_4(self):
        assert WUXING_INDEX["Wasser"] == 4


class TestPlanetToWuxingMapping:
    def test_all_canonical_planets_present(self):
        for planet in CANONICAL_PLANETS:
            assert planet in PLANET_TO_WUXING, f"Missing planet: {planet}"

    @pytest.mark.parametrize("planet", CANONICAL_PLANETS)
    def test_value_type_is_str_or_list(self, planet):
        val = PLANET_TO_WUXING[planet]
        assert isinstance(val, (str, list)), f"{planet}: unexpected type {type(val)}"

    @pytest.mark.parametrize("planet", CANONICAL_PLANETS)
    def test_all_elements_are_valid(self, planet):
        val = PLANET_TO_WUXING[planet]
        elements = val if isinstance(val, list) else [val]
        for e in elements:
            assert e in VALID_ELEMENTS, f"{planet} → {e!r} not in {VALID_ELEMENTS}"

    def test_mercury_is_dual(self):
        """Mercury is the only planet with a list value (day/night duality)."""
        assert isinstance(PLANET_TO_WUXING["Mercury"], list)
        assert len(PLANET_TO_WUXING["Mercury"]) == 2

    def test_only_mercury_is_dual(self):
        dual = [p for p, v in PLANET_TO_WUXING.items() if isinstance(v, list)]
        assert dual == ["Mercury"]

    def test_sun_is_fire(self):
        assert PLANET_TO_WUXING["Sun"] == "Feuer"

    def test_moon_is_water(self):
        assert PLANET_TO_WUXING["Moon"] == "Wasser"

    def test_jupiter_is_wood(self):
        assert PLANET_TO_WUXING["Jupiter"] == "Holz"

    def test_saturn_is_earth(self):
        assert PLANET_TO_WUXING["Saturn"] == "Erde"

    def test_venus_is_metal(self):
        assert PLANET_TO_WUXING["Venus"] == "Metall"

    def test_mars_is_fire(self):
        assert PLANET_TO_WUXING["Mars"] == "Feuer"

    def test_north_node_and_true_north_node_agree(self):
        assert PLANET_TO_WUXING["NorthNode"] == PLANET_TO_WUXING["TrueNorthNode"]
