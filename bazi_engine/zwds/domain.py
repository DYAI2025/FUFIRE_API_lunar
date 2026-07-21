"""Typed ZWDS coordinate IDs and safe modulo helpers (Level-0/1, stdlib only).

The Heavenly Stem, Earthly Branch, and zodiac Animal are three SEPARATE typed
things. The source guide's ``庚 / 午`` row conflated a stem (``庚``) with a
branch (``午``); modelling stems, branches, and animals as three distinct enum
classes makes that conflation structurally impossible — a ``StemId`` can never
be passed where a ``BranchId`` is expected, and an animal is never an instance
of ``BranchId`` even though both are integers in ``0..11``.

``StemId.WU`` (stem index 4) and ``BranchId.WU`` (branch index 6, 午/Horse)
share the romanization "WU" but are different tokens in different enums with
different integer values — that separation is the whole point of this module.

The modulo helpers never rely on language-specific negative-remainder
behavior; they always return a value in the canonical non-negative range.
"""

from __future__ import annotations

from enum import IntEnum


class StemId(IntEnum):
    """The 10 Heavenly Stems (天干), canonical index Jia = 0."""

    JIA = 0
    YI = 1
    BING = 2
    DING = 3
    WU = 4
    JI = 5
    GENG = 6
    XIN = 7
    REN = 8
    GUI = 9


class BranchId(IntEnum):
    """The 12 Earthly Branches (地支), canonical index Zi = 0."""

    ZI = 0
    CHOU = 1
    YIN = 2
    MAO = 3
    CHEN = 4
    SI = 5
    WU = 6
    WEI = 7
    SHEN = 8
    YOU = 9
    XU = 10
    HAI = 11


class AnimalId(IntEnum):
    """The 12 zodiac Animals, index Rat = 0.

    A DISTINCT enum from :class:`BranchId` even though both span ``0..11`` — an
    animal value is never a branch value and vice versa.
    """

    RAT = 0
    OX = 1
    TIGER = 2
    RABBIT = 3
    DRAGON = 4
    SNAKE = 5
    HORSE = 6
    GOAT = 7
    MONKEY = 8
    ROOSTER = 9
    DOG = 10
    PIG = 11


def mod12(x: int) -> int:
    """Return ``x`` reduced into ``0..11`` without negative-remainder surprises."""
    return ((x % 12) + 12) % 12


def mod10(x: int) -> int:
    """Return ``x`` reduced into ``0..9`` without negative-remainder surprises."""
    return ((x % 10) + 10) % 10
