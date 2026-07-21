# PRD — BaZi Hehun Endpoint and Landingpage Integration

Status: user-confirmed  
Feature Slug: `bazi-hehun`  
Owner: Ben / FuFirE product owner  
Generated: 2026-07-01T23:18:20Z  
Amended: 2026-07-02 (council-adopted decisions D1–D7 — see changelog); 2026-07-02 post-audit remediation (audit F1–F5, user-decided — see changelog)  
Mode: PLUMBLINE_READY_PACKAGE  
Readiness-Level: USER_CONFIRMED

## Amendment 2026-07-02 (council-adopted)

All decisions explicitly adopted by the user on 2026-07-02 (`docs/concilium/2026-07-02-bazi-hehun-challenge.md`, "ADOPT ALL"):

- D1 → REQ-007 rewritten: score fields (`total_score`, `sub_scores`, `score_class`) are ABSENT from the MVP schema (not null-shipped); AC-007a–d now assert absence; AC-007e (lexical blocked-language guard) kept. RISK-001 mitigation updated; EV-004 reworded; REQ-013/REQ-014 wording made consistent.
- D2 → REQ-002 rewritten: birth_input-only MVP; `mode=raw_bazi` / `CanonicalBaziChartInput` deferred post-MVP (additive). RESOLVES OQ-002. AC-002b/d now assert rejection/absence of raw mode. RISK-003 mitigation updated. NOGOAL-005 added.
- D3 → REQ-006 rewritten: MVP layers = Day Master comparison, spouse-palace/day-branch facts, Wu-Xing vector comparison only; the five interaction matrices (branch, stem, Ten-Gods A→B/B→A, Shen-Sha) deferred until MISSING-001..003 close (verified: `spec/rulesets/standard_bazi_2026.json` contains no such tables). NOGOAL-006 added. AC-009b adjusted for consistency.
- D4 → REQ-008/AC-008b: LLM/Fusion interpretation-readiness claim struck; the AC-008a block schema IS the contract; downstream LLM consumption requires its own separately gated spec outside this endpoint.
- D5 → REQ-012: consent enforced server-side — REQUIRED request boolean `second_person_consent_confirmed`, backend 422 when false/absent, value hash-logged (no PII); AC-012c is now a backend contract test. OQ-001 (legal adequacy) gates PUBLIC LAUNCH, not the build. (Post-audit remediation 2026-07-02: public launch = feature-flag flip, gated on OQ-001 + user sign-off — CAN-015.)
- D6 → EV-007 added: demand-side post-launch signal, ≥10 external (non-team) calls within 30 days of landingpage visibility (ASSUMPTION: threshold pending user confirmation).
- D7 → REQ-011/RISK-004: honest subtitle "Deterministic pair-chart facts — no compatibility score" (DE equivalent allowed); no copy may promise marriage matching. AC-011f added.
- CONTRA-001 fix: AC numbering for REQ-014/REQ-015/REQ-016 made internally consistent (former mislabels AC-NFR-*/AC-015* removed); evidence register unified with the canvas (EV-001..EV-007); no phantom IDs (CAN-012/CAN-013/CAN-014 now genuinely exist in the amended canvas).
- Note: the user-confirmed Vision is unedited; VIS-004's "or canonical raw charts" clause is deferred by D2 (raw mode post-MVP) — this narrows scope and does not weaken any VIS-006 boundary.

## Amendment 2026-07-02 — post-audit remediation (single Phase-0.7 pass, user-decided)

Applied per `docs/audits/2026-07-02-bazi-hehun-spec-audit.md`; every change executes an
explicit user decision of 2026-07-02. The spec freezes after this pass.

- F1 → frontend repo added to the canvas Allowed change scope (user-approved expansion
  per D8 rule); council cost-saver 9 annotated FALSIFIED in the concilium report.
