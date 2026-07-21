"""ZWDS-P1-09 — Five-Elements Bureau (五行局) from the Ming-palace stem/branch.

Pure 0-based formula (design-pack ``zwds_formula_spec.md`` §8) over the resolved
Ming palace. This module imports ONLY the stdlib — no ``bazi``/``western``/
``fusion``/``impact``/routers/``app`` and no zwds siblings.

Given the Ming palace's Heavenly-Stem index ``stem0`` (0..9) and Earthly-Branch
index ``branch0`` (0..11):

* Parity guard — a valid pair satisfies ``(stem0 - branch0) % 2 == 0``; anything
  else is rejected before lookup.
* ``stem_group  = (stem0 // 2) + 1``
* ``branch_group = ((branch0 % 6) // 2) + 1``
* ``v = ((stem_group + branch_group - 1) % 5) + 1`` -> Bureau via ``_BUREAU_BY_V``.

The parity guard raises :class:`ValueError` (the design-pack allows the ZWDS
error base "if apt"; this module deliberately keeps its imports to the stdlib
only, so the stdlib exception is used).
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Dict, Mapping, Tuple

FORMULA_ID = "five-elements-bureau.mnemonic-v1"
SOURCE_STATUS = "SOURCE_REVIEWED"

# v -> (bureau id, phase id, number). Design-pack §8 mnemonic mapping.
_BUREAU_BY_V: Mapping[int, Tuple[str, str, int]] = MappingProxyType(
    {
        1: ("WOOD_3", "WOOD", 3),
        2: ("METAL_4", "METAL", 4),
        3: ("WATER_2", "WATER", 2),
        4: ("FIRE_6", "FIRE", 6),
        5: ("EARTH_5", "EARTH", 5),
    }
)


@dataclass(frozen=True)
class Bureau:
    """The Five-Elements Bureau of a ZWDS chart (immutable)."""

    id: str
    phase_id: str
    number: int
    formula_id: str
    source_status: str


def _has_valid_parity(stem0: int, branch0: int) -> bool:
    """A ZWDS Ming-palace pair is valid only when stem/branch share parity."""
    return (stem0 - branch0) % 2 == 0


def _bureau_v(stem0: int, branch0: int) -> int:
    """The mnemonic bureau selector ``v`` in ``1..5`` (assumes valid parity)."""
    stem_group = (stem0 // 2) + 1
    branch_group = ((branch0 % 6) // 2) + 1
    return ((stem_group + branch_group - 1) % 5) + 1


def five_elements_bureau(stem0: int, branch0: int) -> Bureau:
    """Resolve the Five-Elements Bureau from a Ming-palace ``(stem0, branch0)``.

    Raises :class:`ValueError` when the pair fails the parity invariant.
    """
    if not _has_valid_parity(stem0, branch0):
        raise ValueError(
            "invalid Five-Elements Bureau parity: "
            f"(stem0={stem0}, branch0={branch0}) must satisfy "
            "(stem0 - branch0) % 2 == 0"
        )
    bureau_id, phase_id, number = _BUREAU_BY_V[_bureau_v(stem0, branch0)]
    return Bureau(
        id=bureau_id,
        phase_id=phase_id,
        number=number,
        formula_id=FORMULA_ID,
        source_status=SOURCE_STATUS,
    )


def bureau_pair_table() -> Dict[Tuple[int, int], str]:
    """Return the derived 60-pair table ``(stem0, branch0) -> bureau id``.

    Contains exactly the 60 valid-parity pairs, generated from the mnemonic
    formula. Returns a fresh mutable copy of the frozen :data:`BUREAU_TABLE`
    snapshot.
    """
    return {
        (stem0, branch0): _BUREAU_BY_V[_bureau_v(stem0, branch0)][0]
        for stem0 in range(10)
        for branch0 in range(12)
        if _has_valid_parity(stem0, branch0)
    }


# Immutable 60-pair snapshot, derived once from the formula at import time.
BUREAU_TABLE: Mapping[Tuple[int, int], str] = MappingProxyType(bureau_pair_table())
