"""
dignities.py — Planetary dignity lookup tables and helpers.

Level 4 module. Provides essential dignity classifications:
domicile (rulership), detriment, exaltation, fall per planet and zodiac sign.
Pure functions, no side effects.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Literal, Optional

DignityType = Literal["domicile", "detriment", "exaltation", "fall"]

# Zodiac sign indices (0-based, tropical)
# 0=Aries, 1=Taurus, 2=Gemini, 3=Cancer, 4=Leo, 5=Virgo,
# 6=Libra, 7=Scorpio, 8=Sagittarius, 9=Capricorn, 10=Aquarius, 11=Pisces

# Domicile (rulership): planet rules this sign
_DOMICILE: Dict[str, List[int]] = {
    "Sun": [4],            # Leo
    "Moon": [3],           # Cancer
    "Mercury": [2, 5],     # Gemini, Virgo
    "Venus": [1, 6],       # Taurus, Libra
    "Mars": [0, 7],        # Aries, Scorpio
    "Jupiter": [8, 11],    # Sagittarius, Pisces
    "Saturn": [9, 10],     # Capricorn, Aquarius
    "Uranus": [10],        # Aquarius
    "Neptune": [11],       # Pisces
    "Pluto": [7],          # Scorpio
}

# Detriment: opposite of domicile
_DETRIMENT: Dict[str, List[int]] = {
    "Sun": [10],           # Aquarius
    "Moon": [9],           # Capricorn
    "Mercury": [8, 11],    # Sagittarius, Pisces
    "Venus": [0, 7],       # Aries, Scorpio
    "Mars": [1, 6],        # Taurus, Libra
    "Jupiter": [2, 5],     # Gemini, Virgo
    "Saturn": [3, 4],      # Cancer, Leo
    "Uranus": [4],         # Leo
    "Neptune": [5],        # Virgo
    "Pluto": [1],          # Taurus
}

# Exaltation: planet is exalted in this sign
_EXALTATION: Dict[str, int] = {
    "Sun": 0,              # Aries
    "Moon": 1,             # Taurus
    "Mercury": 5,          # Virgo
    "Venus": 11,           # Pisces
    "Mars": 9,             # Capricorn
    "Jupiter": 3,          # Cancer
    "Saturn": 6,           # Libra
    "Uranus": 7,           # Scorpio
    "Neptune": 3,          # Cancer (modern)
    "Pluto": 4,            # Leo (modern)
}

# Fall: opposite of exaltation
_FALL: Dict[str, int] = {
    "Sun": 6,              # Libra
    "Moon": 7,             # Scorpio
    "Mercury": 11,         # Pisces
    "Venus": 5,            # Virgo
    "Mars": 3,             # Cancer
    "Jupiter": 9,          # Capricorn
    "Saturn": 0,           # Aries
    "Uranus": 1,           # Taurus
    "Neptune": 9,          # Capricorn (modern)
    "Pluto": 10,           # Aquarius (modern)
}

# Dignity weight modifiers for composite weight calculation
DIGNITY_MULTIPLIERS: Dict[DignityType, float] = {
    "domicile": 1.2,
    "exaltation": 1.15,
    "detriment": 0.85,
    "fall": 0.8,
}


@dataclass(frozen=True)
class PlanetDignity:
    """Dignity status of a planet in a specific zodiac sign."""

    planet: str
    sign_index: int
    dignity: Optional[DignityType]
    multiplier: float


def get_dignity(planet: str, sign_index: int) -> Optional[DignityType]:
    """Return the dignity type for a planet in a given sign, or None if peregrine.

    Args:
        planet: Capitalized planet name (e.g. "Mars", "Jupiter").
        sign_index: Zodiac sign index 0-11 (0=Aries).

    Returns:
        DignityType or None if the planet has no special dignity in this sign.
    """
    if planet in _DOMICILE and sign_index in _DOMICILE[planet]:
        return "domicile"
    if planet in _EXALTATION and _EXALTATION[planet] == sign_index:
        return "exaltation"
    if planet in _DETRIMENT and sign_index in _DETRIMENT[planet]:
        return "detriment"
    if planet in _FALL and _FALL[planet] == sign_index:
        return "fall"
    return None


def get_planet_dignity(planet: str, sign_index: int) -> PlanetDignity:
    """Return full dignity info including multiplier for a planet/sign pair.

    Args:
        planet: Capitalized planet name.
        sign_index: Zodiac sign index 0-11.

    Returns:
        PlanetDignity with dignity type and weight multiplier.
    """
    dignity = get_dignity(planet, sign_index)
    multiplier = DIGNITY_MULTIPLIERS.get(dignity, 1.0) if dignity else 1.0
    return PlanetDignity(
        planet=planet,
        sign_index=sign_index,
        dignity=dignity,
        multiplier=multiplier,
    )


def dignity_multiplier(planet: str, longitude: float) -> float:
    """Return the dignity weight multiplier for a planet at a given longitude.

    Convenience function that derives sign from longitude.

    Args:
        planet: Capitalized planet name (e.g. "Sun", "Mars").
        longitude: Ecliptic longitude in degrees (0-360).

    Returns:
        Multiplier: 1.2 (domicile), 1.15 (exaltation), 0.85 (detriment),
        0.8 (fall), or 1.0 (peregrine).
    """
    sign_index = int(longitude // 30) % 12
    dignity = get_dignity(planet, sign_index)
    if dignity is None:
        return 1.0
    return DIGNITY_MULTIPLIERS[dignity]
