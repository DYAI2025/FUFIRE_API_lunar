"""Template variants for daily horoscope generators.

Provides weekday modifiers, Jieqi seasonal flavors, and relation-specific
template pools so daily readings vary by (relation × jieqi × weekday).
"""
from __future__ import annotations

from datetime import datetime
from typing import Tuple

# ---------------------------------------------------------------------------
# Weekday energy modifiers (German, index 0=Monday ... 6=Sunday)
# ---------------------------------------------------------------------------
WEEKDAY_ENERGY_DE = {
    0: ("Montag", "Mond", "Innenschau und Intuition dominieren."),
    1: ("Dienstag", "Mars", "Tatendrang und Entschlossenheit praegen den Tag."),
    2: ("Mittwoch", "Merkur", "Kommunikation und Austausch stehen im Vordergrund."),
    3: ("Donnerstag", "Jupiter", "Expansion und Grosszuegigkeit praegen die Stimmung."),
    4: ("Freitag", "Venus", "Harmonie und Genuss sind heute besonders spuerbar."),
    5: ("Samstag", "Saturn", "Struktur und Verantwortung fordern deine Aufmerksamkeit."),
    6: ("Sonntag", "Sonne", "Selbstausdruck und Vitalitaet strahlen heute besonders."),
}

# ---------------------------------------------------------------------------
# Jieqi seasonal energy (24 terms → 8 seasonal groups)
# ---------------------------------------------------------------------------
_JIEQI_SEASON_MAP = {
    # Early Spring (wood rising)
    "Lichun": "fruehling_aufbruch",
    "Yushui": "fruehling_aufbruch",
    "Jingzhe": "fruehling_aufbruch",
    "Chunfen": "fruehling_aufbruch",
    # Late Spring (wood full)
    "Qingming": "fruehling_reife",
    "Guyu": "fruehling_reife",
    # Early Summer (fire rising)
    "Lixia": "sommer_aufbruch",
    "Xiaoman": "sommer_aufbruch",
    "Mangzhong": "sommer_aufbruch",
    "Xiazhi": "sommer_aufbruch",
    # Late Summer (fire→earth transition)
    "Xiaoshu": "sommer_reife",
    "Dashu": "sommer_reife",
    # Early Autumn (metal rising)
    "Liqiu": "herbst_aufbruch",
    "Chushu": "herbst_aufbruch",
    "Bailu": "herbst_aufbruch",
    "Qiufen": "herbst_aufbruch",
    # Late Autumn (metal full)
    "Hanlu": "herbst_reife",
    "Shuangjiang": "herbst_reife",
    # Early Winter (water rising)
    "Lidong": "winter_aufbruch",
    "Xiaoxue": "winter_aufbruch",
    "Daxue": "winter_aufbruch",
    "Dongzhi": "winter_aufbruch",
    # Late Winter (water → wood transition)
    "Xiaohan": "winter_reife",
    "Dahan": "winter_reife",
}

JIEQI_FLAVOR_DE = {
    "fruehling_aufbruch": "Die aufsteigende Holz-Energie weckt Wachstumsimpulse.",
    "fruehling_reife": "Der Fruehling entfaltet sich vollstaendig -- Saat traegt Knospen.",
    "sommer_aufbruch": "Feuer-Energie steigt: Sichtbarkeit und Aktivitaet nehmen zu.",
    "sommer_reife": "Die Feuer-Energie erreicht ihren Hoehepunkt -- Transformation beginnt.",
    "herbst_aufbruch": "Metall-Energie bringt Klarheit und Konzentration zurueck.",
    "herbst_reife": "Der Herbst verdichtet sich -- Zeit fuer Ernte und Rueckschau.",
    "winter_aufbruch": "Wasser-Energie laesst Stille und Tiefe einziehen.",
    "winter_reife": "Die tiefste Ruhe des Jahres -- Regeneration und Vorbereitung.",
}


