# 08 — Zwei Deutungslogiken: Narrativ und Diagnostisch

Dieses Dokument definiert zwei vollständige, in sich konsistente Logiken,
wie die Fusion-Mathematik in astrologische Sprache übersetzt werden kann.
Beide Logiken sind **schematisch plausibel** — jede Aussage ist aus den
Zahlen ableitbar, keine ist erfunden.

---

## Vorbedingung: Was "schematisch plausibel" bedeutet

Schematische Plausibilität hat zwei Bedingungen:

1. **Mathematische Bindung:** Jede Aussage muss eindeutig aus Zahlenwerten
   folgen. Gleiche Zahlen → gleiche Aussage, immer.

2. **Traditionskongruenz:** Die Aussage muss innerhalb des Bedeutungsraums
   beider astrologischen Traditionen liegen. Es wird nichts erfunden —
   nur übersetzt und verbunden.

---

## Logik A: Die astrologische Geschichte (narrativ-symbolisch)

### Grundprinzip

Die Mathematik liefert den **Plot** — der Archetyp liefert die **Sprache**.
Das Ergebnis ist eine Geschichte, die der Nutzer wiedererkennen kann.

### Schritt 1: Archetyp bestimmen

Aus H-Wert und Resonanzachse (dominantes `rᵢ`):

```python
def get_archetype(H, resonance_axis):
    if H >= 0.8:
        return ARCHETYPES_HIGH[resonance_axis]
    elif H >= 0.6:
        return ARCHETYPES_MEDIUM_HIGH[resonance_axis]
    elif H >= 0.4:
        return ARCHETYPES_MEDIUM[resonance_axis]
    elif H >= 0.2:
        return ARCHETYPES_MEDIUM_LOW[resonance_axis]
    else:
        return ARCHETYPES_LOW[resonance_axis]
```

**Archetypen-Matrix (Auswahl):**

| | Holz | Feuer | Erde | Metall | Wasser |
|---|---|---|---|---|---|
| **H ≥ 0.8** | Der Visionär | Der Leuchtturm | Der Anker | Der Meister | Der Tiefenschwimmer |
| **H 0.6–0.8** | Der Wachstumstreiber | Der Kommunikator | Der Strukturgeber | Der Differenzierer | Der Intuitive |
| **H 0.4–0.6** | Der Alchemist des Aufbruchs | Der Alchemist des Ausdrucks | Der Alchemist der Form | Der Alchemist der Klarheit | Der Alchemist der Tiefe |
| **H 0.2–0.4** | Der Wanderer | Der Flackernde | Der Sucher | Der Zweifler | Der Rückgezogene |
| **H < 0.2** | Der Brückenbauer (Holz) | Der Brückenbauer (Feuer) | Der Brückenbauer (Erde) | Der Brückenbauer (Metall) | Der Brückenbauer (Wasser) |

### Schritt 2: Narrative aufbauen

Jeder Archetyp hat eine **Dreisatz-Erzählung**:

1. **Wer du bist** (aus dem BaZi — innere Struktur)
2. **Was der Moment bringt** (aus Western — kosmischer Kontext)
3. **Wie sich beides verhält** (aus H und Differenzfeld)

**Beispiel: H = 0.84, Resonanzachse = Feuer, d_Holz = −0.4**

```
Archetypus: "Der Leuchtturm"

[Wer du bist]
Dein BaZi zeigt eine ausgeprägte Feuer- und Holzstruktur —
Vitalität, Ausdruck und Wachstumsdrang sind in deiner Zeitstruktur tief verankert.
Das Holzelement (Stämme Jia oder Yi) trägt das Feuer: du wächst, um zu leuchten.

[Was der Moment bringt]
Der Himmel deiner Geburt spricht dieselbe Sprache: Sonne und Mars in Feuerachsen,
Jupiter (Holz) prominent. Die kosmische Konfiguration spiegelt, was du innerlich bist.

[Wie sich beides verhält]
Hier arbeiten Ost und West synoptisch — mit einem H von 0.84 ist die
systemische Kongruenz außergewöhnlich hoch. Die Differenz zeigt: deine innere
Holzstruktur übersteigt das Himmelsangebot leicht (d_Holz = −0.4). Das bedeutet:
Wachstumsantrieb kommt primär von innen, nicht vom kosmischen Rückenwind.
Du trägst dein Feuer selbst.
```

### Schritt 3: Entwicklungsfeld einbinden

Das Differenzfeld wird als **offene Frage** formuliert, nicht als Defizit:

```
Das Feld, das die stärkste Spannung trägt, ist {max(|dᵢ|) Achse}.
Wenn d < 0: "Was brauchst du, um das, was du innerlich bist, 
             in der Welt sichtbar zu machen?"
Wenn d > 0: "Was bietet dir das Leben an, das du noch nicht 
             vollständig angenommen hast?"
```

