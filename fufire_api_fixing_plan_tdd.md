# FuFire API Fixing Plan mit TDD

Plan path: `docs/plans/2026-05-23-fufire-api-contract-drift-and-error-contract-fixes.md`  
Status: `ready-for-execution-with-open-questions`

Reference-Doc: [`fufire_api_audit_report.md`](sandbox:/mnt/data/fufire_api_audit_report.md)

## SMART-CONTEXT

**Current situation:**  
Der Auditbericht weist 13 Findings in der FuFire/FuFirE API aus. Die gravierendsten Risiken liegen in OpenAPI-Drift, unvollständigen Fehlerkontrakten, einem falschen Webhook-Dokumentationspfad, lokaler Ephemeris-DX, Superglue-Fehlermapping und einer nicht grünen Full-Test-Suite.

**Key stakeholders:**  
Backend Devs, QA/Release, API-Konsumenten/B2B-Integratoren, technische Dokumentation, Ops/SRE, Security.

**Important constraints:**
- Keine Produktivaufrufe und keine echten Fremdsystem-Requests.
- Keine Secrets in Tests oder Plan.
- Keine direkte Änderung an `main`/`master`; Arbeit in Feature-Branch.
- OpenAPI und Runtime müssen nach Fix synchron sein.
- Tests müssen zuerst geschrieben oder angepasst werden, bevor Implementierung erfolgt.

**Relevant history:**  
Der Auditbericht markiert `spec/openapi/openapi.json`/Runtime-OpenAPI als zentrale Contract-Fläche, aber zeigt Drift und Dokumentationswidersprüche. Lokale Runtime-Tests wurden ohne SE1-Dateien ausgeführt; Ephemeris-503 ist daher als lokales Setup-/DX-Risiko zu behandeln, nicht automatisch als Produktionsausfall.

**Goals:**
- Stabilen, deterministischen OpenAPI-Vertrag herstellen.
- Reale Fehlerfälle in OpenAPI, Runtime und Docs vereinheitlichen.
- Webhook-, Legacy-Auth-, Header-, Rate-Limit- und `/chart`-Dokumentation an Runtime-Entscheidungen angleichen.
- Full-Test-Suite wieder als Release-Signal nutzbar machen.

**Arbeitsdefinition des Problems:**  
Die API besitzt eine solide technische Basis, aber mehrere Source-of-Truth-Drifts zwischen Code, OpenAPI, Dokumentation und Runtime-Verhalten. Der Fix muss zuerst Vertragssicherheit und reproduzierbare Tests herstellen, dann DX-/Dokumentationslücken schließen, ohne produktive Integrationen unkontrolliert zu brechen.

## REASONING-TECHNIQUE

**Gewählt:** Plan-and-Solve  
**Begründung:** Die Audit-Findings sind konkret, priorisierbar und lassen sich in TDD-Tasks sequenzieren. Es gibt einige Produktentscheidungen, aber die technische Hauptlinie ist klar: erst Contract-Determinismus, dann Error Contract, dann Docs/DX, dann Testbaseline.

<!-- GOAL_START -->
Goal: FuFire API Contract- und Runtime-Drift beheben

Ziel. Behebe die im Auditbericht `fufire_api_audit_report.md` dokumentierten API-Issues so, dass OpenAPI, Runtime, Tests und Dokumentation wieder konsistent sind. Priorität haben P0/P1-Findings: deterministischer OpenAPI-Export, vollständiger ErrorEnvelope-Contract, korrekter Webhook-Pfad, lokale Ephemeris-DX, Superglue-503-Mapping, Standard-Headers auf Fehlern und grüne Testsignale.

Scope. Branch `fix/api-contract-drift-and-error-contract`; betroffene Bereiche: `bazi_engine/routers/*`, `bazi_engine/app.py`, `bazi_engine/middleware.py`, `bazi_engine/services/superglue_client.py`, `spec/openapi/openapi.json`, `docs/*`, `README.md`, `tests/*`, CI/Test-Konfiguration falls vorhanden.

Bedingungen (hart).
- TDD-first: pro Fix zuerst ein fehlender/fehlschlagender Test oder Contract-Check.
- Keine externen Produktivsysteme, keine echten Secrets, keine destruktiven Requests.
- Keine erfundenen Pfade oder Testergebnisse; unbekannte CI-Dateien erst per Discovery prüfen.
- Backward Compatibility bewusst behandeln: Route-Entfernung nur mit expliziter Deprecation-/Owner-Entscheidung.

Akzeptanzkriterien.
- `scripts/export_openapi.py --check` besteht stabil für mehrere `PYTHONHASHSEED`-Werte.
- Geschützte Operationen dokumentieren relevante 401/429/500/503 ErrorEnvelope-Responses.
- Dokumentierter Webhook-Pfad und Runtime-Pfad stimmen überein.
- Missing `SUPERGLUE_API_KEY` erzeugt strukturierte 503 statt generischer 500.
- Standard-Headers sind auch auf Fehlerantworten vorhanden oder Docs/OpenAPI schränken die Garantie korrekt ein.
- Full-Test-Befehl ist grün oder sauber segmentiert und dokumentiert.

Explizit out-of-scope.
- Keine fachliche Neuberechnung oder Validierung astrologischer Algorithmen.
- Keine Produktiv- oder externen Superglue/ElevenLabs-Calls.
- Keine große Router-/Framework-Migration.
- Keine Einführung neuer API-Versionen außer klar markierter Deprecation-Dokumentation.