def get_jieqi_season(jieqi_name: str) -> str:
    """Return seasonal group key for a Jieqi name."""
    return _JIEQI_SEASON_MAP.get(jieqi_name, "fruehling_aufbruch")


def get_jieqi_flavor(jieqi_name: str) -> str:
    """Return German seasonal flavor text for a Jieqi."""
    season = get_jieqi_season(jieqi_name)
    return JIEQI_FLAVOR_DE.get(season, "")


def get_weekday_modifier(target_date: str) -> Tuple[str, str, str]:
    """Return (weekday_name, planet_ruler, energy_text) for a date string."""
    dt = datetime.strptime(target_date, "%Y-%m-%d")
    weekday_idx = dt.weekday()  # 0=Monday
    return WEEKDAY_ENERGY_DE.get(weekday_idx, ("Tag", "Neutral", ""))


# ---------------------------------------------------------------------------
# Relation summary variants (eastern daily)
# Each relation has 3 templates; selection is deterministic via day-of-year.
# ---------------------------------------------------------------------------
RELATION_SUMMARY_VARIANTS_DE = {
    "companion": [
        "Der heutige Tag schwingt mit deinem Day Master {dm} in Gleichklang. {element}-Energie verstaerkt dich.",
        "Heute begegnest du deinem eigenen Element. Dein Day Master {dm} findet Resonanz in der {element}-Schwingung.",
        "{element} trifft auf {element} -- ein Tag der Staerkung fuer deinen Day Master {dm}.",
    ],
    "resource": [
        "Heute naehrt der Tag deinen Day Master {dm}. {element} bringt Unterstuetzung von aussen.",
        "Dein Day Master {dm} wird heute getragen. Die {element}-Energie naehrt dich aus der Tiefe.",
        "Ein naehrender Tag: {element} fliesst zu deinem Day Master {dm} und baut Reserven auf.",
    ],
    "output": [
        "Dein Day Master {dm} produziert heute aktiv. Guter Tag fuer sichtbare Ergebnisse.",
        "Heute will dein Day Master {dm} sich ausdruecken. Die {element}-Energie verstaerkt deine Wirkung.",
        "Schaffenskraft pragt den Tag -- dein Day Master {dm} erzeugt {element} und wird sichtbar.",
    ],
    "power": [
        "Dein Day Master {dm} kontrolliert die Tagesenergie. Fokussiere dich und halte Disziplin.",
        "Die {element}-Energie prueft deinen Day Master {dm} heute. Bleibe standhaft -- Struktur zahlt sich aus.",
        "Kontrolle ist das Thema: Dein Day Master {dm} steht unter {element}-Druck. Nutze die Spannung produktiv.",
    ],
    "wealth": [
        "Die Tagesenergie fordert deinen Day Master {dm} heraus. Achte auf Ressourcen und Grenzen.",
        "{element} liegt heute in Reichweite deines Day Masters {dm}. Greife gezielt zu -- nicht impulsiv.",
        "Dein Day Master {dm} erobert heute {element}-Terrain. Dosiere deine Kraefte bewusst.",
    ],
    "neutral": [
        "Ein ausgeglichener Tag fuer deinen Day Master {dm}. Beobachte und reagiere bewusst.",
        "Keine starke Dynamik heute -- dein Day Master {dm} darf frei navigieren.",
        "Die Tagesenergie ist neutral zu deinem Day Master {dm}. Nutze den Freiraum fuer eigene Akzente.",
    ],
}