### Textgenerierungsprinzip

Die Geschichte wird **modular** aufgebaut — jeder Block stammt aus
einem Template, befüllt mit konkreten Zahlenwerten:

```
[ARCHETYP]     = f(H, resonance_axis)
[BAZI_PROFIL]  = f(dominant_bazi_element, top_branch_hidden)
[WEST_PROFIL]  = f(dominant_western_planet, dominant_sign)
[KONGRUENZ]    = f(H, threshold_label)
[ENTWICKLUNG]  = f(max_diff_element, sign(diff))
[FRAGE]        = f(max_diff_element, sign(diff), archetype)
```

**Jede Aussage ist aus den Zahlen ableitbar. Keine Aussage ist erfunden.**

---

## Logik B: Die diagnostische Karte (analytisch-funktional)

**Implementation:** `bazi_engine/wuxing/zones.py`  
**Kernfunktion:** `classify_zones()`, `build_leitfragen()`, `format_report_b()`

### Grundprinzip

Keine Erzählung, kein Archetyp — nur **Topografie**. Die Karte zeigt,
wo Stärken liegen, wo Spannung besteht, und wo Entwicklungsraum ist.
Das Ergebnis ist ein strukturierter Report, den der Nutzer selbst interpretiert.

### Die vier Zonen — exklusiv und hierarchisch

Jedes der fünf Elemente wird genau einer Zone zugeordnet. Die Klassifikation
ist **hierarchisch** (Priorität bestimmt bei Überlappung) und **exklusiv**
(kein Element ist in zwei Zonen gleichzeitig). Die Disjunktheit ist
mathematisch beweisbar — nicht nur Konvention.

**Prioritätsreihenfolge:**
```
1. TENSION      (höchste Priorität)
2. STRENGTH
3. DEVELOPMENT
4. NEUTRAL      (nicht im Report angezeigt)
```

**Pseudocode (kanonisch):**

```python
def classify_zones(west_norm, bazi_norm,
                   thr_tension=0.15, thr_strength=0.20,
                   thr_development=0.15, eps=1e-12):
    diffs = {e: west_norm[e] - bazi_norm[e] for e in ELEMENTS}
    zones = {}
    for e in ELEMENTS:
        w, b, d = west_norm[e], bazi_norm[e], diffs[e]

        # 1) TENSION — abs(d) > 0.15 (strikt, priorisiert)
        if abs(d) > thr_tension + eps:
            zones[e] = "TENSION"

        # 2) STRENGTH — beidseitig hoch UND kein Tension
        elif (w > thr_strength + eps) and (b > thr_strength + eps):
            zones[e] = "STRENGTH"

        # 3) DEVELOPMENT — beidseitig niedrig
        elif (w < thr_development - eps) and (b < thr_development - eps):
            zones[e] = "DEVELOPMENT"

        # 4) NEUTRAL — alles andere
        else:
            zones[e] = "NEUTRAL"

    return zones, diffs
```

**Mathematischer Disjunktionsbeweis:**

| Paar | Warum ausgeschlossen |
|---|---|
| TENSION ∩ STRENGTH | Strength verlangt `abs(d) ≤ 0.15`, Tension `abs(d) > 0.15` → unmöglich |
| STRENGTH ∩ DEVELOPMENT | Strength: beide > 0.20; Development: beide < 0.15 → unmöglich (0.20 > 0.15) |
| TENSION ∩ DEVELOPMENT | Wenn beide < 0.15, dann `abs(d) = abs(w−b) < 0.15` → kein Tension möglich |

**Hinweis zu Gleitkommazahlen:** `eps=1e-12` schützt vor Grenzfällen bei
exakt 0.15 oder 0.20 — die Schwellen sind **strikt** (`>`, nicht `>=`).

### Die vier Zonen im Detail

**TENSION** — Das aktivste Interpretationsfeld

```
Kriterium: abs(d_i) > 0.15
Beispiel:  west=0.37, bazi=0.21 → d=+0.16 → TENSION (West dominiert)
```

Tension ist kein Defizit — es ist eine **Bewegung**. Das Element befindet
sich in aktiver Spannung zwischen Innen (BaZi) und Außen (West). Die
Richtung des Vorzeichens zeigt, wohin die Energie tendiert:

- `d > 0` (West > BaZi): Kosmischer Impuls übersteigt innere Struktur.
  Der Moment bietet mehr, als die eigene Grundlage trägt.
- `d < 0` (BaZi > West): Innere Stärke übersteigt kosmisches Angebot.
  Die eigene Kapazität sucht einen Ausdruck, den der Moment nicht spiegelt.

**STRENGTH** — Das stabile Fundament

```
Kriterium: west > 0.20 AND bazi > 0.20 AND abs(d) ≤ 0.15
Beispiel:  west=0.28, bazi=0.23 → d=+0.05 → STRENGTH
```

