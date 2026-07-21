"""Tests for decanates and Egyptian Terms (bounds) — TASK-decanates-terms."""
from __future__ import annotations

import pytest

from bazi_engine.decanates_terms import (
    DECANATE_MATCH_BOOST,
    TERM_MATCH_BOOST,
    Decanate,
    SubSignRulers,
    Term,
    decanate_match,
    decanate_ruler,
    get_decanate,
    get_sub_sign_rulers,
    get_term,
    sub_sign_multiplier,
    term_match,
    term_ruler,
)

# ── Decanates ────────────────────────────────────────────────────────────────


class TestGetDecanate:
    def test_aries_first_decan_mars(self):
        d = get_decanate(0.0)
        assert d.sign_index == 0
        assert d.decan_index == 0
        assert d.ruler == "Mars"
        assert d.start_degree == 0.0
        assert d.end_degree == 10.0

    def test_aries_second_decan_sun(self):
        d = get_decanate(15.0)
        assert d.sign_index == 0
        assert d.decan_index == 1
        assert d.ruler == "Sun"
        assert d.start_degree == 10.0
        assert d.end_degree == 20.0

    def test_aries_third_decan_jupiter(self):
        d = get_decanate(25.0)
        assert d.sign_index == 0
        assert d.decan_index == 2
        assert d.ruler == "Jupiter"
        assert d.start_degree == 20.0
        assert d.end_degree == 30.0

    def test_decan_boundary_at_10_belongs_to_second(self):
        # 10° exactly is the start of the second decan, not the first.
        assert get_decanate(10.0).decan_index == 1
        assert get_decanate(10.0).ruler == "Sun"

    def test_decan_boundary_at_20_belongs_to_third(self):
        assert get_decanate(20.0).decan_index == 2
        assert get_decanate(20.0).ruler == "Jupiter"

    def test_pisces_third_decan_mars(self):
        d = get_decanate(355.0)
        assert d.sign_index == 11
        assert d.decan_index == 2
        assert d.ruler == "Mars"
        assert d.start_degree == 350.0
        assert d.end_degree == 360.0

    def test_wraps_at_360(self):
        # 360 wraps to 0 → Aries first decan
        assert get_decanate(360.0).ruler == "Mars"
        assert get_decanate(360.0).sign_index == 0

    def test_negative_longitude_wraps(self):
        # -10 = 350 → Pisces third decan
        assert get_decanate(-10.0).sign_index == 11
        assert get_decanate(-10.0).decan_index == 2

    def test_returns_frozen_dataclass(self):
        d = get_decanate(0.0)
        assert isinstance(d, Decanate)
        with pytest.raises((AttributeError, Exception)):
            d.ruler = "Saturn"  # type: ignore[misc]


class TestDecanateRulerCoverage:
    """Spot-check that every sign's three decans use the expected element rotation."""

    def test_leo_rulers(self):
        # Leo → Sun, Jupiter (Sagittarius), Mars (Aries)
        assert decanate_ruler(120.0) == "Sun"
        assert decanate_ruler(135.0) == "Jupiter"
        assert decanate_ruler(145.0) == "Mars"

    def test_capricorn_rulers(self):
        # Capricorn (sign 9) → Saturn, Venus (Taurus), Mercury (Virgo)
        assert decanate_ruler(270.0) == "Saturn"
        assert decanate_ruler(280.0) == "Venus"
        assert decanate_ruler(290.0) == "Mercury"

    def test_cancer_rulers(self):
        # Cancer (sign 3) → Moon, Mars (Scorpio), Jupiter (Pisces)
        assert decanate_ruler(90.0) == "Moon"
        assert decanate_ruler(100.0) == "Mars"
        assert decanate_ruler(110.0) == "Jupiter"


# ── Egyptian Terms ───────────────────────────────────────────────────────────


