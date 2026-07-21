# Math Inspection Endpoints — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: superpowers:executing-plans / test-driven-development. Fresh coder + independent reviewer per increment; reviewer mutation-verifies load-bearing tests.

**Goal:** Add 3 calculation-INSPECTION endpoints to the FuFirE backend that EXPOSE existing deterministic engines — no new metaphysical math, no invented tables.

**Endpoints:** `POST /v1/chronometry/resolve`, `POST /v1/calculate/bazi/trace`, `POST /v1/calculate/fusion/vector-map`.

**Repo/branch:** `/Users/benjaminpoersch/Projects/codebase/FuFirE` @ `feat/math-endpoints` (off main). Python 3.12 + FastAPI, pytest (`testpaths=tests`).

**Prime directive:** no fabrication. Each endpoint's numbers MUST equal what the in-process engine actually computes; golden fixtures are generated FROM the live engine, ephemeris-tag-split (MOSEPH/swieph).

**Out of scope (deferred):** `/v1/calculate/ziwei` + `/v1/calculate/fusion/state-matrix` — ZiWei tables now EXIST at `…/docs/ziwei_reference_tables_fufire_v2_pack` (palace_grid, sihua_policy, formula_candidates, fixtures TC-001/002, parity harness) → unblocked for a SEPARATE next iteration. Landingpage tester reconciliation (regenerate its openapi to surface these 3) = separate follow-up.

---

## Ground-truth corrections (verified in code — trust over the PRD, which had no repo checkout)

