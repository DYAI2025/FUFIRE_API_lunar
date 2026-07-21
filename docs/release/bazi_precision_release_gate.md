# FuFirE BaZi Precision — Release & Stop-Gate Policy

**Authority:** This document is the binding release-gate policy for the
`BAZI-PRECISION-V2` initiative. Reviewers and release managers refuse
default-behavior changes that do not satisfy the gates below.

Read alongside:

- `docs/audits/fufire_bazi_precision_pre_audit.md` (baseline evidence)
- `docs/precision/deviations.md` (active defects)
- `3-code/tasks.md` (phase BAZI-PRECISION-V2)
- `docs/migration/fusion_score_deltas.md` (to be created in FBP-04-006)

## 0. Non-negotiables

These rules are **never** overridden by velocity pressure.

1. `/v1` and `/v1/calculate/*` are **frozen**. Bug fixes that change
   numeric output ship under `/v2` and remain opt-in there until a
   migration report is accepted.
2. `CIVIL`, `LMT`, and `TLST` are three distinct time standards. Code,
   tests, traces, and docs must never alias them.
3. `TLST` is *not* a `tzinfo`. It is apparent solar time with day
   offset.
4. The Zi-day boundary policy and the hour-branch policy must use the
   same effective-time source for a given request.
5. The day-cycle anchor must have a verified ID and source before any
   v2 default uses it. Until then, v2 may exist but cannot be made
   default.
6. Hidden-stem tables must live in a single source of truth referenced
   by both `compute_bazi` and `/validate`.
7. Ten Gods, Day Master Strength, and branch/stem interactions must
   **not** influence the 5-dimensional Wu-Xing mass vector. They are
   separate interpretation features.
8. Raw, weighted, and L2-normalized Wu-Xing vectors must be
   distinguishable in every response that exposes them.
9. Fusion v1 and Fusion v2 must run in parallel and produce a
   case-by-case delta report before any default switch.
10. Score and signature deltas must be measured and documented before
    any default switch.
11. The OpenAPI contract and error envelope must remain contract-tested
    (`tests/test_openapi_contract.py`, `tests/test_error_handling.py`,
    `tests/test_error_sanitization.py`).

## 1. Phase stop-gates

A phase **cannot start** until the prior phase's stop-gate is signed
off by the human reviewer named in §3 below.

### Phase 0 → Phase 1

Required to be true:

- `docs/audits/fufire_bazi_precision_pre_audit.md` exists and contains
  evidence for every claim it makes.
- `docs/precision/deviations.md` exists with the seeded P0/P1 entries.
- `spec/golden/bazi_case.schema.json` exists and passes its schema
  test.
- `tests/golden_reference_cases.py` is split into ENGINE_BASELINE vs
  EXTERNAL_ORACLE entries; `tests/test_golden.py` honors the
  `source_type`.
- `scripts/export_bazi_baseline.py` runs deterministically offline and
  produces `tests/fixtures/bazi_baseline_v1.json` (or a documented
  reason why the export was deferred).
- `tests/test_invariants.py::test_day_offset_reference_examples` is
  rewritten per FBP-00-005 wording (no literal `49`).
- `3-code/tasks.md` Phase BAZI-PRECISION-V2 block is appended.
- Production code is **unchanged** apart from the test rewrite (which
  does not affect behavior).

Phase 1 may proceed **opt-in / diagnostic only** until DEV-2026-004
(day anchor) is resolved. /v1 default remains CIVIL.

### Phase 1 → Phase 2

- `bazi_engine/time_context.py` exists with `EffectiveTimeContext`
  carrying `civil`, `utc`, `lmt`, `tlst_hours`, `eot_minutes`,
  `tz_offset`, `date_rollover`.
- `TimeStandard` enum extended to include `TLST`; rejection paths for
  `INVALID` remain 422.
- `/calculate/tst` and core TLST agree within a documented tolerance
  (`tests/test_tst_endpoint_consistency.py`).
- `solar_time.py` still passes
  `tests/test_import_hierarchy.py::test_solar_time_has_no_internal_imports`.
- LMT and TLST are never synonymous in trace, code, or tests.
- `/v1` default remains `CIVIL`.

### Phase 2 → Phase 3

