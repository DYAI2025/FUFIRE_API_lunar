"""
test_calibration.py — Tests für bazi_engine/wuxing/calibration.py

Testet:
  A) H_calibrated nutzt effektiven [0,1]-Bereich (kein Kompressionsartefakt)
  B) Qualitätsflag: ok / sparse / degenerate korrekt vergeben
  C) Baselines konsistent mit Kalibrierungstabelle
  D) Nullvektor → degenerate + h_calibrated=0.0
  E) Kontrastnormierung: H < baseline → 0.0 (geclampt, nicht negativ)
  F) Pipeline-Integrität: calibrate_harmony() auf echten Fusion-Daten
"""
from __future__ import annotations

import pytest

from bazi_engine.wuxing.calibration import (
    _BASELINE_TABLE,
    CalibrationResult,
    _n_bazi_bucket,
    _n_west_bucket,
    calibrate_harmony,
)
from bazi_engine.wuxing.vector import WuXingVector

_STANDARD_BODIES = {
    "Sun":     {"longitude": 321.5, "is_retrograde": False},
    "Moon":    {"longitude":  45.2, "is_retrograde": False},
    "Mercury": {"longitude": 280.1, "is_retrograde": True},
    "Venus":   {"longitude": 310.0, "is_retrograde": False},
    "Mars":    {"longitude": 150.0, "is_retrograde": False},
    "Jupiter": {"longitude":  60.0, "is_retrograde": False},
    "Saturn":  {"longitude": 340.0, "is_retrograde": False},
}

_STANDARD_PILLARS = {
    "year":  {"stem": "Jia",  "branch": "Chen"},
    "month": {"stem": "Bing", "branch": "Yin"},
    "day":   {"stem": "Jia",  "branch": "Chen"},
    "hour":  {"stem": "Xin",  "branch": "Wei"},
}

_V_TYPICAL = WuXingVector(1.5, 2.0, 0.8, 1.2, 0.9)  # typischer nicht-null Vektor


class TestQualityFlag:
    def test_ok_with_sufficient_planets(self):
        bodies = {f"P{i}": {"longitude": float(i*30), "is_retrograde": False} for i in range(7)}
        pillars = {p: {"stem": "Jia", "branch": "Zi"} for p in ("year","month","day","hour")}
        result = calibrate_harmony(0.75, bodies, pillars, _V_TYPICAL, _V_TYPICAL)
        assert result.quality == "ok"

    def test_sparse_with_two_planets(self):
        bodies = {"Sun": {"longitude": 0.0, "is_retrograde": False},
                  "Moon": {"longitude": 90.0, "is_retrograde": False}}
        pillars = {"year": {"stem": "Jia", "branch": "Zi"}}
        result = calibrate_harmony(0.75, bodies, pillars, _V_TYPICAL, _V_TYPICAL)
        assert result.quality == "sparse"

    def test_degenerate_with_zero_west_vector(self):
        result = calibrate_harmony(
            0.0, _STANDARD_BODIES, _STANDARD_PILLARS,
            WuXingVector.zero(), _V_TYPICAL,
        )
        assert result.quality == "degenerate"
        assert result.h_calibrated == 0.0

    def test_degenerate_with_zero_bazi_vector(self):
        result = calibrate_harmony(
            0.0, _STANDARD_BODIES, _STANDARD_PILLARS,
            _V_TYPICAL, WuXingVector.zero(),
        )
        assert result.quality == "degenerate"

    def test_degenerate_both_zero_vectors(self):
        result = calibrate_harmony(
            0.0, {}, {},
            WuXingVector.zero(), WuXingVector.zero(),
        )
        assert result.quality == "degenerate"


class TestCalibrationRange:
    def test_h_calibrated_between_0_and_1(self):
        for h_raw in [0.5, 0.6, 0.7, 0.8, 0.9, 0.99]:
            result = calibrate_harmony(h_raw, _STANDARD_BODIES, _STANDARD_PILLARS,
                                       _V_TYPICAL, _V_TYPICAL)
            assert 0.0 <= result.h_calibrated <= 1.0, (
                f"h_raw={h_raw}: h_calibrated={result.h_calibrated}"
            )

    def test_h_raw_below_baseline_gives_zero(self):
        """H < Baseline → h_calibrated = 0.0 (geclampt)."""
        # Baseline für 7 Planeten / 4 Pfeiler ≈ 0.72
        result = calibrate_harmony(0.50, _STANDARD_BODIES, _STANDARD_PILLARS,
                                   _V_TYPICAL, _V_TYPICAL)
        assert result.h_calibrated == 0.0

    def test_h_raw_1_gives_high_calibrated(self):
        """H_raw = 1.0 → h_calibrated nahe 1.0."""
        result = calibrate_harmony(1.0, _STANDARD_BODIES, _STANDARD_PILLARS,
                                   _V_TYPICAL, _V_TYPICAL)
        assert result.h_calibrated > 0.8

    def test_h_calibrated_is_non_negative(self):
        for h_raw in [0.0, 0.1, 0.3, 0.5]:
            result = calibrate_harmony(h_raw, _STANDARD_BODIES, _STANDARD_PILLARS,
                                       _V_TYPICAL, _V_TYPICAL)
            assert result.h_calibrated >= 0.0

    def test_h_raw_preserved(self):
        result = calibrate_harmony(0.75, _STANDARD_BODIES, _STANDARD_PILLARS,
                                   _V_TYPICAL, _V_TYPICAL)
        assert result.h_raw == 0.75


