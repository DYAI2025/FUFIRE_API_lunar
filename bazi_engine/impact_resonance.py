"""
impact_resonance.py — BaZi resonance computation for transit planets.

Level 4 module. Computes the Wu-Xing relationship between each transit
planet's element and the natal day master element, producing a BaziResonance
for each ActivePlanet.

Wu-Xing Cycles:
- Sheng (相生, generating): Wood→Fire→Earth→Metal→Water→Wood
- Ke (相剋, controlling): Wood→Earth→Water→Fire→Metal→Wood
"""
from __future__ import annotations

import logging
from typing import Dict, List

from .impact_types import (
    ActivePlanet,
    BaziResonance,
    ResonanceIntensity,
    ResonanceType,
    WuXingElement,
)
from .wuxing.constants import PLANET_TO_WUXING

logger = logging.getLogger(__name__)

# ── Stem → Element mapping ──────────────────────────────────────────────────

STEM_ELEMENT: Dict[str, WuXingElement] = {
    "Jia": "wood", "Yi": "wood",
    "Bing": "fire", "Ding": "fire",
    "Wu": "earth", "Ji": "earth",
    "Geng": "metal", "Xin": "metal",
    "Ren": "water", "Gui": "water",
}

# German element names from wuxing/constants.py → English for impact_types
_DE_TO_EN: Dict[str, WuXingElement] = {
    "Holz": "wood",
    "Feuer": "fire",
    "Erde": "earth",
    "Metall": "metal",
    "Wasser": "water",
}

# ── Wu-Xing cycle relationships ─────────────────────────────────────────────

# Generating cycle (相生): A generates B
_SHENG: Dict[WuXingElement, WuXingElement] = {
    "wood": "fire",
    "fire": "earth",
    "earth": "metal",
    "metal": "water",
    "water": "wood",
}

# Controlling cycle (相剋): A controls B
_KE: Dict[WuXingElement, WuXingElement] = {
    "wood": "earth",
    "fire": "metal",
    "earth": "water",
    "metal": "wood",
    "water": "fire",
}


def day_master_element(stem_name: str) -> WuXingElement:
    """Extract the Wu-Xing element from a BaZi day stem name."""
    elem = STEM_ELEMENT.get(stem_name)
    if elem is None:
        raise ValueError(f"Unknown stem: {stem_name!r}. Expected one of {list(STEM_ELEMENT)}")
    return elem


def planet_element(planet_name: str) -> WuXingElement:
    """Get the Wu-Xing element for a planet using PLANET_TO_WUXING.

    For dual-element planets (Mercury), returns the first element.
    Planet names are matched case-insensitively (transit uses lowercase,
    PLANET_TO_WUXING uses capitalized).
    """
    cap_name = planet_name.capitalize()
    raw = PLANET_TO_WUXING.get(cap_name)
    if raw is None:
        logger.warning("No Wu-Xing mapping for planet %r, defaulting to earth", planet_name)
        return "earth"
    de_name = raw if isinstance(raw, str) else raw[0]
    return _DE_TO_EN.get(de_name, "earth")


def determine_resonance_type(
    master_element: WuXingElement,
    transit_element: WuXingElement,
) -> ResonanceType:
    """Determine the Wu-Xing relationship type between day master and transit.

    - gleichklang: same element
    - naehrung: transit generates (nourishes) master, OR master generates transit
    - kontrolle: transit controls master, OR master controls transit
    - neutral: no direct relationship (shouldn't occur in 5-element system)
    """
    if master_element == transit_element:
        return "gleichklang"
    if _SHENG.get(transit_element) == master_element:
        return "naehrung"  # transit nourishes master (resource)
    if _SHENG.get(master_element) == transit_element:
        return "naehrung"  # master produces transit (output, still nourishing cycle)
    if _KE.get(transit_element) == master_element:
        return "kontrolle"  # transit controls master (power)
    if _KE.get(master_element) == transit_element:
        return "kontrolle"  # master controls transit (wealth)
    return "neutral"


def determine_intensity(
    orb: float,
    weight: float,
) -> ResonanceIntensity:
    """Derive resonance intensity from the planet's orb and composite weight.

    Combines orb tightness and planet weight into a single score:
    - stark: score > 0.7
    - mittel: score > 0.4
    - gering: score ≤ 0.4
    """
    score = (1.0 - min(orb / 8.0, 1.0)) * 0.6 + weight * 0.4
    if score > 0.7:
        return "stark"
    if score > 0.4:
        return "mittel"
    return "gering"


def compute_bazi_resonance(
    master_element: WuXingElement,
    transit_planet_name: str,
    orb: float,
    weight: float,
) -> BaziResonance:
    """Compute BaZi resonance for a single transit planet."""
    t_element = planet_element(transit_planet_name)
    return BaziResonance(
        element=t_element,
        type=determine_resonance_type(master_element, t_element),
        intensity=determine_intensity(orb, weight),
    )


def enrich_active_planets(
    active_planets: List[ActivePlanet],
    master_element: WuXingElement,
) -> List[ActivePlanet]:
    """Replace placeholder BaziResonance on each ActivePlanet with real values.

    Returns a new list (does not mutate input — models are frozen).
    """
    enriched: List[ActivePlanet] = []
    for p in active_planets:
        resonance = compute_bazi_resonance(master_element, p.planet, p.orb, p.weight)
        enriched.append(
            ActivePlanet(
                planet=p.planet,
                aspect=p.aspect,
                orb=p.orb,
                strength=p.strength,
                is_retrograde=p.is_retrograde,
                natal_position=p.natal_position,
                transit_position=p.transit_position,
                sector=p.sector,  # preserve original zodiac-derived sector
                weight=p.weight,
                bazi_resonance=resonance,
            )
        )
    return enriched
