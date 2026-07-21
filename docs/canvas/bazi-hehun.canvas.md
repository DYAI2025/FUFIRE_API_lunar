# Product Canvas — BaZi Hehun

Status: user-confirmed  
Feature Slug: `bazi-hehun`  
Generated: 2026-07-01T23:18:20Z  
Originally confirmed: 2026-07-02 by user (Ben) — see Confirmation History below  
Amended: 2026-07-02 (council decisions D1–D8, all explicitly user-adopted)  
Re-confirmed: 2026-07-02 by user (Ben) — amended canvas incl. ASSUMPTION-003 threshold  
Post-audit remediation: 2026-07-02 (single Phase-0.7 pass — user-decided F1/F2/F3/F4; Status unchanged, see Confirmation History)  
Readiness-Level: USER_CONFIRMED  
Mode: PLUMBLINE_READY_PACKAGE

## Amendment 2026-07-02 (council-adopted, user decision "ADOPT ALL")

- D1: Score fields (`total_score`, `sub_scores`, `score_class`) are OMITTED from the MVP response schema entirely (not shipped always-null); a versioned scoring block may be added additively later once source-approved rulesets exist (contracts freeze on release).
- D2: birth_input-only MVP — `mode=raw_bazi` / `CanonicalBaziChartInput` cut from MVP scope, deferred post-MVP (additive); RESOLVES OQ-002.
- D3: MVP pair-analysis layers are only the fully-populated, source-verified ones (Day Master comparison, spouse-palace/day-branch facts, Wu-Xing vector comparison); the five interaction matrices are deferred until domain-approved tables exist (MISSING-001..003).
- D4: LLM-readiness claim struck from AC-008b — the AC-008a block schema IS the contract; downstream LLM consumption needs its own separately gated spec.
- D5: Consent enforced server-side — required request boolean `second_person_consent_confirmed`, 422 when false/absent, hash-logged (no PII); OQ-001 (legal adequacy) gates PUBLIC LAUNCH, not the build. (Post-audit remediation 2026-07-02: public launch = feature-flag flip, gated on OQ-001 + user sign-off — CAN-015.)
- D6: One falsifiable demand-side success signal added (≥10 external calls / 30 days — threshold is ASSUMPTION, pending user confirmation at re-confirmation).
- D7: Honest framing — category `Hehun` / label `BaZi Hehun` kept; RISK-004 mitigation subtitle changed to "Deterministic pair-chart facts — no compatibility score" (DE equivalent allowed); no copy may promise marriage matching.
- D8: Allowed change scope section approved by user as written (2026-07-02).

## Amendment 2026-07-02 — post-audit remediation (user-decided F1/F2/F3/F4)

Applied by `requirements-analyst` in the single Phase-0.7 remediation pass mandated by
`docs/audits/2026-07-02-bazi-hehun-spec-audit.md`. Every change executes an explicit
user decision of 2026-07-02; none is agent-inferred product meaning. Per the audit and
orchestrator ruling this does NOT reopen the canvas to `draft` — Status stays
`user-confirmed`.

- F1 (BLOCKER, resolved): the frontend repo IS in scope — user-approved expansion of the
  Allowed change scope per the D8 expansion rule. See the new "Frontend repo" subsection
  under Allowed change scope. Council cost-saver 9 ("zero custom frontend code") is
  annotated FALSIFIED in `docs/concilium/2026-07-02-bazi-hehun-challenge.md`
  (evidence: `endpoint-catalog.ts:42-77`, unmapped-tag fallback "Raw Data").
- F2 (BLOCKER, resolved): PUBLIC LAUNCH boundary defined — new CAN-015: Hehun
  landingpage visibility ships behind a feature flag, DEFAULT OFF in production; flag
  flip = PUBLIC LAUNCH, gated on BOTH (a) OQ-001 legal-review resolution AND (b)
  explicit user launch sign-off. Backend endpoint may be live earlier (API-reachable,
  not advertised). Encoded as PRD AC-011g/AC-011h.
- F3 (resolved): DECISION-001 recorded in the PRD — `/v1/match/bazi-hehun` is mounted
  /v1-ONLY, a documented deliberate deviation from the repo CLAUDE.md dual-mount idiom
  (precedent: admin router is /v1-only); rationale: downstream API-key consumers only
  call `/v1/*`. AC-001c stands unchanged.
- F4 (resolved): EV-007 measurement mechanism defined — external-call attribution via
  API-key allowlist: calls authenticated with API keys OUTSIDE a maintained team/admin
  key allowlist count as external; counts + key-tier only, no PII (PRD AC-013d).
  ASSUMPTION-003 stays confirmed.

