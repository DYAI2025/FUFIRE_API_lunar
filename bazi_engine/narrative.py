"""
narrative.py — Template-based transit narrative generation.

ADR-3: Sync template always. No LLM in request path.
Gemini async enrichment is a future enhancement.
"""
from __future__ import annotations

import string
from typing import Any, Dict, List

# German narrative templates keyed by event type
_TEMPLATES = {
    "resonance_jump": {
        "headline": "$planet trifft dein $sign-Feld",
        "body": (
            "$planet steht aktuell in deinem Sektor $sector ($sign). "
            "Das ist einer deiner stärksten Bereiche \u2014 $personal_context. "
            "Diese Konstellation bringt Energie und Aufmerksamkeit in dieses Feld."
        ),
        "advice": (
            "Nutze die $planet-Energie heute bewusst. "
            "Dein $sign-Feld ist aktiviert \u2014 ein guter Moment f\u00fcr Entscheidungen in diesem Bereich."
        ),
    },
    "moon_event": {
        "headline": "Mond-Resonanz in deinem $sign-Feld",
        "body": (
            "Der Mond durchquert gerade deinen Sektor $sector ($sign). "
            "$personal_context. "
            "Emotionale Themen in diesem Bereich treten heute st\u00e4rker hervor."
        ),
        "advice": (
            "Achte heute besonders auf deine emotionalen Reaktionen. "
            "Der Mond verst\u00e4rkt die Sensibilit\u00e4t in deinem $sign-Bereich."
        ),
    },
    "dominance_shift": {
        "headline": "Dein Schwerpunkt verschiebt sich",
        "body": (
            "Eine neue dominante Energie entsteht in Sektor $sector ($sign). "
            "$personal_context."
        ),
        "advice": "Beobachte, welche neuen Themen sich heute zeigen.",
    },
}

_DEFAULT_TEMPLATE = {
    "headline": "Dein kosmisches Wetter heute",
    "body": (
        "Die aktuelle Planetenkonstellation ist ruhig. "
        "Keine besonderen Transite aktivieren deine starken Felder. "
        "Ein guter Tag f\u00fcr Routine und Reflexion."
    ),
    "advice": "Nutze die Ruhe f\u00fcr innere Arbeit und Planung.",
}

ZODIAC_SIGNS_DE = {
    "aries": "Widder", "taurus": "Stier", "gemini": "Zwillinge",
    "cancer": "Krebs", "leo": "L\u00f6we", "virgo": "Jungfrau",
    "libra": "Waage", "scorpio": "Skorpion", "sagittarius": "Sch\u00fctze",
    "capricorn": "Steinbock", "aquarius": "Wassermann", "pisces": "Fische",
}

ZODIAC_SIGNS = [
    "aries", "taurus", "gemini", "cancer", "leo", "virgo",
    "libra", "scorpio", "sagittarius", "capricorn", "aquarius", "pisces",
]


def generate_narrative(transit_state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate narrative text from a transit state.

    Uses template engine (sync, <50ms).
    Returns headline, body, advice, pushworthy, push_text.
    """
    events: List[Dict[str, Any]] = transit_state.get("events", [])

    if not events:
        return {
            "headline": _DEFAULT_TEMPLATE["headline"],
            "body": _DEFAULT_TEMPLATE["body"],
            "advice": _DEFAULT_TEMPLATE["advice"],
            "pushworthy": False,
            "push_text": None,
        }

    # Use highest-priority event for narrative
    primary = min(events, key=lambda e: e.get("priority", 99))
    event_type = primary.get("type", "")
    template = _TEMPLATES.get(event_type, _DEFAULT_TEMPLATE)

    sector = primary.get("sector", 0)
    sign_en = ZODIAC_SIGNS[sector] if 0 <= sector < 12 else "aries"
    sign_de = ZODIAC_SIGNS_DE.get(sign_en, sign_en)
    planet = primary.get("trigger_planet", "").capitalize()
    personal_context = primary.get("personal_context", "")

    fmt = {
        "planet": planet,
        "sign": sign_de,
        "sector": sector,
        "personal_context": personal_context,
    }

    headline = string.Template(template["headline"]).safe_substitute(fmt)
    body = string.Template(template["body"]).safe_substitute(fmt)
    advice = string.Template(template["advice"]).safe_substitute(fmt)

    pushworthy = primary.get("priority", 99) <= 1

    return {
        "headline": headline,
        "body": body,
        "advice": advice,
        "pushworthy": pushworthy,
        "push_text": headline if pushworthy else None,
    }