class TestGetTerm:
    def test_aries_first_term_jupiter(self):
        # Aries: Jupiter 0–6, Venus 6–12, Mercury 12–20, Mars 20–25, Saturn 25–30
        t = get_term(0.0)
        assert t.sign_index == 0
        assert t.ruler == "Jupiter"
        assert t.start_degree == 0.0
        assert t.end_degree == 6.0

    def test_aries_venus_at_8_degrees(self):
        t = get_term(8.0)
        assert t.ruler == "Venus"
        assert t.start_degree == 6.0
        assert t.end_degree == 12.0

    def test_aries_mercury_at_15_degrees(self):
        t = get_term(15.0)
        assert t.ruler == "Mercury"

    def test_aries_mars_at_22_degrees(self):
        t = get_term(22.0)
        assert t.ruler == "Mars"
        assert t.start_degree == 20.0
        assert t.end_degree == 25.0

    def test_aries_saturn_at_28_degrees(self):
        t = get_term(28.0)
        assert t.ruler == "Saturn"
        assert t.start_degree == 25.0
        assert t.end_degree == 30.0

    def test_term_boundary_at_6_belongs_to_venus(self):
        # 6° exactly: Jupiter ends at 6 (exclusive), Venus starts at 6
        assert get_term(6.0).ruler == "Venus"

    def test_pisces_last_term_saturn(self):
        # Pisces: Venus 0–12, Jupiter 12–16, Mercury 16–19, Mars 19–28, Saturn 28–30
        t = get_term(330.0 + 29.5)  # 359.5°
        assert t.sign_index == 11
        assert t.ruler == "Saturn"
        assert t.start_degree == 358.0
        assert t.end_degree == 360.0

    def test_term_wraps_at_360(self):
        # 360 wraps to 0 → Aries Jupiter term
        assert get_term(360.0).ruler == "Jupiter"

    def test_negative_longitude_wraps(self):
        # -1 = 359 → Pisces Saturn (28–30)
        assert get_term(-1.0).sign_index == 11
        assert get_term(-1.0).ruler == "Saturn"

    def test_returns_frozen_dataclass(self):
        t = get_term(0.0)
        assert isinstance(t, Term)
        with pytest.raises((AttributeError, Exception)):
            t.ruler = "Sun"  # type: ignore[misc]


class TestEgyptianTermsTableIntegrity:
    """The Egyptian Terms table is canonical — every sign must total 30°
    and use only the five visible non-luminary planets."""

    VISIBLE_NON_LUMINARIES = {"Mercury", "Venus", "Mars", "Jupiter", "Saturn"}

    def test_every_sign_totals_30_degrees(self):
        # Walk the term boundaries for each sign and assert the last cumulative
        # bound is 30° exactly.
        from bazi_engine.decanates_terms import _EGYPTIAN_TERMS
        for sign_idx, terms in _EGYPTIAN_TERMS.items():
            assert terms[-1][1] == 30, f"Sign {sign_idx} does not total 30°"

    def test_all_terms_use_five_visible_planets(self):
        from bazi_engine.decanates_terms import _EGYPTIAN_TERMS
        for sign_idx, terms in _EGYPTIAN_TERMS.items():
            rulers = {ruler for ruler, _ in terms}
            assert rulers <= self.VISIBLE_NON_LUMINARIES, (
                f"Sign {sign_idx} uses non-canonical ruler(s): "
                f"{rulers - self.VISIBLE_NON_LUMINARIES}"
            )

    def test_each_sign_has_five_terms(self):
        from bazi_engine.decanates_terms import _EGYPTIAN_TERMS
        for sign_idx, terms in _EGYPTIAN_TERMS.items():
            assert len(terms) == 5, f"Sign {sign_idx} has {len(terms)} terms, expected 5"

    def test_term_bounds_strictly_increasing(self):
        """No zero-width terms; bounds must be strictly monotonic."""
        from bazi_engine.decanates_terms import _EGYPTIAN_TERMS
        for sign_idx, terms in _EGYPTIAN_TERMS.items():
            ends = [end for _, end in terms]
            for prev, curr in zip(ends, ends[1:]):
                assert curr > prev, (
                    f"Sign {sign_idx} has non-increasing term bound at {prev}->{curr}"
                )