- F2 → launch boundary defined: canvas CAN-015 (feature flag, default OFF in
  production; flip = PUBLIC LAUNCH, gated on OQ-001 + explicit user launch sign-off);
  AC-011g/AC-011h added under REQ-011; all "gates PUBLIC LAUNCH" mentions now name the
  mechanism.
- F3 → DECISION-001 recorded (see Decisions): /v1-only mount for the match route.
- F4 → EV-007 measurement mechanism defined (API-key allowlist attribution); AC-013d
  added under REQ-013.
- F5 → stale cross-references fixed (canvas is `user-confirmed`, re-confirmed
  2026-07-02, not draft).
- F7/F8/claim 2 → carried into "Planning notes (from spec audit)".

## Decisions

- DECISION-001 (2026-07-02, resolves audit F3): `/v1/match/bazi-hehun` is mounted
  /v1-ONLY — a documented, deliberate deviation from the repo CLAUDE.md dual-mount
  idiom (precedent: the admin router is /v1-only). Rationale: downstream API-key
  consumers only call `/v1/*`. AC-001c stands unchanged.

## Source Summary

This PRD is derived from the reviewed FuFirE BaZi-Hehun PRD, the user decisions made after review, and the supplied target-system endpoint draft. It is an AgileTeam intake artifact, not a repository write or runtime proof.

| Source ID | Type | Title | Limits |
| --- | --- | --- | --- |
| SRC-001 | user_provided | User-provided BaZi-Hehun endpoint draft | User-provided design source; not runtime evidence and not traditional-domain validation. |
| SRC-002 | repository_evidence | Backend generated OpenAPI contract | Static exported contract; not a live server proof. |
| SRC-003 | repository_evidence | Backend BaZi router request/response | Static code; not executed during this PRD task. |
| SRC-004 | repository_evidence | Backend v1 router mounting | Static code; actual exported route requires running the app or export script after implementation. |
| SRC-005 | repository_evidence | FuFirE BaZi ruleset | Repo content is real; traditional correctness of the tables is not independently proven here. |
| SRC-006 | repository_evidence | Existing Wu-Xing vector calculation | Single-chart vector only; not pair compatibility. |
| SRC-007 | repository_evidence | Sprint plan gap statement | Planning document; not runtime evidence. |
| SRC-008 | repository_evidence | Frontend OpenAPI snapshots | Static snapshot; production deployment not queried. |
| SRC-009 | repository_evidence | Frontend endpoint catalog builder | Static code; UI rendering requires frontend tests. |
| SRC-010 | repository_evidence | Frontend endpoint tester | Static code; not browser-live evidence. |
| SRC-011 | repository_evidence | Frontend BFF proxy | Static code; not a live request proof. |
| SRC-012 | skill_instructions | AI-Native PRD Architect skill | Process instruction; not product-domain evidence. |
| SRC-013 | user_decision | Council challenge gate decisions D1–D8, adopted 2026-07-02 | User steering decision; recorded in `docs/concilium/2026-07-02-bazi-hehun-challenge.md`. |
| SRC-014 | user_decision | User decision during PRD v0.2 review (pre-intake): future registered-user opt-in matching model | User-provided product decision; not runtime evidence; scoped as P2 future (REQ-016). |

## Problem Statement

EXPLICIT: FuFirE needs a deterministic BaZi Hehun endpoint that compares two charts through source-labelled raw analysis layers and exposes the endpoint on the API landingpage. The MVP contract contains no score fields at all (omitted, not null — D1) while complete domain-approved interaction data is missing.

## Target Users

- EXPLICIT: API consumers using FuFirE BaZi endpoints.
- EXPLICIT: Users of the FuFirE API landingpage endpoint tester.
- EXPLICIT: Coding agents/developers implementing and validating the feature.

## Goals

