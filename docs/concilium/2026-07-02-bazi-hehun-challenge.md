# Council Challenge Gate (Phase 0.16) — bazi-hehun

Date: 2026-07-02  
Mode: `concilium --mode=challenge` (Challenger · Advisor · Critic)  
Bound: ≤180 words/role/round, 2 collision rounds (both used)  
Real consumed cost: 6 agents, 378,823 subagent tokens, ~224s wall-clock  
Basis: user-confirmed Canvas + Vision (2026-07-02), draft PRD  
User decision (2026-07-02, via explicit steering choice): **ADOPT ALL** —
scope cuts 1–3, safety fixes 4–5, positioning 6–7 all adopted; the orchestrator's
proposed Allowed-change-scope section was approved as written. Consequence per
governance: the Canvas is amended, returns to `draft`, and requires explicit user
re-confirmation before the Development entry condition can be met.

## Surviving points after collision round 2

### Converged / unrebutted — HIGH

1. **Omit score fields instead of always-null** (Challenger + Advisor converged).
   FuFirE endpoints are contract-frozen on release; shipping always-null
   `total_score`/`sub_scores`/`score_class` freezes a scoring shape before any scoring
   model exists. Fix: omit score fields from the MVP response schema entirely; add a
   versioned scoring block additively once source-approved rulesets exist.
   Touches: CAN-005 wording, REQ-007/AC-007*.

2. **birth_input-only MVP; defer raw_bazi mode** (Advisor, unrebutted; decides OQ-002).
   `CanonicalBaziChartInput v0.1` is new versioned public contract surface with no
   confirmed consumer. Cutting it halves schema/validation/fixture work; raw_bazi can be
   added later additively. Touches: CAN-007, REQ-002 (AC-002b/d).

3. **Ship only fully-populated layers; drop the five REQ-006 matrices** (Advisor,
   code-verified: `spec/rulesets/standard_bazi_2026.json` contains no branch/stem
   interaction or Ten-Gods tables — all five matrices would emit only
   `MISSING_INTERACTION_TABLE` placeholders). MVP layers: Day Master comparison,
   spouse-palace/day-branch facts, Wu-Xing vector comparison. Matrices return when
   tables are domain-approved (MISSING-001..003). Touches: REQ-006.

4. **Strike the LLM-readiness claim from AC-008b** (Challenger + Critic converged,
   Advisor conceded). "Interpretation-ready for downstream LLM/Fusion usage" relocates
   the no-advice boundary one hop to an uncontrolled LLM; the real deliverable would be
   an unwritten LLM-context contract. Fix: AC-008a block schema stays the contract;
   LLM consumption gets its own gated spec outside this endpoint. Touches: REQ-008/AC-008b.

5. **Consent: enforce server-side, but legality stays a launch gate** (all three roles).
   A's checkbox is attestation, not B's GDPR Art.-7 consent; Art.-14 duty to inform B
   unaddressed. Fix: required request boolean (422 when false, hash-logged) closes the
   direct-API bypass and makes AC-012c a backend contract test — but OQ-001 (legal
   review) gates PUBLIC LAUNCH, independent of build. Touches: REQ-012.

### User-judgment — positioning (medium)

6. **Demand evidence absent / success unfalsifiable** (Challenger unrebutted + Critic).
   CAN-001 is circular ("endpoint doesn't exist"); sole demand source is the user's own
   draft (SRC-001); all success signals are supply-side. Proposal: add one falsifiable
   demand signal (e.g. N external calls within 30 days) or classify consciously as
   infrastructure, not product.

7. **"Hehun" framing designs in an expectation break** (Critic, unrebutted).
   合婚 literally means marriage matching; the category name promises what
   NOGOAL-002/VIS-006 forbid, and the RISK-004 subtitle "compatibility analysis"
   deepens it. Proposal: honest subtitle ("deterministic pair-chart facts, no score").

### Cost-savers (no canvas change needed)

8. No service-extraction refactor needed: `routers/bazi.py` already calls pure
   `compute_bazi()` — RISK-005's "extract first" step is already satisfied.
9. ~~Frontend "Hehun" category rides the existing OpenAPI-tag→catalog pipeline
   (`_openapi_tags()` in app.py + operation tag + snapshot sync); zero custom frontend
   code beyond the consent field, which the generic SchemaForm renders automatically.~~
   **FALSIFIED** — spec-audit konfabulation claim 8, 2026-07-02
   (`docs/audits/2026-07-02-bazi-hehun-spec-audit.md`): the catalog uses an explicit
   `TAG_TO_CATEGORY` map (`Fufire_API-landingpage/src/lib/endpoint-catalog.ts:42-77`);
   unmapped tags fall back to **"Raw Data"**. A new `Hehun` tag therefore requires a
   `TAG_TO_CATEGORY` entry + category-union extension + subtitle copy (plus, per user
   decision F2, the feature-flag mechanism — CAN-015). Frontend repo added to the
   allowed change scope by user decision 2026-07-02 (audit F1). Annotation only; the
   original council text is preserved above per governance.

## Governance notes

- Council suggests only; no artifact was auto-edited. User reclassifies.
- The earlier "≤ ~15k tokens total" bound remains withdrawn; real cost reported above.
