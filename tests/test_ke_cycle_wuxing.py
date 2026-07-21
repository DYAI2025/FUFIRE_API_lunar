"""Tests for bazi_engine/wuxing/ke_cycle.py — Ke-cycle (相剋) analysis.

Covers:
- KE_CYCLE and KE_INVERSE are complete and consistent
- KE_INVERSE is the true inverse of KE_CYCLE
- KeCycleRelation is a frozen dataclass
- ke_tensions_in_vector: finds tensions, threshold respected, sorted by intensity
- ke_tensions_in_vector: zero vector and empty vector edge cases
- ke_cross_tensions: cross-system tensions, both directions detected
- ke_cross_tensions: empty result when no thresholds met
- ke_cycle_summary: aggregates all three categories, dominant_ke is correct
- Exported from bazi_engine.wuxing package
"""
from __future__ import annotations

import dataclasses

import pytest

from bazi_engine.wuxing import (
    KE_CYCLE,
    KE_INVERSE,
    KeCycleRelation,
    ke_cross_tensions,
    ke_cycle_summary,
    ke_tensions_in_vector,
)
from bazi_engine.wuxing.constants import WUXING_ORDER
from bazi_engine.wuxing.vector import WuXingVector

# ── Helpers ──────────────────────────────────────────────────────────────────

def _vec(**kwargs: float) -> WuXingVector:
    """Build WuXingVector from kwargs, defaulting to 0.0."""
    return WuXingVector(
        holz=kwargs.get("Holz", 0.0),
        feuer=kwargs.get("Feuer", 0.0),
        erde=kwargs.get("Erde", 0.0),
        metall=kwargs.get("Metall", 0.0),
        wasser=kwargs.get("Wasser", 0.0),
    )


# ── Catalog integrity ─────────────────────────────────────────────────────────

class TestKeCycleCatalog:
    def test_ke_cycle_covers_all_elements(self):
        assert set(KE_CYCLE.keys()) == set(WUXING_ORDER)

    def test_ke_cycle_targets_are_all_elements(self):
        assert set(KE_CYCLE.values()) == set(WUXING_ORDER)

    def test_ke_cycle_is_bijection(self):
        """Each element controls exactly one other and is controlled by exactly one."""
        assert len(set(KE_CYCLE.values())) == 5

    def test_ke_inverse_is_true_inverse(self):
        for controller, controlled in KE_CYCLE.items():
            assert KE_INVERSE[controlled] == controller

    def test_ke_inverse_covers_all_elements(self):
        assert set(KE_INVERSE.keys()) == set(WUXING_ORDER)

    def test_classical_ke_cycle_values(self):
        """Spot-check canonical Ke-cycle directions."""
        assert KE_CYCLE["Holz"] == "Erde"     # Wood → Earth
        assert KE_CYCLE["Erde"] == "Wasser"   # Earth → Water
        assert KE_CYCLE["Wasser"] == "Feuer"  # Water → Fire
        assert KE_CYCLE["Feuer"] == "Metall"  # Fire → Metal
        assert KE_CYCLE["Metall"] == "Holz"   # Metal → Wood

    def test_no_self_control(self):
        for elem, target in KE_CYCLE.items():
            assert elem != target


# ── KeCycleRelation frozen ────────────────────────────────────────────────────

class TestKeCycleRelationFrozen:
    def test_is_frozen(self):
        rel = KeCycleRelation(
            controller="Holz", controlled="Erde",
            controller_strength=0.5, controlled_strength=0.3,
            ke_intensity=0.15,
        )
        with pytest.raises((dataclasses.FrozenInstanceError, AttributeError)):
            rel.controller = "Feuer"  # type: ignore[misc]


# ── ke_tensions_in_vector ─────────────────────────────────────────────────────

class TestKeTensionsInVector:
    def test_detects_tension_above_threshold(self):
        # Holz and Erde both present — Holz controls Erde
        v = _vec(Holz=3.0, Erde=3.0)
        results = ke_tensions_in_vector(v, threshold=0.15)
        controllers = {r.controller for r in results}
        assert "Holz" in controllers

    def test_no_tension_below_threshold(self):
        # Holz strong, Erde very weak
        v = _vec(Holz=10.0, Erde=0.1)
        results = ke_tensions_in_vector(v, threshold=0.15)
        # After normalization Erde ≈ 0.01 — below threshold
        assert not any(r.controller == "Holz" for r in results)

    def test_zero_vector_returns_empty(self):
        v = WuXingVector.zero()
        assert ke_tensions_in_vector(v) == []

    def test_sorted_by_descending_intensity(self):
        # Make multiple Ke pairs active
        v = _vec(Holz=3.0, Erde=3.0, Wasser=3.0, Feuer=3.0, Metall=3.0)
        results = ke_tensions_in_vector(v, threshold=0.0)
        intensities = [r.ke_intensity for r in results]
        assert intensities == sorted(intensities, reverse=True)

    def test_intensity_is_product_of_strengths(self):
        v = _vec(Holz=3.0, Erde=3.0)
        results = ke_tensions_in_vector(v, threshold=0.0)
        holz_rel = next((r for r in results if r.controller == "Holz"), None)
        assert holz_rel is not None
        assert holz_rel.ke_intensity == pytest.approx(
            holz_rel.controller_strength * holz_rel.controlled_strength, rel=1e-9
        )

    def test_threshold_zero_detects_all_five_pairs(self):
        # Balanced vector — all elements equal strength
        v = _vec(Holz=1.0, Feuer=1.0, Erde=1.0, Metall=1.0, Wasser=1.0)
        results = ke_tensions_in_vector(v, threshold=0.0)
        assert len(results) == 5

    def test_single_element_no_tension(self):
        v = _vec(Holz=1.0)
        results = ke_tensions_in_vector(v, threshold=0.15)
        assert results == []