- GOAL-001: Implement `POST /v1/match/bazi-hehun` as the canonical route.
- GOAL-002: Expose the feature in the landingpage under category `Hehun` with label `BaZi Hehun` and the honest subtitle per D7.
- GOAL-003: Return deterministic raw analysis with source statuses and warnings; score fields are omitted from the MVP contract entirely (D1).
- GOAL-004: Preserve privacy by default: no raw birth data logs, `persist_raw=false`, server-side-enforced consent boolean for second-person data (D5).

## Non-Goals

- NOGOAL-001: No numeric compatibility score in MVP — score fields are omitted from the contract entirely (D1); a versioned scoring block may be added additively post-MVP once source-approved rulesets exist.
- NOGOAL-002: No guarantee of marriage success, separation risk, fate, health, wealth or psychological condition.
- NOGOAL-003: No western synastry or Fusion scoring in this endpoint.
- NOGOAL-004: No registered user-to-user stored matching in MVP; this is a future separate PRD.
- NOGOAL-005 (D2): No `mode=raw_bazi` / `CanonicalBaziChartInput` in MVP; deferred post-MVP as an additive, versioned change.
- NOGOAL-006 (D3): No interaction-matrix pair layers (branch matrix, stem matrix, asymmetric Ten-Gods A→B/B→A, Shen-Sha) in MVP; deferred until domain-approved tables exist (MISSING-001..003).

## Assumptions

- ASSUMPTION (verified-at-code-level 2026-07-02): Existing BaZi calculation can be extracted or reused via internal backend service boundary. Audit claim 1 (belegt): `bazi_engine/routers/bazi.py:379` calls pure `compute_bazi()` — chart-computation reuse is satisfied. Residual for planning: normalization equivalence (AC-003c) requires REUSING shared response-shaping helpers, not copying them — see Planning notes (c).
- ASSUMPTION (deferred by D2): If/when `raw_bazi` ships post-MVP, `CanonicalBaziChartInput` is the sustainable external raw mode; full `BaziResponse` remains internal adapter input. Not part of the MVP contract.
- ASSUMPTION: MVP value is acceptable as raw deterministic analysis without scores.
- ASSUMPTION (D6): Demand threshold "≥10 external (non-team) calls within 30 days of landingpage visibility" — confirmed by the user at canvas re-confirmation 2026-07-02 (ASSUMPTION-003; the assumption now concerns demand itself, not the threshold value). Measured per the EV-007 API-key-allowlist mechanism (AC-013d).

## Open Questions

- OQ-001: OPEN — Final legal/privacy wording for second-person birth data consent. Per D5: gates PUBLIC LAUNCH, does not gate the build. Public launch = feature-flag flip, gated on OQ-001 + user sign-off (CAN-015, AC-011g/h).
- OQ-002: RESOLVED 2026-07-02 by user decision (D2) — `raw_bazi` does NOT ship in MVP; birth_input-only; raw mode deferred post-MVP (additive).
- OQ-003: OPEN — Which domain-reviewed source will approve later interaction/scoring tables.

## Requirements with REQ IDs

