# PRD — FuFire Domain Ownership

> Quelle: SRC-001. Slug: `fufire-domain-ownership`. Adressat: FuFire-API (Server).
> Consumer: Sizhu-Middleware (read-only).

## Kontext
Verlagerung des Metaphysik-Domänenvertrags (Interpretation + Geocoding) von der
Sizhu-Middleware nach FuFire. Middleware wird dünner Consumer eines stabilen
`/v1/`-Vertrags.

## Requirements

### REQ-001 — Geocoding-Endpunkt (EXPLICIT)
Ortsname → Koordinaten.
- Input: Ortsname (String, optional Land/Region-Hint).
- Output: `{ lat: number, lon: number, resolved_name: string, confidence: number }`.
- Ambiguität (OQ-001 ENTSCHIEDEN): best-match + `confidence` zurückgeben. Schwellwert
  `confidence < 0.6` → **Fehler (fail loud)** statt stille Falschauswahl. Über Schwelle:
  bester Treffer + Score.
- Grund: schließt `NO_GEOCODER_CONFIGURED`; wuxing braucht lat/lon.
- Trace: AC-001, AC-001b · EV-001 · RISK-003 · VIS-003 · CAN-004.

### REQ-002 — Aggregat-Endpunkt `/v1/personalize` (EXPLICIT)
Geburtsdaten → fertige Prompt-Vars in EINEM Call.
- Input (OQ-003 ENTSCHIEDEN): akzeptiert **Ortsname ODER lat/lon** (`oneOf`).
  Name vorhanden → `/personalize` ruft REQ-001 **intern** (Middleware bleibt dünn).
  lat/lon vorhanden → direkt benutzt (Bypass für Tests + Paritäts-Diff, keine Geocoder-Varianz).
  Plus Datum + Zeit.
- Output-Vertrag (OQ-004 ENTSCHIEDEN — 6 Prompt-Vars FLACH oben = bindender Vertrag;
  `bazi/trace` + `chronometry` INLINE, aber unter eigenem Key `domain_extras`, damit
  additive Extras den stabilen 6-Felder-Vertrag nicht verschmutzen):
  ```json
  { "animal": "...", "element": "...", "birth_year": 0,
    "dominant_element": "...", "eastern": "...", "western": "...",
    "domain_extras": { "bazi_trace": { }, "chronometry": { } } }
  ```
- Semantik-Parität zur alten Middleware-Interpreter-Logik:
  - locale-Animal (lokalisiertes Tierkreiszeichen)
  - dominant-Element via Argmax über Element-Verteilung
  - day-anchor-Caveat (Tagessäulen-Sonderbehandlung)
- Parität bei identischer Eingabe = Abnahmekriterium (RISK-002).
- Trace: AC-002, AC-002b · EV-002, EV-002-Parität · RISK-001, RISK-002 · VIS-003 · CAN-004, CAN-006.

### REQ-003 — Migration deferred-unverified Mappings (EXPLICIT)
`bazi/trace` + `chronometry` werden FuFire-Sache. Die Daten existieren bereits als
Engine-Endpunkte (`/v1/calculate/bazi/trace`, `/v1/chronometry/resolve`); REQ-003 ist
**Konsumieren statt selbst mappen**: ausgeliefert INLINE im `/v1/personalize`-Response
unter `domain_extras` (OQ-004 ENTSCHIEDEN). Middleware trägt sie nicht mehr als Tech-Debt.
- Trace: AC-003 · EV-003 · CAN-004.

### REQ-004 — E2E-Chain-Erfolg (EXPLICIT)
Simulierter Kauf-Trigger → Middleware → `/v1/personalize` (intern ggf. Geocoding) →
echter Response → Template-Autofill → LLM-Generierung → QA Gate 1 + 2 bestanden,
0 manuelle Koordinateneingaben. Gegen ECHTE FuFire-Endpunkte.
- Trace: AC-004 · EV-004 · VIS-004.

