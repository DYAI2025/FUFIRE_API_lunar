"""ZWDS-P1-12 — four guide-defined auxiliary stars.

Pure ZWDS star geometry over the resolved seed, 0-based throughout (branches
``ZI=0..HAI=11``). Matches the design-pack formula spec
(``docs/zwds/design-pack/zwds_formula_spec.md`` §11). The golden truth is
``response_example_core.json`` (seed: m=1, hour_branch_index=0).

These four stars are a **seed subset**, NOT a complete auxiliary-star catalog,
so every placement is flagged ``source_status == "SOURCE_NEEDED"``.

Variable contract (design-pack §2):

* ``m`` — effective lunar month, **1-based** (1..12).
* ``hour_branch_index`` — the 0-based birth-hour branch (``ZI=0``). It equals the
  spec's ``(h - 1)``; the formulas below use it verbatim.

This module imports ONLY :mod:`bazi_engine.zwds.domain`, this package's
:class:`StarBranch`, and the stdlib.
"""

from __future__ import annotations

from typing import List, Tuple

from bazi_engine.zwds.domain import BranchId, mod12
from bazi_engine.zwds.stars import StarBranch

# Anchor branches for the guide-auxiliary placements (spec §11).
CHEN: int = int(BranchId.CHEN)  # 4
XU: int = int(BranchId.XU)  # 10

GUIDE_AUX_FAMILY: str = "GUIDE_AUX_4"
GUIDE_AUX_FORMULA: str = "guide-auxiliary-placement.v1"
GUIDE_AUX_SOURCE_STATUS: str = "SOURCE_NEEDED"


def guide_auxiliary_stars(m: int, hour_branch_index: int) -> List[StarBranch]:
    """The four guide-defined auxiliary-star placements (§11).

    * ``ZUO_FU = mod12(CHEN + (m - 1))``
    * ``YOU_BI = mod12(XU - (m - 1))``
    * ``WEN_QU = mod12(CHEN + hour_branch_index)``
    * ``WEN_CHANG = mod12(XU - hour_branch_index)``

    ``hour_branch_index`` is the spec's ``(h - 1)`` (0-based birth-hour branch).
    """
    h1 = hour_branch_index
    positions: Tuple[Tuple[str, int], ...] = (
        ("ZUO_FU", mod12(CHEN + (m - 1))),
        ("YOU_BI", mod12(XU - (m - 1))),
        ("WEN_QU", mod12(CHEN + h1)),
        ("WEN_CHANG", mod12(XU - h1)),
    )
    return [
        StarBranch(
            star_id=star_id,
            family_id=GUIDE_AUX_FAMILY,
            branch_index=branch_index,
            formula_id=GUIDE_AUX_FORMULA,
            source_status=GUIDE_AUX_SOURCE_STATUS,
        )
        for star_id, branch_index in positions
    ]
