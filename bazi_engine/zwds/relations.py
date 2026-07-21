"""ZWDS-P1-14 — San Fang Si Zheng (三方四正) relations.

Pure ZWDS geometry over the palace ring, 0-based throughout (branches
``ZI=0..HAI=11``). For a focus branch ``p`` (design-pack
``zwds_formula_spec.md`` §13):

* ``harmony_1 = mod12(p + 4)``
* ``harmony_2 = mod12(p + 8)``
* ``opposition = mod12(p + 6)``

The harmony pair plus the focus form the "three sides" (三方); the opposition is
the "four corners" (四正) partner. This layer returns geometry ONLY —
beneficial/harmful interpretation belongs to a separately sourced layer.

This module imports ONLY :mod:`bazi_engine.zwds.domain` and the stdlib; it never
reaches into ``bazi``/``western``/``fusion``/``impact``/routers/``app``. Palaces
are consumed structurally (``palace_role_id`` + ``branch_id``), so it does not
import the palace module either.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Protocol, Tuple

from bazi_engine.zwds.domain import BranchId, mod12

# Fixed San-Fang-Si-Zheng offsets from the focus branch (design-pack §13).
_HARMONY_1_OFFSET = 4
_HARMONY_2_OFFSET = 8
_OPPOSITION_OFFSET = 6


class PalaceLike(Protocol):
    """Structural view of the palace fields the relations layer consumes.

    Keeps this module free of a hard dependency on the palace module — any
    object exposing a ``palace_role_id`` and a ``branch_id`` fits.
    """

    palace_role_id: str
    branch_id: BranchId


@dataclass(frozen=True)
class Relation:
    """The San-Fang-Si-Zheng relation set for one focus palace (immutable).

    * ``focus_palace_role_id`` — the palace this relation is centred on.
    * ``focus_branch_id`` — that palace's Earthly-Branch index.
    * ``harmony_branch_ids`` — the two trine partners ``(p+4, p+8)``, in that
      order.
    * ``opposition_branch_id`` — the opposing branch ``(p+6)``.
    """

    focus_palace_role_id: str
    focus_branch_id: BranchId
    harmony_branch_ids: Tuple[BranchId, BranchId]
    opposition_branch_id: BranchId


def relation_for_branch(palace_role_id: str, focus_branch_index: int) -> Relation:
    """Build the relation set for a single focus branch (§13 geometry)."""
    p = mod12(focus_branch_index)
    return Relation(
        focus_palace_role_id=palace_role_id,
        focus_branch_id=BranchId(p),
        harmony_branch_ids=(
            BranchId(mod12(p + _HARMONY_1_OFFSET)),
            BranchId(mod12(p + _HARMONY_2_OFFSET)),
        ),
        opposition_branch_id=BranchId(mod12(p + _OPPOSITION_OFFSET)),
    )


def relations_for_palaces(palaces: Iterable[PalaceLike]) -> List[Relation]:
    """One :class:`Relation` per palace, in the given palace order.

    Each ``palace`` is consumed structurally: it must expose a
    ``palace_role_id`` (str) and a ``branch_id`` (a :class:`BranchId`).
    """
    return [
        relation_for_branch(palace.palace_role_id, int(palace.branch_id))
        for palace in palaces
    ]