| REQ ID | Source ID | Priority | Title | Requirement | Source IDs |
| --- | --- | --- | --- | --- | --- |
| REQ-001 | FR-001 | P0 | Create canonical backend route with Hehun labeling | Implement a canonical versioned BaZi-Hehun pair-analysis endpoint at POST /v1/match/bazi-hehun. Public UI label must be BaZi Hehun under category Hehun. Do not expose unversioned legacy route unless explicitly decided. | SRC-001, SRC-002, SRC-004, SRC-007 |
| REQ-002 | FR-002 | P0 | birth_input-only MVP input mode (raw_bazi deferred) | Endpoint accepts mode=birth_input with two FuFirE BaziRequest-compatible person payloads. mode=raw_bazi / CanonicalBaziChartInput is NOT part of the MVP contract (user decision D2, 2026-07-02, resolves OQ-002); it is deferred post-MVP and may only be added additively behind an explicit schema version. Full FuFirE BaziResponse input remains internal-adapter-only if ever added. | SRC-001, SRC-003, SRC-013 |
| REQ-003 | FR-003 | P0 | Reuse FuFirE BaZi calculation through internal service boundary | For each person, obtain a single-chart BaZi result equivalent to /v1/calculate/bazi or /v1/calculate/bazi/trace before pair analysis. Prefer extraction of shared Python service functions that both the existing route and the Hehun route call. HTTP calls to /v1/calculate/bazi are only recommended if the match engine runs as a separate service/process. | SRC-001, SRC-003, SRC-004 |
| REQ-004 | FR-004 | P0 | Normalize individual charts | Normalize both raw charts into canonical Stem, Branch, Pillar, WuxingVector and IndividualChartAnalysis structures with provenance and warning codes. | SRC-001, SRC-003, SRC-005, SRC-006 |
| REQ-005 | FR-005 | P0 | Run individual chart analysis first | Before pair comparison, compute individual layers for each chart: Day Master, spouse palace/day branch, month command, Wu-Xing vector, source status, warnings and optional domain-reviewed derived fields. DMS, Yong-Shen and spouse-star layers remain MISSING/NEEDS_DOMAIN_REVIEW when no approved rule source exists. | SRC-001, SRC-005, SRC-006 |
| REQ-006 | FR-006 | P0 | Compute the MVP pair-analysis layers (matrices deferred) | Compare A and B across exactly the fully-populated, source-verified MVP layers: (1) Day Master comparison, (2) spouse-palace/day-branch facts, (3) Wu-Xing vector comparison (user decision D3). The five interaction matrices — branch matrix, stem matrix, asymmetric Ten-Gods A→B and B→A, Shen-Sha — are DEFERRED until domain-approved interaction/Ten-Gods tables exist (MISSING-001..003; verified fact: spec/rulesets/standard_bazi_2026.json contains no such tables, so they would only emit MISSING_INTERACTION_TABLE placeholders). No layer assigns numeric points. | SRC-001, SRC-005, SRC-013 |
| REQ-007 | FR-007 | P0 | Score fields absent from the MVP contract | The MVP response schema contains NO score fields: total_score, sub_scores, score_class (and any awarded_points/score_confidence) do not exist in the contract (user decision D1 — omitted, not null-shipped, because FuFirE endpoint contracts freeze on release). A versioned scoring block may be added ADDITIVELY post-MVP once complete interaction tables, Ten-Gods mapping, DMS/Yong-Shen logic and validation fixtures are source-verified and approved (MISSING-001..003). The lexical blocked-language output guard remains in force. | SRC-001, SRC-005, SRC-013 |
| REQ-008 | FR-008 | P0 | Structured raw analysis response | Return raw_analysis_text blocks that are deterministic, factual, layer-scoped and source-linked without being free advice. The AC-008a block schema (id, layer, statement_type, subject, text, source_status, evidence_ids) IS the contract; no LLM/Fusion interpretation-readiness is claimed or designed for (D4) — downstream LLM consumption requires its own separately gated spec outside this endpoint. | SRC-001, SRC-013 |
| REQ-009 | FR-009 | P0 | Error envelope consistency | Reuse FuFirE ErrorEnvelope/problem-style error behavior for validation, upstream/compute failure, malformed payloads, deferred-mode requests and ruleset-incomplete cases. | SRC-002, SRC-003, SRC-004, SRC-011 |
| REQ-010 | FR-010 | P0 | OpenAPI contract and schemas | Add request/response schemas, examples and route documentation to generated backend OpenAPI and export/sync to frontend contract snapshots. | SRC-002, SRC-004, SRC-008, SRC-009 |
| REQ-011 | FR-011 | P0 | Frontend endpoint tester visibility with honest framing | Ensure the landing page endpoint tester exposes the new endpoint from the OpenAPI catalog under category Hehun with label BaZi Hehun and the honest subtitle "Deterministic pair-chart facts — no compatibility score" (EN; DE equivalent allowed alongside — D7); renders editable nested fields for person_a/person_b/options (incl. the consent boolean); validates payload before sending; sends through /api/v1/proxy. No copy may promise marriage matching. Hehun visibility ships behind a feature flag, DEFAULT OFF in production (CAN-015, user decision 2026-07-02); visibility criteria (incl. AC-011e) are evaluated with the flag ON. | SRC-009, SRC-010, SRC-011, SRC-013 |
| REQ-012 | FR-012 | P0 | Security and privacy defaults with server-side consent | Default persist_raw=false; never log raw birth date/time/place or supplied custom key; emit hashes, request ID and warning codes only. The request schema carries a REQUIRED boolean second_person_consent_confirmed; the backend returns 422 when it is false or absent (server-side enforcement closes the direct-API bypass — D5); the consent value is hash-logged with request_id (no PII). GDPR legal adequacy (OQ-001) remains subject to review and gates PUBLIC LAUNCH, not the build — public launch = feature-flag flip, gated on OQ-001 + user sign-off (CAN-015). | SRC-001, SRC-003, SRC-011, SRC-013 |
| REQ-013 | FR-013 | P1 | Observability and evidence ledger | Record request_id, endpoint, ruleset_id/version, warning classes, source completeness, latency and evidence ledger completeness. Score fields do not exist in the MVP contract (D1), so no score metrics or distributions are emitted. Metrics classify calls as team vs external via the API-key allowlist (calls with keys outside the maintained team/admin allowlist count as external); counts + key-tier only, no PII — this is the EV-007 measurement mechanism (user decision 2026-07-02, audit F4). | SRC-001, SRC-011 |
| REQ-014 | NFR-001 | P0 | Determinism | Same input, same ruleset_version and same schema version produce byte-stable normalized core fields. Numeric score stability is not applicable: score fields are omitted from the MVP contract (D1). | SRC-001, SRC-005 |
| REQ-015 | NFR-002 | P1 | Performance boundary | Endpoint should add bounded overhead over two single-chart calculations. Initial target: p95 match computation overhead under 250ms excluding BaZi chart generation; full request p95 target MISSING until live baseline exists. | SRC-001 |
| REQ-016 | FR-015 | P2 | Future registered-user opt-in matching model | Future feature: allow registered users to store matchable birth-profile data and explicitly opt in to being matched by other users. A match may only be generated when the stored profile owner has enabled a consent flag that permits other users to use their data for match calculation. This is out of MVP scope and requires separate privacy/security PRD before implementation. | SRC-014 |

