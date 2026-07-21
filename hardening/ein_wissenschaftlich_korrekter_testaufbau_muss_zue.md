Ein wissenschaftlich korrekter Testaufbau muss zuerst eine unangenehme, aber zentrale Trennung machen:

**1. Was ist in der vorhandenen FuFirE-/Fusion-Dokumentation als Kern wirklich belegt?**

**2. Was ist nur eine plausible Erweiterungshypothese aus dem langen Essay?**

In den geladenen Kerndokumenten ist der belegte Kern klar: westliche Astrologie plus BaZi werden in einem gemeinsamen 5D-Wu-Xing-Raum verarbeitet; dokumentiert sind Zeitkorrektur, Vektorgeometrie, Harmony Index und eine deterministische, zustandslose Orchestrierung. Kreuzkorrelationsmatrizen fuer tiefe Synastrie, asymmetrische Fuzzy-Orbs und grossskalige Impact-Score-Filter sind in dieser Kernuebersicht dagegen **nicht** als dokumentierter Basisumfang sichtbar. Der Testplan muss diese Dinge daher als **separat zu pruefende Module/Hypothesen** behandeln, nicht als bereits bewiesene Engine-Eigenschaften.

README

Dazu passt auch die Produktlogik in den internen Unterlagen: Die Plattform will Praezision im Kern haben, diese aber als klare Nutzererfahrung uebersetzen, statt den Nutzer mit Mathematik zu ueberfrachten. Entsprechend sind im Risk Framework bereits wahrnehmbare Metriken wie Precision-Badge-Interaktion, D7/D30-Retention und die Aussage „accurate than other apps“ als relevante Erfolgsmasse definiert.

Bazodiac_Risk_Framework_2026

Die User Journey stuetzt das: exakte Geburtsdaten, Julian Date, Delta T, EoT/True Solar Time, Wu-Xing-Mapping, Harmony Index und anschliessend eine resource-oriented Experience statt Fatalismus.

full_user_journey_through_the_a…

---

# Ziel des Testaufbaus

Der Testaufbau soll **nicht** „Astrologie als Ganzes beweisen“.

Er soll vier engere, sauber pruefbare Fragen beantworten:

**Engine-Korrektheit:** Rechnet der deterministische Kern stabil, reproduzierbar und grenzfallfest?

**Algorithmischer Mehrwert:** Erzeugen Aggregationslogik, Matrixmethoden, Orbengewichtung und Impact-Scoring gegenueber einfachen Baselines einen messbaren Zusatznutzen?

**Narrativer Mehrwert:** Fuehren NLP-Filter und Ranglogik zu besseren, faktenkonsistenteren und als relevanter wahrgenommenen Outputs?

**Informationsforensik:** Kann das System Eigennamen- und Retrieval-Rauschen rund um „FuFirE“ sauber vom eigentlichen Forschungsgegenstand trennen?

---

# Testarchitektur in 5 Arbeitspaketen

## Arbeitspaket A – Deterministischer Kern: mathematische Korrektheit

### Zweck

Pruefen, ob der belegte FuFirE-Kern technisch das tut, was er laut Doku tun soll: deterministisch, zustandslos, praezise und reproduzierbar.

README

### Hypothesen

**H-A1:** Identische Inputs erzeugen identische Outputs.

**H-A2:** Zeit- und Grenzfalllogik bleibt stabil an kritischen Schwellen:

DST-Uebergaenge

Mitternacht

Li Chun

Jie-Qi-Monatsgrenzen

hohe/ungewoehnliche Breitengrade

**H-A3:** Abweichungen gegen Referenzimplementierungen bleiben innerhalb vorher definierter Toleranzen.

### Testdaten

**Synthetische Grenzfalldaten**

Geburten +/- 60 min um DST-Spruenge

Geburten +/- 24 h um Li Chun

Geburten genau auf 15°-Solarterm-Grenzen

extreme Laengen-/Breitengrade

**Monte-Carlo-Sample**

z. B. 10k zufaellige Geburtszeitpunkte/Orte

**Goldstandard-Sample**

Referenzberechnungen mit explizit fixierter Swiss-Ephemeris-/Referenzkonfiguration

### Metriken

Reproduzierbarkeit: Hash-identischer Output bei Wiederholung

Numerische Abweichung:

Sonnenlaenge

Pillar-Wechsel korrekt/inkorrekt

Harmony Index Delta

Grenzfall-Fehlerrate

Fehlklassifikationsrate an Jahres-/Monats-/Stundenwechseln

### Erfolgskriterien

100 % Reproduzierbarkeit bei identischer Runtime-Konfiguration

0 stiller Wechsel des Output-Typs

< 0,1 % Grenzfall-Fehler im validierten Sample

