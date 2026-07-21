"""
research/pattern_analysis.py — Statistische Mustererkennung in Fusion-Features.

Testet ob Features (H, d_i, r_i, Zonen) systematische Unterschiede zwischen
externen Phasen (Jieqi, Mondphasen) aufweisen.

METHODISCHE SICHERHEITSMASSNAHMEN:
  1. Kruskal-Wallis-Test statt ANOVA (robuster gegen nicht-normalverteilte Daten)
  2. Bonferroni-Korrektur für multiple Tests
  3. Effektstärke (η² / Epsilon²) neben p-Wert
  4. Bias-Detektion: Nullvektoren, ungleiche Stichproben, Rundungsartefakte
  5. Minimum-n pro Gruppe (n_min=10) als Validitätsschwelle
  6. Separater Permutationstest für Validierung

INTERPRETATIONSREGELN:
  • p < 0.05 nach Bonferroni + η² ≥ 0.01 (kleiner Effekt): möglicherweise real
  • p < 0.01 nach Bonferroni + η² ≥ 0.06 (mittlerer Effekt): wahrscheinlich real
  • Ohne Effektstärke-Schwelle: statistisch signifikant ≠ praktisch bedeutsam
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional

from ..wuxing.constants import WUXING_ORDER
from .dataset_generator import SyntheticBirthChart

# ── Typen ─────────────────────────────────────────────────────────────────────

@dataclass
class PhaseGroupStats:
    """Deskriptive Statistik für eine Feature-Gruppe."""
    phase_name: str
    n:          int
    mean:       float
    std:        float
    median:     float
    q25:        float
    q75:        float

    @property
    def is_reliable(self) -> bool:
        return self.n >= 10


@dataclass
class KruskalWallisResult:
    """Ergebnis des Kruskal-Wallis-Tests."""
    feature_name:       str
    h_statistic:        float   # Kruskal-Wallis H-Statistik
    p_value:            float   # Roher p-Wert
    p_value_bonferroni: float   # Bonferroni-korrigierter p-Wert
    n_comparisons:      int     # Anzahl Tests (für Bonferroni)
    eta_squared:        float   # Effektstärke η² = (H - k + 1) / (n - k)
    n_groups:           int
    n_total:            int
    is_significant:     bool    # p_bonferroni < 0.05 AND eta_squared >= 0.01

    @property
    def effect_size_label(self) -> str:
        if self.eta_squared < 0.01:
            return "kein"
        if self.eta_squared < 0.06:
            return "klein"
        if self.eta_squared < 0.14:
            return "mittel"
        return "groß"


@dataclass
class BiasReport:
    """Pipeline-Bias-Detektionsbericht."""
    n_total:            int
    n_degenerate:       float   # Anteil Nullvektoren
    n_sparse:           float   # Anteil sparse-Qualität
    phase_imbalance:    float   # Max/Min Stichprobengröße pro Phase (Verhältnis)
    h_raw_at_zero:      float   # Anteil H_raw == 0.0
    h_raw_at_one:       float   # Anteil H_raw == 1.0 (Klemmungsartefakt)
    extreme_diff_rate:  float   # Anteil Charts mit |d_i| > 0.45 (Outlier)
    warnings:           list[str] = field(default_factory=list)

    @property
    def has_critical_bias(self) -> bool:
        return (
            self.n_degenerate > 0.05
            or self.phase_imbalance > 3.0
            or self.h_raw_at_zero > 0.05
        )


# ── Hilfsfunktionen ───────────────────────────────────────────────────────────

def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _std(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    m = _mean(values)
    return math.sqrt(sum((x - m) ** 2 for x in values) / (len(values) - 1))


def _percentile(sorted_vals: list[float], p: float) -> float:
    """p in [0, 1]."""
    if not sorted_vals:
        return 0.0
    idx = p * (len(sorted_vals) - 1)
    lo = int(idx)
    hi = min(lo + 1, len(sorted_vals) - 1)
    return sorted_vals[lo] + (idx - lo) * (sorted_vals[hi] - sorted_vals[lo])


def _chi2_p_value(h: float, df: int) -> float:
    """Approximierter p-Wert aus χ²-Verteilung (für Kruskal-Wallis).
    Nutzung der regularisierten unvollständigen Gamma-Funktion.
    Für df ≥ 2 ausreichend genau für unsere Zwecke (±5%).
    """
    if df <= 0 or h <= 0:
        return 1.0
    # Regularisierte obere unvollständige Gamma-Funktion: 1 - γ(df/2, h/2) / Γ(df/2)
    # Approximation via Wilson-Hilferty für große h
    x = h / df
    z = (x ** (1/3) - (1 - 2/(9*df))) / math.sqrt(2/(9*df))
    # Standard-Normal-Überlebenswahrscheinlichkeit
    p = 0.5 * math.erfc(z / math.sqrt(2))
    return max(1e-300, min(1.0, p))


def _rank_all(groups: list[list[float]]) -> list[list[float]]:
    """Bildet Ränge für Kruskal-Wallis."""
    all_vals = [(v, g_idx, v_idx)
                for g_idx, grp in enumerate(groups)
                for v_idx, v in enumerate(grp)]
    all_vals.sort(key=lambda x: x[0])
    n = len(all_vals)

    # Durchschnittsränge bei Bindungen
    ranks = [0.0] * n
    i = 0
    while i < n:
        j = i
        while j < n - 1 and all_vals[j][0] == all_vals[j + 1][0]:
            j += 1
        avg_rank = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            ranks[k] = avg_rank
        i = j + 1

    # Ränge zurück in Gruppen
    group_ranks: list[list[float]] = [[] for _ in groups]
    for (_, g_idx, _), rank in zip(all_vals, ranks):
        group_ranks[g_idx].append(rank)

    return group_ranks


# ── Kernfunktionen ────────────────────────────────────────────────────────────

def _group_stats(name: str, values: list[float]) -> PhaseGroupStats:
    s = sorted(values)
    return PhaseGroupStats(
        phase_name=name,
        n=len(s),
        mean=round(_mean(s), 5),
        std=round(_std(s), 5),
        median=round(_percentile(s, 0.5), 5),
        q25=round(_percentile(s, 0.25), 5),
        q75=round(_percentile(s, 0.75), 5),
    )


def analyse_feature_by_phase(
    charts: list[SyntheticBirthChart],
    feature: str,
    phase_attr: str = "jieqi",
    element: Optional[str] = None,
) -> dict[str, PhaseGroupStats]:
    """Berechnet deskriptive Statistiken für ein Feature, gruppiert nach Phase.

    Args:
        charts:      Liste von SyntheticBirthChart.
        feature:     Feature-Name: "h_raw"|"h_calibrated"|"diff"|"resonance"
        phase_attr:  "jieqi" oder "lunar".
        element:     Für "diff"/"resonance": welches Element (z.B. "Feuer").

    Returns:
        Dict: phase_name → PhaseGroupStats.
    """
    groups: dict[str, list[float]] = {}

    for chart in charts:
        if chart.quality == "degenerate":
            continue

        phase = getattr(chart, phase_attr)
        phase_name = phase.name_pinyin if phase_attr == "jieqi" else phase.name_de

        if feature == "h_raw":
            val = chart.h_raw
        elif feature == "h_calibrated":
            val = chart.h_calibrated
        elif feature == "diff" and element:
            val = chart.diffs[element]
        elif feature == "resonance" and element:
            val = chart.resonance[element]
        elif feature == "n_tension":
            val = float(chart.n_tension)
        else:
            continue

        groups.setdefault(phase_name, []).append(val)

    return {name: _group_stats(name, vals) for name, vals in groups.items()}


def kruskal_wallis_test(
    charts: list[SyntheticBirthChart],
    feature: str,
    phase_attr: str = "jieqi",
    element: Optional[str] = None,
    n_comparisons: int = 1,  # für Bonferroni
    n_min_per_group: int = 10,
) -> KruskalWallisResult:
    """Kruskal-Wallis-Test: Hat das Feature signifikante Unterschiede zwischen Phasen?

    Args:
        charts:          Datensatz.
        feature:         "h_raw"|"h_calibrated"|"diff"|"resonance"|"n_tension"
        phase_attr:      "jieqi"|"lunar"
        element:         Element für diff/resonance.
        n_comparisons:   Anzahl paralleler Tests (für Bonferroni).
        n_min_per_group: Gruppen mit n < n_min werden ausgeschlossen.

    Returns:
        KruskalWallisResult mit H-Statistik, p-Wert, Effektstärke.
    """
    groups_data = analyse_feature_by_phase(charts, feature, phase_attr, element)
    _group_values = [
        [c for c in [
            (getattr(chart, phase_attr).name_pinyin
             if phase_attr == "jieqi"
             else getattr(chart, phase_attr).name_de)
            == name and chart.quality != "degenerate"
            and (_get_val(chart, feature, element) is not None)
            for chart in charts
        ]]
        for name in groups_data
    ]

    # Direkter Aufbau der Gruppen
    phase_groups: dict[str, list[float]] = {}
    for chart in charts:
        if chart.quality == "degenerate":
            continue
        val = _get_val(chart, feature, element)
        if val is None:
            continue
        phase = getattr(chart, phase_attr)
        name = phase.name_pinyin if phase_attr == "jieqi" else phase.name_de
        phase_groups.setdefault(name, []).append(val)

    # Gruppen mit zu wenig Daten ausfiltern
    valid_groups = {k: v for k, v in phase_groups.items() if len(v) >= n_min_per_group}

    if len(valid_groups) < 2:
        return KruskalWallisResult(
            feature_name=feature + (f"[{element}]" if element else ""),
            h_statistic=0.0, p_value=1.0, p_value_bonferroni=1.0,
            n_comparisons=n_comparisons, eta_squared=0.0,
            n_groups=len(valid_groups), n_total=0, is_significant=False,
        )

    groups_list = list(valid_groups.values())
    n_total = sum(len(g) for g in groups_list)
    k = len(groups_list)

    # Kruskal-Wallis H-Statistik
    group_ranks = _rank_all(groups_list)
    H_stat = (12.0 / (n_total * (n_total + 1))) * sum(
        len(grp) * (_mean(ranks) - (n_total + 1) / 2.0) ** 2
        for grp, ranks in zip(groups_list, group_ranks)
    )

    # p-Wert (χ²-Approximation, df = k-1)
    p_raw = _chi2_p_value(H_stat, k - 1)
    p_bonferroni = min(1.0, p_raw * n_comparisons)

    # Effektstärke η² (Epsilon²-Schätzer)
    eta_sq = max(0.0, (H_stat - k + 1) / (n_total - k)) if n_total > k else 0.0

    feature_label = feature + (f"[{element}]" if element else "")
    is_sig = p_bonferroni < 0.05 and eta_sq >= 0.01

    return KruskalWallisResult(
        feature_name=feature_label,
        h_statistic=round(H_stat, 4),
        p_value=round(p_raw, 6),
        p_value_bonferroni=round(p_bonferroni, 6),
        n_comparisons=n_comparisons,
        eta_squared=round(eta_sq, 6),
        n_groups=k,
        n_total=n_total,
        is_significant=is_sig,
    )


def _get_val(chart: SyntheticBirthChart, feature: str, element: Optional[str]) -> Optional[float]:
    if feature == "h_raw":
        return chart.h_raw
    if feature == "h_calibrated":
        return chart.h_calibrated
    if feature == "diff" and element:
        return chart.diffs.get(element)
    if feature == "resonance" and element:
        return chart.resonance.get(element)
    if feature == "n_tension":
        return float(chart.n_tension)
    return None


def phase_zone_frequencies(
    charts: list[SyntheticBirthChart],
    phase_attr: str = "jieqi",
) -> dict[str, dict[str, float]]:
    """Berechnet Zonenfrequenzen (TENSION/STRENGTH/DEVELOPMENT) pro Phase.

    Returns:
        Dict: phase_name → {element → TENSION-Rate (0–1)}
    """
    phase_tension: dict[str, dict[str, list[int]]] = {}

    for chart in charts:
        if chart.quality == "degenerate":
            continue
        phase = getattr(chart, phase_attr)
        name = phase.name_pinyin if phase_attr == "jieqi" else phase.name_de
        if name not in phase_tension:
            phase_tension[name] = {e: [] for e in WUXING_ORDER}
        for elem in WUXING_ORDER:
            phase_tension[name][elem].append(
                1 if chart.zones[elem] == "TENSION" else 0
            )

    return {
        name: {
            elem: round(sum(vals) / len(vals), 4) if vals else 0.0
            for elem, vals in elem_data.items()
        }
        for name, elem_data in phase_tension.items()
    }


def detect_pipeline_bias(
    charts: list[SyntheticBirthChart],
    phase_attr: str = "jieqi",
) -> BiasReport:
    """Erkennt systematische Bias-Quellen im generierten Datensatz.

    Prüft auf:
      - Nullvektor-Rate (degenerate)
      - Stichproben-Imbalance pro Phase
      - H-Klemmungsartefakte (H == 0.0 oder H == 1.0)
      - Extreme d_i-Werte (Outlier)
    """
    n = len(charts)
    if n == 0:
        return BiasReport(0, 0, 0, 0, 0, 0, 0)

    n_deg = sum(1 for c in charts if c.quality == "degenerate") / n
    n_sparse = sum(1 for c in charts if c.quality == "sparse") / n
    h_zero = sum(1 for c in charts if c.h_raw == 0.0) / n
    h_one  = sum(1 for c in charts if c.h_raw >= 0.9999) / n

    extreme = sum(
        1 for c in charts
        if any(abs(v) > 0.45 for v in c.diffs.values())
    ) / n

    # Phase-Balance
    phase_counts: dict[str, int] = {}
    for chart in charts:
        phase = getattr(chart, phase_attr)
        name = phase.name_pinyin if phase_attr == "jieqi" else phase.name_de
        phase_counts[name] = phase_counts.get(name, 0) + 1

    if phase_counts:
        max_n = max(phase_counts.values())
        min_n = max(1, min(phase_counts.values()))
        imbalance = max_n / min_n
    else:
        imbalance = 0.0

    warnings = []
    if n_deg > 0.05:
        warnings.append(f"KRITISCH: {n_deg*100:.1f}% Nullvektoren (degenerate)")
    if imbalance > 3.0:
        warnings.append(f"KRITISCH: Phase-Imbalance {imbalance:.1f}x (max/min)")
    if h_zero > 0.05:
        warnings.append(f"WARNUNG: {h_zero*100:.1f}% H=0.0 Artefakte")
    if n_sparse > 0.20:
        warnings.append(f"WARNUNG: {n_sparse*100:.1f}% sparse-Qualität")
    if extreme > 0.10:
        warnings.append(f"INFO: {extreme*100:.1f}% Charts mit Extrem-d_i > 0.45")

    return BiasReport(
        n_total=n,
        n_degenerate=round(n_deg, 4),
        n_sparse=round(n_sparse, 4),
        phase_imbalance=round(imbalance, 2),
        h_raw_at_zero=round(h_zero, 4),
        h_raw_at_one=round(h_one, 4),
        extreme_diff_rate=round(extreme, 4),
        warnings=warnings,
    )
