"""
test_wuxing_zones.py — Tests für bazi_engine/wuxing/zones.py

Testet:
  A) Das 10-Case-Fixture (alle Schwellenwert- und Prioritätsfälle)
  B) Disjunktions-Beweis (keine Zone kann gleichzeitig in zwei Kategorien sein)
  C) Grenzwertanalyse (exakt auf den Schwellen: 0.149/0.150/0.151, 0.199/0.200/0.201)
  D) Leitfragen-Bibliothek (question_tension, question_development, build_leitfragen)
  E) Report-Format (format_report_b Grundstruktur)
  F) Sheng-Zyklus-Integrität (prev/next-Konsistenz der Zyklusdaten)
"""
from __future__ import annotations

import pytest

from bazi_engine.wuxing.constants import WUXING_ORDER
from bazi_engine.wuxing.zones import (
    _NEXT,
    _PREV,
    ZoneResult,
    build_leitfragen,
    classify_zones,
    format_report_b,
    question_development,
    question_tension,
)

ELEMENTS = WUXING_ORDER

# ── Hilfsfunktion: gleichmäßige Basisverteilung ──────────────────────────────

def _base(val: float = 0.18) -> dict:
    """Erstellt einen gleichmäßigen 5-Vektor als Ausgangspunkt für Tests."""
    return {e: val for e in ELEMENTS}


def _vec(**overrides) -> dict:
    """Gleichmäßiger Basisvektor mit spezifischen Element-Overrides."""
    v = _base()
    v.update(overrides)
    return v


# ── A) 10-Case-Fixture ────────────────────────────────────────────────────────

