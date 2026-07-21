# Plan: FuFirE Premium-Verifikation + unabhängige CI/CD-Prüfung

**Repo:** `DYAI2025/FuFirE` (Python 3.10–3.12, FastAPI, `bazi_engine/`, pyswisseph)
**Autor-Kontext:** erstellt aus dem Bazodiac-BFF (`New_Bazi`), das die FuFirE-API konsumiert.
**Ausführender:** eine Claude-Code-Instanz, die **im FuFirE-Repo** arbeitet.
**Datum:** 2026-07-01

---

## 0. Ziel & Nicht-Ziele

### Ziel
FuFirE auf **internationale Premium-API-Qualität** heben und diese Qualität **kontinuierlich, unabhängig und automatisiert beweisbar** machen. Konkret:

1. **Keine stille Präzisions-Degradierung.** Eine bezahlte Response darf niemals aus dem Moshier-Fallback (MOSEPH) stammen, ohne dass das hart erzwungen, in der Response attestiert und in Prod überwacht wird.
2. **Unabhängige Implementierung über die geteilte DE-Quelle als Grundwahrheit.** Die astronomische Rechenlogik wird gegen JPL Horizons geprüft — eine *unabhängige Implementierung über dieselbe JPL-DE-Reihe*, die Swiss Ephemeris komprimiert (NICHT eine quellen-unabhängige Wahrheit; Details + was das fängt/nicht fängt in WS-B). Zusätzlich zur bestehenden astro.com-AA-Validierung. Einziger quellen-unabhängiger Check: arithmetische BaZi-Tages-Säule.
3. **Premium-Genauigkeit.** Aszendent/Häuser von aktuell 97,2 % auf Premium-Niveau (Zielschwelle als harter Gate, s. FQ-030) — Ursache ist das historische Zeitzonen-/LMT-Modell.
4. **BaZi-Korrektheit unabhängig verankert** (Solar-Terms/Jié gegen offizielle Observatoriums-Tabellen; Tages-Säule arithmetisch beweisbar).
5. **Regelmäßige unabhängige Claude-Prüfung** als geplanter, adversarialer Audit-Job in GitHub Actions — nicht als Gummistempel.
6. **Mehr CI/CD-Jobs**, die genau diese Garantien bei jedem PR, nächtlich und vor jedem Release durchsetzen.

### Nicht-Ziele
- Keine Änderung der astrologischen **Deutungs-/Narrativ**-Inhalte (nur Rechenlogik + Nachweisbarkeit).
- Keine neuen fachlichen Features (keine neuen Endpunkte außer Verifikations-Tooling).
- Kein Umstieg der Ephemeriden-Engine weg von Swiss Ephemeris (JPL nur als **Oracle**, nicht als Laufzeit-Backend).
- Kein Umbau des Deploy-Targets (Cloud Run bleibt).

---

## 1. Vorbedingungen & bekannter Ist-Zustand

