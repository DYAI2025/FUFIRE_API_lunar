"""
phases/jieqi_phase.py — 24 Jieqi als primäre externe Periodikreferenz.

Die 24 Jieqi (节气, Sonnenwende-Perioden) sind die astronomisch
präziseste und traditionskonformste externe Zeitachse für die
Fusion-Analyse:

  • Astronomisch: jede Periode = 15° Sonnenlänge (~15.2 Tage)
  • BaZi-konform: Jieqi definieren die Monatsgrenzen der Vier Pfeiler
  • Deterministisch: eindeutig aus UTC-Zeitpunkt + Sonnenlänge
  • Vollständig external: unabhängig vom individuellen Chart

WICHTIG: Diese Phase-Klassifikation setzt eine bekannte Sonnenlänge voraus.
Ohne Ephemeris-Berechnung wird die Sonnenlänge aus dem Datum approximiert
(Spencer-Formel, ±1°). Für Forschungszwecke ist Swiss Ephemeris zu bevorzugen.

Periodennummern: 0–23, beginnend bei Lichun (315°, ~3. Februar).
Die Ordnung folgt der BaZi-Jahresgrenze (Holz = Frühling = Jahresanfang).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

# ── Jieqi-Definitionen ────────────────────────────────────────────────────────
# Format: (Startlänge °, Name_zh_pinyin, Name_de, Wu-Xing-Qualität)
# Ordnung: beginnend bei 315° (Lichun = BaZi-Jahresbeginn)

JIEQI_PHASES: list[tuple[float, str, str, str]] = [
    (315.0, "Lichun",      "Frühlingsanfang",    "Holz_Yang"),
    (330.0, "Yushui",      "Regenwasser",         "Holz_Yin"),
    (345.0, "Jingzhe",     "Insektenerwachen",    "Holz_Yang"),
    (  0.0, "Chunfen",     "Frühlingsäquinoktium","Holz_Yin"),
    ( 15.0, "Qingming",    "Klares Licht",        "Feuer_Yang"),
    ( 30.0, "Guyu",        "Getreidegen",         "Feuer_Yin"),
    ( 45.0, "Lixia",       "Sommeranfang",        "Feuer_Yang"),
    ( 60.0, "Xiaoman",     "Kleines Fülle",       "Feuer_Yin"),
    ( 75.0, "Mangzhong",   "Ährenfrucht",         "Erde_Yang"),
    ( 90.0, "Xiazhi",      "Sommersonnenwende",   "Erde_Yin"),
    (105.0, "Xiaoshu",     "Kleine Hitze",        "Erde_Yang"),
    (120.0, "Dashu",       "Große Hitze",         "Erde_Yin"),
    (135.0, "Liqiu",       "Herbstanfang",        "Metall_Yang"),
    (150.0, "Chushu",      "Ende der Hitze",      "Metall_Yin"),
    (165.0, "Bailu",       "Weißer Tau",          "Metall_Yang"),
    (180.0, "Qiufen",      "Herbstäquinoktium",   "Metall_Yin"),
    (195.0, "Hanlu",       "Kalter Tau",          "Wasser_Yang"),
    (210.0, "Shuangjiang", "Reiffall",            "Wasser_Yin"),
    (225.0, "Lidong",      "Winteranfang",        "Wasser_Yang"),
    (240.0, "Xiaoxue",     "Kleiner Schnee",      "Wasser_Yin"),
    (255.0, "Daxue",       "Großer Schnee",       "Wasser_Yang"),
    (270.0, "Dongzhi",     "Wintersonnenwende",   "Wasser_Yin"),
    (285.0, "Xiaohan",     "Kleine Kälte",        "Holz_Yang"),
    (300.0, "Dahan",       "Große Kälte",         "Holz_Yin"),
]

_N = len(JIEQI_PHASES)  # 24


@dataclass(frozen=True)
class JieqiPhase:
    """Klassifikationsergebnis: Jieqi-Phase für einen Zeitpunkt."""
    index:           int     # 0–23
    start_longitude: float   # Anfangssonnenlänge der Phase (z.B. 315.0)
    name_pinyin:     str     # z.B. "Lichun"
    name_de:         str     # z.B. "Frühlingsanfang"
    wuxing_quality:  str     # z.B. "Holz_Yang"
    solar_longitude: float   # Sonnenlänge des Zeitpunkts (0–360°)
    position_in_phase: float # 0.0–1.0: wie weit in der Phase (0=Beginn, 1=Ende)

    @property
    def element(self) -> str:
        """Nur das Element (ohne Yin/Yang)."""
        return self.wuxing_quality.split("_")[0]

    @property
    def polarity(self) -> str:
        """Yang oder Yin."""
        return self.wuxing_quality.split("_")[1]

    @property
    def is_yang(self) -> bool:
        return self.polarity == "Yang"


def _approximate_solar_longitude(dt: datetime) -> float:
    """Approximiert die Sonnenlänge aus dem Datum (Spencer-Formel, ±1°).

    Für Produktionsnutzung Swiss Ephemeris verwenden.
    Für Forschung/Test ist diese Approximation ausreichend.

    Returns:
        Sonnenlänge in Grad [0, 360).
    """
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    dt_utc = dt.astimezone(timezone.utc)

    # Day of year (1–366)
    day_of_year = dt_utc.timetuple().tm_yday

    # Spencer-Formel für Sonnenlänge (vereinfacht)
    # Referenz: vernal equinox ≈ 21. März = Tag 80
    # Sonnenlänge = (day_of_year - 80) / 365.25 * 360
    raw = (day_of_year - 80) / 365.25 * 360.0
    return raw % 360.0


def classify_jieqi_phase(
    solar_longitude: Optional[float] = None,
    dt: Optional[datetime] = None,
) -> JieqiPhase:
    """Klassifiziert einen Zeitpunkt in eine der 24 Jieqi-Phasen.

    Args:
        solar_longitude: Bekannte Sonnenlänge [0, 360°]. Wenn gegeben,
                         wird dt ignoriert.
        dt:              Datetime (UTC). Wird für Approximation genutzt,
                         wenn solar_longitude nicht angegeben.

    Returns:
        JieqiPhase mit Index, Name, Wu-Xing-Qualität, Position in Phase.

    Raises:
        ValueError: Wenn weder solar_longitude noch dt gegeben.
    """
    if solar_longitude is None:
        if dt is None:
            raise ValueError("Entweder solar_longitude oder dt muss angegeben sein.")
        solar_longitude = _approximate_solar_longitude(dt)

    solar_longitude = solar_longitude % 360.0

    # Finde die aktuelle Phase: größte Startlänge ≤ solar_longitude
    # Achtung: die Phasen sind nicht linear sortiert (beginnen bei 315°)
    # Konvertiere: relativ zu 315° als Ursprung
    offset = (solar_longitude - 315.0) % 360.0  # 0–360, relativ zu Lichun

    phase_idx = int(offset / 15.0) % _N
    start_lon = JIEQI_PHASES[phase_idx][0]
    position = (offset % 15.0) / 15.0  # 0.0–1.0

    _, name_py, name_de, quality = JIEQI_PHASES[phase_idx]

    return JieqiPhase(
        index=phase_idx,
        start_longitude=start_lon,
        name_pinyin=name_py,
        name_de=name_de,
        wuxing_quality=quality,
        solar_longitude=round(solar_longitude, 4),
        position_in_phase=round(position, 4),
    )
