"""
impact_harmony.py — Harmony index, day mode, intensity, and drivers.

Level 4 module. Computes the coherence metrics for the /impact/active
response by combining natal Wu-Xing vectors with transit Wu-Xing vectors
and active planet data.
"""
from __future__ import annotations

from typing import Dict, List, Optional

from .impact_types import (
    ActivePlanet,
    DayMode,
    Driver,
    DriverLevel,
    Evidence,
    ResonanceBadge,
    WuXingElement,
)
from .wuxing.analysis import calculate_harmony_index as _calc_harmony
from .wuxing.vector import WuXingVector

# Element order matching WuXingVector fields: holz, feuer, erde, metall, wasser
_EN_TO_IDX: Dict[WuXingElement, int] = {
    "wood": 0,
    "fire": 1,
    "earth": 2,
    "metal": 3,
    "water": 4,
}


def natal_wuxing_vector(
    soulprint_sectors: Optional[Dict[str, float]],
    quiz_sectors: Optional[Dict[str, float]],
) -> WuXingVector:
    """Build a Wu-Xing vector from soulprint and quiz sector weights.

    Public alias for _natal_wuxing_vector (used by routers).
    """
    return _natal_wuxing_vector(soulprint_sectors, quiz_sectors)


def transit_wuxing_vector(active_planets: List[ActivePlanet]) -> WuXingVector:
    """Build a Wu-Xing vector from active planet weights per element.

    Public alias for _transit_wuxing_vector (used by routers).
    """
    return _transit_wuxing_vector(active_planets)


def _aspect_tightness_multiplier(orb: float) -> float:
    """Compute a multiplier that amplifies tight aspects in the Wu-Xing vector.

    Tight aspects (low orb) get a stronger boost to the element signal:
    - orb 0° → 1.5x (exact aspect, maximum amplification)
    - orb 4° → ~1.0x (neutral)
    - orb 8° → 0.75x (loose aspect, reduced contribution)

    Uses a linear ramp from 1.5 at orb=0 to 0.75 at orb=8.
    """
    return round(1.5 - 0.09375 * min(orb, 8.0), 4)


def _transit_wuxing_vector(active_planets: List[ActivePlanet]) -> WuXingVector:
    """Build a Wu-Xing vector from active planet weights per element.

    Applies aspect-tightness amplification: tight aspects contribute more
    to their element's weight than loose ones.
    """
    vals = [0.0, 0.0, 0.0, 0.0, 0.0]
    for p in active_planets:
        idx = _EN_TO_IDX.get(p.bazi_resonance.element, 2)  # default earth
        amplified = p.weight * _aspect_tightness_multiplier(p.orb)
        vals[idx] += amplified
    return WuXingVector(*vals)


def _natal_wuxing_vector(
    soulprint_sectors: Optional[Dict[str, float]],
    quiz_sectors: Optional[Dict[str, float]],
) -> WuXingVector:
    """Build a Wu-Xing vector from soulprint and quiz sector weights.

    If both are provided, average them. If neither, return a uniform vector.
    """
    if soulprint_sectors is None and quiz_sectors is None:
        return WuXingVector(0.2, 0.2, 0.2, 0.2, 0.2)

    vals = [0.0, 0.0, 0.0, 0.0, 0.0]
    count = 0
    for sectors in (soulprint_sectors, quiz_sectors):
        if sectors is not None:
            count += 1
            for elem, weight in sectors.items():
                if elem in _EN_TO_IDX:
                    vals[_EN_TO_IDX[elem]] += weight

    if count > 1:
        vals = [v / count for v in vals]

    return WuXingVector(*vals)


def compute_harmony_index(
    natal_vec: WuXingVector,
    transit_vec: WuXingVector,
) -> float:
    """Compute Wu-Xing cosine coherence index (0–1).

    Delegates to wuxing.analysis.calculate_harmony_index (dot_product method)
    and returns a bare float.
    """
    if natal_vec.magnitude() == 0 or transit_vec.magnitude() == 0:
        return 0.0
    result = _calc_harmony(natal_vec, transit_vec, method="dot_product")
    return round(max(0.0, min(1.0, result["harmony_index"])), 4)


