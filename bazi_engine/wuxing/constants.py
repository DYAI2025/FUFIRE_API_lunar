"""
wuxing/constants.py — Wu-Xing domain constants (pure data, no logic).

Planet-to-Element mapping based on classical Western–Chinese
elemental correspondences and planetary rulerships.
"""
from __future__ import annotations

from typing import Dict, List, Union

# Classical Western Astrology → Chinese Five Elements (Wu Xing)
PLANET_TO_WUXING: Dict[str, Union[str, List[str]]] = {
    "Sun":          "Feuer",           # Fire  — Vitality, life force
    "Moon":         "Wasser",          # Water — Emotions, intuition
    "Mercury":      ["Erde", "Metall"],# Dual  — Earth (day chart) / Metal (night chart)
    "Venus":        "Metall",          # Metal — Beauty, value, form
    "Mars":         "Feuer",           # Fire  — Action, energy
    "Jupiter":      "Holz",            # Wood  — Growth, expansion, wisdom
    "Saturn":       "Erde",            # Earth — Structure, limits, discipline
    "Uranus":       "Holz",            # Wood  — Innovation, sudden change
    "Neptune":      "Wasser",          # Water — Dreams, spirituality
    "Pluto":        "Feuer",           # Fire  — Transformation, power
    "Chiron":       "Wasser",          # Water — Healing, wounds
    "Lilith":       "Wasser",          # Water — Dark Moon, instincts
    "NorthNode":    "Holz",            # Wood  — Future direction, growth path
    "TrueNorthNode": "Holz",
}

# Element order follows the Wu Xing generative cycle (相生)
WUXING_ORDER: List[str] = ["Holz", "Feuer", "Erde", "Metall", "Wasser"]
WUXING_INDEX: Dict[str, int] = {elem: i for i, elem in enumerate(WUXING_ORDER)}