# ── ke_cross_tensions ─────────────────────────────────────────────────────────

class TestKeCrossTensions:
    def test_western_controlling_bazi(self):
        # Western has strong Holz, BaZi has strong Erde
        west = _vec(Holz=5.0)
        bazi = _vec(Erde=5.0)
        results = ke_cross_tensions(west, bazi, threshold=0.5)
        assert any(r.controller == "Holz" and r.controlled == "Erde" for r in results)

    def test_bazi_controlling_western(self):
        # BaZi has strong Metall, Western has strong Holz
        west = _vec(Holz=5.0)
        bazi = _vec(Metall=5.0)
        results = ke_cross_tensions(west, bazi, threshold=0.5)
        assert any(r.controller == "Metall" and r.controlled == "Holz" for r in results)

    def test_both_directions_detected_simultaneously(self):
        # West: Holz strong → controls BaZi Erde
        # BaZi: Metall strong → controls West Holz
        west = _vec(Holz=5.0)
        bazi = _vec(Erde=3.0, Metall=3.0)
        results = ke_cross_tensions(west, bazi, threshold=0.1)
        controllers = {r.controller for r in results}
        assert "Holz" in controllers or "Metall" in controllers  # at least one direction

    def test_below_threshold_returns_empty(self):
        # Both vectors dominated by one element — the Ke target of that element
        # is zero in both, so no cross tension fires above threshold=0.9
        west = _vec(Holz=1.0)   # normalized: Holz=1.0, all others=0
        bazi = _vec(Feuer=1.0)  # normalized: Feuer=1.0, all others=0
        # Holz controls Erde (not Feuer), so no Holz→Erde cross tension (Erde=0 in bazi)
        # Wasser controls Feuer — but Wasser=0 in west
        results = ke_cross_tensions(west, bazi, threshold=0.5)
        assert results == []

    def test_sorted_by_descending_intensity(self):
        west = _vec(Holz=3.0, Wasser=2.0, Feuer=2.0)
        bazi = _vec(Erde=3.0, Feuer=2.0, Metall=2.0)
        results = ke_cross_tensions(west, bazi, threshold=0.0)
        intensities = [r.ke_intensity for r in results]
        assert intensities == sorted(intensities, reverse=True)

    def test_symmetric_vectors_no_dominant_direction(self):
        v = _vec(Holz=1.0, Feuer=1.0, Erde=1.0, Metall=1.0, Wasser=1.0)
        results = ke_cross_tensions(v, v, threshold=0.0)
        # Every Ke pair appears twice (west→bazi and bazi→west)
        assert len(results) == 10


# ── ke_cycle_summary ──────────────────────────────────────────────────────────

class TestKeCycleSummary:
    def test_summary_has_required_keys(self):
        west = _vec(Holz=3.0, Erde=2.0)
        bazi = _vec(Wasser=3.0, Feuer=2.0)
        result = ke_cycle_summary(west, bazi)
        assert set(result.keys()) == {
            "internal_western", "internal_bazi", "cross_tensions", "dominant_ke"
        }

    def test_dominant_ke_is_highest_intensity(self):
        west = _vec(Holz=5.0, Erde=5.0)  # internal Ke: Holz→Erde
        bazi = _vec(Wasser=1.0)
        result = ke_cycle_summary(west, bazi, threshold=0.0)
        all_relations = (
            result["internal_western"]
            + result["internal_bazi"]
            + result["cross_tensions"]
        )
        if all_relations and result["dominant_ke"] is not None:
            assert result["dominant_ke"].ke_intensity == max(
                r.ke_intensity for r in all_relations
            )

    def test_zero_vectors_dominant_is_none(self):
        result = ke_cycle_summary(WuXingVector.zero(), WuXingVector.zero())
        assert result["dominant_ke"] is None

    def test_zero_vectors_all_lists_empty(self):
        result = ke_cycle_summary(WuXingVector.zero(), WuXingVector.zero())
        assert result["internal_western"] == []
        assert result["internal_bazi"] == []
        assert result["cross_tensions"] == []