FIXTURE = [
    {
        "id": "T01_tension_pos_0p16",
        "west":  _vec(Holz=0.35),
        "bazi":  _vec(Holz=0.19),
        "expected": {"Holz": "TENSION", "Feuer": "NEUTRAL", "Erde": "NEUTRAL",
                     "Metall": "NEUTRAL", "Wasser": "NEUTRAL"},
        "notes": "abs(d_Holz)=0.16 > 0.15 → TENSION, West dominiert",
    },
    {
        "id": "T02_strength_exact_0p15",
        "west":  _vec(Holz=0.355),
        "bazi":  _vec(Holz=0.205),
        "expected": {"Holz": "STRENGTH", "Feuer": "NEUTRAL", "Erde": "NEUTRAL",
                     "Metall": "NEUTRAL", "Wasser": "NEUTRAL"},
        "notes": "d=+0.15 exakt → NICHT Tension (strict >), beide > 0.20 → STRENGTH",
    },
    {
        "id": "T03_strength_0p149",
        "west":  _vec(Holz=0.350),
        "bazi":  _vec(Holz=0.201),
        "expected": {"Holz": "STRENGTH", "Feuer": "NEUTRAL", "Erde": "NEUTRAL",
                     "Metall": "NEUTRAL", "Wasser": "NEUTRAL"},
        "notes": "abs(d)=0.149 ≤ 0.15, beide > 0.20 → STRENGTH",
    },
    {
        "id": "T04_tension_beats_strength",
        "west":  _vec(Holz=0.37),
        "bazi":  _vec(Holz=0.21),
        "expected": {"Holz": "TENSION", "Feuer": "NEUTRAL", "Erde": "NEUTRAL",
                     "Metall": "NEUTRAL", "Wasser": "NEUTRAL"},
        "notes": "beide > 0.20, aber abs(d)=0.16 → TENSION hat Priorität",
    },
    {
        "id": "T05_development_both_0p149",
        "west":  _vec(Wasser=0.149),
        "bazi":  _vec(Wasser=0.149),
        "expected": {"Holz": "NEUTRAL", "Feuer": "NEUTRAL", "Erde": "NEUTRAL",
                     "Metall": "NEUTRAL", "Wasser": "DEVELOPMENT"},
        "notes": "beide < 0.15 (strict) → DEVELOPMENT",
    },
    {
        "id": "T06_not_development_at_0p15",
        "west":  _vec(Wasser=0.15),
        "bazi":  _vec(Wasser=0.14),
        "expected": {"Holz": "NEUTRAL", "Feuer": "NEUTRAL", "Erde": "NEUTRAL",
                     "Metall": "NEUTRAL", "Wasser": "NEUTRAL"},
        "notes": "west=0.15 NICHT < 0.15 (strict) → NEUTRAL, nicht DEVELOPMENT",
    },
    {
        "id": "T07_development_asymmetric",
        "west":  _vec(Wasser=0.149),
        "bazi":  _vec(Wasser=0.10),
        "expected": {"Holz": "NEUTRAL", "Feuer": "NEUTRAL", "Erde": "NEUTRAL",
                     "Metall": "NEUTRAL", "Wasser": "DEVELOPMENT"},
        "notes": "beide < 0.15, unterschiedliche Werte → DEVELOPMENT",
    },
    {
        "id": "T08_neutral_mixed_0p19_0p21",
        "west":  _vec(Metall=0.19),
        "bazi":  _vec(Metall=0.21),
        "expected": {"Holz": "NEUTRAL", "Feuer": "NEUTRAL", "Erde": "NEUTRAL",
                     "Metall": "NEUTRAL", "Wasser": "NEUTRAL"},
        "notes": "nicht Tension (abs(d)=0.02), nicht Strength (west≤0.20), nicht Dev → NEUTRAL",
    },
    {
        "id": "T09_tension_neg_0p20",
        "west":  _vec(Erde=0.10),
        "bazi":  _vec(Erde=0.30),
        "expected": {"Holz": "NEUTRAL", "Feuer": "NEUTRAL", "Erde": "TENSION",
                     "Metall": "NEUTRAL", "Wasser": "NEUTRAL"},
        "notes": "abs(d)=0.20 > 0.15 → TENSION, BaZi dominiert",
    },
    {
        "id": "T10_mix_tension_strength_development",
        "west":  {"Holz": 0.37, "Feuer": 0.28, "Erde": 0.18, "Metall": 0.18, "Wasser": 0.12},
        "bazi":  {"Holz": 0.21, "Feuer": 0.23, "Erde": 0.18, "Metall": 0.18, "Wasser": 0.11},
        "expected": {"Holz": "TENSION", "Feuer": "STRENGTH", "Erde": "NEUTRAL",
                     "Metall": "NEUTRAL", "Wasser": "DEVELOPMENT"},
        "notes": "integrierter Gesamtfall: alle drei Reporting-Zonen gleichzeitig",
    },
]


@pytest.mark.parametrize("case", FIXTURE, ids=[c["id"] for c in FIXTURE])
def test_fixture_zones(case):
    """Das 10-Case-Fixture muss vollständig übereinstimmen."""
    result = classify_zones(case["west"], case["bazi"])
    for elem in ELEMENTS:
        got = result.zones[elem]
        exp = case["expected"][elem]
        d_val = result.diffs[elem]
        assert got == exp, (
            f"[{case['id']}] {elem}: got={got!r}, expected={exp!r}, "
            f"d={d_val:.6f}, west={case['west'][elem]}, bazi={case['bazi'][elem]}"
        )


# ── B) Disjunktionsbeweis (Property-Tests) ───────────────────────────────────

