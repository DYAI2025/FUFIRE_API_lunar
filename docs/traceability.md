# Traceability matrix

Central REQ ↔ acceptance-test ↔ impl-task ↔ evidence matrix across all `/agileteam`
features. One section per feature/increment. Every top-level REQ carries the mandatory
Canvas fields (`canvas-link`, `canvas-problem`, `canvas-target-user`, `canvas-value-claim`,
`canvas-success-signal`, `canvas-risk-status`) and the True-Line fields (`vision-link`,
`value-check-id`, `true-line-status`) per the Product Canvas / Plumbline governance rules.

---
## Feature: `bazi-hehun` — Phase 0 (intake, council-amended)

Status: user-confirmed (Canvas, PRD, and Vision all user-confirmed 2026-07-02)
Confirmed by user: yes — PRD confirmed and Vision GO given 2026-07-02 ("PRD bestätigt — GO").
Canvas amended 2026-07-02 per council decisions D1–D8 (all user-adopted), re-confirmed the
same day (incl. ASSUMPTION-003 threshold). Spec audit (Phase 0.7): BLOCKED → single
remediation pass (F1–F5, all user-decided) → spec FROZEN (commit fabe6bf).
Nothing implemented yet; development entered at Vision GO 2026-07-02.

- **PRD:** `docs/prd/bazi-hehun.prd.md` (Status: `user-confirmed`, 2026-07-02)
- **Canvas:** `docs/canvas/bazi-hehun.canvas.md` (Status: `user-confirmed`, re-confirmed 2026-07-02 after D1–D8 amendment)
- **Vision:** `docs/vision/bazi-hehun.vision.md` (Status: `user-confirmed`, 2026-07-02 — unedited by the amendment; VIS-004's "or canonical raw charts" clause deferred by D2)
- **Council verdict:** `docs/concilium/2026-07-02-bazi-hehun-challenge.md` (user decision: ADOPT ALL, D1–D8)
- **Ledger:** `docs/governance/bazi-hehun.missing-assumption-blocker-ledger.md` (MISSING-001..005 open; OQ-001/OQ-003 open; OQ-002 and CONTRA-001 resolved 2026-07-02; ASSUMPTION-001 verified-at-code-level; Decisions section added 2026-07-02)
- **Spec audit:** `docs/audits/2026-07-02-bazi-hehun-spec-audit.md` (Phase 0.7 — verdict BLOCKED; F1/F2 blockers resolved by explicit user decisions 2026-07-02, remediated in the single pass; gate does not re-run)

### Canvas traceability fields (shared across REQ-001..REQ-016 — same canvas, same increment)

Unless a per-REQ exception is listed below the table, these six values apply to every REQ in this section.

| Field | Value |
|---|---|
| `canvas-link` | `docs/canvas/bazi-hehun.canvas.md` (Status: `user-confirmed`, re-confirmed 2026-07-02 after D1–D8 amendment) |
| `canvas-problem` | CAN-001 — FuFirE lacks the requested deterministic BaZi-Hehun pair-analysis endpoint and frontend visibility for it. (Council finding 6: problem statement is supply-side/circular; demand falsifier CAN-014 added as counterweight.) |
| `canvas-target-user` | CAN-002 — API consumers, frontend landingpage users, and coding agents implementing the feature. |
| `canvas-value-claim` | CAN-003 — deterministic, source-status-labelled raw pair analysis without unsupported fate/relationship claims; bounded by CAN-005 (score fields omitted, D1), CAN-007 (birth_input-only, D2), CAN-012 (three MVP layers only, D3). Per-REQ anchor in the "canvas-item" column of the core matrix. |
| `canvas-success-signal` | CAN-011 (supply-side: OpenAPI path, Hehun frontend visibility, non-heuristic raw analysis, no raw-birth-data logging) + CAN-014 (demand-side, ASSUMPTION per D6: ≥10 external non-team calls within 30 days of landingpage visibility — threshold pending user confirmation). |
| `canvas-risk-status` | aligned — RISK-001..004 carried into PRD Risks with amended mitigations (D1/D2/D5/D7); no open BLOCKER (audit F1/F2 resolved by user decisions 2026-07-02); OQ-001 gates PUBLIC LAUNCH only (D5) — public launch = feature-flag flip, gated on OQ-001 + user sign-off (CAN-015, AC-011g/h); MISSING-001..003 gate only the deferred matrices/scoring, not the MVP layers. |

Per-REQ exceptions:

- REQ-016 `canvas-risk-status`: aligned-deferred — P2 future feature anchored to CAN-010 (ASSUMPTION); requires its own privacy/security PRD and legal review (AC-016e) before any implementation.
- REQ-015 `canvas-success-signal`: no canvas-level signal exists for latency; performance target is an enabling NFR with its full-request p95 target explicitly MISSING until a live baseline exists (AC-015c).

### Core matrix

STATUS (updated 2026-07-03, after Milestone C / Gate A): the backend increment is built and wired through the production composition root (`bazi_engine/app.py` `include_router(match.router, prefix="/v1")`, DECISION-001 /v1-only). The AUTHORITATIVE per-REQ evidence source is `docs/reality/bazi-hehun.evidence.jsonl` (`plumbline-reality-check`); the columns below are reconciled to it. `wired-in-prod?` = **yes (app.py composition root, in-process TestClient)** for the backend-reachable REQs; `evidence-class` = **integration-fake** (assembled FastAPI app, MOSEPH fallback, honest ephemeris skips) — NOT `integration`/real-boundary, which stays honestly deferred to T22 (MISSING-005). Frontend REQs (REQ-010 AC-010b, REQ-011) are Milestone D — not yet built. Backend Gate A independently re-run by the orchestrator 2026-07-03: full suite 2657 passed / 61 skipped / 1 xfailed, ruff clean, mypy 1 pre-existing out-of-scope error only, OpenAPI drift-check OK, coverage 91%. Test IDs are planned test locations per the approved allowed-change-scope (`tests/test_match_*.py`); frontend tests (AC-010b under REQ-010, and REQ-011 incl. the AC-011g/h feature-flag tests) live in the frontend repo `/Users/benjaminpoersch/Projects/SaaS/FuFirEProject/Fufire_API-landingpage`, which is IN the approved allowed change scope since 2026-07-02 (audit F1, user-approved expansion — see the canvas "Frontend repo" subsection; enforced procedurally via the changed-files list until per-repo tooling exists) — noted per row.

Evidence-register coverage note: EV-001..EV-005 appear in per-row `evidence-needed` cells. EV-006 is this matrix itself (coverage of every REQ — satisfied by this document, not a row cell). EV-007 (demand-side, post-launch, D6; threshold ≥10/30d = ASSUMPTION-003, user-confirmed 2026-07-02) anchors to CAN-014 and is tracked in the open-items table below — post-launch evidence, attaches to no pre-launch REQ row. EV-007 measurement mechanism (user-decided 2026-07-02, audit F4): external-call attribution via API-key allowlist — calls authenticated with API keys outside the maintained team/admin key allowlist count as external; counts + key-tier only, no PII (AC-013d; planned test `tests/test_match_observability.py`).

| REQ | canvas-item | acceptance-criteria | test IDs (planned, not implemented) | evidence-needed | wired-in-prod? | evidence-class |
|---|---|---|---|---|---|---|
| REQ-001 | CAN-004, CAN-008 | AC-001a, AC-001b, AC-001c, AC-001d | `tests/test_match_contract.py` (route + OpenAPI path); frontend label test in frontend repo | EV-001, EV-003 | yes — app.py composition root (in-process) | integration-fake (assembled app; real-boundary deferred T22) |
| REQ-002 | CAN-007 (D2) | AC-002a, AC-002b, AC-002c, AC-002d | `tests/test_match_schema.py` (birth_input required fields; raw_bazi rejected 422; no CanonicalBaziChartInput in OpenAPI) | EV-002 | yes — app.py composition root (in-process) | integration-fake (assembled app; real-boundary deferred T22) |
| REQ-003 | CAN-006 | AC-003a, AC-003b, AC-003c, AC-003d | `tests/test_match_service_boundary.py` (+ existing `tests/test_golden.py` unchanged as regression anchor) | EV-002 | yes — app.py composition root (in-process) | integration-fake (assembled app; real-boundary deferred T22) |
| REQ-004 | CAN-004, CAN-006 | AC-004a, AC-004b, AC-004c | `tests/test_match_normalization.py` | EV-002 | yes — app.py composition root (in-process) | integration-fake (assembled app; real-boundary deferred T22) |
| REQ-005 | CAN-004, CAN-012 | AC-005a, AC-005b, AC-005c | `tests/test_match_individual_analysis.py` | EV-002 | yes — app.py composition root (in-process) | integration-fake (assembled app; real-boundary deferred T22) |
| REQ-006 | CAN-012 (D3) | AC-006a, AC-006b, AC-006c, AC-006d | `tests/test_match_pair_layers.py` (exactly 3 layers; no matrix layers; no MISSING_INTERACTION_TABLE stubs) | EV-002, EV-004 | yes — app.py composition root (in-process) | integration-fake (assembled app; real-boundary deferred T22) |
| REQ-007 | CAN-005 (D1) | AC-007a, AC-007b, AC-007c, AC-007d, AC-007e | `tests/test_match_score_absence.py` (schema + response key-absence; lexical blocked-language scan) | EV-004 | yes — app.py composition root (in-process) | integration-fake (assembled app; real-boundary deferred T22) |
| REQ-008 | CAN-004 (D4 scope cut) | AC-008a, AC-008b, AC-008c | `tests/test_match_raw_blocks.py` (block schema fields; no LLM-readiness claim in schema/docs/examples) | EV-002 | yes — app.py composition root (in-process) | integration-fake (assembled app; real-boundary deferred T22) |
| REQ-009 | CAN-004 | AC-009a, AC-009b, AC-009c, AC-009d | `tests/test_match_errors.py` (422 shapes; deferred-mode rejection; no PII echo) | EV-002, EV-005 | yes — app.py composition root (in-process) | integration-fake (assembled app; real-boundary deferred T22) |
| REQ-010 | CAN-004 | AC-010a, AC-010b, AC-010c, AC-010d | `tests/test_match_contract.py` + `scripts/export_openapi.py --check`; frontend snapshot sync verified in frontend repo | EV-001 | backend: yes (app.py) / frontend snapshot: Milestone D | backend integration-fake; frontend not built |
| REQ-011 | CAN-008 (D7), CAN-013, CAN-015 (F2) | AC-011a, AC-011b, AC-011c, AC-011d, AC-011e, AC-011f, AC-011g, AC-011h | Frontend repo tests (catalog category/label/subtitle, SchemaForm consent field, proxy allowlist; feature-flag tests: default OFF in production, flag OFF hides the endpoint from the catalog UI, flag ON shows it under Hehun with honest subtitle — AC-011g/h); backend side covered by `tests/test_match_contract.py` tag assertions | EV-003 | yes — frontend built, flag DEFAULT OFF (launch deferred) | integration-fake (vitest 1060 pass; llms leak-guard proven; real-boundary + launch deferred T22) |
| REQ-012 | CAN-009, CAN-013 (D5) | AC-012a, AC-012b, AC-012c, AC-012d, AC-012e, AC-012f | `tests/test_match_privacy.py` (consent-boolean 422 contract test; log-redaction; hash-only consent logging) | EV-005 | yes — app.py composition root (in-process) | integration-fake (assembled app; real-boundary deferred T22) |
| REQ-013 | CAN-004, CAN-014 (EV-007 mechanism) | AC-013a, AC-013b, AC-013c, AC-013d | `tests/test_match_observability.py` (evidence_ledger completeness; no personal data in metrics; team-vs-external classification via API-key allowlist, counts + key-tier only — AC-013d) | EV-002, EV-005, EV-007 (mechanism only — demand evidence itself is post-launch) | yes — app.py composition root (in-process) | integration-fake (assembled app; real-boundary deferred T22) |
| REQ-014 | CAN-003, CAN-005 | AC-014a, AC-014b | `tests/test_match_determinism.py` (canonical hash stability; fixture snapshots) | EV-002 | yes — app.py composition root (in-process) | integration-fake (assembled app; real-boundary deferred T22) |
| REQ-015 | CAN-004 | AC-015a, AC-015b, AC-015c | `tests/test_match_perf.py` (purity + metrics emission); live p95 baseline MISSING until deployment (AC-015c) | EV-002 (partial — live baseline evidence MISSING) | yes — purity/metrics asserted (app.py) | integration-fake; live p95 (AC-015c) deferred T22 |
| REQ-016 | CAN-010 (P2 future) | AC-016a, AC-016b, AC-016c, AC-016d, AC-016e | none — deferred; requires separate privacy/security PRD before any test/impl work | none in this increment (separate PRD + legal review required) | no — not implemented (deferred P2) | none — pre-implementation |

### True-Line fields (per REQ)

`vision-link` = `docs/vision/bazi-hehun.vision.md` (Status: `user-confirmed`, 2026-07-02) for every REQ; the VIS anchor per REQ is listed below. `true-line-status` = **pending** for every REQ (no value check has run — pre-implementation).

| REQ | vision-link (VIS anchor) | value-check-id | true-line-status |
|---|---|---|---|
| REQ-001 | `docs/vision/bazi-hehun.vision.md` — VIS-005 | VC-REQ-001 | pending |
| REQ-002 | `docs/vision/bazi-hehun.vision.md` — VIS-004 (raw-chart clause deferred by D2) | VC-REQ-002 | pending |
| REQ-003 | `docs/vision/bazi-hehun.vision.md` — VIS-007 | VC-REQ-003 | pending |
| REQ-004 | `docs/vision/bazi-hehun.vision.md` — VIS-004, VIS-007 | VC-REQ-004 | pending |
| REQ-005 | `docs/vision/bazi-hehun.vision.md` — VIS-004 | VC-REQ-005 | pending |
| REQ-006 | `docs/vision/bazi-hehun.vision.md` — VIS-003, VIS-004 | VC-REQ-006 | pending |
| REQ-007 | `docs/vision/bazi-hehun.vision.md` — VIS-005, VIS-006 | VC-REQ-007 | pending |
| REQ-008 | `docs/vision/bazi-hehun.vision.md` — VIS-003, VIS-004 | VC-REQ-008 | pending |
| REQ-009 | `docs/vision/bazi-hehun.vision.md` — VIS-005 | VC-REQ-009 | pending |
| REQ-010 | `docs/vision/bazi-hehun.vision.md` — VIS-005 | VC-REQ-010 | pending |
| REQ-011 | `docs/vision/bazi-hehun.vision.md` — VIS-002, VIS-005 | VC-REQ-011 | pending |
| REQ-012 | `docs/vision/bazi-hehun.vision.md` — VIS-008 | VC-REQ-012 | pending |
| REQ-013 | `docs/vision/bazi-hehun.vision.md` — VIS-005 | VC-REQ-013 | pending |
| REQ-014 | `docs/vision/bazi-hehun.vision.md` — VIS-001, VIS-005 | VC-REQ-014 | pending |
| REQ-015 | `docs/vision/bazi-hehun.vision.md` — VIS-004 (no dedicated vision item; enabling NFR) | VC-REQ-015 | pending |
| REQ-016 | `docs/vision/bazi-hehun.vision.md` — VIS-008 | VC-REQ-016 | pending |

### Open items carried (not silently closed — see ledger for full detail)

| ID | Label | One-line |
|---|---|---|
| MISSING-001..003 | MISSING | Domain-approved interaction/Ten-Gods/DMS tables — gate the deferred matrices and any future scoring block, not the MVP layers (D3) |
| MISSING-004 / OQ-001 | MISSING / OPEN QUESTION | Legal/privacy-reviewed consent copy — gates PUBLIC LAUNCH, not the build (D5); public launch = feature-flag flip, gated on OQ-001 + user sign-off (CAN-015, AC-011g/h) |
| MISSING-005 | MISSING | Runtime evidence from deployed backend + landingpage — gates any Done claim |
| OQ-003 | OPEN QUESTION | Domain source for later interaction/scoring table approval |
| ASSUMPTION-003 | CONFIRMED | D6 demand threshold (≥10 external calls / 30 days) — explicitly accepted by the user at canvas re-confirmation 2026-07-02; measurable via the AC-013d API-key-allowlist attribution (audit F4) |
| ASSUMPTION-001 | VERIFIED (code-level) | Chart-computation reuse verified 2026-07-02: `bazi_engine/routers/bazi.py:379` calls pure `compute_bazi()`; residual for planning: AC-003c normalization equivalence requires reusing shared response-shaping helpers, not copying them |
| F1 | RESOLVED (was BLOCKER) | Frontend repo unnamed in spec — resolved 2026-07-02 by user decision: frontend repo added to the canvas Allowed change scope ("Frontend repo" subsection); council cost-saver 9 annotated FALSIFIED in the concilium report |
| F2 | RESOLVED (was BLOCKER) | Public-launch boundary undefined — resolved 2026-07-02 by user decision: CAN-015 feature flag, default OFF in production; flip = PUBLIC LAUNCH, gated on OQ-001 + explicit user launch sign-off (AC-011g/h) |
| DECISION-001 | DECISION | `/v1/match/bazi-hehun` mounted /v1-ONLY (audit F3) — deliberate, documented deviation from the repo dual-mount idiom (precedent: admin router); recorded in PRD "Decisions" and the ledger |
| — | GATE (CLEARED 2026-07-02) | Canvas re-confirmation by user — given 2026-07-02 with the exact required phrase |
| — | GATE (CLEARED 2026-07-02, pending freeze) | Phase-0.7 spec audit — verdict BLOCKED; F1/F2 resolved by explicit user decisions, remediated in the single pass 2026-07-02; gate does not re-run; spec freezes after this pass |

---


## Feature: `fufire-premium-verification-ci` — increment 1 (WS-A: attestation end-to-end)

Status: user-confirmed (Canvas, PRD, and Vision all user-confirmed 2026-07-01)

- **PRD:** `docs/prd/fufire-premium-verification-ci.prd.md` (Status: `user-confirmed`, 2026-07-01)
- **Canvas:** `docs/canvas/fufire-premium-verification-ci.canvas.md` (Status: `user-confirmed`, 2026-07-01)
- **Vision:** `docs/vision/fufire-premium-verification-ci.vision.md` (Status: `user-confirmed`,
  2026-07-01 — confirmed together with the PRD via the orchestrator's confirmation prompt.)
- **Council verdict:** `docs/archive/2026-07-01-fufire-premium-verification-ci.md` (SHARPEN, user approved "proceed")

### Canvas traceability fields (shared across both REQs — same canvas, same increment)

| Field | Value |
|---|---|
| `canvas-link` | `docs/canvas/fufire-premium-verification-ci.canvas.md` |
| `canvas-problem` | G3 — "Attestierung nicht end-to-end": `assert_no_moseph_fallback` exists but unconfirmed coverage across all `swe.calc_ut`/`swe.houses`/`swe.fixstar` paths; `tzdb_version_id` sometimes `"unknown"` (canvas §1) |
| `canvas-target-user` | Broad — any paying FuFirE API customer/integrator, not BFF-specific (canvas §2, user-decided 2026-07-01) |
| `canvas-value-claim` | A paid response can structurally never originate from unrequested MOSEPH; every response exposes real (never `"unknown"`) `ephemeris_mode`/`house_system_fallback`/`ephemeris_id`/`tzdb_version_id` (canvas §4) — **baseline guarantee for all paying customers, not a premium-tier differentiator** (council sharpen #1) |
| `canvas-success-signal` | `pytest tests/test_ephemeris_attestation.py -q` green; AST/grep guard shows 0 direct `swe.calc*`/`houses*`/`fixstar*` outside `ephemeris.py`; per-endpoint attestation contract test green; `scripts/export_openapi.py --check` green (canvas §5). **Phase 1 planning confirmed** (2026-07-01): `routers/chart.py` (`ChartResponse`) and all of `routers/transit.py`'s response models lack `quality_flags`/`provenance` entirely — same gap class as `BaziResponse`/`WxResponse`/`TSTResponse`, added to T9's scope (`docs/plans/2026-07-01-fufire-premium-verification-ci.md`). |
| `canvas-risk-status` | Risks recorded canvas §8 (rollout-breaks-prod, flag-less houses/fixstar design gap, response-field additive-change risk, tzdata-pin decision) — all carried into PRD §§6, 8, 10; none unresolved as `BLOCKER` |

### Core matrix

| REQ | acceptance-test | impl-task | evidence | wired-in-prod? | evidence-class |
|---|---|---|---|---|---|
| `FQ-ATT-01` | AC-01-1 … AC-01-6 (PRD §7) | T1–T6, T12 (PRD §11) | `tests/test_ephemeris_attestation.py` (11 tests green), `tests/test_ephemeris_guard_ast.py` (AST guard, live-violation demonstrated), `tests/test_ephemeris_concurrency.py` (2 tests green), `tests/test_ephemeris_fallback.py` (24+ tests green, patch targets migrated) — full merged suite 2743 passed/0 failed 2026-07-08. `docs/reality/fufire-premium-verification-ci.evidence.jsonl`. Live smoke 2026-07-08 against `https://api.fufire.space` (real prod key): `/v1/calculate/bazi` 2xx carries `ephemeris_mode=SWIEPH`, `ephemeris_id=swieph_sepl18`, no `house_system_fallback`; `/v1/calculate/tst` carries no `quality_flags`, real `provenance`. | **yes** — merged via PR #142 (base, 2026-07-07) + PR #145 (resume cycle, 2026-07-08); Railway deployment `SUCCESS` for commit `819a86e` (service `FuFire`) | **production-verified** (live endpoint smoke with real injected secrets, 2026-07-08) |
| `FQ-ATT-02` | AC-02-1 … AC-02-6 (PRD §7) | T7–T11, T12 (PRD §11) | `tests/test_attestation_contract.py` (24 tests green incl. tst no-swe-calc spy guard, value-level anchored to real pinned `tzdata`); `spec/openapi/openapi.json` regenerated + `--check` green; `pyproject.toml`/`requirements.lock`/`uv.lock` pin `tzdata>=2026.2`; `tests/test_security_findings.py` + `tests/test_dst_pii_http.py` (PII scrub proven at the real HTTP boundary). `docs/reality/fufire-premium-verification-ci.evidence.jsonl`. Live smoke 2026-07-08: `provenance.tzdb_version_id=2026.2` (never `"unknown"`); DST-gap/format/unknown-tz 422 bodies verified scrubbed on `/v1/calculate/bazi` and `/v1/calculate/bazi/dayun` (the route that leaked pre-deploy). | **yes** — PR #142 + PR #145; Railway deployment `SUCCESS` commit `819a86e` | **production-verified** (live endpoint smoke with real injected secrets, 2026-07-08) |

### True-Line fields (per REQ)

| REQ | vision-link | value-check-id | true-line-status |
|---|---|---|---|
| `FQ-ATT-01` | `docs/vision/fufire-premium-verification-ci.vision.md` (Status: `user-confirmed`) | VCHK-01a, VCHK-01b, VCHK-03, VCHK-04, VCHK-05, VCHK-07 — all confirmed PASS by independent re-verification (orchestrator + code-reviewer + plumbline-watcher + product-owner, each re-running tests themselves, 2026-07-01); resume-cycle chain re-run on the post-review diff 2026-07-08 (Watcher closure after ADR-2 user sign-off) | **true — production-verified 2026-07-08**; all CONTRAs resolved (`docs/contradictions/fufire-premium-verification-ci.contradictions.md`, incl. the 2026-07-08 resume-cycle section) |
| `FQ-ATT-02` | `docs/vision/fufire-premium-verification-ci.vision.md` (Status: `user-confirmed`, same vision doc, shared increment) | VCHK-02, VCHK-06 — confirmed PASS; VCHK-02 anchor tightened (`== importlib.metadata.version("tzdata")`) per code-reviewer mutation-test finding; live-verified `tzdb=2026.2` 2026-07-08 | **true — production-verified 2026-07-08** |

### Open items carried from PRD §9 (not silently closed — see PRD for full detail)

| ID | Label | One-line |
|---|---|---|
| OQ-1 | CONFIRMED (user, 2026-07-01) | Scope of `house_system_fallback`: house-computing endpoints only (western/fusion/chart/experience); absent on bazi/wuxing/tst |
| OQ-2 | OPEN QUESTION | Is `POST /validate` (BAFE) in scope for FQ-ATT-02? |
| OQ-3 | OPEN QUESTION (evidence-needed) | Do any downstream consumers actually read `quality_flags` today? (Not asserted either way.) |
| OQ-4 | Architecture decision (planner) | Mechanism choice for flag-checkable class (PRD §6.1, Option A vs. B) |
| OQ-5 | Architecture decision (planner) | Design for flag-less `houses*` class (PRD §6.2) |
| OQ-6 | Implementation detail (ADR-eligible) | Exact `tzdata` version to pin |
| OQ-7 | Implementation detail (ADR-eligible) | Hard-fail vs. fallback semantics for `_detect_tzdb_version()` |
| OQ-8 | Implementation detail (ADR-eligible) | Narrow `ephemeris_mode` type to `Literal["SWIEPH"]`? |

No `BLOCKER` currently open for this increment.
