"""Tests for bazi_engine.match.ten_gods (MISSING-002 resolved).

Two independent validations, matching the user's own directive to "use
[the two reference docs] as tables for the calculation logic and validate
with them":

1. ``test_ten_gods_reproduces_full_matrix`` — the closed rule encoded in
   the ruleset's ``ten_gods.relation_to_god`` block is checked against
   EVERY cell of the explicit 10x10 Shi Shen matrix transcribed from
   ``systematisches_handbuch_der_bazi_hehun_kompatibili.md`` (Tabelle 8).

2. ``test_ten_gods_matches_worked_example_charts`` — the SAME rule is
   cross-checked against ``systemische_hehun_kompatibilitaetsanalyse.md``'s
   two worked real-person charts (Person A, Person B), computed through
   the ACTUAL engine (not hand-typed), reproducing the doc's own stated
   Ten-God assignments.

   Person A's hour pillar in that source document carries an internal
   inconsistency: its own computed True Solar Time (WOZ, 14:20:27) falls
   in the Wei (未, 13:00-15:00) bracket per the same source's own hour
   table, yet the document labels the hour Shen (申, 15:00-17:00) — the
   civil-clock bracket, not its own WOZ result. The engine's
   ``time_standard="LMT"`` mode reproduces the document's own WOZ math
   exactly (Ji-Wei, not Geng-Shen) for Person A, and reproduces the FULL
   4-pillar chart (including hour) for Person B without any caveat. This
   test asserts the mathematically-correct LMT-derived values, not the
   source document's mislabeled Person-A hour — the discrepancy is
   documented here, not silently reconciled.
"""
from __future__ import annotations

import itertools

import pytest

from bazi_engine.bazi_rules import load_default_ruleset
from bazi_engine.constants import STEMS
from bazi_engine.match.ten_gods import (
    element_relation,
    stem_polarity,
    ten_god_for_stems,
)

# Ground truth: systematisches_handbuch_der_bazi_hehun_kompatibili.md,
# Tabelle 8 (10x10 Shi Shen matrix), transcribed verbatim (day-master row ->
# target-stem column -> Ten God), translated to the ruleset's English labels.
EXPECTED_TEN_GODS = {
    "Jia": {"Jia": "Friend", "Yi": "RobWealth", "Bing": "EatingGod", "Ding": "HurtingOfficer", "Wu": "IndirectWealth", "Ji": "DirectWealth", "Geng": "SevenKilling", "Xin": "DirectOfficer", "Ren": "IndirectRes", "Gui": "DirectRes"},
    "Yi": {"Jia": "RobWealth", "Yi": "Friend", "Bing": "HurtingOfficer", "Ding": "EatingGod", "Wu": "DirectWealth", "Ji": "IndirectWealth", "Geng": "DirectOfficer", "Xin": "SevenKilling", "Ren": "DirectRes", "Gui": "IndirectRes"},
    "Bing": {"Jia": "IndirectRes", "Yi": "DirectRes", "Bing": "Friend", "Ding": "RobWealth", "Wu": "EatingGod", "Ji": "HurtingOfficer", "Geng": "IndirectWealth", "Xin": "DirectWealth", "Ren": "SevenKilling", "Gui": "DirectOfficer"},
    "Ding": {"Jia": "DirectRes", "Yi": "IndirectRes", "Bing": "RobWealth", "Ding": "Friend", "Wu": "HurtingOfficer", "Ji": "EatingGod", "Geng": "DirectWealth", "Xin": "IndirectWealth", "Ren": "DirectOfficer", "Gui": "SevenKilling"},
    "Wu": {"Jia": "SevenKilling", "Yi": "DirectOfficer", "Bing": "IndirectRes", "Ding": "DirectRes", "Wu": "Friend", "Ji": "RobWealth", "Geng": "EatingGod", "Xin": "HurtingOfficer", "Ren": "IndirectWealth", "Gui": "DirectWealth"},
    "Ji": {"Jia": "DirectOfficer", "Yi": "SevenKilling", "Bing": "DirectRes", "Ding": "IndirectRes", "Wu": "RobWealth", "Ji": "Friend", "Geng": "HurtingOfficer", "Xin": "EatingGod", "Ren": "DirectWealth", "Gui": "IndirectWealth"},
    "Geng": {"Jia": "IndirectWealth", "Yi": "DirectWealth", "Bing": "SevenKilling", "Ding": "DirectOfficer", "Wu": "IndirectRes", "Ji": "DirectRes", "Geng": "Friend", "Xin": "RobWealth", "Ren": "EatingGod", "Gui": "HurtingOfficer"},
    "Xin": {"Jia": "DirectWealth", "Yi": "IndirectWealth", "Bing": "DirectOfficer", "Ding": "SevenKilling", "Wu": "DirectRes", "Ji": "IndirectRes", "Geng": "RobWealth", "Xin": "Friend", "Ren": "HurtingOfficer", "Gui": "EatingGod"},
    "Ren": {"Jia": "EatingGod", "Yi": "HurtingOfficer", "Bing": "IndirectWealth", "Ding": "DirectWealth", "Wu": "SevenKilling", "Ji": "DirectOfficer", "Geng": "IndirectRes", "Xin": "DirectRes", "Ren": "Friend", "Gui": "RobWealth"},
    "Gui": {"Jia": "HurtingOfficer", "Yi": "EatingGod", "Bing": "DirectWealth", "Ding": "IndirectWealth", "Wu": "DirectOfficer", "Ji": "SevenKilling", "Geng": "DirectRes", "Xin": "IndirectRes", "Ren": "RobWealth", "Gui": "Friend"},
}


