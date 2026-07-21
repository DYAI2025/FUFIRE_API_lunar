"""ZWDS-P1-15 — decadal limits (大限).

Guide-seed rule (design-pack ``zwds_formula_spec.md`` §14): the first start age
is the bureau number, each next 10-year range starts 10 years later, the first
range is the Ming palace, and the walk direction is resolved from an explicit
flow or the year-stem yin/yang + sex rule. The golden truth is
``docs/zwds/design-pack/response_example_core.json`` -> ``chart.decadal_limits``
(bureau 6, forward).

Direction resolution reuses :mod:`bazi_engine.dayun.direction` (source ledger
S-03 mandates reuse).
"""

from __future__ import annotations

import json
from pathlib import Path

from bazi_engine.zwds.decadal import (
    AGE_RECKONING_ID,
    DecadalLimit,
    decadal_direction,
    decadal_limits,
)
from bazi_engine.zwds.domain import mod12
from bazi_engine.zwds.palace import build_palaces

_REPO_ROOT = Path(__file__).resolve().parents[2]
_DESIGN_PACK = (
    _REPO_ROOT / "docs" / "zwds" / "design-pack" / "response_example_core.json"
)

# Example seed (m=1, hour_branch_index=0, y_s=0 JIA) → Ming on YIN, bureau 6.
_BUREAU_NUMBER = 6
_MING_BRANCH = 2  # YIN


def _golden_decadal() -> list[dict]:
    data = json.loads(_DESIGN_PACK.read_text())
    return data["chart"]["decadal_limits"]


def test_example_forward_matches_golden_all_twelve() -> None:
    """bureau 6, forward → exactly the 12 golden ranges (sequence/ages/branch/role)."""
    palaces = build_palaces(m=1, hour_branch_index=0, y_s=0)
    limits = decadal_limits(palaces, bureau_number=_BUREAU_NUMBER, direction="forward")
    assert len(limits) == 12
    golden = _golden_decadal()
    assert len(golden) == 12
    for limit, g in zip(limits, golden):
        assert isinstance(limit, DecadalLimit)
        assert limit.sequence_index_0 == g["sequence_index_0"]
        assert limit.start_age_inclusive == g["start_age_inclusive"]
        assert limit.end_age_inclusive == g["end_age_inclusive"]
        assert limit.age_reckoning_id == g["age_reckoning_id"] == AGE_RECKONING_ID
        assert limit.direction == g["direction"] == "forward"
        assert limit.branch_id.name == g["branch_id"]
        assert limit.palace_role_id == g["palace_role_id"]


def test_forward_ages_and_first_range_is_ming() -> None:
    """First range starts at the bureau number and sits on the Ming palace."""
    palaces = build_palaces(m=1, hour_branch_index=0, y_s=0)
    limits = decadal_limits(palaces, bureau_number=_BUREAU_NUMBER, direction="forward")
    assert limits[0].palace_role_id == "MING"
    assert limits[0].start_age_inclusive == _BUREAU_NUMBER
    for j, limit in enumerate(limits):
        assert limit.sequence_index_0 == j
        assert limit.start_age_inclusive == _BUREAU_NUMBER + 10 * j
        assert limit.end_age_inclusive == _BUREAU_NUMBER + 10 * j + 9


def test_backward_reverses_palace_walk() -> None:
    """backward: first range still Ming, then decreasing branch (mod12(ming-j))."""
    palaces = build_palaces(m=1, hour_branch_index=0, y_s=0)
    branch_to_role = {int(p.branch_id): p.palace_role_id for p in palaces}
    limits = decadal_limits(palaces, bureau_number=_BUREAU_NUMBER, direction="backward")
    assert len(limits) == 12
    assert limits[0].palace_role_id == "MING"
    for j, limit in enumerate(limits):
        expected_branch = mod12(_MING_BRANCH - j)
        assert limit.sequence_index_0 == j
        assert int(limit.branch_id) == expected_branch, j
        assert limit.palace_role_id == branch_to_role[expected_branch], j
        assert limit.direction == "backward"
        # ages still start at the bureau number and step by 10.
        assert limit.start_age_inclusive == _BUREAU_NUMBER + 10 * j
        assert limit.end_age_inclusive == _BUREAU_NUMBER + 10 * j + 9


def test_forward_and_backward_diverge_after_first() -> None:
    """Both start on Ming but the second range differs (opposite walk)."""
    palaces = build_palaces(m=1, hour_branch_index=0, y_s=0)
    fwd = decadal_limits(palaces, bureau_number=_BUREAU_NUMBER, direction="forward")
    bwd = decadal_limits(palaces, bureau_number=_BUREAU_NUMBER, direction="backward")
    assert fwd[0].branch_id == bwd[0].branch_id  # both Ming @ YIN
    assert fwd[1].branch_id != bwd[1].branch_id  # MAO vs CHOU


def test_direction_resolution_via_dayun() -> None:
    """Direction resolver reuses dayun: yang+male→forward, yin+male→backward."""
    # JIA (index 0) is yang → forward for a male.
    assert decadal_direction(year_stem_index=0, sex_at_birth="male") == "forward"
    # YI (index 1) is yin → backward for a male.
    assert decadal_direction(year_stem_index=1, sex_at_birth="male") == "backward"
    # Explicit flow passes straight through.
    assert decadal_direction(flow_direction="backward") == "backward"
    assert decadal_direction(flow_direction="forward") == "forward"


def test_decadal_limit_is_frozen() -> None:
    """DecadalLimit is an immutable (frozen) dataclass."""
    palaces = build_palaces(m=1, hour_branch_index=0, y_s=0)
    limit = decadal_limits(palaces, bureau_number=_BUREAU_NUMBER, direction="forward")[0]
    try:
        limit.start_age_inclusive = 0  # type: ignore[misc]
    except Exception as exc:  # dataclasses.FrozenInstanceError
        assert type(exc).__name__ == "FrozenInstanceError"
    else:  # pragma: no cover - must not reach
        raise AssertionError("DecadalLimit must be frozen")