## Problem

EXPLICIT: FuFirE lacks the requested deterministic BaZi-Hehun pair-analysis endpoint and frontend visibility for it.

## Users / Customers

EXPLICIT: API consumers, frontend landingpage users, and coding agents implementing the FuFirE BaZi-Hehun feature.

## Value Promise

EXPLICIT: Users can submit two BaZi-compatible inputs and receive deterministic, source-status-labelled raw compatibility analysis without unsupported fate or relationship claims.

## Current Alternatives

ASSUMPTION: Users can currently compute individual BaZi charts through existing calculation endpoints, but not a deterministic pair-analysis layer exposed as BaZi Hehun.

## Key Capabilities

- CAN-004: Implement POST /v1/match/bazi-hehun, schemas, normalization, raw analysis response, evidence ledger, OpenAPI exposure, and frontend Hehun category visibility.
- CAN-005 (amended per D1): No numeric compatibility score exists in the MVP contract. `total_score`, `sub_scores` and `score_class` are OMITTED from the response schema entirely (not null-shipped). A versioned scoring block may be added additively later once real source-verified data/rulesets exist.
- CAN-006: Reuse or extract internal BaZi computation through a backend service boundary rather than coupling the match endpoint to browser state or user sessions.
- CAN-007 (amended per D2): birth_input-only MVP. `mode=raw_bazi` / `CanonicalBaziChartInput` is deferred post-MVP (additive). If/when raw mode ships later, it must be a reduced, versioned canonical schema; full internal BaziResponse remains internal-adapter-only.
- CAN-008 (amended per D7): Landingpage category and visible feature framing use Hehun / BaZi Hehun, with the honest subtitle "Deterministic pair-chart facts — no compatibility score" (EN; DE equivalent allowed alongside). No output/copy may promise marriage matching.
- CAN-009: MVP requires user acknowledgement that the second person knows and agrees to the birth-data entry; legal review remains required.
- CAN-012 (new, per D3): MVP pair-analysis layers = ONLY fully-populated, source-verified layers: Day Master comparison, spouse-palace/day-branch facts, Wu-Xing vector comparison. The five interaction matrices (branch matrix, stem matrix, asymmetric Ten-Gods A→B/B→A, Shen-Sha) are DEFERRED until domain-approved interaction/Ten-Gods tables exist (MISSING-001..003). Verified fact: `spec/rulesets/standard_bazi_2026.json` contains no such tables — the matrices would only emit MISSING_INTERACTION_TABLE placeholders.
- CAN-013 (new, per D5): Consent is enforced server-side: the request schema carries a REQUIRED boolean `second_person_consent_confirmed`; the backend returns 422 when it is false or absent; the value is hash-logged (no PII). This closes the direct-API bypass. GDPR legal adequacy (OQ-001) remains OPEN and gates PUBLIC LAUNCH — it does not gate the build. Public launch = feature-flag flip, gated on OQ-001 + user sign-off (CAN-015).
- CAN-015 (new, EXPLICIT, user decision 2026-07-02, per audit F2): PUBLIC LAUNCH boundary = frontend feature flag. The Hehun category/endpoint visibility in the landingpage ships behind a feature flag that is DEFAULT OFF in production. Flag flip = PUBLIC LAUNCH and is gated on BOTH (a) OQ-001 legal-review resolution AND (b) explicit user launch sign-off. The backend endpoint may be live earlier (API-reachable, not advertised in the catalog UI). Encoded as PRD AC-011g/AC-011h (testable in the frontend repo).

## Non-Goals

- EXPLICIT: No heuristic score in MVP — score fields are omitted from the contract entirely (D1).
- EXPLICIT: No relationship guarantee, fate claim, diagnosis, or therapeutic advice.
- EXPLICIT: No western synastry or Fusion calculation inside the BaZi Hehun score/path.
- EXPLICIT: Registered user-to-user matching is deferred to a separate feature/PRD.
- EXPLICIT (D2): No `mode=raw_bazi` / `CanonicalBaziChartInput` in MVP (deferred post-MVP, additive).
- EXPLICIT (D3): No interaction-matrix layers (branch matrix, stem matrix, Ten-Gods A→B/B→A, Shen-Sha) in MVP.

## Constraints

- EXPLICIT: Endpoint path remains `/v1/match/bazi-hehun`.
- EXPLICIT: Public visible feature framing uses `BaZi Hehun` and category `Hehun`, with honest subtitle per D7.
- EXPLICIT (amended per D1): Score fields (`total_score`, `sub_scores`, `score_class`) are omitted from the MVP contract entirely; a versioned scoring block may only be added additively once source-verified rulesets and test data exist.
- MISSING: Domain-approved complete interaction tables for all BaZi pair-analysis layers.
- MISSING: Legal review for consent and second-person birth data handling.

