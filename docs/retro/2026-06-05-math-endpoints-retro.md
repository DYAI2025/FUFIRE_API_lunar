# Retrospective — Math Inspection Endpoints (chronometry / bazi-trace / fusion-vector-map)

Date: 2026-06-05 · Branch: `feat/math-endpoints` (off main) · Method: `/agileteam` · Outcome: **ACCEPTED**, 2481 passed / 52 skipped / 1 xfailed / 0 failed, ruff+mypy clean on new files, OpenAPI synced.

## What shipped (3 endpoints, exposing existing deterministic engines — zero fabrication)
- `POST /v1/chronometry/resolve` — composes `solar_time`/`ephemeris`/`jieqi` into a ChronometryFrame + precision grading (missing time → `unknown_time`, no noon default). New `bazi_engine/chronometry.py` + router. `JIEQI_NAMES` added as pure reference data.
- `POST /v1/calculate/bazi/trace` — ADR-1: `include_trace` opt-out flag (default True, zero churn) + alias route reusing the EXISTING `_build_derivation_trace` (no new trace math).
- `POST /v1/calculate/fusion/vector-map` — `sum_l1_normalize()` primitive + endpoint exposing `compute_fusion_analysis`/wuxing; raw + sum_l1 + l2_cosine vectors + H (elemental_overlap_h, cosine_similarity=`cosmic_state`). REQ-F-006 naming corrected.

## What was DEFERRED (and why — no fabrication)
- `/v1/calculate/ziwei` + `/v1/calculate/fusion/state-matrix` — **now UNBLOCKED**: real reference tables exist at `…/Fufire_API-landingpage/docs/ziwei_reference_tables_fufire_v2_pack` (palace_grid_v2, sihua_policy_registry_v2, formula_candidates_v2, fixtures TC-001/002, parity harness, validate_v2.py). A future iteration can build ZiWei strictly from these tables (verify against the parity harness; do NOT invent). state-matrix depends on ziwei.
- `trig_coherence` (raw + 01) — PRD defines only the transform, not the metric; no engine fn; no authoritative source. Shipping it as a renamed `cosmic_state` would be a fake distinct metric. **DEFERRED pending an ADR that defines + sources it.**

## Learnings (individual)

**L1 — the re-grounding guardrail (added last iteration) earned its keep at scale.** The expansion-pack PRD was written without a repo checkout and was wrong on ~8 load-bearing facts: the BaZi trace already exists and ships unconditionally (PRD treated it as new + invented field names that don't exist: `seasonal_strength`, `five_tigers_step`…); fusion cosine already exists as `cosmic_state`; `trig_coherence` is undefined; no solar-term name table; element keys are German not English; `precision.grade` genuinely new. Phase-0 verification against the live modules caught every one BEFORE any code. Had we trusted the PRD, we'd have shipped invented fields = exactly the mockup failure the project exists to prevent.

**L2 — "endpoint == engine" is a TAUTOLOGICAL anti-mockup test.** Reviewer finding H-1 (chronometry): the golden tests recomputed expected values by calling the same engine fns the endpoint calls → stubbing `sun_lon_deg_ut`→constant left all 19 tests GREEN. A genuine anti-mockup anchor needs values INDEPENDENT of the system under test: a frozen on-disk golden + hardcoded sanity asserts cross-checked against an external method (here Meeus/NOAA astronomy). Once added, the stub-constant mutation turns 3 tests red. We then applied this proactively to fusion/vector-map (frozen golden + hardcoded dominance/invariant asserts) — and it caught a constant stub there too.

**L3 — refuse to ship an undefined metric, even renamed (GT3).** The honest move when the PRD wants `trig_coherence` but no formula/source exists is to NOT ship it (defer to an ADR), not to alias an existing metric under a new name. A "distinct" metric that's secretly a duplicate is soft fabrication.

**L4 — disclose + track an inherited bug, don't hide or silently fix (GT6).** The new `/bazi/trace` beta endpoint reaches a pre-existing late-Zi+TLST divergence (trace.day can differ from the headline pillar by one day). We did NOT fix the engine (snapshot-churning, own increment) and did NOT hide it: caveat in the OpenAPI description + a `strict=True` xfail that pins the known divergence and flips red (signalling "remove the caveat") once the engine is fixed.

## System-level adjustment (candidate — needs user sign-off for shared config)
- **Anti-mockup tests must include an INDEPENDENT anchor, not just system-under-test echo.** Add to the code-reviewer discipline: when reviewing a golden/anti-mockup test, verify the expected values are independent of the production code path (frozen fixture cross-checked by an external method / hardcoded domain fact) — an "output == recompute-via-the-same-fn" assertion is tautological and passes a fabricated engine. (Origin: H-1, this iteration.)

## Carried forward (backlog)
- **Cross-repo reconciliation:** the 3 new backend endpoints are NOT yet in the landingpage tester — regenerate the landingpage `openapi.json` from the backend so `buildEndpointCatalog` + the P0 validator surface them (beta). Add curated examples if the synthesizer can't satisfy them.
- ziwei + state-matrix (now unblocked — tables exist).
- trig_coherence ADR (define + source the metric).
- GT6 engine fix: make `_build_derivation_trace` TLST-aware (reuse `compute_bazi`'s late-Zi rollover) → the strict xfail will flip red, then remove the OpenAPI caveat.
- Pre-existing backend lint/type debt (NOT this iteration): ruff `F401 DAY_OFFSET` (`bazi.py:19`) + 4 mypy errors — present on main, CI lint/typecheck already red; separate cleanup commit.
- Cosmetic nits: `mock_server` vector-map is moseph-pinned (add a comment); mixed rounding precision on sibling harmony fields.
- Deploy: `feat/math-endpoints` not merged/deployed; backend `feat/key-issuance` also still unmerged.