Done-Definition. Pull Request mit Tests, Codefixes, regenerierter OpenAPI, aktualisierter Dokumentation und Validierungslog; alle P0/P1-Findings aus dem Audit sind entweder behoben oder als bewusst akzeptiertes Risiko mit Owner-Entscheidung dokumentiert.

Reference-Doc: `fufire_api_audit_report.md`
<!-- GOAL_END -->

## Evidence and source boundary

**Primäre Quelle:** `fufire_api_audit_report.md`, insbesondere:
- Findings `FUFIRE-API-001` bis `FUFIRE-API-013`.
- Endpoint Test Matrix `T001` bis `T030`.
- Contradiction Register `C-001` bis `C-010`.
- Remediation Backlog und Suggested Test Additions.

**Bekannte Fakten aus dem Auditbericht:**
- Stack: Python/FastAPI/Pydantic, OpenAPI 3.1, `scripts/export_openapi.py --check` vorhanden.
- Relevante Pfade: `bazi_engine/app.py`, `bazi_engine/routers/chart.py`, `bazi_engine/routers/superglue.py`, `bazi_engine/routers/webhooks.py`, `bazi_engine/middleware.py`, `bazi_engine/services/superglue_client.py`, `spec/openapi/openapi.json`, `README.md`, `docs/API_REFERENCE.md`, `docs/api/01_developer_api_reference.md`, `CONTRACT.md`, `tests/*`.
- Bekannte Audit-Testbefehle: `PYTHONPATH=$PWD python3 scripts/export_openapi.py --check`, `PYTHONPATH=$PWD pytest -q`, zielgerichtete Pytest-Runs.

**ASSUMPTION:** Die aktuelle Arbeitskopie entspricht dem im Audit geprüften ZIP-Root und nicht einer abweichenden Nested-Copy.  
**MISSING:** Exakte CI-Dateipfade sind nicht aus dem Bericht gesichert. Discovery vor CI-Änderungen erforderlich.  
**OPEN QUESTION:** Soll `/chart` versteckt/deprecated werden oder bewusst als Legacy public contract bestehen bleiben?  
**OPEN QUESTION:** Soll der Webhook öffentlich `/api/webhooks/chart` oder intern `/internal/api/webhooks/chart` sein? Default im Plan: Runtime bleibt intern, Docs werden auf `/internal/api/webhooks/chart` korrigiert, sofern kein Product-Owner widerspricht.  
**OPEN QUESTION:** Soll `X-RateLimit-Remaining` implementiert oder aus dem Standard-Header-Contract entfernt werden? Default im Plan: Dokumentation/OpenAPI auf „conditional when available“ korrigieren, keine Phantom-Zähler einführen.

## Requirements

| ID | Requirement | Source | Verification |
|---|---|---|---|
| REQ-F-001 | OpenAPI-Komponenten müssen deterministisch und kollisionsfrei erzeugt werden. | FUFIRE-API-001 | Multi-seed OpenAPI-Test + `export_openapi.py --check` |
| REQ-F-002 | Geschützte Operationen müssen dokumentierte 401/429/500/503 ErrorEnvelope-Responses haben, soweit Runtime sie erzeugt. | FUFIRE-API-002 | OpenAPI Contract Test |
| REQ-F-003 | Der dokumentierte Webhook-Pfad muss dem erreichbaren Runtime-Pfad entsprechen. | FUFIRE-API-004 | TestClient Route-Test + Docs-Grep |
| REQ-F-004 | Fehlende Superglue-Konfiguration muss 503 `service_unavailable` statt 500 liefern. | FUFIRE-API-005 | Negative Integration Tests |
| REQ-F-005 | Standard-Headers müssen auch bei 500/503/404/422/401 vorhanden sein oder die Dokumentation muss präzise einschränken. | FUFIRE-API-006 | Header Tests über Fehlerfälle |
| REQ-F-006 | Rate-Limit-Header-Contract darf keine nicht vorhandenen Header als garantiert ausweisen. | FUFIRE-API-007 | OpenAPI/docs check + Runtime header test |
| REQ-F-007 | Legacy-Auth-Dokumentation muss Runtime-Verhalten unter `FUFIRE_API_KEYS` korrekt beschreiben. | FUFIRE-API-008/009 | Docs diff + auth negative tests |
| REQ-F-008 | CONTRACT.md und API-Dokumentation müssen API-Surface-Scope korrekt beschreiben. | FUFIRE-API-010/011/013 | Generated route inventory check oder Docs review |
| REQ-NF-001 | Full-Test-Signal muss reproduzierbar sein: grün oder sauber segmentiert. | FUFIRE-API-012 | `pytest -q` oder definierte Testprofile |
| REQ-NF-002 | Lokaler Quickstart muss Ephemeris-Abhängigkeit ausführbar erklären. | FUFIRE-API-003 | README/runbook review + optional ready-state test |
| REQ-S-001 | Keine Tests gegen externe Produktivsysteme und keine Secrets im Repo. | Audit constraint | Review checklist + env-only dummy values |

## Architecture and file boundaries

**Smallest robust architecture decision:** Keine neue Schicht und kein Frameworkwechsel. Fixes bleiben in bestehenden Routern, OpenAPI-Customizer, Middleware, Service-Fehlermapping, Tests und Docs.

