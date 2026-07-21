# Spec-Sanity Audit (Phase 0.7) — bazi-hehun

Date: 2026-07-02  
Auditor: `spec-auditor` (ultrathink-craftsmanship FULL mode, run exactly once — no re-run) + konfabulations-audit  
Verdict: **BLOCKED** (2 blockers, both remediable without touching user decisions D1–D8)  
Remediation budget: exactly ONE pass by `requirements-analyst`, then the spec freezes.

## Konfabulations-audit (claim provenance)

| # | Claim | Classification | Evidence / action |
|---|---|---|---|
| 1 | `routers/bazi.py` calls pure `compute_bazi()` (RISK-005/ASSUMPTION-001) | belegt | `bazi_engine/routers/bazi.py:379`. ASSUMPTION-001 can close. |
| 2 | "No extraction refactor needed" (council cost-saver 8, strong form) | ableitbar | Chart-computation reuse real; response shaping (format_pillar/trace/provenance) is router-embedded — AC-003c normalization equivalence still needs shared-helper reuse. Keep "verify at planning" hedge. |
| 3 | `standard_bazi_2026.json` has no interaction/Ten-Gods tables (D3) | belegt | 14 top-level keys, zero hits for interact/ten_god/shensha/chong/combin. |
| 4 | FuFirE endpoint contracts freeze on release (D1) | belegt | Repo CLAUDE.md OpenAPI section ("Endpoints are frozen"). |
| 5 | Routers dual-mounted legacy + /v1 (SRC-004) | belegt | `app.py:324-355`. See F3 idiom conflict. |
| 6 | ErrorEnvelope/problem-style 422 behavior (REQ-009) | belegt | `routers/shared.py:46`, `app.py:227,472,489,524`. |
| 7 | Frontend catalog derives categories from OpenAPI tags | belegt (weak form) | `Fufire_API-landingpage/src/lib/endpoint-catalog.ts:42-77` — explicit `TAG_TO_CATEGORY` map; unmapped tags fall back to **"Raw Data"**. |
| 8 | "Zero custom frontend code beyond consent field" (council cost-saver 9) | **nicht behaupten — FALSIFIED** | New `Hehun` tag is unmapped → renders "Raw Data". Needs `TAG_TO_CATEGORY` entry + category-union extension + subtitle copy. → F1. |
| 9 | Proxy validates path+method against loaded OpenAPI, fail-closed | belegt | `src/server/app.ts:1056-1107`. |
| 10 | Frontend snapshots public/openapi.json + src/api/openapi.json exist | belegt | ls confirmed. |
| 11 | SchemaForm renders nested objects + booleans generically | belegt | `src/lib/form-spec.ts`, `SchemaForm.tsx:129,164`. |
| 12 | /v1/calculate/bazi + /trace exist | belegt | openapi.json paths. |
| 13 | Single-chart Wu-Xing vector exists | belegt | `bazi_engine/wuxing/vector.py`. |
| 14 | Day-cycle anchor unverified → warnings premise | belegt | Ruleset `anchor_verification: "unverified"`. |
| 15 | "Landingpage visibility ≠ public launch" | **ungeprüft — load-bearing premise** | Landingpage deploys to production (railway.json); no artifact defines the launch boundary. → F2. |
| 16 | EV-007 "external (non-team) calls" measurable | ungeprüft | No attribution mechanism defined. → F4. |
| 17 | 合婚 = marriage matching (D7) | ungeprüft | No propagation risk — adopted mitigation is stricter than the claim requires. |
| 18 | GDPR Art. 7/14 statements (council) | ungeprüft | Correctly handled — spec keeps legal adequacy OPEN (OQ-001), never asserts it. |
| 19 | Spouse-palace layer "source-verified" | ableitbar (computed facts) / nicht behaupten (interpretive) | No spouse-palace table in ruleset; layer must stay computed facts + source_status. AC-005c guards. → F7 note. |
| 20 | SRC-007 sprint-plan gap | ungeprüft | Not premise-bearing. |
| 21 | PRD Links say Canvas "draft — pending re-confirmation" (prd.md:204,209) | nicht behaupten (stale) | Contradicts re-confirmed canvas. → F5. |