## Risks

- RISK-001: False authority risk if heuristic compatibility scores are emitted prematurely. Mitigation (D1): score fields do not exist in the MVP contract.
- RISK-002: Privacy risk from birth date/time/place and second-person data. Mitigation (D5): server-side consent boolean, no raw persistence by default, hash-only logging.
- RISK-003: Coupling risk if raw mode accepts full unstable internal BaziResponse from external clients. Mitigation (D2): raw mode cut from MVP; any future raw mode must be a versioned canonical schema.
- RISK-004: UX comprehension risk because `Hehun` is authentic but not self-explanatory. Mitigation (amended per D7): honest subtitle "Deterministic pair-chart facts — no compatibility score" (DE equivalent allowed) — NOT "Traditional BaZi compatibility analysis"; no copy may promise marriage matching.

## Success Signal

- EXPLICIT (supply-side, CAN-011): Feature is successful when backend OpenAPI contains the endpoint, frontend displays it under Hehun, sample valid input returns non-heuristic raw analysis, and no raw birth data is logged by default.
- ASSUMPTION (demand-side falsifier, CAN-014, per D6): ≥10 external (non-team) calls to POST /v1/match/bazi-hehun within 30 days of landingpage visibility. The concrete threshold (≥10 / 30 days) is a proposed default, subject to user confirmation at canvas re-confirmation.

## Evidence

Unified evidence register (shared with PRD — IDs identical in both artifacts):

- EV-001: Static OpenAPI path assertion for `POST /v1/match/bazi-hehun`.
- EV-002: Backend route smoke test plus schema/contract tests with valid `birth_input` (raw_bazi deferred per D2).
- EV-003: Frontend landingpage visibility test under category `Hehun` with honest subtitle (D7).
- EV-004: Contract tests proving score fields are absent from the response schema and responses (D1).
- EV-005: Log-redaction test proving raw birth data is not logged by default; consent boolean is hash-logged only (D5).
- EV-006: Traceability matrix covers every `REQ-*`.
- EV-007: Demand-side, post-launch: ≥10 external (non-team) calls to POST /v1/match/bazi-hehun within 30 days of landingpage visibility (= public-launch flag flip, CAN-015). Threshold = ASSUMPTION-003, user-confirmed at canvas re-confirmation 2026-07-02 (D6). Measurement mechanism (user-decided 2026-07-02, audit F4): external-call attribution via API-key allowlist — calls authenticated with API keys outside the maintained team/admin key allowlist count as external; counts + key-tier only, no PII (PRD AC-013d, planned test `tests/test_match_observability.py`).

## Allowed Scope

EXPLICIT: Implement POST /v1/match/bazi-hehun, schemas, normalization, raw analysis response, evidence ledger, OpenAPI exposure, and frontend Hehun category visibility.

## Unresolved Questions

- OQ-001: OPEN — Exact final legal/privacy wording for second-person consent. Per D5 this gates PUBLIC LAUNCH, not the build. Public launch = feature-flag flip, gated on OQ-001 + user sign-off (CAN-015).
- OQ-002: RESOLVED by user decision 2026-07-02 (D2) — `raw_bazi` mode does NOT ship in MVP; birth_input-only; raw mode deferred post-MVP (additive).
- OQ-003: OPEN — Which domain source will approve traditional interaction tables for later score output.

## Canvas Item Register