# ── Match boosts ─────────────────────────────────────────────────────────────


class TestMatchHelpers:
    def test_decanate_match_true_for_aries_first_decan_mars(self):
        assert decanate_match("Mars", 5.0) is True

    def test_decanate_match_false_for_wrong_planet(self):
        assert decanate_match("Venus", 5.0) is False

    def test_term_match_true_for_aries_first_term_jupiter(self):
        assert term_match("Jupiter", 3.0) is True

    def test_term_match_false_for_wrong_planet(self):
        assert term_match("Sun", 3.0) is False

    def test_sub_sign_multiplier_neither_returns_one(self):
        # Aries 5°: decan ruler Mars, term ruler Jupiter — Sun matches neither
        assert sub_sign_multiplier("Sun", 5.0) == 1.0

    def test_sub_sign_multiplier_decan_only(self):
        # Aries 5°: decan ruler Mars, term ruler Jupiter
        # Mars matches decan, not term
        assert sub_sign_multiplier("Mars", 5.0) == DECANATE_MATCH_BOOST

    def test_sub_sign_multiplier_term_only(self):
        # Aries 5°: decan Mars, term Jupiter — Jupiter matches term only
        assert sub_sign_multiplier("Jupiter", 5.0) == TERM_MATCH_BOOST

    def test_sub_sign_multiplier_both_compounds(self):
        # Find a longitude where decan ruler == term ruler.
        # Aries 22°: decan = Jupiter (20–30), term = Mars (20–25). Not a match.
        # Leo 0°: decan = Sun, term = Jupiter (Leo: Jupiter 0–6).
        # Capricorn 0°: decan = Saturn (270–280), term = Mercury (Cap: Mercury 0–7). No.
        # Try Libra 0°: decan = Venus (180–190), term = Saturn (Libra: Saturn 0–6). No.
        # Cancer 0°: decan = Moon (90–100), term = Mars (Cancer: Mars 0–7). No.
        # Pick a constructed case: Aries 22° (decan 20–30 = Jupiter; term 20–25 = Mars).
        # Force a true match by checking a known-rare case:
        #   Sagittarius 0–12°: decan 0–10 = Jupiter; term 0–12 = Jupiter. Both match!
        assert decanate_ruler(245.0) == "Jupiter"
        assert term_ruler(245.0) == "Jupiter"
        expected = DECANATE_MATCH_BOOST * TERM_MATCH_BOOST
        assert sub_sign_multiplier("Jupiter", 245.0) == pytest.approx(expected)


# ── Aggregator ───────────────────────────────────────────────────────────────


class TestSubSignRulersAggregator:
    def test_returns_both_classifications(self):
        srs = get_sub_sign_rulers(15.0)
        assert isinstance(srs, SubSignRulers)
        assert srs.longitude == 15.0
        assert srs.decanate.ruler == "Sun"          # Aries 15° → 2nd decan = Sun
        assert srs.term.ruler == "Mercury"          # Aries 15° → Mercury term (12–20)

    def test_aggregator_is_frozen(self):
        srs = get_sub_sign_rulers(15.0)
        with pytest.raises((AttributeError, Exception)):
            srs.longitude = 0.0  # type: ignore[misc]


# ── Boost constants sanity ───────────────────────────────────────────────────


class TestBoostConstants:
    def test_decanate_boost_is_modest_uplift(self):
        assert 1.0 < DECANATE_MATCH_BOOST < 1.2

    def test_term_boost_is_modest_uplift(self):
        assert 1.0 < TERM_MATCH_BOOST < 1.2

    def test_decanate_boost_at_least_as_strong_as_term(self):
        # Decan rulership is conventionally a stronger signal than terms;
        # the boost should reflect that ordering.
        assert DECANATE_MATCH_BOOST >= TERM_MATCH_BOOST
