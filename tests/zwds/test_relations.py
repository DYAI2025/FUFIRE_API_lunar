"""ZWDS-P1-14 — San Fang Si Zheng (三方四正) relations.

Pure geometry over the palace ring: for a focus branch ``p`` the triangle
harmony pair is ``mod12(p+4)``/``mod12(p+8)`` and the opposition is
``mod12(p+6)`` (design-pack ``zwds_formula_spec.md`` §13). No benefic/malefic
interpretation lives here. The golden truth is
``docs/zwds/design-pack/response_example_core.json`` -> ``chart.relations``.
"""

from __future__ import annotations

import json
from pathlib import Path

from bazi_engine.zwds.domain import BranchId, mod12
from bazi_engine.zwds.palace import build_palaces
from bazi_engine.zwds.relations import Relation, relations_for_palaces

_REPO_ROOT = Path(__file__).resolve().parents[2]
_DESIGN_PACK = (
    _REPO_ROOT / "docs" / "zwds" / "design-pack" / "response_example_core.json"
)


def _golden_relations() -> list[dict]:
    data = json.loads(_DESIGN_PACK.read_text())
    return data["chart"]["relations"]


def test_all_twelve_branches_relations_in_range_and_formula() -> None:
    """For every focus branch the harmony/opposition follow the +4/+8/+6 rule."""
    for p in range(12):
        h1 = mod12(p + 4)
        h2 = mod12(p + 8)
        opp = mod12(p + 6)
        assert 0 <= h1 <= 11 and 0 <= h2 <= 11 and 0 <= opp <= 11
        assert opp == mod12(p + 6)
        # opposition is always exactly 6 away (both directions collapse to +6).
        assert opp == (p + 6) % 12


def test_example_ming_yin_triangle() -> None:
    """MING@YIN(2) -> harmony {WU(6), XU(10)}, opposition SHEN(8)."""
    palaces = build_palaces(m=1, hour_branch_index=0, y_s=0)
    relations = relations_for_palaces(palaces)
    ming = next(r for r in relations if r.focus_palace_role_id == "MING")
    assert ming.focus_branch_id == BranchId.YIN
    assert {b.name for b in ming.harmony_branch_ids} == {"WU", "XU"}
    assert [b.name for b in ming.harmony_branch_ids] == ["WU", "XU"]  # order: +4, +8
    assert ming.opposition_branch_id == BranchId.SHEN


def test_example_full_twelve_relations_match_golden() -> None:
    """The full 12-relation set matches response_example_core.json exactly."""
    palaces = build_palaces(m=1, hour_branch_index=0, y_s=0)
    relations = relations_for_palaces(palaces)
    assert len(relations) == 12
    golden = _golden_relations()
    assert len(golden) == 12
    # one relation per palace, in palace order.
    assert [r.focus_palace_role_id for r in relations] == [
        g["focus_palace_role_id"] for g in golden
    ]
    for r, g in zip(relations, golden):
        assert isinstance(r, Relation)
        assert r.focus_palace_role_id == g["focus_palace_role_id"]
        assert r.focus_branch_id.name == g["focus_branch_id"]
        assert [b.name for b in r.harmony_branch_ids] == g["harmony_branch_ids"]
        assert r.opposition_branch_id.name == g["opposition_branch_id"]


def test_relation_is_frozen() -> None:
    """Relation is an immutable (frozen) dataclass."""
    palaces = build_palaces(m=1, hour_branch_index=0, y_s=0)
    r = relations_for_palaces(palaces)[0]
    try:
        r.opposition_branch_id = BranchId.ZI  # type: ignore[misc]
    except Exception as exc:  # dataclasses.FrozenInstanceError
        assert type(exc).__name__ == "FrozenInstanceError"
    else:  # pragma: no cover - must not reach
        raise AssertionError("Relation must be frozen")
