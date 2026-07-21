# Implementation Plan — `bazi-hehun` (POST /v1/match/bazi-hehun + landingpage visibility)

Status: plan (Phase 1 output — no code written by this document)
Feature Slug: `bazi-hehun`
Date: 2026-07-02
Planner: strategic-planning agent (/agileteam Phase 1)
Spec basis (FROZEN, commit fabe6bf): `docs/prd/bazi-hehun.prd.md`, `docs/canvas/bazi-hehun.canvas.md`,
`docs/traceability.md`, `docs/audits/2026-07-02-bazi-hehun-spec-audit.md`
Acceptance-test contract (parallel, tester-owned): `docs/testing/bazi-hehun.acceptance-tests.md`
Worktree (backend): `/Users/benjaminpoersch/fufireAPI/FuFirE-bazi-hehun` (branch `feature/bazi-hehun`)
Frontend repo (user-approved scope, audit F1): `/Users/benjaminpoersch/Projects/SaaS/FuFirEProject/Fufire_API-landingpage`

---

## 1. Goal

Ship the deterministic BaZi-Hehun pair-analysis MVP:

- `POST /v1/match/bazi-hehun` — /v1-ONLY mount (DECISION-001), API-key protected,
  birth_input-only (D2), exactly the 3 MVP pair layers (D3/CAN-012), zero score fields
  anywhere in schema or response (D1), server-side consent 422 (D5/CAN-013),
  privacy-by-default logging, evidence ledger, `quality_flags.ephemeris_mode` attestation
  parity (audit F8 / planning note b).
- Landingpage endpoint-tester visibility under category `Hehun`, label `BaZi Hehun`,
  honest subtitle "Deterministic pair-chart facts — no compatibility score" (D7),
  consent field in the generated form, behind a NEW feature flag DEFAULT OFF in
  production (CAN-015). The flag **flip** is a later, user-gated launch act — NOT part
  of this build; only the mechanism + its tests are.

## 2. Non-goals (binding, from the frozen spec)

- No score fields — `total_score`, `sub_scores`, `score_class`, `awarded_points`,
  `score_confidence` do not exist in any schema, response, example, or doc (D1, REQ-007).
- No `mode=raw_bazi` / `CanonicalBaziChartInput` (D2, NOGOAL-005).
- No interaction-matrix layers and **no `MISSING_INTERACTION_TABLE` placeholder blocks**
  (D3, NOGOAL-006, AC-006b/c).
- No LLM/Fusion interpretation-readiness claims (D4, AC-008b).
- No western synastry, no registered-user matching (REQ-016 is P2, deferred).
- No legacy unversioned `/match/...` mount (AC-001c, DECISION-001).
- No production flag flip / public launch (OQ-001 + user sign-off gate, CAN-015).

## 3. Preconditions and known gaps

Verified at code level (this planning pass, worktree = main state):

| Fact | Evidence |
|---|---|
| Pure `compute_bazi()` reachable from router | `bazi_engine/routers/bazi.py:372` (`res = compute_bazi(inp)`; audit claim 1) |
| Shared response shaping lives at Level 5 | `bazi_engine/routers/shared.py:35` `format_pillar()`, `ErrorEnvelope`, `ProvenanceResponse`, `PrecisionBlock`, `QualityFlags` |
| Single mount idiom + /v1-only precedent | `bazi_engine/app.py:322` `_protected = [Depends(require_api_key)]`; admin router mounted /v1-only at `app.py:359` |
| API-key tier + downstream access | `bazi_engine/auth.py:82` `resolve_key_info()`; `require_api_key` stores `KeyInfo` on `request.state.key_info` (`auth.py:242,262`) |
| Request-ID available to routers | `bazi_engine/middleware.py:25-26` sets `request.state.request_id` |
| Ephemeris mode attestation source | `SwissEphBackend.mode` (`bazi_engine/ephemeris.py:66-89`); env resolution pattern `bazi_engine/transit.py:61` `_effective_ephemeris_mode()`; centralized MOSEPH attestation per commits d9780a9/518b556 |
| Wu-Xing ledger with visible/hidden stems + weights exists | `bazi_engine/wuxing/analysis.py:110` `calculate_wuxing_vector_from_planets_with_ledger`, hidden-stem Qi labels at `analysis.py:229-251`; ruleset keys `hidden_stems`, `hidden_stems_weighting` in `spec/rulesets/standard_bazi_2026.json` |
| Ruleset has NO interaction/Ten-Gods/Shen-Sha tables | audit claim 3 (14 top-level keys, zero interaction hits) — confirms D3 layer cut |
| Day anchor is `anchor_verification: "unverified"` | ruleset `day_cycle_anchor` → AC-004c warning premise |
| OpenAPI export/drift tooling | `scripts/export_openapi.py` (`--check` CI mode) |
| Frontend: TAG_TO_CATEGORY map + "Raw Data" fallback | `src/lib/endpoint-catalog.ts:42-58`, fallback line 75 |
| Frontend: category union lives in `src/types.ts:24-39` | must gain `"Hehun"` member (see scope note, §8) |
| Frontend: SchemaForm renders nested objects + booleans generically | `SchemaForm.tsx:129-141` (checkbox), `:164-178` (recursive object); ajv pre-send validation in `form-validate.ts` gates Send |
| Frontend: proxy is fail-closed against loaded OpenAPI | `src/server/app.ts:1073-1106`; spec served at `/api/v1/openapi.json` (`app.ts:507-518`), loaded from `src/api/openapi.json` (dev) / `dist/openapi.json` (prod) |
| Frontend: snapshot authority check exists | `scripts/verify-openapi-authority.mjs`; `npm run test:authority` |
| Frontend: NO feature-flag mechanism exists | verified 2026-07-02 — must be created (T18) |
| Frontend: vitest, tests in `tests/unit|integration|e2e` | `vitest.config.ts`; existing `tests/unit/endpoint-catalog.test.ts` |