dokumentierte Toleranzfenster pro Kennzahl

### Transparenzregel

Jeder Testlauf speichert:

Code-Commit

Ephemeris-Version

Runtime-Flags

Timezone-Datenstand

Seed

Testdaten-Version

---

## Arbeitspaket B – Aggregationslogik und Matrixalgebra

Hier beginnt der eigentliche Werttest.

## Wichtige methodische Korrektur

Wenn du Begriffe wie **Kreuzkorrelationsmatrix**, **tiefe Synastrie**, **asymmetrische Fuzzy-Orbs** oder **Impact-Scoring** testest, brauchst du zunaechst eine **Baseline-Familie**. Sonst pruefst du nur, ob ein komplexes Modell komplex ist.

### Zu testende Modellfamilien

Mindestens vier Stufen:

**B0 Minimalbaseline**

Einfache additive Heuristik ohne Matrix, ohne Fuzzy-Orb, ohne Learned Ranking

**B1 Matrix only**

Kreuzkorrelations-/Gewichtungsmatrix, aber keine Fuzzy-Orbs

**B2 Matrix + Fuzzy-Orb**

gleiche Matrix, zusaetzlich kontinuierliche Orbengewichtung

**B3 Matrix + Fuzzy-Orb + Impact-Ranking**

Vollmodell mit Priorisierung fuer Front-End-Ausgabe

### B1. Synastrie / Kreuzkorrelationslogik

#### Hypothesen

**H-B1:** Eine strukturierte Matrixlogik erzeugt relevantere Paar-Ausgaben als simple additive Aspekte.

**H-B2:** Die zusaetzliche Modellkomplexitaet fuehrt nicht zu schlechterer Kalibrierung oder schlechterer Erklaerbarkeit.

#### Datensaetze

Nicht „wahre Beziehungsqualitaet“ als ontologischer Fakt testen. Das waere wissenschaftlich ueberzogen. Stattdessen drei Label-Ebenen:

**Expertenpanel-Labels**

Astrologie-experten bewerten 300-500 anonymisierte Paare auf Relevanz/innere Koharenz

**User-perceived relevance**

Nutzer beurteilen, ob ein Pairing-Report „relevant“, „hilfreich“, „zu generisch“, „off“ ist

**Behavioral proxy**

Scroll depth

Save/share rate

Return-to-report rate

Purchase/upgrade propensity

#### Metriken

NDCG@k / MAP fuer Report-Ranking

User rating mean

Experten-Konsens vs Modellscore

Inter-rater agreement (Cohen/Fleiss Kappa)

Calibration curve: hoher Score -> tatsaechlich hoeher bewertete Relevanz?

#### Erfolgskriterium

B2 oder B3 muss gegen B0 mindestens in **zwei** der drei Ebenen besser sein:

Expertenrelevanz

Nutzerrelevanz

Verhalten

Sonst ist die zusaetzliche Komplexitaet nicht gerechtfertigt.

---

### B2. Asymmetrische Fuzzy-Orb-Gewichtung

#### Hypothesen

**H-B3:** Kontinuierliche Orbengewichtung schlaegt harte Schwellwerte.

**H-B4:** Asymmetrie pro Aspekt/Planet verbessert die Kalibrierung gegenueber symmetrischen Standard-Orbs.

#### Testdesign

Vergleiche:

**C0:** harter Orb-Cutoff

**C1:** symmetrische kontinuierliche Funktion

**C2:** asymmetrische kontinuierliche Funktion

#### Metriken

Rank correlation zwischen Modellstärke und Expertenrating

Brier Score / ECE fuer Kalibrierung

Output-Stabilitaet bei kleinen Inputaenderungen

Sensitivitaet an Grenzfaellen

#### Kritische Transparenzregel

Die gewaehlte Dichtefunktion und alle Parameter muessen **vorab festgelegt** werden.

Kein nachtraegliches Kurven-Tuning auf Basis der Ergebnisse.

---

### B3. Impact-Scoring und parallele Front-End-Filterung

Das ist marktrelevant, weil nicht alle berechneten Konstellationen dem Nutzer gezeigt werden koennen.

#### Hypothesen

**H-B5:** Impact-Scoring liefert hoehere wahrgenommene Relevanz als naive Top-N-Auswahl.

**H-B6:** Mehr parallele Signale steigern Relevanz nur bis zu einem Sättigungspunkt; darueber sinkt Klarheit.

#### Kandidatenmodelle

**R0:** Top-N nach absoluter Staerke

**R1:** Top-N nach Staerke x Seltenheit

**R2:** Top-N nach Staerke x Seltenheit x Person-Context

**R3:** Top-N nach vollem Impact-Score mit Context + Novelty + confidence penalty

#### Offline-Datensatz