def compute_intensity(
    harmony_index: float,
    active_planet_count: int,
    space_weather_score: float,
) -> float:
    """Compute overall intensity scalar (0–1).

    Weighted combination: harmony alignment (40%), planet activity (40%),
    space weather (20%).
    """
    planet_factor = min(active_planet_count / 5.0, 1.0)
    raw = harmony_index * 0.4 + planet_factor * 0.4 + space_weather_score * 0.2
    return round(max(0.0, min(1.0, raw)), 4)


def classify_day_mode(
    harmony_index: float,
    intensity: float,
) -> DayMode:
    """Classify the day's energy mode from harmony and intensity."""
    if intensity >= 0.75:
        return "pulse"
    if harmony_index >= 0.6 and intensity < 0.4:
        return "calm"
    if harmony_index < 0.4 or intensity >= 0.6:
        return "tense"
    return "active"


def compute_drivers(
    space_weather_score: float,
    active_planet_count: int,
    harmony_index: float,
) -> List[Driver]:
    """Compute the 4 coherence drivers for the Driver Strip.

    Returns exactly 4 drivers: geomagnetic, solar, transit, day_field.
    """
    def _level(score: float) -> DriverLevel:
        if score >= 0.7:
            return "tense"
        if score >= 0.4:
            return "active"
        return "calm"

    geo_score = space_weather_score
    solar_score = min(space_weather_score * 1.2, 1.0)
    transit_score = min(active_planet_count / 5.0, 1.0)
    day_field_score = 1.0 - harmony_index

    return [
        Driver(name="geomagnetic", level=_level(geo_score)),
        Driver(name="solar", level=_level(solar_score)),
        Driver(name="transit", level=_level(transit_score)),
        Driver(name="day_field", level=_level(day_field_score)),
    ]


def find_top_sector(active_planets: List[ActivePlanet]) -> WuXingElement:
    """Find the dominant Wu-Xing element from active planets by total weight."""
    totals: Dict[WuXingElement, float] = {
        "wood": 0.0, "fire": 0.0, "earth": 0.0, "metal": 0.0, "water": 0.0,
    }
    for p in active_planets:
        elem = p.bazi_resonance.element
        totals[elem] = totals.get(elem, 0.0) + p.weight
    return max(totals, key=lambda k: totals[k])


def build_resonance_badges(
    active_planets: List[ActivePlanet],
) -> List[ResonanceBadge]:
    """Build resonance badges from active planets with non-neutral resonance."""
    badges: List[ResonanceBadge] = []
    for p in active_planets:
        if p.bazi_resonance.type == "neutral":
            continue
        type_label = {
            "gleichklang": "Gleichklang",
            "naehrung": "Naehrung",
            "kontrolle": "Kontrolle",
        }.get(p.bazi_resonance.type, p.bazi_resonance.type)

        elem_label = {
            "wood": "Holz", "fire": "Feuer", "earth": "Erde",
            "metal": "Metall", "water": "Wasser",
        }.get(p.bazi_resonance.element, p.bazi_resonance.element)

        badges.append(ResonanceBadge(
            label=f"{elem_label}-{type_label}",
            element=p.bazi_resonance.element,
            type=p.bazi_resonance.type,
            intensity=p.bazi_resonance.intensity,
            source_planet=p.planet,
        ))
    return badges


def build_evidence(
    natal_vec: WuXingVector,
    transit_vec: WuXingVector,
    harmony_index: float,
    method: str = "dot_product",
) -> Evidence:
    """Build the evidence object for traceability."""
    return Evidence(
        resonance_formula=f"harmony = dot(normalize(natal_vec), normalize(transit_vec)), method={method}",
        parameters={
            "natal_vector": natal_vec.to_dict(),
            "transit_vector": transit_vec.to_dict(),
            "harmony_index": harmony_index,
            "method": method,
        },
    )
