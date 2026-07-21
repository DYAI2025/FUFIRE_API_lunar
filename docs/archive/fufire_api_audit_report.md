# GPT: GPT-5.5 Thinking — 22.05.2026 / 23:38 Uhr — Topic: FuFire-API Audit eines ZIP-Repositories

## SMART-CONTEXT

**1. Current situation:**  
Ein ZIP-Repository `FuFirE-main (6).zip` wurde für einen lokalen, sandboxed API-Audit bereitgestellt. Die beigefügte Audit-Spezifikation verlangt eine evidence-first Gap-Analyse mit Repository-Recon, OpenAPI-Prüfung, Runtime-Tests und Contradiction Register.

**2. Key stakeholders:** Dev-Team, API-Integratoren, B2B-Kunden, Ops/SRE, Security, QA/Release Management, technische Dokumentation.

**3. Important constraints:** Keine Tests gegen Produktivsysteme; lokale/sandboxed Tests; keine Credential-Extraktion; keine destruktiven Requests; fehlende SE1-Ephemeris-Dateien im Sandbox-Dateisystem; keine Garantie, dass die Sandbox der Produktions-Docker-Umgebung entspricht.

**4. Relevant history:** Das Repository beschreibt FuFirE/BAFE als FastAPI-basierte Berechnungs-API mit BaZi, westlicher Astrologie, Fusion, Transits, Experience, Superglue-Proxy, Impact und verstecktem Webhook. `CONTRACT.md` bezeichnet `spec/openapi/openapi.json` als Source of Truth.

**5. Goals:**  
Primärziel: belastbare API-Gap-Analyse mit belegbaren Findings.  
Nebenziele: Endpunkt-Inventar, OpenAPI-Drift-Prüfung, lokale Runtime-Tests, Dokumentationskonflikte, Root-Cause-Synthese, Remediation-Backlog.

**6. Arbeitsdefinition des Problems:**  
Zu prüfen ist, ob Code, OpenAPI, Dokumentation, Tests und lokales Runtime-Verhalten konsistent genug für produktionsnahe API-Verträge sind. Besondere Aufmerksamkeit gilt Drift zwischen Source-of-Truth-Behauptung, tatsächlicher Route Map und realen Fehlerantworten.

### Offene Fragen
- Sind die SE1-Ephemeris-Dateien absichtlich nur über Docker/Deployment verfügbar oder sollen lokale Entwickler sie separat installieren?
- Soll `/chart` public-legacy, internal oder deprecated sein?
- Soll der ElevenLabs Webhook öffentlich `/api/webhooks/chart` oder intern `/internal/api/webhooks/chart` heißen?

## SPEC

- **Primary objective:** Erstelle eine evidence-first FuFire API Audit & Gap Analysis.
- **Specific requirements:** Repository entpacken, API inventarisieren, OpenAPI prüfen, GET/POST lokal testen, Widersprüche registrieren, Findings mit Root Cause und Fix liefern.
- **Constraints:** Nur lokale Tests; keine externen Produktivsysteme; keine erfundenen Testergebnisse; nicht ausführbare Punkte als `BLOCKED`/`NOT_RUN` markieren.
- **Target:** FastAPI/Python-Repository im ZIP; Stakeholder Dev/Ops/API-Konsumenten.
- **DO:** Code, OpenAPI, Docs, Tests und Runtime gegenüberstellen.
- **DON'T:** Keine Produktivaufrufe, keine Credential-Nutzung, keine Annahmen als Fakten.
- **Success criteria / quality metrics:** Vollständige Route Map; belegbare Findings; Testmatrix mit tatsächlichen Statuscodes; klare Priorisierung.
- **Evaluation process:** Statische Analyse + `app.routes`/`app.openapi()` + lokale `TestClient`-Requests + `pytest`-Auszüge + Dokumentationsvergleich.

## REASONING-TECHNIQUE

- **Gewählt:** Plan-and-Solve
- **Begründung:** Audit-Ziel ist klar strukturiert; die Lösung benötigt mehrere sequentielle Schritte: Recon → Contract-Prüfung → Runtime-Tests → Findings → Remediation. Für riskante Stellen wurde zusätzlich ein Contradiction-Hunt angewandt, aber nicht als primäre Technik.

## ITERATION_CYCLE 1

- **Ziel:** Repository-Struktur, Stack und API-Einstiegspunkte sicher bestimmen.
- **Schritte:** ZIP entpackt, Datei-Inventar erstellt, `pyproject.toml`, Router, App-Mounts, Docs und OpenAPI-Dateien identifiziert.
- **Ergebnis:** FastAPI/Python-Projekt mit 51 schema-visible Operationen und 1 hidden internal Webhook. Relevante Entry Points: `bazi_engine/app.py`, `bazi_engine/routers/*`, `spec/openapi/openapi.json`, `docs/API_REFERENCE.md`, `docs/api/01_developer_api_reference.md`.
- **KPI-Abgleich:** Route Inventory erfüllt; Stack erkannt; OpenAPI-Datei gefunden.
- **Selbstkritik:** ZIP enthält eine verschachtelte Kopie `FuFirE-main/FuFirE-main`; Audit fokussiert auf äußeres Root, weil dort aktive `bazi_engine/`, `tests/`, `spec/` und `docs/` liegen.

## ITERATION_CYCLE 2

- **Ziel:** OpenAPI, Dokumentation und Runtime-Verhalten gegeneinander prüfen.
- **Schritte:** `app.openapi()` exportiert, `scripts/export_openapi.py --check` ausgeführt, Endpoint Security/Responses gescannt, Hashseed-basierte OpenAPI-Nondeterministik getestet.
- **Ergebnis:** OpenAPI driftet; Komponenten-Naming für `ChartRequest` ist nondeterministisch; 39 geschützte Operationen dokumentieren keine 401/429/503.
- **KPI-Abgleich:** OpenAPI-Konformität teilweise geprüft; Drift reproduziert; Widerspruchsregister gefüllt.
- **Selbstkritik:** Kein externer OpenAPI-Validator wurde als harte Quelle genutzt; die belastbareren Befunde stammen aus FastAPI-Runtime, Export-Check und direktem Diff.

## ITERATION_CYCLE 3

- **Ziel:** Lokale Tests und Findings finalisieren.
- **Schritte:** 30 Runtime-Tests mit `TestClient`, targeted pytest, full pytest mit/ohne fehlendes `respx`, Root-Cause-Synthese und Remediation Backlog erstellt.
- **Ergebnis:** Mehrere Kernendpunkte sind lokal wegen fehlender SE1-Dateien `503`; TST/Validate/Narrative/Signature-Delta funktionieren; Superglue-Konfigurationsfehler wird 500; Webhook-Dokumentationspfad ist 404.
- **KPI-Abgleich:** GET und POST repräsentativ getestet; nicht vollständig lauffähige astronomische Endpunkte sauber als ephemeris-blocked markiert.
- **Selbstkritik:** Die Sandbox entspricht nicht zwingend Docker-Prod, weil Docker SE1-Dateien kopiert und `SE_EPHE_PATH` setzt. Runtime-503-Befunde sind daher lokale/developer-experience Findings, nicht automatisch Produktionsausfälle.

---

# FuFire API Audit & Gap Analysis Report

## 1. Executive Summary

**Gesamtzustand:** Die API ist strukturell deutlich über MVP-Niveau: FastAPI-Router sind typisiert, ErrorEnvelope-Handler existieren, Request-ID-Middleware ist vorhanden, OpenAPI wird aktiv generiert, und eine große Testbasis liegt vor. Der Audit findet jedoch kritische Contract- und Dokumentationsdrift: OpenAPI ist nicht stabil, Dokumentation nennt falsche/fehlende Pfade, reale Fehlerantworten sind in OpenAPI unvollständig, und die lokale Quickstart-Erfahrung scheitert für viele Kernendpunkte ohne Ephemeris-Daten.