Known gaps carried into the build (not closed by this plan):

- MISSING-001..003 — domain-approved interaction/Ten-Gods/DMS tables. Gate ONLY the
  deferred matrices/scoring. This plan contains **zero** matrix work; AC-006b/c tests
  guard against leakage.
- MISSING-004 / OQ-001 — legal consent wording. Gates flag flip, not build. Build uses
  neutral consent copy that must not imply legal review (AC-012d).
- MISSING-005 — runtime evidence from the deployed boundary. Closed only by T22
  (final validation milestone, requires deployment).
- OQ-003 — domain source for future tables. No build impact.
- REQ-015 full-request p95 target — explicitly MISSING until T22 produces a live
  baseline (AC-015c).

---

## 4. Architecture sketch

### 4.1 Backend — new Level-4 subpackage `bazi_engine/match/` + Level-5 router

```
Level 0-3 (existing, untouched): constants, types, exc, ephemeris, time_utils, jieqi,
                                 bafe.ruleset_loader (carve-out data loader)
Level 4 (existing, untouched):   bazi.compute_bazi, bazi_rules, wuxing/*, auth (KeyInfo),
                                 provenance.build_provenance
Level 4 (NEW):  bazi_engine/match/
                ├── __init__.py        # public surface of the subpackage
                ├── types.py           # frozen dataclasses: NormalizedChart, PairLayer,
                │                      #   TextBlock, EvidenceEntry, Warning codes enum
                ├── normalize.py       # REQ-004: BaziResult+BaziInput → NormalizedChart
                │                      #   (canonical stems/branches/pillars, wuxing ledger
                │                      #    visible+hidden w/ source+weight, warnings)
                ├── individual.py      # REQ-005: per-person layers (day_master, spouse-
                │                      #   palace/day-branch FACTS, month command, vector,
                │                      #   DMS/Yong-Shen stubs w/ source_status+confidence)
                ├── pair.py            # REQ-006: EXACTLY 3 layers — day_master_comparison,
                │                      #   spouse_palace_day_branch, wuxing_vector_comparison
                ├── textblocks.py      # REQ-008: raw_analysis_text blocks (AC-008a schema)
                │                      #   + lexical blocked-language guard (AC-007e)
                ├── evidence.py        # REQ-013: evidence ledger — 1 entry per block+warning
                ├── privacy.py         # REQ-012: consent hash-log helper, redaction rules
                ├── observability.py   # REQ-013/015: latency metric log; team-vs-external
                │                      #   classification (KeyInfo + FUFIRE_TEAM_KEY_ALLOWLIST)
                └── canonical.py       # REQ-014: order-independent canonical JSON hash
Level 5 (NEW):  bazi_engine/routers/match.py
                # Pydantic request/response models + endpoint. Composition seam (see 4.2).
Level 5 (edit): bazi_engine/app.py — import + ONE include_router line (/v1-only, DECISION-001
                comment), placed next to the admin mount (app.py:359 precedent).
```

Import direction: `match/*` imports only Levels 0–4 (`bazi`, `bazi_rules`, `wuxing`,
`constants`, `types`, `auth` for `KeyInfo` — same-level, allowed). `match/*` **never**
imports `routers/*`, `app`, `limiter`, or `services/*`. `routers/match.py` imports
`match/*`, `routers/shared.py`, `routers/bazi.py` (sibling, for `BaziRequest`), and
`..limiter`. `tests/test_import_hierarchy.py` must stay green.

