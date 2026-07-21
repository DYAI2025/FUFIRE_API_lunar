"""
impact.py — Natal-vs-transit aspect matching for /impact/active.

Level 4 module. Computes which transit planets form significant aspects
(orb ≤ 8°) to natal positions, with strength classification and composite
weight. Pure functions, no side effects.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from .aspects import ASPECT_DEFS, _angular_distance
from .dignities import dignity_multiplier, get_dignity
from .impact_types import ActivePlanet, BaziResonance, Strength, WuXingElement
from .transit import PLANET_WEIGHTS

# Maximum orb for natal-transit aspect matching (PRD P0-3)
MAX_ORB_DEG = 8.0

# Zodiac sign index → Wu-Xing element mapping
# Standard Chinese astrology: sectors grouped by element
_SIGN_TO_ELEMENT: Dict[int, WuXingElement] = {
    0: "fire",   # Aries
    1: "earth",  # Taurus
    2: "metal",  # Gemini
    3: "water",  # Cancer
    4: "fire",   # Leo
    5: "earth",  # Virgo
    6: "metal",  # Libra
    7: "water",  # Scorpio
    8: "fire",   # Sagittarius
    9: "earth",  # Capricorn
    10: "metal", # Aquarius
    11: "water", # Pisces
}

# Aspect type weights — tighter aspect types get higher weight
_ASPECT_TYPE_WEIGHT: Dict[str, float] = {
    "conjunction": 1.0,
    "opposition": 0.9,
    "trine": 0.85,
    "square": 0.8,
    "sextile": 0.7,
    "quincunx": 0.5,
    "semi-sextile": 0.5,
}


def classify_strength(orb: float) -> Strength:
    """Classify aspect strength from orb (PRD P0-3 rule)."""
    if orb < 3.0:
        return "high"
    if orb <= 5.0:
        return "medium"
    return "low"


# House type multipliers (angular = strongest, cadent = weakest)
_ANGULAR_HOUSES = {1, 4, 7, 10}
_SUCCEDENT_HOUSES = {2, 5, 8, 11}
_CADENT_HOUSES = {3, 6, 9, 12}

HOUSE_MULTIPLIERS: Dict[str, float] = {
    "angular": 1.3,
    "succedent": 1.0,
    "cadent": 0.8,
}


def determine_house(
    planet_lon: float,
    house_cusps: Dict[str, float],
) -> int:
    """Determine which house (1–12) a planet falls in based on house cusps.

    Args:
        planet_lon: Planet ecliptic longitude (0–360).
        house_cusps: Dict of house number (str "1"–"12") → cusp longitude.

    Returns:
        House number (1–12). Returns 1 if cusps are invalid.
    """
    if not house_cusps or len(house_cusps) < 12:
        return 1

    cusps = [house_cusps.get(str(i), 0.0) for i in range(1, 13)]

    for i in range(12):
        cusp_start = cusps[i] % 360
        cusp_end = cusps[(i + 1) % 12] % 360
        lon = planet_lon % 360

        if cusp_start <= cusp_end:
            if cusp_start <= lon < cusp_end:
                return i + 1
        else:
            # Wraps around 0°
            if lon >= cusp_start or lon < cusp_end:
                return i + 1

    return 1


def house_multiplier(house_num: int) -> float:
    """Return the weight multiplier for a house number."""
    if house_num in _ANGULAR_HOUSES:
        return HOUSE_MULTIPLIERS["angular"]
    if house_num in _CADENT_HOUSES:
        return HOUSE_MULTIPLIERS["cadent"]
    return HOUSE_MULTIPLIERS["succedent"]


def _composite_weight(
    orb: float,
    planet_name: str,
    aspect_type: str,
    house_mult: float = 1.0,
    dig_mult: float = 1.0,
) -> float:
    """Compute composite weight (0-1) from orb, planet rank, aspect type, house, and dignity.

    Combines three normalized factors then applies house and dignity multipliers:
    - Orb factor: 1.0 at exact, 0.0 at MAX_ORB_DEG
    - Planet weight: normalized from PLANET_WEIGHTS (heavier planets score higher)
    - Aspect factor: from _ASPECT_TYPE_WEIGHT
    - House multiplier: angular x1.3, succedent x1.0, cadent x0.8
    - Dignity multiplier: domicile x1.2, exaltation x1.15, detriment x0.85, fall x0.8
    """
    orb_factor = max(0.0, 1.0 - orb / MAX_ORB_DEG)

    raw_pw = PLANET_WEIGHTS.get(planet_name, 1.0)
    max_pw = max(PLANET_WEIGHTS.values())
    planet_factor = raw_pw / max_pw

    aspect_factor = _ASPECT_TYPE_WEIGHT.get(aspect_type, 0.5)

    raw = (orb_factor * 0.5 + planet_factor * 0.3 + aspect_factor * 0.2) * house_mult * dig_mult
    return round(max(0.0, min(1.0, raw)), 4)


def _element_for_longitude(lon: float) -> WuXingElement:
    """Map ecliptic longitude to Wu-Xing element via zodiac sign."""
    sign_idx = int(lon // 30) % 12
    return _SIGN_TO_ELEMENT[sign_idx]


def find_active_planets(
    natal_bodies: Dict[str, Dict[str, Any]],
    transit_data: Dict[str, Dict[str, Any]],
    house_cusps: Optional[Dict[str, float]] = None,
) -> List[ActivePlanet]:
    """Find transit planets with orb ≤ 8° to any natal position.

    Args:
        natal_bodies: From compute_western_chart()["bodies"] — keyed by
            capitalized planet name (e.g. "Mars"), each with "longitude".
        transit_data: From compute_transit_now()["planets"] — keyed by
            lowercase planet name (e.g. "mars"), each with "longitude", "speed".
        house_cusps: Optional house cusps from compute_western_chart()["houses"].
            When provided, planets in angular houses get ×1.3 weight boost,
            cadent houses get ×0.8 reduction.

    Returns:
        List of ActivePlanet sorted by tightest orb first.
        Each transit planet appears at most once (its tightest aspect to any
        natal body wins). This is intentional — one dominant aspect per
        transit planet, not a multi-aspect list.
        BaziResonance is populated with a placeholder (neutral) — the real
        resonance is computed by enrich_active_planets().
    """
    results: List[ActivePlanet] = []

    for transit_name, transit_info in transit_data.items():
        transit_lon = transit_info.get("longitude")
        if transit_lon is None:
            continue

        transit_speed = transit_info.get("speed", 0.0)
        is_retro = transit_speed < 0

        natal_bodies_to_check = {
            k: v for k, v in natal_bodies.items()
            if "longitude" in v and v["longitude"] is not None and "error" not in v
        }

        best_match: Optional[Dict[str, Any]] = None
        best_orb = MAX_ORB_DEG + 1

        for natal_name, natal_info in natal_bodies_to_check.items():
            natal_lon = natal_info["longitude"]
            dist = _angular_distance(transit_lon, natal_lon)

            for aspect_name, exact_angle, _factor in ASPECT_DEFS:
                deviation = abs(dist - exact_angle)
                if deviation <= MAX_ORB_DEG and deviation < best_orb:
                    best_orb = deviation
                    best_match = {
                        "natal_name": natal_name,
                        "natal_lon": natal_lon,
                        "aspect": aspect_name,
                        "orb": round(deviation, 2),
                    }

        if best_match is not None:
            sector = _element_for_longitude(transit_lon)
            h_mult = 1.0
            if house_cusps:
                h_num = determine_house(transit_lon, house_cusps)
                h_mult = house_multiplier(h_num)
            cap_name = transit_name.capitalize()
            sign_idx = int(transit_lon // 30) % 12
            dig = get_dignity(cap_name, sign_idx)
            d_mult = dignity_multiplier(cap_name, transit_lon)
            results.append(
                ActivePlanet(
                    planet=transit_name,
                    aspect=best_match["aspect"],
                    orb=best_match["orb"],
                    strength=classify_strength(best_match["orb"]),
                    is_retrograde=is_retro,
                    natal_position=round(best_match["natal_lon"], 2),
                    transit_position=round(transit_lon, 2),
                    sector=sector,
                    weight=_composite_weight(
                        best_match["orb"], transit_name, best_match["aspect"],
                        h_mult, d_mult,
                    ),
                    dignity=dig,
                    bazi_resonance=BaziResonance(
                        element=sector,
                        type="neutral",
                        intensity="gering",
                    ),
                )
            )

    results.sort(key=lambda p: p.orb)
    return results