## Acceptance Criteria

| AC ID | REQ ID | Acceptance Criterion |
| --- | --- | --- |
| AC-001a | REQ-001 | Backend OpenAPI contains POST /v1/match/bazi-hehun with request and response schemas. |
| AC-001b | REQ-001 | GET/POST to non-existent /v1/match paths returns stable ErrorEnvelope/problem response, not internal error. |
| AC-001c | REQ-001 | No unversioned /match/... route is exposed unless DECISION accepts legacy alias. |
| AC-001d | REQ-001 | Frontend display name uses BaZi Hehun, category Hehun. |
| AC-002a | REQ-002 | birth_input requires person_a and person_b with date/tz/lon/lat. |
| AC-002b | REQ-002 | The MVP schema defines no mode=raw_bazi; a request with mode=raw_bazi or raw chart payloads returns 422 validation_error (deferred post-MVP per D2). |
| AC-002c | REQ-002 | Invalid mode or missing required payload returns 422 with per-field detail. |
| AC-002d | REQ-002 | The published OpenAPI request schema contains only birth_input mode fields; no CanonicalBaziChartInput schema is published in MVP. |
| AC-003a | REQ-003 | Existing /v1/calculate/bazi behavior remains unchanged. |
| AC-003b | REQ-003 | Hehun route does not duplicate core chart calculation logic. |
| AC-003c | REQ-003 | Same-person chart output used by Hehun is equivalent to existing BaziResponse normalization source. |
| AC-003d | REQ-003 | No user-session cache or cross-user state is used as the meaning of reuse. |
| AC-004a | REQ-004 | day_master is day.heavenly_stem only; month_master/hour_master are stored as provenance labels only. |
| AC-004b | REQ-004 | visible stems and hidden stems are included in Wu-Xing ledger with source and weight. |
| AC-004c | REQ-004 | unverified day-cycle anchor and birth_time_known=false produce warnings. |
| AC-005a | REQ-005 | output contains individual.person_a and individual.person_b. |
| AC-005b | REQ-005 | DMS/Yong-Shen fields carry source_status and confidence. |
| AC-005c | REQ-005 | missing reviewed thresholds do not masquerade as tradition-verified facts. |
| AC-006a | REQ-006 | The pair section contains exactly the three MVP layers — day_master_comparison, spouse_palace_day_branch, wuxing_vector_comparison — each fully populated from source-verified computation. |
| AC-006b | REQ-006 | No branch-matrix, stem-matrix, Ten-Gods (A→B/B→A) or Shen-Sha layer appears in the MVP response schema (deferred until MISSING-001..003 close). |
| AC-006c | REQ-006 | No MISSING_INTERACTION_TABLE placeholder blocks are emitted in MVP: layers whose tables are missing are absent from the contract, not stubbed. |
| AC-006d | REQ-006 | Pair-analysis text is limited to calculated facts, rule applications, source-status markers and warnings; no layer emits numeric points. |
| AC-007a | REQ-007 | The response schema defines no total_score field, and no MVP response contains a total_score key. |
| AC-007b | REQ-007 | The response schema defines no sub_scores or awarded_points fields, and no MVP response contains them. |
| AC-007c | REQ-007 | The response schema defines no score_class or score_confidence field; source_completeness_confidence, if present, is named and documented as source-status metadata and never a compatibility score. |
| AC-007d | REQ-007 | No response emits any numeric compatibility value, including PROPOSED_HEURISTIC values (contract test plus lexical scan). |
| AC-007e | REQ-007 | no output says perfect match, marriage guarantee, breakup prediction or fate certainty (lexical blocked-language guard). |
| AC-008a | REQ-008 | each text block has id, layer, statement_type, subject, text, source_status, evidence_ids. |
| AC-008b | REQ-008 | The AC-008a block schema is the complete response-text contract; no field, doc or example claims LLM/Fusion interpretation-readiness (D4); downstream LLM consumption is out of scope for this endpoint and requires its own separately gated spec. |
| AC-008c | REQ-008 | response contains warnings and blocked-language safeguards. |
| AC-009a | REQ-009 | 422 validation_error for malformed request. |
| AC-009b | REQ-009 | Requests attempting deferred capabilities (mode=raw_bazi, scoring/matrix options) return 422 with stable ErrorEnvelope detail, not internal error; ruleset_incomplete remains reserved in the error contract for future scoring/matrix modes. |
| AC-009c | REQ-009 | 502/503 for compute/upstream failures where applicable. |
| AC-009d | REQ-009 | errors never echo raw birth data or API keys. |
| AC-010a | REQ-010 | backend OpenAPI validates as JSON. |
| AC-010b | REQ-010 | frontend public/openapi.json and src/api/openapi.json include the new path after sync. |
| AC-010c | REQ-010 | operation has product tag that maps intentionally to Hehun. |
| AC-010d | REQ-010 | example request is valid and does not contain invented computed values. |
| AC-011a | REQ-011 | /api/v1/openapi.json includes final match path after backend sync. |
| AC-011b | REQ-011 | endpoint catalog includes category Hehun and display label BaZi Hehun. |
| AC-011c | REQ-011 | SchemaForm renders nested person_a/person_b/options fields, including the required second_person_consent_confirmed boolean. |
| AC-011d | REQ-011 | proxy allows POST only when path/method is present in loaded OpenAPI. |
| AC-011e | REQ-011 | endpoint tester can send a valid sample request in browser/live or integration test evidence. |
| AC-011f | REQ-011 | Visible subtitle is "Deterministic pair-chart facts — no compatibility score" (or its DE equivalent alongside); no visible copy promises marriage matching or compatibility scoring (D7). |
| AC-011g | REQ-011 | Hehun visibility is behind a feature flag, default OFF in production (CAN-015; testable in the frontend repo). |
| AC-011h | REQ-011 | With the flag OFF the endpoint does not appear in the landingpage catalog UI; with the flag ON it appears under Hehun with the honest subtitle (CAN-015; testable in the frontend repo). |
| AC-012a | REQ-012 | no raw birth datetime, timezone, lon/lat or person payload appears in application logs. |
| AC-012b | REQ-012 | persist_raw=false by default. |
| AC-012c | REQ-012 | The request schema requires second_person_consent_confirmed; the backend returns 422 when the field is false or absent (backend contract test — closes the direct-API bypass, D5). |
| AC-012d | REQ-012 | consent copy does not imply legal review or platform certification. |
| AC-012e | REQ-012 | if future profile matching is added, opt-in/opt-out and revocation are modeled per user profile. |
| AC-012f | REQ-012 | The consent boolean value is hash-logged together with request_id; no PII is logged (D5). |
| AC-013a | REQ-013 | each response has evidence_ledger entries for every emitted analysis block and warning (no score contributions exist in MVP — D1). |
| AC-013b | REQ-013 | metrics avoid personal data. |
| AC-013c | REQ-013 | request-id is propagated through frontend/proxy/backend logs where available. |
| AC-013d | REQ-013 | Match endpoint metrics classify calls as team vs external via the API-key allowlist (calls authenticated with keys outside the maintained team/admin allowlist count as external); counts and key-tier only, no PII (EV-007 measurement mechanism — audit F4). |
| AC-014a | REQ-014 | canonical raw hash is stable for equivalent JSON ordering. |
| AC-014b | REQ-014 | fixture output snapshots are stable. |
| AC-015a | REQ-015 | computation is pure/in-memory after charts are available. |
| AC-015b | REQ-015 | latency metrics are emitted. |
| AC-015c | REQ-015 | performance target is revised after real-boundary measurement. |
| AC-016a | REQ-016 | user profile has explicit allow_match_by_other_users flag default false. |
| AC-016b | REQ-016 | consent is revocable and revocation prevents new matches. |
| AC-016c | REQ-016 | no requester receives raw birth data of another user unless separately consented. |
| AC-016d | REQ-016 | access and audit logs record who requested a match and which consent state authorized it. |
| AC-016e | REQ-016 | separate legal/privacy review completed before public release. |