Premise-poisoning: claims **#8 and #15** are ungeprüft/falsified AND load-bearing → blockers.

## Ultrathink findings

Bias hooks: authority bias (council cost-savers carried unverified — #8 falsified); look-where-the-light-is (frontend repo never named despite two P0 REQs living there); anchoring (AC-001c vs repo dual-mount idiom, unacknowledged conflict); completion-pressure doc lag (stale PRD refs); overengineering pruned by D1–D3.

Failure-mode chains → coverage:
- **A build=launch** (consent ships → visibility merge → production deploy → public exposure with unreviewed legal copy → OQ-001 bypassed by pipeline): **UNCOVERED** → F2.
- **B "Raw Data" mislabel** (builder trusts cost-saver 9 → backend tag only → category falls back → AC-011b/f fail late, frontend outside scope): **surface UNCOVERED** → F1.
- **C score reintroduction**: COVERED (AC-007a–e, EV-004, planned score-absence test, frozen contract).
- **D mount-idiom conflict** (builder follows CLAUDE.md → dual-mounts → AC-001c fails → rework loop): decision unrecorded → F3.
- **E ephemeris-mode divergence** (match response lacks `quality_flags.ephemeris_mode` attestation single-chart has): partial → F8 note.
- **F 422 echoes birth data**: COVERED (AC-009d + planned error tests).
- **G demand falsifier unmeasurable** (no team/external attribution → EV-007 degrades to vibes): **UNCOVERED** → F4.

## Findings

| ID | Severity | Finding |
|---|---|---|
| F1 | **BLOCKER** | REQ-010(AC-010b)/REQ-011 (P0) require changes in the frontend repo `/Users/benjaminpoersch/Projects/SaaS/FuFirEProject/Fufire_API-landingpage`, which no spec artifact names, scopes, or tasks; council cost-saver 9 ("zero custom frontend code") is falsified. Build would violate the D8 scope guard or ship "BaZi Hehun" under "Raw Data". Remediation: name the repo, define its allowed change scope (user approval required per D8 expansion rule), annotate cost-saver 9 as falsified. |
| F2 | **BLOCKER** | Premise "landingpage visibility ≠ public launch" is ungeprüft and load-bearing: EV-003/CAN-011 make frontend visibility a build deliverable on a production-deployed site while OQ-001 only gates "PUBLIC LAUNCH" — boundary undefined. D5 stands; a mechanical gate (flag / staging / explicit user launch sign-off before the visibility merge deploys) must be specified. |
| F3 | important | AC-001c (/v1-only unless DECISION) contradicts repo CLAUDE.md dual-mount idiom. Record one explicit decision. |
| F4 | important | EV-007 has no measurement mechanism ("external non-team" attribution undefined; REQ-013 emits no caller classification). Add one observability AC or the confirmed falsifier is unfalsifiable. |
| F5 | minor | Stale PRD cross-references (prd.md:204,209) say canvas is draft. Fix in remediation pass. |
| F7 | note | Spouse-palace layer: "source-verified" only for computed identification facts; keep layer to computed facts + source_status (AC-005c guards). Domain validity stays with MISSING-001..003. |
| F8 | note | Match response should carry `quality_flags.ephemeris_mode` attestation like single-chart responses, so REQ-014 determinism is environment-honest. Make explicit at planning (fits REQ-004 provenance). |

## Verdict

**BLOCKED** → exactly one remediation pass (requirements-analyst) covering F1, F2 (+ F3 decision, F4 measurement AC, F5 doc-sync), then the spec freezes. This gate does not re-run.

Hard limit, stated honestly: this audit checked reasoning quality and claim provenance only. It proves nothing about functional correctness, BaZi domain correctness (MISSING-001..003), legal adequacy (OQ-001), or the deployed system — those belong to downstream gates. A green post-remediation state must not be read as "the system works."