**Wichtigste Risiken:**

1. **Contract Drift / SDK-Risiko:** OpenAPI-Komponenten ändern sich abhängig von Prozessbedingungen wegen doppelter `ChartRequest`-Modellnamen.
2. **Dokumentationsbruch:** Webhook-Pfad `/api/webhooks/chart` ist dokumentiert, aber nicht gemountet.
3. **Undokumentierte Fehlerfälle:** 401/429/503 fehlen fast überall in OpenAPI, obwohl Runtime sie produziert.
4. **Lokale Nicht-Ausführbarkeit:** Viele Kernendpunkte liefern 503 ohne SE1-Dateien; README-Quickstart deckt das nicht ab.
5. **Testdrift:** Targeted API tests sind grün, aber die vollständige Suite zeigt Snapshot-Drift.

**Findings nach Severity:**

| Severity | Count |
|---|---:|
| Critical | 0 |
| High | 4 |
| Medium | 7 |
| Low | 2 |
| Info | 0 |

**Sofortmaßnahmen:**

1. Pydantic-Modellnamen kollisionsfrei machen und OpenAPI regenerieren.
2. Webhook-Pfad-Entscheidung treffen und Docs/Routing synchronisieren.
3. Gemeinsame ErrorEnvelope-Responses 401/429/500/503 in OpenAPI einziehen.
4. README-Quickstart um SE1-/Docker-Pfad ergänzen.
5. Superglue-Konfigurationsfehler als 503 statt 500 mappen.

## 2. Repository Inventory

**Erkannter Tech Stack:**

- Sprache: Python, `requires-python >=3.10` (`pyproject.toml:9`)
- Framework: FastAPI + Uvicorn (`pyproject.toml:12-13`)
- Validation: Pydantic + `jsonschema` Draft-07 für `/validate`
- Rate limiting: `slowapi` (`pyproject.toml:16`, `bazi_engine/limiter.py`)
- External/astronomical dependency: `pyswisseph`, lokale SE1-Dateien erforderlich
- HTTP client: `httpx` für Superglue hooks
- Deployment: Dockerfile mit ephemeris build stage; `SE_EPHE_PATH=/usr/local/share/swisseph`

**Relevante Dateien:**

| Area | Files |
|---|---|
| App entry | `bazi_engine/app.py`, `api/index.py` |
| Routers | `bazi_engine/routers/*.py` |
| Auth/rate limit | `bazi_engine/auth.py`, `bazi_engine/limiter.py`, `bazi_engine/middleware.py` |
| OpenAPI | `spec/openapi/openapi.json`, `scripts/export_openapi.py`, `openapitools.json` |
| JSON Schemas | `spec/schemas/ValidateRequest.schema.json`, `spec/schemas/ValidateResponse.schema.json`, `spec/schemas/refdata_manifest.schema.json` |
| Docs | `README.md`, `docs/API_REFERENCE.md`, `docs/api/01_developer_api_reference.md`, `CONTRACT.md`, `docs/ERROR_CODES.md` |
| Tests | `tests/` with 100+ test files, `tests/snapshots/moseph/` |
| Deployment | `Dockerfile`, `Dockerfile.ephe-base`, `fly.toml`, `railway.toml` |

**Erkannte Start-/Testbefehle:**

```bash
uvicorn bazi_engine.app:app --reload
python scripts/export_openapi.py --check
pytest -q
pytest -q tests/test_openapi_contract.py tests/test_b2b_api_audit.py tests/test_endpoint_negative.py tests/test_error_handling.py tests/test_error_sanitization.py tests/test_endpoints.py
```

**Audit commands actually executed:**

```bash
unzip -q '/mnt/data/FuFirE-main (6).zip' -d /mnt/data/fufire-audit-work/repo
PYTHONPATH=$PWD python3 scripts/export_openapi.py --check
PYTHONPATH=$PWD pytest -q tests/test_openapi_contract.py tests/test_b2b_api_audit.py tests/test_endpoint_negative.py tests/test_error_handling.py tests/test_error_sanitization.py tests/test_endpoints.py --tb=short --disable-warnings
PYTHONPATH=$PWD pytest -q --tb=short --disable-warnings --maxfail=20
PYTHONPATH=$PWD python3 /mnt/data/fufire-audit-work/run_runtime_audit.py
```

## 3. API Surface Map

Runtime inventory found **51 schema-visible operations** and **1 hidden internal operation**.

