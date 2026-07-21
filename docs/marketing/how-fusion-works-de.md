# Wie FuFirE Fusion funktioniert — Die Mathematik hinter dem Kohärenz-Index

## Das Problem

Zwei jahrtausendealte Systeme beschreiben denselben Geburtsmoment in komplett unterschiedlichen Formaten. Westliche Astrologie: Planetenpositionen auf einem 360°-Kreis. BaZi (Vier Säulen des Schicksals): Himmelsstämme und Erdzweige aus einem 60er-Zyklus. Wie vergleicht man das?

## Schritt 1: Eine gemeinsame Sprache — Die Fünf Elemente

Beide Systeme lassen sich auf Wu-Xing (Fünf Elemente) abbilden: Holz, Feuer, Erde, Metall, Wasser.

**Westlich → Fünf Elemente:**

Jeder Planet hat eine feste Elementzuordnung nach klassischen Entsprechungen:

- Sonne → Feuer, Mond → Wasser, Merkur → Erde (Tagchart) oder Metall (Nachtchart)
- Venus → Metall, Mars → Feuer, Jupiter → Holz, Saturn → Erde
- Uranus → Holz, Neptun → Wasser, Pluto → Feuer

Jeder Planet wirft Gewicht 1.0 in den Topf seines Elements (rückläufig: 1.3×). Ergebnis: ein Vektor mit 5 Zahlen.

Beispiel:

```
Western-Vektor = [Holz: 3.3, Feuer: 2.0, Erde: 1.3, Metall: 2.0, Wasser: 3.0]
```

**BaZi → Fünf Elemente:**

Jede der 4 Säulen trägt bei durch:

- Himmelsstamm → direktes Element (Gewicht 1.0)
- Erdzweig → versteckte Stämme mit traditionellen Qi-Gewichten (Hauptqi: 1.0, Mittelqi: 0.5, Restqi: 0.3)

Beispiel:

```
BaZi-Vektor = [Holz: 1.5, Feuer: 2.8, Erde: 3.1, Metall: 1.3, Wasser: 2.0]
```

## Schritt 2: Die Verteilungen vergleichen

Jetzt haben wir zwei Vektoren im R^5 (fünfdimensionaler Raum). Uns interessiert nicht die absolute Menge, sondern die Form (Verteilung). Deshalb normalisieren wir beide auf Einheitslänge:

```
v_normalisiert = v / ||v||₂

wobei ||v||₂ = √(v₁² + v₂² + v₃² + v₄² + v₅²)
```

Dann messen wir den Winkel dazwischen mit der Kosinus-Ähnlichkeit:

```
H_roh = cos(θ) = (v_west · v_bazi) / (||v_west|| × ||v_bazi||)
```

H_roh = 1.0 → identische Verteilung. H_roh = 0.0 → komplett unterschiedliche Schwerpunkte.

## Schritt 3: Das Kalibrierungsproblem (Warum Rohwerte lügen)

Hier kommt die entscheidende Erkenntnis, die FuFirE von naiven Ansätzen unterscheidet:

Da alle fünf Werte positiv sind (man kann kein negatives Holz haben), zeigen zwei komplett zufällige Vektoren schon grob in die gleiche Richtung. Die erwartete Kosinus-Ähnlichkeit zweier Zufalls-Charts liegt bei ~0.45 bis 0.80, je nach Eingabedichte.

Ohne Korrektur würde fast jedes Chart-Paar „harmonisch" aussehen. Das wäre unehrlich.

## Schritt 4: Monte-Carlo-Kalibrierung

Wir haben 5.000 simulierte Zufalls-Chartpaare pro Dichtekonfiguration durchgerechnet (reproduzierbar: `python scripts/calibrate_baselines.py --seed 42`). Die Simulation verteilt n zufällige Beiträge gleichmäßig auf 5 Element-Töpfe und misst die Kosinus-Ähnlichkeit.

Ergebnisse (vollständige Tabelle):

