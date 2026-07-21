# Strategy Decision (Phase 2): New Core + Adapter (Option B)

Decision: Option B) New Core + Adapter layer inside this repo.

## Options considered

A) Refactor-in-place in V2
- Pros: minimal packaging changes
- Cons: high conflict density (network downloads, hour rule, lack of /validate contract), hard to keep legacy API stable while enforcing strict contract-first behavior.

B) New Core + Adapter (chosen)
- Implement spec-conform core modules (validator, mapping, refdata policy, ruleset loader) as a new internal package.
- Keep legacy API endpoints as best-effort (or clearly marked legacy), but route new /validate to the new core.
- Pros: clean separation, deterministic tests, easier rollback, contract-first.
- Cons: some duplication until legacy endpoints are migrated.

C) Scratch (new repo)
- Pros: cleanest
- Cons: breaks integration requirement; higher operational risk; migration burden.

## Why Option B wins

Hard criteria:
- Coupling: legacy code is coupled to SwissEph + implicit file bootstrap (network). Decoupling is safest via a new core.
- Contract compliance: /validate + schemas + evidence is easiest to implement from scratch with dedicated models.
- Testability: acceptance tests TV/PT can target the new core deterministically using overrides.

## Implementation plan mapping (epics)

- E0: Implement /validate skeleton + schema validation + response schema self-check
- E1-mini: Implement RefData policy checks + network guard (no downloads)
- E4: Implement canonical branch mapping + forbidden mixing detector
- E3-lite: Implement ruleset loader (standard_bazi_2026) + hidden stems mapping
- E2: Implement DST fold/gap detection + TLST hour rule for discretization evidence
- E5a/E5b: Implement kernel + harmonics features (invariant checks)

## Rollback plan

- Keep legacy endpoints untouched behind a feature flag if needed.
- /validate is additive: safe to deploy without breaking existing clients.