- Day-cycle anchor verification status is documented in
  `docs/precision/day_cycle_anchor.md` and the ruleset
  `anchor_verification` field is updated accordingly.
- `tests/test_bazi_day_anchor.py`,
  `tests/test_bazi_zi_day_boundary.py`,
  `tests/test_bazi_tlst_hour_pillar.py` all pass.
- `compute_bazi()` and `/validate` consume the same ruleset values
  (`tests/test_ruleset_driven.py`).
- LiChun and Jieqi external goldens are added for the documented
  boundary cases.

### Phase 3 → Phase 4

- Typed derivation trace shipped; `true_solar_time_used` correctly
  reflects TLST (not LMT). `lmt_used` (or equivalent) exists.
- Provenance carries `ruleset_id`, `ruleset_version`,
  `time_policy_id`, `day_anchor_id`, `vector_model_id`.
- OpenAPI is regenerated and `tests/test_openapi_contract.py` is green.
- v2 error responses are planned (not necessarily implemented) on the
  RFC 9457 Problem Details model.

### Phase 4 → Phase 5

- Raw, weighted, and L2-normalized Wu-Xing vectors are separately
  exposed in fusion responses.
- Fusion v1 and v2 run in parallel; delta report
  (`docs/migration/fusion_score_deltas.md`) is published with
  per-case old/new pillars, raw vectors, normalized vectors,
  harmony, calibrated harmony, signature delta.
- `tests/test_fusion_v1_v2_parallel.py` passes.
- Hidden stems come from one source of truth verified by
  `tests/test_classical_hidden_stem_ledger.py`.

### Phase 5 → Phase 6 (API v2 contract)

- Classical interpretation layer exists in `bazi_engine/classical/`
  with typed models, hidden stem ledger, optional Ten Gods, optional
  Day Master Strength, branch/stem interactions.
- `tests/test_classical_no_vector_contamination.py` confirms classical
  features do not influence the 5-D vector.
- Domain reviewer signs off on DMS spec (if implemented).

### Phase 6 → release

- `/v2/calculate/bazi` and `/v2/calculate/fusion` are contract-tested.
- `tests/test_regression_v1_compatibility.py` passes — `/v1`
  reproduces frozen baseline snapshots.
- OpenAPI surfaces v1 and v2 simultaneously; deprecated v1 fields are
  marked.

## 2. Default-switch criteria

A default behavior change (e.g., switching `/v1` to apply TLST or to
use the new fusion) requires **all** of:

1. Migration report (`docs/migration/fusion_score_deltas.md`) with
   distribution statistics over the regression case set.
2. Updated `tests/fixtures/bazi_baseline_v1.json` snapshot
   (or a new baseline file) with the new default's outputs.
3. Sign-off from the domain reviewer (see §3) **and** the API
   compatibility reviewer.
4. Public deprecation notice in `CHANGELOG.md` (release-please-owned;
   `RELEASE_NOTES.md` was retired 2026-07-13, see `docs/archive/`).

Without all four, the default does not change.

## 3. Reviewer roles

| Role | Responsibility |
|------|----------------|
| Domain reviewer | Verifies day-cycle anchor, LiChun / Jieqi boundary calibration, Ten Gods mapping, DMS scoring. Must sign off on FBP-02-003, FBP-05-003, FBP-05-004. |
| API compatibility reviewer | Verifies `/v1` regression snapshots, OpenAPI drift, error envelope compatibility. Must sign off on FBP-03-005, FBP-06-001. |
| Release manager | Verifies CHANGELOG, version-bump consistency (DEV-2026-003), deployment plan. Must sign off on FBP-06-001. |

Reviewer assignments are tracked per-task in
`3-code/tasks.md`.

## 4. Rollback policy

If a v2 default switch is shipped and a regression is reported within
30 days:

1. Immediate revert of the default-switch commit on `main`.
2. Hotfix release pinning `/v1` semantics in `/v2` until the issue
   is root-caused.
3. Postmortem appended to this file with the failing case as a new
   `EXTERNAL_ORACLE` golden if appropriate.

## 5. What this document does *not* govern

- Day-to-day code review (handled by `CODEOWNERS` / PR templates).
- Operational deployment (handled by `docs/runbooks/`).
- Marketing claims about precision — those are the responsibility of
  product / legal; this gate only governs the behavior of the
  software.
