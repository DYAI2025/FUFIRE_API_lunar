# Repo-Analyse & Funktionsweise (FuFirE — Fusion Firmament Engine)

## Überblick

Dieses Repository stellt eine FastAPI-Anwendung bereit, die BaZi (Vier Säulen), westliche Astrologie (Swiss Ephemeris) und eine Fusionslogik (Wu‑Xing‑Vektoren + Kohärenz-Index) kombiniert. Die Kernlogik liegt in `bazi_engine/` und wird in `bazi_engine/app.py` als HTTP‑API veröffentlicht. Die Anwendung setzt auf Swiss Ephemeris und erwartet lokale Ephemeriden-Dateien (keine impliziten Downloads zur Laufzeit).【F:bazi_engine/app.py†L1-L616】【F:bazi_engine/ephemeris.py†L1-L107】

## BaZi‑Berechnung (Vier Säulen)

Die BaZi‑Berechnung in `bazi_engine/bazi.py` läuft in diesen Schritten:

1. **Zeitzonen-/Zeitanpassung**: Eingabezeit wird mit `parse_local_iso` geparst und über `to_chart_local` (LMT/CIVIL) in die Chart‑Lokalzeit sowie UTC transformiert.【F:bazi_engine/bazi.py†L63-L74】
2. **Ephemeris‑Backend**: Es wird `SwissEphBackend` verwendet; andere Backends sind nicht implementiert (siehe Schutz in `compute_bazi`).【F:bazi_engine/bazi.py†L52-L56】
3. **LiChun‑Anker**: Jahreswechsel wird über LiChun (315° Sonnen‑Longitude) bestimmt; daraus ergibt sich das Solarjahr und die Jahres‑Säule.【F:bazi_engine/bazi.py†L40-L92】
4. **Monats‑Säulen**: Monatsgrenzen werden über LiChun → nächstes LiChun bestimmt und daraus Monatssäulen abgeleitet.【F:bazi_engine/bazi.py†L94-L108】
5. **Tagssäule**: Tag wird über konfigurierbare Day‑Boundary berechnet, optional mit Anker‑Datum/Offset für die Sexagenary‑Reihe.【F:bazi_engine/bazi.py†L111-L129】
6. **Stundensäule**: Stundenzweig aus lokaler Zeit (2‑Stunden‑Segmente), Stundestamm aus Tagstamm berechnet.【F:bazi_engine/bazi.py†L31-L36】【F:bazi_engine/bazi.py†L131-L137】
7. **Diagnostik**: Optional werden die 24 Solartermine im LiChun‑Fenster berechnet und mitgegeben (für Validierung/Diagnose).【F:bazi_engine/bazi.py†L141-L170】

## Westliche Chart‑Berechnung (Swiss Ephemeris)

Die westliche Chart‑Berechnung ist in `bazi_engine/western.py` implementiert:

- **Planetenpositionen**: Swiss Ephemeris wird via `swe.calc_ut` aufgerufen; es werden Longituden, Geschwindigkeiten, Retrograde‑Status, und Tierkreiszeichen berechnet.【F:bazi_engine/western.py†L35-L74】
- **Häuser/Angles**: Standardmäßig Placidus, mit Fallbacks auf Porphyry und Whole Sign; die API gibt zusätzlich Ascendant/MC/Vertex aus.【F:bazi_engine/western.py†L77-L120】

## Ephemeriden‑Handling

`bazi_engine/ephemeris.py` erzwingt, dass lokale Ephemeriden-Dateien vorliegen. Es gibt **keine** impliziten Downloads bei Start oder Berechnung; fehlende Dateien führen zu einem `FileNotFoundError`. Standardpfad ist `~/.cache/bazi_engine/swisseph` oder der Pfad aus `SE_EPHE_PATH`.【F:bazi_engine/ephemeris.py†L10-L107】

## Fusionslogik (Wu‑Xing & Kohärenz-Index)

Die Fusion findet in `bazi_engine/fusion.py` statt:

