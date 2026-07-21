# Acceptance / E2E Test Contract — `bazi-hehun`

Status: QA-derived, black-box, BINDING for the coder
Feature Slug: `bazi-hehun`
Derived: 2026-07-02, Phase 1 QA setup, independently from the frozen spec (commit fabe6bf)
Author: tester (QA agent) — no implementation plans were read; no production code written
Spec sources (frozen): `docs/prd/bazi-hehun.prd.md`, `docs/canvas/bazi-hehun.canvas.md`,
`docs/vision/bazi-hehun.vision.md`, `docs/traceability.md`,
`docs/audits/2026-07-02-bazi-hehun-spec-audit.md`,
`docs/governance/bazi-hehun.missing-assumption-blocker-ledger.md`

---

## 0. Contract conventions (binding)

### 0.1 Evidence classes

| Class | Meaning |
|---|---|
| `unit-fake` | Pure in-process function test; no app assembly. |
| `integration-fake` | FastAPI `TestClient` against the ASSEMBLED production app (`from bazi_engine.app import app`) — the real composition path, fake network. This is the default class for this feature. |
| `real-boundary-smoke` | Deployed backend (Railway) / deployed landingpage with real env + real API keys. NOT automatable in this repo pre-deploy — tracked in §3 and MISSING-005. |

Rule (Reality Ledger): every test below that claims contract coverage MUST run against
the assembled app (`bazi_engine.app.app`), never against a hand-built router or a
hand-instantiated Pydantic model, except where explicitly marked `unit-fake`.
A REQ whose only green evidence is `unit-fake`/`integration-fake` but whose AC touches
the deployed system (see §4 ceilings) is NOT done until the §3 real-boundary item closes.

### 0.2 Canonical fixtures (binding names)

```python
# tests/fixtures/match_payloads.py  (new; shared by all test_match_*.py)

SENTINEL_A = {"date": "1988-06-04T07:31:00", "tz": "Pacific/Chatham",
              "lon": 173.9391, "lat": -43.9502}
SENTINEL_B = {"date": "1979-11-23T22:04:00", "tz": "America/Caracas",
              "lon": -66.9036, "lat": 10.4806}

VALID_MATCH_REQUEST = {
    "mode": "birth_input",
    "person_a": SENTINEL_A,
    "person_b": SENTINEL_B,
    # consent boolean: REQUIRED per REQ-012/AC-012c. Its exact schema location
    # (top-level vs options) is the coder's choice, but the location MUST be pinned
    # in this fixture once chosen and every ancestor on its path MUST be `required`
    # in the OpenAPI schema so that omission always yields 422 (see T-012-01/02).
    "second_person_consent_confirmed": True,
}
```

The sentinel values are deliberately distinctive (Chatham/Caracas, odd minutes,
4-decimal coords) so that log-scan and echo tests (T-012-*, T-009-04) are lexically
falsifiable: if any of these strings appears in logs or error bodies, the test fails.

### 0.3 Idiom (match existing suite)

- Ephemeris: conftest defaults `EPHEMERIS_MODE=MOSEPH` when SE1 files are absent.
  Tests that pin SWIEPH-specific values use `@pytest.mark.swieph`. Snapshot fixtures
  are keyed per mode (`tests/snapshots/moseph/`, `tests/snapshots/swieph/`) exactly as
  `test_snapshot_stability.py` does. Determinism tests (T-014-*) assert stability
  WITHIN a mode, never equality ACROSS modes.
- Error shape: `ErrorEnvelope` per `spec/schemas/ErrorEnvelope.schema.json` —
  required fields `{error, message, request_id}` (see `tests/test_error_envelope_schema.py`).
- OpenAPI: read via `app.openapi_schema = None; spec = app.openapi()` (idiom of
  `tests/test_openapi_contract.py`); drift via `python scripts/export_openapi.py --check`.
- Logging: `caplog.at_level(logging.DEBUG)` on the ROOT logger for redaction scans, so
  no logger namespace can smuggle PII past the assertion.

### 0.4 Blocked-language lexicon (AC-007e / AC-011f — binding list)

Spec-mandated (EN, case-insensitive, substring over every string value in the
response): `perfect match`, `marriage guarantee`, `breakup prediction`,
`fate certainty`. QA-added hardening (same scan, DE equivalents — additions, not spec
reinterpretation): `perfekte übereinstimmung`, `ehegarantie`, `trennungsvorhersage`,
`schicksals`. Forbidden score keys (AC-007a–d, exact key match, recursive):
`total_score`, `sub_scores`, `score_class`, `awarded_points`, `score_confidence`.

---

## 1. Per-REQ contract (Glättung beats + test specs)

Format per REQ — Beat 0: boundary|pure. Beat 1 These. Beat 2 Gegenthese. Beat 3
Schärfung. Then the binding tests. All tests live in the file the traceability matrix
assigns.

---

### REQ-001 — Canonical /v1 route with Hehun labeling

- **Beat 0:** boundary (route mounted into the assembled app; cross-repo label).
- **These:** "The route exists at POST /v1/match/bazi-hehun."
- **Gegenthese:** router file exists and unit tests pass against it, but it is never
  mounted in `app.py` (dead code) — or it is dual-mounted per the repo idiom, silently
  violating DECISION-001, and the legacy path leaks an unauthenticated surface.
- **Schärfung:** hit the ASSEMBLED app at both paths — /v1 must answer, legacy must 404
  with a stable envelope (T-001-01 + T-001-03).

**File: `tests/test_match_contract.py`**

