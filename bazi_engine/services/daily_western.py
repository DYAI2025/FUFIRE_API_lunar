"""Western daily horoscope generator — template-based, deterministic."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List

from ..transit import ZODIAC_SIGNS, compute_transit_now
from .daily_templates import get_weekday_modifier

_SECTOR_THEMES_DE = {
    0: ["Identitaet", "Auftreten", "Neubeginn"],
    1: ["Ressourcen", "Werte", "Sicherheit"],
    2: ["Kommunikation", "Austausch", "Lernen"],
    3: ["Familie", "Geborgenheit", "Herkunft"],
    4: ["Ausdruck", "Kreativitaet", "Freude"],
    5: ["Alltag", "Routine", "Gesundheit"],
    6: ["Beziehung", "Partnerschaft", "Harmonie"],
    7: ["Tiefe", "Wandlung", "Macht"],
    8: ["Weite", "Sinn", "Horizonterweiterung"],
    9: ["Karriere", "Verantwortung", "Ziel"],
    10: ["Gemeinschaft", "Zukunft", "Ideale"],
    11: ["Innenwelt", "Intuition", "Loslassen"],
}


def generate_western_daily(
    sun_sign_idx: int,
    moon_sign_idx: int,
    asc_sign_idx: int,
    soulprint_sectors: List[float],
    target_date: str,
    tz: str,
    lat: float,
    lon: float,
    locale: str = "de-DE",
) -> Dict[str, Any]:
    """Generate structured western daily horoscope."""
    dt = datetime.strptime(target_date, "%Y-%m-%d").replace(hour=12, tzinfo=timezone.utc)
    transit_data = compute_transit_now(dt)
    transit_sectors = transit_data["sector_intensity"]

    combined = [t * s for t, s in zip(transit_sectors, soulprint_sectors)]
    active_indices = sorted(range(12), key=lambda i: combined[i], reverse=True)[:2]

    themes = []
    for idx in active_indices:
        themes.extend(_SECTOR_THEMES_DE.get(idx, ["Energie"])[:1])

    sun_sign = ZODIAC_SIGNS[sun_sign_idx % 12]
    weekday_name, weekday_planet, weekday_energy = get_weekday_modifier(target_date)

    summary = (
        f"Fuer dich als {sun_sign.title()} stehen heute {', '.join(themes)} im Fokus. "
        f"Die Planetenkonstellation aktiviert deine Sektoren {active_indices[0]+1} und {active_indices[1]+1}."
    )
    weekday_note = f"{weekday_name} ({weekday_planet}): {weekday_energy}"
    caution = f"Achte in Sektor {active_indices[1]+1} auf Ueberanstrengung -- hier liegt heute Spannung."
    opportunity = f"Sektor {active_indices[0]+1} bietet dir heute besonderes Potenzial. Nutze die Energie aktiv."

    return {
        "summary": summary,
        "themes": themes,
        "caution": caution,
        "opportunity": opportunity,
        "weekday_note": weekday_note,
        "evidence": {
            "transit_sectors": active_indices,
            "natal_focus": ["sun", "ascendant"],
            "weekday": weekday_name,
        },
    }