| Method | Path | Handler/Source | Auth | Request Schema / Params | Response Schema | Documented? | Tested? |
|---|---|---|---|---|---|---|---|
| GET | / | bazi_engine/routers/info.py:79 | Public | — | bazi_engine.routers.info.RootResponse | OpenAPI | partial |
| GET | /health | bazi_engine/routers/info.py:124 | Public | — | bazi_engine.routers.info.HealthResponse | OpenAPI | partial |
| GET | /ready | bazi_engine/routers/info.py:130 | Public | — | bazi_engine.routers.info.HealthResponse | OpenAPI | partial |
| GET | /build | bazi_engine/routers/info.py:146 | Public | — | bazi_engine.routers.info.BuildResponse | OpenAPI | partial |
| GET | /api | bazi_engine/routers/info.py:152 | Public | query:datum;query:zeit;query:ort;query:tz;query:lon;query:lat;query:ambiguousTime;query:nonexistentTime | bazi_engine.routers.info.ApiResponse | OpenAPI | partial |
| GET | /info/wuxing-mapping | bazi_engine/routers/info.py:193 | Public | — | bazi_engine.routers.info.WuxingMappingResponse | OpenAPI | partial |
| POST | /validate | /opt/pyvenv/lib/python3.13/site-packages/slowapi/extension.py:51 | API key / internal auth | payload:<class 'bazi_engine.routers.validate.ValidateRequest'> | bazi_engine.routers.validate.ValidateResponse | OpenAPI | partial |
| POST | /calculate/bazi | /opt/pyvenv/lib/python3.13/site-packages/slowapi/extension.py:198 | API key / internal auth | req:<class 'bazi_engine.routers.bazi.BaziRequest'> | bazi_engine.routers.bazi.BaziResponse | OpenAPI | partial |
| POST | /calculate/western | /opt/pyvenv/lib/python3.13/site-packages/slowapi/extension.py:92 | API key / internal auth | req:<class 'bazi_engine.routers.western.WesternRequest'> | bazi_engine.routers.western.WesternResponse | OpenAPI | partial |
| POST | /calculate/fusion | /opt/pyvenv/lib/python3.13/site-packages/slowapi/extension.py:83 | API key / internal auth | req:<class 'bazi_engine.routers.fusion.FusionRequest'> | bazi_engine.routers.fusion.FusionResponse | OpenAPI | partial |
| POST | /calculate/wuxing | bazi_engine/routers/fusion.py:193 | API key / internal auth | req:<class 'bazi_engine.routers.fusion.WxRequest'> | bazi_engine.routers.fusion.WxResponse | OpenAPI | partial |
| POST | /calculate/tst | bazi_engine/routers/fusion.py:256 | API key / internal auth | req:<class 'bazi_engine.routers.fusion.TSTRequest'> | bazi_engine.routers.fusion.TSTResponse | OpenAPI | partial |
| POST | /chart | bazi_engine/routers/chart.py:167 | API key / internal auth | req:<class 'bazi_engine.routers.chart.ChartRequest'> | bazi_engine.routers.chart.ChartResponse | OpenAPI | partial |
| GET | /transit/now | /opt/pyvenv/lib/python3.13/site-packages/slowapi/extension.py:165 | API key / internal auth | query:datetime_param | bazi_engine.routers.transit.TransitNowResponse | OpenAPI | partial |
| POST | /transit/state | bazi_engine/routers/transit.py:191 | API key / internal auth | <class 'bazi_engine.routers.transit.TransitStateRequest'> | bazi_engine.routers.transit.TransitStateResponse | OpenAPI | partial |
| GET | /transit/timeline | bazi_engine/routers/transit.py:200 | API key / internal auth | query:days | bazi_engine.routers.transit.TimelineResponse | OpenAPI | partial |
| POST | /transit/narrative | bazi_engine/routers/transit.py:208 | API key / internal auth | <class 'bazi_engine.routers.transit.NarrativeRequest'> | bazi_engine.routers.transit.NarrativeResponse | OpenAPI | partial |
| POST | /experience/bootstrap | /opt/pyvenv/lib/python3.13/site-packages/slowapi/extension.py:430 | API key / internal auth | <class 'bazi_engine.routers.experience.BootstrapRequest'> | bazi_engine.routers.experience.BootstrapResponse | OpenAPI | partial |
| POST | /experience/signature-delta | /opt/pyvenv/lib/python3.13/site-packages/slowapi/extension.py:483 | API key / internal auth | <class 'bazi_engine.routers.experience.SignatureDeltaRequest'> | bazi_engine.routers.experience.SignatureDeltaResponse | OpenAPI | partial |
| POST | /experience/daily | /opt/pyvenv/lib/python3.13/site-packages/slowapi/extension.py:627 | API key / internal auth | <class 'bazi_engine.routers.experience.DailyRequest'> | bazi_engine.routers.experience.DailyResponse | OpenAPI | partial |
| GET | /api/profile/{user_id} | /opt/pyvenv/lib/python3.13/site-packages/slowapi/extension.py:58 | API key / internal auth | path:user_id | bazi_engine.routers.superglue.SuperglueProxyResponse | OpenAPI | partial |
| GET | /api/profile | /opt/pyvenv/lib/python3.13/site-packages/slowapi/extension.py:71 | API key / internal auth | query:user_id | bazi_engine.routers.superglue.SuperglueProxyResponse | OpenAPI | partial |
| GET | /api/daily/{user_id} | /opt/pyvenv/lib/python3.13/site-packages/slowapi/extension.py:84 | API key / internal auth | path:user_id | bazi_engine.routers.superglue.SuperglueProxyResponse | OpenAPI | partial |
| GET | /api/daily | /opt/pyvenv/lib/python3.13/site-packages/slowapi/extension.py:97 | API key / internal auth | query:user_id | bazi_engine.routers.superglue.SuperglueProxyResponse | OpenAPI | partial |
| POST | /api/profile/{user_id}/chart | /opt/pyvenv/lib/python3.13/site-packages/slowapi/extension.py:110 | API key / internal auth | typing.Optional[bazi_engine.routers.superglue.ChartRequest] | bazi_engine.routers.superglue.SuperglueProxyResponse | OpenAPI | partial |
| POST | /impact/active | /opt/pyvenv/lib/python3.13/site-packages/slowapi/extension.py:42 | API key / internal auth | <class 'bazi_engine.impact_types.ImpactRequest'> | bazi_engine.impact_types.ImpactResponse | OpenAPI | partial |
| GET | /v1/ | bazi_engine/routers/info.py:79 | Public | — | bazi_engine.routers.info.RootResponse | OpenAPI | custom |
| GET | /v1/health | bazi_engine/routers/info.py:124 | Public | — | bazi_engine.routers.info.HealthResponse | OpenAPI | custom |
| GET | /v1/ready | bazi_engine/routers/info.py:130 | Public | — | bazi_engine.routers.info.HealthResponse | OpenAPI | custom |
| GET | /v1/build | bazi_engine/routers/info.py:146 | Public | — | bazi_engine.routers.info.BuildResponse | OpenAPI | custom |
| GET | /v1/api | bazi_engine/routers/info.py:152 | Public | query:datum;query:zeit;query:ort;query:tz;query:lon;query:lat;query:ambiguousTime;query:nonexistentTime | bazi_engine.routers.info.ApiResponse | OpenAPI | custom |
| GET | /v1/info/wuxing-mapping | bazi_engine/routers/info.py:193 | Public | — | bazi_engine.routers.info.WuxingMappingResponse | OpenAPI | custom |
| POST | /v1/validate | /opt/pyvenv/lib/python3.13/site-packages/slowapi/extension.py:51 | API key / internal auth | payload:<class 'bazi_engine.routers.validate.ValidateRequest'> | bazi_engine.routers.validate.ValidateResponse | OpenAPI | custom |
| POST | /v1/calculate/bazi | /opt/pyvenv/lib/python3.13/site-packages/slowapi/extension.py:198 | API key / internal auth | req:<class 'bazi_engine.routers.bazi.BaziRequest'> | bazi_engine.routers.bazi.BaziResponse | OpenAPI | custom |
| POST | /v1/calculate/western | /opt/pyvenv/lib/python3.13/site-packages/slowapi/extension.py:92 | API key / internal auth | req:<class 'bazi_engine.routers.western.WesternRequest'> | bazi_engine.routers.western.WesternResponse | OpenAPI | custom |
| POST | /v1/calculate/fusion | /opt/pyvenv/lib/python3.13/site-packages/slowapi/extension.py:83 | API key / internal auth | req:<class 'bazi_engine.routers.fusion.FusionRequest'> | bazi_engine.routers.fusion.FusionResponse | OpenAPI | custom |
| POST | /v1/calculate/wuxing | bazi_engine/routers/fusion.py:193 | API key / internal auth | req:<class 'bazi_engine.routers.fusion.WxRequest'> | bazi_engine.routers.fusion.WxResponse | OpenAPI | custom |
| POST | /v1/calculate/tst | bazi_engine/routers/fusion.py:256 | API key / internal auth | req:<class 'bazi_engine.routers.fusion.TSTRequest'> | bazi_engine.routers.fusion.TSTResponse | OpenAPI | custom |
| GET | /v1/transit/now | /opt/pyvenv/lib/python3.13/site-packages/slowapi/extension.py:165 | API key / internal auth | query:datetime_param | bazi_engine.routers.transit.TransitNowResponse | OpenAPI | custom |
| POST | /v1/transit/state | bazi_engine/routers/transit.py:191 | API key / internal auth | <class 'bazi_engine.routers.transit.TransitStateRequest'> | bazi_engine.routers.transit.TransitStateResponse | OpenAPI | custom |
| GET | /v1/transit/timeline | bazi_engine/routers/transit.py:200 | API key / internal auth | query:days | bazi_engine.routers.transit.TimelineResponse | OpenAPI | custom |
| POST | /v1/transit/narrative | bazi_engine/routers/transit.py:208 | API key / internal auth | <class 'bazi_engine.routers.transit.NarrativeRequest'> | bazi_engine.routers.transit.NarrativeResponse | OpenAPI | custom |
| POST | /v1/experience/bootstrap | /opt/pyvenv/lib/python3.13/site-packages/slowapi/extension.py:430 | API key / internal auth | <class 'bazi_engine.routers.experience.BootstrapRequest'> | bazi_engine.routers.experience.BootstrapResponse | OpenAPI | custom |
| POST | /v1/experience/signature-delta | /opt/pyvenv/lib/python3.13/site-packages/slowapi/extension.py:483 | API key / internal auth | <class 'bazi_engine.routers.experience.SignatureDeltaRequest'> | bazi_engine.routers.experience.SignatureDeltaResponse | OpenAPI | custom |
| POST | /v1/experience/daily | /opt/pyvenv/lib/python3.13/site-packages/slowapi/extension.py:627 | API key / internal auth | <class 'bazi_engine.routers.experience.DailyRequest'> | bazi_engine.routers.experience.DailyResponse | OpenAPI | custom |
| GET | /v1/profile/{user_id} | /opt/pyvenv/lib/python3.13/site-packages/slowapi/extension.py:58 | API key / internal auth | path:user_id | bazi_engine.routers.superglue.SuperglueProxyResponse | OpenAPI | custom |
| GET | /v1/profile | /opt/pyvenv/lib/python3.13/site-packages/slowapi/extension.py:71 | API key / internal auth | query:user_id | bazi_engine.routers.superglue.SuperglueProxyResponse | OpenAPI | custom |
| GET | /v1/daily/{user_id} | /opt/pyvenv/lib/python3.13/site-packages/slowapi/extension.py:84 | API key / internal auth | path:user_id | bazi_engine.routers.superglue.SuperglueProxyResponse | OpenAPI | custom |
| GET | /v1/daily | /opt/pyvenv/lib/python3.13/site-packages/slowapi/extension.py:97 | API key / internal auth | query:user_id | bazi_engine.routers.superglue.SuperglueProxyResponse | OpenAPI | custom |
| POST | /v1/profile/{user_id}/chart | /opt/pyvenv/lib/python3.13/site-packages/slowapi/extension.py:110 | API key / internal auth | typing.Optional[bazi_engine.routers.superglue.ChartRequest] | bazi_engine.routers.superglue.SuperglueProxyResponse | OpenAPI | custom |
| POST | /v1/impact/active | /opt/pyvenv/lib/python3.13/site-packages/slowapi/extension.py:42 | API key / internal auth | <class 'bazi_engine.impact_types.ImpactRequest'> | bazi_engine.impact_types.ImpactResponse | OpenAPI | custom |


