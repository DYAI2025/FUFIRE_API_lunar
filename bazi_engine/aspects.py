"""
aspects.py — Planetary aspect calculations.

Computes angular aspects (conjunction, opposition, trine, square, sextile)
between all planet pairs using differentiated per-planet orb tables.
Pure function, no side effects.

Orb model:
  effective_orb = (base_orb_A + base_orb_B) / 2 × aspect_factor

Base orbs follow standard professional astrology conventions:
luminaries (Sun/Moon) get the widest orbs, outer/minor bodies the narrowest.
"""
from __future__ import annotations

from typing import Any, Dict, List, Tuple

# ── Per-planet base orbs (degrees) ───────────────────────────────────────────
# Luminaries: widest orbs (most visible influence)
# Personal planets: medium orbs
# Outer planets: narrower orbs (generational, slower)
# Minor bodies: tightest orbs (supplementary)

PLANET_BASE_ORBS: Dict[str, float] = {
    "Sun": 10.0,
    "Moon": 10.0,
    "Mercury": 7.0,
    "Venus": 7.0,
    "Mars": 7.0,
    "Jupiter": 8.0,
    "Saturn": 8.0,
    "Uranus": 5.0,
    "Neptune": 5.0,
    "Pluto": 5.0,
    "Chiron": 3.0,
    "Lilith": 2.0,
    "NorthNode": 3.0,
    "TrueNorthNode": 3.0,
}

# Default base orb for unknown bodies
_DEFAULT_BASE_ORB = 4.0

# ── Aspect definitions with factors ─────────────────────────────────────────
# (name, exact_angle, orb_factor)
# Major aspects (conjunction/opposition/trine) get full orb.
# Square slightly tighter, sextile tighter still.

ASPECT_DEFS: List[Tuple[str, float, float]] = [
    ("conjunction", 0.0, 1.0),
    ("semi-sextile", 30.0, 0.5),
    ("sextile", 60.0, 0.75),
    ("square", 90.0, 0.875),
    ("trine", 120.0, 1.0),
    ("quincunx", 150.0, 0.5),
    ("opposition", 180.0, 1.0),
]

# Major planets for aspect calculation
ASPECT_PLANETS = [
    "Sun", "Moon", "Mercury", "Venus", "Mars",
    "Jupiter", "Saturn", "Uranus", "Neptune", "Pluto",
]


def _angular_distance(lon1: float, lon2: float) -> float:
    """Shortest angular distance between two ecliptic longitudes."""
    diff = abs(lon1 - lon2) % 360
    return min(diff, 360 - diff)


def effective_orb(planet1: str, planet2: str, aspect_factor: float) -> float:
    """Calculate effective orb for a planet pair and aspect type.

    effective_orb = (base_orb_A + base_orb_B) / 2 × aspect_factor
    """
    orb_a = PLANET_BASE_ORBS.get(planet1, _DEFAULT_BASE_ORB)
    orb_b = PLANET_BASE_ORBS.get(planet2, _DEFAULT_BASE_ORB)
    return (orb_a + orb_b) / 2.0 * aspect_factor


def compute_aspects(
    bodies: Dict[str, Dict[str, Any]],
    planets: List[str] | None = None,
) -> List[Dict[str, Any]]:
    """
    Compute aspects between all planet pairs using differentiated orbs.

    Args:
        bodies: Dict of planet name -> {longitude, ...}
        planets: Which planets to include (default: ASPECT_PLANETS)

    Returns:
        List of aspect dicts: {planet1, planet2, type, angle, orb,
                               exact_angle, effective_orb}
    """
    if planets is None:
        planets = [
            p for p in ASPECT_PLANETS
            if p in bodies and "longitude" in bodies[p] and bodies[p]["longitude"] is not None
        ]

    aspects: List[Dict[str, Any]] = []

    for i, p1 in enumerate(planets):
        if p1 not in bodies or bodies[p1].get("longitude") is None:
            continue
        for p2 in planets[i + 1:]:
            if p2 not in bodies or bodies[p2].get("longitude") is None:
                continue
            lon1 = bodies[p1]["longitude"]
            lon2 = bodies[p2]["longitude"]
            dist = _angular_distance(lon1, lon2)

            for name, exact, factor in ASPECT_DEFS:
                eff_orb = effective_orb(p1, p2, factor)
                deviation = abs(dist - exact)
                if deviation <= eff_orb:
                    aspects.append({
                        "planet1": p1,
                        "planet2": p2,
                        "type": name,
                        "angle": round(dist, 2),
                        "orb": round(deviation, 2),
                        "exact_angle": exact,
                        "effective_orb": round(eff_orb, 2),
                    })
                    break  # one aspect per pair

    # Sort by tightest orb first
    aspects.sort(key=lambda a: a["orb"])
    return aspects
