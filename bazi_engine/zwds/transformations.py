"""ZWDS-P1-13 — versioned Four-Transformations (四化) table + loader.

The Four-Transformations mapping (year stem -> {HUA_LU, HUA_QUAN, HUA_KE,
HUA_JI} -> star) is **data, not code**: at least two documented tabulations
differ in the Geng (庚) and Ren (壬) HUA_KE cells, so the table must be a
versioned data file whose ``table_id`` and ``sha256`` are disclosed in every
response (design-pack ``zwds_formula_spec.md`` §12).

The shipped table is the mainstream, iztro-corroborated tabulation. It is a
``SOURCE_NEEDED`` seed — implementation-corroborated, NOT historically
source-reviewed — with two contested cells (``GENG.HUA_KE``, ``REN.HUA_KE``).

This module imports ONLY :mod:`bazi_engine.zwds.domain`, the stdlib, and
``json``/``hashlib`` for the table load; it never reaches into
``bazi``/``western``/``fusion``/``impact``/routers/``app``.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Dict, List

from bazi_engine.resource_loader import package_resource
from bazi_engine.zwds.domain import StemId

# The versioned ruleset data file (bazi_engine/data/zwds/rulesets/<id>/...).
TABLE_PATH = package_resource(
    "bazi_engine.data",
    "zwds",
    "rulesets",
    "zwds.fufire.core-seed.v1",
    "transformations.json",
)

# Fixed emission order of the four transformation types (design-pack §12).
_TRANSFORMATION_ORDER: tuple[str, ...] = ("HUA_LU", "HUA_QUAN", "HUA_KE", "HUA_JI")

_TRANSFORMATION_SCOPE: str = "natal"


def _load_raw_bytes() -> bytes:
    """Return the raw table bytes (used for both parsing and hashing)."""
    return TABLE_PATH.read_bytes()


_RAW_BYTES: bytes = _load_raw_bytes()
_TABLE: Dict[str, Any] = json.loads(_RAW_BYTES)

# Public, disclosed provenance of the loaded table.
TABLE_ID: str = str(_TABLE["table_id"])
SOURCE_STATUS: str = str(_TABLE["source_status"])
CONTESTED_CELLS: tuple[str, ...] = tuple(_TABLE.get("contested_cells", []))
# sha256 over the raw file bytes — the value the ruleset envelope must disclose.
TABLE_SHA256: str = hashlib.sha256(_RAW_BYTES).hexdigest()

_ROWS: Dict[str, Dict[str, str]] = _TABLE["rows"]


@dataclass(frozen=True)
class Transformation:
    """One of the four star transformations sourced by a year stem (immutable).

    * ``type`` — the transformation kind (``HUA_LU``/``HUA_QUAN``/``HUA_KE``/
      ``HUA_JI``).
    * ``star_id`` — the transformed star (one of the 18 core-seed stars).
    * ``source_stem_id`` — the year Heavenly Stem that induces it (e.g. ``JIA``).
    * ``table_id`` — the versioned table that produced the mapping.
    * ``scope`` — placement scope; ``"natal"`` for the natal chart.
    """

    type: str
    star_id: str
    source_stem_id: str
    table_id: str
    scope: str = _TRANSFORMATION_SCOPE


def four_transformations(year_stem_index: int) -> List[Transformation]:
    """The four transformations induced by ``year_stem_index`` (0..9, JIA=0).

    Returns exactly four :class:`Transformation` records in the fixed order
    ``HUA_LU, HUA_QUAN, HUA_KE, HUA_JI``.
    """
    stem_name = StemId(year_stem_index).name
    row = _ROWS[stem_name]
    return [
        Transformation(
            type=hua_type,
            star_id=row[hua_type],
            source_stem_id=stem_name,
            table_id=TABLE_ID,
            scope=_TRANSFORMATION_SCOPE,
        )
        for hua_type in _TRANSFORMATION_ORDER
    ]


def transformation_types_by_star(year_stem_index: int) -> Dict[str, List[str]]:
    """Map each transformed ``star_id`` -> its transformation type list.

    Lets chart assembly attach ``transformation_types`` to star placements. A
    star that receives more than one transformation from the same stem would
    accumulate multiple entries (the shipped seed table assigns at most one).
    """
    by_star: Dict[str, List[str]] = {}
    for t in four_transformations(year_stem_index):
        by_star.setdefault(t.star_id, []).append(t.type)
    return by_star
