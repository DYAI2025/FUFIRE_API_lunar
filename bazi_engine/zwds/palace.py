"""ZWDS-P1-07/08 — Ming/Shen palaces, 12-palace layout, Five-Tigers stems.

Pure ZWDS geometry over the resolved seed. Every formula here is 0-based
(branches ``ZI=0..HAI=11``, stems ``JIA=0..GUI=9``) and matches the design-pack
formula spec (``docs/zwds/design-pack/zwds_formula_spec.md`` §5-7). The golden
truth is ``response_example_core.json`` (seed: m=1, hour_branch_index=0, y_s=0).

This module imports ONLY :mod:`bazi_engine.zwds.domain` and the stdlib; it never
reaches into ``bazi``/``western``/``fusion``/``impact``/routers/``app``.

Variable contract (design-pack §2):

* ``m`` — effective lunar month, **1-based** (1..12).
* ``hour_branch_index`` — the 0-based birth-hour branch (``ZI=0``). It equals the
  spec's ``(h - 1)``; the formulas below use it verbatim.
* ``y_s`` — the year Heavenly Stem, 0-based (``JIA=0``).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple

from bazi_engine.zwds.domain import BranchId, StemId, mod10, mod12

# The YIN branch (寅, index 2) is the fixed anchor for both the palace layout
# and the Five-Tigers stem rule.
YIN: int = int(BranchId.YIN)

# Source-order palace role IDs (design-pack §6). Sequence index 0 is always MING.
PALACE_ROLES: Tuple[str, ...] = (
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


def ming_branch(m: int, hour_branch_index: int) -> int:
    """Ming (Life) palace branch index (§5).

    ``ming_b = mod12(YIN + (m - 1) - hour_branch_index)``.
    """
    return mod12(YIN + (m - 1) - hour_branch_index)


def shen_branch(m: int, hour_branch_index: int) -> int:
    """Shen (Body) palace branch index (§5).

    ``shen_b = mod12(YIN + (m - 1) + hour_branch_index)``.
    """
    return mod12(YIN + (m - 1) + hour_branch_index)


def yin_stem(y_s: int) -> int:
    """Five-Tigers stem seated on the YIN palace from the year stem (§7).

    ``yin_stem = mod10(2 * y_s + 2)``.
    """
    return mod10(2 * y_s + 2)


def palace_stem(branch_b: int, y_s: int) -> int:
    """Heavenly stem seated on ``branch_b`` via the Five-Tigers rule (§7).

    ``palace_stem(b) = mod10(yin_stem + mod12(b - YIN))``.
    """
    return mod10(yin_stem(y_s) + mod12(branch_b - YIN))


@dataclass(frozen=True)
class Palace:
    """One of the twelve palaces of a ZWDS chart (immutable)."""

    palace_role_id: str
    sequence_index_0: int
    branch_id: BranchId
    stem_id: StemId
    is_ming_palace: bool
    is_shen_palace: bool


def build_palaces(m: int, hour_branch_index: int, y_s: int) -> List[Palace]:
    """Lay out the full twelve-palace ring for the resolved seed.

    Palace at sequence ``i`` (0..11): ``branch = mod12(ming_b - i)`` and
    ``role = PALACE_ROLES[i]``, with its Five-Tigers ``stem`` attached. The
    ``is_ming_palace`` flag is the MING role seated on ``ming_b``; every palace
    whose branch equals ``shen_b`` is flagged ``is_shen_palace`` (in the example
    ``ming_b == shen_b == YIN``, so the Ming palace is also the Shen palace).
    """
    ming_b = ming_branch(m, hour_branch_index)
    shen_b = shen_branch(m, hour_branch_index)

    palaces: List[Palace] = []
    for i, role in enumerate(PALACE_ROLES):
        branch = mod12(ming_b - i)
        stem = palace_stem(branch, y_s)
        palaces.append(
            Palace(
                palace_role_id=role,
                sequence_index_0=i,
                branch_id=BranchId(branch),
                stem_id=StemId(stem),
                is_ming_palace=(branch == ming_b and role == "MING"),
                is_shen_palace=(branch == shen_b),
            )
        )
    return palaces