class TestDisjunction:
    """Beweist, dass die vier Zonen paarweise disjunkt sind."""

    def _classify(self, w, b) -> dict:
        return classify_zones(
            {e: w for e in ELEMENTS},
            {e: b for e in ELEMENTS},
        ).zones

    def test_tension_excludes_strength(self):
        """Wenn abs(d) > 0.15 → TENSION, nie STRENGTH."""
        zones = classify_zones(
            _vec(Holz=0.40),  # west high
            _vec(Holz=0.21),  # bazi > 0.20, d=0.19 > 0.15
        ).zones
        assert zones["Holz"] == "TENSION"
        # Hätte ohne Priorität STRENGTH sein können (beide > 0.20)

    def test_strength_values_cannot_be_development(self):
        """Strength verlangt beide > 0.20; Development verlangt beide < 0.15.
        Unmöglich gleichzeitig erfüllt (0.20 > 0.15)."""
        # Mathematisch ausgeschlossen — dieser Test bestätigt die Implementierung
        zones = classify_zones(
            _vec(Holz=0.25),
            _vec(Holz=0.25),
        ).zones
        assert zones["Holz"] == "STRENGTH"
        # Kann nie DEVELOPMENT sein, da 0.25 ≮ 0.15

    def test_development_cannot_trigger_tension(self):
        """Wenn beide < 0.15, dann |d| = |w-b| < 0.15 → keine TENSION."""
        zones = classify_zones(
            _vec(Wasser=0.12),
            _vec(Wasser=0.10),  # d=0.02, |d| < 0.15
        ).zones
        assert zones["Wasser"] == "DEVELOPMENT"

    def test_all_elements_classified(self):
        """Jedes Element bekommt genau eine Zone."""
        result = classify_zones(_vec(), _vec())
        assert set(result.zones.keys()) == set(ELEMENTS)
        for e in ELEMENTS:
            assert result.zones[e] in ("TENSION", "STRENGTH", "DEVELOPMENT", "NEUTRAL")

    def test_exactly_four_zone_labels(self):
        """Nur die vier definierten Labels werden vergeben."""
        result = classify_zones(
            {"Holz": 0.37, "Feuer": 0.28, "Erde": 0.18, "Metall": 0.18, "Wasser": 0.12},
            {"Holz": 0.21, "Feuer": 0.23, "Erde": 0.18, "Metall": 0.18, "Wasser": 0.11},
        )
        for zone in result.zones.values():
            assert zone in {"TENSION", "STRENGTH", "DEVELOPMENT", "NEUTRAL"}


# ── C) Grenzwertanalyse ───────────────────────────────────────────────────────

class TestBoundaries:
    """Systematische Grenzwerttests an den drei Schwellenwerten."""

    # --- Tension-Schwelle 0.15 ---

    def test_d_0p1499_not_tension(self):
        """d = 0.1499 < 0.15 → nicht TENSION."""
        zones = classify_zones(_vec(Holz=0.3699), _vec(Holz=0.22)).zones
        assert zones["Holz"] != "TENSION"  # d=0.1499

    def test_d_exactly_0p15_not_tension(self):
        """d = 0.15 exakt → strict > → nicht TENSION."""
        zones = classify_zones(_vec(Holz=0.355), _vec(Holz=0.205)).zones
        # d = 0.355 - 0.205 = 0.150 exakt → nicht TENSION
        assert zones["Holz"] != "TENSION"

    def test_d_0p1501_is_tension(self):
        """d = 0.1501 > 0.15 → TENSION."""
        zones = classify_zones(_vec(Holz=0.3701), _vec(Holz=0.22)).zones
        assert zones["Holz"] == "TENSION"

    # --- Strength-Schwelle 0.20 ---

    def test_west_0p1999_not_strength(self):
        """west = 0.1999 ≤ 0.20 → nicht STRENGTH."""
        zones = classify_zones(_vec(Holz=0.1999), _vec(Holz=0.22)).zones
        assert zones["Holz"] != "STRENGTH"

    def test_both_exactly_0p20_not_strength(self):
        """west = bazi = 0.20 → strict > → nicht STRENGTH."""
        zones = classify_zones(_vec(Holz=0.20), _vec(Holz=0.20)).zones
        assert zones["Holz"] != "STRENGTH"

    def test_both_0p2001_is_strength(self):
        """west = bazi = 0.2001, d=0 → STRENGTH."""
        zones = classify_zones(_vec(Holz=0.2001), _vec(Holz=0.2001)).zones
        assert zones["Holz"] == "STRENGTH"

    # --- Development-Schwelle 0.15 ---

    def test_both_0p1501_not_development(self):
        """west = bazi = 0.1501 ≥ 0.15 → nicht DEVELOPMENT."""
        zones = classify_zones(_vec(Wasser=0.1501), _vec(Wasser=0.1501)).zones
        assert zones["Wasser"] != "DEVELOPMENT"

    def test_both_exactly_0p15_not_development(self):
        """west = bazi = 0.15 → strict < → nicht DEVELOPMENT."""
        zones = classify_zones(_vec(Wasser=0.15), _vec(Wasser=0.15)).zones
        assert zones["Wasser"] != "DEVELOPMENT"

    def test_both_0p1499_is_development(self):
        """west = bazi = 0.1499 < 0.15 → DEVELOPMENT."""
        zones = classify_zones(_vec(Wasser=0.1499), _vec(Wasser=0.1499)).zones
        assert zones["Wasser"] == "DEVELOPMENT"

    def test_one_above_threshold_not_development(self):
        """west < 0.15, bazi ≥ 0.15 → nicht DEVELOPMENT (beide müssen niedrig sein)."""
        zones = classify_zones(_vec(Wasser=0.10), _vec(Wasser=0.16)).zones
        assert zones["Wasser"] != "DEVELOPMENT"