| # | Correction | Consequence |
|---|---|---|
| GT1 | **BaZi trace already exists + is attached unconditionally** — `_build_derivation_trace` (`routers/bazi.py:210`), `BaziDerivationTrace` (`types.py:173`), `BaziResponse.derivation_trace` populated every call (bazi.py:370). Real shape `{year, month, day, hour, time_resolution, provenance_ids}`. | bazi/trace = ADD `include_trace: bool = True` (opt-out) + alias route `/v1/calculate/bazi/trace` reusing the existing trace+`compute_bazi`. **Do NOT invent the PRD's `seasonal_strength`/`five_tigers_step`/`late_rat_correction`-as-flag fields** — they don't exist. |
| GT2 | **Fusion cosine already exists as `cosmic_state`** (dot of L2-normalized vectors, fusion.py:147). Engine has L2 (`WuXingVector.normalize/magnitude`) only — **no L1**. | Add `sum_l1_normalize()`; `cosine_similarity` ← existing `cosmic_state` (reuse, don't reimplement). REQ-F-006 naming: the S/sum(S) view is `sum_l1`, NEVER `l2`. |
| GT3 | **`trig_coherence_raw` is undefined math** — PRD only defines the `_01` transform; no engine fn; no authoritative source for a distinct "coherence". | **DEFER `trig_coherence` (raw + 01) from this iteration.** Shipping it as a renamed `cosmic_state` = a fake distinct metric (soft fabrication). Backlog an ADR to define+source it. vector-map ships WITHOUT it. |
| GT4 | **No 24-solar-term NAME table** (`jieqi.py` is degrees-only). | Add `JIEQI_NAMES` constant (24 fixed public-domain names) = pure reference DATA, clearly labeled — deterministic, not invented math. `solar_term` = `JIEQI_NAMES[floor(sun_lon/15)]` from the live Sun longitude. |
| GT5 | `precision.grade`, `unknown_time`, `algorithm_version`, `mapping_version`, `sum_l1`, `elemental_overlap_h` all genuinely new. | Reuse existing version sources: `algorithm_version` ← `bazi_engine.__version__`; `mapping_version` ← new `FUSION_MAPPING_VERSION` const; anchor, don't fabricate a scheme. |
| GT6 | **Latent bug R4:** `_build_derivation_trace` re-derives day via `apply_day_boundary`, ignoring `compute_bazi`'s TLST-aware late-Zi rollover (`bazi.py:178-197`) → trace JDN can disagree with the computed day pillar in late-Zi+TLST. | **Do NOT fix this iteration** (would churn existing snapshots). The /trace endpoint inherits it honestly. Backlog. The consistency test (TRC-E4) asserts trace pillars == `compute_bazi` pillars — if this bug bites a test case, narrow the fixture + backlog the fix. |
| GT7 | Element keys: engine = German `[Holz,Feuer,Erde,Metall,Wasser]`; PRD = English. | Use **German (engine truth)** + document the divergence. |
| GT8 | `ruff`/`mypy` NOT in `pyproject.toml` (no `[tool.ruff]`/`[tool.mypy]`), but caches exist → run via CI/pre-commit. | Condition the lint/type gate on what `ci.yml` actually runs; don't invent stricter config. |

---

## ADR-1: bazi trace — `include_trace` flag + alias route (not a fresh reimpl)
Add `include_trace: bool = True` to `BaziRequest` (default True = current behavior → zero snapshot churn; gives callers a real opt-out they lack today) AND a thin alias route `POST /calculate/bazi/trace` (+`/v1`) that calls the same handler. Both reuse `compute_bazi` + `_build_derivation_trace`. The published path satisfies the landingpage tester; no duplicated trace math.

## Design per endpoint
- **chronometry/resolve:** new pure module `bazi_engine/chronometry.py` (`resolve_chronometry()` dataclass + `JIEQI_NAMES` + `grade_precision()`), thin router `routers/chronometry.py`. Compose `compute_effective_time_context` (EoT, TLST, utc, tz_offset) + `datetime_utc_to_jd_ut`/`SwissEphBackend` (jd_ut, delta_t, sun_lon) + `jdn_gregorian` (jdn) + `lon*4` (longitude correction) + `_lichun_jd_ut_for_year` (boundary_flags). `precision.grade ∈ {exact, degraded, unknown_time, unresolved}`; **date-only input → grade=unknown_time, hour-derived fields null, NO noon default.**
- **bazi/trace:** per ADR-1.
- **fusion/vector-map:** add `sum_l1_normalize()` to `wuxing/vector.py`; new route on `routers/fusion.py`. Build RAW vectors via `calculate_wuxing_*_with_ledger`, then `raw` / `sum_l1` / `l2_cosine` from the SAME raw. H: `elemental_overlap_h`=dot(sum_l1) [0,1]; `cosine_similarity`=existing `cosmic_state` [0,1]. `mapping_version`+`algorithm_version`. (No `trig_coherence` — GT3.)
- All: register bare + `/v1` under `_protected`; label **beta** in OpenAPI tag/description.

---

## DoD (each bullet → proving test)
- Full `pytest` green, no regression (~2455 → +new); existing `/calculate/bazi` default response UNCHANGED → `test_regression_v1_compatibility` (extended) + `test_bazi_trace_endpoint::test_include_trace_false_omits_trace`.
- L1 normalization sums to 1, zero-safe → `test_wuxing_sum_l1::{test_sum_l1_sums_to_one,test_zero_vector_unchanged}`.
- Chronometry == live in-process engine (anti-mockup) → `test_chronometry_frame::test_resolve_known_case_matches_engine`, `test_chronometry_endpoint::test_endpoint_equals_pure_module`.
- Missing time → unknown_time, no noon default → `test_chronometry_frame::test_missing_time_grade_unknown` + `test_chronometry_endpoint::test_unknown_time_no_noon_default`.
- Li Chun boundary flips → `test_chronometry_frame::test_lichun_boundary_flags`; non-integer tz + far longitude → `::test_noninteger_tz_and_far_longitude`.
- Invalid input → stable 422 → `test_chronometry_endpoint::test_invalid_input_422`, `test_fusion_vector_map::test_invalid_input_422`.
- Trace == existing derivation_trace + == compute_bazi pillars → `test_bazi_trace_endpoint::{test_trace_alias_route_matches_existing,test_trace_pillars_match_compute_bazi}`; real fields not PRD fictions → `::test_trace_exposes_real_fields`.
- Late-Zi rollover branch vs midnight → `test_bazi_trace_endpoint::test_late_zi_vs_midnight`.
- vector-map raw/sum_l1/l2 from same raw, naming sum_l1≠l2 (REQ-F-006) → `test_fusion_vector_map::{test_sum_l1_and_l2_from_same_raw,test_naming_is_sum_l1_not_l2}`; H in range + == cosmic_state → `::test_h_components_in_range`; zero-vector safe → `::test_zero_vector_safe`; == compute_fusion_analysis → `::test_engine_consistency`.
- Version metadata present (REQ-F-007) → `test_fusion_vector_map::test_versions_present`, `test_chronometry_endpoint::test_endpoint_200_shape`.
- Golden bit-stability (ephemeris-split) → `test_snapshot_math_endpoints::test_snapshot_stability[...]`.
- 3 endpoints in OpenAPI bare+/v1, beta-labeled → `test_openapi_beta_tags`.

## TDD task list (failing test → run-fail → minimal impl → green → commit)
Phase A: A1 `sum_l1_normalize` (wuxing/vector.py). 
Phase B: B1 chronometry frame == engine, B2 JIEQI_NAMES/solar_term, B3 Li Chun flags, B4 missing-time grade, B5 non-int tz/far-lon (chronometry.py pure module). 
Phase C: C1 endpoint 200+shape+version, C2 endpoint==pure module, C3 invalid→422, C4 unknown-time e2e (router + app.py register + beta tag). 
Phase D: D1 include_trace opt-out, D2 alias==existing, D3 real-fields-not-fictions, D-late-zi (bazi.py + alias route). 
Phase E: E1 sum_l1/l2 from same raw, E2 naming, E3 H in range + ==cosmic_state, E4 versions, E5 zero-vector, E6 invalid→422 (fusion router + models). 
Phase F: F1 golden snapshots (ephemeris-split, generated from engine), F2 openapi beta tags, F3 regression compatibility.

## Mutation checklist (reviewer reproduces → each must turn suite RED)
stub engine fn→constant → golden/consistency red; mislabel sum_l1 as l2 → naming red; default missing time→noon → unknown_time red; drop algorithm_version → metadata red; drop mapping_version → fusion metadata red; un-normalized vector → invariant red; trace rebuilt independently (drift) → TRC consistency red; skip Zi rollover → late-zi-vs-midnight red; round tz to whole hours → non-int-tz red.

## Risks
trig_coherence undefined → DEFERRED (GT3, backlog ADR). solar_term name table → pure data (GT4). late-Zi trace bug → inherited honestly, backlog (GT6). MOSEPH/swieph drift → ephemeris-split snapshots + numeric asserts compare endpoint-vs-in-process (backend-agnostic). PRD field-name fictions → tests lock real names (D3). New deps: NONE.

## Increments (coder→reviewer each)
1. **chronometry** (Phase A foundation if needed for nothing here; B+C) — Task #60.
2. **bazi/trace** (Phase D) — Task #61.
3. **fusion/vector-map** (Phase A + E) — Task #62.
Then Phase F (snapshots+openapi) folded per-increment; Phase 3 gate (#63); Phase 4 retro (#64).
