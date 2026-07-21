"""Deterministic Da-Yun interpretation layer.

Fills semantic_summary (supports/frictions/practice) from the decade's Ten-God
relation to the Day Master plus classical branch relations (六冲 clash, 六合
combine) between the decade branch and the four natal branches. Deterministic;
no favorability / yong-shen judgment (anti-fabrication).
"""
from __future__ import annotations

from ..constants import STEMS

# 六合 (Six Combinations): fixed classical pairs.
# Zi-Chou, Yin-Hai, Mao-Xu, Chen-You, Si-Shen, Wu-Wei.
SIX_COMBINE = frozenset(
    frozenset(p) for p in [(0, 1), (2, 11), (3, 10), (4, 9), (5, 8), (6, 7)]
)


def _clashes(a: int, b: int) -> bool:
    """六冲: branches 6 positions apart clash (Zi-Wu, Chou-Wei, ...)."""
    return (a - b) % 12 == 6


def _combines(a: int, b: int) -> bool:
    return frozenset((a, b)) in SIX_COMBINE


def branch_interactions(decade_branch_index: int, natal_branches: dict) -> dict:
    """Return {'clashes': [pos,...], 'combines': [pos,...]} — the natal positions
    ('year'/'month'/'day'/'hour') the decade branch clashes / combines with.
    Order follows year, month, day, hour."""
    clashes, combines = [], []
    for pos in ("year", "month", "day", "hour"):
        nb = natal_branches[pos]
        if _clashes(decade_branch_index, nb):
            clashes.append(pos)
        if _combines(decade_branch_index, nb):
            combines.append(pos)
    return {"clashes": clashes, "combines": combines}


# Ten-God → (bucket, German phrase). bucket ∈ {'support','friction','neutral'}.
_TEN_GOD_BUCKET = {
    "Zheng Yin":  ("support",  "Direkte Quelle stützt deinen Kern (Lernen, Rückhalt)."),
    "Pian Yin":   ("support",  "Indirekte Quelle nährt unkonventionell (Intuition, Nischenwissen)."),
    "Shi Shen":   ("support",  "Schöpferische Ausgabe fließt leicht (Ausdruck, Genuss)."),
    "Zheng Cai":  ("support",  "Direktes Vermögen — stetiger, greifbarer Ertrag."),
    "Bi Jian":    ("neutral",  "Gefährte — Gleichrangige, Selbstbehauptung, Teamdynamik."),
    "Zheng Guan": ("neutral",  "Verantwortung — Struktur, Pflicht, Anerkennung von außen."),
    "Pian Cai":   ("neutral",  "Indirektes Vermögen — Chancen, unregelmäßiger Fluss."),
    "Shang Guan": ("friction", "Disruptive Ausgabe — Reibung mit Regeln/Autorität, aber Innovationsdruck."),
    "Qi Sha":     ("friction", "Druck/Struktur — Belastung, die zu Disziplin zwingt."),
    "Jie Cai":    ("friction", "Rivale — Konkurrenz um Ressourcen, Wachsamkeit nötig."),
}
_PRACTICE = {
    "support":  "Diese Dekade trägt — nutze den Rückenwind für Aufbau statt Absicherung.",
    "friction": "Diese Dekade fordert — kleine, disziplinierte Schritte schlagen große Sprünge.",
    "neutral":  "Diese Dekade ist gestaltbar — setze bewusst Richtung, sie kippt in keine Extreme.",
}
_PALACE_DE = {
    "year":  "Jahr (Herkunft)",
    "month": "Monat (Umfeld/Karriere)",
    "day":   "Tag (Selbst/Partnerschaft)",
    "hour":  "Stunde (Nachkommen/Spätphase)",
}


def build_semantic_summary(day_master_stem_index, decade_pillar, natal_branches, relation) -> dict:
    """Assemble the current-decade semantic_summary. Deterministic. Schema:
    {road_metaphor:str, supports:[str], frictions:[str], practice:[str]}."""
    ten_god = relation["ten_god"]
    bucket, phrase = _TEN_GOD_BUCKET.get(ten_god, ("neutral", ""))
    inter = branch_interactions(decade_pillar["index60"] % 12, natal_branches)

    supports, frictions = [], []
    if bucket == "support" and phrase:
        supports.append(phrase)
    elif bucket == "friction" and phrase:
        frictions.append(phrase)
    # neutral phrase: attach to neither list (keeps arrays evidence-clean).
    for pos in inter["combines"]:
        supports.append(f"六合 mit der {_PALACE_DE[pos]}-Säule — Bündelung/Unterstützung dort.")
    for pos in inter["clashes"]:
        frictions.append(f"六冲 mit der {_PALACE_DE[pos]}-Säule — Aufbruch/Spannung dort.")

    road_metaphor = (
        f"Diese Dekade beschreibt die Strasse, auf der dein "
        f"{STEMS[day_master_stem_index]}-Kern gerade wirkt."
    )
    return {
        "road_metaphor": road_metaphor,
        "supports": supports,
        "frictions": frictions,
        "practice": [_PRACTICE[bucket]],
    }
