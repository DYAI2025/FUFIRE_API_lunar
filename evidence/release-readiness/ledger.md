# FuFire Lunar release-readiness evidence ledger

Baseline captured on 2026-07-21 from live commit
`fe8f0198f6a4bda1568d986bf8aac06efe4e123c`.

| Evidence | Class | Result | Boundary |
|---|---|---|---|
| GitHub repository metadata | production-observed | Default branch was `master`; initial live head recorded | Branch protection/ruleset was not exposed |
| Git refs | production-observed | `master` plus two Dependabot branches; no tags | `main` did not exist at capture time |
| Uploaded ZIP versus fresh clone | source-inspected | No file differences outside `.git` | Does not prove runtime behavior |
| Commit status | production-observed | Railway reported success for the baseline commit | Deployment settings and source branch remain unknown |
| GitHub PR workflow runs | production-observed | None associated with the baseline commit | Non-PR Actions inventory unavailable through the connector |
| pytest collection before recovery | local-verified | 3625 tests collected, one collection error | `gate_contracts.py` was absent |
| Recovered gate helper | source-inspected | Sourced from `DYAI2025/FuFirE` commit `9b00e0e…`, blob `1827e08…` | Sibling-repository provenance; not invented history |
| Integration branches | production-observed | `release/readiness-integration` and `main` created from the frozen baseline SHA | Default branch is still `master`; external setting change unavailable |
| Atomic CI gate | local-verified | `release-gate` aggregates test, typecheck, lint, complexity, security, Docker, distribution, codegen, and contract jobs fail-closed | Required ruleset/branch-protection proof is MISSING |
| Python distribution | local-verified | Wheel and sdist inventory plus source-free clean-install smokes succeeded on local Python 3.12 | CI 3.10/3.11/3.12 and Docker execution pending |
| Ephemeris authority | local-verified | Immutable lock, four verified SE1 hashes, shared CI/Docker fetcher, and read-only snapshot update path | Domain approval of corpus tolerance is MISSING |
| Wu-Xing snapshot drift | local-verified | 50 locked SWIEPH Wu-Xing snapshots gained only `basis=western_planetary`; structural diff verified no numeric/provenance change | Maintainer review is MISSING |
| Lunar V2 reference corpus | local-verified | USNO phase corpus and SWIEPH invariant/range/transition tests succeeded locally | Domain approval remains MISSING |
| Runtime safety | local-verified | Production auth/CORS/Redis/feature configuration fails closed; `/ready` returns 503 for required dependency degradation | Railway configuration and deployed smoke are MISSING |
| Conditional surfaces | local-verified | Key issuance and ZWDS default disabled; MOSEPH/marketing/precision policies enforced | ZWDS/product approvals remain MISSING if scope changes |
| Supply-chain policy | local-verified | `uv.lock` is canonical; hash-locked runtime export, npm lock, exact tools, action SHAs, image digests, non-root runtime, SBOM validation | Docker inspect and GitHub CI artifact/run ID pending |
| Local release-candidate verification | local-verified | Python 3.12: 3672 passed, 102 skipped, 1 expected failure; coverage 93.03%; Ruff, Mypy, complexity, OpenAPI drift, readiness artifacts, and toolchain checks passed | Python 3.10/3.11 CI and built-container execution pending |
| Dependency and security audit | local-verified | `pip-audit` reports no known vulnerabilities after upgrading Click to 8.4.2; Bandit high/medium scan passed; CycloneDX SBOM validated | CI-produced SBOM/run identity and signature pending |
| release-please identity | source-inspected | Workflow requires explicit `RELEASE_PLEASE_TOKEN` and fails closed when absent | Credential provisioning and bot-PR check-run proof are MISSING |
| Swiss Ephemeris licensing | source-inspected | Root MIT, README proprietary, installed pyswisseph AGPL classifier, and official dual-license requirement conflict | RB-017: Professional-license evidence or approved AGPL path is MISSING |
| Staging and rollback | prepared-only | Fail-closed runbooks and evidence template added | No Railway deploy, load test, promotion, tag, release, or rollback was executed |

The release decision remains **BLOCKED** until mandatory and applicable
conditional gates in the execution plan have verifiable evidence.