class TestCalibrationMonotonicity:
    """Höheres H_raw → höheres (oder gleiches) H_calibrated."""
    def test_monotone_in_h_raw(self):
        h_raws = [0.65, 0.70, 0.75, 0.80, 0.85, 0.90, 0.95]
        cals = [
            calibrate_harmony(h, _STANDARD_BODIES, _STANDARD_PILLARS,
                               _V_TYPICAL, _V_TYPICAL).h_calibrated
            for h in h_raws
        ]
        for i in range(len(cals) - 1):
            assert cals[i] <= cals[i + 1] + 1e-6, (
                f"Nicht monoton: cals[{i}]={cals[i]:.4f} > cals[{i+1}]={cals[i+1]:.4f}"
            )


class TestBaselineTable:
    def test_all_9_bucket_combinations_present(self):
        buckets = ("sparse", "medium", "dense")
        for wb in buckets:
            for bb in buckets:
                assert (wb, bb) in _BASELINE_TABLE

    def test_baselines_in_plausible_range(self):
        for (wb, bb), (mean, std) in _BASELINE_TABLE.items():
            assert 0.4 <= mean <= 0.95, f"({wb},{bb}): mean={mean} außerhalb [0.4, 0.95]"
            assert 0.05 <= std <= 0.35, f"({wb},{bb}): std={std} außerhalb [0.05, 0.35]"

    def test_dense_dense_has_highest_baseline(self):
        dense = _BASELINE_TABLE[("dense", "dense")][0]
        for key, (mean, _) in _BASELINE_TABLE.items():
            if key != ("dense", "dense"):
                assert mean <= dense + 0.05, (
                    f"({key[0]},{key[1]}) mean={mean:.4f} > dense-dense={dense:.4f}"
                )

    def test_sparse_sparse_has_lowest_baseline(self):
        sparse = _BASELINE_TABLE[("sparse", "sparse")][0]
        for key, (mean, _) in _BASELINE_TABLE.items():
            if key != ("sparse", "sparse"):
                assert mean >= sparse - 0.05

    def test_bucket_boundaries(self):
        assert _n_west_bucket(1) == "sparse"
        assert _n_west_bucket(3) == "sparse"
        assert _n_west_bucket(4) == "medium"
        assert _n_west_bucket(8) == "medium"
        assert _n_west_bucket(9) == "dense"
        assert _n_bazi_bucket(8) == "sparse"
        assert _n_bazi_bucket(9) == "medium"
        assert _n_bazi_bucket(17) == "dense"


class TestCalibrationResult:
    def test_sigma_above_positive_when_h_above_baseline(self):
        result = calibrate_harmony(0.95, _STANDARD_BODIES, _STANDARD_PILLARS,
                                   _V_TYPICAL, _V_TYPICAL)
        assert result.sigma_above > 0

    def test_sigma_above_negative_when_h_below_baseline(self):
        result = calibrate_harmony(0.40, _STANDARD_BODIES, _STANDARD_PILLARS,
                                   _V_TYPICAL, _V_TYPICAL)
        assert result.sigma_above < 0

    def test_interpretation_band_returns_string(self):
        result = calibrate_harmony(0.85, _STANDARD_BODIES, _STANDARD_PILLARS,
                                   _V_TYPICAL, _V_TYPICAL)
        assert isinstance(result.interpretation_band, str)
        assert len(result.interpretation_band) > 0

    def test_interpretation_band_degenerate(self):
        result = calibrate_harmony(0.0, {}, {},
                                   WuXingVector.zero(), WuXingVector.zero())
        assert "Undefiniert" in result.interpretation_band

    def test_is_reliable_true_for_ok(self):
        result = calibrate_harmony(0.80, _STANDARD_BODIES, _STANDARD_PILLARS,
                                   _V_TYPICAL, _V_TYPICAL)
        assert result.is_reliable is True

    def test_is_reliable_false_for_degenerate(self):
        result = calibrate_harmony(0.0, {}, {},
                                   WuXingVector.zero(), WuXingVector.zero())
        assert result.is_reliable is False

    def test_n_west_and_n_bazi_stored(self):
        result = calibrate_harmony(0.75, _STANDARD_BODIES, _STANDARD_PILLARS,
                                   _V_TYPICAL, _V_TYPICAL)
        assert result.n_west == 7  # 7 Planeten in _STANDARD_BODIES
        assert result.n_bazi_contributions == 16  # 4 stems + Chen(3)+Yin(3)+Chen(3)+Wei(3) hidden


class TestCalibrationOnRealData:
    """Integration: calibrate_harmony auf echter Fusion-Pipeline-Ausgabe."""

    def test_full_pipeline_produces_calibration(self):
        from datetime import datetime, timezone

        from bazi_engine.fusion import compute_fusion_analysis
        from bazi_engine.wuxing.analysis import calculate_wuxing_from_bazi, calculate_wuxing_vector_from_planets
        from bazi_engine.wuxing.calibration import calibrate_harmony

        result = compute_fusion_analysis(
            birth_utc_dt=datetime(2024, 2, 10, 13, 30, tzinfo=timezone.utc),
            latitude=52.52, longitude=13.405,
            bazi_pillars=_STANDARD_PILLARS,
            western_bodies=_STANDARD_BODIES,
        )
        h_raw = result["harmony_index"]["harmony_index"]
        west_v = calculate_wuxing_vector_from_planets(_STANDARD_BODIES)
        bazi_v = calculate_wuxing_from_bazi(_STANDARD_PILLARS)
        cal = calibrate_harmony(h_raw, _STANDARD_BODIES, _STANDARD_PILLARS, west_v, bazi_v)

        assert isinstance(cal, CalibrationResult)
        assert 0.0 <= cal.h_calibrated <= 1.0
        assert cal.quality == "ok"
        assert cal.h_raw == pytest.approx(h_raw, abs=1e-6)