**File-boundary strategy:**
- Router/schema fixes: `bazi_engine/routers/chart.py`, `bazi_engine/routers/superglue.py`, `bazi_engine/routers/webhooks.py`.
- Contract generation: `bazi_engine/app.py`, `scripts/export_openapi.py` nur falls nötig, `spec/openapi/openapi.json` regenerieren.
- Error handling/middleware: `bazi_engine/middleware.py`, ggf. zentrale exception handler in `bazi_engine/app.py`.
- Superglue config mapping: `bazi_engine/services/superglue_client.py`, `bazi_engine/routers/superglue.py`.
- Documentation: `README.md`, `docs/API_REFERENCE.md`, `docs/api/01_developer_api_reference.md`, `CONTRACT.md`, ggf. `docs/ERROR_CODES.md`.
- Tests: bevorzugt neue fokussierte Contract-/Runtime-Testdateien unter `tests/`; existierende Testdateien nur ändern, wenn dort bereits passende Contract-Checks liegen.

## Implementation phases

| Phase | Priority | Outcome | Findings covered |
|---|---:|---|---|
| 0 | P0 | Discovery, baseline, failing tests reproduzieren | all |
| 1 | P0 | OpenAPI deterministisch machen | 001 |
| 2 | P0 | Common ErrorEnvelope responses in OpenAPI | 002, 009 |
| 3 | P0 | Webhook path truth fix | 004 |
| 4 | P1 | Runtime error handling and headers | 005, 006 |
| 5 | P1 | Header/docs/auth/ephemeris docs align | 003, 007, 008 |
| 6 | P1 | Test-suite baseline restore | 012 |
| 7 | P2 | Tags, contract count, `/chart` lifecycle | 010, 011, 013 |

## Tasks

### TASK-001: Baseline reproduzieren und Fix-Branch absichern

Objective: Stelle sicher, dass die Audit-Findings in der lokalen Arbeitskopie reproduzierbar sind, bevor Code geändert wird.  
Requirement links: REQ-S-001, REQ-NF-001  
Files/modules:
- Inspect: `pyproject.toml`, `tests/`, `scripts/export_openapi.py`, `spec/openapi/openapi.json`
- Create: `audit-fix-log.md` oder PR-Beschreibung mit Baseline-Auszügen

Steps:
1. Feature-Branch erstellen: `fix/api-contract-drift-and-error-contract`.
2. Dependencies gemäß Projektstandard installieren; keine Secrets setzen außer Dummy-Testwerte.
3. Baseline ausführen:
   - `PYTHONPATH=$PWD python3 scripts/export_openapi.py --check`
   - `PYTHONPATH=$PWD pytest -q --tb=short --disable-warnings --maxfail=20`
4. Ergebnisse in Fix-Log/PR notieren.
5. Keine Codeänderung in diesem Task außer optionalem Fix-Log.

Acceptance criteria:
- Baseline-Fehler sind reproduziert oder Abweichungen sind dokumentiert.
- Keine produktiven URLs/Secrets wurden genutzt.

Validation:
- Command: `git diff --stat`
- Expected result: höchstens Fix-Log/Notizdatei geändert.

Rollback note: Fix-Log entfernen oder Branch zurücksetzen.

---

### TASK-002: OpenAPI-Determinismus-Test für `ChartRequest`-Kollision schreiben

Objective: Füge einen failing Contract-Test hinzu, der die nondeterministische OpenAPI-Komponentenzuordnung erkennt.  
Requirement links: REQ-F-001  
Files/modules:
- Create: `tests/test_openapi_determinism.py`
- Inspect: `bazi_engine/routers/chart.py`, `bazi_engine/routers/superglue.py`, `scripts/export_openapi.py`

Steps:
1. Schreibe einen Test, der `app.openapi()` in Subprozessen mit `PYTHONHASHSEED=0..10` exportiert.
2. Prüfe, dass relevante `$ref`-Targets für `/chart` und `/v1/profile/{user_id}/chart` über Seeds stabil bleiben.
3. Prüfe zusätzlich, dass keine zwei schema-visible Pydantic-Modelle denselben unqualifizierten Namen `ChartRequest` verwenden, außer sie haben explizite stabile Titel/Aliases.
4. Test ausführen und erwartetes Fail dokumentieren.

Acceptance criteria:
- Test schlägt vor Implementierung reproduzierbar fehl.
- Test nennt die kollidierenden Modelle klar.

Validation:
- Command: `PYTHONPATH=$PWD pytest -q tests/test_openapi_determinism.py`
- Expected result before fix: FAIL wegen `ChartRequest`-Kollision oder seed-abhängigen `$ref`s.

Rollback note: Neue Testdatei löschen.

---

### TASK-003: Kollidierende `ChartRequest`-Modelle umbenennen oder explizit betiteln

Objective: Entferne die OpenAPI-Komponentennamenskollision ohne Änderung der JSON-Request-Body-Form.  
Requirement links: REQ-F-001  
Files/modules:
- Modify: `bazi_engine/routers/chart.py`
- Modify: `bazi_engine/routers/superglue.py`
- Modify: `spec/openapi/openapi.json` nach Regeneration
- Test: `tests/test_openapi_determinism.py`

Steps:
1. Wähle die kleinste robuste Option: Klassen umbenennen, z. B. `ChartComputeRequest` und `SuperglueChartTriggerRequest`.
2. Halte Feldnamen, Validierungsregeln und Request-JSON unverändert.
3. Aktualisiere Typreferenzen in den betroffenen Handlern.
4. Regeneriere OpenAPI.
5. Führe Multi-seed-Test und Export-Check aus.