### 4.2 The reuse-vs-hierarchy seam (planning note c + AC-003c, decided here)

Constraint conflict: planning note (c) demands REUSING shared response-shaping helpers
(`format_pillar` etc.), but those live at Level 5 (`routers/shared.py`) and `match/` is
Level 4. **Resolution: composition at the router.** `routers/match.py`:

1. builds one `BaziInput` per person exactly like `routers/bazi.py:349-371`
   (`resolve_local_iso` → `BaziInput`), calls pure `compute_bazi()` twice (AC-003b/d —
   no duplicated core logic, no cross-user state);
2. shapes each person's `pillars` block by calling the SAME `format_pillar` from
   `routers/shared.py` — imported, not copied (AC-003c);
3. passes raw `BaziResult`/`BaziInput` pairs into the pure `match/` engine functions,
   which never format for HTTP.

AC-003c is enforced by test, not by trust: `tests/test_match_service_boundary.py`
computes `/v1/calculate/bazi` for person A and asserts the per-person pillar block inside
the match response deep-equals it.

The **person payload type is `BaziRequest` itself** (imported from `routers/bazi.py`):
one frozen OpenAPI component, "BaziRequest-compatible" by construction (REQ-002,
AC-002a). Its `include_trace` field is accepted and ignored (documented in the field
description of the match request).

### 4.3 Request/response contract (shape summary for the builder + tester)

```
MatchRequest:
  mode: Literal["birth_input"]                  # any other value → 422 (AC-002b/c)
  person_a: BaziRequest                          # reused component (AC-002a)
  person_b: BaziRequest
  options: MatchOptions (REQUIRED)
    second_person_consent_confirmed: bool        # REQUIRED; validator → 422 when False
    persist_raw: bool = False                    # default false (AC-012b)
    model_config: extra="forbid"                 # scoring/matrix options → 422 (AC-009b)
  model_config: extra="forbid"                   # raw chart payloads → 422 (AC-002b)

MatchResponse:
  schema_version: str                            # e.g. "hehun-mvp-1"
  individual: {person_a: IndividualAnalysis, person_b: IndividualAnalysis}   # AC-005a
  pair: {day_master_comparison, spouse_palace_day_branch, wuxing_vector_comparison}
                                                 # exactly these 3 keys (AC-006a/b)
  raw_analysis_text: [TextBlock]                 # id, layer, statement_type, subject,
                                                 # text, source_status, evidence_ids (AC-008a)
  warnings: [WarningEntry]                       # AC-004c, AC-008c
  evidence_ledger: [EvidenceEntry]               # AC-013a
  provenance: ProvenanceResponse                 # reuse build_provenance() (REQ-004)
  quality_flags: MatchQualityFlags               # {ephemeris_mode: "SWIEPH"|"MOSEPH"} (F8)
  precision: {person_a: PrecisionBlock, person_b: PrecisionBlock}
  request_id: str                                # echo for AC-013c
  # NO total_score / sub_scores / score_class / awarded_points / score_confidence — D1
```

`MatchQualityFlags` is a NEW minimal model in `routers/match.py` (`ephemeris_mode` only,
sourced from the centralized ephemeris attestation — `SwissEphBackend.mode` /
`EPHEMERIS_MODE` env resolution as in `transit.py:61`). Rationale: the shared
`QualityFlags` (`routers/shared.py:80`) requires western-only `house_system_*` fields
that would be dishonest noise on a BaZi-only endpoint. Field name + values are identical
to the single-chart attestation → parity per audit F8. (Micro-decision recorded here;
builder does not re-decide.)

DMS/Yong-Shen fields (AC-005b): present as objects with `source_status:
"NEEDS_DOMAIN_REVIEW"` (or `"MISSING"`) + `confidence` — they carry status, never
invented values (AC-005c). The spouse-palace layer emits **computed identification facts
only** (day-branch identity, stem/branch labels) + `source_status` — no interpretive
claims (planning note a, F7).

### 4.4 Where each concern lives