# ── D) Leitfragen-Bibliothek ─────────────────────────────────────────────────

class TestQuestionTension:
    def test_positive_d_returns_list(self):
        q = question_tension("Feuer", 0.30)
        assert isinstance(q, list)
        assert len(q) >= 1

    def test_negative_d_returns_list(self):
        q = question_tension("Holz", -0.25)
        assert isinstance(q, list)
        assert len(q) >= 1

    def test_no_sheng_returns_one_question(self):
        q = question_tension("Erde", 0.20, use_sheng=False)
        assert len(q) == 1

    def test_with_sheng_returns_two_questions(self):
        q = question_tension("Metall", 0.20, use_sheng=True)
        assert len(q) == 2

    def test_sheng_question_marked(self):
        q = question_tension("Wasser", 0.20, use_sheng=True)
        assert any("[Sheng-Frage]" in s for s in q)

    def test_sheng_next_element_appears(self):
        """Sheng-Frage für Feuer muss 'Erde' (next) erwähnen."""
        q = question_tension("Feuer", -0.20, use_sheng=True)
        sheng_q = next(s for s in q if "[Sheng-Frage]" in s)
        assert "Erde" in sheng_q  # next(Feuer) = Erde

    def test_sheng_prev_element_in_positive_d(self):
        """Bei d > 0: Sheng-Frage soll prev-Element erwähnen."""
        q = question_tension("Feuer", 0.20, use_sheng=True)
        sheng_q = next(s for s in q if "[Sheng-Frage]" in s)
        assert "Holz" in sheng_q  # prev(Feuer) = Holz

    @pytest.mark.parametrize("elem", ELEMENTS)
    def test_all_elements_generate_question(self, elem):
        q = question_tension(elem, 0.20)
        assert len(q) >= 1
        assert all(isinstance(s, str) and len(s) > 0 for s in q)

    def test_magnitude_in_question_text(self):
        """Der Betrag der Differenz (als Indexpunkte) erscheint im Text."""
        q = question_tension("Holz", 0.30)
        core = q[0]
        # 0.30 × 100 = 30.0 Indexpunkte
        assert "30.0" in core

    def test_zero_d_handled(self):
        q = question_tension("Erde", 0.0)
        assert len(q) >= 1