Strength-Elemente laufen. Beide Systeme bestätigen diese Achse —
mit ähnlicher Intensität und ohne starke Divergenz. Das ist der
Bereich, wo der Mensch ohne innere Reibung operiert.

**DEVELOPMENT** — Der unentwickelte Raum

```
Kriterium: west < 0.15 AND bazi < 0.15
Beispiel:  west=0.12, bazi=0.11 → DEVELOPMENT
```

Kein Mangel — ein **Potenzialfeld**. In der BaZi-Tradition: fehlendes
Element (缺, quē). Es ist zugleich Schwachstelle (das fehlende Element
schwächt bestimmte Lebensbereiche) und Hebel (wenig Input erzeugt große
Wirkung in diesem Bereich).

**NEUTRAL** — Weder noch

```
Kriterium: keines der obigen
```

Das Element ist in einem mittleren Bereich ohne starke Ausprägung
nach oben oder unten. Nicht im Report angezeigt — nicht bedeutungslos,
aber kein aktives Thema.

### Anzeigewerte: Indexpunkte, nicht Prozent

Die L2-normalisierten Vektoren sind **keine additiven Prozentanteile**.
Ihre Komponenten summieren sich nicht auf 100%, sondern erfüllen:
`‖v‖₂ = √(Σ vᵢ²) = 1`.

Für die Anzeige werden sie mit 100 skaliert und als **Indexpunkte** bezeichnet:

```
Indexpunkte = L2-Koordinate × 100
```

Diese Konvention verhindert, dass Nutzer die Werte als Prozentanteile
misinterpretieren und versuchen, sie aufzusummieren.

**Korrekte Formulierung:**  
"Feuer: 61,2 Indexpunkte (West) / 34,0 Indexpunkte (BaZi)"  
**Nicht:** "61,2% Feuer-Anteil" (da Σ ≠ 100%)

### Ausgabeformat (v3 — regelkonformes Beispiel)

Das folgende Beispiel ist vollständig regelkonform mit dem obigen Pseudocode.
Alle Zonenzuordnungen sind aus den d_i-Werten ableitbar:

```
abs(d_Holz)  = 0.499 > 0.15  → TENSION
abs(d_Feuer) = 0.272 > 0.15  → TENSION
abs(d_Erde)  = 0.142 ≤ 0.15 AND west=0.418>0.20 AND bazi=0.560>0.20 → STRENGTH
abs(d_Metall)= 0.351 > 0.15  → TENSION
abs(d_Wasser)= 0.235 > 0.15  → TENSION
```

```
═══════════════════════════════════════════════════════
FUSION ANALYSE — DIAGNOSTISCHE KARTE (Logik B)
═══════════════════════════════════════════════════════

HARMONY INDEX: 68.47 Indexpunkte (Gute Harmonie)
(Cosinus-Ähnlichkeit der normierten Elementarvektoren)

───────────────────────────────────────────────────────
STÄRKEFELDER  (beidseitig > 20 Pkt., Δ ≤ 15 Pkt.)
───────────────────────────────────────────────────────
● Erde       West  41.8   BaZi  56.0   Δ−14.2

───────────────────────────────────────────────────────
SPANNUNGSFELDER  (|Δ| > 15 Pkt., priorisiert)
───────────────────────────────────────────────────────
▲ Holz       West  23.1   BaZi  73.0   Δ−49.9  [BaZi dominiert]
▲ Feuer      West  61.2   BaZi  34.0   Δ+27.2  [West dominiert]
▲ Metall     West  52.1   BaZi  17.0   Δ+35.1  [West dominiert]
▲ Wasser     West  33.7   BaZi  10.2   Δ+23.5  [West dominiert]

───────────────────────────────────────────────────────
ENTWICKLUNGSFELDER  (beidseitig < 15 Pkt.)
───────────────────────────────────────────────────────
[leer — kein Element beidseitig unter 15 Pkt.]

───────────────────────────────────────────────────────
LEITFRAGEN
───────────────────────────────────────────────────────
Holz (Spannung −49.9 Pkt., BaZi dominiert):
  Deine innere Holz-Stärke übersteigt das, was der Himmel deiner Geburt
  anbot. Wo sucht diese Wachstumskraft einen Ausdruck, den sie noch
  nicht gefunden hat?
  [Sheng-Frage] Würde ein bewusster Schritt Richtung Feuer helfen,
  damit deine innere Holz-Stärke sichtbarer wird, ohne sich zu überdehnen?

Feuer (Spannung +27.2 Pkt., West dominiert):
  Der kosmische Moment bietet mehr Feuer-Energie, als deine innere
  Struktur aktuell trägt. Wo wartet ein Impuls von außen noch auf
  deine Annahme?
  [Sheng-Frage] Würde eine stärkere Verwurzelung in Holz helfen, damit
  der Feuer-Impuls von außen tragfähig wird und in Erde weiterfließen kann?

═══════════════════════════════════════════════════════
Indexpunkte = L2-Koordinaten × 100. Nicht additiv aufsummieren.
═══════════════════════════════════════════════════════
```

