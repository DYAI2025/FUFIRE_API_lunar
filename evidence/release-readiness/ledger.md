# FuFire Lunar release-readiness evidence ledger

Baseline captured on 2026-07-21 from live commit
`fe8f0198f6a4bda1568d986bf8aac06efe4e123c`.

| Evidence | Class | Result | Boundary |
|---|---|---|---|
| GitHub repository metadata | production-observed | Default branch was `master`; initial live head recorded | Branch protection/ruleset was not exposed |
| Git refs | production-observed | `master` plus two Dependabot branches; no tags | `main` did not exist at capture time |
| Uploaded ZIP versus fresh clone | source-inspected | No file differences outside `.git` | Does not prove runtime behavior |
| Commit status | production-observed | Railway reported success for the baseline commit | Deployment settings and source branch remain unknown |
| GitHub PR workflow runs at baseline | production-observed | None associated with the frozen baseline commit | Non-PR Actions inventory unavailable through the connector |
| pytest collection before recovery | local-verified | 3625 tests collected, one collection error | `gate_contracts.py` was absent |
| Recovered gate helper | source-inspected | Sourced from `DYAI2025/FuFirE` commit `9b00e0e…`, blob `1827e08…` | Sibling-repository provenance; not invented history |
| Integration branches | production-observed | `release/readiness-integration` and `main` created from the frozen baseline SHA | Default branch is still `master`; external setting change unavailable |
| Atomic CI gate | production-observed | GitHub CI run `29875872793` completed successfully; its `release-gate` job `88786666804` aggregated every mandatory job fail-closed | Required ruleset/branch-protection proof is MISSING |
| Python distribution | production-observed | Wheel/sdist inventory and source-free clean-install smokes succeeded locally and in GitHub on Python 3.10, 3.11, and 3.12 | PyPI publication is out of scope while release is blocked |
| Ephemeris authority | local-verified | Immutable lock, four verified SE1 hashes, shared CI/Docker fetcher, and read-only snapshot update path | Domain approval of corpus tolerance is MISSING |
| Wu-Xing snapshot drift | local-verified | 50 locked SWIEPH Wu-Xing snapshots gained only `basis=western_planetary`; structural diff verified no numeric/provenance change | Maintainer review is MISSING |
| Lunar V2 reference corpus | local-verified | USNO phase corpus and SWIEPH invariant/range/transition tests succeeded locally | Domain approval remains MISSING |
| Runtime safety | local-verified | Production auth/CORS/Redis/feature configuration fails closed; `/ready` returns 503 for required dependency degradation | Railway configuration and deployed smoke are MISSING |
| Conditional surfaces | local-verified | Key issuance and ZWDS default disabled; MOSEPH/marketing/precision policies enforced | ZWDS/product approvals remain MISSING if scope changes |
| Supply-chain policy | production-observed | `uv.lock` is canonical; hash-locked isolated runtime prefix, npm lock, exact tools, action SHAs, image digests, SBOM validation, and real multi-stage Docker build succeeded in run `29875872793` | Runtime inspect/smoke, attestation signature, and registry digest remain MISSING |
| Local release-candidate verification | local-verified | Python 3.12: 3672 passed, 102 skipped, 1 expected failure; coverage 93.03%; Ruff, Mypy, complexity, OpenAPI drift, readiness artifacts, and toolchain checks passed | Cross-version and container evidence is recorded in GitHub CI run `29875872793` |
| Dependency and security audit | production-observed | Local and CI audits passed; artifact `8512947602` contains the CycloneDX SBOM plus blocked, hash-addressed release-evidence manifest | Evidence signature remains MISSING |
| GitHub build artifacts | production-observed | Run `29875872793` uploaded SBOM/evidence, coverage, OpenAPI provenance, and Docker build records with API-reported SHA-256 digests | Artifacts expire 2026-10-19; durable signed attestation is MISSING |
| release-please identity | source-inspected | Workflow requires explicit `RELEASE_PLEASE_TOKEN` and fails closed when absent | Credential provisioning and bot-PR check-run proof are MISSING |
| Swiss Ephemeris licensing | source-inspected | Root MIT, README proprietary, installed pyswisseph AGPL classifier, and official dual-license requirement conflict | RB-017: Professional-license evidence or approved AGPL path is MISSING |
| Staging and rollback | prepared-only | Fail-closed runbooks and evidence template added | No Railway deploy, load test, promotion, tag, release, or rollback was executed |

The release decision remains **BLOCKED** until mandatory and applicable
conditional gates in the execution plan have verifiable evidence.