## Non-Functional Requirements

| REQ ID | Original ID | Title | Requirement |
| --- | --- | --- | --- |
| REQ-014 | NFR-001 | Determinism | Same input, same ruleset_version and same schema version produce byte-stable normalized core fields. Numeric score stability is not applicable: score fields are omitted from the MVP contract (D1). |
| REQ-015 | NFR-002 | Performance boundary | Endpoint should add bounded overhead over two single-chart calculations. Initial target: p95 match computation overhead under 250ms excluding BaZi chart generation; full request p95 target MISSING until live baseline exists. |

## Risks

- RISK-001: Heuristic score leakage would create false authority. Mitigation (D1): score fields do not exist in the MVP contract; a versioned scoring block may only be added additively once source-verified data exists.
- RISK-002: Privacy and consent risk around second-person birth data. Mitigation (D5): server-side-enforced consent boolean (422 when false/absent, hash-logged), no raw persistence by default. OQ-001 gates public launch — public launch = feature-flag flip, gated on OQ-001 + user sign-off (CAN-015).
- RISK-003: Contract instability if public raw mode accepts full internal `BaziResponse`. Mitigation (D2): raw mode cut from MVP; any future raw mode must be a versioned canonical input added additively.
- RISK-004: `Hehun` may require explanation in UI. Mitigation (D7): honest subtitle "Deterministic pair-chart facts — no compatibility score" (DE equivalent allowed) — explicitly NOT "Traditional BaZi compatibility analysis"; no copy may promise marriage matching.
- RISK-005: Internal-service reuse may require refactoring current route logic. Mitigation: extract pure compute service behind existing route first. (Council note: `routers/bazi.py` already calls pure `compute_bazi()`; the extraction step may already be satisfied — verify at planning.)