## 4. OpenAPI Conformance Review

### 4.1 Specification quality

- OpenAPI version: `3.1.0`.
- `spec/openapi/openapi.json` exists and contains 51 paths/operations.
- Runtime `app.openapi()` also reports 51 paths/operations.
- Byte-level drift check fails: `scripts/export_openapi.py --check` returns `FAIL: OpenAPI spec drifted. Run: python scripts/export_openapi.py`.
- Drift root cause is not merely formatting: component references for colliding `ChartRequest` model names change.

### 4.2 Schema problems

- Duplicate Pydantic model name `ChartRequest` exists in at least two routers.
- Depending on `PYTHONHASHSEED`, either `/chart` or Superglue chart-trigger gets the short `ChartRequest` component name while the other receives a module-prefixed name.
- This makes OpenAPI export nondeterministic and breaks stable SDK generation.

### 4.3 Status code coverage

- Protected operations declare `security=[{'APIKeyHeader': []}]`, but OpenAPI responses omit `401` for all 39 protected operations.
- 429 is described globally but not attached to operations.
- Ephemeris-dependent endpoints can return 503 but do not document 503 broadly.
- `/validate` is better documented than most endpoints: OpenAPI patch explicitly sets 200/422/500.

### 4.4 Security schemes

- `APIKeyHeader` exists as an OpenAPI `apiKey` header scheme.
- Auth runtime behavior is stronger than one doc claims: legacy business endpoints are protected when `FUFIRE_API_KEYS` is configured.
- Auth error code mismatch: docs say `invalid_api_key`, runtime says `unauthorized`.

### 4.5 Examples

- Core docs provide examples, but examples relying on astronomical computation fail locally without SE1 files.
- Webhook docs provide a non-mounted URL.

### 4.6 operationId/tags

- No duplicate/missing `operationId` detected across 51 operations.
- Global tag list omits `Superglue` and `Impact`, though 12 operations use those tags.

## 5. Endpoint Test Matrix

Runtime tests used FastAPI `TestClient` with `FUFIRE_API_KEYS=ff_pro_testsecret`, `SUPERGLUE_API_KEY` unset, `ELEVENLABS_TOOL_SECRET` unset, and no SE1 files in the sandbox cache.