@pytest.fixture()
def ruleset():
    return load_default_ruleset()


def test_ten_gods_reproduces_full_matrix(ruleset) -> None:
    """The ruleset-driven closed rule reproduces all 100 cells of Tabelle 8."""
    for day_master, target in itertools.product(STEMS, STEMS):
        expected = EXPECTED_TEN_GODS[day_master][target]
        actual = ten_god_for_stems(ruleset, day_master, target)
        assert actual == expected, (
            f"DM={day_master} target={target}: expected {expected}, got {actual}"
        )


def test_stem_polarity_matches_classical_yang_yin() -> None:
    yang = {"Jia", "Bing", "Wu", "Geng", "Ren"}
    for stem in STEMS:
        expected = "yang" if stem in yang else "yin"
        assert stem_polarity(stem) == expected


def test_element_relation_five_way_split() -> None:
    # Wood day master: same=wood, resource=water, output=fire, wealth=earth, officer=metal
    assert element_relation("Holz", "Holz") == "same"
    assert element_relation("Holz", "Wasser") == "resource"
    assert element_relation("Holz", "Feuer") == "output"
    assert element_relation("Holz", "Erde") == "wealth"
    assert element_relation("Holz", "Metall") == "officer"


def _compute_ten_gods_for_person(date: str, tz: str, lon: float, lat: float):
    """Compute a real chart via the engine (LMT standard, matching the
    source document's WOZ methodology) and return {pillar: (stem, ten_god)}."""
    from bazi_engine.bazi import compute_bazi
    from bazi_engine.types import BaziInput

    result = compute_bazi(
        BaziInput(
            birth_local=date,
            timezone=tz,
            longitude_deg=lon,
            latitude_deg=lat,
            time_standard="LMT",
        )
    )
    ruleset = load_default_ruleset()
    day_master = STEMS[result.pillars.day.stem_index]
    pillars = {}
    for name in ("year", "month", "hour"):
        stem = STEMS[getattr(result.pillars, name).stem_index]
        pillars[name] = (stem, ten_god_for_stems(ruleset, day_master, stem))
    return day_master, pillars


def test_ten_gods_matches_worked_example_charts() -> None:
    """Cross-check against systemische_hehun_kompatibilitaetsanalyse.md's
    two worked charts (Person A: 1980-06-24 15:44 Hannover; Person B:
    1990-04-03 20:01 Bergisch Gladbach), computed through the real engine.
    """
    # Person A — DM Wu (戊). Year/Month verified against the source
    # document's own stated Ten-God assignments (Eating God / Indirect
    # Wealth). Hour is asserted against the CORRECT LMT/WOZ-derived value
    # (Ji-Wei -> Rob Wealth), not the source's mislabeled Geng-Shen/Eating
    # God (see module docstring: the source's own WOZ math gives Wei, not
    # Shen, for this hour).
    day_master_a, pillars_a = _compute_ten_gods_for_person(
        "1980-06-24T15:44:00", "Europe/Berlin", 9.7167, 52.3667
    )
    assert day_master_a == "Wu"
    assert pillars_a["year"] == ("Geng", "EatingGod")
    assert pillars_a["month"] == ("Ren", "IndirectWealth")
    assert pillars_a["hour"] == ("Ji", "RobWealth")  # LMT-correct; source mislabels this hour

    # Person B — DM Wu (戊). Full 4-pillar chart (including hour) matches
    # the source document's stated chart AND Ten-God assignments exactly.
    day_master_b, pillars_b = _compute_ten_gods_for_person(
        "1990-04-03T20:01:00", "Europe/Berlin", 7.1333, 50.9833
    )
    assert day_master_b == "Wu"
    assert pillars_b["year"] == ("Geng", "EatingGod")
    assert pillars_b["month"] == ("Ji", "RobWealth")
    assert pillars_b["hour"] == ("Xin", "HurtingOfficer")


def test_spouse_star_convention_narrow() -> None:
    """The shipped convention is the NARROW one Tabelle 10 actually states:
    single primary god per gender, opposite-polarity god is a disruption
    signal, not a co-equal spouse star."""
    from bazi_engine.bafe.ruleset_loader import spouse_star_convention

    convention = spouse_star_convention(load_default_ruleset())
    assert convention["male"] == ["DirectWealth"]
    assert convention["female"] == ["DirectOfficer"]
    assert convention["disruption_signal"]["male"]["god"] == "IndirectWealth"
    assert convention["disruption_signal"]["female"]["god"] == "SevenKilling"