## Evidence Needed

Unified evidence register (IDs identical in canvas and PRD):

- EV-001: OpenAPI schema includes `POST /v1/match/bazi-hehun`.
- EV-002: Backend route smoke test plus schema/contract tests return valid non-heuristic raw analysis for two valid `birth_input` payloads (raw_bazi deferred — D2).
- EV-003: Frontend landingpage lists endpoint under `Hehun` category with honest subtitle (D7).
- EV-004: Contract tests prove score fields (`total_score`, `sub_scores`, `score_class`, `awarded_points`, `score_confidence`) are absent from the response schema and from responses (D1).
- EV-005: Log-redaction test proves raw birth date/time/place is not logged by default; consent boolean is hash-logged only (D5).
- EV-006: Traceability matrix covers every `REQ-*`.
- EV-007 (demand-side, post-launch — D6): ≥10 external (non-team) calls to `POST /v1/match/bazi-hehun` within 30 days of landingpage visibility (= public-launch flag flip, CAN-015). Threshold = ASSUMPTION-003, user-confirmed at canvas re-confirmation 2026-07-02. Measurement mechanism (user-decided 2026-07-02, audit F4): external-call attribution via API-key allowlist — calls authenticated with API keys outside the maintained team/admin key allowlist count as external; counts + key-tier only, no PII (AC-013d, planned test `tests/test_match_observability.py`).

