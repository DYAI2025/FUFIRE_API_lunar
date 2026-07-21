"""ZWDS-P1-12 — four guide-defined auxiliary stars.

Ephemeris-free, pure-formula tests over the resolved seed. The golden truth is
``docs/zwds/design-pack/response_example_core.json`` (seed: m=1,
hour_branch_index=0). These four stars are a seed subset, NOT a complete
auxiliary-star catalog, hence ``source_status == "SOURCE_NEEDED"``.

Every formula is 0-based (branches ``ZI=0..HAI=11``) and matches the design-pack
formula spec (``docs/zwds/design-pack/zwds_formula_spec.md`` §11), where the
spec's ``(h-1)`` is exactly ``hour_branch_index``.
"""

from __future__ import annotations

from bazi_engine.zwds.domain import BranchId
from bazi_engine.zwds.stars import StarBranch
from bazi_engine.zwds.stars.auxiliary import (
    GUIDE_AUX_FAMILY,
    GUIDE_AUX_FORMULA,
    GUIDE_AUX_SOURCE_STATUS,
    guide_auxiliary_stars,
)


def test_all_144_aux_in_range() -> None:
    """Every (m in 1..12, hour_branch_index in 0..11) yields branches in 0..11."""
    count = 0
    for m in range(1, 13):
        for h1 in range(0, 12):
            placements = guide_auxiliary_stars(m, h1)
            assert len(placements) == 4, (m, h1)
            for p in placements:
                assert 0 <= p.branch_index <= 11, (m, h1, p.star_id, p.branch_index)
            count += 1
    assert count == 144


def test_example_seed_aux_branches_exact() -> None:
    """m=1, h1=0 → ZUO_FU/WEN_QU on CHEN(4), YOU_BI/WEN_CHANG on XU(10)."""
    got = {p.star_id: p.branch_index for p in guide_auxiliary_stars(1, 0)}
    assert got == {
        "ZUO_FU": int(BranchId.CHEN),
        "YOU_BI": int(BranchId.XU),
        "WEN_QU": int(BranchId.CHEN),
        "WEN_CHANG": int(BranchId.XU),
    }


def test_aux_placements_carry_family_formula_status() -> None:
    """Every aux placement carries the GUIDE_AUX_4 family/formula/source metadata."""
    for p in guide_auxiliary_stars(1, 0):
        assert isinstance(p, StarBranch)
        assert p.family_id == GUIDE_AUX_FAMILY == "GUIDE_AUX_4"
        assert p.formula_id == GUIDE_AUX_FORMULA == "guide-auxiliary-placement.v1"
        # Seed subset — deliberately NOT reviewed.
        assert p.source_status == GUIDE_AUX_SOURCE_STATUS == "SOURCE_NEEDED"