| ID | Test function | Given / When / Then | ACs | Class |
|---|---|---|---|---|
| T-001-01 | `test_v1_match_route_exists_and_answers` | Given the assembled app; When POST `/v1/match/bazi-hehun` with `VALID_MATCH_REQUEST`; Then status 200 and a JSON body (not 404/405). | AC-001a | integration-fake |
| T-001-02 | `test_openapi_contains_match_path_with_schemas` | Given `app.openapi()`; Then `paths["/v1/match/bazi-hehun"]["post"]` exists with a requestBody schema ref AND a 200 response schema ref (both resolvable in `components.schemas`). | AC-001a, EV-001 | integration-fake |
| T-001-03 | `test_legacy_unversioned_match_route_is_404_error_envelope` | Given the assembled app; When POST `/match/bazi-hehun` (valid payload); Then status 404 AND body validates against `spec/schemas/ErrorEnvelope.schema.json` (has `error`, `message`, `request_id`). DECISION-001 negative test — kills chain D. | AC-001c | integration-fake |
| T-001-04 | `test_nonexistent_v1_match_paths_return_stable_envelope` | When GET and POST `/v1/match/does-not-exist`; Then 404 (or 405), body is the stable ErrorEnvelope shape, never a raw traceback/HTML. | AC-001b | integration-fake |
| T-001-05 | `test_match_operation_tag_is_hehun_mapping_key` | Given `app.openapi()`; Then the match operation's `tags` contains EXACTLY the tag string the frontend `TAG_TO_CATEGORY` maps to category `Hehun` (pin the literal, e.g. `"Hehun"`). This is the backend half of the cross-repo pin that kills chain B; the frontend half is FE-CAT-01/02. | AC-001d, AC-010c | integration-fake |

Note: AC-001d's visible label/category is a frontend fact — backend can only pin the
tag. Frontend tests FE-CAT-01/02 (§2) complete AC-001d.

---

### REQ-002 — birth_input-only input mode (raw_bazi deferred)

- **Beat 0:** boundary (published schema + endpoint validation behavior).
- **These:** "Only birth_input is accepted; raw mode is deferred."
- **Gegenthese:** the endpoint silently IGNORES an unknown `mode` value or extra raw
  chart payloads and computes anyway — green happy-path tests, but the deferred mode is
  de-facto shipped without a schema version, freezing an unversioned contract (RISK-003).
- **Schärfung:** send `mode=raw_bazi` and raw-chart-shaped payloads to the assembled
  endpoint and demand a 422 ErrorEnvelope, plus prove `CanonicalBaziChartInput` is
  absent from the published components (T-002-02/03/05).

**File: `tests/test_match_schema.py`**

| ID | Test function | Given / When / Then | ACs | Class |
|---|---|---|---|---|
| T-002-01 | `test_birth_input_requires_both_persons_with_core_fields` | For each of: missing `person_a`, missing `person_b`, and each of `date/tz/lon/lat` removed from `person_a`; When POST; Then 422 with per-field detail locating the missing field. | AC-002a, AC-002c | integration-fake |
| T-002-02 | `test_mode_raw_bazi_rejected_422` | Given `VALID_MATCH_REQUEST` with `"mode": "raw_bazi"`; When POST; Then 422, body is ErrorEnvelope-shaped, and the detail names the mode/validation error — NOT 200, NOT 500. | AC-002b, AC-009b | integration-fake |
| T-002-03 | `test_raw_chart_payload_rejected_422` | Given a request whose `person_a` is replaced by a chart-shaped object (e.g. `{"pillars": {...}, "day_master": "..."}`) instead of birth fields; When POST; Then 422 validation_error, not a computed response. | AC-002b | integration-fake |
| T-002-04 | `test_invalid_mode_and_malformed_payload_422_with_detail` | `mode="banana"`, empty body `{}`, and non-JSON body; each yields 422 (or 400 for non-JSON) with stable envelope + per-field detail; never 500. | AC-002c, AC-009a | integration-fake |
| T-002-05 | `test_no_canonical_bazi_chart_input_schema_published` | Given `app.openapi()`; Then no key in `components.schemas` equals or contains `CanonicalBaziChartInput`, and the match request schema's `mode` (if an enum) contains ONLY `birth_input`. | AC-002d | integration-fake |

---

### REQ-003 — Reuse of BaZi calculation through internal service boundary

- **Beat 0:** boundary (wiring across components; regression surface on an existing
  production endpoint).
- **These:** "Hehun reuses the existing chart computation; /v1/calculate/bazi unchanged."
- **Gegenthese:** the coder COPIES `compute_bazi` + the router-embedded response-shaping
  helpers into `bazi_engine/match/`; all Hehun tests are green, `/v1/calculate/bazi` is
  untouched — but the two normalizations drift on the first future fix, and AC-003c is
  satisfied only by coincidence today (exactly the residual named at ASSUMPTION-001).
- **Schärfung:** same-person equivalence THROUGH the two assembled endpoints
  (T-003-02) plus a structural no-duplication check (T-003-03); the existing golden
  suite pins AC-003a.

**File: `tests/test_match_service_boundary.py`** (+ existing `tests/test_golden.py`
runs UNCHANGED as the AC-003a regression anchor — the coder MUST NOT edit it)

| ID | Test function | Given / When / Then | ACs | Class |
|---|---|---|---|---|
| T-003-01 | `test_existing_calculate_bazi_behavior_unchanged` | Assert `tests/test_golden.py` is byte-identical to its state on `main` at branch point (git diff check), and POST `/v1/calculate/bazi` with `SENTINEL_A` returns 200 with the pre-feature response keys (snapshot from `main`). | AC-003a | integration-fake |
| T-003-02 | `test_same_person_chart_parity_with_calculate_bazi` | Given `SENTINEL_A`; When POST `/v1/calculate/bazi` AND POST the match endpoint with person_a=person_b=`SENTINEL_A`; Then the four pillars (stem+branch per Year/Month/Day/Hour), the day_master, and the Wu-Xing vector visible in `individual.person_a` are EQUAL (field-by-field) to the single-chart response's normalization of the same facts. Same process, same EPHEMERIS_MODE. | AC-003c | integration-fake |
| T-003-03 | `test_match_package_does_not_duplicate_core_computation` | Static check: `bazi_engine/match/**` contains no function named `compute_bazi`/`find_crossing` and no copied jieqi/day-offset tables; it must IMPORT from `bazi_engine.bazi` (and shared shaping helpers). Grep-based, precise allowlist of imports. | AC-003b | unit-fake (static) |
| T-003-04 | `test_no_cross_request_state_between_match_calls` | Two sequential match calls with different persons; Then response for call 2 contains no field derived from call 1's persons (assert absence of call-1 sentinels), and repeating call 1 afterwards is byte-identical to its first run (no session/user cache semantics). | AC-003d | integration-fake |

---

### REQ-004 — Normalization with provenance and warnings

- **Beat 0:** boundary (normalized structures + attestation must SURFACE in the
  assembled response; inner math is pure but that is not what the AC claims).