Fuer jeden User-Zeitpunkt:

50-500 berechnete potenzielle Signale

Experten-/User-Labels fuer „should surface“ vs „should not surface“

#### Online-A/B-Test

Randomisierte Ausgabe:

Arm A: R0

Arm B: R2

Arm C: R3

#### Primäre Metriken

CTR auf surfaced insight

dwell time

save rate

next-day return

perceived relevance

overload rate („too much“, „too vague“, „not me“)

#### Sekundaere Metriken

D7 retention

premium conversion

daily open rate

Das knuepft direkt an das Risk Framework an, das Onboarding, wahrgenommene Genauigkeit, D7/D30-Retention und Companion-Nutzung bereits als zentrale Entscheidungsmasse definiert.

Bazodiac_Risk_Framework_2026

---

## Arbeitspaket C – NLP-Filter und semantische Synthese

Hier muss die Pruefung sehr sauber formuliert werden.

### Nicht testen

Nicht: „Ist der Text wahr?“ im metaphysischen Sinn.

### Testen

faktische Konsistenz zum Engine-Output

Widerspruchsfreiheit

Uebertreibungsgrad

Nuetzlichkeit

wahrgenommene Personalisierung

sprachliche Klarheit

### Hypothesen

**H-C1:** NLP-Filter reduzieren Widersprueche gegen structured output.

**H-C2:** gefilterte Texte werden als hilfreicher und weniger generisch bewertet.

**H-C3:** mehr Narrativ darf die Faktentreue nicht senken.

### Testarme

**N0:** reiner structured output ohne Narrative

**N1:** Template-basierte Narrativisierung

**N2:** LLM-Narrativisierung ohne Guardrails

**N3:** LLM-Narrativisierung mit Guardrails/Fact-binding

### Metriken

factual consistency audit

contradiction rate

unsupported claim rate

readability

helpfulness rating

personalization rating

trust rating

### Bewertungsprozess

doppelt verblindetes Human Rating

zusaetzlich regelbasierter Fact-Check gegen JSON source-of-truth

Fail-fast-Kriterium: jeder Text mit harter Faktabweichung zaehlt als Fehler, auch wenn er „schoen“ klingt

---

## Arbeitspaket D – Informationsforensik und Suchraum-Hygiene

Diesen Teil solltest du **nicht** mit dem Engine-Test vermischen, sondern als eigenes Modul behandeln.

### Ziel

Pruefen, ob Recherchen, Knowledge Retrieval und Markenbeobachtung zu „FuFirE“ sauber gegen Rauschen abgeschirmt werden koennen.

### Testdatensatz

Baue einen kontrollierten Korpus mit vier Klassen:

**D1 True positive**

echte Bazodiac/FuFirE/Fusion-Unterlagen

**D2 OCR-noise**

future/fufire/Fuhre-Artefakte

**D3 aerospace collision**

SpaceX static fire / rocket engine

**D4 unrelated semantic neighbors**

mobile repair, local place names etc.

### Hypothesen

**H-D1:** Ein diszipliniertes Query-/Filter-Schema erhoeht Precision signifikant.

**H-D2:** False positives koennen unter einen akzeptablen Schwellwert gesenkt werden, ohne Recall zu zerstoeren.

### Testvarianten

naive keyword search

keyword + ontology filters

entity resolution + source whitelisting

reranker mit domain classifier

### Metriken

Precision@k

Recall@k

false positive rate

contamination rate

analyst time to clean set

### Erfolgskriterium

Die produktive Recherche-Pipeline sollte:

hohe Precision erzielen

weniger analyst cleanup benoetigen

dokumentiert begruenden koennen, warum etwas als irrelevant ausgeschlossen wurde

---

## Arbeitspaket E – Markt- und Nutzerwirksamkeit

Das ist der letzte, aber geschaeftlich wichtigste Block.

Die internen Unterlagen sagen sehr deutlich: Das Risiko ist nicht nur, ob die Engine stark ist, sondern ob Nutzer diese Praezision als Mehrwert **wahrnehmen**. Precision Badge, wahrgenommene Genauigkeit, D7/D30-Retention, Companion-Nutzung und WTP sind bereits als Entscheidungsachsen formuliert.

Bazodiac_Risk_Framework_2026

Daher muss der Testaufbau zwei Ebenen verbinden:

### E1. Wahrgenommene Glaubwuerdigkeit

Hypothese:

**H-E1:** Sichtbar gemachte Praezision steigert Vertrauen und Relevanzwahrnehmung.

Testarme:

ohne Precision Proof

mit Precision Badge

mit Delta-Visualisierung

mit Vergleichs-Hook

Metriken:

tap rate

trust rating

“more accurate than other apps”

onboarding completion