## Planning notes (from spec audit 2026-07-02)

Carried from `docs/audits/2026-07-02-bazi-hehun-spec-audit.md` (F7/F8 + konfabulation
claim 2) as planning inputs — no new scope:

- (a) Spouse-palace layer (REQ-005/REQ-006): limited to computed identification facts +
  `source_status`. No spouse-palace table exists in the ruleset
  (`spec/rulesets/standard_bazi_2026.json`); AC-005c guards against interpretive claims
  masquerading as tradition-verified facts (F7).
- (b) The match response must carry the same `quality_flags.ephemeris_mode` attestation
  as single-chart responses — fits REQ-004 provenance; REQ-014 determinism must be
  environment-honest (F8).
- (c) Chart-computation reuse is verified (`bazi_engine/routers/bazi.py:379` calls pure
  `compute_bazi()`), but normalization equivalence (AC-003c) requires REUSING the shared
  response-shaping helpers, not copying them. ASSUMPTION-001 is marked
  verified-at-code-level in the ledger (claim 2).

## Links to Vision, Canvas, and Traceability

- Product Vision: `docs/vision/bazi-hehun.vision.md`
- Product Canvas: `docs/canvas/bazi-hehun.canvas.md` (Status: `user-confirmed` — re-confirmed 2026-07-02 after the D1–D8 amendment, incl. the ASSUMPTION-003 threshold; post-audit remediation 2026-07-02 does not reopen it)
- Traceability Matrix: `docs/traceability.md`

## User Confirmation

Confirmed by user: yes  
Confirmed on: 2026-07-02  
Confirmer: Ben (product owner)  
Confirmation note: "PRD bestätigt — GO" given at the USER GATE on 2026-07-02, together with the explicit Vision GO that starts development. The spec was frozen after the single Phase-0.7 remediation pass; this confirmation covers the frozen state (commit fabe6bf).
