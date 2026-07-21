# 09 — Nutzertest-Design: Messung astrologischer Deutungswirkung

---

## Was getestet wird

Zwei Deutungslogiken (→ Dok 08) werden auf ihre **Wirksamkeit beim Nutzer** geprüft.
Wirksamkeit hat drei Dimensionen:

1. **Treffsicherheit** — Erkennt der Nutzer sich in der Deutung wieder?
2. **Verständlichkeit** — Kann der Nutzer die Deutung ohne Vorkenntnisse lesen?
3. **Handlungsrelevanz** — Verändert die Deutung etwas im Denken oder Verhalten?

---

## Testdesign

### A/B-Test mit innersubjektem Vergleich

Jeder Nutzer bekommt **beide** Logiken — in zufälliger Reihenfolge.
Kein Nutzer weiß, dass es zwei verschiedene Logiken gibt.

```
Gruppe 1: Logik A zuerst → Logik B
Gruppe 2: Logik B zuerst → Logik A
```

Damit kontrollieren wir den Reihenfolgeeffekt (die erste Deutung wirkt
als Anker für die zweite).

### Voraussetzungen

- Geburtsdatum, -uhrzeit, -ort des Nutzers (für echte Berechnungen)
- Keine astrologischen Vorkenntnisse erforderlich (aber interessant zu erheben)

---

## Fragebogen

### Block 0: Screening (vor der Deutung)

Wird nicht als Fragebogen präsentiert, sondern als Teil der Dateneingabe.

```
1. Geburtsdatum, Uhrzeit, Ort (Pflichtfeld)
2. Wie vertraut bist du mit westlicher Astrologie?
   [Keine Ahnung | Gelegentlich gelesen | Regelmäßig | Professionell]
3. Wie vertraut bist du mit chinesischer Astrologie / BaZi?
   [Keine Ahnung | Gelegentlich gelesen | Regelmäßig | Professionell]
4. Was erhoffst du dir von dieser Analyse?
   [Offenes Textfeld, max. 200 Zeichen]
```

---

### Block 1: Erste Deutung (Logik A oder B, randomisiert)

*Nutzer liest die Deutung. Dann:*

**1.1 Treffsicherheit**
```
Wie sehr erkennst du dich in dieser Beschreibung wieder?
○ Kaum       (1)
○ Ein wenig  (2)
○ Teilweise  (3)
○ Gut        (4)
○ Sehr gut   (5)
```

**1.2 Überraschung**
```
Hat die Beschreibung etwas enthalten, das dich überrascht hat?
○ Gar nicht
○ Ja, ein kleines Detail
○ Ja, etwas Wichtiges
○ Ja, es war das Überraschendste
[Wenn Überraschung ≥ 2]: Was hat dich überrascht? [Freitext]
```

**1.3 Verständlichkeit**
```
War die Beschreibung verständlich ohne Vorkenntnisse?
○ Nein, ich habe vieles nicht verstanden
○ Teilweise — einige Begriffe unklar
○ Ja, gut verständlich
○ Ja, sehr klar
```

**1.4 Emotionale Resonanz**
```
Wie hast du dich beim Lesen gefühlt?
[Mehrfachauswahl möglich]
□ Neugierig
□ Bestätigt
□ Skeptisch
□ Berührt
□ Verstanden
□ Fremd/distanziert
□ Anderes: [Freitext]
```

**1.5 Nützlichkeit**
```
Wie nützlich ist diese Beschreibung für dein Verständnis von dir selbst?
○ Nicht nützlich
○ Eher nicht nützlich
○ Teilweise nützlich
○ Nützlich
○ Sehr nützlich
```

---

### Block 2: Zweite Deutung (andere Logik)

*Dieselben Fragen 1.1–1.5, für die zweite Deutung.*

---

### Block 3: Vergleich der beiden Deutungen

**3.1 Präferenz**
```
Welche Beschreibung hat dich mehr angesprochen?
○ Die erste
○ Die zweite
○ Beide gleich
○ Keine von beiden
```

**3.2 Komplementarität**
```
Haben die beiden Beschreibungen sich ergänzt?
○ Ja, sie haben verschiedene Dinge beschrieben
○ Ja, sie sagten dasselbe, aber anders
○ Nein, sie haben sich widersprochen
○ Nein, sie haben dasselbe gesagt
```

