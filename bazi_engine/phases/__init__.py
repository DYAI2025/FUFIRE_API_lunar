"""
bazi_engine/phases — Externe Periodikreferenz für Fusion Astrology.

Bestimmt für jeden Geburtszeitpunkt deterministisch:
  - Jieqi-Phase (24 Sonnenwenden-Perioden, 15° Sonnenlänge je)
  - Mondphase (8 Mondphasen, 45° Mond-Sonne-Winkel je)

Beide Phasen sind astronomisch definiert, realweltlich referenzierbar
und vollständig unabhängig vom individuellen Elementarprofil.
"""
from .jieqi_phase import (
    JIEQI_PHASES,
    JieqiPhase,
    classify_jieqi_phase,
)
from .lunar_phase import (
    LUNAR_PHASES,
    LunarPhase,
    classify_lunar_phase,
)

__all__ = [
    "JieqiPhase",
    "classify_jieqi_phase",
    "JIEQI_PHASES",
    "LunarPhase",
    "classify_lunar_phase",
    "LUNAR_PHASES",
]
