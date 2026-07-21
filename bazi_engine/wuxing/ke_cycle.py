"""
wuxing/ke_cycle.py — Ke-cycle (相剋) destructive relationship analysis.

The Ke-cycle (controlling/overcoming cycle) describes which element
controls/destroys which:

  Wood  (Holz)   → Earth (Erde)   : roots break soil
  Earth (Erde)   → Water (Wasser) : earth dams water
  Water (Wasser) → Fire  (Feuer)  : water extinguishes fire
  Fire  (Feuer)  → Metal (Metall) : fire melts metal
  Metal (Metall) → Wood  (Holz)   : axe cuts tree

Pure functions, no side effects.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

from .constants import WUXING_ORDER
from .vector import WuXingVector

# ── Ke-cycle tables ──────────────────────────────────────────────────────────

# KE_CYCLE[elem] = the element that *elem* controls/overcomes
KE_CYCLE: Dict[str, str] = {
    "Holz":   "Erde",
    "Erde":   "Wasser",
    "Wasser": "Feuer",
    "Feuer":  "Metall",
    "Metall": "Holz",
}

# KE_INVERSE[elem] = the element that controls *elem*
KE_INVERSE: Dict[str, str] = {v: k for k, v in KE_CYCLE.items()}


# ── Data types ───────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class KeCycleRelation:
    """A detected Ke-cycle (destructive) relationship between two elements."""

    controller: str   # element that overcomes/controls
    controlled: str   # element that is overcome/controlled
    controller_strength: float  # normalized strength of the controller
    controlled_strength: float  # normalized strength of the controlled
    ke_intensity: float  # product of both strengths (proxy for tension severity)


# ── Analysis functions ───────────────────────────────────────────────────────

def ke_tensions_in_vector(
    vector: WuXingVector,
    threshold: float = 0.15,
) -> List[KeCycleRelation]:
    """Find active Ke-cycle tensions within a single Wu-Xing vector.

    A Ke tension is active when both the controller and the controlled element
    exceed the threshold in the same normalized vector. This indicates that two
    mutually destructive forces are simultaneously present — internal conflict.

    Args:
        vector:    Wu-Xing vector (raw or normalized; internally normalized).
        threshold: Minimum normalized element strength to participate in a
                   Ke tension (default 0.15).

    Returns:
        List of KeCycleRelation, sorted by descending ke_intensity.
    """
    norm = vector.normalize()
    norm_dict = norm.to_dict()

    results: List[KeCycleRelation] = []
    for controller in WUXING_ORDER:
        controlled = KE_CYCLE[controller]
        c_strength = norm_dict[controller]
        t_strength = norm_dict[controlled]
        if c_strength >= threshold and t_strength >= threshold:
            results.append(KeCycleRelation(
                controller=controller,
                controlled=controlled,
                controller_strength=c_strength,
                controlled_strength=t_strength,
                ke_intensity=c_strength * t_strength,
            ))

    results.sort(key=lambda r: r.ke_intensity, reverse=True)
    return results


def ke_cross_tensions(
    western: WuXingVector,
    bazi: WuXingVector,
    threshold: float = 0.15,
) -> List[KeCycleRelation]:
    """Find Ke-cycle tensions across two vectors (western vs. BaZi).

    A cross-tension exists when an element is strong in one vector while the
    element it controls is strong in the other vector. This models a situation
    where one energetic system suppresses a key force in the other.

    Both directions are checked:
    - Western element controlling a BaZi element
    - BaZi element controlling a Western element

    Args:
        western:   Western planetary Wu-Xing vector.
        bazi:      BaZi natal Wu-Xing vector.
        threshold: Minimum normalized strength to qualify (default 0.15).

    Returns:
        List of KeCycleRelation (sources are not distinguished — use
        controller_strength / controlled_strength to infer directionality),
        sorted by descending ke_intensity.
    """
    w_norm = western.normalize().to_dict()
    b_norm = bazi.normalize().to_dict()

    results: List[KeCycleRelation] = []
    for controller in WUXING_ORDER:
        controlled = KE_CYCLE[controller]

        # Western controls BaZi
        if w_norm[controller] >= threshold and b_norm[controlled] >= threshold:
            results.append(KeCycleRelation(
                controller=controller,
                controlled=controlled,
                controller_strength=w_norm[controller],
                controlled_strength=b_norm[controlled],
                ke_intensity=w_norm[controller] * b_norm[controlled],
            ))

        # BaZi controls Western
        if b_norm[controller] >= threshold and w_norm[controlled] >= threshold:
            results.append(KeCycleRelation(
                controller=controller,
                controlled=controlled,
                controller_strength=b_norm[controller],
                controlled_strength=w_norm[controlled],
                ke_intensity=b_norm[controller] * w_norm[controlled],
            ))

    results.sort(key=lambda r: r.ke_intensity, reverse=True)
    return results


def ke_cycle_summary(
    western: WuXingVector,
    bazi: WuXingVector,
    threshold: float = 0.15,
) -> dict:
    """Produce a complete Ke-cycle analysis for a western + BaZi vector pair.

    Args:
        western:   Western planetary Wu-Xing vector.
        bazi:      BaZi natal Wu-Xing vector.
        threshold: Minimum normalized element strength (default 0.15).

    Returns:
        Dict with:
          - "internal_western": Ke tensions within the western vector
          - "internal_bazi":    Ke tensions within the BaZi vector
          - "cross_tensions":   Cross-system Ke tensions
          - "dominant_ke":      The single highest-intensity Ke relation, or None
    """
    internal_w = ke_tensions_in_vector(western, threshold)
    internal_b = ke_tensions_in_vector(bazi, threshold)
    cross = ke_cross_tensions(western, bazi, threshold)

    all_relations = internal_w + internal_b + cross
    dominant = max(all_relations, key=lambda r: r.ke_intensity) if all_relations else None

    return {
        "internal_western": internal_w,
        "internal_bazi":    internal_b,
        "cross_tensions":   cross,
        "dominant_ke":      dominant,
    }
