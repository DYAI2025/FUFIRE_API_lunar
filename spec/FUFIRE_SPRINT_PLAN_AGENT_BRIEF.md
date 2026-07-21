# Agent Brief: FuFirE B2B-Ready Sprint Plan

> **An:** Claude Code Agent (Opus 4.6)
> **Von:** Ben (Product Owner)
> **Datum:** 09.03.2026
> **Aufgabe:** Erstelle einen vollständigen, iterativen Projektplan mit Sprints für die FuFirE (Fusion Firmament Engine), der nach der letzten Iteration eine vollständig B2B-fähige, kostenpflichtige API liefert.

---

## Dein Auftrag

Du erstellst einen Sprint-Plan als `.docx`-Datei. Kein Code. Kein Prototyp. Ein Projektplan.

Jeder Sprint liefert ein **funktionales Inkrement** — nach jedem Sprint ist die Engine in einem besseren, testbaren Zustand als vorher. Kein Sprint darf "Vorarbeit ohne sichtbares Ergebnis" sein. Nach dem letzten Sprint ist FuFirE B2B-ready: Ein externer Entwickler kann sich einen API-Key holen, gegen die Docs integrieren, und ein Produkt darauf bauen.

---

## Kontext: Was ist FuFirE?

FuFirE (Fusion Firmament Engine) ist eine kostenpflichtige B2B-API, die drei astrologische Systeme fusioniert:
- **Western Astrology** (Swiss Ephemeris, Placidus Houses, Tropical Zodiac)
- **Chinese BaZi** (Four Pillars of Destiny, regelbasiert)
- **WuXing Five Elements** (Element-Vektor aus BaZi + Western)
- **Fusion** (Cross-System-Analyse, mehrere Modi: trusted/advanced/experimental)

Bazodiac (bazodiac.space) ist das Showcase-Projekt — eine Consumer-App die alle FuFirE-Endpunkte nutzt. Bazodiac ist NICHT das Primärprodukt. FuFirE ist das Primärprodukt.

### Repos
- `DYAI2025/FuFirE` — Python, FastAPI, Swiss Ephemeris (ehemals BAFE, kürzlich rebranded)
- `DYAI2025/Astro-Noctum` — React, TypeScript, Vite (Bazodiac Frontend, konsumiert FuFirE)

### Hosting
- Railway (FuFirE API + Astro-Noctum)
- Supabase (Auth, Profile Storage, Event Storage)

---

## Kontext: Aktueller Zustand nach Rebranding

Das Rebranding von BAFE → FuFirE ist abgeschlossen. Folgende Probleme bestehen TROTZ des Rebrands:

### Was funktioniert
- `/calculate/western` — Planetenpositionen via Swiss Ephemeris. Grundsätzlich korrekt.
- `/calculate/bazi` — Vier Säulen, Day Master. Stabilster Teil der Engine.
- `/calculate/wuxing` — Element-Vektor. Funktioniert, aber intransparent (Black Box).
- `/calculate/fusion` — Existiert, liefert wenig Daten. Quasi-Placeholder.
- Tests: 992 passed, 9 pre-existing failures, 13 skipped.

### Was NICHT funktioniert oder fehlt

**Fehlerquellen (aus Ops-Analyse):**
1. DST / lokale Zeitauflösung — Ambiguous/nonexistent local times erzeugen 422 oder stille Shifts
2. Unknown timezone / ISO-Formatfehler — uneinheitlich propagiert
3. Ephemeris unavailable — fehlende Files liefern 503 (immerhin eigener Fehlerpfad)
4. Geocoding-Timeout im Webhook-Pfad
5. Doku-Drift (OpenAPI ≠ Runtime-Response, besonders bei `/calculate/bazi`)
6. Cold Starts
7. Build-Abhängigkeit von externem Ephemeris-Download

**Fehlende B2B-Infrastruktur:**
- Kein einheitliches Error-Envelope (verschiedene Formate je nach Fehlerpfad)
- Keine API-Key-Authentifizierung
- Kein Rate Limiting
- Kein `/v1/` Prefix (Breaking Changes nicht migrierbar)
- `/health` prüft keine Dependencies
- Keine Request-IDs in Fehlern
- Keine Webhook-Separation (ElevenLabs-Webhook und API-Endpunkte unter gleichem Router)
- Stille Defaults statt expliziter Fehler (z.B. House System Fallback)

**Fehlende API-Module (noch nicht implementiert):**
- `/transit/*` — Echtzeit-Planetenpositionen (Swiss Ephemeris kann es, Endpunkt fehlt)
- `/contribution/*` — Quiz-Ingestion für B2B-Kunden
- `/match/*` — Paar-/Team-Kompatibilität

