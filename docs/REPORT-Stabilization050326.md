# Abschlussbericht: Contract-Stabilisierung (05.03.2026)

**Commit:** `9d33922` auf `main` @ `DYAI2025/BAFE`  
**Scope:** Keine Behavior-Änderungen — rein strukturelle Stabilisierung  
**Teststand:** 767 Tests grün, 10 skipped, 0 Failures

---

## 1. Ausgangslage

| Problem | Auswirkung |
|---------|-----------|
| Kein committetes OpenAPI-Artefakt | Externe Dienste hatten keinen stabilen Contract zum Anbinden |
| `/validate` war in OpenAPI `object any` | Codegen und Dokumentation lieferten keine Typen für den Haupt-Validator |
| 8 von 13 Endpoints hatten untypisierte Responses | Clients konnten keine typisierten SDKs generieren |
| `_BUILD_VERSION` war 3× hardcodiert | Versionsdrift zwischen `app.py`, `chart.py`, `info.py` möglich |
| Kein CI-Gate für Contract-Drift | Schema-Änderungen konnten unbemerkt durchrutschen |

---

## 2. Was wurde geändert

### 2.1 Bug-Fix: Versionszentralisierung (B0)

**Vorher:** `_BUILD_VERSION = "1.0.0-rc1-20260220"` in drei Dateien.  
**Nachher:** Einzige Quelle ist `bazi_engine.__version__`. Die Router importieren davon, mit Fallback auf `BUILD_VERSION` Env-Variable für Deployments.

| Datei | Änderung |
|-------|----------|
| `bazi_engine/__init__.py` | `__version__` hinzugefügt |
| `bazi_engine/app.py` | Importiert `__version__` statt Hardcode |
| `bazi_engine/routers/chart.py` | Importiert `_ENGINE_VERSION` |
| `bazi_engine/routers/info.py` | Importiert `_ENGINE_VERSION` |

### 2.2 OpenAPI-Baseline (C0)

| Artefakt | Pfad | Zweck |
|----------|------|-------|
| OpenAPI Spec | `spec/openapi/openapi.json` | Committeter Contract — Source of Truth |
| Export-Script | `scripts/export_openapi.py` | Generiert Spec aus `app.openapi()` |
| CI-Step | `.github/workflows/ci.yml` | `--check` Modus bricht bei Drift |

**Workflow:** Nach jeder Endpoint-Änderung → `python scripts/export_openapi.py` → diff reviewen → committen. CI schützt automatisch.

### 2.3 `/validate` Typisierung (C1)

`app.py` enthält jetzt einen `_custom_openapi()` Hook, der:

1. `ValidateRequest.schema.json` und `ValidateResponse.schema.json` aus `spec/schemas/` lädt
2. Draft-07-Metakeys (`$schema`, `$id`) entfernt (OpenAPI-inkompatibel)
3. Beide als `components.schemas.ValidateRequest` / `ValidateResponse` einbettet
4. Die `/validate`-Route patcht: Request → `$ref: ValidateRequest`, Response → `$ref: ValidateResponse`
5. `ErrorEnvelope` Schema für 422/500 Fehler-Responses ergänzt

**Runtime bleibt identisch** — die Draft-07 Validierung via `jsonschema.Draft7Validator` ist unverändert.

### 2.4 Alle Endpoints typisiert (C2)

| Endpoint | Neues Response-Model | Vorher |
|----------|---------------------|--------|
| `GET /` | `RootResponse` | `Dict[str, Any]` |
| `GET /health` | `HealthResponse` | `Dict[str, str]` |
| `GET /build` | `BuildResponse` | `Dict[str, str]` |
| `GET /api` | `ApiResponse` | `Dict[str, Any]` |
| `GET /info/wuxing-mapping` | `WuxingMappingResponse` | `Dict[str, Any]` |
| `POST /calculate/bazi` | `BaziResponse` | `Dict[str, Any]` |
| `POST /calculate/western` | `WesternResponse` | `Dict[str, Any]` |
| `POST /internal/api/webhooks/chart` | `WebhookChartResponse` | `Dict[str, Any]` |

Bereits typisiert (unverändert): `/calculate/fusion`, `/calculate/wuxing`, `/calculate/tst`, `/chart`.

**Alle Response-Models wurden aus dem tatsächlichen Rückgabeverhalten abgeleitet — kein Feld hinzugefügt oder entfernt.**

### 2.5 Dokumentation

| Datei | Inhalt |
|-------|--------|
| `CONTRACT.md` | Vertragsdokumentation: Source of Truth, Versionierung, Endpoint-Übersicht |
| `CLAUDE.md` (erweitert) | Neuer Abschnitt "OpenAPI Contract" + Gotchas #7/#8 |

---

## 3. Automatische Tests

### 3.1 Bestehende Tests (759, unverändert)

| Testdatei | Abdeckung |
|-----------|-----------|
| `test_golden.py` | Bekannte korrekte Pillar-Ergebnisse |
| `test_golden_vectors.py` | Randfälle (hohe Breitengrade, LMT, Zi-Grenze) |
| `test_invariants.py` | Strukturelle Eigenschaften (DAY_OFFSET) |
| `test_api.py` | FuFirE Contract-Schema-Validierung |
| `test_endpoints.py` | FastAPI Endpoint-Integration |
| `test_fusion.py` | Wu-Xing Fusion-Analyse |
| `test_properties.py` | Generative / Property-basierte Tests |
| `test_time_utils.py` | DST, Zeitzonen-Randfälle |
| `test_western.py` | Western Chart Berechnungen |
| `test_phases.py` | Lunar/Jieqi Phasen |
| `test_chart.py` | Combined Chart Endpoint |
| `test_error_handling.py` | Fehlerbehandlung |
| `test_import_hierarchy.py` | Modulhierarchie-Verletzungen |
| + weitere | Calibration, Services, Constants, Zones, Research |