- **These:** "Charts are normalized into canonical structures with provenance and warnings."
- **Gegenthese:** normalization objects exist internally and unit tests on them pass,
  but the response omits provenance/warnings — or (chain E / audit F8) the match
  response lacks the `quality_flags.ephemeris_mode` attestation single-chart responses
  carry, so a MOSEPH-computed match masquerades as environment-identical to SWIEPH.
- **Schärfung:** ephemeris-mode PARITY through the assembled path: match response's
  `quality_flags.ephemeris_mode` must exist and equal the single-chart response's value
  in the same process (T-004-04).

**File: `tests/test_match_normalization.py`**

| ID | Test function | Given / When / Then | ACs | Class |
|---|---|---|---|---|
| T-004-01 | `test_day_master_is_day_stem_only` | Given a valid match response; Then for each person, `day_master` equals that person's day-pillar heavenly stem; any month/hour "master" values appear only as provenance labels, never as `day_master`. | AC-004a | integration-fake |
| T-004-02 | `test_wuxing_ledger_includes_visible_and_hidden_stems_with_source_and_weight` | Then each person's Wu-Xing ledger entries carry a source marker distinguishing visible vs hidden stems AND a numeric weight; both kinds are present for a chart known to have hidden stems. | AC-004b | integration-fake |
| T-004-03 | `test_unverified_anchor_and_unknown_birth_time_produce_warnings` | Given the shipped ruleset (`anchor_verification: "unverified"`) and a request with `birth_time_known=false` (or the schema's equivalent); Then the response `warnings` contain a day-cycle-anchor warning code AND a birth-time-unknown warning code (stable codes, not prose-matched). | AC-004c | integration-fake |
| T-004-04 | `test_match_response_carries_ephemeris_mode_attestation_parity` | Given the same process; When POST `/v1/calculate/bazi` and the match endpoint; Then match body has `quality_flags.ephemeris_mode` ∈ {"SWIEPH","MOSEPH"} AND it EQUALS the single-chart response's `quality_flags`/metadata ephemeris mode. Kills chain E (audit F8). | AC-004a-context, planning note (b), REQ-014 env-honesty | integration-fake |

---

### REQ-005 — Individual chart analysis first

- **Beat 0:** boundary (response contract for `individual.*`; F7 honesty lives here).
- **These:** "Each person gets an individual analysis with source statuses."
- **Gegenthese:** `individual.person_a/b` are populated and green, but DMS/Yong-Shen
  or spouse-palace fields carry confident-sounding values WITHOUT `source_status` /
  with implied tradition verification — audit F7: interpretive claims masquerading as
  source-verified facts, precisely what AC-005c forbids.
- **Schärfung:** walk every DMS/Yong-Shen/spouse-star field and demand
  `source_status ∈ {MISSING, NEEDS_DOMAIN_REVIEW}` while MISSING-001..003 are open
  (T-005-02/03) — a test that FAILS the moment someone "helpfully" fills them.

**File: `tests/test_match_individual_analysis.py`**

| ID | Test function | Given / When / Then | ACs | Class |
|---|---|---|---|---|
| T-005-01 | `test_response_contains_individual_person_a_and_b` | Valid request; Then body has `individual.person_a` and `individual.person_b`, each with Day Master, spouse-palace/day-branch facts, month command, Wu-Xing vector, source status, warnings. | AC-005a | integration-fake |
| T-005-02 | `test_dms_yongshen_fields_carry_source_status_and_confidence` | Then every DMS/Yong-Shen field present has BOTH a `source_status` and a confidence marker; while MISSING-003 is open the status MUST be `MISSING` or `NEEDS_DOMAIN_REVIEW` — never a verified-looking status. | AC-005b, AC-005c | integration-fake |
| T-005-03 | `test_spouse_palace_layer_is_computed_facts_only` | Then spouse-palace content is limited to computed identification facts (which branch/pillar) + `source_status`; assert `statement_type` of any spouse-palace text block is a factual type (not interpretation) and its text contains no relationship-quality adjectives (reuse the §0.4 lexicon + QA list: `harmonious`, `unstable`, `loyal`, `unfaithful`). Audit F7 guard. | AC-005c | integration-fake |

---

### REQ-006 — Exactly the three MVP pair layers

- **Beat 0:** boundary (response + schema shape of the pair section).
- **These:** "The pair section has the three source-verified layers."
- **Gegenthese:** the three layers exist AND, alongside them, helpful
  `MISSING_INTERACTION_TABLE` stub layers for the five deferred matrices — green on
  "three layers present", but the contract now CONTAINS the deferred layers as stubs,
  freezing them into the released schema (exactly what D3 rejected).
- **Schärfung:** EXHAUSTIVE layer enumeration: the pair section's key set is EXACTLY
  the three layer names, and a recursive scan proves `MISSING_INTERACTION_TABLE`
  appears nowhere in any response (T-006-01/03).

**File: `tests/test_match_pair_layers.py`**

| ID | Test function | Given / When / Then | ACs | Class |
|---|---|---|---|---|
| T-006-01 | `test_pair_section_contains_exactly_three_mvp_layers` | Valid response; Then the pair section's layer key set == {`day_master_comparison`, `spouse_palace_day_branch`, `wuxing_vector_comparison`} — no more, no fewer — and each is non-empty/fully populated. | AC-006a | integration-fake |
| T-006-02 | `test_no_matrix_layers_in_schema` | Given `app.openapi()` match response schema, recursively collected property names; Then none matches (case-insensitive substring) `branch_matrix`, `stem_matrix`, `ten_gods`, `shen_sha`/`shensha`. | AC-006b | integration-fake |
| T-006-03 | `test_no_missing_interaction_table_stub_anywhere` | Recursive scan of the full response JSON (keys AND string values); Then the token `MISSING_INTERACTION_TABLE` appears nowhere. | AC-006c | integration-fake |
| T-006-04 | `test_pair_text_is_factual_and_pointless` | Every pair-layer text block's `statement_type` is within the factual set (calculated fact / rule application / source-status / warning), and NO numeric value anywhere in the pair section is named like a point/score (recursive key scan: `*_points`, `*_score*`). | AC-006d | integration-fake |

---

### REQ-007 — Score fields ABSENT from the contract

- **Beat 0:** boundary (published schema + every emitted response).
- **These:** "There is no score in the MVP."
- **Gegenthese:** the response body has no `total_score` — but a nested component
  schema (or an OpenAPI example, or a docstring) still defines/mentions one, so the
  frozen published contract ADVERTISES scoring, and the false-authority risk
  (RISK-001) ships in documentation even though runtime never emits it.
- **Schärfung:** recursive scan of the ENTIRE reachable schema graph from the match
  path — properties, examples, descriptions — plus deep response-key scan and the
  lexical guard (T-007-01/02/03). Kills chain C permanently.

**File: `tests/test_match_score_absence.py`**

| ID | Test function | Given / When / Then | ACs | Class |
|---|---|---|---|---|
| T-007-01 | `test_schema_graph_contains_no_score_fields` | Given `app.openapi()`; resolve ALL schemas transitively reachable from `/v1/match/bazi-hehun` (request+responses, through `$ref`); Then no property name, no `required` entry, no enum value, no example key equals any of the five forbidden keys (§0.4). | AC-007a, AC-007b, AC-007c, EV-004 | integration-fake |
| T-007-02 | `test_response_contains_no_score_keys_recursively` | Valid response; deep-walk every dict key at every depth; Then none of the five forbidden keys occurs. Run against ≥3 distinct person pairs (incl. same-person) so absence is not pair-specific. | AC-007a, AC-007b, AC-007d | integration-fake |
| T-007-03 | `test_no_numeric_compatibility_value_or_blocked_language` | Deep-walk every string value in the response; Then no §0.4 blocked-language phrase occurs (case-insensitive), and no text block contains a pattern like `\b\d{1,3}\s*(%|/\s*100|points?)\b` presented as compatibility; no value labeled `PROPOSED_HEURISTIC` exists anywhere. | AC-007d, AC-007e, AC-008c | integration-fake |
| T-007-04 | `test_source_completeness_confidence_if_present_is_documented_metadata` | If any field named `source_completeness_confidence` exists in schema or response, its schema `description` MUST state it is source-status metadata and MUST NOT contain the words `compatibility` or `score` as a claim; absent field ⇒ pass. | AC-007c | integration-fake |

---

### REQ-008 — Structured raw_analysis_text blocks

- **Beat 0:** boundary (response-text contract; documentation claims).
- **These:** "Text blocks follow the AC-008a schema."
- **Gegenthese:** blocks carry the seven fields, but `evidence_ids` are empty/dangling
  (pointing at no ledger entry) and a docstring/OpenAPI description advertises
  "LLM-ready" output — the block contract is nominally green while its evidence links
  are decorative and D4's struck claim sneaks back in via docs.
- **Schärfung:** referential integrity — every `evidence_ids` entry MUST resolve to an
  `evidence_ledger` entry (T-008-02, jointly with T-013-01) — and a lexical scan of the
  published schema/descriptions for LLM/Fusion-readiness claims (T-008-03).

**File: `tests/test_match_raw_blocks.py`**

| ID | Test function | Given / When / Then | ACs | Class |
|---|---|---|---|---|
| T-008-01 | `test_every_text_block_has_the_seven_contract_fields` | Valid response; Then EVERY raw-analysis text block has exactly-typed `id`, `layer`, `statement_type`, `subject`, `text`, `source_status`, `evidence_ids` (list); `id` values unique; `layer` ∈ the emitted layer set. | AC-008a | integration-fake |
| T-008-02 | `test_evidence_ids_resolve_to_ledger_entries` | Then every id in every block's `evidence_ids` exists in the response `evidence_ledger`; no dangling refs; no block with an empty `evidence_ids` unless its `statement_type` is a warning/status type. | AC-008a, AC-013a | integration-fake |
| T-008-03 | `test_no_llm_readiness_claim_in_schema_docs_or_examples` | Scan the match operation's OpenAPI `description`s, schema descriptions and examples; Then none contains `LLM`, `interpretation-ready`, `Fusion interpretation` as a readiness claim (D4). | AC-008b | integration-fake |
| T-008-04 | `test_response_contains_warnings_array_and_guard_metadata` | Then the response has a `warnings` array (possibly empty for a clean input, non-empty for T-004-03's input) and blocked-language safeguards hold (delegated assertion: T-007-03 runs on the same body). | AC-008c | integration-fake |

---

### REQ-009 — Error envelope consistency

- **Beat 0:** boundary (assembled exception handlers; PII surface).
- **These:** "Errors use the stable envelope."
- **Gegenthese:** 422s look right, but FastAPI's DEFAULT validation error echoes the
  offending `input` back — so the one place users send a second person's birth data
  WITHOUT consent (the consent-missing 422) is exactly the place the API echoes that
  birth data to the caller and into any upstream log. Green envelope tests, live PII leak.
- **Schärfung:** T-009-04 sends sentinel birth data in an INVALID request and asserts
  the 422 body contains none of the sentinel strings — this fails against FastAPI's
  default handler, forcing the custom input-stripping handler to exist. Kills chain F.

**File: `tests/test_match_errors.py`**

| ID | Test function | Given / When / Then | ACs | Class |
|---|---|---|---|---|
| T-009-01 | `test_malformed_request_422_error_envelope` | Malformed payloads (wrong types, garbage date); Then 422, body validates against ErrorEnvelope schema, `error` field identifies validation, per-field detail present. | AC-009a | integration-fake |
| T-009-02 | `test_deferred_capabilities_rejected_422_stable_detail` | `mode=raw_bazi`, and options requesting scoring/matrix capabilities (e.g. `{"options": {"include_scores": true}}` — any unknown deferred-capability key); Then 422 (or documented strict-rejection), stable envelope, NEVER 500; the error contract reserves `ruleset_incomplete` (assert the code exists in the error-code enum/spec, unused in MVP). | AC-009b | integration-fake |
| T-009-03 | `test_compute_failure_returns_502_or_503_envelope` | Monkeypatch the chart-computation dependency to raise (idiom of `test_error_sanitization.py`'s patch targets); When POST valid request; Then 502/503 (or 500 per repo convention — MUST be ≥500 with ErrorEnvelope), and the internal exception text does NOT appear in the body. | AC-009c | integration-fake |
| T-009-04 | `test_422_never_echoes_birth_data_or_api_keys` | Given a request with sentinels but `second_person_consent_confirmed` absent AND separately a type-invalid `person_b.date`; When POST (with an `Authorization`/api-key header containing a sentinel key string); Then NO sentinel birth value (date strings, tz names, lon/lat as substrings) and NO key material appears anywhere in the 422/4xx body. Proves the custom handler strips FastAPI's default `input` echo. | AC-009d, AC-012a-adjacent | integration-fake |

---

### REQ-010 — OpenAPI contract + snapshot sync

- **Beat 0:** boundary (generated artifact + cross-repo sync).
- **These:** "The contract is exported and synced."
- **Gegenthese:** `app.openapi()` in-process contains the path, but
  `spec/openapi/openapi.json` was never regenerated (drift) — CI's `--check` or the
  frontend sync then ships an OLD snapshot and the landingpage catalog cannot see the
  endpoint even with the flag ON; every backend test stays green.
- **Schärfung:** run the ACTUAL export drift check as a test (T-010-02), and pin the
  committed spec file itself, not the in-memory schema (T-010-01).

**File: `tests/test_match_contract.py`** (same file as REQ-001, per traceability)

| ID | Test function | Given / When / Then | ACs | Class |
|---|---|---|---|---|
| T-010-01 | `test_committed_openapi_json_is_valid_and_contains_match_path` | Load `spec/openapi/openapi.json` from disk; Then it parses as JSON AND contains `paths["/v1/match/bazi-hehun"]`. | AC-010a, EV-001 | integration-fake (artifact) |
| T-010-02 | `test_export_openapi_check_passes` | Run `python scripts/export_openapi.py --check` as subprocess; Then exit 0 (no drift between app and committed spec). | AC-010a | integration-fake (artifact) |
| T-010-03 | `test_match_operation_example_is_valid_and_not_confabulated` | Extract the request example from the committed spec; Then (a) POSTing it to the assembled app returns 200; (b) the example contains ONLY request-schema fields (no response/computed values like pillars, day_master, hashes); (c) it has `second_person_consent_confirmed: true`. | AC-010d | integration-fake |
| — | (tag mapping) | covered by T-001-05. | AC-010c | — |
| — | (frontend snapshots) | FE-SNAP-09 in §2 — CANNOT be automated in this repo. | AC-010b, AC-011a | frontend repo |

---

### REQ-011 — Landingpage visibility, honest framing, feature flag

- **Beat 0:** boundary (UI + production build config in the FRONTEND repo).
- **These:** "The endpoint is visible under Hehun with the honest subtitle, behind a flag."
- **Gegenthese:** ALL backend tests green, endpoint perfect — and the landingpage
  auto-deploys the visibility merge to production with the flag defaulting ON (or no
  flag at all), so PUBLIC LAUNCH happens as a side effect of `git push`, bypassing
  OQ-001 and the user's launch sign-off. This is audit chain A verbatim; the backend
  repo cannot detect it.
- **Schärfung:** FE-FLAG-04 asserts the flag resolves OFF in the PRODUCTION build
  configuration (not a test env default), and FE-FLAG-05 renders the catalog with the
  production flag state and asserts Hehun is ABSENT. Final kill requires the §3
  real-boundary check against the deployed landingpage (pre-launch: Hehun invisible).

Backend-side residue in `tests/test_match_contract.py`: T-001-05 (tag pin). Everything
else for REQ-011 is frontend-repo — specified precisely in §2 (FE-CAT-01/02,
FE-SUB-03, FE-FLAG-04/05/06, FE-FORM-07, FE-PROXY-08, FE-E2E-10). ACs: AC-011a–h.

---

### REQ-012 — Privacy defaults + server-side consent

- **Beat 0:** boundary (logging side effects; validation behavior; the single most
  load-bearing dark zone of this feature).
- **These:** "Consent is enforced server-side; nothing raw is logged."
- **Gegenthese:** the consent check lives in the FRONTEND form only (checkbox
  required), backend green because tests always send `true` — a direct API caller
  bypasses consent entirely (the exact bypass D5 closed on paper); and/or a stray
  `logger.debug("payload=%s", body)` in the new match module logs both birth datasets
  on every call while all functional tests stay green.
- **Schärfung:** T-012-01 omits/falsifies the boolean against the ASSEMBLED app and
  demands 422; T-012-03 captures the ROOT logger at DEBUG during a full valid request
  and asserts zero sentinel occurrences — a test that any accidental payload log
  instantly fails.

**File: `tests/test_match_privacy.py`**

| ID | Test function | Given / When / Then | ACs | Class |
|---|---|---|---|---|
| T-012-01 | `test_consent_absent_returns_422` | `VALID_MATCH_REQUEST` minus `second_person_consent_confirmed`; When POST; Then 422 ErrorEnvelope naming the missing consent field; AND the schema path to the field is fully `required` in OpenAPI (no optional ancestor). | AC-012c | integration-fake |
| T-012-02 | `test_consent_false_returns_422` | Same request with the boolean `false`; Then 422 (not 200 with a warning) with a stable consent-specific detail code. | AC-012c | integration-fake |
| T-012-03 | `test_no_raw_birth_data_in_logs_at_any_level` | `caplog.at_level(logging.DEBUG)` on the root logger; POST a VALID request (200); Then across ALL captured records (message + args + formatted), none of: `1988-06-04`, `07:31`, `Pacific/Chatham`, `1979-11-23`, `America/Caracas`, `173.9391`, `-43.9502`, `-66.9036`, `10.4806` occurs. Repeat for the 422 (consent-absent) path. | AC-012a, EV-005 | integration-fake |
| T-012-04 | `test_consent_value_is_hash_logged_with_request_id` | Same capture; Then at least one record from the match logger contains the request_id AND a hash-formatted token (documented format, e.g. 64-hex sha256) for the consent value; the record contains NO person fields. | AC-012f | integration-fake |
| T-012-05 | `test_persist_raw_defaults_false_and_no_raw_artifact_written` | (a) OpenAPI: `persist_raw` schema default is `false`; (b) run a valid request inside a `tmp_path`-monitored cwd with a snapshot of writable app dirs; Then no new file contains any sentinel value. | AC-012b | integration-fake |
| T-012-06 | `test_consent_copy_claims_no_legal_certification` | Scan the consent field's schema `description` + any served consent copy in the committed spec; Then it does not contain `legally reviewed`, `GDPR-compliant`, `certified` (OQ-001 is open — copy must not imply legal review). | AC-012d | integration-fake |
| — | AC-012e (future profile matching) | Deferred with REQ-016 — no MVP test; see §3. | AC-012e | — |

---

### REQ-013 — Observability + evidence ledger + EV-007 mechanism

- **Beat 0:** boundary (metrics/log surface; the EV-007 demand falsifier's mechanism).
- **These:** "Calls are measured and classified team vs external."
- **Gegenthese:** metrics emit counts, but every caller lands in one bucket because
  the allowlist is empty/unwired in the assembled app — after 30 days EV-007 "passes"
  with 10 calls that were all the team's own smoke tests: the demand falsifier
  becomes unfalsifiable again (chain G), silently.
- **Schärfung:** T-013-03 drives one allowlisted key and one non-allowlisted key
  through the ASSEMBLED app with auth enforced and asserts the two calls land in
  DIFFERENT buckets — a test that fails if classification is unwired or one-bucketed.

**File: `tests/test_match_observability.py`**

| ID | Test function | Given / When / Then | ACs | Class |
|---|---|---|---|---|
| T-013-01 | `test_evidence_ledger_covers_every_block_and_warning` | Valid response; Then `evidence_ledger` has ≥1 entry for every emitted analysis block AND every warning; no ledger entry mentions score contributions (key scan per §0.4). | AC-013a | integration-fake |
| T-013-02 | `test_metrics_and_observability_records_contain_no_pii` | Capture the metrics/log emission for one valid call; Then records contain request_id, endpoint, ruleset id/version, warning classes, latency, source-completeness — and NO sentinel birth values, NO raw API key material (only tier/hash). | AC-013b, AC-013c | integration-fake |
| T-013-03 | `test_team_vs_external_classification_via_key_allowlist` | Given `FUFIRE_REQUIRE_API_KEYS` enforced and an allowlist env containing key K_team but not K_ext; When one call with each key; Then observability output classifies K_team's call `team` and K_ext's call `external`, exposing counts + key-tier ONLY (no key string, no PII). Kills chain G's mechanism half. | AC-013d, EV-007-mechanism | integration-fake |
| T-013-04 | `test_request_id_propagates_into_match_logs_and_response` | Send `X-Request-ID: qa-fixed-id-123`; Then the response header/envelope and the captured match log records carry the same id (RequestIdMiddleware parity through the new route). | AC-013c | integration-fake |

---

### REQ-014 — Determinism

- **Beat 0:** boundary (byte-stability must hold through the production serializer and
  is ephemeris-environment-dependent — F8 makes this environment-honest, not pure math).
- **These:** "Same input ⇒ byte-stable normalized core fields."
- **Gegenthese:** the canonical hash is computed over a hand-built internal dict in a
  unit test (stable forever), while the ACTUAL response serialization order or a
  wall-clock timestamp field churns every call — deterministic in the lab, unstable on
  the wire; or snapshots recorded under MOSEPH are compared in a SWIEPH CI leg and the
  suite flakes into being `skip`ped forever.
- **Schärfung:** T-014-02 calls the ASSEMBLED endpoint twice and compares the
  serialized normalized-core byte ranges; snapshots are per-ephemeris-mode
  (`snapshots/moseph/`, `snapshots/swieph/` idiom) so environment-honesty is explicit.

**File: `tests/test_match_determinism.py`**

| ID | Test function | Given / When / Then | ACs | Class |
|---|---|---|---|---|
| T-014-01 | `test_canonical_hash_invariant_under_json_key_order` | Build two semantically identical request docs with permuted key order; feed both through the canonicalization function (`bazi_engine.match` canonical-JSON path — same discipline as `bafe/canonical_json.py`); Then hashes are EQUAL; mutate one value ⇒ hashes DIFFER. | AC-014a | unit-fake |
| T-014-02 | `test_repeated_identical_requests_yield_byte_stable_core` | POST the same `VALID_MATCH_REQUEST` twice against the assembled app; Then the normalized core fields (individual.*, pair layers, raw blocks, evidence_ledger — everything EXCEPT explicitly documented volatile fields such as request_id/timestamp, whose exclusion list is pinned IN the test) serialize byte-identically; AND the response's provenance/canonical hash field (wherever the coder pins it in the schema — the test records its JSONPath) is identical across both calls and recomputable from the body. | AC-014a, AC-014b | integration-fake |
| T-014-03 | `test_fixture_snapshot_stability_per_ephemeris_mode` | Golden pair fixtures (≥2 pairs, incl. one `birth_time_known=false`); snapshot stored under `tests/snapshots/<mode>/match_*.json` keyed by the ACTIVE `EPHEMERIS_MODE`; Then current output == snapshot for the active mode. SWIEPH leg marked `@pytest.mark.swieph` (auto-skip without SE1 files, per conftest). | AC-014b | integration-fake |

---

### REQ-015 — Performance boundary

- **Beat 0:** boundary (metrics emission is wiring; the p95 target is a deployed-system
  fact and explicitly MISSING until a live baseline exists).
- **These:** "Match adds bounded overhead and emits latency metrics."
- **Gegenthese:** a local timing assertion "overhead < 250ms" passes trivially on the
  dev machine and proves nothing about the deployed p95 — worse, it becomes a flaky
  gate that gets skipped, while NO latency metric is actually emitted in production,
  so AC-015c's revision can never happen (unmeasurable, like chain G's shape).
- **Schärfung:** do NOT write a hard local latency assertion as the acceptance test;
  instead prove the MEASUREMENT wiring exists (T-015-02) and the purity property
  (T-015-01). The 250ms/p95 evaluation is a named real-boundary item (§3).

**File: `tests/test_match_perf.py`**

| ID | Test function | Given / When / Then | ACs | Class |
|---|---|---|---|---|
| T-015-01 | `test_pair_analysis_is_pure_after_charts_available` | Given two precomputed chart objects; When calling the pair-analysis service function directly, with filesystem/network access monkeypatched to raise; Then it completes (no I/O) and twice-same-input ⇒ identical output. | AC-015a | unit-fake |
| T-015-02 | `test_latency_metric_emitted_per_match_request` | One valid request via the assembled app; Then the observability surface (per T-013-02's mechanism) contains a numeric duration/latency measurement for the match computation distinct from total request time. | AC-015b | integration-fake |
| — | AC-015c | Live p95 baseline + target revision: NOT automatable in this repo — §3 item RB-3. | AC-015c | real-boundary |

---

### REQ-016 — Future registered-user matching (P2)

- **Beat 0:** N/A — DEFERRED by the frozen spec; requires its own privacy/security PRD.
- **These/Gegenthese/Schärfung:** not run — writing tests here would fabricate scope.
- **Tests:** NONE in this increment (matches traceability row). Explicitly named:
  AC-016a–e and AC-012e have NO test and NO blocker — they are out-of-increment by
  user decision, tracked in the ledger (CAN-010). Any coder adding profile-matching
  code in this increment violates the scope guard; T-003-03's static check plus the
  §0.4 schema scans give incidental protection (no `allow_match_by_other_users` field
  may appear — add this key to T-007-01's forbidden-key scan as QA hardening).

---

## 2. Frontend-repo test contract (implemented in `/Users/benjaminpoersch/Projects/SaaS/FuFirEProject/Fufire_API-landingpage`)

These are BINDING specifications; they cannot be automated in the backend repo and are
never to be silently dropped. Framework: the frontend repo's existing test runner;
component tests render the real catalog/SchemaForm components, not mocks of them.

| ID | Test (suggested location) | Given / When / Then | ACs | Chain |
|---|---|---|---|---|
| FE-CAT-01 | `src/lib/endpoint-catalog.test.ts` | `TAG_TO_CATEGORY` contains an entry mapping the backend's Hehun tag (the exact literal pinned by backend T-001-05) to category `Hehun`; the category union type includes `Hehun` (compile + runtime assert). | AC-011b, AC-001d | B |
| FE-CAT-02 | `src/lib/endpoint-catalog.test.ts` | Build the catalog from an OpenAPI fixture containing `POST /v1/match/bazi-hehun` tagged with the Hehun tag; Then the entry's category is `Hehun` and display label is `BaZi Hehun` — and is NOT `Raw Data` (explicit negative assertion on the fallback). | AC-011b, AC-001d | B (kill) |
| FE-SUB-03 | catalog/endpoint-card component test | Render the Hehun catalog entry (flag ON); Then visible subtitle text is exactly `Deterministic pair-chart facts — no compatibility score` (a DE equivalent may appear ALONGSIDE, never instead); AND no rendered copy for this entry matches the blocked-promise lexicon: `marriage`, `Ehe`, `compatibility score`, `soulmate`, `match guarantee`. | AC-011f | — |
| FE-FLAG-04 | feature-flag config test | Resolve the Hehun visibility flag under the PRODUCTION build configuration (production env/build mode, not test defaults); Then it is `false`/OFF. This must read the same config artifact the production build uses. | AC-011g | A (kill, local half) |
| FE-FLAG-05 | catalog render test | Render the full catalog UI with the flag OFF and an OpenAPI snapshot that CONTAINS the match path; Then no `Hehun` category and no `BaZi Hehun` entry is present in the rendered output. (Proves OFF hides even when the contract contains the endpoint.) | AC-011h | A |
| FE-FLAG-06 | catalog render test | Same render with flag ON; Then the entry appears under `Hehun` with label `BaZi Hehun` and the FE-SUB-03 subtitle. | AC-011h, AC-011b, AC-011f | A |
| FE-FORM-07 | `SchemaForm` test | Given the match request schema from the synced snapshot; Then SchemaForm renders editable nested fields for `person_a`, `person_b`, `options`, INCLUDING the `second_person_consent_confirmed` boolean as a required checkbox; client-side validation blocks submission while unchecked/invalid. | AC-011c | — |
| FE-PROXY-08 | proxy (`src/server/app.ts`) test | With the synced OpenAPI loaded: POST `/api/v1/proxy` for `/v1/match/bazi-hehun` is ALLOWED; the same request against a snapshot WITHOUT the path is REJECTED (fail-closed); non-POST methods on the path are rejected. | AC-011d | — |
| FE-SNAP-09 | snapshot-sync test | Both `public/openapi.json` and `src/api/openapi.json` parse and contain `paths["/v1/match/bazi-hehun"]` after sync. | AC-010b, AC-011a | — |
| FE-E2E-10 | integration/browser test (flag ON) | Endpoint tester composes and sends the valid sample request through `/api/v1/proxy` against a stubbed-or-live backend; Then a 2xx response renders. Browser-live evidence acceptable per AC-011e. | AC-011e | — |

---

## 3. Tests that CANNOT be automated in this repo (named, never dropped)

| ID | Item | Why not automatable here | Evidence class | Gate it belongs to |
|---|---|---|---|---|
| FE-* (10 specs) | All §2 tests | Live in the frontend repo (user-approved scope expansion, audit F1). | frontend integration | Done-claim for REQ-010(b)/REQ-011 |
| RB-1 | Deployed-backend smoke: POST `https://<railway-prod>/v1/match/bazi-hehun` with a REAL API key; assert 200 + T-007-02-style score-absence + `quality_flags.ephemeris_mode` present; assert legacy `/match/bazi-hehun` 404 in prod. | Needs the deployed artifact + real secrets (MISSING-005; repo Development Principle: verify the deployed artifact). | real-boundary-smoke | MISSING-005 — blocks ANY Done claim |
| RB-2 | Pre-launch production landingpage check: production URL catalog does NOT show Hehun while the flag is OFF (and DOES after the user-signed launch flip). | Production deploy state; cannot be proven by any local build test — this is chain A's final falsifier. | real-boundary-smoke | CAN-015 / chain A residual |
| RB-3 | Live p95 latency baseline + revision of the 250ms overhead target. | Spec itself marks the full-request p95 target MISSING until live baseline (AC-015c). | real-boundary-smoke | AC-015c |
| RB-4 | EV-007 demand evidence: ≥10 external calls / 30 days post-flip, read from the AC-013d classification counters. | Post-launch, time-boxed, real traffic. The MECHANISM is tested (T-013-03); the EVIDENCE is not automatable. | real-boundary (post-launch) | EV-007 / ASSUMPTION-003 |
| — | OQ-001 legal adequacy | Not a test at all — a legal review gating the launch flip. Named so it is never mistaken for QA-covered. | none | CAN-015 launch gate |
| — | REQ-016 / AC-016a–e / AC-012e | Deferred P2 by frozen spec; separate PRD + legal review required before any test exists. | none | out of increment |

**Declared BLOCKERs from this QA pass: none.** Every failure-mode chain resolves to a
test or an explicitly named real-boundary item above. One WATCH item (not a blocker):
the exact schema location of `second_person_consent_confirmed` (top-level vs `options`)
is left to the coder by the frozen spec (PRD says "request schema carries", AC-011c
groups it with options); T-012-01 is written location-agnostic but requires the whole
path to be `required` — the coder must pin the location in `tests/fixtures/match_payloads.py`
on first implementation, and it freezes with the contract.

---

## 4. Failure-mode-chain coverage (audit chains A–G → tests)

| Chain | Description (audit) | Killed by | Status at contract time |
|---|---|---|---|
| A | build=launch: visibility merge auto-deploys to production, bypassing OQ-001 | FE-FLAG-04 (prod default OFF) + FE-FLAG-05 (OFF hides) + FE-FLAG-06 (ON shows) + RB-2 (deployed falsifier) | COVERED (frontend repo + named real-boundary residual RB-2) |
| B | "Raw Data" mislabel: unmapped Hehun tag falls back | T-001-05 (backend tag pin) + FE-CAT-01/02 (mapping + explicit not-Raw-Data negative) | COVERED (cross-repo pin, both halves) |
| C | score reintroduction | T-007-01/02/03/04 (schema-graph, deep response, lexical, metadata honesty) + T-006-04 | COVERED |
| D | mount-idiom conflict (dual-mount vs DECISION-001) | T-001-01 + T-001-03 (legacy 404 ErrorEnvelope negative test) | COVERED |
| E | ephemeris-mode divergence (match lacks attestation) | T-004-04 (quality_flags.ephemeris_mode presence + parity with single-chart in-process) + T-014-03 per-mode snapshots | COVERED |
| F | 422 echoes birth data | T-009-04 (sentinel no-echo, forces custom handler) + T-012-03 (log side) | COVERED |
| G | demand falsifier unmeasurable | T-013-03 (allowlist classification, two buckets, counts+tier only) + RB-4 (named post-launch evidence) | COVERED (mechanism); evidence = RB-4 by design |

Council surviving points (D1–D8) map: D1→REQ-007 tests; D2→REQ-002 tests; D3→REQ-006
tests; D4→T-008-03; D5→T-012-01/02/04; D6→T-013-03+RB-4; D7→FE-SUB-03+T-007-03;
D8/F1→§2 exists at all. Audit F7→T-005-03; F8→T-004-04.

---

## 5. Evidence-class ceiling per REQ

What the best LOCAL test can prove vs what irreducibly needs real-boundary evidence.

| REQ | Local ceiling | Residual needing real-boundary / other-repo evidence |
|---|---|---|
| REQ-001 | integration-fake (assembled app, both mounts) | RB-1 (deployed route + prod legacy-404); FE label half |
| REQ-002 | integration-fake (full schema+behavior) | RB-1 confirms deployed schema matches |
| REQ-003 | integration-fake (in-process parity) | none beyond RB-1 — parity is in-process by nature |
| REQ-004 | integration-fake | RB-1: deployed `ephemeris_mode` will differ from local MOSEPH runs — attestation makes that honest, but only RB-1 proves the prod value |
| REQ-005 | integration-fake | domain validity itself is NOT provable by any test — MISSING-001..003 (source_status honesty is the tested proxy) |
| REQ-006 | integration-fake | none |
| REQ-007 | integration-fake (schema graph + responses) | RB-1 re-runs score-absence against prod body |
| REQ-008 | integration-fake | none |
| REQ-009 | integration-fake | RB-1: prod error path with real middleware/proxy stack |
| REQ-010 | integration-fake (committed artifact + drift check) | FE-SNAP-09 (other repo) |
| REQ-011 | backend: tag pin only | FE-* (all of it) + RB-2 (production flag state — the ONLY proof chain A is closed in reality) |
| REQ-012 | integration-fake (caplog root scan, 422 no-echo) | RB-1: prod logging config differs from test config — a prod log-level or handler could reintroduce leakage invisible locally; include a redaction spot-check in RB-1 runtime-log review |
| REQ-013 | integration-fake (mechanism) | RB-4: demand evidence is post-launch by definition |
| REQ-014 | integration-fake per ephemeris mode | RB-1: determinism claim is only environment-honest once the prod mode is attested (T-004-04 field observed live) |
| REQ-015 | unit-fake purity + integration-fake metric wiring | RB-3: p95 target evaluation is deployed-only |
| REQ-016 | none (deferred) | separate PRD |

Fake-only alert (Reality Ledger): REQ-011 and REQ-015(c) and REQ-013(EV-007 evidence)
have ceilings BELOW their acceptance meaning inside this repo. They must be carried as
open items until FE-*, RB-2, RB-3, RB-4 close — a green backend suite alone is RED for
these three per the ledger rules.

---

## 6. Counts

- Backend repo (this repo): **53 test functions** across 13 planned files
  (`test_match_contract.py` 8, `test_match_schema.py` 5, `test_match_service_boundary.py` 4,
  `test_match_normalization.py` 4, `test_match_individual_analysis.py` 3,
  `test_match_pair_layers.py` 4, `test_match_score_absence.py` 4,
  `test_match_raw_blocks.py` 4, `test_match_errors.py` 4, `test_match_privacy.py` 6,
  `test_match_observability.py` 4, `test_match_determinism.py` 3, `test_match_perf.py` 2)
  — plus `tests/test_golden.py` unchanged as regression anchor and the new shared
  fixture module `tests/fixtures/match_payloads.py`.
- Frontend repo: **10 test specifications** (FE-CAT-01..FE-E2E-10).
- Named real-boundary items: **4** (RB-1..RB-4) + 2 non-test gates (OQ-001, REQ-016).
- Declared BLOCKERs: **0**. Watch item: consent-field schema location pin (see §3).
