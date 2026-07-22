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
- Public UTC range `[1900-01-01, 2100-01-01)`, fail-closed validation, and an
  honest `high_precision|degraded` precision grade (never `exact`).
- Provider version and immutable ephemeris-lock ID in every SWIEPH response.
- Twenty independent, minute-resolution USNO phase events across five epochs,
  checked with a provisional 90-second engineering tolerance.

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

## Current release boundary

The 2026-07-21 release-readiness execution reran the Lunar reference work with
the four files from `ephemeris.lock.json` in real SWIEPH mode. The superseded
MOSEPH-only limitation above therefore no longer applies. Final evidence counts
are written by the RC gate after the complete suite runs.

The technical reference gate is implemented, but the astronomy/domain owner
has not yet approved the provisional 90-second tolerance. That decision remains
MISSING and blocks a final release claim.
