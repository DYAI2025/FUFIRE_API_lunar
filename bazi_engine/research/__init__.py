"""
bazi_engine/research — Empirisches Analysewerkzeug für Fusion Astrology.

Ermöglicht statistische Validierung der Fusion-Features (H, d_i, r_i, Zonen)
gegenüber externen Phaseneinteilungen (Jieqi, Mondphasen).

Ziel: Herausfinden ob statistisch stabile, reproduzierbare Muster existieren —
oder ob alle Unterschiede im Rauschen / Artefakten begründet sind.
"""
from .dataset_generator import (
    SyntheticBirthChart,
    generate_synthetic_dataset,
)
from .pattern_analysis import (
    BiasReport,
    PhaseGroupStats,
    analyse_feature_by_phase,
    detect_pipeline_bias,
    kruskal_wallis_test,
    phase_zone_frequencies,
)

__all__ = [
    "SyntheticBirthChart",
    "generate_synthetic_dataset",
    "PhaseGroupStats",
    "analyse_feature_by_phase",
    "kruskal_wallis_test",
    "phase_zone_frequencies",
    "detect_pipeline_bias",
    "BiasReport",
]