**Fachliche Schwächen:**
- WuXing: Planet→Element Zuordnung zu grob, kein Contribution Ledger
- Fusion: Echte westliche Positionen (Längen, Häuser, Aspekte) fließen kaum ein
- H_calibrated existiert im Code, wird aber nicht standardmäßig ausgegeben
- BaZi-Ruleset nicht versioniert/externisiert

---

## Designprinzip: DATENWAHRHEIT

Das oberste Prinzip, das JEDEN Sprint durchzieht:

**Jeder Wert den FuFirE ausgibt muss drei Fragen beantworten können: Woher kommt er? Wie wurde er berechnet? Warum genau dieser Wert und kein anderer?**

Konsequenzen:
- **Kein stiller Fallback.** Wenn etwas nicht berechnet werden kann, gibt es einen Fehler — keinen stillen Default.
- **Provenance in jeder Response.** engine_version, ruleset_id, ephemeris_id, house_system, zodiac_mode.
- **Contribution Ledger.** Jeder WuXing-Wert, jede Fusion-Komponente zeigt auf die Eingangsdaten.
- **Determinismus.** Gleiche Inputs = identische Outputs. Keine Zufallskomponenten.
- **Echte Validierung.** Kein Marketingclaim basiert auf synthetischen Daten.

---

## Modulare API-Architektur (Zielzustand)

FuFirE hat vier unabhängig buchbare Module:

| Modul | Endpunkte | Use Case |
|-------|-----------|----------|
| STATIC CORE | /v1/calculate/western, /bazi, /wuxing, /fusion | Geburtschart. Basis-Tier. |
| TRANSIT | /v1/transit/now, /state, /narrative, /timeline | Echtzeit-Planeten. Optional. |
| CONTRIBUTION | /v1/contribution/ingest, /signal | Quiz-Ingestion. Für Dating/HR. |
| MATCHING | /v1/match/compatibility, /team | Kompatibilität. Für Dating/TeamBuilding. |

Drei Fusion-Modi: `trusted` (hard_segment, Default), `advanced` (soft_kernel, Premium), `experimental` (harmonic_phasor, Research).

---

## Architektur-Entscheidungen (ADRs) — bereits getroffen

Diese Entscheidungen sind GESETZT. Nicht erneut evaluieren.

| ADR | Entscheidung | Gewählt |
|-----|-------------|---------|
| 1 | Cache Backend Transit | cachetools.TTLCache (in-memory). Redis erst bei Multi-Worker. |
| 2 | History Store 30-Tage-Avg | Supabase Tabelle: transit_history |
| 3 | Narrative Generation | Sync Template (immer) + Async Gemini Cache (optional) |
| 4 | bafe/ Directory Rename | NICHT umbenennen. Nur String-Literale. |
| 5 | /calculate/fusion Erweiterung | Optionales `correlations` Feld (null default) |
| 6 | Transit Graceful Degradation | Feature Flag: VITE_USE_REAL_TRANSITS |
| 7 | OG:image /fu-ring | Statisches Placeholder. Puppeteer → später. |

---

## Deine Aufgabe im Detail

### Format
Erstelle eine `.docx`-Datei mit dem Titel "FuFirE B2B Sprint Plan v1".

### Struktur pro Sprint

Jeder Sprint bekommt:

1. **Sprint-Nummer + Name** (z.B. "Sprint 1 — Ehrliche Engine")
2. **Sprint-Ziel** — Ein Satz der beschreibt, was nach diesem Sprint ANDERS ist. Muss testbar sein.
3. **Funktionales Inkrement** — Was kann ein Entwickler nach diesem Sprint tun, was er vorher nicht konnte?
4. **Tasks** — Nummerierte Liste mit Beschreibung, geschätztem Aufwand, Akzeptanzkriterium pro Task.
5. **Definition of Done für den Sprint** — Checkliste, wann der Sprint als abgeschlossen gilt.
6. **Abhängigkeiten** — Was muss aus vorherigen Sprints fertig sein?
7. **Risiken** — Was könnte den Sprint blockieren?

### Inhaltliche Anforderungen

- **Sprintlänge:** Jeder Sprint ist 1-2 Wochen Arbeit für EINEN Entwickler.
- **Reihenfolge:** Priorisiere nach Vertrauensrisiko, nicht nach Implementierungsbequemlichkeit. Was das Vertrauen eines B2B-Kunden am meisten gefährdet, kommt zuerst.
- **Keine stillen Defaults:** Wenn ein Sprint einen bestehenden stillen Fallback aufdeckt, muss der Sprint ihn in einen expliziten Fehler oder ein Qualitätsflag umwandeln. Sachen die kaputt sind müssen sich auch kaputt ZEIGEN.
- **Iteration = funktionales Inkrement:** Nach jedem Sprint ist die API in einem besseren, testbaren Zustand. Kein Sprint darf "nur Vorbereitung" sein.
- **Letzter Sprint = B2B-Ready:** Nach dem letzten Sprint kann ein externer Entwickler: (1) sich einen API-Key holen, (2) gegen die OpenAPI-Docs integrieren, (3) einheitliche Fehler parsen, (4) alle vier Module nutzen, (5) seinem eigenen Kunden erklären woher jeder Wert kommt.