Acceptance criteria:
- Keine schema-visible Kollisionsklasse `ChartRequest` mehr.
- `scripts/export_openapi.py --check` ist stabil.
- Request/Response JSON bleibt rückwärtskompatibel.

Validation:
- Command: `for seed in 0 1 2 3 4 5 6 7 8 9 10; do PYTHONHASHSEED=$seed PYTHONPATH=$PWD python3 scripts/export_openapi.py --check; done`
- Expected result: alle Läufe PASS.

Rollback note: Klassenumbenennung und OpenAPI-Regeneration zurücknehmen.

---

### TASK-004: Common ErrorEnvelope-Contract-Test schreiben

Objective: Erzwinge per Test, dass geschützte Operationen relevante Fehlerstatuscodes dokumentieren.  
Requirement links: REQ-F-002, REQ-F-007  
Files/modules:
- Create or modify: `tests/test_openapi_error_contract.py` oder vorhandene `tests/test_openapi_contract.py`
- Inspect: `bazi_engine/app.py`, `bazi_engine/auth.py`, `bazi_engine/limiter.py`

Steps:
1. Lade `app.openapi()`.
2. Identifiziere Operationen mit `security`/`APIKeyHeader`.
3. Assert: jede geschützte Operation enthält `401` und `429`.
4. Assert: Operationen, die bekannte Service-/Ephemeris-Dependencies haben, enthalten `503`.
5. Assert: `401`, `429`, `500`, `503` referenzieren `ErrorEnvelope` oder ein kompatibles Envelope-Schema.
6. Test vor Implementierung ausführen und erwartetes Fail dokumentieren.

Acceptance criteria:
- Test deckt mindestens die im Audit genannten 39 geschützten Operationen ab.
- Test schlägt vor Fix wegen fehlender Responses fehl.

Validation:
- Command: `PYTHONPATH=$PWD pytest -q tests/test_openapi_error_contract.py`
- Expected result before fix: FAIL mit Liste fehlender Statuscodes.

Rollback note: Neue Testdatei löschen oder Änderung an bestehender Testdatei zurücknehmen.

---

### TASK-005: Common ErrorEnvelope-Responses in `_custom_openapi()` normalisieren

Objective: Ergänze OpenAPI-Responses so, dass Runtime-Fehlerfälle sichtbar und SDK-fähig werden.  
Requirement links: REQ-F-002, REQ-F-007  
Files/modules:
- Modify: `bazi_engine/app.py`
- Modify: `spec/openapi/openapi.json`
- Test: `tests/test_openapi_error_contract.py`

Steps:
1. In `bazi_engine/app.py` die bestehende OpenAPI-Patch-Logik inspizieren.
2. Reusable responses für `401 Unauthorized`, `429 Too Many Requests`, `500 Internal Server Error`, `503 Service Unavailable` mit `ErrorEnvelope` definieren oder referenzieren.
3. Auf geschützte Operationen anwenden; `503` bei bekannten dependency-basierten Endpunkten oder konservativ bei allen protected service operations dokumentieren.
4. Beispiele knapp halten und keine geheimen Details enthalten.
5. OpenAPI regenerieren.
6. Contract-Tests ausführen.

Acceptance criteria:
- Geschützte Operationen enthalten 401/429.
- Ephemeris-/Superglue-/Webhook-Service-Dependency-Endpunkte enthalten 503.
- Error schema ist konsistent.

Validation:
- Command: `PYTHONPATH=$PWD pytest -q tests/test_openapi_error_contract.py tests/test_openapi_determinism.py`
- Expected result: PASS.

Rollback note: OpenAPI-Patch und generierte Spec zurücknehmen.

---

### TASK-006: Webhook-Pfad-Entscheidung als Test fixieren

Objective: Mache den gewünschten Webhook-Pfad explizit und testbar.  
Requirement links: REQ-F-003  
Files/modules:
- Create or modify: `tests/test_webhook_routes.py`
- Inspect: `bazi_engine/app.py`, `bazi_engine/routers/webhooks.py`, docs

Steps:
1. Default-Entscheidung im PR festhalten: Runtime bleibt intern unter `/internal/api/webhooks/chart`, sofern Product-Owner keine öffentliche Route verlangt.
2. Test mit `TestClient`: `POST /internal/api/webhooks/chart` erreicht Handler und gibt ohne Secret strukturierten 503 zurück.
3. Test: `POST /api/webhooks/chart` ist entweder nicht dokumentiert oder wird bewusst als Redirect/Alias unterstützt. Default: nicht dokumentiert, 404 ist akzeptabel.
4. Docs-Grep-Test oder Review-Check hinzufügen, dass `/api/webhooks/chart` nicht mehr als gültiger Integrationspfad veröffentlicht wird.

Acceptance criteria:
- Eine einzige dokumentierte Integrations-URL existiert.
- Test beweist Erreichbarkeit der dokumentierten URL.

Validation:
- Command: `PYTHONPATH=$PWD pytest -q tests/test_webhook_routes.py`
- Expected result before docs/code fix: FAIL wegen falscher Dokumentation oder fehlendem Test.

Rollback note: Testdatei/Doc-Änderung zurücknehmen.

---

### TASK-007: Webhook-Dokumentation und optional Routing korrigieren

Objective: Bringe Dokumentation, Routerdocstring und Integration-Konfiguration auf denselben Pfad.  
Requirement links: REQ-F-003  
Files/modules:
- Modify: `docs/API_REFERENCE.md`
- Modify: `docs/api/01_developer_api_reference.md`
- Modify: `bazi_engine/routers/webhooks.py` docstring/comment only unless route policy changes
- Modify if needed: `bazi_engine/app.py`