## Non-Functional Requirements
- NFR-001 (LATENCY, OQ-002 ENTSCHIEDEN) — `/v1/personalize` Durchschnitt ~2 s,
  Hard ceiling **p95 ≤ 5 s**. Entspannter interner Rahmen; testbar via EV.
- NFR-002 (SECRET-HYGIENE, EXPLICIT) — Auth via API-Key; Key niemals in Response/Log.
- NFR-003 (CONTRACT-STABILITY, EXPLICIT) — Vertrag versioniert/stabil unter `/v1/`.

## Akzeptanzkriterien (Given/When/Then)
- AC-001 → REQ-001: Given Ortsname ohne Koordinaten, When Personalize-Run startet,
  Then FuFire liefert lat/lon, kein Operator-Eingabefeld nötig.
- AC-001b → REQ-001: Given mehrdeutiger Ortsname, When Geocoding, Then best-match +
  confidence; bei confidence < 0.6 Fehler (fail loud), keine stille Falschauswahl.
- AC-002 → REQ-002: Given valide Geburtsdaten, When 1 Call `/v1/personalize`, Then
  vollständige Prompt-Vars; Middleware interpretiert keine Pillars mehr.
- AC-002b → REQ-002: Given identische Eingabe, When alt(interpreter) vs. neu(endpoint),
  Then Prompt-Vars identisch (locale-animal, dominant-argmax, day-anchor).
- AC-003 → REQ-003: Given Personalisierung, When Run, Then bazi/trace + chronometry
  aus FuFire; keine deferred-unverified Mappings mehr in Middleware.
- AC-004 → REQ-004: Given simulierter Kauf-Trigger, When Event in Middleware, Then
  Chain bis QA Gate 2 bestanden, 0 manuelle Koordinateneingaben.

## Evidence
- EV-001 → REQ-001: Live-Smoke gegen realen Geocoding-Endpunkt (host-only Log, Secret-Hygiene-Selfcheck).
- EV-002 → REQ-002: Contract-Drift-Smoke gegen `/v1/personalize` — FAIL LOUD bei Shape-Drift.
- EV-002-Parität → REQ-002: Diff-Test alt vs. neu bei identischem Input → 0 Abweichungen.
- EV-003 → REQ-003: Grep — kein Interpreter-Mapping für bazi/trace + chronometry mit Prod-Importer in Middleware.
- EV-004 → REQ-004: E2E-Run gegen echte FuFire-Endpunkte bis Gate 2.
- Dependency-Richtung: FuFire-Vertrag am realen Call-Site mit echtem Secret verifiziert
  (Live-Smoke) BEVOR Consumer-Capability als „real" gilt. Grüne Unit-Tests beweisen den
  assemblierten Vertrag nicht.

## Risiken
- RISK-001 Cross-Repo-Drift → stabiler `/v1/`-Vertrag + EV-002 Drift-Smoke (Consumer-Seite).
- RISK-002 Semantik-Bruch bei Interpreter-Verlagerung → AC-002b Paritäts-Diff.
- RISK-003 Geocoding-Ambiguität → AC-001b Fallback definieren.

## Entscheidungen (vormals offen, vom Operator bestätigt 2026-06-17)
- OQ-001 ✅ Geocoding-Ambiguität: best-match + `confidence`; `< 0.6` → Fehler (fail loud). (→ AC-001b, RISK-003)
- OQ-002 ✅ Latenz: Ø ~2 s, p95 ≤ 5 s. (→ NFR-001)
- OQ-003 ✅ `/v1/personalize` Input: Ortsname ODER lat/lon (`oneOf`), Name → internes Geocoding, lat/lon = Bypass. (→ REQ-002)
- OQ-004 ✅ bazi/trace + chronometry: INLINE im Payload unter `domain_extras`; 6 Prompt-Vars bleiben flach. (→ REQ-002, REQ-003)

Keine offenen Punkte. Build-ready.