CAUTION_VARIANTS_DE = {
    "companion": [
        "Die {relation}-Dynamik kann heute zu Ueberreaktion fuehren. Bleibe geerdet.",
        "Gleichklang klingt harmonisch, kann aber zu Selbstueberschaetzung fuehren.",
        "Zu viel {element} verstaerkt blinde Flecken. Suche bewusst Gegengewichte.",
    ],
    "resource": [
        "Uebermaessiges Annehmen kann passiv machen. Bleibe aktiv trotz Unterstuetzung.",
        "Naehrende Energie kann traege machen -- halte deine Eigeninitiative wach.",
        "Verlasse dich heute nicht ausschliesslich auf aeussere Hilfe.",
    ],
    "output": [
        "Hohe Produktivitaet kann erschoepfen. Plane bewusste Pausen ein.",
        "Nicht alles, was heute entsteht, muss sofort geteilt werden. Qualitaet vor Quantitaet.",
        "Dein Ausdruck ist stark -- achte darauf, andere nicht zu ueberfordern.",
    ],
    "power": [
        "Die Kontrolldynamik kann heute zu Rigiditaet fuehren. Lass auch Unerwartetes zu.",
        "Disziplin ist wichtig, aber Uebersteuerung blockiert Fluss. Finde die Balance.",
        "Machtdynamik kann Konflikte ausloesen -- wahle deine Kaempfe bewusst.",
    ],
    "wealth": [
        "Gier nach Ressourcen kann heute blind machen. Pruefe, bevor du zugreifst.",
        "Die Herausforderung liegt im Timing -- nicht alles muss heute erobert werden.",
        "Achte auf Grenzen -- Ueberausgabe (Energie oder Mittel) liegt heute nah.",
    ],
    "neutral": [
        "Neutralitaet kann zu Orientierungslosigkeit fuehren. Setze bewusst Prioritaeten.",
        "Ohne starken Impuls kann der Tag ziellos verlaufen. Gib dir selbst Struktur.",
        "Ein ruhiger Tag kann taeuschen -- bleibe aufmerksam fuer subtile Signale.",
    ],
}

OPPORTUNITY_VARIANTS_DE = {
    "companion": [
        "{theme} ist heute dein staerkstes Feld. Nutze die {element}-Energie bewusst.",
        "Dein Element ist verstaerkt -- idealer Tag fuer Projekte, die deiner Natur entsprechen.",
        "Gleiche Schwingung heisst Rueckenwind. Setze heute auf das, was dir leicht faellt.",
    ],
    "resource": [
        "{theme} ist heute dein staerkstes Feld. Nutze die {element}-Energie bewusst.",
        "Die zufliessende Energie eignet sich hervorragend zum Lernen und Aufbauen.",
        "Heute kannst du Reserven anlegen -- nutze die naehrende Qualitaet aktiv.",
    ],
    "output": [
        "{theme} ist heute dein staerkstes Feld. Nutze die {element}-Energie bewusst.",
        "Deine Schaffenskraft ist hoch -- idealer Tag, um Ergebnisse zu liefern.",
        "Was du heute erschaffst, hat besondere Strahlkraft. Zeige dich.",
    ],
    "power": [
        "{theme} ist heute dein staerkstes Feld. Nutze die {element}-Energie bewusst.",
        "Struktur und Fokus sind heute deine Superkraefte -- setze sie gezielt ein.",
        "Kontrolle bedeutet Richtung. Nutze die Klarheit fuer wichtige Entscheidungen.",
    ],
    "wealth": [
        "{theme} ist heute dein staerkstes Feld. Nutze die {element}-Energie bewusst.",
        "Die Herausforderung birgt Potenzial -- wer klug zugreift, gewinnt heute.",
        "Wealth-Tage bringen materielle und immaterielle Chancen. Augen offen halten.",
    ],
    "neutral": [
        "{theme} ist heute dein staerkstes Feld. Nutze die {element}-Energie bewusst.",
        "Freiraum ist Luxus -- nutze ihn fuer strategische Planung oder kreative Arbeit.",
        "Ohne Druck laesst sich heute Grundlegendes vorbereiten. Idealer Tag zum Sortieren.",
    ],
}


def select_variant(variants: list, target_date: str) -> str:
    """Deterministically select a variant based on day-of-year."""
    dt = datetime.strptime(target_date, "%Y-%m-%d")
    doy = dt.timetuple().tm_yday
    return variants[doy % len(variants)]
