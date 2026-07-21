"""
wuxing/zones.py — Logik B: Exklusive, hierarchische Zonenklassifikation.

Klassifiziert jede der fünf Wu-Xing-Achsen in genau eine Zone:
  TENSION      — abs(d_i) > thr_tension         (priorisiert)
  STRENGTH     — west > thr_strength AND bazi > thr_strength AND abs(d_i) <= thr_tension
  DEVELOPMENT  — west < thr_development AND bazi < thr_development
  NEUTRAL      — keines der obigen (nicht im Report angezeigt)

Garantie: Die vier Zonen sind paarweise disjunkt.
Beweis:
  • TENSION vs STRENGTH:     Strength verlangt abs(d) <= thr, Tension abs(d) > thr → disjunkt.
  • STRENGTH vs DEVELOPMENT: Strength verlangt beide > 0.20, Development beide < 0.15 → unmöglich.
  • TENSION vs DEVELOPMENT:  Wenn beide < 0.15, dann |d| = |w - b| < 0.15, d.h. keine Tension.

Leitfragen-Bibliothek:
  question_tension()     — datengebundene Kernfrage + optionale Sheng-Frage
  question_development() — datengebundene Kernfrage + optionale Sheng-Frage
  build_leitfragen()     — erzeugt vollständigen Fragensatz für einen Report

Hinweis zu Anzeigewerten:
  Die Werte in wu_xing_vectors sind L2-Koordinaten, keine additiven Prozentanteile.
  Für die Anzeige: als "Indexpunkte" (0–100 skaliert) kennzeichnen, nicht als "%".
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Literal

from .constants import WUXING_ORDER

# ── Typen ────────────────────────────────────────────────────────────────────

ZoneLabel = Literal["TENSION", "STRENGTH", "DEVELOPMENT", "NEUTRAL"]

# Sheng-Zyklus (相生): prev/next aus fixer Ordnung — keine Messung, reine Konstante
_NEXT: Dict[str, str] = {
    "Holz":   "Feuer",
    "Feuer":  "Erde",
    "Erde":   "Metall",
    "Metall": "Wasser",
    "Wasser": "Holz",
}
_PREV: Dict[str, str] = {v: k for k, v in _NEXT.items()}


@dataclass(frozen=True)
class ZoneResult:
    """Klassifikationsergebnis für alle fünf Elemente."""
    zones:  Dict[str, ZoneLabel]
    diffs:  Dict[str, float]          # d_i = west_i − bazi_i (roh, nicht gerundet)
    west:   Dict[str, float]          # normierte westliche Werte (Eingabe)
    bazi:   Dict[str, float]          # normierte BaZi-Werte (Eingabe)

    def tension_elements(self) -> List[str]:
        return [e for e in WUXING_ORDER if self.zones[e] == "TENSION"]

    def strength_elements(self) -> List[str]:
        return [e for e in WUXING_ORDER if self.zones[e] == "STRENGTH"]

    def development_elements(self) -> List[str]:
        return [e for e in WUXING_ORDER if self.zones[e] == "DEVELOPMENT"]


# ── Kernfunktion ─────────────────────────────────────────────────────────────

def classify_zones(
    west_norm: Dict[str, float],
    bazi_norm: Dict[str, float],
    thr_tension:     float = 0.15,
    thr_strength:    float = 0.20,
    thr_development: float = 0.15,
    eps:             float = 1e-12,
) -> ZoneResult:
    """Klassifiziert alle fünf Elemente exklusiv und hierarchisch.

    Priorität: TENSION > STRENGTH > DEVELOPMENT > NEUTRAL.

    Args:
        west_norm:       L2-normierter westlicher Vektor (dict, keys=WUXING_ORDER).
        bazi_norm:       L2-normierter BaZi-Vektor.
        thr_tension:     Mindest-|d_i| für TENSION (default 0.15).
        thr_strength:    Mindestwert für beide Seiten bei STRENGTH (default 0.20).
        thr_development: Höchstwert für beide Seiten bei DEVELOPMENT (default 0.15).
        eps:             Numerischer Schutzpuffer (default 1e-12).

    Returns:
        ZoneResult mit zones, diffs, west, bazi.
    """
    diffs: Dict[str, float] = {
        e: float(west_norm[e]) - float(bazi_norm[e])
        for e in WUXING_ORDER
    }
    zones: Dict[str, ZoneLabel] = {}

    for e in WUXING_ORDER:
        w = float(west_norm[e])
        b = float(bazi_norm[e])
        d = diffs[e]
        abs_d = abs(d)

        # 1) TENSION — priorisiert
        if abs_d > thr_tension + eps:
            zones[e] = "TENSION"

        # 2) STRENGTH — nur wenn nicht TENSION
        elif (w > thr_strength + eps) and (b > thr_strength + eps):
            zones[e] = "STRENGTH"

        # 3) DEVELOPMENT — beidseitig niedrig
        elif (w < thr_development - eps) and (b < thr_development - eps):
            zones[e] = "DEVELOPMENT"

        # 4) NEUTRAL — alles andere
        else:
            zones[e] = "NEUTRAL"

    return ZoneResult(
        zones=zones,
        diffs=diffs,
        west={e: float(west_norm[e]) for e in WUXING_ORDER},
        bazi={e: float(bazi_norm[e]) for e in WUXING_ORDER},
    )


# ── Leitfragen-Bibliothek ─────────────────────────────────────────────────────

def _direction_label(d: float) -> str:
    if d > 0:
        return "West dominiert"
    if d < 0:
        return "BaZi dominiert"
    return "ausgeglichen"


def _delta_idx(d: float) -> float:
    """Differenz als Indexpunkte (0–100-Skala), gerundet auf 1 Dezimale."""
    return round(abs(d) * 100, 1)


def question_tension(
    elem: str,
    d: float,
    use_sheng: bool = True,
) -> List[str]:
    """Erzeugt Leitfragen für ein TENSION-Element.

    Kernfrage: datengebunden aus d-Vorzeichen und Magnitude.
    Sheng-Frage: interpretationsbasiert, als explizite Frage formuliert.
    Beides sind Fragen, keine Faktenbehauptungen.

    Args:
        elem:      Element-Name (z.B. "Feuer").
        d:         Differenz west_norm − bazi_norm für dieses Element.
        use_sheng: Falls True, wird eine Sheng-basierte Zusatzfrage angehängt.

    Returns:
        Liste mit 1–2 Fragen (Strings).
    """
    mag = _delta_idx(d)
    questions: List[str] = []

    # Kernfrage (Ground: d-Vorzeichen + Magnitude)
    if d > 0:
        questions.append(
            f"{elem} (Spannung +{mag} Pkt., West dominiert): "
            f"Der kosmische Moment bietet mehr {elem}-Energie, als deine innere Struktur aktuell trägt. "
            f"Wo wartet ein Impuls von außen noch auf deine Annahme?"
        )
    elif d < 0:
        questions.append(
            f"{elem} (Spannung −{mag} Pkt., BaZi dominiert): "
            f"Deine innere {elem}-Stärke übersteigt das, was der Himmel deiner Geburt anbot. "
            f"Wo sucht diese Kraft einen Ausdruck, den sie noch nicht gefunden hat?"
        )
    else:
        questions.append(
            f"{elem} (ausgeglichen, aber hohe Präsenz): "
            f"Was macht diese Achse trotz des Gleichgewichts zu einem aktiven Thema?"
        )

    # Sheng-Frage (Interpretation: prev/next aus fixer Ordnung — kein Messsignal)
    if use_sheng:
        prev_e = _PREV[elem]
        next_e = _NEXT[elem]
        if d > 0:
            questions.append(
                f"[Sheng-Frage] Würde eine stärkere Verwurzelung in {prev_e} helfen, "
                f"damit der {elem}-Impuls von außen tragfähig wird "
                f"und in {next_e} weiterfließen kann?"
            )
        elif d < 0:
            questions.append(
                f"[Sheng-Frage] Würde ein bewusster Schritt Richtung {next_e} helfen, "
                f"damit deine innere {elem}-Stärke sichtbarer wird, "
                f"ohne sich zu überdehnen?"
            )
        else:
            questions.append(
                f"[Sheng-Frage] Welche kleine Bewegung von {elem} nach {next_e} "
                f"wäre im Moment stimmig?"
            )

    return questions


def question_development(
    elem: str,
    west_val: float,
    bazi_val: float,
    use_sheng: bool = True,
) -> List[str]:
    """Erzeugt Leitfragen für ein DEVELOPMENT-Element.

    Args:
        elem:      Element-Name.
        west_val:  Normierter westlicher Wert für dieses Element.
        bazi_val:  Normierter BaZi-Wert.
        use_sheng: Falls True, wird eine Sheng-Zusatzfrage angehängt.

    Returns:
        Liste mit 1–2 Fragen.
    """
    w_idx = round(west_val * 100, 1)
    b_idx = round(bazi_val * 100, 1)
    questions: List[str] = []

    questions.append(
        f"{elem} (Entwicklungsfeld, West {w_idx} / BaZi {b_idx} Pkt.): "
        f"Dieses Element ist in beiden Systemen schwach vertreten — "
        f"kein Mangel, sondern ein unentwickelter Raum. "
        f"Welche kleine, risikoarme Praxis würde diese Achse stärken?"
    )

    if use_sheng:
        prev_e = _PREV[elem]
        questions.append(
            f"[Sheng-Frage] Würde ein Mikro-Schritt im Vorgänger {prev_e} "
            f"das {elem}-Feld indirekt nähren — ohne Druck auf sofortige Leistung?"
        )

    return questions


def build_leitfragen(
    result: ZoneResult,
    use_sheng: bool = True,
) -> Dict[str, Dict[str, List[str]]]:
    """Erzeugt vollständigen Fragensatz für TENSION- und DEVELOPMENT-Elemente.

    STRENGTH-Elemente erhalten keine Leitfragen (sie laufen von selbst).
    NEUTRAL-Elemente werden nicht angezeigt.

    Args:
        result:    ZoneResult aus classify_zones().
        use_sheng: Falls True, Sheng-Zusatzfragen einschließen.

    Returns:
        {"tension": {elem: [fragen]}, "development": {elem: [fragen]}}
    """
    output: Dict[str, Dict[str, List[str]]] = {
        "tension":     {},
        "development": {},
    }
    for elem in WUXING_ORDER:
        zone = result.zones[elem]
        if zone == "TENSION":
            output["tension"][elem] = question_tension(
                elem, result.diffs[elem], use_sheng=use_sheng
            )
        elif zone == "DEVELOPMENT":
            output["development"][elem] = question_development(
                elem, result.west[elem], result.bazi[elem], use_sheng=use_sheng
            )
    return output


# ── Report-Template ───────────────────────────────────────────────────────────

def format_report_b(
    harmony: float,
    harmony_label: str,
    result: ZoneResult,
    use_sheng: bool = True,
) -> str:
    """Rendert den Logik-B-Report als lesbaren Text.

    Hinweis: Werte werden als 'Indexpunkte (L2-Koordinaten × 100)' ausgegeben,
    nicht als additive Prozentanteile. Eine Sachse zeigt den relativen Vektor-
    anteil im normalisierten Raum, nicht den prozentualen Anteil an einer Summe.

    Args:
        harmony:       Harmony Index (0–1).
        harmony_label: Interpretationslabel (aus interpret_harmony()).
        result:        ZoneResult aus classify_zones().
        use_sheng:     Sheng-Leitfragen einschließen.

    Returns:
        Mehrzeiliger Report-String.
    """
    leitfragen = build_leitfragen(result, use_sheng=use_sheng)
    lines: List[str] = []

    lines += [
        "═" * 55,
        "FUSION ANALYSE — DIAGNOSTISCHE KARTE (Logik B)",
        "═" * 55,
        "",
        f"HARMONY INDEX: {harmony * 100:.2f} Indexpunkte ({harmony_label})",
        "(Cosinus-Ähnlichkeit der normierten Elementarvektoren)",
        "",
    ]

    # Stärkefelder
    strength = result.strength_elements()
    if strength:
        lines.append("─" * 55)
        lines.append("STÄRKEFELDER  (beidseitig > 20 Pkt., Δ ≤ 15 Pkt.)")
        lines.append("─" * 55)
        for e in strength:
            w = round(result.west[e] * 100, 1)
            b = round(result.bazi[e] * 100, 1)
            lines.append(f"● {e:<8}  West {w:5.1f}  BaZi {b:5.1f}  Δ{round(result.diffs[e]*100,1):+.1f}")
        lines.append("")

    # Spannungsfelder
    tension = result.tension_elements()
    if tension:
        lines.append("─" * 55)
        lines.append("SPANNUNGSFELDER  (|Δ| > 15 Pkt., priorisiert)")
        lines.append("─" * 55)
        for e in tension:
            w = round(result.west[e] * 100, 1)
            b = round(result.bazi[e] * 100, 1)
            d = result.diffs[e]
            lbl = _direction_label(d)
            lines.append(
                f"▲ {e:<8}  West {w:5.1f}  BaZi {b:5.1f}  "
                f"Δ{round(d*100,1):+.1f}  [{lbl}]"
            )
        lines.append("")

    # Entwicklungsfelder
    development = result.development_elements()
    if development:
        lines.append("─" * 55)
        lines.append("ENTWICKLUNGSFELDER  (beidseitig < 15 Pkt.)")
        lines.append("─" * 55)
        for e in development:
            w = round(result.west[e] * 100, 1)
            b = round(result.bazi[e] * 100, 1)
            lines.append(f"○ {e:<8}  West {w:5.1f}  BaZi {b:5.1f}")
        lines.append("")

    # Leitfragen
    if leitfragen["tension"] or leitfragen["development"]:
        lines.append("─" * 55)
        lines.append("LEITFRAGEN")
        lines.append("─" * 55)
        for section_key in ("tension", "development"):
            for elem, qs in leitfragen[section_key].items():
                for q in qs:
                    lines.append(f"  {q}")
                lines.append("")

    lines.append("═" * 55)
    lines.append(
        "Indexpunkte = L2-Koordinaten × 100. Nicht additiv aufsummieren."
    )
    return "\n".join(lines)