Steps:
1. Alle Vorkommen von `/api/webhooks/chart` prüfen.
2. Bei Default-Entscheidung intern: auf `/internal/api/webhooks/chart` ändern und deutlich als internal/secret-protected markieren.
3. Falls Product-Owner public URL verlangt: stattdessen `/api/webhooks/chart` zusätzlich mounten und Test entsprechend ändern.
4. Keine Security-Abschwächung ohne explizite Entscheidung.

Acceptance criteria:
- Docs und Runtime-Pfad stimmen überein.
- `tests/test_webhook_routes.py` besteht.

Validation:
- Command: `grep -R "/api/webhooks/chart" -n docs bazi_engine | cat`
- Expected result: Nur noch gewünschte und kontextualisierte Vorkommen.

Rollback note: Docs/Routing-Änderung zurücknehmen.

---

### TASK-008: Superglue-Konfigurationsfehler-Test schreiben

Objective: Beweise, dass fehlende Superglue-Konfiguration aktuell als falscher 500 erscheint und nach Fix 503 liefert.  
Requirement links: REQ-F-004, REQ-F-005  
Files/modules:
- Create or modify: `tests/test_superglue_config_errors.py` oder vorhandene `tests/test_superglue_router.py`
- Inspect: `bazi_engine/services/superglue_client.py`, `bazi_engine/routers/superglue.py`

Steps:
1. Setze `FUFIRE_API_KEYS=ff_pro_testsecret`; entferne `SUPERGLUE_API_KEY` aus Test-Env.
2. Rufe `GET /v1/profile/testuser` und `POST /v1/profile/testuser/chart` mit gültigem API-Key auf.
3. Assert: Status `503`, ErrorEnvelope `service_unavailable`, sichere Message ohne Secret-Leak.
4. Assert: Standard-Headers vorhanden, sofern TASK-010 bereits umgesetzt ist; sonst als separate Erwartung vorbereiten.

Acceptance criteria:
- Test schlägt vor Fix mit 500 fehl.
- Test ist rein lokal und mockt keine externen Produktivsysteme.

Validation:
- Command: `PYTHONPATH=$PWD pytest -q tests/test_superglue_config_errors.py`
- Expected result before fix: FAIL mit 500 statt 503.

Rollback note: Testdatei löschen.

---

### TASK-009: Superglue-Konfigurationsfehler als 503 mappen

Objective: Ersetze generische unhandled 500 bei fehlender Superglue-Konfiguration durch strukturierten Service-Unavailable-Fehler.  
Requirement links: REQ-F-004  
Files/modules:
- Modify: `bazi_engine/services/superglue_client.py`
- Modify: `bazi_engine/routers/superglue.py`
- Test: `tests/test_superglue_config_errors.py`

Steps:
1. Definiere eine spezifische Exception, z. B. `SuperglueConfigurationError`, statt generischem `RuntimeError`.
2. Werfe diese Exception, wenn `SUPERGLUE_API_KEY` fehlt.
3. Fange sie im Router oder zentralen Handler und mappe auf 503 ErrorEnvelope.
4. Message operational hilfreich, aber secret-neutral formulieren: z. B. „Superglue service is not configured“.
5. Optional `/v1/ready` um dependency-status erweitern nur, wenn bestehender Health-Contract dies zulässt; sonst separater Folge-Task.

Acceptance criteria:
- T020/T022-Äquivalent liefert 503 statt 500.
- Kein Secret oder Env-Wert wird in Response/Logs offengelegt.

Validation:
- Command: `PYTHONPATH=$PWD pytest -q tests/test_superglue_config_errors.py`
- Expected result: PASS.

Rollback note: Exception-Klasse und Router-Mapping zurücknehmen.

---

### TASK-010: Fehler-Header-Test für 401/404/422/500/503 schreiben

Objective: Stelle sicher, dass dokumentierte Standard-Headers auch in Fehlerpfaden vorhanden sind.  
Requirement links: REQ-F-005  
Files/modules:
- Create or modify: `tests/test_error_response_headers.py`
- Inspect: `bazi_engine/middleware.py`, `bazi_engine/app.py`

Steps:
1. Teste repräsentative Fehlerpfade: missing auth 401, unknown route 404, validation 422, Superglue config 503, künstlicher/unhandled 500 falls bestehend sicher simulierbar.
2. Assert Headers: `X-Request-ID`, `X-API-Version`, `X-Response-Time-ms`; Rate-Limit-Headers separat behandeln.
3. Prüfe, dass Body-`request_id` und Header-`X-Request-ID` konsistent sind, sofern Runtime dies unterstützt.
4. Test vor Implementierung ausführen; erwartetes Fail bei unhandled 500/503 dokumentieren.

Acceptance criteria:
- Mindestens ein bisher betroffener Fehlerpfad fails vor Fix.
- Kein Test löst externe Calls aus.

Validation:
- Command: `PYTHONPATH=$PWD pytest -q tests/test_error_response_headers.py`
- Expected result before fix: FAIL wegen fehlender Standard-Headers in mindestens einem Fehlerpfad.

Rollback note: Neue Testdatei löschen.

---

### TASK-011: Header-Injection für Fehlerpfade robust machen

Objective: Garantierte Korrelations-/Versionsheader auch bei Exception-Responses herstellen.  
Requirement links: REQ-F-005  
Files/modules:
- Modify: `bazi_engine/middleware.py`
- Modify if needed: `bazi_engine/app.py`
- Test: `tests/test_error_response_headers.py`

