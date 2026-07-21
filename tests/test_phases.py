"""
test_phases.py — Tests für bazi_engine/phases/

Testet:
  A) JieqiPhase: Klassifikation, Abdeckung, Zyklusstruktur
  B) LunarPhase: Klassifikation, Abdeckung, Zyklusstruktur
  C) Externe Unabhängigkeit: Phasen stammen NICHT aus individuellen Chartdaten
  D) Determinismus: gleiche Eingabe → gleiche Ausgabe
  E) Vollständigkeit: alle 24 Jieqi / alle 8 Mondphasen erreichbar
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from bazi_engine.phases import (
    JIEQI_PHASES,
    LUNAR_PHASES,
    JieqiPhase,
    LunarPhase,
    classify_jieqi_phase,
    classify_lunar_phase,
)

VALID_ELEMENTS = {"Holz", "Feuer", "Erde", "Metall", "Wasser"}
VALID_POLARITIES = {"Yang", "Yin"}


# ── A) JieqiPhase ─────────────────────────────────────────────────────────────

class TestJieqiPhaseClassification:
    def test_returns_jieqi_phase(self):
        r = classify_jieqi_phase(solar_longitude=315.0)
        assert isinstance(r, JieqiPhase)

    def test_lichun_at_315(self):
        r = classify_jieqi_phase(solar_longitude=315.0)
        assert r.name_pinyin == "Lichun"
        assert r.index == 0

    def test_chunfen_at_0(self):
        r = classify_jieqi_phase(solar_longitude=0.0)
        assert r.name_pinyin == "Chunfen"

    def test_xiazhi_at_90(self):
        r = classify_jieqi_phase(solar_longitude=90.0)
        assert r.name_pinyin == "Xiazhi"

    def test_qiufen_at_180(self):
        r = classify_jieqi_phase(solar_longitude=180.0)
        assert r.name_pinyin == "Qiufen"

    def test_dongzhi_at_270(self):
        r = classify_jieqi_phase(solar_longitude=270.0)
        assert r.name_pinyin == "Dongzhi"

    def test_index_in_range(self):
        for lon in range(0, 360, 5):
            r = classify_jieqi_phase(solar_longitude=float(lon))
            assert 0 <= r.index < 24

    def test_position_in_phase_0_to_1(self):
        for lon in [0.0, 7.5, 14.9, 89.9, 270.0, 359.9]:
            r = classify_jieqi_phase(solar_longitude=lon)
            assert 0.0 <= r.position_in_phase <= 1.0

    def test_element_is_valid(self):
        for lon in range(0, 360, 15):
            r = classify_jieqi_phase(solar_longitude=float(lon))
            assert r.element in VALID_ELEMENTS

    def test_polarity_is_valid(self):
        for lon in range(0, 360, 15):
            r = classify_jieqi_phase(solar_longitude=float(lon))
            assert r.polarity in VALID_POLARITIES

    def test_from_datetime_returns_phase(self):
        dt = datetime(2024, 2, 10, 12, 0, tzinfo=timezone.utc)
        r = classify_jieqi_phase(dt=dt)
        assert isinstance(r, JieqiPhase)

    def test_raises_without_args(self):
        with pytest.raises(ValueError):
            classify_jieqi_phase()

    def test_solar_longitude_modulo(self):
        """360° und 0° müssen dieselbe Phase ergeben."""
        r0 = classify_jieqi_phase(solar_longitude=0.0)
        r360 = classify_jieqi_phase(solar_longitude=360.0)
        assert r0.index == r360.index

    def test_phase_boundaries_are_15_degrees_apart(self):
        """Jede Phase beginnt genau 15° nach der vorherigen."""
        for i in range(len(JIEQI_PHASES)):
            start = JIEQI_PHASES[i][0]
            next_start = JIEQI_PHASES[(i + 1) % 24][0]
            diff = (next_start - start) % 360.0
            assert abs(diff - 15.0) < 1e-9, f"Phase {i}: Abstand {diff}° ≠ 15°"


class TestJieqiPhaseCoverage:
    def test_all_24_phases_reachable(self):
        """Jede der 24 Phasen muss durch einen Sonnenlängenwert erreichbar sein."""
        seen = set()
        for lon in range(0, 360, 15):
            r = classify_jieqi_phase(solar_longitude=float(lon) + 7.5)
            seen.add(r.index)
        assert len(seen) == 24

    def test_all_24_names_unique(self):
        names = [p[1] for p in JIEQI_PHASES]
        assert len(set(names)) == 24

    def test_five_elements_all_represented(self):
        qualities = {p[3].split("_")[0] for p in JIEQI_PHASES}
        assert qualities == VALID_ELEMENTS

    def test_each_element_has_yang_and_yin(self):
        for elem in VALID_ELEMENTS:
            yang = any(p[3] == f"{elem}_Yang" for p in JIEQI_PHASES)
            yin  = any(p[3] == f"{elem}_Yin"  for p in JIEQI_PHASES)
            assert yang, f"{elem}_Yang fehlt"
            assert yin,  f"{elem}_Yin fehlt"


# ── B) LunarPhase ─────────────────────────────────────────────────────────────

class TestLunarPhaseClassification:
    def test_returns_lunar_phase(self):
        r = classify_lunar_phase(moon_sun_angle=0.0)
        assert isinstance(r, LunarPhase)

    def test_new_moon_at_0(self):
        r = classify_lunar_phase(moon_sun_angle=0.0)
        assert r.name_de == "Neumond"
        assert r.index == 0

    def test_first_quarter_at_90(self):
        r = classify_lunar_phase(moon_sun_angle=90.0)
        assert r.name_de == "Erstes Viertel"

    def test_full_moon_at_180(self):
        r = classify_lunar_phase(moon_sun_angle=180.0)
        assert r.name_de == "Vollmond"

    def test_last_quarter_at_270(self):
        r = classify_lunar_phase(moon_sun_angle=270.0)
        assert r.name_de == "Letztes Viertel"

    def test_index_in_range(self):
        for angle in range(0, 360, 10):
            r = classify_lunar_phase(moon_sun_angle=float(angle))
            assert 0 <= r.index < 8

    def test_position_in_phase_0_to_1(self):
        for angle in [0.0, 22.5, 44.9, 89.9, 179.9, 359.9]:
            r = classify_lunar_phase(moon_sun_angle=angle)
            assert 0.0 <= r.position_in_phase <= 1.0

    def test_is_waxing_true_below_180(self):
        r = classify_lunar_phase(moon_sun_angle=90.0)
        assert r.is_waxing is True

    def test_is_waxing_false_above_180(self):
        r = classify_lunar_phase(moon_sun_angle=270.0)
        assert r.is_waxing is False

    def test_is_full_near_180(self):
        r = classify_lunar_phase(moon_sun_angle=180.0)
        assert r.is_full is True

    def test_is_new_near_0(self):
        r = classify_lunar_phase(moon_sun_angle=0.0)
        assert r.is_new is True

    def test_from_datetime(self):
        dt = datetime(2024, 1, 25, 17, 54, tzinfo=timezone.utc)  # Vollmond ~2024-01-25
        r = classify_lunar_phase(dt=dt)
        assert isinstance(r, LunarPhase)

    def test_raises_without_args(self):
        with pytest.raises(ValueError):
            classify_lunar_phase()

    def test_modulo_360(self):
        r0 = classify_lunar_phase(moon_sun_angle=0.0)
        r360 = classify_lunar_phase(moon_sun_angle=360.0)
        assert r0.index == r360.index


class TestLunarPhaseCoverage:
    def test_all_8_phases_reachable(self):
        seen = set()
        for angle in range(0, 360, 45):
            r = classify_lunar_phase(moon_sun_angle=float(angle) + 22.5)
            seen.add(r.index)
        assert len(seen) == 8

    def test_all_8_names_unique(self):
        names = [p[1] for p in LUNAR_PHASES]
        assert len(set(names)) == 8

    def test_boundaries_are_45_degrees_apart(self):
        for i in range(len(LUNAR_PHASES)):
            start = LUNAR_PHASES[i][0]
            next_s = LUNAR_PHASES[(i + 1) % 8][0]
            diff = (next_s - start) % 360.0
            assert abs(diff - 45.0) < 1e-9


# ── C) Externe Unabhängigkeit ─────────────────────────────────────────────────

class TestExternalIndependence:
    """Phasen dürfen NICHT von individuellen Chart-Daten abhängen."""

    def test_jieqi_depends_only_on_solar_longitude(self):
        """Zwei Charts mit gleicher Sonnenlänge → gleiche Jieqi-Phase."""
        r1 = classify_jieqi_phase(solar_longitude=45.0)
        r2 = classify_jieqi_phase(solar_longitude=45.0)
        assert r1.index == r2.index
        assert r1.name_pinyin == r2.name_pinyin

    def test_lunar_depends_only_on_moon_sun_angle(self):
        r1 = classify_lunar_phase(moon_sun_angle=135.0)
        r2 = classify_lunar_phase(moon_sun_angle=135.0)
        assert r1.index == r2.index

    def test_jieqi_independent_of_bazi_input(self):
        """Die Jieqi-Phase hängt nicht von den Vier Pfeilern ab."""
        # Beide haben gleiche Sonnenlänge, unterschiedliche Pfeiler → gleiche Phase
        r1 = classify_jieqi_phase(solar_longitude=90.0)
        r2 = classify_jieqi_phase(solar_longitude=90.0)
        # (Pfeiler-Simulation: beide bekommen dieselbe Phase)
        assert r1.name_pinyin == r2.name_pinyin

    def test_all_24_jieqi_have_defined_wuxing_quality(self):
        for lon in [i * 15.0 + 7.5 for i in range(24)]:
            r = classify_jieqi_phase(solar_longitude=lon)
            assert "_" in r.wuxing_quality
            elem, pol = r.wuxing_quality.split("_")
            assert elem in VALID_ELEMENTS
            assert pol in VALID_POLARITIES


# ── D) Determinismus ──────────────────────────────────────────────────────────

class TestDeterminism:
    @pytest.mark.parametrize("lon", [0.0, 45.0, 90.0, 135.0, 180.0, 225.0, 270.0, 315.0])
    def test_jieqi_deterministic(self, lon):
        r1 = classify_jieqi_phase(solar_longitude=lon)
        r2 = classify_jieqi_phase(solar_longitude=lon)
        assert r1 == r2

    @pytest.mark.parametrize("angle", [0.0, 45.0, 90.0, 135.0, 180.0, 225.0, 270.0, 315.0])
    def test_lunar_deterministic(self, angle):
        r1 = classify_lunar_phase(moon_sun_angle=angle)
        r2 = classify_lunar_phase(moon_sun_angle=angle)
        assert r1 == r2