### Was der Plan abdecken muss (vollständig)

Der Sprint-Plan muss ALLE folgenden Arbeitspakete in Sprints einordnen. Nichts weglassen:

**Rechenkern (Datenwahrheit):**
- Ephemeris-Fallback eliminieren (kein MOSEPH im Paid-Tier)
- Provenance-Block in jede Response
- Bit-Stabilität (Snapshot-Tests für Referenzfälle)
- Western House-System Fallback explizit machen
- Aspekte in Core-Output
- BaZi-Ruleset versionieren + externisieren + Golden Tests
- WuXing Contribution Ledger (pro Planet, pro Säule)
- Echte westliche Positionen in Fusion (Längen, Häuser, Aspekte)
- H_calibrated als Standard-Output
- Fusion-Modi (trusted/advanced/experimental) implementieren

**API-Infrastruktur (B2B-Ready):**
- Einheitliches Error-Envelope (error_code, message, details, request_id)
- API-Key Authentifizierung + Usage Tracking
- Rate Limiting (slowapi, pro API-Key, pro Modul)
- /v1/ Prefix auf alle Endpunkte
- /health mit Dependency Checks (Ephemeris, Geocoding)
- Request-IDs in allen Responses
- Webhook-Separation (/v1/* vs. /internal/webhooks/*)
- OpenAPI/README/Runtime synchronisieren (Response-Model-Drift fixen)
- Strukturierte Logs + Sentry/Tracing
- Ephemeris-Files vendoren (nicht zur Buildzeit downloaden)

**Neue Module:**
- /transit/now — Echtzeit-Planetenpositionen
- /transit/state — Personalisierter Transit mit Events
- /transit/narrative — Ringwetter-Text (Template sync + Gemini async)
- /transit/timeline — Vorschau N Tage
- /contribution/ingest — Quiz-Events → Sektor-Signale
- /contribution/signal — Aggregierter T(s) pro User
- /match/compatibility — Paar-Kompatibilität
- /match/team — Team-Balance

**Validierung + Markt:**
- Audit-Trail pro Response (compact + audit Modus)
- Externe Validierung mit realen Datensätzen (Forschungsprotokoll)
- Developer Portal / API-Dokumentation
- Trusted vs. Experimental sauber getrennt in Produktlogik

### Was du NICHT tun sollst

- Keinen Code schreiben.
- Keine technischen Implementierungsdetails (kein "erstelle Datei X mit Inhalt Y").
- Nicht die ADRs neu evaluieren — sie sind gesetzt.
- Nicht Bazodiac-Frontend-Tasks einplanen — der Plan betrifft NUR die FuFirE Engine API.
- Nicht die Sprintlänge auf >2 Wochen dehnen. Lieber mehr Sprints mit kleineren Inkrementen.

### Tonfall

Direkt, präzise, keine Füllwörter. Jeder Satz muss eine Information tragen. Das Dokument wird von einem Entwickler gelesen der es 1:1 umsetzt — kein Marketing, keine Vision-Prosa, keine "wir könnten auch"-Optionen. Entscheidungen treffen, nicht Optionen auflisten.

---

## Qualitätskriterien für deinen Output

Der Sprint-Plan ist GUT wenn:
- [ ] Jeder Sprint hat ein testbares Sprint-Ziel
- [ ] Jeder Sprint liefert ein funktionales Inkrement (nicht nur "Vorbereitung")
- [ ] Die Reihenfolge folgt Vertrauensrisiko (was B2B-Vertrauen am meisten gefährdet, zuerst)
- [ ] Alle oben gelisteten Arbeitspakete sind in Sprints eingeordnet — nichts fehlt
- [ ] Der letzte Sprint endet mit einer vollständig B2B-fähigen API
- [ ] Kein Sprint hat mehr als 2 Wochen Aufwand für einen Entwickler
- [ ] Abhängigkeiten zwischen Sprints sind explizit
- [ ] Das Designprinzip Datenwahrheit ist in jedem Sprint sichtbar
- [ ] Die 9 pre-existing Test Failures sind in einem Sprint adressiert
- [ ] Die Gesamtschätzung ist realistisch (nicht optimistisch)

---

## Starte jetzt.
