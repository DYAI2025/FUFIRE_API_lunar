# Swiss Ephemeris license gate (RB-017)

Status: **BLOCKED — legal approval and license evidence are missing**  
Owner: Legal / Product Owner  
Engineering gate owner: Release Manager  
Captured: 2026-07-21

## Evidence

The release candidate executes `pyswisseph==2.10.3.2`, downloads four Swiss
Ephemeris SE1 files during the immutable image build, and exposes calculations
through an HTTP service. The evidence available in this repository is not a
valid production license decision:

| Evidence | Observed value | Result |
|---|---|---|
| Root `LICENSE` | MIT | Conflicts with the dependency/distribution evidence below |
| README license section | "Proprietary" | Conflicts with root `LICENSE` |
| Installed `pyswisseph` classifier | GNU Affero General Public License v3 | Copyleft obligation requires legal evaluation |
| Astrodienst official programmer documentation | Requires a choice between AGPL and the Swiss Ephemeris Professional License before distribution or public service activation | No choice or entitlement ID is present |

Authoritative source: [Astrodienst Swiss Ephemeris programmer documentation](https://www.astro.com/swisseph/swephprg.htm).

## Fail-closed decision

No public container distribution, production activation, tag, or GitHub Release
is authorized until one of these paths is approved in writing:

1. A Swiss Ephemeris Professional License whose scope covers this service and
   its deployment/distribution model; or
2. An explicitly approved AGPL-compatible release of the complete applicable
   work, with all repository, package, image, source-offer, and notice
   obligations implemented.

Engineering must not infer a path from the current MIT or "Proprietary" text.
This document is an engineering release gate, not legal advice.

## Required evidence to close RB-017

- Approval owner and approval date.
- Non-secret license/entitlement reference ID and covered legal entity.
- Approved use: internal service, public SaaS/API, container distribution, and
  downloadable Python artifacts, as applicable.
- Consistent `LICENSE`, README, `pyproject.toml`, SBOM/container notices, and
  release notes.
- Legal confirmation that the four locked SE1 assets and `pyswisseph` usage are
  covered by the selected path.

Contract text and license keys must remain outside the repository and CI logs.

## Verification

The Release Manager records only the non-secret evidence ID in the release
ledger, inspects the built wheel/container license inventory, and keeps the
release decision `BLOCKED` until Legal marks every applicable use above as
covered.
