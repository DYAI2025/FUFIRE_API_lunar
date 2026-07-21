"""BaZi daily horoscope generator — solar-term-based, deterministic."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from ..bazi import pillar_from_index60, sexagenary_day_index_from_date
from ..constants import BRANCHES, STEMS
from ..ephemeris import SwissEphBackend, datetime_utc_to_jd_ut
from .daily_templates import (
    CAUTION_VARIANTS_DE,
    OPPORTUNITY_VARIANTS_DE,
    RELATION_SUMMARY_VARIANTS_DE,
    get_jieqi_flavor,
    get_weekday_modifier,
    select_variant,
)

_log = logging.getLogger(__name__)

_STEM_ELEMENT = {
    "Jia": "Holz", "Yi": "Holz",
    "Bing": "Feuer", "Ding": "Feuer",
    "Wu": "Erde", "Ji": "Erde",
    "Geng": "Metall", "Xin": "Metall",
    "Ren": "Wasser", "Gui": "Wasser",
}

_SHENG_CYCLE = {"Holz": "Feuer", "Feuer": "Erde", "Erde": "Metall", "Metall": "Wasser", "Wasser": "Holz"}
_KE_CYCLE = {"Holz": "Erde", "Feuer": "Metall", "Erde": "Wasser", "Metall": "Holz", "Wasser": "Feuer"}


def _determine_relation(natal_element: str, daily_element: str) -> str:
    if natal_element == daily_element:
        return "companion"
    if _SHENG_CYCLE.get(natal_element) == daily_element:
        return "output"
    if _SHENG_CYCLE.get(daily_element) == natal_element:
        return "resource"
    if _KE_CYCLE.get(natal_element) == daily_element:
        return "wealth"
    if _KE_CYCLE.get(daily_element) == natal_element:
        return "power"
    return "neutral"


_RELATION_THEMES_DE = {
    "companion": ["Gleichklang", "Staerkung", "Vertrauen"],
    "resource": ["Unterstuetzung", "Naehrung", "Rueckhalt"],
    "output": ["Ausdruck", "Produktivitaet", "Sichtbarkeit"],
    "power": ["Kontrolle", "Disziplin", "Fokus"],
    "wealth": ["Ressourcen", "Chancen", "Taktung"],
    "neutral": ["Balance", "Beobachtung", "Ruhe"],
}


# All 24 solar terms (Jieqi) — indexed by solar longitude / 15
# Index 0 = 0° (Chunfen), ..., Index 21 = 315° (LiChun), etc.
_JIEQI_24_NAMES = [
    "Chunfen",    # 0°   — Frühlings-Tagundnachtgleiche
    "Qingming",   # 15°  — Reine Klarheit
    "Guyu",       # 30°  — Getreideregen
    "Lixia",      # 45°  — Sommeranfang
    "Xiaoman",    # 60°  — Kleine Fülle
    "Mangzhong",  # 75°  — Grannen und Saat
    "Xiazhi",     # 90°  — Sommersonnenwende
    "Xiaoshu",    # 105° — Kleine Hitze
    "Dashu",      # 120° — Große Hitze
    "Liqiu",      # 135° — Herbstanfang
    "Chushu",     # 150° — Ende der Hitze
    "Bailu",      # 165° — Weißer Tau
    "Qiufen",     # 180° — Herbst-Tagundnachtgleiche
    "Hanlu",      # 195° — Kalter Tau
    "Shuangjiang",# 210° — Frost fällt
    "Lidong",     # 225° — Winteranfang
    "Xiaoxue",    # 240° — Kleiner Schnee
    "Daxue",      # 255° — Großer Schnee
    "Dongzhi",    # 270° — Wintersonnenwende
    "Xiaohan",    # 285° — Kleine Kälte
    "Dahan",      # 300° — Große Kälte
    "Lichun",     # 315° — Frühlingsanfang
    "Yushui",     # 330° — Regenwasser
    "Jingzhe",    # 345° — Erwachen der Insekten
]


def _determine_jieqi_from_ephemeris(
    target_date: str,
    ephe_path: Optional[str] = None,
) -> str:
    """Determine active solar term using Swiss Ephemeris solar longitude.

    Finds the sun's ecliptic longitude at noon UTC on the target date
    and maps it to the preceding solar term boundary (every 15°).
    """
    try:
        dt = datetime.strptime(target_date, "%Y-%m-%d").replace(
            hour=12, tzinfo=timezone.utc
        )
        backend = SwissEphBackend(ephe_path=ephe_path)
        jd_ut = datetime_utc_to_jd_ut(dt)
        sun_lon = backend.sun_lon_deg_ut(jd_ut)

        # Solar term index = floor(sun_longitude / 15)
        # Each 15° segment corresponds to one of 24 solar terms
        term_index = int(sun_lon // 15) % 24
        return _JIEQI_24_NAMES[term_index]
    except Exception:
        _log.warning(
            "Ephemeris-based Jieqi lookup failed for %s, using fallback",
            target_date,
            exc_info=True,
        )
        return _determine_jieqi_fallback(target_date)


def _determine_jieqi_fallback(target_date: str) -> str:
    """Fallback Jieqi determination when ephemeris is unavailable.

    Uses approximate solar longitude from day-of-year:
    sun_lon ≈ (day_of_year - 80) × (360/365.25) mod 360
    """
    dt = datetime.strptime(target_date, "%Y-%m-%d")
    doy = dt.timetuple().tm_yday
    # Approximate solar longitude (Chunfen ≈ day 80 = 0°)
    approx_lon = ((doy - 80) * (360.0 / 365.25)) % 360
    term_index = int(approx_lon // 15) % 24
    return _JIEQI_24_NAMES[term_index]


def generate_eastern_daily(
    day_master: str,
    target_date: str,
    tz: str = "Europe/Berlin",
    locale: str = "de-DE",
) -> Dict[str, Any]:
    """Generate structured BaZi daily horoscope."""
    dt = datetime.strptime(target_date, "%Y-%m-%d")

    # Compute daily pillar using sexagenary cycle
    day_idx60 = sexagenary_day_index_from_date(dt.year, dt.month, dt.day)
    day_pillar = pillar_from_index60(day_idx60)
    daily_stem = STEMS[day_pillar.stem_index]
    daily_branch = BRANCHES[day_pillar.branch_index]

    natal_element = _STEM_ELEMENT.get(day_master, "Erde")
    daily_element = _STEM_ELEMENT.get(daily_stem, "Erde")
    relation = _determine_relation(natal_element, daily_element)

    # Precise Jieqi from Swiss Ephemeris (with graceful fallback)
    jieqi_name = _determine_jieqi_from_ephemeris(target_date)

    themes = _RELATION_THEMES_DE.get(relation, ["Energie"])

    # Select variant templates based on (relation × day-of-year)
    summary_variants = RELATION_SUMMARY_VARIANTS_DE[relation]
    summary = select_variant(summary_variants, target_date).format(dm=day_master, element=daily_element)
    summary += f" Solarterm: {jieqi_name}."

    # Structured sub-fields for downstream consumers (not concatenated into summary)
    jieqi_note = get_jieqi_flavor(jieqi_name)
    weekday_name, weekday_planet, weekday_energy = get_weekday_modifier(target_date)
    weekday_note = f"{weekday_name} ({weekday_planet}): {weekday_energy}"

    caution_variants = CAUTION_VARIANTS_DE[relation]
    caution = select_variant(caution_variants, target_date).format(
        relation=relation, element=daily_element,
    )

    opp_variants = OPPORTUNITY_VARIANTS_DE[relation]
    opportunity = select_variant(opp_variants, target_date).format(
        theme=themes[0], element=daily_element,
    )

    return {
        "summary": summary,
        "themes": themes,
        "caution": caution,
        "opportunity": opportunity,
        "jieqi_note": jieqi_note,
        "weekday_note": weekday_note,
        "evidence": {
            "day_master": day_master,
            "daily_pillar": {"stem": daily_stem, "branch": daily_branch},
            "relation_to_day_master": relation,
            "jieqi": jieqi_name,
            "weekday": weekday_name,
        },
    }