Steps:
1. Analysiere die aktuelle `BaseHTTPMiddleware`-Implementierung.
2. Bevorzuge kleinste robuste Änderung: Exception in Middleware fangen, zentralen Handler nutzen und Header auch auf diese Response setzen; falls technisch unzuverlässig, pure ASGI Middleware implementieren.
3. Verhindere doppelte Header und miss keine vorhandene `request_id`.
4. Führe Fehler-Header-Tests aus.
5. Dokumentation nur dann anpassen, wenn Header-Garantie bewusst eingeschränkt wird. Default: Garantie herstellen.

Acceptance criteria:
- Standard-Headers sind auf 401/404/422/500/503 vorhanden.
- Bestehende erfolgreiche Response-Headers bleiben unverändert.

Validation:
- Command: `PYTHONPATH=$PWD pytest -q tests/test_error_response_headers.py tests/test_error_handling.py tests/test_error_sanitization.py`
- Expected result: PASS.

Rollback note: Middleware-Änderung zurücknehmen.

---

### TASK-012: Rate-Limit-Header-Contract korrigieren

Objective: Entferne die falsche Garantie für `X-RateLimit-Remaining` oder implementiere einen echten Wert.  
Requirement links: REQ-F-006  
Files/modules:
- Modify: `bazi_engine/app.py`
- Modify: `docs/API_REFERENCE.md`
- Modify: `docs/api/01_developer_api_reference.md`
- Test: `tests/test_openapi_error_contract.py` oder `tests/test_rate_limit_headers.py`

Steps:
1. Entscheidung im PR festhalten: Default ist Dokumentationskorrektur statt Phantom-Implementierung.
2. OpenAPI-Patch so ändern, dass `X-RateLimit-Remaining` nicht als garantiert für alle v1 responses erscheint; optional als conditional header dokumentieren.
3. Docs entsprechend ändern.
4. Runtime-Test prüfen: vorhandene Header dürfen bleiben; nicht vorhandene Header dürfen nicht als guaranteed dokumentiert sein.

Acceptance criteria:
- OpenAPI und Docs versprechen keinen Header, den Runtime nicht liefert.
- Keine Fake-Remaining-Werte werden erzeugt.

Validation:
- Command: `PYTHONPATH=$PWD pytest -q tests/test_rate_limit_headers.py tests/test_openapi_error_contract.py`
- Expected result: PASS. Falls `tests/test_rate_limit_headers.py` neu ist, zuerst failing, dann passing.

Rollback note: OpenAPI/docs Änderungen zurücknehmen.

---

### TASK-013: Legacy-Auth- und Auth-Error-Dokumentation angleichen

Objective: Korrigiere Dokumentation und Tests für Legacy-Auth und 401-Error-Code.  
Requirement links: REQ-F-007  
Files/modules:
- Modify: `docs/API_REFERENCE.md`
- Modify: `docs/api/01_developer_api_reference.md`
- Modify: `docs/ERROR_CODES.md` falls vorhanden/passend
- Test: existing auth tests or new `tests/test_auth_contract_docs.py` if doc checks are used

Steps:
1. Dokumentiere: Legacy business routes require API key when `FUFIRE_API_KEYS` is configured.
2. Dokumentiere Runtime-Code `unauthorized` für fehlenden/ungültigen API-Key oder ändere Runtime bewusst auf `invalid_api_key`. Default: Docs an Runtime angleichen.
3. Entferne/relativiere `tier_insufficient`, wenn kein 403 tier dependency existiert.
4. Ergänze negative Runtime-Tests falls noch nicht vorhanden: legacy route missing key -> 401.

Acceptance criteria:
- Docs enthalten keine Aussage „legacy business routes are public“, wenn Runtime schützt.
- Dokumentierte 401 ErrorEnvelope entspricht TestClient-Response.

Validation:
- Command: `PYTHONPATH=$PWD pytest -q tests/test_endpoint_negative.py tests/test_b2b_api_audit.py`
- Expected result: PASS.

Rollback note: Docs/test Änderungen zurücknehmen.

---

### TASK-014: Lokalen Ephemeris-Quickstart dokumentieren

Objective: Mache die SE1-Abhängigkeit für lokale Entwickler ausführbar und diagnostizierbar.  
Requirement links: REQ-NF-002  
Files/modules:
- Modify: `README.md`
- Modify/Create: `docs/runbooks/ephemeris-local-setup.md` if docs/runbooks exists; otherwise `docs/EPHEMERIS_SETUP.md`
- Modify if safe: readiness docs for `/v1/ready`

Steps:
1. Dokumentiere drei Wege: Docker-first, lokale SE1-Dateien mit `SE_EPHE_PATH`, oder bewusstes `EPHEMERIS_MODE=MOSEPH` falls im Projekt unterstützt.
2. Nenne die benötigten Dateien aus Audit: `sepl_18.se1`, `semo_18.se1`, `seas_18.se1`, `seplm06.se1`.
3. Ergänze Troubleshooting: 503 `ephemeris_unavailable` bedeutet fehlende lokale Daten, nicht zwingend API-Bug.
4. Optional: `/ready`-Response-Dokumentation um dependency availability erweitern, ohne bestehenden Contract zu brechen.

Acceptance criteria:
- README-Quickstart erklärt, wie T006/T007/T008 lokal 200 erreichen können oder warum 503 erwartbar ist.
- Keine urheberrechtlich/ lizenzrechtlich unsicheren Daten werden ins Repo eingecheckt.

