# Product Vision — BaZi Hehun

Status: user-confirmed  
Feature Slug: `bazi-hehun`  
Generated: 2026-07-01T23:18:20Z  
Confirmed: 2026-07-02 by user (Ben)  
Readiness-Level: USER_CONFIRMED

Canvas: `docs/canvas/bazi-hehun.canvas.md`

## Product Vision Statement

VIS-001 — EXPLICIT: FuFirE provides an authentic BaZi Hehun capability for deterministic pair analysis while preserving source discipline, privacy, and non-fatalistic output boundaries.

## Target Group

VIS-002 — EXPLICIT: Developers and users of the FuFirE API landingpage who need a reproducible BaZi-based compatibility analysis endpoint.

## User Needs

VIS-003 — EXPLICIT: A user wants to compare two BaZi charts without receiving free-form, unverifiable, therapeutic, romantic, or fatalistic advice.

## Product Value

VIS-004 — EXPLICIT: The system converts two valid birth inputs or canonical raw charts into structured raw analysis blocks with provenance, warnings, and confidence/source-status separation.

## Business or Project Goals

- VIS-005 — EXPLICIT: OpenAPI-visible endpoint, frontend category Hehun, deterministic response schema, no heuristic scoring, privacy-safe logging, and traceable evidence per requirement.
- VIS-007 — EXPLICIT: Backend logic should be modular: calculation service, normalization, pair-comparison layers, raw-text generation, evidence and warning construction.

## Success Signals

- Endpoint appears in backend OpenAPI as `POST /v1/match/bazi-hehun`.
- Frontend landingpage shows category `Hehun` and visible endpoint label `BaZi Hehun`.
- Valid two-person input returns a deterministic raw-analysis response without heuristic score.
- Every output claim has source status, evidence ID or explicit uncertainty marker.
- Default logs contain request IDs, warning codes and hashes, not raw birth data.

## Boundaries

VIS-006 — EXPLICIT: No marriage guarantee, breakup prediction, health/wealth/fate claim, psychological diagnosis, or western synastry fusion in MVP.

## Assumptions

- ASSUMPTION: MVP can be valuable without numeric compatibility scores if raw layers are transparent and source-status-labelled.
- ASSUMPTION: Hehun is the preferred product term because the user resolved naming toward authenticity.
- ASSUMPTION: A canonical raw chart input is more sustainable than accepting full internal BaziResponse objects as external public contract.

## Missing Items

- MISSING: Final domain-verified interaction tables and scoring formulas.
- MISSING: Final legal/privacy review for second-person birth data consent.
- MISSING: Runtime proof in deployed FuFirE API and landingpage.

## Vision Item Register

| Vision ID | Field | Marker | Content |
| --- | --- | --- | --- |
| VIS-001 | Product Vision Statement | EXPLICIT | FuFirE provides an authentic BaZi Hehun capability for deterministic pair analysis while preserving source discipline, privacy, and non-fatalistic output boundaries. |
| VIS-002 | Target Group | EXPLICIT | Developers and users of the FuFirE API landingpage who need a reproducible BaZi-based compatibility analysis endpoint. |
| VIS-003 | User Need | EXPLICIT | A user wants to compare two BaZi charts without receiving free-form, unverifiable, therapeutic, romantic, or fatalistic advice. |
| VIS-004 | Product Value | EXPLICIT | The system converts two valid birth inputs or canonical raw charts into structured raw analysis blocks with provenance, warnings, and confidence/source-status separation. |
| VIS-005 | Success Signals | EXPLICIT | OpenAPI-visible endpoint, frontend category Hehun, deterministic response schema, no heuristic scoring, privacy-safe logging, and traceable evidence per requirement. |
| VIS-006 | Boundaries | EXPLICIT | No marriage guarantee, breakup prediction, health/wealth/fate claim, psychological diagnosis, or western synastry fusion in MVP. |
| VIS-007 | Sustainable Architecture | EXPLICIT | Backend logic should be modular: calculation service, normalization, pair-comparison layers, raw-text generation, evidence and warning construction. |
| VIS-008 | Data Ethics Boundary | EXPLICIT | Second-person birth data must not be entered unless the submitting user confirms awareness/consent; stored user-to-user matching is deferred to a separate PRD. |

## Confirmation Status

user-confirmed

Confirmed by user: yes  
Confirmed on: 2026-07-02  
Confirmer: Ben (product owner)  
Confirmation note: exact required phrase given — "Ich bestätige, dass Product Canvas und Product Vision meine Absicht korrekt wiedergeben und als Grundlage für AgileTeam Planning verwendet werden dürfen."
