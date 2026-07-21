# DECISION-002 — Response schema for POST /v1/match/bazi-hehun (user-decided 2026-07-02)

Source: user-provided draft "PartnershipAnalysisRawResponseV1" (pasted 2026-07-02),
adopted **ADAPTED to the frozen spec** by explicit user choice ("Adaptiert übernehmen").
This document BINDS the Milestone-B schema task (plan T8+). Exact Pydantic naming/field
spelling is the schema task's job; this binds structure and inclusion/exclusion.

## BINDING — adopt from the draft

- **meta block**: schema_name/schema_version (`BaziHehunRawResponse` v1), endpoint,
  response_kind=raw_analysis_data, generated_at_utc, request_id, correlation_id,
  ruleset_id + ruleset_version, engine_version (from `bazi_engine.__version__` — never
  "MISSING" in real responses, per FQ-ATT discipline), and the `no_score_policy`
  STATEMENT block (policy prose is allowed — the score FIELDS themselves stay absent, D1).
- **request_context**: mode=birth_input only; input_mode_status; birth_input_policy;
  raw_bazi_policy deferral notice (documentation of D2, no schema surface for raw mode);
  privacy_echo_policy (redacted-by-default, no birth-data echo); language.
- **subjects**: person_a/person_b with subject_id, role, display_label, identity_policy
  (pseudonymous allowed, no real name required), birth_context carrying STATUS fields +
  precision (birth_time_known, time/location precision) + redacted_input_ref
  (input_hash, canonical_birth_context_hash) — raw birth data is NEVER echoed.
- **relationship_context** incl. consent_status: acknowledgement flag, consent text
  version, final_legal_text_status, `go_live_blocker: true` until OQ-001 resolves.
- **per-person charts**: four_pillars, day_master, spouse_palace, month_command,
  wuxing_vector WITH contribution_ledger, quality_flags (incl. ephemeris_mode —
  attestation parity with single-chart responses, planning note b), warnings,
  calculation_provenance (upstream source, hashes, calendar_standard, tz handling,
  ruleset id/version).
- **individual_layers**: computed layers (day_master, spouse_palace, month_command) with
  facts + evidence_ids; PRD-mandated deferral statuses for ten_gods (missing),
  day_master_strength + useful_god (needs_domain_review, confidence 0.0, no value field)
  — exactly the AC-005b/T3 shape.
- **pair_layers**: EXACTLY the three MVP layers — day_master_comparison,
  spouse_palace_day_branch, wuxing_vector_comparison (D3).
- **raw analysis text blocks** per AC-008a (id, layer, statement_type, subject, text,
  source_status, evidence_ids).
- **evidence_ledger**, **missing_and_blockers**, **safety_and_language_policy**
  (allowed_output / blocked_output / requires_human_review_before_go_live — matches
  AC-008c safeguards).

## REJECTED — user kept the frozen decisions intact

- `non_scoring_outputs` block (total_score/sub_scores/score_class as null) — **D1**:
  score keys do not exist in the contract, not even as null.
- `structural_matrices` (stem/branch/ten_gods/wuxing matrices, incl. "missing" stubs) —
  **D3**: matrices deferred, no stubs.
- `month_command_pair`, `pillar_pair_overview`, `shensha_layer` stub as pair layers —
  **D3**: exactly three pair layers; month_command stays individual-level only.
- `interpretation_input.allowed_for_llm_interpretation: true` and
  "ready_for_downstream_interpretation" status — **D4**: no LLM-readiness claim; blocks
  carry source_status/evidence_ids, downstream LLM use needs its own gated spec.
- `modalities.western_astrology` / `modalities.fusion` stubs — **NOGOAL-003** + contract
  freeze: no empty modality stubs; a multi-modality envelope may be introduced
  ADDITIVELY when those features actually ship. MVP nests the BaZi-Hehun content
  directly.

## Reminders for the schema task

- WATCH item (test contract §3): pin the location of `second_person_consent_confirmed`
  at first implementation; every ancestor on its path must be `required`.
- Response schema must pass the score-absence schema-graph tests (T-007-*) and the
  blocked-language lexical guard.

# DECISION-003 — Wei (未) hidden-stem weighting source (user-decided 2026-07-02)

Until BAZI-PRECISION-V2 domain review rules finally (MISSING-006): the match engine
binds its Wu-Xing ledger weighting to the SAME source the existing `/calculate/wuxing`
endpoint uses (legacy `bazi_engine/wuxing/analysis.py` tables, mainstream Ji-Ding-Yi) —
the product must not disagree with itself. The ruleset's outlier ordering
(`standard_bazi_2026.json`, Ji-Yi-Ding) stays recorded as MISSING-006 for domain review;
the loud divergence test stays and asserts the divergence is DETECTED and legacy binds.