**3.3 Gesamteindruck**
```
Was würdest du dir bei einer solchen Analyse wünschen,
das du noch nicht bekommen hast? [Freitext, max. 500 Zeichen]
```

---

### Block 4: Validierungsfragen (nach beiden Deutungen)

Diese Fragen testen, ob die Deutung astrologisch korrekt "gelesen" wird.

**4.1 Dominantes Element — Selbstwahrnehmung**
```
Welches der fünf Elemente beschreibt dich deiner Meinung nach am besten?
○ Holz  (Wachstum, Aufbruch, Visionär)
○ Feuer (Ausdruck, Verbindung, Vitalität)
○ Erde  (Stabilität, Form, Verlässlichkeit)
○ Metall (Klarheit, Distinktion, Präzision)
○ Wasser (Tiefe, Intuition, Anpassung)
```

*Validierung:* Stimmt die Selbstwahrnehmung mit dem dominant_bazi_element überein?

**4.2 Harmony Index — Subjektive Entsprechung**
```
Wie stimmig fühlst du dich normalerweise — d.h. wie sehr
"passen" inneres Erleben und äußeres Auftreten für dich zusammen?
○ Sehr wenig (1)
○ Wenig (2)
○ Mittel (3)
○ Gut (4)
○ Sehr gut (5)
```

*Validierung:* Korreliert diese Selbsteinschätzung mit dem berechneten H?

**4.3 Entwicklungsfeld**
```
In welchem Bereich arbeitest du gerade aktiv an dir?
[Freitext oder Mehrfachauswahl, offenes Coding im Auswertungsschritt]
```

---

### Block 5: Demographische Variablen (optional, kurz)

```
Alter: [Dropdown 5-Jahres-Gruppen]
Geschlecht: [offen]
Hauptsprache: [offen]
Professioneller Kontext mit Astrologie: Ja / Nein
```

---

## Auswertungsplan

### Primäre Metriken (pro Logik)

| Metrik | Berechnung | Zielwert |
|---|---|---|
| Treffsicherheitsrate | Ø Item 1.1 | ≥ 3.5 / 5 |
| Verständlichkeitsrate | % Antworten "gut/sehr klar" Item 1.3 | ≥ 70% |
| Nützlichkeitsrate | % Antworten "nützlich/sehr nützlich" | ≥ 60% |
| Präferenzrate (im Vergleich) | % Item 3.1 | Signifikanztest |

### Sekundäre Validierung

| Test | Variable A | Variable B | Methode |
|---|---|---|---|
| Dominant-Element-Validierung | Selbstwahrnehmung (4.1) | dominant_bazi_element | κ (Cohen's Kappa) |
| Harmony-Index-Korrelation | Stimmigkeit (4.2) | H | Spearman ρ |
| Vorwissens-Moderationseffekt | Treffsicherheit (1.1) | Astro-Vorwissen (0.3) | Moderationsanalyse |

### Qualitative Auswertung

Freitextantworten (1.2, 3.3, 4.3) werden thematisch kodiert:
- Welche Formulierungen lösen Wiedererkennung aus?
- Welche Begriffe erzeugen Unverständnis?
- Welche Entwicklungsfelder werden spontan genannt?

---

## Stichprobengröße

Für belastbare Aussagen zu Logik A vs. B:
- **Mindestens 30 Nutzer** pro Gruppe (60 gesamt) für erste Richtwerte
- **100+ Nutzer** für Korrelationsanalysen (Harmony Index vs. Stimmigkeit)

Für die Validieurng des Dominant-Element-Mappings:
- Alle 5 Elemente müssen in der Stichprobe vertreten sein
- → Mindestens 10 Nutzer pro dominantes Element (50 gesamt)

---

## Ethische Rahmung

- Nutzer werden informiert, dass Geburtsdaten nur für die Analyse genutzt werden
- Keine persistente Speicherung ohne explizite Einwilligung
- Deutungen enthalten **keine Vorhersagen** und keine medizinischen/rechtlichen Aussagen
- Framing: "Wir testen ein mathematisches Werkzeug, das astrologische Traditionen verbindet. Wir möchten wissen, ob es für dich bedeutungsvoll ist."
