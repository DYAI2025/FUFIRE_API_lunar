"""ZWDS-P0-02 — typed ID enums + safe modulo.

Structural guarantee: Heavenly Stem, Earthly Branch, and zodiac Animal are
THREE separate typed things. A stem can never be passed where a branch is
expected, and an animal is never an instance of BranchId (kills the source
guide's ``庚 / 午`` stem/branch conflation at the type level).
"""

from __future__ import annotations

from enum import IntEnum

from bazi_engine.zwds.domain import AnimalId, BranchId, StemId, mod10, mod12


def test_stem_id_members_and_length() -> None:
    assert StemId.JIA == 0
    assert StemId.GUI == 9
    assert len(StemId) == 10


def test_branch_id_members_and_length() -> None:
    assert BranchId.ZI == 0
    assert BranchId.HAI == 11
    assert len(BranchId) == 12


def test_animal_id_is_distinct_from_branch_id() -> None:
    assert len(AnimalId) == 12
    # Distinct classes — an animal value is never a BranchId instance.
    assert AnimalId is not BranchId
    assert type(AnimalId.RAT) is not BranchId
    assert not isinstance(AnimalId.RAT, BranchId)


def test_stem_wu_and_branch_wu_are_different_tokens() -> None:
    # Same romanization "WU", different enums, different int values (4 vs 6).
    assert StemId.WU is not BranchId.WU
    assert int(StemId.WU) != int(BranchId.WU)
    assert int(StemId.WU) == 4
    assert int(BranchId.WU) == 6


def test_all_three_are_separate_intenum_classes() -> None:
    for cls in (StemId, BranchId, AnimalId):
        assert issubclass(cls, IntEnum)
    assert StemId is not BranchId
    assert BranchId is not AnimalId
    assert StemId is not AnimalId


def test_mod12_never_relies_on_negative_remainder() -> None:
    assert mod12(-1) == 11
    assert mod12(14) == 2
    assert mod12(12) == 0


def test_mod10_never_relies_on_negative_remainder() -> None:
    assert mod10(-1) == 9
    assert mod10(10) == 0
