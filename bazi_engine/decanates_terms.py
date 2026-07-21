"""
decanates_terms.py — Decanate and Egyptian Terms (Bounds) lookup tables.

Level 4 module. Provides sub-sign rulership classifications used by enterprise
clients for fine-grained planetary position interpretation:

    - Decanates (декаnates / decans): each 30° sign is divided into three 10°
      sectors, each ruled by a planet. This module uses the **Triplicity
      (Chaldean) decan system** — the first decan is ruled by the sign's own
      planet, and the second and third decans rotate through the rulers of the
      same element in zodiacal order.

    - Egyptian Terms (Bounds): each sign is divided into five unequal segments
      totalling 30°, each ruled by one of the five visible (non-luminary)
      planets — Mercury, Venus, Mars, Jupiter, Saturn. The table below uses
      the canonical **Egyptian Bounds** as reported by Ptolemy in
      *Tetrabiblos* I.21 and corroborated by Vettius Valens. The order of
      planets within each sign is fixed by tradition; sums per sign always
      equal 30°.

Pure functions, no side effects. Mirrors the shape of ``dignities.py`` so
downstream consumers (impact.py, narrative.py) can use the same idioms.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple

# Zodiac sign indices (0-based, tropical):
# 0=Aries, 1=Taurus, 2=Gemini, 3=Cancer, 4=Leo, 5=Virgo,
# 6=Libra, 7=Scorpio, 8=Sagittarius, 9=Capricorn, 10=Aquarius, 11=Pisces

# ── Decanates ────────────────────────────────────────────────────────────────
#
# Triplicity (Chaldean) system. For each sign, a tuple of three ruler names
# covering the 0–10°, 10–20°, 20–30° sectors of the sign.
#
# Element rotation: Fire (Aries→Leo→Sagittarius), Earth (Taurus→Virgo→
# Capricorn), Air (Gemini→Libra→Aquarius), Water (Cancer→Scorpio→Pisces).
# Within an element, the first decan is the sign's own ruler; second and
# third decans use the next signs of the same element, taking each sign's
# own ruler.

_DECANATE_RULERS: Dict[int, Tuple[str, str, str]] = {
    0:  ("Mars",    "Sun",     "Jupiter"),  # Aries:    Mars, Sun (Leo), Jupiter (Sagittarius)
    1:  ("Venus",   "Mercury", "Saturn"),   # Taurus:   Venus, Mercury (Virgo), Saturn (Capricorn)
    2:  ("Mercury", "Venus",   "Saturn"),   # Gemini:   Mercury, Venus (Libra), Saturn (Aquarius)
    3:  ("Moon",    "Mars",    "Jupiter"),  # Cancer:   Moon, Mars (Scorpio), Jupiter (Pisces)
    4:  ("Sun",     "Jupiter", "Mars"),     # Leo:      Sun, Jupiter (Sagittarius), Mars (Aries)
    5:  ("Mercury", "Saturn",  "Venus"),    # Virgo:    Mercury, Saturn (Capricorn), Venus (Taurus)
    6:  ("Venus",   "Saturn",  "Mercury"),  # Libra:    Venus, Saturn (Aquarius), Mercury (Gemini)
    7:  ("Mars",    "Jupiter", "Moon"),     # Scorpio:  Mars, Jupiter (Pisces), Moon (Cancer)
    8:  ("Jupiter", "Mars",    "Sun"),      # Sagittarius: Jupiter, Mars (Aries), Sun (Leo)
    9:  ("Saturn",  "Venus",   "Mercury"),  # Capricorn: Saturn, Venus (Taurus), Mercury (Virgo)
    10: ("Saturn",  "Mercury", "Venus"),    # Aquarius: Saturn, Mercury (Gemini), Venus (Libra)
    11: ("Jupiter", "Moon",    "Mars"),     # Pisces:   Jupiter, Moon (Cancer), Mars (Scorpio)
}


@dataclass(frozen=True)
class Decanate:
    """Decanate (10° sub-sign) info for a zodiacal longitude."""

    sign_index: int
    decan_index: int          # 0, 1, or 2
    ruler: str
    start_degree: float       # absolute longitude (0–360) of decan start
    end_degree: float         # absolute longitude (0–360) of decan end (exclusive)


def get_decanate(longitude: float) -> Decanate:
    """Return the decanate that contains a given ecliptic longitude.

    Args:
        longitude: Ecliptic longitude in degrees. Wrapped to [0, 360).

    Returns:
        Decanate dataclass with sign, decan index (0/1/2), ruler, and the
        absolute degree boundaries of the 10° sector containing ``longitude``.
    """
    lon = longitude % 360
    sign_index = int(lon // 30)
    pos_in_sign = lon - sign_index * 30
    decan_index = int(pos_in_sign // 10)
    ruler = _DECANATE_RULERS[sign_index][decan_index]
    sign_start = sign_index * 30.0
    return Decanate(
        sign_index=sign_index,
        decan_index=decan_index,
        ruler=ruler,
        start_degree=sign_start + decan_index * 10.0,
        end_degree=sign_start + (decan_index + 1) * 10.0,
    )


def decanate_ruler(longitude: float) -> str:
    """Convenience wrapper: return the decanate ruler for a longitude."""
    return get_decanate(longitude).ruler


# ── Egyptian Terms (Bounds) ──────────────────────────────────────────────────
#
# Each sign is divided into five unequal segments totalling 30°. Each segment
# is ruled by one of the five non-luminary visible planets. The table below is
# the **Egyptian Terms** per Ptolemy *Tetrabiblos* I.21 — the most widely cited
# Hellenistic system.
#
# Format per sign: list of (ruler, end_degree_within_sign) tuples in order.
# The end_degree is cumulative within the sign (0–30) and the segment runs
# from the previous tuple's end (or 0 for the first) up to its own end.

_EGYPTIAN_TERMS: Dict[int, List[Tuple[str, float]]] = {
    0:  [("Jupiter", 6),  ("Venus",   12), ("Mercury", 20), ("Mars",    25), ("Saturn",  30)],  # Aries
    1:  [("Venus",   8),  ("Mercury", 14), ("Jupiter", 22), ("Saturn",  27), ("Mars",    30)],  # Taurus
    2:  [("Mercury", 6),  ("Jupiter", 12), ("Venus",   17), ("Mars",    24), ("Saturn",  30)],  # Gemini
    3:  [("Mars",    7),  ("Venus",   13), ("Mercury", 19), ("Jupiter", 26), ("Saturn",  30)],  # Cancer
    4:  [("Jupiter", 6),  ("Venus",   11), ("Saturn",  18), ("Mercury", 24), ("Mars",    30)],  # Leo
    5:  [("Mercury", 7),  ("Venus",   17), ("Jupiter", 21), ("Mars",    28), ("Saturn",  30)],  # Virgo
    6:  [("Saturn",  6),  ("Mercury", 14), ("Jupiter", 21), ("Venus",   28), ("Mars",    30)],  # Libra
    7:  [("Mars",    7),  ("Venus",   11), ("Mercury", 19), ("Jupiter", 24), ("Saturn",  30)],  # Scorpio
    8:  [("Jupiter", 12), ("Venus",   17), ("Mercury", 21), ("Saturn",  26), ("Mars",    30)],  # Sagittarius
    9:  [("Mercury", 7),  ("Jupiter", 14), ("Venus",   22), ("Saturn",  26), ("Mars",    30)],  # Capricorn
    10: [("Mercury", 7),  ("Venus",   13), ("Jupiter", 20), ("Mars",    25), ("Saturn",  30)],  # Aquarius
    11: [("Venus",   12), ("Jupiter", 16), ("Mercury", 19), ("Mars",    28), ("Saturn",  30)],  # Pisces
}


@dataclass(frozen=True)
class Term:
    """Egyptian Term (bound) info for a zodiacal longitude."""

    sign_index: int
    ruler: str
    start_degree: float       # absolute longitude (0–360) of term start
    end_degree: float         # absolute longitude (0–360) of term end (exclusive)


def get_term(longitude: float) -> Term:
    """Return the Egyptian Term that contains a given ecliptic longitude.

    Args:
        longitude: Ecliptic longitude in degrees. Wrapped to [0, 360).

    Returns:
        Term dataclass with sign, ruler, and absolute degree boundaries.
    """
    lon = longitude % 360
    sign_index = int(lon // 30)
    pos_in_sign = lon - sign_index * 30
    sign_start = sign_index * 30.0
    prev_end = 0.0
    for ruler, end_in_sign in _EGYPTIAN_TERMS[sign_index]:
        if pos_in_sign < end_in_sign:
            return Term(
                sign_index=sign_index,
                ruler=ruler,
                start_degree=sign_start + prev_end,
                end_degree=sign_start + end_in_sign,
            )
        prev_end = end_in_sign
    # Reached the final term boundary (pos_in_sign == 30 exactly after wrap):
    # fall through to the last bound — defensive against floating-point edges.
    last_ruler, last_end = _EGYPTIAN_TERMS[sign_index][-1]
    prev_end = _EGYPTIAN_TERMS[sign_index][-2][1] if len(_EGYPTIAN_TERMS[sign_index]) >= 2 else 0.0
    return Term(
        sign_index=sign_index,
        ruler=last_ruler,
        start_degree=sign_start + prev_end,
        end_degree=sign_start + last_end,
    )


def term_ruler(longitude: float) -> str:
    """Convenience wrapper: return the Egyptian Term ruler for a longitude."""
    return get_term(longitude).ruler


# ── Combined sub-sign rulership ──────────────────────────────────────────────


@dataclass(frozen=True)
class SubSignRulers:
    """All sub-sign rulers for a single zodiacal position."""

    longitude: float
    decanate: Decanate
    term: Term


def get_sub_sign_rulers(longitude: float) -> SubSignRulers:
    """Return both decanate and Egyptian Term info for a longitude.

    Convenience aggregator for callers that want both classifications at once
    (e.g. enterprise narrative generation).
    """
    return SubSignRulers(
        longitude=longitude % 360,
        decanate=get_decanate(longitude),
        term=get_term(longitude),
    )


# ── Optional ruler-match boost ───────────────────────────────────────────────
#
# Convention parallel to dignities.DIGNITY_MULTIPLIERS: callers that aggregate
# planet weights may apply a small boost when the planet under consideration
# also rules its decanate or term. Conservative starting values — these are
# intentionally smaller than dignity boosts because sub-sign rulership is a
# weaker classical signal than full dignity.

DECANATE_MATCH_BOOST: float = 1.05
TERM_MATCH_BOOST: float = 1.03


def decanate_match(planet: str, longitude: float) -> bool:
    """Return True if ``planet`` rules the decanate at ``longitude``."""
    return decanate_ruler(longitude) == planet


def term_match(planet: str, longitude: float) -> bool:
    """Return True if ``planet`` rules the Egyptian Term at ``longitude``."""
    return term_ruler(longitude) == planet


def sub_sign_multiplier(planet: str, longitude: float) -> float:
    """Combined decanate + term boost for a planet at a longitude.

    Returns 1.0 when the planet rules neither, ``DECANATE_MATCH_BOOST`` for
    decanate-only, ``TERM_MATCH_BOOST`` for term-only, and the product for
    both. Useful in weighted Wu-Xing fusion where sub-sign rulership refines
    full dignity classification (see ``dignities.dignity_multiplier``).

    The classifications are independent — a planet may rule one, both, or
    neither at a given longitude — so multiplying preserves the right
    semantics when both fire.
    """
    multiplier = 1.0
    if decanate_match(planet, longitude):
        multiplier *= DECANATE_MATCH_BOOST
    if term_match(planet, longitude):
        multiplier *= TERM_MATCH_BOOST
    return multiplier


# ── Public surface re-exports for typed consumers ─────────────────────────────

__all__ = [
    "Decanate",
    "Term",
    "SubSignRulers",
    "DECANATE_MATCH_BOOST",
    "TERM_MATCH_BOOST",
    "get_decanate",
    "decanate_ruler",
    "decanate_match",
    "get_term",
    "term_ruler",
    "term_match",
    "get_sub_sign_rulers",
    "sub_sign_multiplier",
]
