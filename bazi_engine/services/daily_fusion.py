"""Fusion daily reading — independent synthesis of western + eastern."""
from __future__ import annotations

from typing import Any, Dict


def _find_shared_themes(w_themes: list, e_themes: list) -> list:
    shared = list(set(w_themes) & set(e_themes))
    if shared:
        return shared
    _AFFINITIES = {
        "Ausdruck": ["Sichtbarkeit", "Produktivitaet"],
        "Kreativitaet": ["Ausdruck", "Sichtbarkeit"],
        "Fokus": ["Disziplin", "Kontrolle"],
        "Kommunikation": ["Austausch", "Gleichklang"],
        "Gleichklang": ["Harmonie", "Staerkung"],
        "Ressourcen": ["Chancen", "Taktung"],
        "Identitaet": ["Auftreten", "Neubeginn"],
        "Beziehung": ["Partnerschaft", "Harmonie"],
    }
    for wt in w_themes:
        for et in e_themes:
            if et in _AFFINITIES.get(wt, []) or wt in _AFFINITIES.get(et, []):
                return [f"{wt} + {et}"]
    return [w_themes[0] if w_themes else "Energie"]


def generate_fusion_daily(
    western: Dict[str, Any],
    eastern: Dict[str, Any],
    locale: str = "de-DE",
) -> Dict[str, Any]:
    """Synthesize western + eastern into independent fusion reading."""
    w_themes = western.get("themes", [])
    e_themes = eastern.get("themes", [])
    shared = _find_shared_themes(w_themes, e_themes)
    tension_themes = list(set(w_themes + e_themes) - set(shared))

    shared_str = ", ".join(shared) if shared else "Balancierung"
    tension_str = ", ".join(tension_themes[:2]) if tension_themes else "keine offensichtliche Spannung"

    relation = eastern.get("evidence", {}).get("relation_to_day_master", "neutral")
    day_master = eastern.get("evidence", {}).get("day_master", "")

    jieqi = eastern.get("evidence", {}).get("jieqi", "")
    weekday = eastern.get("evidence", {}).get("weekday", western.get("evidence", {}).get("weekday", ""))

    summary = (
        f"Dein Fusionstag verbindet {shared_str} aus beiden Systemen. "
        f"Westlich staerkt dein Transitfeld, oestlich arbeitet dein Day Master {day_master} in {relation}-Dynamik."
    )
    jieqi_note = f"Solarterm {jieqi} faerbt beide Systeme." if jieqi else ""
    weekday_note = f"{weekday}-Energie verbindet die Impulse." if weekday else ""
    synthesis = (
        f"Beide Systeme zeigen heute einen gemeinsamen Impuls: {shared_str}. "
        f"Gleichzeitig entsteht Spannung im Bereich {tension_str}. "
        f"Die Synthese liegt darin, beides bewusst zu halten — "
        f"den {shared_str}-Impuls aktiv zu nutzen und den Spannungsbereich nicht zu verdraengen."
    )
    action = (
        f"Nutze heute gezielt den Bereich {shared_str}. "
        f"Plane eine bewusste Handlung, die beide Energien verbindet."
    )
    pushworthy = relation in ("power", "wealth", "resource")
    push_text = f"Dein {relation.title()}-Tag: {shared_str} ruft." if pushworthy else None

    return {
        "summary": summary,
        "synthesis": synthesis,
        "action": action,
        "pushworthy": pushworthy,
        "push_text": push_text,
        "jieqi_note": jieqi_note,
        "weekday_note": weekday_note,
    }
