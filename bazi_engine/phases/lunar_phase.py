"""
phases/lunar_phase.py — 8 Mondphasen als sekundäre externe Periodikreferenz.

Die 8 Mondphasen werden über den Mond-Sonne-Winkel (Elongation) definiert:
  0°–45°:   Neumond (0° = exakter Neumond)
  45°–90°:  Zunehmend I (Sichel)
  90°–135°: Erstes Viertel
  135°–180°: Zunehmend II (Gibbös)
  180°–225°: Vollmond (180° = exakter Vollmond)
  225°–270°: Abnehmend I (Gibbös)
  270°–315°: Letztes Viertel
  315°–360°: Abnehmend II (Sichel)

Die Mondphase ist astronomisch präzise und realweltlich beobachtbar.
Sie hat eine Periode von ~29.5 Tagen und ist vollständig extern —
unabhängig vom individuellen Chart.

HINWEIS: Ohne Ephemeris-Daten wird der Mond-Sonne-Winkel approximiert.
Approximationsgenauigkeit: ±3–5° (~6–10 Stunden). Für Forschungszwecke
mit Mondphasen-Granularität ist Swiss Ephemeris zu bevorzugen.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

# ── Mondphasen-Definitionen ───────────────────────────────────────────────────
# Format: (Startwinkel °, Name_de, Energie-Qualität)

LUNAR_PHASES: list[tuple[float, str, str]] = [
    (  0.0, "Neumond",           "Impuls"),
    ( 45.0, "Zunehmend I",       "Aufbau"),
    ( 90.0, "Erstes Viertel",    "Entscheidung"),
    (135.0, "Zunehmend II",      "Verdichtung"),
    (180.0, "Vollmond",          "Manifestation"),
    (225.0, "Abnehmend I",       "Integration"),
    (270.0, "Letztes Viertel",   "Loslassen"),
    (315.0, "Abnehmend II",      "Ruhe"),
]

_N = len(LUNAR_PHASES)  # 8


@dataclass(frozen=True)
class LunarPhase:
    """Klassifikationsergebnis: Mondphase für einen Zeitpunkt."""
    index:               int    # 0–7
    start_angle:         float  # Startwinkel der Phase (0, 45, 90, ...)
    name_de:             str    # z.B. "Vollmond"
    energy_quality:      str    # z.B. "Manifestation"
    moon_sun_angle:      float  # Mond-Sonne-Winkel [0, 360°)
    position_in_phase:   float  # 0.0–1.0

    @property
    def is_waxing(self) -> bool:
        """Zunehmend (0°–180°)."""
        return self.moon_sun_angle < 180.0

    @property
    def is_full(self) -> bool:
        """Nähe zum Vollmond (150°–210°)."""
        return 150.0 <= self.moon_sun_angle <= 210.0

    @property
    def is_new(self) -> bool:
        """Nähe zum Neumond (< 30° oder > 330°)."""
        a = self.moon_sun_angle
        return a < 30.0 or a > 330.0


def _approximate_moon_sun_angle(dt: datetime) -> float:
    """Approximiert den Mond-Sonne-Winkel (Elongation) aus dem Datum.

    Methode: Lineare Näherung basierend auf einem bekannten Neumond-Referenzpunkt.
    Referenz: 2024-01-11 11:57 UTC (Neumond)
    Mondperiode: 29.530589 Tage

    Genauigkeit: ±5° (±10 Stunden). Ausreichend für Phasenzuordnung,
    aber nicht für präzise astronomische Berechnungen.
    """
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    dt_utc = dt.astimezone(timezone.utc)

    # Referenz-Neumond: 2024-01-11T11:57:00 UTC
    NEW_MOON_REF = datetime(2024, 1, 11, 11, 57, 0, tzinfo=timezone.utc)
    LUNAR_PERIOD_DAYS = 29.530589

    delta_days = (dt_utc - NEW_MOON_REF).total_seconds() / 86400.0
    phase_fraction = (delta_days % LUNAR_PERIOD_DAYS) / LUNAR_PERIOD_DAYS
    return (phase_fraction * 360.0) % 360.0


def classify_lunar_phase(
    moon_sun_angle: Optional[float] = None,
    dt: Optional[datetime] = None,
) -> LunarPhase:
    """Klassifiziert einen Zeitpunkt in eine der 8 Mondphasen.

    Args:
        moon_sun_angle: Bekannter Mond-Sonne-Winkel [0, 360°).
                        Wenn gegeben, wird dt ignoriert.
        dt:             Datetime (UTC). Für Approximation.

    Returns:
        LunarPhase mit Index, Name, Energie-Qualität, Position.

    Raises:
        ValueError: Wenn weder moon_sun_angle noch dt gegeben.
    """
    if moon_sun_angle is None:
        if dt is None:
            raise ValueError("Entweder moon_sun_angle oder dt muss angegeben sein.")
        moon_sun_angle = _approximate_moon_sun_angle(dt)

    moon_sun_angle = moon_sun_angle % 360.0
    phase_idx = int(moon_sun_angle / 45.0) % _N
    position = (moon_sun_angle % 45.0) / 45.0

    start_angle, name_de, energy = LUNAR_PHASES[phase_idx]

    return LunarPhase(
        index=phase_idx,
        start_angle=start_angle,
        name_de=name_de,
        energy_quality=energy,
        moon_sun_angle=round(moon_sun_angle, 4),
        position_in_phase=round(position, 4),
    )