- **Planeten → Wu‑Xing**: Planeten werden über eine feste Zuordnung auf Elemente gemappt (Mercury dual, tag/nacht‑abhängig).【F:bazi_engine/fusion.py†L12-L79】
- **Wu‑Xing‑Vektoren**: Für westliche Planeten wird ein Vektor erstellt, retrograde Planeten erhalten eine stärkere Gewichtung.【F:bazi_engine/fusion.py†L82-L138】
- **BaZi → Wu‑Xing**: Stämme liefern ein Element, Zweige liefern versteckte Elemente mit Gewichtung.【F:bazi_engine/fusion.py†L169-L252】
- **Kohärenz-Index**: Ähnlichkeit der normierten Vektoren (Dot Product / Cosine) erzeugt einen Skalar (0–1) mit Interpretation.【F:bazi_engine/fusion.py†L255-L314】
- **Gesamtanalyse**: `compute_fusion_analysis` liefert Vektoren, Kohärenz-Index, Element‑Vergleich, Cosmic‑State und Interpretationstext.【F:bazi_engine/fusion.py†L427-L495】

## HTTP‑API: Endpunkte & Requests

Die API ist in `bazi_engine/app.py` definiert. Die wichtigsten Endpunkte sind:

### Basis & Gesundheit
- `GET /` → Status/Version。【F:bazi_engine/app.py†L131-L133】
- `GET /health` → Health‑Check.【F:bazi_engine/app.py†L135-L137】

### Validierung
- `POST /validate` → Request‑Schema‑Validierung (Bafe‑Validator).【F:bazi_engine/app.py†L140-L150】

### Minimaler Western‑Sign‑Check
- `GET /api` → berechnet Sonnenzeichen aus Datum/Zeit/Ort (Query‑Parameter).【F:bazi_engine/app.py†L153-L194】

### BaZi
- `POST /calculate/bazi` → Vier‑Säulen‑Berechnung inkl. LiChun‑Datum und optionaler Solarterme.【F:bazi_engine/app.py†L196-L237】

### Western Chart
- `POST /calculate/western` → Planeten, Häuser, Winkel (Swiss Ephemeris).【F:bazi_engine/app.py†L239-L261】

### Fusion (BaZi + Western)
- `POST /calculate/fusion` → kombiniert BaZi‑Pfeiler + Western‑Planeten zu Harmonie‑Index/Interpretation.【F:bazi_engine/app.py†L274-L332】

### Wu‑Xing‑Vektor nur aus Western‑Planeten
- `POST /calculate/wuxing` → Element‑Vektor, dominantes Element, Gleichung der Zeit, TST.【F:bazi_engine/app.py†L335-L387】

### True Solar Time
- `POST /calculate/tst` → TST‑Berechnung als eigenständiger Service.【F:bazi_engine/app.py†L390-L439】

### Mapping Info
- `GET /info/wuxing-mapping` → Planet‑zu‑Element‑Mapping + Reihenfolge.【F:bazi_engine/app.py†L440-L449】

### ElevenLabs Webhook
- `POST /internal/api/webhooks/chart` → geschützter Webhook mit HMAC/API‑Key/Bearer‑Auth; liefert West‑ und Ost‑Signaturen (vereinfachtes Payload). Interner Pfad — nur für ElevenLabs-Integration, nicht öffentliche API-Oberfläche.【F:bazi_engine/app.py†L501-L612】

## Testergebnisse (Anforderungssicht)

Die Kernanforderungen lassen sich auf Basis der Implementierung und einer lokalen Probeausführung bestätigen:

- **BaZi‑Charts komplett**: Vier Säulen (Jahr/Monat/Tag/Stunde) mit LiChun‑Logik und 24 Solartermen werden berechnet; die API liefert alle Säulen strukturiert zurück.【F:bazi_engine/bazi.py†L73-L170】【F:bazi_engine/app.py†L196-L237】
- **Ephemeriden komplett**: Western‑Charts verwenden Swiss Ephemeris, inklusive Planeten, Häusern und Angles. Die Berechnung ist vollständig, solange lokale Ephemeriden-Dateien vorhanden sind (keine Netz‑Downloads zur Laufzeit).【F:bazi_engine/western.py†L1-L120】【F:bazi_engine/ephemeris.py†L10-L107】
- **Fusion/Harmonisierung**: Wu‑Xing‑Vektoren werden aus BaZi‑ und Western‑Daten gebildet und zu Kohärenz-Index + Interpretation verschmolzen (`compute_fusion_analysis`).【F:bazi_engine/fusion.py†L82-L495】

