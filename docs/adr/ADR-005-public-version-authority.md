# ADR-005: Public release version authority for Lunar V2

- Status: proposed; Product/Release approval required
- Date: 2026-07-22
- Owners: Product Owner, Release Owner, Engine Maintainer
- Related gates: LR-006, LR-007

## Context

The reconstructed package and release-please baseline is `1.5.0`, while the runtime module and generated OpenAPI still expose the historical engine label `1.0.0-rc1-20260220`. ADR-003 identifies `1.6.0` as the intended additive Lunar V2 target but explicitly leaves Product approval missing.

Changing one version field in isolation would create a new form of drift. Inferring `1.6.0` from code completeness or CI success would incorrectly convert a Product/Release decision into a technical side effect.

## Proposed decision

1. The approved SemVer release is the public contract/package version and must be identical in `pyproject.toml`, the release-please manifest, changelog release heading, generated OpenAPI `info.version`, release tag, and the release-facing field returned by `/build`.
2. An internal or dated engine build label, when still needed, must use a separately named field such as `engine_build` or `build_label`; it must not compete with the public `version` field.
3. Product/Release must explicitly approve the Lunar V2 release version. The current proposal is `1.6.0`; it is not approved by this ADR.
4. After approval, the version change must be applied in one bounded RC change, OpenAPI must be regenerated through `scripts/export_openapi.py`, and tests must fail on any drift among package, runtime, OpenAPI, manifest, changelog, tag, and `/build`.
5. No tag, release PR merge, or production promotion may occur while the approval ID or any version authority remains missing.

## Current decision state

**BLOCKED.** The technical recommendation is recorded, but the public release version and final `/build` field design are not approved. The repository must preserve fail-closed release evidence until those approvals exist.

## Closure evidence

- Product/Release approval ID and approved SemVer.
- Generated OpenAPI diff and clean `scripts/export_openapi.py --check`.
- Cross-artifact version-consistency tests on Python 3.10/3.11/3.12.
- Release PR/tag evidence tied to the approved commit and immutable image digest.
