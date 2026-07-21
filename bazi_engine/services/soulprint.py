"""Compute 12-sector soulprint vector from natal signals."""
from __future__ import annotations

from typing import Dict, List

# Wu-Xing element → associated zodiac sectors
_WUXING_SECTORS: Dict[str, List[int]] = {
    "Holz": [3, 4],    # Cancer, Leo
    "Feuer": [4, 5],   # Leo, Virgo
    "Erde": [1, 7],    # Taurus, Scorpio
    "Metall": [6, 9],  # Libra, Capricorn
    "Wasser": [8, 11], # Sagittarius, Pisces
}

def compute_soulprint(
    sun_sign_idx: int,
    moon_sign_idx: int,
    asc_sign_idx: int,
    personal_planets: Dict[str, int],  # planet_name → sector_idx
    wuxing_vector: Dict[str, float],
) -> List[float]:
    """Return normalized 12-sector soulprint vector."""
    sectors = [0.0] * 12
    sectors[sun_sign_idx % 12] += 1.0
    sectors[moon_sign_idx % 12] += 0.8
    sectors[asc_sign_idx % 12] += 0.6
    for _planet, sector_idx in personal_planets.items():
        sectors[sector_idx % 12] += 0.4
    for element, weight in wuxing_vector.items():
        for sector_idx in _WUXING_SECTORS.get(element, []):
            sectors[sector_idx] += weight * 0.5
    total = sum(sectors)
    if total > 0:
        sectors = [round(s / total, 6) for s in sectors]
    return sectors