| Western-Dichte | BaZi-Dichte | Erwartete Baseline | Standardabweichung |
|---|---|---|---|
| dünn (1-3 Planeten) | dünn (1-8 Qi) | 0.449 | 0.267 |
| dünn | mittel (9-16 Qi) | 0.524 | 0.208 |
| dünn | dicht (17+ Qi) | 0.546 | 0.176 |
| mittel (4-8 Planeten) | dünn | 0.609 | 0.215 |
| mittel | mittel | 0.690 | 0.176 |
| mittel | dicht | 0.727 | 0.150 |
| dicht (9+ Planeten) | dünn | 0.665 | 0.187 |
| dicht | mittel | 0.761 | 0.145 |
| dicht | dicht | 0.796 | 0.122 |

## Schritt 5: Der kalibrierte Kohärenz-Index

Der finale Score misst, wie weit DEIN Chart über der Zufalls-Baseline liegt:

```
H_kalibriert = max(0, (H_roh - H_baseline) / (1 - H_baseline))
```

- H_kalibriert = 0.0 → „Dein Chart ist genau so ähnlich wie zwei Zufalls-Charts"
- H_kalibriert = 0.5 → „Auf halbem Weg zwischen Zufall und perfekter Übereinstimmung"
- H_kalibriert = 1.0 → „Maximale strukturelle Kongruenz"

### Rechenbeispiel

Berlin, 10. Februar 2024, 14:30 MEZ:

- H_roh = 0.84 (klingt beeindruckend!)
- H_baseline = 0.796 (aber zufällige dichte Charts liegen im Schnitt bei 0.80)
- H_kalibriert = (0.84 - 0.796) / (1 - 0.796) = 0.22
- Interpretation: moderate Übereinstimmung — 22% über dem, was der Zufall erwarten lässt

## Was das bedeutet (und was nicht)

**Was gemessen wird:** Der Grad, zu dem dein westliches Planetenchart und dein chinesisches BaZi-Chart dieselben Elemente betonen — über das hinaus, was der Zufall erklären würde.

**Was NICHT behauptet wird:**

- Es beweist nicht, dass Astrologie „funktioniert"
- Es sagt nicht deine Zukunft voraus
- Es behauptet nicht, dass die zwei Systeme übereinstimmen „sollten"
- Es ist eine mathematische Messung, kein spirituelles Urteil

**Was es ehrlich macht:**

- Jede Berechnung ist deterministisch (gleiche Eingabe = gleiche Ausgabe, immer)
- Jeder Beitrag wird in einem Ledger protokolliert (du kannst sehen, welcher Planet oder Stamm was beigetragen hat)
- Die Kalibrierung ist reproduzierbar (du kannst die Simulation selbst ausführen)
- Der Quellcode ist überprüfbar

## Das Contribution Ledger (Beitragsprotokoll)

Jede API-Antwort enthält eine vollständige Audit-Spur. Für jedes Element in jedem Vektor kannst du sehen:

- Welcher Planet/Stamm/Zweig beigetragen hat
- Wie viel Gewicht (1.0 Standard, 1.3 rückläufig, 0.5 Mittelqi, 0.3 Restqi)
- Warum (klassische Zuordnung, sektabhängige Merkur-Dualregel, versteckte-Stämme-Tradition)

Du musst also nie einer Blackbox vertrauen. Du kannst jede Zahl nachprüfen.

## Wahre Sonnenzeit-Korrektur

Ein wichtiges Detail: BaZi-Stundensäulen hängen davon ab, wann die Sonne tatsächlich über dem Geburtsort steht — nicht was die Uhr sagt. Eine Person, die um 14:30 Uhr in Westspanien geboren wird (Zeitzonenmeridian bei 15°O, tatsächlicher Standort bei -8°W), hat eine wahre Sonnenzeit von ungefähr 1,5 Stunden früher.

FuFirE wendet die Zeitgleichung (saisonale Korrektur, ±16,4 Minuten) und eine Längengrad-Korrektur (4 Minuten pro Grad Abweichung vom Zeitzonenmeridian) an, um sicherzustellen, dass die BaZi-Seite der Fusion astronomisch korrekte Zeit verwendet.

## Reproduzierbarkeit

Alles hier Beschriebene kann unabhängig verifiziert werden:

- Kalibrierung: `python scripts/calibrate_baselines.py --trials 5000 --seed 42`
- Vollständige Ergebnisse: `docs/calibration-results.json`
- Quellcode: offen zur Überprüfung
- API-Antworten: enthalten Provenance-Metadaten (Engine-Version, Ephemeris-Backend, Parameter-Set)

---

*FuFirE — Fusion Firmament Engine. Transparent by Design.*