Validation:
- Command: `grep -R "SE_EPHE_PATH\|ephemeris_unavailable\|sepl_18.se1" -n README.md docs | cat`
- Expected result: klare Treffer in Quickstart/Runbook.

Rollback note: Dokumentationsänderungen zurücknehmen.

---

### TASK-015: Full-Test-Suite-Signal wiederherstellen

Objective: Sorge dafür, dass `pytest -q` als Release-Signal entweder grün ist oder korrekt segmentiert wird.  
Requirement links: REQ-NF-001  
Files/modules:
- Inspect/modify: `pyproject.toml`
- Inspect/modify: `tests/snapshots/moseph/*`
- Inspect/modify: CI config (`MISSING: discover .github/workflows, GitLab, etc.`)
- Test: `tests/test_snapshot_stability.py` and full suite

Steps:
1. Prüfe, ob `respx` als Dev/Test-Dependency in `pyproject.toml` fehlt; wenn ja, ergänzen.
2. Reproduziere Snapshot-Fails gezielt: `PYTHONPATH=$PWD pytest -q tests/test_snapshot_stability.py --tb=short`.
3. Entscheide pro Snapshot-Abweichung: erwartete neue Felder akzeptieren und Snapshot regenerieren oder Code regressionsfrei korrigieren.
4. `tzdb_version_id unknown != 2026.1` untersuchen: Testumgebung pinnen oder Erwartung tolerant machen, wenn Version runtimeabhängig ist.
5. `solar_terms_count 23 != 24` nicht blind aktualisieren; fachliche Ursache prüfen oder als BLOCKER für Domain-Owner markieren.
6. Falls full suite externe/slow Tests enthält, Marker und dokumentierte Testprofile einführen: `unit`, `contract`, `integration`, `external`.

Acceptance criteria:
- `PYTHONPATH=$PWD pytest -q` ist grün in dokumentierter Dev-Umgebung, oder README/CI nutzt explizit grüne Profile und erklärt ausgeschlossene externe Tests.
- Snapshot-Änderungen sind reviewbar und begründet.

Validation:
- Command: `PYTHONPATH=$PWD pytest -q --tb=short --disable-warnings`
- Expected result: PASS or documented segmented PASS command plus explicit skipped/external rationale.

Rollback note: Dependency/test/snapshot Änderungen zurücknehmen; keine Snapshot-Massenupdates ohne Review.

---

### TASK-016: OpenAPI Tags und Contract-Surface aktualisieren

Objective: Aktualisiere API-Taxonomie und Contract-Dokumentation auf die reale Runtime-Surface.  
Requirement links: REQ-F-008  
Files/modules:
- Modify: `bazi_engine/app.py`
- Modify: `CONTRACT.md`
- Modify: `docs/API_REFERENCE.md`
- Modify: `docs/api/01_developer_api_reference.md`
- Test: `tests/test_openapi_tags.py` or existing OpenAPI contract tests

Steps:
1. Test schreiben: alle operation tags müssen im globalen `tags` array existieren.
2. `Superglue` und `Impact` in global tags ergänzen.
3. `CONTRACT.md` ersetzen/aktualisieren: nicht mehr „13 frozen endpoints“ ohne Scope. Gliedere in `v1`, `legacy`, `internal`, `proxy`.
4. Optional: generierte Route-Tabelle aus OpenAPI nutzen statt manuell gepflegter Endpoint-Zählung.

Acceptance criteria:
- Keine operation tags ohne globale Beschreibung.
- CONTRACT.md widerspricht der Runtime-Surface nicht.

Validation:
- Command: `PYTHONPATH=$PWD pytest -q tests/test_openapi_tags.py tests/test_openapi_contract.py`
- Expected result: PASS.

Rollback note: Tag/docs Änderungen zurücknehmen.

---

### TASK-017: `/chart`-Lifecycle bewusst entscheiden und kodieren

Objective: Beseitige die Ambiguität zwischen „internal“ und schema-visible Legacy Endpoint.  
Requirement links: REQ-F-008  
Files/modules:
- Modify conditionally: `bazi_engine/app.py`
- Modify: `docs/API_REFERENCE.md`
- Modify: `docs/api/01_developer_api_reference.md`
- Test: `tests/test_chart_lifecycle_contract.py`

Steps:
1. Owner-Entscheidung einholen oder Default im PR markieren: keine harte Entfernung ohne Zustimmung.
2. Option A, wenn internal: Route unter `/internal` mounten oder `include_in_schema=False`; Docs als internal markieren; Deprecation-Hinweis für alte `/chart` falls Runtime erhalten bleibt.
3. Option B, wenn public legacy: In OpenAPI sichtbar lassen, aber als deprecated/public legacy dokumentieren und Auth-Anforderung klar angeben.
4. Test codiert gewählte Policy: Schema-visibility, Deprecation-Flag, Auth-Anforderung und Docs-Wording.

Acceptance criteria:
- `/chart` hat genau einen expliziten Lifecycle-Status: internal, deprecated legacy oder supported public.
- OpenAPI und Docs sagen dasselbe.

Validation:
- Command: `PYTHONPATH=$PWD pytest -q tests/test_chart_lifecycle_contract.py tests/test_openapi_contract.py`
- Expected result: PASS.

Rollback note: Lifecycle-/routingbezogene Änderungen zurücknehmen; bei Public-API-Bruch nur mit Deprecation-Plan.

---

