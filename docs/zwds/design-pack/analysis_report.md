# ZWDS / FuFirE Re-Audit — Corrected Report

## Verdict

**CONDITIONAL GO** for a versioned `core-seed` natal calculator.  
**BLOCKED** for “complete”, “original”, “universal” or “unfallible” claims.

## Material corrections to the previous package

1. Added the missing `analysis_report.json`; the previous validation log falsely claimed it existed and validated.
2. Corrected the guide's row `庚 / 午`: `庚` is a Heavenly Stem; the seventh Earthly Branch is `午`. Stem, branch and zodiac animal are now separate typed IDs.
3. Corrected Ming/Shen test count from 120 to 144.
4. Reclassified the 150-case Zi Wei check as algebraic equivalence, not independent historical validation.
5. Removed unsupported DST options (`ambiguousTime=error`, `nonexistentTime=shift_backward`) to match FuFirE.
6. Removed public direct-lunar input; it allowed inconsistent caller-supplied calendar state.
7. Removed per-request ruleset overrides; they contradicted immutable ruleset reproducibility.
8. Replaced duplicate embedded star objects with one canonical placement collection plus palace references.
9. Split calculation success from source confidence.
10. Corrected late-Zi handling: advance/re-resolve the chart date through the calendar engine, never increment the lunar day in isolation.
11. Reduced MVP from three live endpoints to natal calculation plus ruleset metadata; dynamics and interpretation are deferred.

## Inputs

The corrected public request accepts civil local datetime, IANA timezone, coordinates, FuFirE-supported DST policies, ruleset ID and an explicit/traditional/omitted decadal direction method. Unknown birth time is not accepted by the full natal endpoint.

## Outputs

The corrected raw response contains:

- immutable ruleset, policy IDs and component hashes;
- normalized time/calendar resolution;
- 12 palaces;
- one canonical star-placement list;
- four natal transformations;
- 12 relation records;
- optional 12 decadal ranges;
- separate calculation/source/crosscheck statuses;
- provenance, trace and chart fingerprint.

## Formula status

- Ming/Shen: computationally coherent.
- Palace roles/stems: computationally coherent.
- Bureau: computationally coherent for 60 valid stem/branch parity pairs.
- Zi Wei/Tian Fu: 150-case algebraic equivalence passed.
- 14 major stars: offset translation matches the guide and implementation comparator.
- Four guide auxiliaries: formula translation passes 144 month/hour cases.
- Four Transformations: table is school/source-specific and must be versioned.
- Decadal rules: ruleset candidate, not universal truth.

## Claims

The guide's historical and marketing claims are not suitable as technical requirements. The full disposition is in `claim_audit.md` and `claim_audit.csv`.

## Architecture decision

Implement the smallest reversible slice:

1. source-governed ruleset repository;
2. deterministic Chinese lunisolar calendar provider;
3. natal core engine;
4. `/v1/calculate/zwds`;
5. `/v1/metadata/zwds/rulesets/{ruleset_id}`.

Only after golden-chart review should dynamics or narrative interpretation be added.

## Remaining blockers

- named school/edition or explicit `core-seed` positioning;
- selected calendar engine and independent boundary corpus;
- source-reviewed full star catalog;
- source-reviewed brightness/dignity tables if claimed;
- selected transformation table;
- practitioner-reviewed golden charts.

## Release decision

`core-seed`: **REVISE THEN RELEASE**.  
`complete original ZWDS`: **BLOCK**.
