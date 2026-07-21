from __future__ import annotations

from typing import Dict, List

STEMS: List[str] = ["Jia", "Yi", "Bing", "Ding", "Wu", "Ji", "Geng", "Xin", "Ren", "Gui"]
BRANCHES: List[str] = ["Zi", "Chou", "Yin", "Mao", "Chen", "Si", "Wu", "Wei", "Shen", "You", "Xu", "Hai"]
ANIMALS: List[str] = [
    "Rat",
    "Ox",
    "Tiger",
    "Rabbit",
    "Dragon",
    "Snake",
    "Horse",
    "Goat",
    "Monkey",
    "Rooster",
    "Dog",
    "Pig",
]

DAY_OFFSET: int = 49  # Offset to align JDN so 1949-10-01 is Jia-Zi (0)

# Ayanamsha modes for sidereal calculations
# Maps mode name to pyswisseph ayanamsha constant
AYANAMSHA_MODES: Dict[str, int] = {
    "sidereal_lahiri": 1,        # swe.SIDM_LAHIRI
    "sidereal_fagan_bradley": 0, # swe.SIDM_FAGAN_BRADLEY
    "sidereal_raman": 3,         # swe.SIDM_RAMAN
}