class TestQuestionDevelopment:
    def test_returns_list(self):
        q = question_development("Wasser", 0.10, 0.12)
        assert isinstance(q, list)
        assert len(q) >= 1

    def test_no_sheng_returns_one(self):
        q = question_development("Wasser", 0.10, 0.12, use_sheng=False)
        assert len(q) == 1

    def test_with_sheng_returns_two(self):
        q = question_development("Wasser", 0.10, 0.12, use_sheng=True)
        assert len(q) == 2

    def test_sheng_prev_element_appears(self):
        """Sheng-Frage für Wasser soll prev=Metall erwähnen."""
        q = question_development("Wasser", 0.10, 0.12, use_sheng=True)
        sheng_q = next(s for s in q if "[Sheng-Frage]" in s)
        assert "Metall" in sheng_q  # prev(Wasser) = Metall

    def test_values_appear_as_index_points(self):
        """west und bazi werden als Indexpunkte (×100) ausgegeben."""
        q = question_development("Holz", 0.12, 0.10)
        core = q[0]
        assert "12.0" in core  # 0.12 × 100
        assert "10.0" in core  # 0.10 × 100

    @pytest.mark.parametrize("elem", ELEMENTS)
    def test_all_elements_generate_question(self, elem):
        q = question_development(elem, 0.10, 0.12)
        assert len(q) >= 1
        assert all(isinstance(s, str) and len(s) > 0 for s in q)


class TestBuildLeitfragen:
    def test_only_tension_and_development_get_questions(self):
        result = classify_zones(
            {"Holz": 0.37, "Feuer": 0.28, "Erde": 0.18, "Metall": 0.18, "Wasser": 0.12},
            {"Holz": 0.21, "Feuer": 0.23, "Erde": 0.18, "Metall": 0.18, "Wasser": 0.11},
        )
        lf = build_leitfragen(result)
        # Holz=TENSION, Feuer=STRENGTH (no question), Wasser=DEVELOPMENT
        assert "Holz" in lf["tension"]
        assert "Wasser" in lf["development"]
        assert "Feuer" not in lf["tension"]
        assert "Feuer" not in lf["development"]

    def test_returns_dict_with_two_sections(self):
        result = classify_zones(_vec(), _vec())
        lf = build_leitfragen(result)
        assert "tension" in lf
        assert "development" in lf

    def test_no_tension_empty_section(self):
        # Alle Elemente bei 0.25, d=0 überall → keine Tension, keine Development
        uniform = {e: 0.25 for e in ELEMENTS}
        result = classify_zones(uniform, uniform)
        lf = build_leitfragen(result)
        assert lf["tension"] == {}

    def test_all_questions_are_strings(self):
        result = classify_zones(
            {"Holz": 0.37, "Feuer": 0.28, "Erde": 0.18, "Metall": 0.18, "Wasser": 0.12},
            {"Holz": 0.21, "Feuer": 0.23, "Erde": 0.18, "Metall": 0.18, "Wasser": 0.11},
        )
        lf = build_leitfragen(result)
        for section in lf.values():
            for elem, qs in section.items():
                for q in qs:
                    assert isinstance(q, str)


# ── E) Report-Format ──────────────────────────────────────────────────────────

class TestFormatReportB:
    def test_returns_string(self):
        result = classify_zones(
            {"Holz": 0.37, "Feuer": 0.28, "Erde": 0.18, "Metall": 0.18, "Wasser": 0.12},
            {"Holz": 0.21, "Feuer": 0.23, "Erde": 0.18, "Metall": 0.18, "Wasser": 0.11},
        )
        r = format_report_b(0.68, "Gute Harmonie", result)
        assert isinstance(r, str)
        assert len(r) > 50

    def test_harmony_index_in_report(self):
        result = classify_zones(_vec(), _vec())
        r = format_report_b(0.72, "Gute Harmonie", result)
        assert "72.00" in r

    def test_section_headers_present(self):
        result = classify_zones(
            {"Holz": 0.37, "Feuer": 0.28, "Erde": 0.18, "Metall": 0.18, "Wasser": 0.12},
            {"Holz": 0.21, "Feuer": 0.23, "Erde": 0.18, "Metall": 0.18, "Wasser": 0.11},
        )
        r = format_report_b(0.68, "Gute Harmonie", result)
        assert "STÄRKEFELDER" in r
        assert "SPANNUNGSFELDER" in r
        assert "ENTWICKLUNGSFELDER" in r

    def test_index_point_disclaimer_present(self):
        result = classify_zones(_vec(), _vec())
        r = format_report_b(0.5, "Moderate Balance", result)
        assert "L2" in r or "Indexpunkte" in r

    def test_no_sheng_no_sheng_label(self):
        result = classify_zones(
            {"Holz": 0.37, "Feuer": 0.28, "Erde": 0.18, "Metall": 0.18, "Wasser": 0.12},
            {"Holz": 0.21, "Feuer": 0.23, "Erde": 0.18, "Metall": 0.18, "Wasser": 0.11},
        )
        r = format_report_b(0.68, "Gute Harmonie", result, use_sheng=False)
        assert "[Sheng-Frage]" not in r

    def test_with_sheng_has_sheng_label(self):
        result = classify_zones(
            {"Holz": 0.37, "Feuer": 0.28, "Erde": 0.18, "Metall": 0.18, "Wasser": 0.12},
            {"Holz": 0.21, "Feuer": 0.23, "Erde": 0.18, "Metall": 0.18, "Wasser": 0.11},
        )
        r = format_report_b(0.68, "Gute Harmonie", result, use_sheng=True)
        assert "[Sheng-Frage]" in r


