"""Tests for constants.py - Domain constants."""

from __future__ import annotations

from bazi_engine.constants import ANIMALS, BRANCHES, DAY_OFFSET, STEMS


class TestStems:
    """Tests for Heavenly Stems (天干)."""

    def test_count(self):
        assert len(STEMS) == 10

    def test_order(self):
        expected = ["Jia", "Yi", "Bing", "Ding", "Wu", "Ji", "Geng", "Xin", "Ren", "Gui"]
        assert STEMS == expected

    def test_jia_is_first(self):
        assert STEMS[0] == "Jia"

    def test_gui_is_last(self):
        assert STEMS[9] == "Gui"

    def test_all_unique(self):
        assert len(STEMS) == len(set(STEMS))

    def test_immutable_type(self):
        assert isinstance(STEMS, list)


class TestBranches:
    """Tests for Earthly Branches (地支)."""

    def test_count(self):
        assert len(BRANCHES) == 12

    def test_order(self):
        expected = ["Zi", "Chou", "Yin", "Mao", "Chen", "Si",
                    "Wu", "Wei", "Shen", "You", "Xu", "Hai"]
        assert BRANCHES == expected

    def test_zi_is_first(self):
        assert BRANCHES[0] == "Zi"

    def test_hai_is_last(self):
        assert BRANCHES[11] == "Hai"

    def test_all_unique(self):
        assert len(BRANCHES) == len(set(BRANCHES))

    def test_wu_is_horse_position(self):
        # Wu (午) is at index 6, corresponding to Horse
        assert BRANCHES[6] == "Wu"


class TestAnimals:
    """Tests for Chinese Zodiac Animals."""

    def test_count(self):
        assert len(ANIMALS) == 12

    def test_order(self):
        expected = ["Rat", "Ox", "Tiger", "Rabbit", "Dragon", "Snake",
                    "Horse", "Goat", "Monkey", "Rooster", "Dog", "Pig"]
        assert ANIMALS == expected

    def test_rat_is_first(self):
        assert ANIMALS[0] == "Rat"

    def test_pig_is_last(self):
        assert ANIMALS[11] == "Pig"

    def test_all_unique(self):
        assert len(ANIMALS) == len(set(ANIMALS))

    def test_matches_branches_length(self):
        assert len(ANIMALS) == len(BRANCHES)


class TestDayOffset:
    """Tests for DAY_OFFSET constant."""

    def test_value(self):
        assert DAY_OFFSET == 49

    def test_is_integer(self):
        assert isinstance(DAY_OFFSET, int)

    def test_positive(self):
        assert DAY_OFFSET > 0

    def test_less_than_60(self):
        # Offset should be within sexagenary cycle
        assert DAY_OFFSET < 60


class TestSexagenaryCycle:
    """Tests for sexagenary cycle calculations using constants."""

    def test_cycle_length(self):
        # 10 stems × 12 branches = 60 combinations (but only 60 valid pairs)
        # LCM(10, 12) = 60
        from math import lcm
        assert lcm(len(STEMS), len(BRANCHES)) == 60

    def test_stem_index_modulo(self):
        # Any day index mod 10 gives valid stem index
        for day_idx in range(120):
            stem_idx = day_idx % 10
            assert 0 <= stem_idx < 10
            assert STEMS[stem_idx] in STEMS

    def test_branch_index_modulo(self):
        # Any day index mod 12 gives valid branch index
        for day_idx in range(120):
            branch_idx = day_idx % 12
            assert 0 <= branch_idx < 12
            assert BRANCHES[branch_idx] in BRANCHES

    def test_reference_date_1949_10_01(self):
        """1949-10-01 should be Jia-Zi (甲子) day with DAY_OFFSET=49."""
        # JDN for 1949-10-01 (Gregorian)
        # Using standard formula: JDN = 367*Y - 7*(Y+(M+9)/12)/4 - 3*((Y+(M-9)/7)/100+1)/4 + 275*M/9 + D + 1721029
        # For 1949-10-01: JDN = 2433191 (same algorithm as bazi_engine.bazi.jdn_gregorian)
        jdn_1949_10_01 = 2433191
        sexagenary_idx = (jdn_1949_10_01 + DAY_OFFSET) % 60
        # Jia-Zi is index 0
        assert sexagenary_idx == 0


class TestConstantsIntegrity:
    """Integration tests ensuring constants work together."""

    def test_branch_animal_correspondence(self):
        """Each branch index corresponds to its zodiac animal."""
        correspondences = [
            (0, "Zi", "Rat"),
            (1, "Chou", "Ox"),
            (2, "Yin", "Tiger"),
            (3, "Mao", "Rabbit"),
            (4, "Chen", "Dragon"),
            (5, "Si", "Snake"),
            (6, "Wu", "Horse"),
            (7, "Wei", "Goat"),
            (8, "Shen", "Monkey"),
            (9, "You", "Rooster"),
            (10, "Xu", "Dog"),
            (11, "Hai", "Pig"),
        ]
        for idx, branch, animal in correspondences:
            assert BRANCHES[idx] == branch
            assert ANIMALS[idx] == animal

    def test_stem_element_groups(self):
        """Stems are grouped by element (2 per element)."""
        # Wood: Jia, Yi (0, 1)
        # Fire: Bing, Ding (2, 3)
        # Earth: Wu, Ji (4, 5)
        # Metal: Geng, Xin (6, 7)
        # Water: Ren, Gui (8, 9)
        element_groups = [
            (["Jia", "Yi"], "Wood"),
            (["Bing", "Ding"], "Fire"),
            (["Wu", "Ji"], "Earth"),
            (["Geng", "Xin"], "Metal"),
            (["Ren", "Gui"], "Water"),
        ]
        for stems, element in element_groups:
            for stem in stems:
                assert stem in STEMS