### TASK-018: Finaler Contract-/Regression-Gate

Objective: Beweise, dass alle Fixes zusammen konsistent sind.  
Requirement links: all  
Files/modules:
- All modified files
- `spec/openapi/openapi.json`
- PR validation log

Steps:
1. OpenAPI regenerieren.
2. Multi-seed Export-Check ausführen.
3. Targeted contract/API tests ausführen.
4. Full suite oder dokumentierte Profile ausführen.
5. Docs-Grep für alte/falsche Pfade und Header-Garantien.
6. Review checklist ausfüllen: no secrets, no external calls, no undocumented breaking route removal.

Acceptance criteria:
- P0/P1-Findings sind testbar geschlossen oder mit Owner-Entscheidung dokumentiert.
- OpenAPI und Runtime sind synchron.
- Finaler Validierungslog liegt im PR.

Validation:
```bash
for seed in 0 1 2 3 4 5 6 7 8 9 10; do
  PYTHONHASHSEED=$seed PYTHONPATH=$PWD python3 scripts/export_openapi.py --check
done
PYTHONPATH=$PWD pytest -q tests/test_openapi_determinism.py tests/test_openapi_error_contract.py tests/test_webhook_routes.py tests/test_superglue_config_errors.py tests/test_error_response_headers.py
PYTHONPATH=$PWD pytest -q --tb=short --disable-warnings
```
Expected result: PASS, or explicit segmented PASS with documented exclusions.

Rollback note: PR revert; no schema or route removals should be shipped without changelog/deprecation path.

## Validation strategy

### TDD sequence

1. Reproduce baseline failures.
2. Write focused failing contract/runtime test.
3. Implement smallest fix.
4. Run focused test.
5. Run related regression tests.
6. Regenerate OpenAPI/docs if contract changed.
7. Run final gate.

### Given/When/Then acceptance examples

**OpenAPI determinism**
- Given multiple `PYTHONHASHSEED` values,
- When `app.openapi()`/`scripts/export_openapi.py --check` is executed,
- Then schema refs for chart endpoints remain stable and export check passes.

**Superglue config error**
- Given valid `X-API-Key` and missing `SUPERGLUE_API_KEY`,
- When `/v1/profile/testuser` is requested,
- Then response is 503 ErrorEnvelope `service_unavailable` with standard headers.

**Webhook path**
- Given the documented webhook path,
- When a request is sent without webhook secret,
- Then the route reaches the handler and returns configured auth/service error, not 404.

**Error contract**
- Given a protected operation in OpenAPI,
- When its responses are inspected,
- Then 401 and 429 exist and use ErrorEnvelope; 503 exists for dependency-backed operations.

## Rollback and safety

- Work only in feature branch; no direct `main`/`master` commits.
- No force-push or `--no-verify` in instructions.
- Do not check in SE1 files, API keys, webhook secrets, or external credentials.
- Route removals require explicit owner approval and changelog/deprecation note.
- If OpenAPI regeneration causes large diff, isolate it in one commit after code changes.
- If snapshot changes are broad, split into separate reviewed commit and explain semantic reason.

## Execution handoff

Recommended execution order:
1. TASK-001 baseline.
2. TASK-002 to TASK-005 for P0 OpenAPI contract.
3. TASK-006 to TASK-007 for webhook path truth.
4. TASK-008 to TASK-011 for runtime errors and headers.
5. TASK-012 to TASK-014 for docs/DX/header/auth alignment.
6. TASK-015 for test-suite signal.
7. TASK-016 to TASK-017 for P2 taxonomy/lifecycle.
8. TASK-018 final gate.

Minimal PR split if team prefers smaller reviews:
- PR 1: OpenAPI determinism + error responses.
- PR 2: Webhook + Superglue + headers.
- PR 3: Docs/DX/auth/rate-limit + contract/tag cleanup.
- PR 4: Snapshot/test-suite baseline, if diffs are large.

## Options considered

| Option | Description | Pros | Cons | Decision |
|---|---|---|---|---|
| A | One large PR for all findings | Single audit closure | Hard to review, higher regression risk | Not preferred |
| B | P0/P1 first, P2 later | Fast risk reduction, manageable review | Some low issues remain briefly | Preferred |
| C | Rewrite API routing/docs generation | Could solve source-of-truth drift broadly | Overengineering for current findings | Rejected for this cycle |

## Plausibility and truth self-check

- **Goal block length:** Intentionally compact and under 4000 characters.
- **Unsupported claims removed:** No claim that production is broken; ephemeris issue remains local/DX unless production evidence appears.
- **Paths:** All modify paths are taken from the audit report. CI paths are marked `MISSING` and require discovery.
- **Commands:** Commands are taken from audit report or are direct local Pytest/OpenAPI checks. No external systems are called.
- **Acceptance criteria:** Binary and testable wherever possible.
- **Bias check:** Risk of over-prioritizing contract/docs over domain correctness. Mitigation: domain snapshot mismatch, especially `solar_terms_count`, is not blindly updated and is flagged for deeper review.
- **Overengineering check:** No new framework, no broad rewrite, no new source-of-truth system beyond tests + generated OpenAPI discipline.

## Meta-Status

- **Kategorie:** (2) Faktisch + ableitbar
- **Bias-Notizen:** Der Plan priorisiert auditierte Contract-/DX-/Test-Signal-Probleme. Das ist angemessen für API-Integration, aber nicht gleichbedeutend mit einer fachlichen Bewertung der astrologischen Berechnungsqualität.
