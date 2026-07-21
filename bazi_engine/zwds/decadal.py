"""ZWDS-P1-15 — decadal limits (大限), a ruleset-candidate seed.

Guide-seed rule (design-pack ``zwds_formula_spec.md`` §14):

* the first start age is the Five-Elements Bureau number;
* each subsequent 10-year range starts 10 years later (inclusive ranges);
* the first range is assigned to the Ming palace;
* the walk direction is ``forward`` or ``backward``, resolved from an explicit
  flow or the year-stem yin/yang + sex rule.

Geometry of the walk: ``forward`` advances by INCREASING branch index
(``mod12(ming_b + j)``) — equivalently DECREASING palace ``sequence_index`` —
while ``backward`` decreases the branch (``mod12(ming_b - j)``). Both start on
the Ming palace at age = bureau number.

Age semantics: inclusive ``[start, start+9]``, reckoned as
``east_asian_nominal.guide-v1``. This rule is releaseable only as part of a
named ruleset.

Imports: ONLY :mod:`bazi_engine.zwds.domain`, the stdlib, and
:mod:`bazi_engine.dayun.direction` (direction reuse mandated by source ledger
S-03 — that module itself imports only ``bazi_engine.exc``). It never reaches
into ``bazi``/``western``/``fusion``/``impact``/routers/``app``, and consumes
palaces structurally so it does not import the palace module.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Protocol, Sequence

from bazi_engine.dayun.direction import resolve_direction as _resolve_dayun_direction
from bazi_engine.zwds.domain import BranchId, mod12

AGE_RECKONING_ID: str = "east_asian_nominal.guide-v1"

_DECADE_SPAN: int = 10
_MING_ROLE: str = "MING"
_FORWARD: str = "forward"
_BACKWARD: str = "backward"
_VALID_DIRECTIONS = (_FORWARD, _BACKWARD)


class PalaceLike(Protocol):
    """Structural view of the palace fields the decadal layer consumes."""

    palace_role_id: str
    branch_id: BranchId


@dataclass(frozen=True)
class DecadalLimit:
    """One 10-year decadal limit (大限) of a ZWDS chart (immutable).

    * ``sequence_index_0`` — decadal step, 0..11 (0 is always the Ming palace).
    * ``start_age_inclusive`` / ``end_age_inclusive`` — inclusive age range.
    * ``age_reckoning_id`` — how the ages are counted (nominal East-Asian).
    * ``direction`` — ``"forward"`` or ``"backward"`` walk.
    * ``branch_id`` — the Earthly-Branch index this step lands on.
    * ``palace_role_id`` — the palace seated on that branch.
    """

    sequence_index_0: int
    start_age_inclusive: int
    end_age_inclusive: int
    age_reckoning_id: str
    direction: str
    branch_id: BranchId
    palace_role_id: str


def decadal_direction(
    *,
    flow_direction: Optional[str] = None,
    year_stem_index: Optional[int] = None,
    sex_at_birth: Optional[str] = None,
) -> str:
    """Resolve the decadal walk direction, reusing :mod:`bazi_engine.dayun.direction`.

    Pass ``flow_direction`` for the explicit method, or ``year_stem_index``
    (0..9, JIA=0; even = yang) plus ``sex_at_birth`` for the classical
    year-stem-yin/yang + sex rule.
    """
    if flow_direction is not None:
        return _resolve_dayun_direction(
            {"direction_method": "explicit", "flow_direction": flow_direction}
        )
    polarity: Optional[str] = None
    if year_stem_index is not None:
        polarity = "yang" if year_stem_index % 2 == 0 else "yin"
    return _resolve_dayun_direction(
        {
            "direction_method": "year_stem_yinyang_and_sex",
            "year_stem_polarity": polarity,
            "sex_at_birth": sex_at_birth,
        }
    )


def decadal_limits(
    palaces: Sequence[PalaceLike],
    bureau_number: int,
    direction: str,
) -> List[DecadalLimit]:
    """The twelve decadal limits for a chart (design-pack §14).

    ``palaces`` is consumed structurally (``palace_role_id`` + ``branch_id``).
    ``bureau_number`` is the Five-Elements Bureau number (2..6) and the first
    start age. ``direction`` is a resolved ``"forward"``/``"backward"`` string
    (see :func:`decadal_direction`).
    """
    if direction not in _VALID_DIRECTIONS:
        raise ValueError(
            f"invalid decadal direction {direction!r}; "
            f"expected one of {_VALID_DIRECTIONS}"
        )

    branch_to_role: Dict[int, str] = {
        int(p.branch_id): p.palace_role_id for p in palaces
    }
    ming_branch = _ming_branch(palaces)
    sign = 1 if direction == _FORWARD else -1

    limits: List[DecadalLimit] = []
    for j in range(12):
        branch_index = mod12(ming_branch + sign * j)
        start_age = bureau_number + _DECADE_SPAN * j
        limits.append(
            DecadalLimit(
                sequence_index_0=j,
                start_age_inclusive=start_age,
                end_age_inclusive=start_age + _DECADE_SPAN - 1,
                age_reckoning_id=AGE_RECKONING_ID,
                direction=direction,
                branch_id=BranchId(branch_index),
                palace_role_id=branch_to_role[branch_index],
            )
        )
    return limits


def _ming_branch(palaces: Sequence[PalaceLike]) -> int:
    """Return the Ming palace's branch index (raises if absent)."""
    for palace in palaces:
        if palace.palace_role_id == _MING_ROLE:
            return int(palace.branch_id)
    raise ValueError("palaces must contain the MING palace")
