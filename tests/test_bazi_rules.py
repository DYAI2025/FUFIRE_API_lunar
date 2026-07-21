"""FBP-02-001 — Ruleset-driven derivation helpers.

Today the day-pillar offset is the hardcoded constant
``bazi_engine.constants.DAY_OFFSET = 49``. The ruleset already
carries the day-cycle anchor that *should* define this value
(``spec/rulesets/standard_bazi_2026.json: day_cycle_anchor``).

This module pins the derivation:

    offset = (anchor_sexagenary_index_0based - anchor_jdn) % 60

For the shipped ruleset (anchor_jdn=2419451, anchor_sex_idx=0):

    offset = (0 - 2419451) % 60 = 49

so the new helper is value-equivalent to the historic constant.
When ``day_cycle_anchor`` is corrected under FBP-02-002 the helper
will produce a new offset; the constant stays as a Phase-1 baseline
reference until DEV-2026-005 is mitigated separately.
"""
from __future__ import annotations

import pytest

from bazi_engine.bafe.ruleset_loader import load_ruleset
from bazi_engine.bazi_rules import (
    DEFAULT_RULESET_ID,
    day_offset_from_ruleset,
    load_default_ruleset,
)
from bazi_engine.constants import DAY_OFFSET


def test_day_offset_from_default_ruleset_matches_legacy_constant():
    """Regression: today's anchor must produce the historic offset.

    A change here means the anchor itself moved — investigate before
    accepting. See DEV-2026-004 / FBP-02-002.
    """
    ruleset = load_default_ruleset()
    assert day_offset_from_ruleset(ruleset) == DAY_OFFSET


def test_day_offset_math_explicit():
    """Sanity-check the formula with a synthetic anchor."""
    fake = {
        "day_cycle_anchor": {
            "anchor_jdn": 2419451,
            "anchor_sexagenary_index_0based": 0,
            "anchor_type": "JDN",
            "anchor_verification": "unverified",
        },
    }
    assert day_offset_from_ruleset(fake) == 49


@pytest.mark.parametrize("anchor_jdn,anchor_idx,expected", [
    (2419451, 0, 49),        # canonical
    (2419452, 0, 48),        # +1 day → -1 offset (mod 60)
    (2419451, 1, 50),        # +1 sex idx → +1 offset
    (2419451, 59, 48),       # wraps via mod 60
    (0, 0, 0),               # trivial
])
def test_day_offset_math_parametrized(anchor_jdn, anchor_idx, expected):
    fake = {
        "day_cycle_anchor": {
            "anchor_jdn": anchor_jdn,
            "anchor_sexagenary_index_0based": anchor_idx,
            "anchor_type": "JDN",
            "anchor_verification": "unverified",
        },
    }
    assert day_offset_from_ruleset(fake) == expected


def test_day_offset_rejects_missing_anchor():
    """A ruleset without `day_cycle_anchor` cannot compute an offset."""
    with pytest.raises((KeyError, ValueError)):
        day_offset_from_ruleset({})


def test_day_offset_rejects_non_jdn_anchor_type():
    """Phase 2 supports only JDN anchors. DATE/other types are
    FBP-02-002 follow-ups."""
    fake = {
        "day_cycle_anchor": {
            "anchor_jdn": 2419451,
            "anchor_sexagenary_index_0based": 0,
            "anchor_type": "DATE",   # unsupported in this helper
            "anchor_verification": "unverified",
        },
    }
    with pytest.raises(ValueError):
        day_offset_from_ruleset(fake)


def test_default_ruleset_id_matches_loader():
    """Sanity: the constant we export matches what load_ruleset accepts."""
    rs = load_ruleset(DEFAULT_RULESET_ID)
    assert rs["ruleset_id"] == DEFAULT_RULESET_ID


def test_load_default_ruleset_is_cached():
    """Calling load_default_ruleset() twice returns the same dict
    (lru_cache or equivalent) so callers in compute_bazi() don't hit
    the filesystem per request."""
    a = load_default_ruleset()
    b = load_default_ruleset()
    assert a is b


def test_day_offset_rejects_null_anchor():
    """A ruleset with day_cycle_anchor explicitly null must raise a
    clean ValueError, not an AttributeError from accessing .get on None.
    """
    fake = {"day_cycle_anchor": None}
    with pytest.raises(ValueError, match="day_cycle_anchor"):
        day_offset_from_ruleset(fake)


def test_day_offset_rejects_non_dict_anchor():
    """Anchor must be a dict; lists/strings/ints get a clean error."""
    for bad_value in ([], "JDN", 2419451):
        fake = {"day_cycle_anchor": bad_value}
        with pytest.raises(ValueError, match="day_cycle_anchor"):
            day_offset_from_ruleset(fake)


def test_day_offset_accepts_integer_valued_float_anchor_jdn():
    """For consistency with bafe.ruleset_loader.day_cycle_anchor_status,
    a float anchor_jdn that is integer-valued (e.g. 2419451.0) is
    accepted. Truly fractional values still raise ValueError.
    """
    ok = {
        "day_cycle_anchor": {
            "anchor_jdn": 2419451.0,
            "anchor_sexagenary_index_0based": 0,
            "anchor_type": "JDN",
            "anchor_verification": "unverified",
        },
    }
    assert day_offset_from_ruleset(ok) == 49

    bad = {
        "day_cycle_anchor": {
            "anchor_jdn": 2419451.5,
            "anchor_sexagenary_index_0based": 0,
            "anchor_type": "JDN",
            "anchor_verification": "unverified",
        },
    }
    with pytest.raises(ValueError, match="integer"):
        day_offset_from_ruleset(bad)
