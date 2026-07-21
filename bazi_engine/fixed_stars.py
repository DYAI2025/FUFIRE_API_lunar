"""
fixed_stars.py — Fixed star catalog and conjunction detection.

Level 4 module. Provides a catalog of astrologically significant fixed stars
with J2000.0 tropical ecliptic longitudes and pure conjunction detection.
Pure functions, no side effects.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List


@dataclass(frozen=True)
class FixedStar:
    """A fixed star with its J2000.0 tropical ecliptic position."""

    name: str
    ecliptic_lon: float  # tropical ecliptic longitude, degrees, J2000.0
    magnitude: float     # apparent visual magnitude (lower = brighter)
    nature: str          # traditional nature: "benefic", "malefic", "neutral"


@dataclass(frozen=True)
class FixedStarConjunction:
    """A detected conjunction between a planet and a fixed star."""

    star: FixedStar
    planet: str
    orb: float  # angular separation in degrees (always >= 0)


# ---------------------------------------------------------------------------
# Catalog — J2000.0 tropical ecliptic longitudes
# Source: standard astrological tables (Bernadette Brady, Vivian Robson)
# ---------------------------------------------------------------------------
FIXED_STARS: List[FixedStar] = [
    FixedStar("Algol",         56.17,  2.12, "malefic"),   # β Persei
    FixedStar("Alcyone",       60.00,  2.87, "malefic"),   # η Tauri (Pleiades)
    FixedStar("Aldebaran",     69.78,  0.85, "benefic"),   # α Tauri — Royal Star
    FixedStar("Rigel",         76.83,  0.12, "benefic"),   # β Orionis
    FixedStar("Capella",       81.85,  0.08, "neutral"),   # α Aurigae
    FixedStar("Bellatrix",     80.96,  1.64, "malefic"),   # γ Orionis
    FixedStar("Betelgeuse",    88.75,  0.50, "benefic"),   # α Orionis
    FixedStar("Sirius",       104.08, -1.46, "benefic"),   # α Canis Majoris — brightest star
    FixedStar("Procyon",      115.78,  0.34, "benefic"),   # α Canis Minoris
    FixedStar("Pollux",       113.21,  1.14, "malefic"),   # β Geminorum
    FixedStar("Regulus",      149.83,  1.35, "benefic"),   # α Leonis — Royal Star
    FixedStar("Zosma",        161.32,  2.56, "malefic"),   # δ Leonis
    FixedStar("Denebola",     171.62,  2.14, "malefic"),   # β Leonis
    FixedStar("Vindemiatrix", 189.93,  2.83, "malefic"),   # ε Virginis
    FixedStar("Spica",        203.83,  0.97, "benefic"),   # α Virginis — Behenian
    FixedStar("Arcturus",     204.23, -0.05, "benefic"),   # α Bootis — Behenian
    FixedStar("Antares",      249.77,  0.92, "malefic"),   # α Scorpii — Royal Star
    FixedStar("Vega",         285.32,  0.03, "benefic"),   # α Lyrae — Behenian
    FixedStar("Altair",       301.78,  0.76, "neutral"),   # α Aquilae
    FixedStar("Fomalhaut",    333.87,  1.16, "benefic"),   # α Piscis Austrini — Royal Star
    FixedStar("Scheat",       359.37,  2.42, "malefic"),   # β Pegasi
]


def fixed_star_conjunctions(
    planet_name: str,
    planet_lon: float,
    orb: float = 1.0,
) -> List[FixedStarConjunction]:
    """Return all fixed stars within orb of a planet's ecliptic longitude.

    Args:
        planet_name: Capitalized planet name (e.g. "Mars", "Sun").
        planet_lon: Tropical ecliptic longitude in degrees (0–360).
        orb: Maximum angular separation in degrees (default 1.0).

    Returns:
        List of FixedStarConjunction sorted by ascending orb.
    """
    results: List[FixedStarConjunction] = []
    for star in FIXED_STARS:
        separation = abs(planet_lon - star.ecliptic_lon) % 360.0
        if separation > 180.0:
            separation = 360.0 - separation
        if separation <= orb:
            results.append(FixedStarConjunction(star=star, planet=planet_name, orb=separation))
    results.sort(key=lambda c: c.orb)
    return results


def conjunctions_for_chart(
    planet_positions: dict[str, float],
    orb: float = 1.0,
) -> List[FixedStarConjunction]:
    """Return all fixed-star conjunctions for a full set of planet positions.

    Args:
        planet_positions: Mapping of planet name → tropical ecliptic longitude.
        orb: Maximum angular separation in degrees (default 1.0).

    Returns:
        List of FixedStarConjunction sorted by ascending orb.
    """
    results: List[FixedStarConjunction] = []
    for planet, lon in planet_positions.items():
        results.extend(fixed_star_conjunctions(planet, lon, orb))
    results.sort(key=lambda c: c.orb)
    return results
