"""ZWDS-P1-10/P1-11 — Zi Wei / Tian Fu anchors and the 14 major stars.

Pure ZWDS star geometry over the resolved seed, 0-based throughout (branches
``ZI=0..HAI=11``). Matches the design-pack formula spec
(``docs/zwds/design-pack/zwds_formula_spec.md`` §9-10). The golden truth is
``response_example_core.json`` (seed: d=1, bureau FIRE_6 so B=6, giving Zi Wei on
YOU and Tian Fu on WEI).

This module imports ONLY :mod:`bazi_engine.zwds.domain`, this package's
:class:`StarBranch`, and the stdlib.
"""

from __future__ import annotations

from math import ceil
from typing import List, Tuple

from bazi_engine.zwds.domain import BranchId, mod12
from bazi_engine.zwds.stars import StarBranch

# 寅 (index 2) is the ordinal anchor for the Zi Wei placement (spec §9).
YIN: int = int(BranchId.YIN)

MAJOR_14_FAMILY: str = "MAJOR_14"
MAJOR_14_FORMULA: str = "major-star-offsets.v1"
MAJOR_14_SOURCE_STATUS: str = "SOURCE_REVIEWED"

# Offsets from ``ziwei_b`` (spec §10, first table).
_ZIWEI_OFFSETS: Tuple[Tuple[str, int], ...] = (
    ("ZI_WEI", 0),
    ("TIAN_JI", -1),
    ("TAI_YANG", -3),
    ("WU_QU", -4),
    ("TIAN_TONG", -5),
    ("LIAN_ZHEN", -8),
)

# Offsets from ``tianfu_b`` (spec §10, second table).
_TIANFU_OFFSETS: Tuple[Tuple[str, int], ...] = (
    ("TIAN_FU", 0),
    ("TAI_YIN", 1),
    ("TAN_LANG", 2),
    ("JU_MEN", 3),
    ("TIAN_XIANG", 4),
    ("TIAN_LIANG", 5),
    ("QI_SHA", 6),
    ("PO_JUN", 10),
)


def ziwei_branch(d: int, B: int) -> int:
    """Zi Wei (紫微) branch index from lunar day ``d`` and bureau number ``B`` (§9).

    ``k = ceil(d / B)``; ``delta = k*B - d``; ``step = k + delta`` when ``delta``
    is even else ``k - delta``; ``ziwei_b = mod12(YIN + step - 1)``.
    """
    k = ceil(d / B)
    delta = k * B - d
    step = k + delta if delta % 2 == 0 else k - delta
    return mod12(YIN + step - 1)


def tianfu_branch(ziwei_b: int) -> int:
    """Tian Fu (天府) branch index, mirrored from Zi Wei (§9).

    ``tianfu_b = mod12(4 - ziwei_b)``.
    """
    return mod12(4 - ziwei_b)


def major_stars_from_ziwei(ziwei_b: int) -> List[StarBranch]:
    """The 14 major-star placements given a Zi Wei anchor branch (§10).

    Six stars are offset from ``ziwei_b`` and eight from the derived
    ``tianfu_b``; each position is ``mod12(base + offset)``.
    """
    tianfu_b = tianfu_branch(ziwei_b)
    placements: List[StarBranch] = []
    for star_id, offset in _ZIWEI_OFFSETS:
        placements.append(
            StarBranch(
                star_id=star_id,
                family_id=MAJOR_14_FAMILY,
                branch_index=mod12(ziwei_b + offset),
                formula_id=MAJOR_14_FORMULA,
                source_status=MAJOR_14_SOURCE_STATUS,
            )
        )
    for star_id, offset in _TIANFU_OFFSETS:
        placements.append(
            StarBranch(
                star_id=star_id,
                family_id=MAJOR_14_FAMILY,
                branch_index=mod12(tianfu_b + offset),
                formula_id=MAJOR_14_FORMULA,
                source_status=MAJOR_14_SOURCE_STATUS,
            )
        )
    return placements


def major_stars(d: int, B: int) -> List[StarBranch]:
    """The 14 major-star placements for lunar day ``d`` and bureau number ``B``.

    Composes §9 (Zi Wei anchor) with §10 (offset tables).
    """
    return major_stars_from_ziwei(ziwei_branch(d, B))