### Sheng-Zyklus als Leitfragen-Generator

Der Sheng-Zyklus (→ `docs/fusion/10_sheng_zyklus.md`) ist eine **feste Ordnung**,
kein zusätzliches Messsignal. Er wird in den Leitfragen als
Interpretationsstruktur genutzt — nicht als berechneter Kanal.

Für jedes TENSION-Element `E` mit Differenz `d`:

```
d > 0 (West dominiert):
  prev(E) → "Was stärkt die Basis, damit E tragfähig wird?"
  next(E) → "Wohin würde E weiterfließen, wenn es angenommen wird?"

d < 0 (BaZi dominiert):
  next(E) → "Was hilft E, sichtbarer zu werden, ohne sich zu überdehnen?"

Für DEVELOPMENT-Element E:
  prev(E) → "Würde ein Mikro-Schritt in prev(E) das E-Feld indirekt nähren?"
```

**Wichtig:** Diese Fragen sind explizit als `[Sheng-Frage]` gekennzeichnet —
sie sind Interpretation, keine Messung.

### Unterschied zu Logik A

| | Logik A (Narrativ) | Logik B (Diagnostisch) |
|---|---|---|
| **Zielgruppe** | Mystisch-symbolisch orientierte Nutzer | Analytisch-strukturierte Nutzer |
| **Sprache** | Metapher, Archetypus, Geschichte | Zone, Feld, Prozentsatz |
| **Offenheit** | Geschichte ist offen für Selbstdeutung | Karte ist offen für eigene Schlüsse |
| **Tiefe** | Verlangt astrologisches Vorwissen für volle Wirkung | Funktioniert ohne Vorkenntnisse |
| **Wiedererkennen** | "Das bin ich" (identifikatorisch) | "Das ist meine Situation" (situativ) |
| **Fehlerrisiko** | Archetyp kann falsch greifen | Karte kann korrekt aber bedeutungslos wirken |

---

## Kombinierte Anwendung: Beide Logiken als Paar

Die stärkste Anwendung nutzt **beide Logiken komplementär**:

```
1. Diagnostische Karte → Überblick der Topografie (2 Minuten lesen)
2. Narrative Deutung  → Geschichte, die die Topografie belebt (5 Minuten)
3. Leitfragen        → Übergang in persönliche Reflektion (offen)
```

Das entspricht der klassischen astrologischen Konsultationsstruktur:
Erst die objektive Kartendarstellung (Horoskop zeigen), dann die
narrative Deutung (Gespräch), dann die persönliche Frage.

---

## Anschlussfähigkeit zu den Traditionen

### Logik A: Narrative — westlicher Deutungskanon

Die narrative Deutung folgt der **psychologischen Astrologie** (Liz Greene,
Howard Sasportas, Robert Hand): das Horoskop als Spiegel des Charakters,
der Archetyp als Einladung, nicht als Schicksal. Die verwendeten Archetypen
(Leuchtturm, Anker, Alchemist) sind Jungsche Amplifikationen, die in der
modernen westlichen Astrologie kanonisch sind.

### Logik A: Narrative — BaZi-Deutungskanon

Die BaZi-Tradition hat ebenfalls eine narrative Schicht: Die zehn Götter
(十神, Shí Shén) sind archetypal — "Direkter Reichtum", "Essbarer Gott",
"Offizieller Gott" usw. Das Fusion-Narrativ kann diese Sprache spiegeln,
indem der dominante BaZi-Archetyp mit dem nächstverwandten der zehn Götter
assoziiert wird.

### Logik B: Diagnostisch — Klassische BaZi-Stärkeanalyse

Die Zone-Logik der diagnostischen Karte ist strukturell identisch mit der
klassischen BaZi-Analyse des **Kräftegleichgewichts (五行平衡)**:
- Welches Element ist überrepräsentiert? (→ Spannungsfeld)
- Welches Element fehlt? (→ Entwicklungsfeld)
- Welches ist im Gleichgewicht? (→ Stärkefeld)

Die diagnostische Karte ist damit eine mathematisch formalisierte Version
dessen, was ein erfahrener BaZi-Leser intuitiv tut.

### Logik B: Diagnostisch — Westliches Pendant

Die Kategorisierung in Stärke/Spannung/Entwicklung entspricht dem
**Stellarium-Ansatz** (Marc Edmund Jones) der Planetenmuster-Klassifikation
und dem **Quadrant-Dominanz-Konzept** der modernen Horoskop-Analyse.
Beide fragen: Wo ist die Energie konzentriert, und was fehlt?
