"""ZWDS-P1-10/P1-11 — Zi Wei / Tian Fu anchors + 14 major-star offsets.

Ephemeris-free, pure-formula tests over the resolved seed. The golden truth is
``docs/zwds/design-pack/response_example_core.json`` (seed: m=1,
hour_branch_index=0, d=1, bureau FIRE_6 so B=6).

Every formula is 0-based (branches ``ZI=0..HAI=11``) and matches the design-pack
formula spec (``docs/zwds/design-pack/zwds_formula_spec.md`` §9-10).
"""

from __future__ import annotations

from bazi_engine.zwds.domain import BranchId, mod12
from bazi_engine.zwds.stars import StarBranch
from bazi_engine.zwds.stars.major import (
    MAJOR_14_FAMILY,
    MAJOR_14_FORMULA,
    MAJOR_14_SOURCE_STATUS,
    major_stars,
    major_stars_from_ziwei,
    tianfu_branch,
    ziwei_branch,
)

# Independent (test-owned) copy of the offset tables from spec §10, so the
# property test is not a tautological re-read of the source table.
_ZIWEI_OFFSETS = {
    "ZI_WEI": 0,
    "TIAN_JI": -1,
    "TAI_YANG": -3,
    "WU_QU": -4,
    "TIAN_TONG": -5,
    "LIAN_ZHEN": -8,
}
_TIANFU_OFFSETS = {
    "TIAN_FU": 0,
    "TAI_YIN": 1,
    "TAN_LANG": 2,
    "JU_MEN": 3,
    "TIAN_XIANG": 4,
    "TIAN_LIANG": 5,
    "QI_SHA": 6,
    "PO_JUN": 10,
}


def test_all_150_ziwei_tianfu_in_range() -> None:
    """Every (d in 1..30, B in {2,3,4,5,6}) yields anchors in 0..11 (150 cases)."""
    count = 0
    for d in range(1, 31):
        for B in (2, 3, 4, 5, 6):
            ziwei_b = ziwei_branch(d, B)
            tianfu_b = tianfu_branch(ziwei_b)
            assert 0 <= ziwei_b <= 11, (d, B, ziwei_b)
            assert 0 <= tianfu_b <= 11, (d, B, tianfu_b)
            count += 1
    assert count == 150


def test_example_seed_ziwei_tianfu() -> None:
    """d=1, B=6 → Zi Wei on YOU(9), Tian Fu on WEI(7) (design-pack example)."""
    ziwei_b = ziwei_branch(1, 6)
    assert ziwei_b == BranchId.YOU  # 9
    assert tianfu_branch(ziwei_b) == BranchId.WEI  # 7


def test_twelve_base_positions_property() -> None:
    """For every ziwei_b in 0..11 the 14 placements equal mod12(base+offset)."""
    for ziwei_b in range(12):
        tianfu_b = mod12(4 - ziwei_b)
        placements = {p.star_id: p.branch_index for p in major_stars_from_ziwei(ziwei_b)}
        assert len(placements) == 14, ziwei_b
        for star_id, offset in _ZIWEI_OFFSETS.items():
            assert placements[star_id] == mod12(ziwei_b + offset), (ziwei_b, star_id)
        for star_id, offset in _TIANFU_OFFSETS.items():
            assert placements[star_id] == mod12(tianfu_b + offset), (ziwei_b, star_id)


def test_example_fourteen_star_branches_exact() -> None:
    """The 14 major-star branches match the golden design-pack example exactly."""
    expected = {
        "ZI_WEI": BranchId.YOU,
        "TIAN_JI": BranchId.SHEN,
        "TAI_YANG": BranchId.WU,
        "WU_QU": BranchId.SI,
        "TIAN_TONG": BranchId.CHEN,
        "LIAN_ZHEN": BranchId.CHOU,
        "TIAN_FU": BranchId.WEI,
        "TAI_YIN": BranchId.SHEN,
        "TAN_LANG": BranchId.YOU,
        "JU_MEN": BranchId.XU,
        "TIAN_XIANG": BranchId.HAI,
        "TIAN_LIANG": BranchId.ZI,
        "QI_SHA": BranchId.CHOU,
        "PO_JUN": BranchId.SI,
    }
    placements = major_stars(d=1, B=6)
    assert len(placements) == 14
    got = {p.star_id: p.branch_index for p in placements}
    assert got == {star: int(branch) for star, branch in expected.items()}


def test_major_placements_carry_family_formula_status() -> None:
    """Every major placement carries the MAJOR_14 family/formula/source metadata."""
    for p in major_stars(d=1, B=6):
        assert isinstance(p, StarBranch)
        assert p.family_id == MAJOR_14_FAMILY == "MAJOR_14"
        assert p.formula_id == MAJOR_14_FORMULA == "major-star-offsets.v1"
        assert p.source_status == MAJOR_14_SOURCE_STATUS == "SOURCE_REVIEWED"


def test_star_branch_is_frozen() -> None:
    """StarBranch is an immutable (frozen) dataclass."""
    p = major_stars(d=1, B=6)[0]
    try:
        p.branch_index = 0  # type: ignore[misc]
    except Exception as exc:  # dataclasses.FrozenInstanceError
        assert type(exc).__name__ == "FrozenInstanceError"
    else:  # pragma: no cover - must not reach
        raise AssertionError("StarBranch must be frozen")
