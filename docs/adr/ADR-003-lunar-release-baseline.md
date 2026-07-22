# ADR-003: Lunar release baseline and target version

- Status: accepted for the integration branch; release approval pending
- Date: 2026-07-21

## Context

`DYAI2025/FUFIRE_API_lunar` was created as a one-commit repository from a
snapshot. Its package metadata still said 1.4.0, while the canonical
`DYAI2025/FuFirE` repository had already released the Wu-Xing baseline as
1.5.0 before Lunar V2 was added. The copied release-please bootstrap SHA did
not exist in the Lunar repository.

## Decision

1. Reconstruct 1.5.0 in package metadata, manifest, and changelog, with links
   to the real canonical history rather than inventing local commits or tags.
2. Use the Lunar repository's actual initial commit
   `fe8f0198f6a4bda1568d986bf8aac06efe4e123c` as the release-please bootstrap.
3. Target 1.6.0 for the additive Lunar V2 release. Conventional feature
   commits after the bootstrap are expected to produce that minor release.
4. Do not create a tag or merge a release PR until the owner explicitly
   approves 1.6.0 and all mandatory release gates are green.

## Consequences

- Release automation traverses only reachable history in this repository.
- Historical links remain honest about their source repository.
- Product-owner approval remains MISSING for final release promotion; it is
  not inferred from a passing test or from this ADR.
