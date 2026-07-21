# Corrected FuFirE ZWDS Backend Architecture

## Decision

**CONDITIONAL GO** for a small, versioned calculation bounded context.  
**BLOCKED** for claims of a universal, original or complete Zi Wei Dou Shu engine.

## MVP endpoint surface

### 1. `POST /v1/calculate/zwds`

Returns a natal raw chart for one immutable `ruleset_id`.

### 2. `GET /v1/metadata/zwds/rulesets/{ruleset_id}`

Returns ruleset version, hashes, policy IDs, declared star families, source ledger and release status.

### Deferred

- `/v1/calculate/zwds/dynamics`
- `/v1/interpret/zwds`

Deferring these is intentional. It prevents an unstable natal contract from being multiplied across yearly/monthly/daily layers and keeps interpretation claims outside the computation core.

## Public input decision

The public natal endpoint accepts **civil birth data only**. A direct lunar/replay seed is an internal test DTO, not a normal public input. This prevents callers from supplying mutually inconsistent lunar dates, year cycles, time standards and late-Zi decisions.

Required public birth fields:

- local datetime;
- IANA timezone;
- latitude/longitude;
- DST ambiguity choice: `earlier | later`;
- nonexistent-time policy: `error | shift_forward`;
- sex-at-birth only when the selected traditional direction method is used.

This aligns with the current FuFirE `resolve_local_iso` capabilities. The previous schema incorrectly offered unsupported `ambiguousTime=error` and `nonexistentTime=shift_backward` values.

## Ruleset immutability

Remove per-request policy overrides from the production endpoint. A request chooses one `ruleset_id`; the response returns its full effective fingerprint, including component hashes for the star catalog, transformation table, calendar policy and time policy.

Why: combining an immutable ruleset with arbitrary overrides creates an unbounded, unversioned ruleset and destroys reproducibility. Experimental variants should be materialized as new ruleset IDs.

## Response ownership

Use one canonical star-placement collection:

- `chart.star_placements[]` is the source of truth;
- each palace carries only `placement_ids[]` references.

The previous schema embedded full star objects both globally and inside palaces, allowing contradictory placements.

Use separate enums/types for `StemId`, `BranchId` and `AnimalId`. This directly blocks the guide's `庚 / 午` category error and branch/animal substitution.

Separate:

- `calculation_status`: whether the engine produced a result;
- `source_status`: whether the selected ruleset is sufficiently sourced;
- `crosschecks`: implementation comparison results.

Do not label a result `VERIFIED` merely because JSON Schema validation or deterministic computation succeeded.

## Package layout

```text
bazi_engine/
  zwds/
    __init__.py
    domain.py
    errors.py
    engine.py
    seed.py
    palace.py
    bureau.py
    relations.py
    transformations.py
    calendar_provider.py
    ruleset_repository.py
    trace.py
    validation.py
    stars/
      major.py
      auxiliary.py
  data/zwds/rulesets/<ruleset_id>/
    manifest.json
    palace_roles.json
    star_catalog.json
    bureau_table.json
    transformations.json
    placement_rules.json
    sources.json
  routers/zwds.py
  services/zwds_service.py
```

## FuFirE integration points

Reuse, do not duplicate:

- `bazi_engine.time_utils.resolve_local_iso`
- `bazi_engine.time_context.compute_effective_time_context`
- `bazi_engine.dayun.direction.resolve_direction_for_request`
- API-key dependency and tier limiter
- request IDs and `ErrorEnvelope`
- provenance conventions

Mount the new router **once** under `/v1`. This is a deliberate new B2B surface; do not create a legacy unversioned alias.

## Calendar provider

The inspected dependency set contains no Chinese lunisolar calendar provider. Introduce a protocol:

```python
class ChineseLunisolarCalendar(Protocol):
    def resolve(self, chart_local_date: date) -> ResolvedLunarDate: ...
```

The implementation must be local and deterministic at runtime. A pinned library can bootstrap the feature only if:

- its license permits use;
- it is wrapped behind the protocol;
- calendar boundary goldens are independent of the library;
- the version/hash is returned in provenance.

## Processing order

1. request validation;
2. local-time resolution;
3. effective CIVIL/LMT/TLST time;
4. hour branch and late-Zi detection;
5. chart-date adjustment;
6. lunisolar conversion with rollover;
7. leap-month policy;
8. year-cycle policy;
9. palace/stem/bureau computation;
10. stars, transformations, relations and optional decadals;
11. graph-consistency validation;
12. canonical JSON fingerprint and response.

## Failure codes

- `zwds_birth_time_required`
- `zwds_ruleset_not_found`
- `zwds_ruleset_not_release_ready`
- `zwds_calendar_conversion_failed`
- `zwds_direction_basis_missing`
- `zwds_requested_scope_unavailable`
- `zwds_ruleset_integrity_failed`
- `zwds_graph_invariant_failed`

## Test strategy

### Formula tests

- 144 Ming/Shen combinations (`12 × 12`);
- 60 valid stem/branch Bureau pairs;
- 150 Zi Wei cases (`30 × 5`);
- 12 base positions for all 14 major-star offsets;
- 144 month/hour combinations for four guide auxiliaries;
- 12 San Fang Si Zheng networks.

### Calendar boundaries

- lunar month ends, 29/30-day months;
- lunar-year transition;
- leap-month days 15/16;
- 23:00/00:00 under each late-Zi policy;
- DST fold/gap;
- CIVIL/LMT/TLST changes crossing hour or date boundaries.

### Golden corpus

Do not set an arbitrary count as proof. Define coverage first: every policy boundary, every bureau, every branch, every year-stem transformation row and representative star collisions. Practitioner review and at least one independent comparator are required, but comparator agreement is not treated as historical proof.

## Release gate

Release `core` only when:

- school/edition or explicit “core-seed” status is declared;
- calendar/time/leap/late-Zi/year-cycle policies are fixed;
- ruleset files are schema-valid and hash-locked;
- formula, contract and boundary tests pass;
- response graph has one source of truth;
- docs say `core-seed` or `complete for ruleset X`, never universal completeness.