# ── F) Sheng-Zyklus-Integrität ────────────────────────────────────────────────

class TestShengCycle:
    def test_next_covers_all_five_elements(self):
        assert set(_NEXT.keys()) == set(ELEMENTS)

    def test_prev_covers_all_five_elements(self):
        assert set(_PREV.keys()) == set(ELEMENTS)

    def test_next_is_inverse_of_prev(self):
        for elem in ELEMENTS:
            assert _PREV[_NEXT[elem]] == elem

    def test_full_cycle_returns_to_start(self):
        current = "Holz"
        for _ in range(5):
            current = _NEXT[current]
        assert current == "Holz"

    def test_prev_full_cycle_returns_to_start(self):
        current = "Wasser"
        for _ in range(5):
            current = _PREV[current]
        assert current == "Wasser"

    def test_holz_next_is_feuer(self):
        assert _NEXT["Holz"] == "Feuer"

    def test_wasser_next_is_holz(self):
        assert _NEXT["Wasser"] == "Holz"

    def test_no_element_is_its_own_next(self):
        for elem in ELEMENTS:
            assert _NEXT[elem] != elem

    def test_sheng_order_matches_wuxing_order(self):
        """Der NEXT-Zyklus muss mit WUXING_ORDER übereinstimmen."""
        for i, elem in enumerate(WUXING_ORDER):
            expected_next = WUXING_ORDER[(i + 1) % 5]
            assert _NEXT[elem] == expected_next, (
                f"NEXT[{elem}]={_NEXT[elem]}, expected {expected_next}"
            )


# ── ZoneResult-Methoden ───────────────────────────────────────────────────────

class TestZoneResultMethods:
    def _make_t10(self) -> ZoneResult:
        return classify_zones(
            {"Holz": 0.37, "Feuer": 0.28, "Erde": 0.18, "Metall": 0.18, "Wasser": 0.12},
            {"Holz": 0.21, "Feuer": 0.23, "Erde": 0.18, "Metall": 0.18, "Wasser": 0.11},
        )

    def test_tension_elements_correct(self):
        assert self._make_t10().tension_elements() == ["Holz"]

    def test_strength_elements_correct(self):
        assert self._make_t10().strength_elements() == ["Feuer"]

    def test_development_elements_correct(self):
        assert self._make_t10().development_elements() == ["Wasser"]

    def test_diffs_sign_positive_when_west_greater(self):
        result = classify_zones(_vec(Holz=0.40), _vec(Holz=0.20))
        assert result.diffs["Holz"] > 0

    def test_diffs_sign_negative_when_bazi_greater(self):
        result = classify_zones(_vec(Holz=0.10), _vec(Holz=0.40))
        assert result.diffs["Holz"] < 0

    def test_result_is_frozen(self):
        result = self._make_t10()
        with pytest.raises((AttributeError, TypeError)):
            result.zones = {}  # type: ignore[misc]