| Canvas ID | Field | Marker | Content |
| --- | --- | --- | --- |
| CAN-001 | Problem | EXPLICIT | FuFirE lacks the requested deterministic BaZi-Hehun pair-analysis endpoint and frontend visibility for it. |
| CAN-002 | Users / Customers | EXPLICIT | API consumers, frontend landingpage users, and coding agents implementing the FuFirE BaZi-Hehun feature. |
| CAN-003 | Value Promise | EXPLICIT | Users can submit two BaZi-compatible inputs and receive deterministic, source-status-labelled raw compatibility analysis without unsupported fate or relationship claims. |
| CAN-004 | Allowed Scope | EXPLICIT | Implement POST /v1/match/bazi-hehun, schemas, normalization, raw analysis response, evidence ledger, OpenAPI exposure, and frontend Hehun category visibility. |
| CAN-005 | Non-Heuristic Output Constraint | EXPLICIT (amended D1) | Score fields (`total_score`, `sub_scores`, `score_class`) are OMITTED from the MVP response schema entirely; a versioned scoring block may be added additively later once source-verified data/rulesets exist. |
| CAN-006 | Modular Architecture | EXPLICIT | Reuse or extract internal BaZi computation through a backend service boundary rather than coupling the match endpoint to browser state or user sessions. |
| CAN-007 | Input Mode Strategy | EXPLICIT (amended D2) | birth_input-only MVP; `mode=raw_bazi` / `CanonicalBaziChartInput` deferred post-MVP (additive, versioned); full internal BaziResponse remains internal-adapter-only. |
| CAN-008 | Frontend Category | EXPLICIT (amended D7) | Landingpage category/framing Hehun / BaZi Hehun with honest subtitle "Deterministic pair-chart facts — no compatibility score" (DE equivalent allowed); no marriage-matching promise. |
| CAN-009 | Privacy Consent | EXPLICIT | MVP requires user acknowledgement that the second person knows and agrees to the birth-data entry; legal review remains required. |
| CAN-010 | Future Registered-User Matching | ASSUMPTION | A later feature may allow registered user-to-user matching only with explicit opt-in, revocation, audit and access-control model. |
| CAN-011 | Success Signal (supply-side) | EXPLICIT | Feature is successful when backend OpenAPI contains the endpoint, frontend displays it under Hehun, sample valid input returns non-heuristic raw analysis, and no raw birth data is logged by default. |
| CAN-012 | MVP Pair-Analysis Layers | EXPLICIT (D3) | MVP ships only fully-populated, source-verified layers: Day Master comparison, spouse-palace/day-branch facts, Wu-Xing vector comparison. The five interaction matrices are deferred until MISSING-001..003 close. |
| CAN-013 | Server-Side Consent Enforcement | EXPLICIT (D5) | Request schema carries REQUIRED boolean `second_person_consent_confirmed`; backend 422 when false/absent; value hash-logged (no PII). OQ-001 gates public launch, not build; public launch = feature-flag flip, gated on OQ-001 + user sign-off (CAN-015). |
| CAN-014 | Success Signal (demand-side) | ASSUMPTION (D6) | ≥10 external (non-team) calls to POST /v1/match/bazi-hehun within 30 days of landingpage visibility; threshold pending user confirmation at canvas re-confirmation. |
| CAN-015 | Launch Boundary (public-launch mechanism) | EXPLICIT (user decision 2026-07-02, audit F2) | Hehun landingpage visibility ships behind a feature flag, DEFAULT OFF in production; flag flip = PUBLIC LAUNCH, gated on BOTH OQ-001 legal-review resolution AND explicit user launch sign-off. Backend endpoint may be live earlier (API-reachable, not advertised). Encoded as PRD AC-011g/AC-011h. |

## Allowed change scope

APPROVED by user as written: 2026-07-02 (D8 — was an orchestrator proposal pending approval, now approved).

Amendment 2026-07-02 (T1 review round 1 — scope-gate repair): the list below was
reformatted from backtick-wrapped annotated bullets into bare glob patterns with `#`
annotations, because `plumbline_scope.py::_clean_pattern()` only end-trims backticks and
does not strip trailing prose — the original formatting made every pattern unmatchable
and broke the mandatory scope gate for ALL files. The eight original patterns are
semantically UNCHANGED (formatting only). Two entries were ADDED under the D8 expansion
rule: `tests/fixtures/match_payloads.py` (mandated verbatim by the binding acceptance-test
contract §0.2 and its §3 WATCH item; plan T7 lists a `tests/fixtures/` addition) and
`tests/test_import_hierarchy.py` (LAYERS registration only — without it the plan T1
done-criterion "no Level-5 imports from match/" is vacuously green). Applied under the
reviewer-mandated T1 fix loop (round 1); per D8 these changes require explicit user
sign-off — flagged for ratification at the next user checkpoint.

RATIFIED by user 2026-07-02 (explicit steering choice "Beide ratifizieren"): the
formatting repair AND both added entries (`tests/fixtures/match_payloads.py`,
`tests/test_import_hierarchy.py`) are user-approved. The expanded scope baseline is
confirmed; the T1 watcher value-risk (review-required) is resolved.
(Parser note: no prose line in the Allowed change scope section may begin with -, *, or +
— the scope parser reads such lines as glob patterns.)