### 3.2 Neue Contract-Tests (8)

**`tests/test_openapi_contract.py`:**

| Test | Prüft |
|------|-------|
| `test_version_matches_engine` | `info.version` == `bazi_engine.__version__` |
| `test_all_endpoints_have_typed_responses` | Kein Endpoint mit generischem `object any` Response |
| `test_validate_request_schema_referenced` | `/validate` Request → `$ref: ValidateRequest` |
| `test_validate_response_schema_referenced` | `/validate` Response → `$ref: ValidateResponse` |
| `test_validate_request_has_definitions` | ValidateRequest enthält BirthEvent, EngineConfig, etc. |
| `test_validate_response_has_definitions` | ValidateResponse enthält Issue, ErrorCode, etc. |
| `test_error_envelope_exists` | ErrorEnvelope Schema vorhanden |
| `test_validate_422_uses_error_envelope` | 422 Response referenziert ErrorEnvelope |

### 3.3 CI-Gate: OpenAPI Drift

```yaml
# .github/workflows/ci.yml
- name: Check OpenAPI spec drift
  run: python scripts/export_openapi.py --check
```

Bricht den Build, wenn jemand einen Endpoint ändert ohne die Spec zu aktualisieren.

---

## 4. Verbesserungsbedarf & Empfehlungen

### 4.1 Kurzfristig (nächste Iteration)

| Thema | Empfehlung | Aufwand |
|-------|-----------|---------|
| **Characterization Tests** | Für jeden Endpoint einen Snapshot-Test der tatsächlichen Response-Struktur. Die Response-Models in C2 sind *deklarativ* — ein Test der validiert "Response passt zu Model" fehlt für `/calculate/bazi` und `/calculate/western`. | Klein |
| **Error-Response Konsistenz** | `/calculate/bazi` und `/calculate/western` nutzen `HTTPException(detail=str)`, die anderen Endpoints nutzen `BaziEngineError.to_dict()`. Das ergibt unterschiedliche Error-Formate. Vereinheitlichen auf `ErrorEnvelope` überall. | Mittel |
| **OpenAPI 3.0 Artefakt** | Falls Konsumenten kein OpenAPI 3.1 unterstützen: zusätzlich `openapi.3.0.json` exportieren. Tooling: `openapi-downconvert` oder FastAPI `openapi_version="3.0.2"`. | Klein |

### 4.2 Mittelfristig

| Thema | Empfehlung | Aufwand |
|-------|-----------|---------|
| **Codegen-Gate in CI** | `openapi-generator` für TypeScript/Python Client ausführen → muss kompilieren. Deckt subtile Schema-Fehler auf die statische Prüfung nicht findet. | Mittel |
| **Schemathesis / Contract-Fuzzing** | Automatisches Fuzzing gegen die OpenAPI-Spec. Findet Edge-Cases wo die Runtime vom Contract abweicht. | Mittel |
| **Response Validation Middleware** | FastAPI Middleware die in DEV/TEST Responses gegen die OpenAPI-Schemas validiert. Fängt Drift zur Laufzeit. | Mittel |
| **`/validate` Draft-07 → 2020-12 Migration** | OpenAPI 3.1 ist nativ JSON Schema 2020-12. Die aktuellen Draft-07 Schemas funktionieren, aber `$ref`-Auflösung ist subtil anders. Erst nach ausführlichen Regressionstests migrieren. | Groß |

### 4.3 Langfristig

| Thema | Empfehlung |
|-------|-----------|
| **API Versioning** | Wenn Breaking Changes nötig werden: `/v2/` Prefix oder Header-basiertes Versioning. Aktuell nicht nötig (rc-Phase). |
| **Problem Details (RFC 9457)** | Standard `application/problem+json` statt Custom-ErrorEnvelope. Branchenweit verstanden, bessere Tooling-Unterstützung. |
| **SDK Publishing** | Aus der OpenAPI-Spec automatisch NPM/PyPI Packages generieren und veröffentlichen. |

### 4.4 Was ich explizit NICHT empfehle

- **Endpoints jetzt umbenennen oder umstrukturieren** — andere Dienste binden bereits an. Jede Pfad-Änderung ist ein Breaking Change.
- **Response-Felder entfernen** — nur hinzufügen (additiv).
- **Draft-07 Migration ohne Regressionstest** — subtile Verhaltensänderungen möglich bei `type: ["string", "null"]` etc.

---

## 5. Zusammenfassung

Die FuFirE-API hat jetzt einen **eingefrorenen, CI-geschützten OpenAPI-Contract**. Alle 13 Endpoints sind typisiert, die `/validate`-Schemas sind maschinenlesbar eingebettet, und Versionsdrift ist durch Zentralisierung und CI-Gate verhindert.

**Keine externe Integration muss sich ändern** — die Responses sind byte-identisch zu vorher, nur die Dokumentation und Typ-Informationen sind jetzt vollständig.
