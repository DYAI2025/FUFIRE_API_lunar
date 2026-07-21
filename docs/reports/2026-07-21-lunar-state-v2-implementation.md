# Lunar State V2 — Implementation Evidence

Date: 2026-07-21  
Source plan: `2026-07-20-canonical-instant-tlst-v2.md` supplied with the task

## Delivered

- Fold-preserving immutable `ResolvedInstant` and `resolve_local_instant()`.
- Canonical `JD_UT` derived once from the resolved aware UTC datetime.
- Geocentric apparent ecliptic-of-date Sun/Moon state from Swiss Ephemeris.
- `pheno_ut` metrics: phase angle, illuminated fraction, apparent elongation,
  apparent diameter, magnitude, and lunar horizontal parallax.
- Newton-refined preceding/following true-new-moon events, Moon age, lunation
  length, and progress.
- Corrected eight-phase classification centred at 0°/45°/…/315°, with
  half-open boundaries at centre ±22.5°.
- Protected V2-only `POST /v2/astronomy/lunar-state`; no V1 or bare alias.
- Typed request/response models, rate limit, OpenAPI artifact, route snapshot,
  endpoint documentation, and import-layer registration.

## Compatibility

- No existing V1 router or calculation consumer was migrated.
- The legacy `phases.lunar_phase` approximation and its historical phase
  boundaries are unchanged.
- The public contract is additive under `/v2`.

## Verification

Focused calculation/contract/regression matrix:

```text
348 passed, 73 skipped
```

Additional gates:

```text
ruff: passed
mypy: passed (134 source files)
complexity: passed (threshold 15)
OpenAPI drift check: passed
```

The repository-wide suite was also compared with a pristine extraction of the
uploaded ZIP under the same Python 3.12 environment:

| Tree | Passed | Failed | Skipped | XFailed |
|---|---:|---:|---:|---:|
| Uploaded baseline | 2796 | 218 | 586 | 1 |
| Lunar State V2 | 2824 | 216 | 586 | 1 |

No new full-suite failure category was introduced. The remaining failures are
pre-existing snapshot drift, an incomplete mock route, one ephemeris security
test interaction, and optional space-weather/Superglue test dependencies.

## Environment limitation

Real SWIEPH SE1 files were not available in the execution environment. The
reference-event and endpoint tests therefore ran in the repository's explicit
MOSEPH fallback test mode and correctly reported `precision_grade=degraded`.
Production construction remains fail-closed for missing SWIEPH files, and CI
with SE1 assets should rerun the same reference-event test in SWIEPH mode before
deployment approval.