| Test ID | Method | Path | Scenario | Expected | Actual | Status | Evidence |
|---|---|---|---|---|---|---|---|
| T001 | GET | /v1/health | public health | status 200 | 200 | PASS |  |
| T002 | GET | /v1/ready | public ready | status 200 | 200 | PASS |  |
| T003 | GET | /v1/build | public build | status 200 | 200 | PASS |  |
| T004 | GET | /v1/info/wuxing-mapping | public mapping | status 200 | 200 | PASS |  |
| T005 | GET | /v1/api?datum=1990-05-23&zeit=12:34&tz=Europe/Berlin&lon=13.405&lat=52.52 | public legacy sun lookup mirror | status 200 or 503 if ephemeris missing | 503 | PASS | ephemeris_unavailable / Swiss Ephemeris files missing. Provide them via SE_EPHE_PATH or ephe_path. Missing: ['sepl_18.se1', 'semo_18.se1', 'seas_18.se1', 'seplm |
| T006 | POST | /v1/calculate/bazi | valid bazi | status 200 or 503 if ephemeris missing | 503 | PASS | ephemeris_unavailable / Swiss Ephemeris files missing. Provide them via SE_EPHE_PATH or ephe_path. Missing: ['sepl_18.se1', 'semo_18.se1', 'seas_18.se1', 'seplm |
| T007 | POST | /v1/calculate/western | valid western | status 200 or 503 if ephemeris missing | 503 | PASS | ephemeris_unavailable / Swiss Ephemeris files missing. Provide them via SE_EPHE_PATH or ephe_path. Missing: ['sepl_18.se1', 'semo_18.se1', 'seas_18.se1', 'seplm |
| T008 | POST | /v1/calculate/fusion | valid fusion | status 200 or 503 if ephemeris missing | 503 | PASS | ephemeris_unavailable / Swiss Ephemeris files missing. Provide them via SE_EPHE_PATH or ephe_path. Missing: ['sepl_18.se1', 'semo_18.se1', 'seas_18.se1', 'seplm |
| T009 | POST | /v1/calculate/wuxing | valid wuxing | status 200 or 503 if ephemeris missing | 503 | PASS | ephemeris_unavailable / Swiss Ephemeris files missing. Provide them via SE_EPHE_PATH or ephe_path. Missing: ['sepl_18.se1', 'semo_18.se1', 'seas_18.se1', 'seplm |
| T010 | POST | /v1/calculate/tst | valid tst | status 200 | 200 | PASS |  |
| T011 | POST | /v1/validate | valid validate | status 200 | 200 | PASS |  |
| T012 | GET | /v1/transit/now?datetime=2026-01-01T00:00:00Z | valid transit now | status 200 or 503 if ephemeris missing | 503 | PASS | ephemeris_unavailable / Swiss Ephemeris files missing. Provide them via SE_EPHE_PATH or ephe_path. Missing: ['sepl_18.se1', 'semo_18.se1', 'seas_18.se1', 'seplm |
| T013 | GET | /v1/transit/timeline?days=3 | valid transit timeline | status 200 or 503 if ephemeris missing | 503 | PASS | ephemeris_unavailable / Swiss Ephemeris files missing. Provide them via SE_EPHE_PATH or ephe_path. Missing: ['sepl_18.se1', 'semo_18.se1', 'seas_18.se1', 'seplm |
| T014 | POST | /v1/transit/state | valid transit state | status 200 or 503 if ephemeris missing | 503 | PASS | ephemeris_unavailable / Swiss Ephemeris files missing. Provide them via SE_EPHE_PATH or ephe_path. Missing: ['sepl_18.se1', 'semo_18.se1', 'seas_18.se1', 'seplm |
| T015 | POST | /v1/transit/narrative | valid transit narrative | status 200 | 200 | PASS |  |
| T016 | POST | /v1/experience/bootstrap | valid bootstrap | status 200 or 503 if ephemeris missing | 503 | PASS | ephemeris_unavailable / Swiss Ephemeris files missing. Provide them via SE_EPHE_PATH or ephe_path. Missing: ['sepl_18.se1', 'semo_18.se1', 'seas_18.se1', 'seplm |
| T017 | POST | /v1/experience/signature-delta | valid signature delta | status 200 | 200 | PASS |  |
| T018 | POST | /v1/experience/daily | valid daily | status 200 or 503 if ephemeris missing | 503 | PASS | ephemeris_unavailable / Swiss Ephemeris files missing. Provide them via SE_EPHE_PATH or ephe_path. Missing: ['sepl_18.se1', 'semo_18.se1', 'seas_18.se1', 'seplm |
| T019 | POST | /v1/impact/active | valid impact | status 200 or 503 if ephemeris missing | 503 | PASS | ephemeris_unavailable / Swiss Ephemeris files missing. Provide them via SE_EPHE_PATH or ephe_path. Missing: ['sepl_18.se1', 'semo_18.se1', 'seas_18.se1', 'seplm |
| T020 | GET | /v1/profile/testuser | superglue no env | status 503 config error preferred | 500 | FAIL | internal_error / Internal server error |
| T021 | GET | /v1/profile | superglue missing query | status 422 | 422 | PASS | validation_error / Request validation failed |
| T022 | POST | /v1/profile/testuser/chart | superglue chart no env | status 503 config error preferred | 500 | FAIL | internal_error / Internal server error |
| T023 | POST | /v1/calculate/bazi | missing auth | status 401 | 401 | PASS | unauthorized / Missing or invalid X-API-Key header |
| T024 | POST | /v1/calculate/bazi | invalid auth | status 401 | 401 | PASS | unauthorized / Missing or invalid X-API-Key header |
| T025 | POST | /v1/calculate/bazi | missing required field | status 422 | 422 | PASS | validation_error / Request validation failed |
| T026 | POST | /v1/calculate/bazi | wrong type | status 422 | 422 | PASS | validation_error / Request validation failed |
| T027 | POST | /v1/calculate/bazi | wrong content | status 422 | 422 | PASS | validation_error / Request validation failed |
| T028 | POST | /api/webhooks/chart | documented webhook path | status 200 or documented route reachable | 404 | FAIL | http_error / Not Found |
| T029 | POST | /internal/api/webhooks/chart | actual hidden webhook path no secret | status 503 if secret missing | 503 | PASS | service_unavailable / Webhook service is not configured |
| T030 | GET | /no-such-route | not found | status 404 | 404 | PASS | http_error / Not Found |


**Targeted pytest evidence:**

```text
173 passed, 2 skipped in 3.17s
```

**Full pytest evidence before installing missing dev dependency:**

```text
ERROR collecting tests/test_experience_daily_v2.py ... ModuleNotFoundError: No module named 'respx'
ERROR collecting tests/test_impact_golden.py ... ModuleNotFoundError: No module named 'respx'
ERROR collecting tests/test_impact_router.py ... ModuleNotFoundError: No module named 'respx'
ERROR collecting tests/test_space_weather.py ... ModuleNotFoundError: No module named 'respx'
ERROR collecting tests/test_superglue_client.py ... ModuleNotFoundError: No module named 'respx'
ERROR collecting tests/test_superglue_router.py ... ModuleNotFoundError: No module named 'respx'
```

**Full pytest after installing `respx`, stopped after 20 failures:**

```text
20 failed, 1506 passed, 49 skipped in 16.00s
```

Representative failure pattern:

```text
Snapshot mismatch ...
$.derivation_trace.day.day_anchor_evidence: ADDED
$.derivation_trace.day.day_master_stem: ADDED
$.derivation_trace.hour.time_standard_requested: ADDED = "CIVIL"
$.derivation_trace.hour.time_standard_used: ADDED = "CIVIL"
$.provenance.tzdb_version_id: "unknown" != "2026.1"
```

## 6. Contradiction Register

| ID | Source A | Source B | Contradiction | Severity | Investigation Result | Root Cause |
|---|---|---|---|---|---|---|
| C-001 | `CONTRACT.md` says 13 frozen endpoints | Runtime route inventory shows 51 schema-visible operations + 1 hidden | Contract table obsolete | Medium | Confirmed | API evolved without generated contract refresh |
| C-002 | Docs: `/api/webhooks/chart` | Runtime: `/internal/api/webhooks/chart`; `/api/webhooks/chart` is 404 | Documented webhook path unreachable | High | Confirmed by T028/T029 | App-level `/internal` prefix not reflected in docs |
| C-003 | Docs: legacy `/*` routes no auth | App mounts legacy business routers with `_protected`; runtime 401 | Auth behavior mismatch | Medium | Confirmed | Auth dependency applied to legacy routers |
| C-004 | OpenAPI says protected endpoints have security | Responses omit 401/429/503 | Error contract incomplete | High | Confirmed by OpenAPI scan and T023/T006 | OpenAPI patch incomplete |
| C-005 | Docs: every response has X headers | Superglue 500 has only `content-type` | Header guarantee false for unhandled errors | Medium | Confirmed by T020/T022 | Middleware header injection skipped on unhandled exception path |
| C-006 | Docs/OpenAPI advertise `X-RateLimit-Remaining` | Middleware says no fallback; runtime lacks header | Header contract overpromised | Medium | Confirmed by T010/T011 headers | Docs not updated after honest-header change |
| C-007 | README `pytest -q` quick run claim | Full suite fails/blocks in sandbox | Test command not green under audited env | Medium | Confirmed | Missing dev dependency then snapshot drift |
| C-008 | OpenAPI drift check exists | `scripts/export_openapi.py --check` fails | CI contract gate would fail | High | Confirmed | Nondeterministic component naming + committed drift |
| C-009 | API docs omit Superglue/Impact in catalog | Runtime/OpenAPI expose Superglue/Impact routes | Public surface incomplete | Medium | Confirmed | Docs not generated from OpenAPI |
| C-010 | `/chart` described internal | `/chart` is schema-visible legacy endpoint | Internal/public boundary unclear | Low | Confirmed | Routing does not encode internal status |

## 7. Findings


### FUFIRE-API-001 — OpenAPI component generation drifts because two request models share the name ChartRequest

- **Severity:** High
- **Category:** OpenAPI / Naming
- **Affected endpoint:** /chart and /v1/profile/{user_id}/chart
- **Evidence:** `bazi_engine/routers/chart.py:31` defines `ChartRequest`; `bazi_engine/routers/superglue.py:25` also defines `ChartRequest`. `PYTHONHASHSEED=0` generated `/chart -> #/components/schemas/ChartRequest` and Superglue prefixed; `PYTHONHASHSEED=1` generated `/chart -> #/components/schemas/bazi_engine__routers__chart__ChartRequest` and Superglue as `ChartRequest`. `python scripts/export_openapi.py --check` returned `FAIL: OpenAPI spec drifted.`
- **Expected behavior:** OpenAPI component names must be stable across processes so CI drift checks and code generation are deterministic.
- **Actual behavior:** The schema reference assignment changes with process/hash ordering; committed OpenAPI is not byte-identical to runtime export.
- **Root cause:** Name collision between Pydantic models in different routers; FastAPI/Pydantic disambiguation is order-sensitive.
- **Impact:** Flaky CI, unstable generated SDKs, false contract drift, and potentially breaking client imports.
- **Reproduction steps:** Run `for seed in 0 1; do PYTHONHASHSEED=$seed PYTHONPATH=$PWD python3 - <<'PY' ... app.openapi() ... PY; done`; then run `python scripts/export_openapi.py --check`.
- **Recommendation:** Rename models to `ChartComputeRequest` and `SuperglueChartTriggerRequest` or set explicit model titles; regenerate OpenAPI and add a deterministic OpenAPI snapshot test with fixed seeds.
- **Confidence:** High

### FUFIRE-API-002 — OpenAPI omits real auth/rate-limit/ephemeris error responses for protected operations

- **Severity:** High
- **Category:** OpenAPI / Error Handling
- **Affected endpoint:** GLOBAL protected endpoints
- **Evidence:** OpenAPI scan found 39 protected operations; 39 lacked documented `401`, 39 lacked `429`, and 39 lacked `503`. Runtime tests: T023/T024 returned 401; T006/T007/T008/T009/T012/T013/T014/T016/T018/T019 returned 503 due missing ephemeris.
- **Expected behavior:** Security-protected endpoints should document 401/403; rate-limited endpoints should document 429; ephemeris-dependent endpoints should document 503 ErrorEnvelope.
- **Actual behavior:** Most operations expose only 200/422 in OpenAPI despite runtime producing 401 and 503.
- **Root cause:** Custom OpenAPI patch only injects headers and special-cases `/validate`; it does not normalize common error responses across operations.
- **Impact:** Generated clients cannot model the real API failure modes; B2B integrators will under-handle authentication and service-dependency outages.
- **Reproduction steps:** Generate OpenAPI and inspect responses for any operation with `security=[{'APIKeyHeader': []}]`; execute T023/T024 and T006.
- **Recommendation:** Add reusable `ErrorEnvelope` responses for 401, 403 if used, 429, 500, 503. Apply in `_custom_openapi()` by operation traits.
- **Confidence:** High

### FUFIRE-API-003 — Local valid business requests are blocked without Swiss Ephemeris data, but quickstart does not make that dependency executable

- **Severity:** High
- **Category:** Runtime Behavior / Developer Experience
- **Affected endpoint:** /v1/calculate/*, /v1/transit/*, /v1/experience/*, /v1/impact/active
- **Evidence:** `bazi_engine/ephemeris.py:147-183` requires `sepl_18.se1`, `semo_18.se1`, `seas_18.se1`, `seplm06.se1` and raises `EphemerisUnavailableError`; runtime tests returned 503 with that message for core endpoints. README quickstart lines 16-23 only install and start uvicorn; Dockerfile lines 52-72 copies ephemeris files and sets `SE_EPHE_PATH`.
- **Expected behavior:** A local developer following README should either get a working API or an explicit documented data-bootstrap step.
- **Actual behavior:** The Docker build is self-contained, but direct local quickstart fails for ephemeris-dependent endpoints unless `SE_EPHE_PATH` already contains files or `EPHEMERIS_MODE=MOSEPH` is chosen.
- **Root cause:** Runtime data dependency is encoded in Dockerfile but not in the local quickstart path.
- **Impact:** Time-to-first-success fails for most core examples, increasing support load and hiding actual endpoint behavior behind 503s.
- **Reproduction steps:** Run T006/T007/T008 or `curl /v1/calculate/bazi` locally without `SE_EPHE_PATH`.
- **Recommendation:** Add explicit README/dev setup: download/provide SE1 files, set `SE_EPHE_PATH`, or run via Docker; optionally add a `/ready` dependency detail for ephemeris availability.
- **Confidence:** High

### FUFIRE-API-004 — Webhook documentation points to an unmounted path

- **Severity:** High
- **Category:** Documentation / Endpoint Design
- **Affected endpoint:** POST /api/webhooks/chart vs /internal/api/webhooks/chart
- **Evidence:** Docs list `POST /api/webhooks/chart` (`docs/API_REFERENCE.md:940`, `docs/api/01_developer_api_reference.md:187,341`); router prefix is `/api` at `bazi_engine/routers/webhooks.py:24,96`; app mounts it under `/internal` with `include_in_schema=False` at `bazi_engine/app.py:336`. Runtime T028 `/api/webhooks/chart` returned 404; T029 `/internal/api/webhooks/chart` reached the handler and returned 503 because secret was missing.
- **Expected behavior:** Published docs and runtime route should agree; hidden internal routes should be documented as internal with the actual path.
- **Actual behavior:** The documented public path is unreachable; the actual route is hidden and prefixed `/internal`.
- **Root cause:** App-level prefix was changed without updating docs and router docstring.
- **Impact:** External ElevenLabs/Superglue integration will call the wrong URL and fail.
- **Reproduction steps:** POST `/api/webhooks/chart` locally; compare with POST `/internal/api/webhooks/chart`.
- **Recommendation:** Decide one path. If public, mount without `/internal`; if internal, update all docs, router docstring, and integration configuration to `/internal/api/webhooks/chart`.
- **Confidence:** High

### FUFIRE-API-005 — Superglue endpoints return generic 500 when required configuration is absent

- **Severity:** Medium
- **Category:** Runtime Behavior / Error Handling
- **Affected endpoint:** /v1/profile*, /v1/daily*, /v1/profile/{user_id}/chart
- **Evidence:** `bazi_engine/services/superglue_client.py:40-45` raises `RuntimeError` when `SUPERGLUE_API_KEY` is missing. Router `bazi_engine/routers/superglue.py:65-80,91-107,123-129` catches only `httpx.HTTPStatusError` and `httpx.TimeoutException`. Runtime T020/T022 returned 500 `internal_error`.
- **Expected behavior:** Missing mandatory upstream configuration should be a structured 503 `service_unavailable` or startup/readiness failure.
- **Actual behavior:** Missing `SUPERGLUE_API_KEY` is masked as generic 500; integration teams get no actionable reason from the API response.
- **Root cause:** Configuration error is raised below router catch boundary and caught only by global unhandled exception handler.
- **Impact:** Operational diagnosis is slower; clients may treat configuration outage as transient internal bug.
- **Reproduction steps:** Unset `SUPERGLUE_API_KEY`, set valid `FUFIRE_API_KEYS`, call GET `/v1/profile/testuser`.
- **Recommendation:** Catch `RuntimeError` or define `SuperglueConfigurationError`; map to 503 ErrorEnvelope with safe message; surface status in `/ready`.
- **Confidence:** High

### FUFIRE-API-006 — Standard response headers are not guaranteed on unhandled 500 responses

- **Severity:** Medium
- **Category:** Response Schema / Runtime Behavior
- **Affected endpoint:** Superglue 500 paths
- **Evidence:** Runtime T020/T022 response headers only contained `content-type`; no `X-Request-ID`, `X-API-Version`, or `X-Response-Time-ms`, despite body carrying `request_id`. Middleware intends to add these headers at `bazi_engine/middleware.py:23-49` and documentation says every response has them in app description lines 72-78.
- **Expected behavior:** Every response should contain documented correlation and version headers, including 500s.
- **Actual behavior:** Unhandled exceptions bypass the response-header injection path in observed tests.
- **Root cause:** BaseHTTPMiddleware calls `call_next`; exception responses produced by global handler are not post-processed in this path.
- **Impact:** Tracing and client correlation are weakest exactly during incidents.
- **Reproduction steps:** Run T020 or T022 and inspect headers.
- **Recommendation:** Use pure ASGI middleware or wrap `call_next` with exception handling that always attaches headers; add negative tests for 500 headers.
- **Confidence:** High

### FUFIRE-API-007 — Rate-limit documentation/OpenAPI overstates `X-RateLimit-Remaining` availability

- **Severity:** Medium
- **Category:** Documentation / OpenAPI
- **Affected endpoint:** GLOBAL /v1 protected endpoints
- **Evidence:** App description lines 63-70 says rate-limit responses include `X-RateLimit-Remaining`; `_custom_openapi()` injects it for v1 responses at `bazi_engine/app.py:395-422`; middleware explicitly says it does not set a fallback at `bazi_engine/middleware.py:33-40`. Runtime protected responses showed `X-RateLimit-Limit: 100` but no `X-RateLimit-Remaining`.
- **Expected behavior:** Headers documented in OpenAPI should be produced reliably or marked conditional.
- **Actual behavior:** `X-RateLimit-Remaining` is advertised as standard but absent in tested responses.
- **Root cause:** The implementation moved away from phantom remaining quota but OpenAPI/docs still promise it.
- **Impact:** Clients may rely on a header that is not present, causing quota UX bugs.
- **Reproduction steps:** Call T010/T011 with valid key and inspect headers.
- **Recommendation:** Either implement real remaining counters on all protected routes or remove/condition the header in docs and OpenAPI.
- **Confidence:** High

### FUFIRE-API-008 — Legacy auth behavior contradicts the API reference

- **Severity:** Medium
- **Category:** Documentation / Auth
- **Affected endpoint:** Legacy business endpoints
- **Evidence:** `docs/API_REFERENCE.md:49-55` says no-prefix legacy routes require no auth. App includes legacy business routers with `_protected` dependency at `bazi_engine/app.py:307-318`. Runtime POST `/calculate/bazi` without key returned 401 when `FUFIRE_API_KEYS` was configured.
- **Expected behavior:** Docs should describe actual auth behavior for legacy routes under production auth configuration.
- **Actual behavior:** Legacy routes are protected in code, not public as documented.
- **Root cause:** Docs likely preserved an earlier backward-compatibility assumption after auth middleware was applied to legacy routers.
- **Impact:** Consumers migrating from legacy routes may get unexpected 401s.
- **Reproduction steps:** Set `FUFIRE_API_KEYS`, call POST `/calculate/bazi` without `X-API-Key`.
- **Recommendation:** Update docs to say legacy business routes also require API keys when auth is configured, or change router inclusion if public legacy compatibility is intentional.
- **Confidence:** High

### FUFIRE-API-009 — Auth error codes in docs do not match runtime error envelope

- **Severity:** Low
- **Category:** Documentation / Error Handling
- **Affected endpoint:** Protected endpoints
- **Evidence:** Docs list `invalid_api_key` for 401 and `tier_insufficient` for 403 (`docs/API_REFERENCE.md:86-91`). Runtime T023/T024 returned `error=unauthorized`, `message=Missing or invalid X-API-Key header`; `bazi_engine/auth.py:173-184` raises 401 with `error: unauthorized` and no 403 tier logic in the dependency.
- **Expected behavior:** Documented error codes should be exactly the runtime contract.
- **Actual behavior:** Runtime and documentation differ for common auth failures.
- **Root cause:** Auth implementation was simplified or renamed without doc update.
- **Impact:** Client error handling based on docs will not match actual responses.
- **Reproduction steps:** Call T023/T024 and compare to docs.
- **Recommendation:** Align docs to `unauthorized`, or change runtime to `invalid_api_key`; document 403 only if tier checks exist.
- **Confidence:** High

### FUFIRE-API-010 — CONTRACT.md endpoint count is obsolete relative to runtime API surface

- **Severity:** Medium
- **Category:** Documentation / Architecture
- **Affected endpoint:** GLOBAL
- **Evidence:** `CONTRACT.md:39-57` says all 13 endpoints are frozen. Runtime inventory found 51 schema-visible operations plus one hidden internal webhook. README lists only a subset of v1 routes at lines 41-53.
- **Expected behavior:** Contract documentation should enumerate the full public and hidden API surface or clearly scope itself.
- **Actual behavior:** Contract doc undercounts endpoints and omits Superglue/Impact/v1 duplicates.
- **Root cause:** API evolved without contract document refresh.
- **Impact:** Source-of-truth confusion: auditors and client generators cannot tell whether OpenAPI or CONTRACT.md is authoritative despite `CONTRACT.md:3-7` claiming OpenAPI is source of truth.
- **Reproduction steps:** Run route inventory via `from bazi_engine.app import app; print(app.routes)`.
- **Recommendation:** Replace manual endpoint table with generated table from OpenAPI; separate legacy, v1, internal, and proxy surfaces.
- **Confidence:** High

### FUFIRE-API-011 — Global OpenAPI tag list omits tags used by operations

- **Severity:** Low
- **Category:** OpenAPI / Documentation
- **Affected endpoint:** Superglue and Impact endpoints
- **Evidence:** OpenAPI operation scan found 12 operations tagged `Superglue` or `Impact`; global tag list in `bazi_engine/app.py:361-372` lacks both names.
- **Expected behavior:** Every used operation tag should be represented in the global `tags` array with a description.
- **Actual behavior:** Redoc/Swagger grouping will have undocumented tag groups for Superglue/Impact.
- **Root cause:** New routers were added after the hand-authored tag list.
- **Impact:** Lower-quality generated documentation and incomplete API taxonomy.
- **Reproduction steps:** Inspect `app.openapi()['tags']` and operation tags.
- **Recommendation:** Add `Superglue` and `Impact` entries or generate tag metadata from router registry.
- **Confidence:** High

### FUFIRE-API-012 — Full regression suite is not currently green under the audited sandbox

- **Severity:** Medium
- **Category:** Testing
- **Affected endpoint:** GLOBAL
- **Evidence:** Targeted API tests passed: `173 passed, 2 skipped`. Initial full `pytest -q` errored on missing dev dependency `respx`; after installing `respx`, `pytest --maxfail=20` produced `1506 passed, 49 skipped, 20 failed`, stopping in `tests/test_snapshot_stability.py` due added `derivation_trace` fields, `tzdb_version_id unknown != 2026.1`, and one `solar_terms_count 23 != 24` mismatch.
- **Expected behavior:** Repository test command in README (`pytest -q`) should complete cleanly after installing declared dev dependencies, or failures should be documented/segmented.
- **Actual behavior:** Full suite is not green in the sandbox; snapshot baselines appear stale relative to code.
- **Root cause:** Snapshot contract changed without regenerating baselines or adjusting tolerant comparator; dev dependencies were not preinstalled in the base environment.
- **Impact:** Release confidence is lower for deterministic/snapshot claims.
- **Reproduction steps:** Run `PYTHONPATH=$PWD pytest -q --tb=short --disable-warnings --maxfail=20` after installing dev deps.
- **Recommendation:** Regenerate/approve snapshots or revert response changes; pin and document dev environment; split slow/external tests with explicit markers.
- **Confidence:** High

### FUFIRE-API-013 — /chart is described as internal but remains schema-visible and protected as a legacy endpoint

- **Severity:** Low
- **Category:** Endpoint Design / Documentation
- **Affected endpoint:** POST /chart
- **Evidence:** `docs/API_REFERENCE.md:932-934` says `/chart` is internal use. App includes `chart.router` in public legacy route set with `_protected` at `bazi_engine/app.py:314`; comment says chart is not exposed under `/v1` at `bazi_engine/app.py:320-321`. OpenAPI includes `/chart` as a schema-visible operation.
- **Expected behavior:** Internal endpoints should either be hidden/mounted under `/internal` or documented as supported public legacy endpoints.
- **Actual behavior:** `/chart` is externally visible in OpenAPI but described as internal and has no v1 mirror.
- **Root cause:** Internal/legacy boundary is not consistently encoded in routing and documentation.
- **Impact:** API consumers may adopt an endpoint that product owners intend to keep internal.
- **Reproduction steps:** Inspect OpenAPI paths and docs around `/chart`.
- **Recommendation:** Move `/chart` under `/internal`, hide it from schema, or explicitly mark it deprecated/internal with lifecycle policy.
- **Confidence:** High

## 8. Root Cause Synthesis

| Root Cause Cluster | Findings | Explanation |
|---|---|---|
| Missing generated source-of-truth discipline | FUFIRE-API-001, 004, 010, 011, 013 | Docs and committed OpenAPI are not fully generated from runtime truth or verified across deterministic seeds. |
| Incomplete error contract | FUFIRE-API-002, 005, 006, 007, 009 | Error envelopes exist, but OpenAPI/docs/headers do not consistently represent runtime errors. |
| Runtime dependency hidden from local path | FUFIRE-API-003 | Docker contains ephemeris setup; README local path does not. |
| Router evolution without doc taxonomy update | FUFIRE-API-010, 011 | Superglue and Impact were added but global tags/catalog/contract did not catch up. |
| Snapshot/test baseline drift | FUFIRE-API-012 | Tests encode older output shape/tzdb expectations while current code emits additional derivation trace. |

## 9. Gap Analysis

| Area | Current State | Expected State | Gap | Risk | Recommended Fix | Priority |
|---|---|---|---|---|---|---|
| OpenAPI determinism | Export drifts; `ChartRequest` collision | Stable byte-identical export | Nondeterministic component naming | SDK/CI breakage | Rename models, seed-test export | P0 |
| Error responses | 401/429/503 absent from most operations | Common ErrorEnvelope responses documented | Incomplete client contract | Under-handled failures | Patch OpenAPI common responses | P0 |
| Webhook docs | Docs point to `/api/webhooks/chart` | Runtime path is documented/reachable | Wrong integration URL | Webhook integration fails | Align mount/docs | P0 |
| Local runtime | Core endpoints 503 without SE1 | Quickstart works or explains dependency | Hidden data dependency | Poor DX / false bug reports | README + setup command + readiness | P1 |
| Superglue config | Missing API key returns 500 | Missing upstream config returns 503 | Non-actionable errors | Ops debugging delay | Typed config error | P1 |
| Headers | 500 missing standard headers | Headers on every response | Incident correlation gap | Poor observability | ASGI middleware test/fix | P1 |
| Rate limit headers | Remaining advertised but absent | Either implemented or conditional | Header contract drift | Client quota bugs | Update docs/OpenAPI or implement | P1 |
| Legacy auth docs | Docs say legacy public | Runtime protects legacy business routes | Migration surprise | Unexpected 401s | Update docs or route policy | P1 |
| Test suite | Targeted green; full suite red/blocked | `pytest -q` green or segmented | Release signal weak | False confidence | Fix snapshots/dev deps | P1 |
| Tag taxonomy | Superglue/Impact missing global tags | All used tags documented | Degraded docs | Lower DX | Add tags | P2 |
| `/chart` lifecycle | Internal but schema-visible | Clear public/internal/deprecated status | Boundary ambiguity | Accidental adoption | Hide or document lifecycle | P2 |

## 10. Remediation Backlog

| Priority | Task | Affected Files | Acceptance Criteria | Estimated Complexity |
|---|---|---|---|---|
| P0 | Rename colliding `ChartRequest` models | `bazi_engine/routers/chart.py`, `bazi_engine/routers/superglue.py`, `spec/openapi/openapi.json` | `scripts/export_openapi.py --check` passes for `PYTHONHASHSEED=0..10`; no component ambiguity | Medium |
| P0 | Normalize common ErrorEnvelope responses | `bazi_engine/app.py`, OpenAPI tests | All protected operations document 401/429/500/503 as applicable | Medium |
| P0 | Fix webhook path truth | `bazi_engine/app.py`, `bazi_engine/routers/webhooks.py`, docs, integration config | Documented path returns handler response; incorrect path removed/deprecated | Low/Medium |
| P1 | Document ephemeris setup | `README.md`, `docs/api/*`, `docs/runbooks/*` | Local quickstart includes SE1 setup or Docker-first path; T006 can be made 200 in documented local env | Low |
| P1 | Superglue config error mapping | `bazi_engine/services/superglue_client.py`, `bazi_engine/routers/superglue.py`, tests | Missing `SUPERGLUE_API_KEY` returns 503 with ErrorEnvelope and standard headers | Low |
| P1 | Guarantee headers on 500 | `bazi_engine/middleware.py`, tests | T020/T022 include X-Request-ID, X-API-Version, X-Response-Time-ms | Medium |
| P1 | Fix rate-limit remaining contract | `bazi_engine/middleware.py`, `bazi_engine/app.py`, docs | Either header is present with real counter or removed from standard docs | Medium |
| P1 | Reconcile legacy auth docs | `docs/API_REFERENCE.md`, `docs/api/01_developer_api_reference.md` | Docs match runtime for legacy routes under configured auth | Low |
| P1 | Restore full test-suite signal | `tests/snapshots/moseph/*`, `pyproject.toml`, CI config | Full expected test command is green or marked with explicit external/slow markers | Medium/High |
| P2 | Add missing global tags | `bazi_engine/app.py` | OpenAPI operation tag scan returns zero missing tags | Low |
| P2 | Clarify `/chart` lifecycle | `bazi_engine/app.py`, `docs/*` | `/chart` is hidden/internal or documented as public/deprecated | Low |

## 11. Suggested Test Additions

### Unit tests

- Assert no duplicate Pydantic model class names among schema-visible routers unless explicit `title`/alias is set.
- Assert global OpenAPI tags include every operation tag.
- Assert auth error body exactly matches documented code.
- Assert `call_hook()` missing `SUPERGLUE_API_KEY` maps to 503 at router layer.

### Integration tests

- For each protected route: missing key → 401 ErrorEnvelope with standard headers.
- For representative ephemeris-dependent endpoints: missing SE1 → documented 503 ErrorEnvelope.
- Webhook path tests: documented path must be reachable or docs must not publish it.
- Legacy route auth tests under `FUFIRE_API_KEYS` configured.

### Contract tests

- `PYTHONHASHSEED=0..10 python scripts/export_openapi.py --check`.
- Verify all protected operations include `401`, `429`, and applicable `503` responses.
- Verify all error responses use `#/components/schemas/ErrorEnvelope`.
- Verify no OpenAPI component name contains module path unless intentionally whitelisted.

### Negative tests

- Wrong content type / malformed JSON for all POST endpoints.
- Missing and invalid auth for legacy and v1 business routes.
- Superglue missing upstream config.
- Missing ElevenLabs secret for actual webhook path.
- Unknown route standard ErrorEnvelope and headers.

## 12. Final Quality Gate

| Dimension | Score | Rationale |
|---|---:|---|
| Dokumentationsreife | 62/100 | Broad docs exist, but webhook path, legacy auth, Superglue/Impact coverage and contract count are inconsistent. |
| OpenAPI-Konformität | 58/100 | OpenAPI exists and is rich, but drift/nondeterministic component naming and missing error responses are serious. |
| Endpoint-Konsistenz | 67/100 | Request/response models are typed; routing/versioning/internal boundaries are inconsistent. |
| Testabdeckung | 74/100 | Large test base and targeted API tests pass; full suite currently has snapshot drift and environment dependency issues. |
| Produktionsreife | 66/100 | Good architecture foundation; release-critical contract and documentation drift must be fixed before enterprise-grade API confidence. |

## 13. Limitations

- **No production calls executed.** This audit intentionally did not test `https://bafe-2u0e2a.fly.dev` or Superglue/ElevenLabs external systems.
- **SE1 ephemeris files were not present in the sandbox.** Ephemeris-dependent 503 results prove local/developer-environment behavior, not necessarily Docker/production behavior.
- **No load/rate-limit saturation test executed.** 429 behavior was inferred from code and OpenAPI absence, not exercised to threshold.
- **No security penetration test.** Auth behavior was tested only for missing/invalid API key and webhook missing secret.
- **No exhaustive schema validation of every response body against OpenAPI.** Representative runtime tests were run; deeper contract testing is recommended.
- **Nested repository copy not fully audited separately.** The outer root was treated as active project root.

## DECISION-REVIEW

- **Zentrale Entscheidung:** Der Audit priorisiert Contract drift, documented/runtime contradictions and executable evidence over broad functional astrology correctness.
- **Warum:** Ohne stabile OpenAPI, correct routes and documented error contracts, API consumers cannot safely integrate even if domain calculations are correct.
- **Anpassung fürs nächste Mal:** First run OpenAPI determinism under multiple `PYTHONHASHSEED` values before endpoint-by-endpoint analysis; this catches schema-generation fragility early.

## Meta-Status

- **Kategorie:** (2) Faktisch + ableitbar
- **Bias-Notizen:** Mögliches Audit-Bias zugunsten von Contract-/DX-Problemen, weil lokale SE1-Dateien fehlten und dadurch viele domain-positive tests nicht ausführbar waren. Gegenmaßnahme: 503-Befunde ausdrücklich als lokale/developer-experience oder dependency-gating Findings markiert, nicht als gesicherte Produktionsausfälle.
