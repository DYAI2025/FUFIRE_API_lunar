"""
Archetypische VAD-Profile der 12 Sektoren.

Jeder Sektor reprasentiert ein astrologisches Zeichen mit charakteristischen
emotionalen Qualitaeten, uebersetzt in Valence/Arousal/Dominance.

Quellen:
- Astrologische Haus-/Zeichen-Archetypen (standardisiert)
- VAD-Dimensionen nach Mehrabian & Russell (1974)

Die Profile sind FIXIERT und aendern sich nicht. Sie bilden den
Referenzraum gegen den alle Marker-VADs verglichen werden.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class VADProfile:
    valence: float    # -1.0 to +1.0 (negativ <-> positiv)
    arousal: float    #  0.0 to +1.0 (ruhig <-> aktiviert)
    dominance: float  #  0.0 to +1.0 (submissiv <-> dominant)


SECTOR_VAD: dict[int, VADProfile] = {
    # S0 — Widder (Aries)
    # Impuls, Mut, Initiative, Koerper. Handelt zuerst, denkt spaeter.
    # Emotional: aufbrausend-positiv, hochaktiviert, sehr dominant.
    0: VADProfile(valence=+0.30, arousal=0.90, dominance=0.90),

    # S1 — Stier (Taurus)
    # Sinnlichkeit, Stabilitaet, Genuss, Besitz. Langsam, bestaendig, erdend.
    # Emotional: genussvoll-positiv, ruhig, stabil-dominant.
    1: VADProfile(valence=+0.40, arousal=0.20, dominance=0.60),

    # S2 — Zwillinge (Gemini)
    # Kognition, Kommunikation, Neugier, Anpassung. Schnell, vielseitig.
    # Emotional: leicht-positiv, mittel-aktiviert, balanciert.
    2: VADProfile(valence=+0.20, arousal=0.60, dominance=0.50),

    # S3 — Krebs (Cancer)
    # Emotion, Fuersorge, Heim, Schutz, Empathie. Weich, naehrend.
    # Emotional: warm-positiv, mittel-aktiviert, eher submissiv.
    3: VADProfile(valence=+0.30, arousal=0.50, dominance=0.20),

    # S4 — Loewe (Leo)
    # Ausdruck, Kreativitaet, Fuehrung, Ego, Freude. Strahlend, zentral.
    # Emotional: stark-positiv, hoch-aktiviert, sehr dominant.
    4: VADProfile(valence=+0.60, arousal=0.80, dominance=0.90),

    # S5 — Jungfrau (Virgo)
    # Analyse, Dienst, Praezision, Gesundheit, Ordnung. Kontrolliert, genau.
    # Emotional: neutral-positiv, ruhig, kontrolliert-dominant.
    5: VADProfile(valence=+0.10, arousal=0.30, dominance=0.60),

    # S6 — Waage (Libra)
    # Beziehung, Harmonie, Aesthetik, Diplomatie, Balance. Ausgleichend.
    # Emotional: mild-positiv, ruhig, balanciert.
    6: VADProfile(valence=+0.30, arousal=0.30, dominance=0.40),

    # S7 — Skorpion (Scorpio)
    # Tiefe, Transformation, Intensitaet, Sexualitaet, Macht. Dunkel, komplex.
    # Emotional: negativ-intensiv, hoch-aktiviert, sehr dominant.
    7: VADProfile(valence=-0.40, arousal=0.85, dominance=0.80),

    # S8 — Schuetze (Sagittarius)
    # Freiheit, Philosophie, Expansion, Abenteuer, Wahrheit. Weit, optimistisch.
    # Emotional: positiv, hoch-aktiviert, mittel-dominant.
    8: VADProfile(valence=+0.50, arousal=0.70, dominance=0.60),

    # S9 — Steinbock (Capricorn)
    # Struktur, Ambition, Disziplin, Verantwortung, Status. Ernst, ausdauernd.
    # Emotional: leicht-negativ, mittel-aktiviert, sehr dominant.
    9: VADProfile(valence=-0.10, arousal=0.40, dominance=0.85),

    # S10 — Wassermann (Aquarius)
    # Kollektiv, Innovation, Rebellion, Originalitaet, Zukunft. Unkonventionell.
    # Emotional: neutral-positiv, mittel-aktiviert, niedrig-dominant.
    10: VADProfile(valence=+0.20, arousal=0.50, dominance=0.30),

    # S11 — Fische (Pisces)
    # Intuition, Aufloesung, Spiritualitaet, Traeume, Hingabe. Grenzenlos.
    # Emotional: leicht-positiv, niedrig-aktiviert, sehr submissiv.
    11: VADProfile(valence=+0.10, arousal=0.20, dominance=0.10),
}

SECTOR_NAMES = [
    "Widder", "Stier", "Zwillinge", "Krebs", "Loewe", "Jungfrau",
    "Waage", "Skorpion", "Schuetze", "Steinbock", "Wassermann", "Fische",
]

SECTOR_SIGNS_EN = [
    "aries", "taurus", "gemini", "cancer", "leo", "virgo",
    "libra", "scorpio", "sagittarius", "capricorn", "aquarius", "pisces",
]
