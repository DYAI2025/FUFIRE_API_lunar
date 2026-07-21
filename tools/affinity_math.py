"""
Berechnet AFFINITY_MAP-Zeilen aus VAD-Profilen.

Kernlogik:
  Affinitaet(marker, sektor) = cosine_similarity(marker.VAD, sektor.VAD)
  Negative Similaritaeten werden auf 0 gekappt (keine Anti-Affinitaet).
  Ergebnis wird auf Summe ~ 1.0 normalisiert.
"""

import math
from tools.sector_vad import VADProfile, SECTOR_VAD, SECTOR_NAMES


def cosine_similarity(a: VADProfile, b: VADProfile) -> float:
    """Cosinus-Aehnlichkeit zweier VAD-Profile im 3D-Raum."""
    dot = a.valence * b.valence + a.arousal * b.arousal + a.dominance * b.dominance
    mag_a = math.sqrt(a.valence**2 + a.arousal**2 + a.dominance**2)
    mag_b = math.sqrt(b.valence**2 + b.arousal**2 + b.dominance**2)
    if mag_a < 1e-9 or mag_b < 1e-9:
        return 0.0
    return dot / (mag_a * mag_b)


def compute_affinity_row(marker_vad: VADProfile) -> list[float]:
    """Berechne 12-Sektor-Gewichte aus einem VAD-Profil.

    Returns:
        Liste mit 12 Floats, Summe ~ 1.0, je 2 Nachkommastellen.
    """
    raw = []
    for s in range(12):
        sim = cosine_similarity(marker_vad, SECTOR_VAD[s])
        raw.append(max(0.0, sim))  # Keine negative Affinitaet

    total = sum(raw)
    if total < 1e-9:
        return [round(1.0 / 12, 2)] * 12  # Uniform wenn kein Signal

    normalized = [r / total for r in raw]
    # Runden und kleine Werte (<0.03) auf 0 setzen (Noise-Filter)
    cleaned = [round(v, 2) if v >= 0.03 else 0.0 for v in normalized]

    # Re-normalisieren nach Noise-Filter
    total2 = sum(cleaned)
    if total2 < 1e-9:
        return [round(1.0 / 12, 2)] * 12
    return [round(v / total2, 2) for v in cleaned]


def compare_rows(
    computed: list[float],
    existing: list[float],
    threshold: float = 0.15,
) -> dict:
    """Vergleiche berechnete vs. bestehende AFFINITY_MAP-Zeile.

    Returns:
        Dict mit:
          deltas: list[float] -- pro-Sektor Abweichung
          max_delta: float -- groesste Abweichung
          max_delta_sector: int -- Sektor mit groesster Abweichung
          coherent: bool -- True wenn max_delta < threshold
          warnings: list[str] -- menschenlesbare Warnungen
    """
    deltas = [round(abs(c - e), 3) for c, e in zip(computed, existing)]
    max_delta = max(deltas)
    max_sector = deltas.index(max_delta)

    warnings = []
    for s, d in enumerate(deltas):
        if d >= threshold:
            warnings.append(
                f"S{s} ({SECTOR_NAMES[s]}): Delta {d:.3f} "
                f"(computed={computed[s]:.2f}, existing={existing[s]:.2f})"
            )

    return {
        "deltas": deltas,
        "max_delta": round(max_delta, 3),
        "max_delta_sector": max_sector,
        "coherent": max_delta < threshold,
        "warnings": warnings,
    }


def format_affinity_row_ts(keyword: str, row: list[float]) -> str:
    """Formatiere als TypeScript-Zeile fuer AFFINITY_MAP."""
    parts = []
    for v in row:
        if v == 0:
            parts.append("0  ")
        elif v == 1:
            parts.append("1  ")
        else:
            parts.append(f".{round(v * 100):02d}")
    values_str = ", ".join(parts)
    return f"  '{keyword}': [{values_str}],"
