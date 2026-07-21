"""ZWDS star placements — pure, 0-based star geometry over the resolved seed.

Every module in this subpackage imports ONLY :mod:`bazi_engine.zwds.domain` and
the stdlib (plus this package's own :class:`StarBranch`); nothing here reaches
into ``bazi``/``western``/``fusion``/``impact``/routers/``app``.

:class:`StarBranch` is the small, immutable placement record every star function
returns. The richer engine-assembly fields (``palace_role_id``, ``placement_id``,
``transformation_types``, ``scope``) are attached LATER at chart assembly — they
are deliberately absent from this pure-formula layer.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class StarBranch:
    """A single star seated on an Earthly-Branch index (immutable).

    * ``star_id`` — canonical star token (e.g. ``"ZI_WEI"``).
    * ``family_id`` — the star family (e.g. ``"MAJOR_14"``, ``"GUIDE_AUX_4"``).
    * ``branch_index`` — 0-based Earthly-Branch index (``ZI=0..HAI=11``).
    * ``formula_id`` — the versioned placement formula that produced it.
    * ``source_status`` — provenance flag (``"SOURCE_REVIEWED"`` /
      ``"SOURCE_NEEDED"``).
    """

    star_id: str
    family_id: str
    branch_index: int
    formula_id: str
    source_status: str


__all__ = ["StarBranch"]