report completion

### E2. Zahlungsbereitschaft

Hypothese:

**H-E2:** das framework-curious Segment zahlt fuer Tiefe mehr als entertainment-only Nutzer.

Testdesign:

Free / Essentials / Premium

EN vs DE

rational framing vs emotional framing

Metriken:

pricing page tap

trial start

trial-to-paid

M1 churn

ARPU

DE vs EN delta

Die Ziel- und Kill-Werte koennen direkt aus dem Risk Framework uebernommen werden, weil sie bereits als vorab definierte Entscheidungsregeln formuliert sind.

Bazodiac_Risk_Framework_2026

---

# Gesamtaufbau als Studienprogramm

## Phase 1 – Offline Science Layer

Dauer: 3-5 Wochen

Enthaelt:

Determinismus- und Genauigkeitstests

Ablationsstudien fuer Matrix/Fuzzy/Impact

NLP fact-consistency tests

Retrieval contamination benchmark

Output:

technischer Validierungsbericht

Hypothesenstatus pro Modul

Liste „belegt / plausibel / verworfen“

## Phase 2 – Shadow Mode

Dauer: 2-4 Wochen

Enthaelt:

neue Ranking-/Filtermodelle laufen verdeckt mit

Nutzer sehen noch nur aktuelles Modell

Vergleich von Scores, Selektionen, Stabilitaet, Latenz

Output:

Online-Kompatibilitaet

Rechenkosten

Abweichungsanalyse

## Phase 3 – Randomisierte Produkt-Experimente

Dauer: 8-12 Wochen

Enthaelt:

Precision Proof

Surface Ranking

NLP narrative arms

Pricing / WTP arms

Output:

D7/D30

NPS / perceived accuracy

conversion / churn

kill / continue Entscheidung

---

# Harte methodische Regeln

**Pre-Registration**

Hypothesen, Metriken, Auswertungslogik und Kill-Kriterien vor Start fixieren.

**Keine Metric Hopping**

Keine Zielwechsel nach Tag 30, 60 oder 90.

**Ablation first**

Komplexe Modelle muessen immer gegen einfache Baselines antreten.

**Truthfulness by layer**

mathematische Schicht: numerisch pruefen

Ranking-Schicht: gegen Labels pruefen

NLP-Schicht: gegen Structured Facts pruefen

Markt-Schicht: gegen Verhalten pruefen

**Keine ontologischen Ueberclaims**

Testbar ist Reproduzierbarkeit, Relevanz, Kalibrierung, Wahrnehmung und Marktfit.

Nicht testbar ist „objektive Wahrheit astrologischer Deutung“ im starken Sinn.

**Reproducibility Pack**

Jeder Testbericht braucht:

Datensatzversion

Code-Commit

Seed

Konfiguration

Metrikdefinition

Ausschlussregeln

Fehlerlog

---

# Konkrete Deliverables

Ich wuerde den Testaufbau in diese 8 Artefakte zerlegen:

**Hypothesenregister**

ID

Aussage

Modul

Status

Metriken

Kill-Regel

**Benchmark-Katalog**

A: deterministic core

B: aggregation/synastry

C: NLP

D: retrieval hygiene

E: market perception

**Goldensatz fuer Grenzfaelle**

DST

Li Chun

solar terms

latitude extremes

**Labeling Guide**

Expertenrating

Nutzerrating

Behavioral proxy definition

**Experiment Registry**

Arm-Definition

Sample rule

Runtime flag

Analysis plan

**Dashboard**

engine correctness

ranking lift

NLP consistency

contamination rate

D7/D30

conversion

**Decision Log**

review day 14/30/60/90

continue / warn / kill

**Finaler Validation Report**

belegt

nicht belegt

verbessert

verworfen

produktreif / nicht produktreif

---

# Mein klares Urteil

Der sauberste wissenschaftliche Aufbau ist **nicht** ein grosser Einheits-Test.

Er ist ein **mehrschichtiger Validierungsrahmen**:

**Schicht 1:** deterministische Mathematik

**Schicht 2:** algorithmischer Zusatznutzen

**Schicht 3:** narrative Faktentreue

**Schicht 4:** Informationsforensik

**Schicht 5:** Markt- und Nutzersignal

Und noch wichtiger:

Alles, was im langen Essay als Kreuzkorrelationsmatrix, asymmetrische Fuzzy-Orb-Logik oder hochdimensionale Impact-Filter beschrieben wird, darf im Testplan nur dann als „Engine-Funktion“ erscheinen, wenn es im realen Code oder in belastbaren Spezifikationen auch wirklich vorhanden ist. Sonst muss es als experimentelle Hypothese laufen.

Genau das macht den Plan wissenschaftlich korrekt und transparent.
