"""
test_routers_shared.py — Unit tests for bazi_engine/routers/shared.py

Tests format_pillar() and domain constants in isolation.
"""
from __future__ import annotations

import pytest

from bazi_engine.constants import BRANCHES, STEMS
from bazi_engine.routers.shared import (
    BRANCH_TO_ANIMAL,
    STEM_TO_ELEMENT,
    ZODIAC_SIGNS_DE,
    format_pillar,
)
from bazi_engine.types import Pillar

VALID_ELEMENTS = {"Holz", "Feuer", "Erde", "Metall", "Wasser"}
VALID_ANIMALS_DE = {
    "Ratte", "Ochse", "Tiger", "Hase", "Drache", "Schlange",
    "Pferd", "Ziege", "Affe", "Hahn", "Hund", "Schwein",
}


class TestZodiacSignsDe:
    def test_twelve_signs(self):
        assert len(ZODIAC_SIGNS_DE) == 12

    def test_widder_is_first(self):
        assert ZODIAC_SIGNS_DE[0] == "Widder"

    def test_fische_is_last(self):
        assert ZODIAC_SIGNS_DE[-1] == "Fische"

    def test_no_duplicates(self):
        assert len(ZODIAC_SIGNS_DE) == len(set(ZODIAC_SIGNS_DE))


class TestStemToElement:
    def test_all_ten_stems_present(self):
        assert set(STEM_TO_ELEMENT.keys()) == set(STEMS)

    def test_all_values_are_valid_elements(self):
        for stem, elem in STEM_TO_ELEMENT.items():
            assert elem in VALID_ELEMENTS, f"{stem} → {elem!r}"

    def test_jia_yi_are_holz(self):
        assert STEM_TO_ELEMENT["Jia"] == "Holz"
        assert STEM_TO_ELEMENT["Yi"]  == "Holz"

    def test_bing_ding_are_feuer(self):
        assert STEM_TO_ELEMENT["Bing"] == "Feuer"
        assert STEM_TO_ELEMENT["Ding"] == "Feuer"

    def test_wu_ji_are_erde(self):
        assert STEM_TO_ELEMENT["Wu"] == "Erde"
        assert STEM_TO_ELEMENT["Ji"] == "Erde"

    def test_geng_xin_are_metall(self):
        assert STEM_TO_ELEMENT["Geng"] == "Metall"
        assert STEM_TO_ELEMENT["Xin"]  == "Metall"

    def test_ren_gui_are_wasser(self):
        assert STEM_TO_ELEMENT["Ren"] == "Wasser"
        assert STEM_TO_ELEMENT["Gui"] == "Wasser"


class TestBranchToAnimal:
    def test_all_twelve_branches_present(self):
        assert set(BRANCH_TO_ANIMAL.keys()) == set(BRANCHES)

    def test_zi_is_ratte(self):
        assert BRANCH_TO_ANIMAL["Zi"] == "Ratte"

    def test_hai_is_schwein(self):
        assert BRANCH_TO_ANIMAL["Hai"] == "Schwein"

    def test_all_animals_are_valid(self):
        for branch, animal in BRANCH_TO_ANIMAL.items():
            assert animal in VALID_ANIMALS_DE, f"{branch} → {animal!r}"

    def test_no_duplicate_animals(self):
        assert len(BRANCH_TO_ANIMAL.values()) == len(set(BRANCH_TO_ANIMAL.values()))


class TestFormatPillar:
    @pytest.mark.parametrize("stem_idx,branch_idx", [
        (0, 0),   # Jia-Zi
        (1, 1),   # Yi-Chou
        (9, 11),  # Gui-Hai
        (4, 6),   # Wu-Wu (same name, different things)
    ])
    def test_returns_dict_with_required_keys(self, stem_idx, branch_idx):
        p = Pillar(stem_idx, branch_idx)
        result = format_pillar(p)
        assert {"stamm", "zweig", "tier", "element"} == result.keys()

    def test_jia_zi_correct(self):
        p = Pillar(0, 0)  # Jia-Zi
        result = format_pillar(p)
        assert result["stamm"]   == "Jia"
        assert result["zweig"]   == "Zi"
        assert result["tier"]    == "Ratte"
        assert result["element"] == "Holz"

    def test_gui_hai_correct(self):
        p = Pillar(9, 11)  # Gui-Hai
        result = format_pillar(p)
        assert result["stamm"]   == "Gui"
        assert result["zweig"]   == "Hai"
        assert result["tier"]    == "Schwein"
        assert result["element"] == "Wasser"

    def test_element_always_valid(self):
        for stem_idx in range(10):
            for branch_idx in range(12):
                p = Pillar(stem_idx, branch_idx)
                result = format_pillar(p)
                assert result["element"] in VALID_ELEMENTS

    def test_all_values_are_strings(self):
        p = Pillar(0, 0)
        for key, val in format_pillar(p).items():
            assert isinstance(val, str), f"Key {key!r}: expected str, got {type(val)}"