| Concern | Module | Key ACs |
|---|---|---|
| Normalization + wuxing ledger + warnings | `match/normalize.py` | AC-004a/b/c |
| Individual layers, DMS/Yong-Shen status stubs | `match/individual.py` | AC-005a/b/c |
| 3 pair layers, no points, no matrix stubs | `match/pair.py` | AC-006a-d |
| Raw text blocks + blocked-language guard | `match/textblocks.py` | AC-008a/c, AC-007e |
| Evidence ledger | `match/evidence.py` | AC-013a |
| Consent hash-log, redaction discipline | `match/privacy.py` | AC-012a/f |
| Latency metric, team/external classification | `match/observability.py` | AC-013b/c/d, AC-015b |
| Canonical hash (determinism) | `match/canonical.py` | AC-014a |
| HTTP models, consent 422, error mapping, mount | `routers/match.py` + `app.py` | AC-001*, AC-002*, AC-009*, AC-012c |

Note on `match/canonical.py`: `bafe/canonical_json.py` exists but `bafe` is nominally
Level 5 and the hierarchy carve-out covers ONLY `bafe.ruleset_loader`. A ~10-line
`json.dumps(sort_keys=True)` + sha256 helper in `match/` avoids widening the carve-out.

### 4.5 Frontend (repo: `/Users/benjaminpoersch/Projects/SaaS/FuFirEProject/Fufire_API-landingpage`)

```
src/lib/feature-flags.ts (NEW)     # isHehunVisible(): VITE_FEATURE_HEHUN === "true";
                                   # unset/anything-else ⇒ false ⇒ DEFAULT OFF (CAN-015)
src/lib/endpoint-catalog.ts        # TAG_TO_CATEGORY["Hehun"] = "Hehun"; flag-gated filter
                                   # (flag OFF ⇒ Hehun-tagged ops dropped from catalog);
                                   # CATEGORY_SUBTITLE map (NEW — none exists today)
src/types.ts                       # category union += "Hehun"  (scope note §8)
src/components/EndpointTesterShowcase.tsx  # render category subtitle where category renders
                                   # (line ~646); consent-UI hint (scope: "consent-UI
                                   # component under src/components/** — new or extended")
public/openapi.json + src/api/openapi.json  # snapshot sync from backend export
tests/unit + tests/integration     # vitest; catalog/flag/subtitle/copy tests; proxy test
```

Consent field UI: `SchemaForm` renders the required boolean generically
(`SchemaForm.tsx:129-141`) and ajv blocks Send when it is missing — the visible consent
label/copy comes from the backend OpenAPI field `description`. Therefore the
**consent copy is authored in T8 (backend)** and must not imply legal review (AC-012d);
the frontend only adds honest framing, no marriage-matching promise anywhere (AC-011f).