Amendment 2026-07-03 (T7 review round 1 — scope/contract-tension repair): one entry
was ADDED under the D8 expansion rule: `tests/snapshots/*/match_*.json`. This resolves a
genuine tension the T7 reviewer surfaced (scope-check exit 3): the binding acceptance-test
contract (`docs/testing/bazi-hehun.acceptance-tests.md` §0.3 and T-014-03) explicitly
MANDATES per-ephemeris-mode determinism snapshots at `tests/snapshots/<mode>/match_*.json`
(the `test_snapshot_stability.py` idiom), yet the ratified fence did not permit that path.
Relocating the snapshots was rejected because it would violate that binding contract; the
correct resolution is to widen the fence. The added pattern is deliberately NARROW — it
matches ONLY `match_*.json` under a snapshot mode dir (the two T7 golden pairs), NOT the
200+ pre-existing non-match snapshots — so it grants no incidental authority over the rest
of `tests/snapshots/**`. Per D8 this change requires explicit user sign-off — flagged for
ratification at the next user checkpoint.

RATIFIED by user 2026-07-03 (explicit: "Ich ratifiziere die Scope-Erweiterung für T7
(match_*.json) hiermit"): the narrow `tests/snapshots/*/match_*.json` scope entry is
user-approved. The T7 watcher value-risk (review-required) is resolved; Iteration 1
(Milestone A) is settled.
(Parser note: no prose line in this section may begin with -, *, or +.)

Repo-relative paths an implementation increment may touch (PRIL Scope Guard baseline;
expand only with explicit user approval; bare glob patterns, annotations after `#`):

- bazi_engine/routers/match.py  # new
- bazi_engine/match/**  # new subpackage: normalization, pair analysis, raw text, evidence
- bazi_engine/app.py  # router mount only
- spec/openapi/openapi.json  # regenerated
- spec/schemas/**  # new Hehun request/response schemas, if contract-first artifacts are added
- scripts/export_openapi.py  # only if export needs the new router registered
- tests/test_match_*.py  # new
- tests/fixtures/match_payloads.py  # shared fixture module, contract §0.2 (added T1 review round 1)
- tests/test_import_hierarchy.py  # LAYERS registration only (added T1 review round 1)
- tests/snapshots/*/match_*.json  # per-ephemeris-mode determinism snapshots, contract §0.3 + T-014-03 (added T7 review round 1; narrow: match_*.json only)
- docs/**  # governance artifacts for this feature

### Frontend repo (user-approved expansion 2026-07-02, per audit F1)

Repo root: `/Users/benjaminpoersch/Projects/SaaS/FuFirEProject/Fufire_API-landingpage`

Allowed paths (repo-relative):

- `src/lib/endpoint-catalog.ts` (TAG_TO_CATEGORY entry for the `Hehun` tag + category
  union extension)
- consent-UI component under `src/components/**` (new or extended)
- feature-flag mechanism file(s) for the Hehun visibility flag (CAN-015 / AC-011g)
- `public/openapi.json` + `src/api/openapi.json` (snapshot sync)
- frontend tests

Honest enforcement note: `plumbline-scope-check` runs per-repo; frontend scope is
enforced procedurally via the changed-files list until tooling exists in that repo.

## Confirmation Status

user-confirmed

Confirmed by user: yes  
Confirmed on: 2026-07-02 (re-confirmation of the amended canvas)  
Confirmer: Ben (product owner)  
Confirmation note: exact required phrase given again after the D1–D8 amendment — "Ich bestätige, dass Product Canvas und Product Vision meine Absicht korrekt wiedergeben und als Grundlage für AgileTeam Planning verwendet werden dürfen". The re-confirmation explicitly covers the D6/ASSUMPTION-003 demand threshold (≥10 external non-team calls within 30 days), which the user accepted without modification.

### Confirmation History

Original confirmation (preserved):

Confirmed by user: yes  
Confirmed on: 2026-07-02  
Confirmer: Ben (product owner)  
Confirmation note: exact required phrase given — "Ich bestätige, dass Product Canvas und Product Vision meine Absicht korrekt wiedergeben und als Grundlage für AgileTeam Planning verwendet werden dürfen."

Amendment 2026-07-02: canvas amended per council decisions D1–D8 (all explicitly adopted by the user on 2026-07-02). Per governance, the amended canvas returned to `draft`; the user re-confirmed it the same day (see Confirmation Status above).

Post-audit remediation 2026-07-02 (user-decided F1/F2/F3/F4): canvas amended in the single Phase-0.7 remediation pass (`docs/audits/2026-07-02-bazi-hehun-spec-audit.md`) — frontend-repo scope expansion (F1), CAN-015 launch boundary (F2), DECISION-001 pointer (F3), EV-007 measurement mechanism (F4). Rationale for status: per the audit and orchestrator ruling this does NOT reopen the canvas to `draft`, since every change is a directly user-decided remediation (explicit user decisions of 2026-07-02), not agent-inferred product meaning. Status remains `user-confirmed`. The spec freezes after this pass.
