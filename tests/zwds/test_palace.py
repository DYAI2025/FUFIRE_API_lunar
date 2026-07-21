"""ZWDS-P1-07/08 — Ming/Shen palaces, 12-palace layout, Five-Tigers stems.

Ephemeris-free, pure-formula tests over the resolved seed. The golden truth is
``docs/zwds/design-pack/response_example_core.json`` (seed: m=1,
hour_branch_index=0 (ZI), y_s=0 (JIA)).
"""

from __future__ import annotations

from bazi_engine.zwds.domain import BranchId, StemId
from bazi_engine.zwds.palace import (
    PALACE_ROLES,
    Palace,
    build_palaces,
    ming_branch,
    palace_stem,
    shen_branch,
    yin_stem,
)

YIN = int(BranchId.YIN)  # 2


def test_all_144_ming_shen_in_range() -> None:
    """Every (m, hour_branch_index) combo yields Ming/Shen branches in 0..11."""
    for m in range(1, 13):
        for h1 in range(0, 12):
            ming_b = ming_branch(m, h1)
            shen_b = shen_branch(m, h1)
            assert 0 <= ming_b <= 11, (m, h1, ming_b)
            assert 0 <= shen_b <= 11, (m, h1, shen_b)


def test_example_seed_ming_shen_both_yin() -> None:
    """m=1, h1=0 → Ming and Shen both seat on YIN (design-pack example)."""
    assert ming_branch(1, 0) == YIN
    assert shen_branch(1, 0) == YIN


# Golden 12-palace table for the design-pack example seed
# (m=1, hour_branch_index=0, y_s=0). (sequence, role, branch, stem).
_EXAMPLE_TABLE = [
    (0, "MING", BranchId.YIN, StemId.BING),
    (1, "XIONG_DI", BranchId.CHOU, StemId.DING),
    (2, "FU_QI", BranchId.ZI, StemId.BING),
    (3, "ZI_NU", BranchId.HAI, StemId.YI),
    (4, "CAI_BO", BranchId.XU, StemId.JIA),
    (5, "JI_E", BranchId.YOU, StemId.GUI),
    (6, "QIAN_YI", BranchId.SHEN, StemId.REN),
    (7, "JIAO_YOU", BranchId.WEI, StemId.XIN),
    (8, "GUAN_LU", BranchId.WU, StemId.GENG),
    (9, "TIAN_ZHAI", BranchId.SI, StemId.JI),
    (10, "FU_DE", BranchId.CHEN, StemId.WU),
    (11, "FU_MU", BranchId.MAO, StemId.DING),
]


def test_example_chart_full_palace_table_exact() -> None:
    """The full 12-palace layout matches the golden design-pack example exactly."""
    palaces = build_palaces(m=1, hour_branch_index=0, y_s=0)
    assert len(palaces) == 12
    for palace, (seq, role, branch, stem) in zip(palaces, _EXAMPLE_TABLE):
        assert isinstance(palace, Palace)
        assert palace.sequence_index_0 == seq
        assert palace.palace_role_id == role
        assert palace.branch_id == branch
        assert palace.stem_id == stem


def test_example_chart_ming_shen_flags() -> None:
    """Only MING carries is_ming_palace; the Shen flag lands on the same YIN palace."""
    palaces = build_palaces(m=1, hour_branch_index=0, y_s=0)
    ming = [p for p in palaces if p.is_ming_palace]
    shen = [p for p in palaces if p.is_shen_palace]
    assert len(ming) == 1
    assert len(shen) == 1
    assert ming[0].palace_role_id == "MING"
    assert ming[0].branch_id == BranchId.YIN
    # ming_b == shen_b == YIN in the example, so the Ming palace is also Shen.
    assert shen[0] is ming[0]
    assert ming[0].is_shen_palace is True


def test_palace_roles_order_and_uniqueness() -> None:
    """Roles are exactly the source-order 12, each palace branch is unique."""
    assert PALACE_ROLES == (
        "MING",
        "XIONG_DI",
        "FU_QI",
        "ZI_NU",
        "CAI_BO",
        "JI_E",
        "QIAN_YI",
        "JIAO_YOU",
        "GUAN_LU",
        "TIAN_ZHAI",
        "FU_DE",
        "FU_MU",
    )
    palaces = build_palaces(m=1, hour_branch_index=0, y_s=0)
    branches = {int(p.branch_id) for p in palaces}
    assert branches == set(range(12))


def test_palace_is_frozen() -> None:
    """Palace is an immutable (frozen) dataclass."""
    palace = build_palaces(m=1, hour_branch_index=0, y_s=0)[0]
    try:
        palace.branch_id = BranchId.ZI  # type: ignore[misc]
    except Exception as exc:  # dataclasses.FrozenInstanceError
        assert type(exc).__name__ == "FrozenInstanceError"
    else:  # pragma: no cover - must not reach
        raise AssertionError("Palace must be frozen")


# Five-Tigers year-stem start pairs: y_s -> yin_stem index.
_FIVE_TIGERS = [
    (0, StemId.BING),  # 2*0+2 = 2
    (1, StemId.WU),    # 2*1+2 = 4
    (2, StemId.GENG),  # 2*2+2 = 6
    (3, StemId.REN),   # 2*3+2 = 8
    (4, StemId.JIA),   # 2*4+2 = 10 -> mod10 0
    (5, StemId.BING),  # 2*5+2 = 12 -> mod10 2 (cycle repeats every 5)
]


def test_five_tigers_start_pairs() -> None:
    """yin_stem = mod10(2*y_s + 2) reproduces the five start pairs (period 5)."""
    for y_s, expected in _FIVE_TIGERS:
        assert yin_stem(y_s) == expected


def test_five_tigers_all_ten_stems_period_five() -> None:
    """yin_stem cycles with period 5 across all ten year stems."""
    for y_s in range(10):
        assert yin_stem(y_s) == yin_stem((y_s + 5) % 10)
        assert yin_stem(y_s) == (2 * y_s + 2) % 10


def test_palace_stem_on_yin_equals_yin_stem() -> None:
    """palace_stem(YIN, y_s) == yin_stem(y_s) for every year stem."""
    for y_s in range(10):
        assert palace_stem(YIN, y_s) == yin_stem(y_s)
