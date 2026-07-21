"""
research/dataset_generator.py — Synthetischer Datensatz-Generator.

Erzeugt große Mengen synthetischer BaZi+Western-Charts für statistische
Analysen. Alle Geburten sind gleichmäßig über alle Jieqi-Phasen verteilt
(stratified sampling), um Stichproben-Bias zu vermeiden.

Wichtig: Die generierten Daten sind synthetisch (zufällige Stämme/Zweige/
Planetenpositionen). Sie dienen ausschließlich der Validierung, ob das
Pipeline-System überhaupt stabile Muster erzeugen KANN — nicht zur
Beschreibung realer astrologischer Muster.
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from ..phases.jieqi_phase import JieqiPhase, classify_jieqi_phase
from ..phases.lunar_phase import LunarPhase, classify_lunar_phase
from ..wuxing.analysis import (
    calculate_harmony_index,
    calculate_wuxing_from_bazi,
    calculate_wuxing_vector_from_planets,
)
from ..wuxing.calibration import CalibrationResult, calibrate_harmony
from ..wuxing.constants import WUXING_ORDER
from ..wuxing.zones import classify_zones

# ── Domänenkonstanten ─────────────────────────────────────────────────────────

_STEMS = ["Jia","Yi","Bing","Ding","Wu","Ji","Geng","Xin","Ren","Gui"]
_BRANCHES = ["Zi","Chou","Yin","Mao","Chen","Si","Wu","Wei","Shen","You","Xu","Hai"]
_PLANETS = ["Sun","Moon","Mercury","Venus","Mars","Jupiter","Saturn",
            "Uranus","Neptune","Pluto","Chiron"]


@dataclass
class SyntheticBirthChart:
    """Ein einzelner synthetischer Geburts-Datensatz mit allen Features."""

    # Eingabedaten
    birth_dt:         datetime
    bazi_pillars:     dict
    western_bodies:   dict
    solar_longitude:  float   # Sonnenlänge [0, 360°) — für Jieqi
    moon_sun_angle:   float   # Mond-Sonne-Winkel [0, 360°) — für Mondphase

    # Berechnete Features
    h_raw:            float
    h_calibrated:     float
    calibration:      CalibrationResult
    western_vector:   dict   # normiert
    bazi_vector:      dict   # normiert
    diffs:            dict   # d_i pro Element
    resonance:        dict   # r_i = west_i * bazi_i (Resonanzachse)
    dominant_west:    str    # Element mit max west_i
    dominant_bazi:    str    # Element mit max bazi_i
    resonance_axis:   str    # Element mit max r_i
    zones:            dict   # ZoneResult.zones

    # Externe Phasen
    jieqi:            JieqiPhase
    lunar:            LunarPhase

    # Abgeleitete Indikatoren
    n_tension:        int    # Anzahl Tension-Elemente
    n_strength:       int    # Anzahl Strength-Elemente
    n_development:    int    # Anzahl Development-Elemente
    quality:          str    # "ok" | "sparse" | "degenerate"


def _random_pillars(rng: random.Random) -> dict:
    """Zufällige Vier Pfeiler."""
    return {
        p: {"stem": rng.choice(_STEMS), "branch": rng.choice(_BRANCHES)}
        for p in ("year", "month", "day", "hour")
    }


def _random_bodies(rng: random.Random, n_planets: int = 7) -> dict:
    """Zufällige Planetenpositionen."""
    planets = rng.sample(_PLANETS, min(n_planets, len(_PLANETS)))
    return {
        pl: {
            "longitude": rng.uniform(0.0, 360.0),
            "is_retrograde": rng.random() < 0.18,  # ~18% retrograd (empirisch)
        }
        for pl in planets
    }


def _compute_chart(pillars: dict, bodies: dict) -> dict:
    """Berechnet alle Fusion-Features für ein Chart."""
    v_west = calculate_wuxing_vector_from_planets(bodies)
    v_bazi = calculate_wuxing_from_bazi(pillars)
    harmony = calculate_harmony_index(v_west, v_bazi)
    h_raw = harmony["harmony_index"]

    w_norm = v_west.normalize()
    b_norm = v_bazi.normalize()

    west_d = w_norm.to_dict()
    bazi_d = b_norm.to_dict()
    diffs = {e: round(west_d[e] - bazi_d[e], 6) for e in WUXING_ORDER}
    resonance = {e: round(west_d[e] * bazi_d[e], 6) for e in WUXING_ORDER}

    dominant_west = max(west_d, key=lambda k: west_d[k])
    dominant_bazi = max(bazi_d, key=lambda k: bazi_d[k])
    resonance_axis = max(resonance, key=lambda k: resonance[k])

    zone_result = classify_zones(west_d, bazi_d)
    cal = calibrate_harmony(h_raw, bodies, pillars, v_west, v_bazi)

    return {
        "h_raw": h_raw,
        "h_calibrated": cal.h_calibrated,
        "calibration": cal,
        "western_vector": west_d,
        "bazi_vector": bazi_d,
        "diffs": diffs,
        "resonance": resonance,
        "dominant_west": dominant_west,
        "dominant_bazi": dominant_bazi,
        "resonance_axis": resonance_axis,
        "zones": zone_result.zones,
        "n_tension": len(zone_result.tension_elements()),
        "n_strength": len(zone_result.strength_elements()),
        "n_development": len(zone_result.development_elements()),
        "quality": cal.quality,
    }


def generate_synthetic_dataset(
    n_total: int = 1000,
    seed: int = 42,
    n_planets: int = 7,
    stratify_by_jieqi: bool = True,
) -> list[SyntheticBirthChart]:
    """Erzeugt einen synthetischen Datensatz.

    Args:
        n_total:            Gesamtzahl der Charts.
        seed:               Zufallsseed für Reproduzierbarkeit.
        n_planets:          Anzahl Planeten pro Chart.
        stratify_by_jieqi:  Falls True, werden n_total/24 Charts pro
                            Jieqi-Phase erzeugt (balanced sampling).
                            Falls False, rein zufällig.

    Returns:
        Liste von SyntheticBirthChart-Objekten.
    """
    rng = random.Random(seed)
    charts: list[SyntheticBirthChart] = []

    if stratify_by_jieqi:
        per_phase = max(1, n_total // 24)
        solar_lons = [
            (phase_idx * 15.0 + rng.uniform(0.0, 15.0)) % 360.0
            for phase_idx in range(24)
            for _ in range(per_phase)
        ]
        # Auffüllen auf n_total
        while len(solar_lons) < n_total:
            solar_lons.append(rng.uniform(0.0, 360.0))
        solar_lons = solar_lons[:n_total]
    else:
        solar_lons = [rng.uniform(0.0, 360.0) for _ in range(n_total)]

    # Referenzdatum: 2000-01-01 (irrelevant für statische Approximation)
    base_dt = datetime(2000, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

    for i, solar_lon in enumerate(solar_lons):
        pillars = _random_pillars(rng)
        bodies  = _random_bodies(rng, n_planets)
        moon_angle = rng.uniform(0.0, 360.0)  # zufällig, unabhängig von Sonne

        features = _compute_chart(pillars, bodies)

        birth_dt = base_dt + timedelta(days=i)
        jieqi = classify_jieqi_phase(solar_longitude=solar_lon)
        lunar = classify_lunar_phase(moon_sun_angle=moon_angle)

        charts.append(SyntheticBirthChart(
            birth_dt=birth_dt,
            bazi_pillars=pillars,
            western_bodies=bodies,
            solar_longitude=solar_lon,
            moon_sun_angle=moon_angle,
            jieqi=jieqi,
            lunar=lunar,
            **features,
        ))

    return charts