**Bereits vorhanden (darauf aufbauen, NICHT neu erfinden):**
- `bazi_engine/ephemeris.py` → `assert_no_moseph_fallback(requested_flags, returned_flags)` erkennt stillen Moshier-Fallback am Flag-Bit und wirft `EphemerisUnavailableError`. **Muss geprüft werden: wird das auf JEDEM `swe.calc_ut`-Pfad aufgerufen?**
- `.github/workflows/ci.yml` — Matrix 3.10–3.12; installiert `libswe-dev`; lädt `.se1` (`sepl_18`, `semo_18`, `seas_18`, `seplm06`) + Cache; generiert SWIEPH-Snapshots; `pytest --cov-fail-under=75`; `scripts/export_openapi.py --check`.
- `.github/workflows/build-ephe-base.yml` + `Dockerfile.ephe-base` — Ephemeriden werden in ein Base-Image gebacken (adressiert „Files nicht auf Server").
- `scripts/western_reference_validation.py` + `reports/western_validation_summary.json` — 176 Charts vs astro.com Astrodatabank; Sonne/Mond 100 %, Aszendent 97,15 % (5 Mismatches).
- `tests/golden_reference_cases.py`, `tests/fixtures/western_reference_charts.json`, `tests/fixtures/bazi_baseline_v1.json`.
- `tests/snapshots/{moseph,swieph}/…` inkl. `hilat_*` (Polar-Breiten: Tromsø, Murmansk, Longyearbyen, Reykjavík, Helsinki, Fairbanks) und `lichun_*` (Li-Chun-Solar-Term-Grenze Feb 3/4, Tokyo before/after).
- `bazi_engine/routers/validate.py` + `spec/schemas/Validate{Request,Response}.schema.json` + `docs/validate_contract.md`.
- `spec/tests/tv_matrix.json`, `spec/golden/bazi_case.schema.json`.
- `docs/runbooks/ephemeris-local-setup.md`, `hardening/…testaufbau…md`.
- FuFirE-Responses tragen `quality_flags.ephemeris_mode`, `quality_flags.house_system_fallback`, `provenance.ephemeris_id`, `provenance.tzdb_version_id` (aktuell teils `"unknown"`).

**Bekannte Lücken (= Substanz dieses Plans):**
- **G1 — Scheinbare Unabhängigkeit.** Referenz-Vergleich läuft über astro.com/kerykeion; kerykeion nutzt selbst Swiss Ephemeris → für Planeten-Numerik **nicht** provider-unabhängig. Systematische Swiss-Eph-Fehler bleiben unsichtbar.
- **G2 — Aszendent-Fehler = historisches TZ-Modell.** Die 5 Mismatches korrelieren mit Offset-Diskrepanz `utc_offset_minutes_zoneinfo` vs `utc_offset_minutes_kerykeion` (z. B. 360 vs 351, −321 vs −353). Pre-1970/LMT-Zonen.
- **G3 — Attestierung nicht end-to-end.** Engine-Guard existiert, aber unklar ob (a) auf allen Pfaden aktiv, (b) in `quality_flags` jeder Endpunkt-Response garantiert, (c) `tzdb_version_id` gepinnt/exponiert statt `"unknown"`.
- **G4 — BaZi ohne externe Wahrheit.** Solar-Terms/Pillars nur gegen Selbst-Snapshots; keine offizielle Observatoriums-Referenz.
- **G5 — Kein geplanter unabhängiger KI-Audit.**
- **G6 — Keine Prod-Laufzeit-Attestierung** (Live-Smoke prüft Modus nicht).
- **G7 — Jahres-Untergrenze / Kalenderreform** (proleptisch-gregorianisch vor 1582; im BFF als `BIRTH-YEAR-03` geflaggt) — Engine-Verhalten unspezifiziert.

**Setup-Vorbedingung für den Ausführenden (Task FQ-000):**
Repo orientieren, `pip install -e ".[dev]"`, `.se1` nach `SE_EPHE_PATH` legen (siehe `docs/runbooks/ephemeris-local-setup.md`), `pytest -q` grün bekommen, `reports/western_validation_summary.json` reproduzieren. **Außerdem sofort** `spec/quality_thresholds.json` mit **provisorischen, dokumentierten** Werten anlegen (JPL-Toleranz als „provisorisch bis FQ-B1-Angleichungs-Beweis" markiert), damit WS-B/WS-C es lesen können; Ratifizierung erst in FQ-030. Erst danach Tasks starten.

---

## 2. REQ-IDs (Nachvollziehbarkeit)

| REQ | Anforderung |
|-----|-------------|
| FQ-ATT-01 | Bezahlte Response kann strukturell nie aus unangefordertem MOSEPH stammen (hart, alle Pfade). |
| FQ-ATT-02 | Jede Rechen-Response exponiert `ephemeris_mode`, `ephemeris_id`, `tzdb_version_id`, `house_system_fallback` — nie `"unknown"`. |
| FQ-IND-01 | Planeten-Längen werden gegen JPL Horizons (unabhängige Implementierung über geteilte DE-Quelle) mit Toleranz geprüft; Aszendent separat aus RAMC+Obliquität. |
| FQ-IND-02 | BaZi-Solar-Terms werden gegen offizielle Observatoriums-Tabellen geprüft; Tages-Säule arithmetisch bewiesen. |
| FQ-ACC-01 | Aszendent/Häuser erreichen Premium-Schwelle; historisches TZ-Modell korrekt. |
| FQ-CI-01 | PR-Gate: Attestierung + Referenz-Diffs + Genauigkeits-Schwellen blockieren Merge bei Regression. |
| FQ-CI-02 | Nächtlicher unabhängiger Referenz-Diff (Netz-Oracle) mit Report-Artefakt. |
| FQ-CI-03 | Release-Gate: gebautes Image beweist SWIEPH-only + Prod-Smoke attestiert Modus. |
| FQ-AUD-01 | Geplanter, adversarialer Claude-Audit öffnet Issue/PR mit Findings. |
| FQ-OBS-01 | Prod-Laufzeit-Attestierung + Alarm bei MOSEPH/Fallback/`tzdb=unknown`. |

---

## 3. Aufgabenliste (stabile IDs)

> Reihenfolge = empfohlene Ausführung. FQ-000 → WS-A → WS-C parallel zu WS-B → WS-D → WS-E/F. Jede Task ist einzeln ausführbar.

### WS-A — Attestierung end-to-end (G3)

**FQ-A1 — `assert_no_moseph_fallback` auf allen Rechenpfaden erzwingen** · REQ FQ-ATT-01
- **Discovery zuerst:** `grep -rn "swe\." bazi_engine/` → alle Aufrufer von `swe.calc_ut`/`swe.calc`/`swe.houses*`/`swe.fixstar*` auflisten. Dateien danach adressieren (bestätigt: `bazi_engine/ephemeris.py`, `bazi_engine/western.py`; weitere erst aus grep).
- **Wrapper NICHT einheitlich — zwei Klassen trennen:** `swe.calc_ut`/`swe.calc` nehmen/liefern Ephemeriden-Flags → Moshier-Fallback am Return-Flag-Bit erkennbar (was `assert_no_moseph_fallback` nutzt). `swe.houses` nimmt/liefert **keine** vergleichbaren Flags (Häuser sind geometrisch aus Sternzeit + Obliquität; der Moshier-Bezug tritt nur über die Obliquitäts-/Nutations-`calc` ein). Deshalb: `ephemeris.calc_checked()` für Körper-Calls (Flag-Assertion); **separate** Behandlung für `swe.houses*`/`swe.fixstar` (Flag-Assertion nur wo Flags existieren — sonst No-op oder falscher Raise).
- **Vorgehen:** alle Körper-Direktaufrufe auf `calc_checked` umstellen; House/Fixstar-Pfade über ihre zugrundeliegende Obliquitäts-`calc` absichern. Kein Pfad ruft `swe.calc*` direkt auf.
- **Tests:** `tests/test_ephemeris_attestation.py` — mit `SE_EPHE_PATH` auf leeren Ordner (erzwingt MOSEPH) muss **jeder** Endpunkt/Rechenweg `EphemerisUnavailableError` werfen (parametrisiert über western/bazi/wuxing/fusion/daily). *Mechanismus bestätigt: leerer Ephemeriden-Pfad erzwingt Moshier-Fallback und löscht das `SEFLG_SWIEPH`-Return-Bit → „muss werfen" ist valide.* AST-Lint-Test: verbietet Direktaufrufe von `swe.calc*`, `swe.houses*`, `swe.fixstar` außerhalb `ephemeris.py`.
- **Acceptance:** `pytest tests/test_ephemeris_attestation.py -q` grün; AST-Guard grün; grep zeigt 0 Direktaufrufe außerhalb `ephemeris.py`.

**FQ-A2 — Attestierungs-Felder in jeder Response garantieren, `tzdb_version_id` pinnen** · REQ FQ-ATT-02
- **Dateien:** Response-Builder je Endpunkt (`bazi_engine/app.py`, `bazi_engine/routers/*`, `bazi_engine/bafe/service.py`), `pyproject.toml`/`requirements.lock` (tzdata pinnen), evtl. `provenance`-Assembler.
- **Vorgehen:** `tzdb_version_id` aus gepinnter `tzdata`-Version ableiten (nicht `"unknown"`); sicherstellen dass `quality_flags.ephemeris_mode`, `house_system_fallback`, `provenance.ephemeris_id` bei **jedem** Rechen-Endpunkt gesetzt sind. Response-Modelle (Pydantic) auf `Optional`→`required` für diese Felder ziehen.
- **Tests:** Contract-Test je Endpunkt: Felder vorhanden, `!= "unknown"`, `ephemeris_mode == "SWIEPH"` unter Test-Ephemeriden. Schema-Update in `spec/schemas/` + OpenAPI-Drift-Check muss grün bleiben.
- **Acceptance:** `pytest -k attestation_contract` grün; `python scripts/export_openapi.py --check` grün; Beispiel-Response im Report zeigt konkrete `tzdb_version_id`.

### WS-B — Provider-unabhängige Grundwahrheit (G1, G4)

**FQ-B1 — JPL-Horizons-Oracle für Planeten-Längen** · REQ FQ-IND-01
- **Dateien (neu):** `tests/oracle/jpl_horizons.py` (Client + eingefrorene Request-Parameter), `tests/fixtures/jpl_reference/*.json` (committete Referenz-Vektoren), `scripts/build_jpl_reference.py` (Regenerierung), `tests/oracle/tolerances.py`, `tests/test_planet_longitudes_vs_jpl.py`.
- **Frame-Angleichung (kritisch — sonst systematischer Scheinfehler).** Swiss Ephemeris liefert per Default (`SEFLG_SWIEPH`, ohne `SEFLG_J2000`) **scheinbare, geozentrische** Länge bezogen auf **wahres Äquinoktium und Ekliptik des Datums** = der tropische Tierkreis. JPL Horizons muss **exakt** so gepinnt werden: Center `geo`/`@500`, **apparent** (Lichtlaufzeit + Aberration + Deflection an), Bezugsrahmen **Ekliptik & wahres Äquinoktium des Datums** (NICHT J2000, NICHT mean-of-date), Quantity **31 (ObsEcLon)**, Ayanamsha aus. Diese Parameter **hart in `tests/oracle/jpl_horizons.py` einfrieren** und in `docs/verification_vectors.md` dokumentieren.
- **Drei Angleichungs-Achsen explizit behandeln:** (1) Präzession date-of vs J2000 (~0,014°/Jahr → ~0,28° für 2020, ~1,4° für 1900), (2) **Nutation mean vs wahres Äquinoktium (±0,0047°, größenordnungsgleich mit der ganzen Toleranz)**, (3) Aberration astrometrisch vs scheinbar (~0,006°). Alle drei müssen matchen.
- **Unabhängigkeits-Beweis (statt Kalibrierung gegen Swiss Eph):** SwissEph und JPL teilen dieselbe DE-Quelle → bei korrektem Frame ist Übereinstimmung **sub-Bogensekunde**. Die 0,01°-Prüfung ist damit effektiv ein **Frame-Angleichungs-Test**. Beweis OHNE jede SwissEph-Quelle: denselben Körper aus Horizons als astrometrisch-J2000 UND scheinbar-des-Datums ziehen und prüfen, dass Präzession+Nutation+Aberration analytisch die Differenz erklären. **Ein konstanter Rest-Bias muss GEFIXT werden, nie wegkalibriert.** (Nicht gegen astro.com/kerykeion kalibrieren — die sind selbst Swiss Eph, das zerstört die Unabhängigkeit.)
- **Vorgehen:** Für festen Vektor-Satz (FQ-B3) Referenz einmalig committen (offline-deterministisch, kein Netz im PR-Gate). Engine-Längen (echte Grad, nicht Zeichen-Bucket) gegen JPL diffen. Toleranzen in `tolerances.py`, begründet: Sonne/Mond/innere Planeten ≤ 0,01°, äußere ≤ 0,02°. **KEIN Aszendent hier** (Horizons berechnet keinen Aszendenten — s. FQ-B1b).
- **Tests:** `pytest tests/test_planet_longitudes_vs_jpl.py -q`.
- **Acceptance:** Frame-Angleichungs-Beweis (analytische Differenz erklärt) grün **zuerst**; danach alle Vektoren innerhalb Toleranz; Report `reports/jpl_diff_report.md` mit Max-Delta je Körper. Toleranz-Gate wird erst **required** (FQ-D1), nachdem der Angleichungs-Beweis steht (s. Ordering FQ-030).

**FQ-B1b — Unabhängiger Aszendent-/Häuser-Check (nicht via JPL)** · REQ FQ-IND-01, FQ-ACC-01
- **Vorgehen:** Aszendent ist kein Ephemeriden-Körper, sondern Funktion aus lokaler scheinbarer Sternzeit (RAMC), Schiefe (Obliquität) und geografischer Breite. Unabhängige Prüfung aus **unabhängig berechnetem RAMC + Obliquität** (dieselbe Größe speist WS-C), NICHT aus Horizons. Toleranz Aszendent ≤ 0,1°.
- **Acceptance:** Aszendent für FQ-B3-Vektoren aus RAMC+Obliquität abgeleitet stimmt mit Engine ≤ 0,1° überein; Methode in `docs/verification_vectors.md` dokumentiert.

**FQ-B2 — BaZi-Solar-Terms gegen offizielle Tabellen + Tages-Säule arithmetisch** · REQ FQ-IND-02
- **Dateien (neu):** `tests/fixtures/jieqi_reference/*.json` (Jié-Zeitstempel, committet, Quelle + Lizenz/Attribution im Header), `tests/test_jieqi_vs_official.py`, `tests/test_day_pillar_arithmetic.py`; betroffen: per grep zu lokalisieren (`bazi_engine/jieqi.py` bestätigt-nah; `bazi_engine/dayun/jieqi.py`, `bazi_engine/bazi.py` **erst per grep verifizieren**).
- **Referenzquelle realistisch:** **Hong Kong Observatory** publiziert die 24 Solar-Terms — aber **minutengerundet** und in **UT+8**. Daraus folgt: (i) Fixture-Loader muss den UT+8-Offset behandeln; (ii) Toleranz ≤ 2 min ist sicher, aber die Engine kann gegen eine minutengerundete Quelle **nicht** besser als ~±1 min *bewiesen* werden — explizit so dokumentieren. Purple Mountain Observatory hat **keine** leicht maschinenlesbare Tabelle → nur „falls beschaffbar", **nicht** gleichrangige Pflicht. HKO ist die praktisch nutzbare Primärquelle.
- **Tages-Säulen-Grenze festnageln (sonst Off-by-one):** BaZi-Schulen streiten, ob die Tages-Säule um **00:00** oder um **23:00** (早晚子 / späte Zi-Stunde) wechselt. Konvention **explizit festlegen** und gegen das tatsächliche Engine-Verhalten bestätigen, sonst ist jede Geburt 23:00–24:00 ein stiller Off-by-one. „100 % exakt" gilt erst relativ zur fixierten Konvention.
- **Vorgehen:** (a) Solar-Term-Zeitpunkte (Sonnenlänge = k·15°) gegen HKO, Toleranz ≤ 2 min (mit obiger Präzisions-Einschränkung). (b) Tages-Säule = fortlaufender 60-Jiazi-Zähler ab bekannter Epoche → unabhängig arithmetisch (kein Ephemeriden-Bedarf) gegen Engine, **unter der fixierten Zi-Konvention**. (c) Monats-Säulen-Grenze an Jié-Cusp über vorhandene `lichun_*`-Fälle formalisieren.
- **Tests:** die drei neuen Test-Dateien.
- **Acceptance:** Jié-Delta ≤ 2 min über Referenzjahre (Präzisionsgrenze dokumentiert); Tages-Säule 100 % exakt gegen die dokumentierte Zi-Konvention; Monatsgrenze kippt korrekt in `lichun_*`.

> **Unabhängigkeits-Ehrlichkeit (gilt für WS-B gesamt):** Swiss Ephemeris ist eine Kompression der JPL-DE-Reihe. Der JPL-Diff ist eine **unabhängige Implementierung über dieselbe DE-Quelle**, KEINE quellen-unabhängige Wahrheit. Er fängt Kompressions-, Koordinaten-Transform- und FuFirE-Flag/Nutzungs-Fehler — nicht einen systematischen Fehler in DE selbst (praktisch irrelevant, da DE der Referenzstandard ist). Der einzige **quellen-unabhängige** BaZi-Check ist die arithmetische Tages-Säule.

**FQ-B3 — Kanonische Verifikations-Vektor-Matrix** · REQ FQ-IND-01/02, FQ-ACC-01
- **Dateien:** `spec/tests/tv_matrix.json` erweitern (nicht ersetzen); `docs/verification_vectors.md`.
- **Vorgehen:** Vektor-Sätze definieren + begründen: (1) AA-Prominente (bestehend), (2) JPL-Vektoren, (3) Grenzfälle: DST-Sprung/Wiederhol-Stunde, Solar-Term-Cusp ±Minuten, Datums-/Zeitzonengrenze, Südhemisphäre, Polar-Breite (Placidus-Fallback erwartet), historische Pre-1970-TZ, Pre-1582-Kalender (erwartetes Verhalten definieren, s. G7 — konkreter Hebel: SwissEph `swe_julday` `gregflag` = proleptisch-gregorianisch vs historisch-julianisch; Entscheidung + Beleg dokumentieren), Schaltjahr/29. Feb.
- **Tests:** Matrix wird von FQ-B1/B2/FQ-C1 konsumiert.
- **Acceptance:** jeder Vektor hat erwartete Referenz + Quelle + Toleranz; von mind. einem Test referenziert.

### WS-C — Premium-Genauigkeit: historisches TZ-Modell (G2)

**FQ-C1 — Historisches Zeitzonen-/LMT-Modell korrigieren** · REQ FQ-ACC-01
- **Dateien:** per grep lokalisieren (`bazi_engine/chronometry.py` bestätigt-nah; `time_model.py`/`bafe/time_model.py`, `bazi_engine/western.py` **erst per grep verifizieren**), Reproduktion via `scripts/western_reference_validation.py`.
- **Kein Zirkelschluss gegen kerykeion:** `scripts/western_reference_validation.py` vergleicht gegen kerykeion (= Swiss Eph). Bei den 5 Mismatches ist der **historische Offset selbst strittig** — kerykeions Pre-1970-TZ-Handling kann falsch sein. Deshalb: die „wahre" historische Zeit **nicht** aus kerykeion nehmen, sondern pro Fall aus **unabhängiger TZ-Wahrheit** — LMT direkt aus geografischer Länge für Pre-Zonen-Daten, bzw. autoritative historische TZ-Quelle mit Beleg. Auf kerykeion-Offset zu tunen hieße FuFirE auf *Übereinstimmung mit kerykeion* zu tunen, nicht auf Korrektheit.
- **Vorgehen:** Die 5 Mismatches (Earhart, Churchill(C-Qualität!), Yogananda, +2) reproduzieren; Offset-Diskrepanz `zoneinfo` vs `kerykeion` analysieren; autoritatives TZ-Modell entscheiden + dokumentieren (Vorschlag: IANA-`zoneinfo` mit LMT-Vorschaltung für Pre-Zonen-Daten); Aszendent-Zeit korrekt ableiten.
- **Nicht-gamebare Metrik:** Accuracy auf einem **eingefrorenen, Rodden-gefilterten Chart-Set (nur AA/A)** definieren — der Churchill-C-Fall darf **kein** Gate-Input sein. Sonst ist der Nenner durch Ausschluss „unbequemer" Charts manipulierbar. Rodden-/Data-Quality-Feld im Report führen.
- **Tests:** `tests/test_historical_timezone.py` (Regression auf die 5 Fälle, unabhängige TZ-Wahrheit als Erwartung); `scripts/western_reference_validation.py` erneut → Summary vergleichen.
- **Acceptance:** `asc_accuracy` auf dem AA/A-Frozen-Set ≥ Premium-Schwelle (Wert aus `spec/quality_thresholds.json`, s. FQ-030); die 5 Fälle erklärt (gefixt gegen **unabhängige** TZ-Wahrheit **oder** dokumentiert als Referenzdaten-Fehler mit Beleg — nie stille Toleranz-Aufweichung, nie Ausschluss zur Zielerreichung).

**FQ-030 — Premium-Schwellen als Konstanten festschreiben** · REQ FQ-ACC-01, FQ-CI-01
- **Ordering-Fix:** `spec/quality_thresholds.json` wird **als erster Schritt von WS-B/WS-C** mit **provisorischen, dokumentierten** Werten angelegt (oder in FQ-000 gefaltet), damit FQ-B1/FQ-C1/FQ-D1 es lesen können. FQ-030 **ratifiziert** die Werte am Ende (macht sie „required"). Die JPL-Toleranz bleibt **provisorisch, bis der Frame-Angleichungs-Beweis (FQ-B1) steht**, dann hart.
- **Dateien (neu):** `spec/quality_thresholds.json` (sun/moon-Accuracy, asc-Accuracy auf AA/A-Set, JPL-Toleranzen je Körperklasse, Jié-Toleranz, Aszendent-Toleranz), von Tests + CI-Gates gelesen; `docs/verification_vectors.md` verweist darauf.
- **Acceptance:** Schwellen zentral, versioniert, begründet; kein magischer Wert im Test-Code; provisorisch→ratifiziert nachvollziehbar im Git-Verlauf.

### WS-D — CI/CD-Ausbau (G6, Gates)

**FQ-D1 — PR-Gate-Job „verify-accuracy"** · REQ FQ-CI-01
- **Dateien:** `.github/workflows/ci.yml` (Job ergänzen) oder neu `.github/workflows/verify.yml`.
- **Vorgehen:** Job läuft FQ-A1/A2-Attestierung, FQ-B1/B2 (gegen **committete** JPL/Jié-Fixtures, offline), FQ-C1-Regression, prüft Werte gegen `spec/quality_thresholds.json`. Blockiert Merge bei Regression.
- **Acceptance:** Job in Branch-Protection als required; roter Job bei absichtlich verschlechtertem Wert (Negativ-Probe im PR gezeigt).

**FQ-D2 — Nächtlicher Live-Oracle-Diff** · REQ FQ-CI-02
- **Dateien (neu):** `.github/workflows/nightly-reference.yml` (`schedule: cron`), `scripts/build_jpl_reference.py` (mit `--check`).
- **Vorgehen:** nächtlich **live** JPL Horizons ziehen und gegen committete Fixtures + Engine diffen → erkennt Drift der eingefrorenen Referenz UND Engine-Regression. Öffnet Issue bei Delta. Netz-Flakes tolerant (retry, kein Blockieren von main).
- **Acceptance:** Workflow grün im Normalfall; erzeugt Issue-Artefakt bei künstlichem Delta.

**FQ-D3 — Release-Gate: Image-Attestierung + Prod-Smoke** · REQ FQ-CI-03, FQ-OBS-01
- **Dateien:** `.github/workflows/deploy-cloudrun.yml` (Pre-/Post-Deploy-Steps), neu `scripts/attest_image_ephemeris.py`, `scripts/prod_attestation_smoke.py`.
- **Vorgehen:** Vor Promote: im **gebauten** Image beweisen, dass `.se1` vorhanden + Referenz-Rechnung `ephemeris_mode==SWIEPH` liefert (nicht nur im CI-Runner). **Cloud-Run-Muster gegen Live-Traffic-Risiko:** neue Revision mit **Tag + 0 % Traffic** deployen, die **Revisions-URL** (nicht die Live-URL) smoke-testen → `ephemeris_mode==SWIEPH`, `house_system_fallback==false`, `tzdb_version_id!="unknown"`; Traffic-Migration **erst bei Pass**. Kein Rollback nötig, weil Live nie eine schlechte Revision sieht.
- **Kosten/Credential:** Compute-Routes sind billable + rate-limited → Smoke braucht dediziertes internes Test-Key-Secret **oder** einen nicht-billable Health-Pfad, der SWIEPH trotzdem ausübt (s. FQ-F1). Im Workflow explizit verdrahten.
- **Acceptance:** Deploy schlägt fehl, wenn Image ohne Ephemeriden gebaut wird (Negativ-Probe); Revisions-Smoke-Log zeigt attestierten Modus **vor** Traffic-Migration; Live-URL sieht nie eine ungeprüfte Revision.

### WS-E — Regelmäßiger unabhängiger Claude-Audit (G5)

**FQ-E1 — Geplanter adversarialer Claude-Audit-Workflow** · REQ FQ-AUD-01
- **Dateien (neu):** `.github/workflows/claude-audit.yml` (`schedule: weekly` + `workflow_dispatch`), `.claude/commands/fufire-independent-audit.md` (Audit-Prompt/Skill), `docs/audits/` (Report-Ablage).
- **Charter eng gefasst (LLM darf NIE Wahrheitswerte selbst rechnen):** Ein LLM kann geozentrische scheinbare Ekliptik-Längen oder Jié-Zeitstempel **nicht** berechnen — jedes Finding der Form „Engine sagt X, wahr ist Y" mit prosa-/modell-abgeleitetem Y ist eine Halluzination als Messung, exakt der Fehler, den der Audit fangen soll. Der Audit darf **nur**: (a) **Anti-Fabrication-Code-Muster-Scan** (erfundene Werte als gemessen ausgegeben — vgl. BFF-geflaggtes Fake-Retrograde/Longitude-Muster `retrograde = sin(index) < -0.6`) — das ist die genuin LLM-geeignete, hochwertige Aufgabe; (b) neue Vektoren **zur committeten Harness hinzufügen und diese ausführen** — die **deterministische Oracle-Harness** liefert die Zahl, **nie das Modell**; (c) AST/grep-Checks (neue `swe.calc*`-Direktaufrufe) + `quality_thresholds`-Abgleich gegen echten Code + OpenAPI/Contract-Drift. **Prosa-gerechnete Wahrheitswerte sind explizit verboten.**
- **Output:** strukturierter Report → öffnet **Issue** (kein Auto-Merge). Jede Behauptung: Datei:Zeile + reproduzierbarer Harness-Vektor (Kopplung an `konfabulations-audit`). **Issue-De-Dup:** kein neues Issue öffnen, wenn ein offenes mit gleicher Signatur existiert — sonst wird der Wochen-Job zum Spam-Generator.
- **Guardrails:** read-only auf Code (nur Harness-Vektoren als **PR** vorschlagen, kein Direkt-Write auf main); Issue-Erstellung erlaubt; Kosten-/Zeitlimit; unbelegte Findings als „unverified" markiert, nicht als Fakt.
- **Tests:** Trockenlauf via `workflow_dispatch` auf Branch mit absichtlich eingebautem Fake-Wert-Muster → Audit muss es via Code-Muster-Scan finden.
- **Acceptance:** manueller Dispatch erzeugt Issue; eingebautes Fehlermuster als CONFIRMED gelistet; sauberer Branch → „keine bestätigten Findings"; zweiter Lauf bei gleichem Befund öffnet **kein** Duplikat.

### WS-F — Prod-Laufzeit-Beobachtung (G6)

**FQ-F1 — Laufzeit-Attestierungs-Metrik + Alarm** · REQ FQ-OBS-01
- **Dateien:** Middleware/Response-Hook **per grep lokalisieren** (`bazi_engine/middleware.py` evtl. nicht vorhanden — FastAPI-Middleware wird oft inline in `app.py` registriert; erst prüfen), Health-Endpoint in `bazi_engine/app.py`, Cloud-Run-Monitoring-Konfig.
- **Konsistenz mit FQ-A1 (kein Widerspruch):** Nach WS-A **kann es keine erfolgreiche MOSEPH-Response geben** — der Pfad wirft `EphemerisUnavailableError` (5xx). Daher **nicht** MOSEPH-Mode-Responses zählen (die gibt es nicht mehr), sondern die **Attestierungs-Ausnahme-Rate**: `EphemerisUnavailableError`/einschlägige 5xx + Health-Probe-Fehler. Zusätzlich Struktur-Log-Feld `ephemeris_mode`/`house_system_fallback`/`tzdb`-Version je erfolgreiche Response (Erwartung: konstant SWIEPH/false/gepinnt).
- **Vorgehen:** Health/Ready-Check schlägt fehl, wenn eine Referenz-Rechnung nicht SWIEPH liefert; Alarm bei jeder Attestierungs-Ausnahme oder `tzdb=="unknown"`.
- **Tests:** `tests/test_healthcheck_attestation.py` (leerer Ephemeriden-Pfad → Health rot).
- **Acceptance:** Health rot ohne Ephemeriden; strukturiertes Log-Feld in Prod sichtbar; Alarm-Regel (Attestierungs-Ausnahme-Rate > 0) im Runbook dokumentiert.

---

## 4. Risiken & Rollback

| Risiko | Gegenmaßnahme / Rollback |
|--------|--------------------------|
| **JPL-Ekliptik-Bezug falsch angeglichen** (date-of vs J2000, Aberration) → systematischer Scheinfehler | FQ-B1: Bezug explizit dokumentiert + an einem manuell gegen astro.com verifizierten Referenzpunkt kalibriert, bevor Toleranzen scharfgestellt werden. |
| **Netz-Oracle flakey** (Horizons down) blockiert Entwicklung | PR-Gate nutzt nur **committete** Fixtures (offline); Live-Diff nur nächtlich, non-blocking, mit Retry. |
| **TZ-Modell-Änderung (FQ-C1) verschiebt bestehende Snapshots** | Snapshot-Diffs im PR sichtbar machen; Änderung nur mit dokumentierter Begründung je verschobenem Fall; `UPDATE_SNAPSHOTS` bewusst + reviewt, nie blind. |
| **Attestierungs-Härtung bricht Prod** (wirft wo vorher tolerant) | Feature hinter Config; Staging-Rollout; Rollback = Wrapper-Enforcement per Env deaktivierbar, aber Default = hart. |
| **Claude-Audit produziert Rauschen / Fehlalarme** | Prompt erzwingt Beleg je Finding + Verifikation; Output nur als Issue (kein Auto-Change); wöchentlich statt bei jedem PR. |
| **Referenzdaten selbst falsch** (astro.com C-Quality Fälle wie Churchill) | Mismatches dürfen als „Referenzfehler mit Beleg" geschlossen werden — niemals durch stille Toleranz-Aufweichung; Data-Quality-Feld (AA/A/C) im Report führen. |
| **Premium-Schwelle zu hart → Dauer-Rot** | Schwelle in `spec/quality_thresholds.json` versioniert, mit Begründung; Anhebung ist bewusster, reviewter Commit. |

**Coverage-Gate-Nebenwirkung:** Neue `scripts/build_jpl_reference.py`, `tests/oracle/*` und Netz-Clients zählen gegen `--cov-fail-under=75`. Untestbare Netz-Client-Zeilen per `.coveragerc`-Exclude (`scripts/`, Oracle-Clients) ausnehmen, sonst kippt der bestehende Gate — bei FQ-B1/FQ-D2 mit einplanen.

**Globaler Rollback:** Alle neuen Gates sind eigene Jobs/Workflows. Deaktivieren = Job aus Branch-Protection nehmen bzw. Workflow-Datei zurücknehmen; Engine-Änderungen (FQ-A1/C1) sind isolierte PRs, einzeln revertierbar.

---

## 5. Reihenfolge / Definition of Done (gesamt)
1. FQ-000 Setup grün.
2. WS-A (Attestierung) — Fundament, zuerst.
3. WS-B + WS-C parallel (unabhängige Wahrheit + Premium-Genauigkeit).
4. FQ-030 Schwellen fixieren.
5. WS-D CI-Gates verdrahten (PR/nightly/release).
6. WS-E Claude-Audit, WS-F Prod-Observability.

**Gesamt-DoD:** PR-Gate erzwingt Attestierung + JPL/Jié-Diffs + Premium-Schwellen; nächtlicher Live-Diff + wöchentlicher Claude-Audit laufen; Release-Gate + Prod-Smoke attestieren SWIEPH; kein `swe.calc*`-Direktaufruf; keine Response mit `"unknown"`-Attestierung.