Flag semantics: build-time env (`VITE_FEATURE_HEHUN`) compiled into the bundle. Flip =
set env in Railway + redeploy = the PUBLIC LAUNCH act (CAN-015) — deliberately outside
this build. The proxy stays fail-closed-open-by-spec: the endpoint is API-reachable
through `/api/v1/proxy` even with the flag OFF (canvas: "backend endpoint may be live
earlier — API-reachable, not advertised"). Tests assert catalog invisibility, not proxy
blocking.

---

## 5. Milestones → atomic tasks

TDD is binding per task: the named failing test (from the tester's parallel contract in
`docs/testing/bazi-hehun.acceptance-tests.md`, mapped by AC-ID) is written/adopted FIRST,
shown failing, then implemented. Test file names follow the frozen traceability matrix.
Backend test command baseline: `pytest -q tests/test_match_<area>.py` then the full gate
in T16. `plumbline-scope-check` runs per increment (backend); frontend scope is enforced
via the changed-files list recorded in each frontend task.

### Milestone A (= Iteration 1): Pure match engine — `bazi_engine/match/` (Level 4)

| ID | Goal | Files | AC-IDs | Test-first | Depends on |
|---|---|---|---|---|---|
| T1 | Subpackage scaffold + frozen domain types + warning-code constants | `bazi_engine/match/__init__.py`, `match/types.py` | AC-008a (block shape), AC-013a (entry shape) — structural | `tests/test_match_raw_blocks.py::test_textblock_fields`, `tests/test_match_normalization.py::test_normalized_chart_shape` (fail: ImportError) | — |
| T2 | Normalization: `BaziResult`+`BaziInput` → `NormalizedChart`; day_master = day stem ONLY; month/hour masters as provenance labels; wuxing ledger with visible+hidden stems (source+weight, reuse `wuxing/analysis.py` ledger pattern + ruleset `hidden_stems`/`hidden_stems_weighting` via `bafe.ruleset_loader`); warnings: `DAY_ANCHOR_UNVERIFIED` (ruleset `anchor_verification`), `BIRTH_TIME_UNKNOWN` | `match/normalize.py` | AC-004a, AC-004b, AC-004c | `tests/test_match_normalization.py` | T1 |
| T3 | Individual analysis: `IndividualAnalysis` per person — day master, spouse-palace/day-branch **computed facts only** + `source_status`, month command, wuxing vector; DMS/Yong-Shen fields with `source_status` + `confidence`, never fabricated values | `match/individual.py` | AC-005a, AC-005b, AC-005c | `tests/test_match_individual_analysis.py` | T2 |
| T4 | Pair layers: EXACTLY `day_master_comparison`, `spouse_palace_day_branch`, `wuxing_vector_comparison`; facts/rule-applications/source-status only; NO numeric points; NO matrix layers; NO `MISSING_INTERACTION_TABLE` stubs | `match/pair.py` | AC-006a, AC-006b, AC-006c, AC-006d | `tests/test_match_pair_layers.py` | T3 |
| T5 | Raw text blocks: deterministic, layer-scoped, source-linked blocks `{id, layer, statement_type, subject, text, source_status, evidence_ids}`; lexical blocked-language guard (perfect match / marriage guarantee / breakup prediction / fate certainty / score language) applied to every emitted string | `match/textblocks.py` | AC-008a, AC-008c, AC-007e, AC-006d | `tests/test_match_raw_blocks.py`; guard cases in `tests/test_match_score_absence.py::test_lexical_guard` | T4 |
| T6 | Evidence ledger: exactly one entry per emitted block AND per warning; entry links `evidence_ids`; no score contributions exist (D1) | `match/evidence.py` | AC-013a | `tests/test_match_observability.py::test_evidence_ledger_complete` | T5 |
| T7 | Determinism: `match/canonical.py` order-independent canonical hash; frozen fixture pair + snapshot of the full engine output (pre-HTTP) | `match/canonical.py`, `tests/fixtures/` addition | AC-014a, AC-014b | `tests/test_match_determinism.py` | T5, T6 |

Done-criteria (each task): named test file passes; `pytest -q tests/test_match_*.py`
green so far; `ruff check bazi_engine/match/`; `mypy bazi_engine --ignore-missing-imports`;
`pytest -q tests/test_import_hierarchy.py` green (no Level-5 imports from `match/`).

### Milestone B (= Iteration 2): Router, contract behavior, privacy, observability (Level 5)

| ID | Goal | Files | AC-IDs | Test-first | Depends on |
|---|---|---|---|---|---|
| T8 | Request/response Pydantic models in the router module: `MatchRequest` (mode Literal, `person_a/b: BaziRequest` reused, REQUIRED `options.second_person_consent_confirmed`, `persist_raw=False`, `extra="forbid"` on request+options), `MatchResponse` (§4.3 incl. `MatchQualityFlags`), consent field `description` = neutral copy (no legal-review implication — AC-012d) | `bazi_engine/routers/match.py` (models only) | AC-002a, AC-002b, AC-002c, AC-012b, AC-012d, AC-007a/b/c (schema side) | `tests/test_match_schema.py` (direct model validation — no HTTP needed) | T1 |
| T9 | Endpoint + /v1-only mount: handler builds `BaziInput` per person exactly like `routers/bazi.py:349-371`, calls `compute_bazi()` ×2, shapes pillars via imported `format_pillar`, invokes match engine, assembles `MatchResponse` with `build_provenance()`, `quality_flags.ephemeris_mode`, per-person `PrecisionBlock`, `request_id` from `request.state`; rate limit via `@limiter.limit(tier_limit)`; `app.py`: import + `app.include_router(match.router, prefix="/v1", dependencies=_protected)` next to admin mount with DECISION-001 comment — NO legacy mount | `routers/match.py`, `bazi_engine/app.py` (mount only) | AC-001a (runtime), AC-001c, AC-003a, AC-003b, AC-003c, AC-003d, AC-005a (endpoint), planning note b | `tests/test_match_contract.py::test_route_exists_v1_only`, `tests/test_match_service_boundary.py` (incl. deep-equal pillar parity vs `/v1/calculate/bazi`; `tests/test_golden.py` unchanged as regression anchor) | T4–T8 |
| T10 | Error contract: 422 ErrorEnvelope for consent false/absent (custom validator), malformed payloads, `mode=raw_bazi`, unknown/deferred options; 502/503 mapping for `EphemerisUnavailableError`/compute failure; stable ErrorEnvelope for non-existent `/v1/match/*` paths; NO raw birth data or API keys in any error body | `routers/match.py` | AC-012c, AC-009a, AC-009b, AC-009c, AC-009d, AC-001b | `tests/test_match_errors.py`; consent-422 case also in `tests/test_match_privacy.py` | T9 |
| T11 | Privacy logging: `match/privacy.py` helper — sha256 hash-log of consent value with `request_id` (no PII); handler logs NOTHING containing date/tz/lon/lat/person payload (caplog-scanned); `persist_raw=false` honored (no persistence path exists; field echoed only as accepted option) | `match/privacy.py`, `routers/match.py` | AC-012a, AC-012f, AC-012b (runtime) | `tests/test_match_privacy.py` (caplog full-record scan for all request field values) | T10 |
| T12 | Observability: `match/observability.py` — structured latency log line (`match.request_ms`), team-vs-external classification from `request.state.key_info` (tier) + `FUFIRE_TEAM_KEY_ALLOWLIST` env (comma-separated keys; outside list ⇒ external); emits counts + key-tier ONLY (no PII, no key echo — reuse `KeyInfo.__repr__` last-4 discipline); request-id in every log line | `match/observability.py`, `routers/match.py` | AC-013b, AC-013c, AC-013d, AC-015b | `tests/test_match_observability.py` (EV-007 mechanism test) | T9 |
| T13 | Performance purity: assert computation is pure/in-memory after the two charts (no network/disk in `match/*` — monkeypatch-guard test); document AC-015c (live p95) as deferred to T22 | `tests/test_match_perf.py` only (no prod code expected) | AC-015a, AC-015b (assert), AC-015c (deferral note) | `tests/test_match_perf.py` | T12 |

Done-criteria: all `tests/test_match_*.py` so far green; `pytest -q` full suite green
(regression: golden, snapshot-stability, import-hierarchy, b2b audit); ruff + mypy green;
`plumbline-scope-check` passes (only allowed paths touched — app.py diff is import + one
mount line + comment).

### Milestone C (= Iteration 3): Contract export + score absence + backend gate

| ID | Goal | Files | AC-IDs | Test-first | Depends on |
|---|---|---|---|---|---|
| T14 | Score-absence proof (EV-004): recursive key-absence scan of the exported response schema AND a live response (`total_score`, `sub_scores`, `score_class`, `awarded_points`, `score_confidence`); no numeric compatibility value incl. PROPOSED_HEURISTIC (contract + lexical scan); `source_completeness_confidence` — if emitted — documented as source-status metadata | `tests/test_match_score_absence.py` (tests only) | AC-007a, AC-007b, AC-007c, AC-007d, AC-007e | this task IS the test suite (must pass against T8–T13 output with zero prod-code change; any needed change is a defect fix) | T9 |
| T15 | OpenAPI regeneration + tag + example: run `python scripts/export_openapi.py`; assert `POST /v1/match/bazi-hehun` present with `Hehun` tag (router-level `tags=["Hehun"]` — no app.py tag-metadata edit needed), request example valid with NO invented computed values, NO `CanonicalBaziChartInput` component, no LLM-readiness wording in any description | `spec/openapi/openapi.json` (regenerated), `routers/match.py` (docstring/example polish only) | AC-001a (spec), AC-002d, AC-008b, AC-010a, AC-010c, AC-010d | `tests/test_match_contract.py::test_openapi_*`; existing `tests/test_openapi_contract.py`; `python scripts/export_openapi.py --check` | T10, T14 |
| T16 | Backend increment gate (Gate A input): full suite + lint + type + drift + scope | — (no new files) | rollup of all backend ACs | commands below | T1–T15 |

T16 commands (all must pass):
```bash
pytest -q --cov=bazi_engine --cov-fail-under=75
ruff check bazi_engine/ --output-format=github
mypy bazi_engine --ignore-missing-imports
python scripts/export_openapi.py --check
# plumbline-scope-check against docs/canvas/bazi-hehun.canvas.md allowed paths
```

### Milestone D (= Iteration 4): Frontend (repo: `/Users/benjaminpoersch/Projects/SaaS/FuFirEProject/Fufire_API-landingpage`)

| ID | Goal | Files (repo-relative) | AC-IDs | Test-first | Depends on |
|---|---|---|---|---|---|
| T17 | Snapshot sync: copy backend `spec/openapi/openapi.json` → `src/api/openapi.json` + `public/openapi.json`; authority invariant green | `src/api/openapi.json`, `public/openapi.json` | AC-010b, AC-011a | `npm run test:authority` (`scripts/verify-openapi-authority.mjs`); new unit assert: match path present in loaded spec | T15 |
| T18 | Feature-flag mechanism (NEW — none exists): `src/lib/feature-flags.ts` with `isHehunVisible()` reading `VITE_FEATURE_HEHUN`; default OFF (unset ⇒ false); catalog gating in `buildEndpointCatalog` (flag OFF ⇒ Hehun-tagged operations excluded). Flip itself is OUT of scope (user-gated launch act) | `src/lib/feature-flags.ts` (new), `src/lib/endpoint-catalog.ts` | AC-011g, AC-011h | vitest: `tests/unit/feature-flags.test.ts` + `endpoint-catalog.test.ts` (flag OFF ⇒ no Hehun ops; ON ⇒ present) | T17 |
| T19 | Category + honest framing: `TAG_TO_CATEGORY["Hehun"] = "Hehun"` (`endpoint-catalog.ts:42-58`), category union += `"Hehun"` (`src/types.ts:24-39` — scope note §8), NEW `CATEGORY_SUBTITLE` map with `Hehun: "Deterministic pair-chart facts — no compatibility score"` (DE equivalent allowed alongside), rendered where category renders (`EndpointTesterShowcase.tsx` ~:646); lexical copy test: no visible copy promises marriage matching or scoring | `src/lib/endpoint-catalog.ts`, `src/types.ts`, `src/components/EndpointTesterShowcase.tsx` | AC-001d, AC-011b, AC-011f | vitest: catalog test (label `BaZi Hehun`, category `Hehun`, not "Raw Data"); subtitle render test; copy lexical scan | T17, T18 |
| T20 | Consent UI + tester flow evidence: prove SchemaForm renders nested `person_a`/`person_b`/`options` incl. required consent checkbox (generic path — `SchemaForm.tsx:129-178`); ajv blocks Send without consent; proxy allows POST `/v1/match/bazi-hehun` (path+method in loaded spec) and rejects unknown `/v1/match/*`; send a valid sample request (integration test against mock/live backend) | `tests/unit/form-spec.test.ts` + `form-validate.test.ts` extensions, `tests/integration/api-proxy-match.test.ts` (new), consent hint in `src/components/**` only if the generic render is insufficient | AC-011c, AC-011d, AC-011e | vitest unit + integration (fail first against pre-sync spec) | T17 |
| T21 | Frontend increment gate: full vitest run + build + record changed-files list (procedural scope enforcement) | — | rollup AC-010b, AC-011a-h | `npm run test && npm run test:authority && npm run build`; changed-files list appended to increment report | T17–T20 |

### Milestone E (= Iteration 5): Real-boundary validation — **REQUIRES DEPLOYMENT** (MISSING-005)

| ID | Goal | Files | AC-IDs | Test-first | Depends on |
|---|---|---|---|---|---|
| T22 | Deployed-backend smoke (final validation milestone; runs only after user-gated merge/deploy of the backend — Railway auto-deploys `main`): against the REAL URL with a REAL API key: (1) happy path 200 with 3 pair layers + `quality_flags.ephemeris_mode`; (2) consent-absent → 422 ErrorEnvelope; (3) recursive score-key absence on the live response; (4) Railway runtime logs show latency metric + hash-logged consent + request-id and NO raw birth data; (5) record full-request p95 baseline → revise REQ-015 target (AC-015c); frontend `/api/v1/proxy` round-trip with flag ON in a non-prod env only | smoke script under `docs/**` or scratch (no prod code); results recorded in `docs/traceability.md` evidence column | AC-015c, EV-001/002/005 runtime legs, AC-012a (runtime), MISSING-005 | live checklist derived from `docs/testing/bazi-hehun.acceptance-tests.md` smoke section | T16, T21 + deployment (user gate) |

Per Development Principles: T22 is the only thing that turns "tests green" into
"the deployed artifact works" — no Done claim before it.

---

## 6. Iteration plan (user-visible counter)

**M = 5 planned iterations.** This is the honest total derived from the breakdown; it
may only change VISIBLY (announced counter change), never silently.

| Iteration | Content | Tasks | Exit gate |
|---|---|---|---|
| 1/5 | Pure match engine (Level 4) | T1–T7 | engine tests + hierarchy + lint/type green; scope-check |
| 2/5 | Router + contract behavior + privacy + observability | T8–T13 | full backend suite green; scope-check (app.py = mount only) |
| 3/5 | Score-absence proof + OpenAPI export + backend gate | T14–T16 | T16 command block green |
| 4/5 | Frontend: sync, flag (default OFF), category/subtitle, consent/tester | T17–T21 | vitest + authority + build green; changed-files list recorded |
| 5/5 | Real-boundary smoke (deployed) — MISSING-005 | T22 | live evidence recorded in traceability matrix |

Parallelization notes: within Iteration 1, T3/T4 partially parallel after T2; within
Iteration 2, T11/T12/T13 parallel after T10. Iteration 4 T18/T19 can start once the tag
name is frozen (after T15), T17 first. Iteration 5 is strictly serial after a user-gated
deploy.

**Critical path:** T1 → T2 → T3 → T4 → T5 → T6/T7 → T8/T9 → T10 → T15 → T16 → T17 →
T19/T20 → T21 → (user deploy gate) → T22.

---

## 7. Risks and rollback

| Risk | Impact | Mitigation / rollback |
|---|---|---|
| Reuse-vs-hierarchy seam done wrong (match/ imports routers/shared) | import-hierarchy test fails late; rework | Decision fixed in §4.2 (composition at router); T1 done-criteria runs `test_import_hierarchy.py` from the first task |
| `BaziRequest` reuse drags `include_trace` into the match contract | contract noise | accepted + documented (ignored field); alternative (mirrored model) rejected — would copy, violating planning note c |
| MatchQualityFlags vs shared QualityFlags debate reopens in review | churn | decided in §4.3 with rationale (house_system fields are western-only); parity = field name + value domain, per audit F8 |
| Score language creeps in via text templates | D1 violation, RISK-001 | T5 guard is applied to EVERY emitted string; T14 re-proves at contract level; both run in CI |
| Frontend scope fence: `src/types.ts` + `EndpointTesterShowcase.tsx` not literally listed in canvas allowed paths | procedural scope flag | see §8 — user-sanctioned by the binding build constraints ("TAG_TO_CATEGORY entry + category union", subtitle rendering); record both files in the changed-files list per increment; if challenged, only these two files are affected — trivially revertible |
| Flag is build-time (VITE_*) → flip requires redeploy | launch friction | acceptable and documented as the CAN-015 flip mechanism; runtime server-driven flag rejected as new infrastructure outside approved scope |
| Consent copy wording (OQ-001 open) | launch gate, not build gate | neutral copy in T8 field description (no legal-review implication — AC-012d); final wording is a post-build, pre-flip user decision |
| Ephemeris MOSEPH fallback on the deployed box diverges from local | determinism claims dishonest | `quality_flags.ephemeris_mode` attests per response (F8); T22 checks the live value |
| OpenAPI drift between backend export and frontend snapshots | proxy 404s in tester | T15 `--check` in CI + T17 authority invariant; rollback = re-run export + re-sync |
| Deferred-capability requests (raw_bazi, scoring options) reach prod | contract confusion | `extra="forbid"` + mode Literal → 422 with stable ErrorEnvelope (T10); `ruleset_incomplete` stays a RESERVED error code (documented, unused in MVP) per AC-009b |
| Backend endpoint reachable pre-flip | by design (CAN-015) | not a defect: API-reachable-not-advertised is the approved launch boundary |

Rollback: backend is a single new router + subpackage + one mount line — revert =
`git revert` of the increment commits; no migrations, no persisted state
(`persist_raw=false`, nothing stored). Frontend rollback = revert catalog/flag/snapshot
commits; flag default OFF means even a bad merge is invisible in production.

## 8. Explicit scope notes (procedural fence, frontend)

The canvas frontend allowlist names `src/lib/endpoint-catalog.ts`, consent-UI component
under `src/components/**`, feature-flag file(s), snapshots, frontend tests. Two
additional touches are REQUIRED by the binding build constraints and are declared here
up front rather than discovered mid-build:

1. `src/types.ts` — the category union (`EndpointOperation["category"]`,
   `src/types.ts:24-39`) must gain `"Hehun"`; the user's constraint text explicitly
   mandates "TAG_TO_CATEGORY entry + category union".
2. `src/components/EndpointTesterShowcase.tsx` — subtitle rendering (AC-011f) happens
   where the category renders (~line 646); covered by the "consent-UI component under
   `src/components/**` (new or extended)" clause read as UI-extension permission.

Both files go into the per-increment changed-files list (the procedural enforcement
mechanism named in the canvas). If the scope guard disputes item 2, fallback: render the
subtitle from a new component under `src/components/` imported at that call site.

## 9. Open items carried into build (unchanged status)

- MISSING-001..003 — gate deferred matrices only; zero matrix work in this plan.
- MISSING-004 / OQ-001 — gates flag flip (public launch), not this build (CAN-015).
- MISSING-005 — closed only by T22.
- OQ-003 — no build impact.
- ASSUMPTION-003 / EV-007 — demand evidence is post-launch; this build ships ONLY the
  measurement mechanism (T12, AC-013d).
- Flag flip = PUBLIC LAUNCH = later, user-gated act (OQ-001 + explicit sign-off) —
  explicitly NOT a task in this plan.
