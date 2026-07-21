# ZWDS Claim Audit

| ID | Claim | Status | Correction |
|---|---|---|---|
| `C-01` | “mathematically most rigorous/complex” | **BLOCKED** | Subjective ranking; no operational value for the API. (Guide line 3) |
| `C-02` | Direct historical authorship by Chen Tuan | **SOURCE_NEEDED** | The available secondary source describes this as a traditional attribution (相傳), not demonstrated authorship. (Guide line 3; source ledger S-04) |
| `C-03` | Exclusive imperial secret science | **SOURCE_NEEDED** | No reliable source supplied; remove from technical docs. (Guide line 3) |
| `C-04` | Exactly 108 stars as universal completeness | **BLOCKED** | Catalog counts vary by scope; completeness must be manifest-based. (Guide line 5) |
| `C-05` | Entire system independent of ephemerides | **PARTIAL** | Star placement can use discrete lunar inputs; civil-to-lunar conversion still requires a calendar algorithm. (Guide line 5; repo dependency inspection) |
| `C-06` | No interpretive ambiguity | **BLOCKED** | Computation can be deterministic within a ruleset; interpretation remains rule- and school-dependent. (Guide line 5) |
| `C-07` | True solar time is universally essential | **BLOCKED** | Treat CIVIL/LMT/TLST as ruleset policies. (Guide line 100) |
| `C-08` | Leap-month split after day 15 | **RULESET_CANDIDATE** | Reproducible and implementation-corroborated, but not established as universal. (Guide line 100; iztro source comparator) |
| `C-09` | Late Zi always advances the day | **RULESET_CANDIDATE** | Known variant; must be policy-selected. Bare lunar-day increment is unsafe at month/year boundaries. (Guide line 102; source ledger S-04/S-05) |
| `C-10` | Shen palace means physical development after age 35 | **SOURCE_NEEDED** | Interpretive claim, not a calculation rule; exclude from raw endpoint. (Guide lines 131-135) |
| `C-11` | Ming/Shen and palace sequence formulas | **COMPUTATIONALLY_COHERENT** | Finite-domain checks pass and implementation comparator follows the same structure. (Guide lines 118-178; iztro palace source/tests) |
| `C-12` | Five-Tigers and Bureau calculation | **COMPUTATIONALLY_COHERENT** | 60 valid parity pairs agree between two algebraic forms and comparator examples. (Guide lines 225-346; iztro palace source/tests) |
| `C-13` | Zi Wei/Tian Fu and 14-major-star offsets | **COMPUTATIONALLY_COHERENT** | 150 formula equivalence cases and comparator source/tests agree. (Guide lines 348-597; iztro location/major-star source/tests) |
| `C-14` | One universal Four-Transformations table | **BLOCKED** | Documented tabulations differ in at least Geng/Ren rows; table ID and hash are mandatory. (Guide table; source ledger S-04) |
| `C-15` | Benefic/malefic compensation in San Fang Si Zheng | **SOURCE_NEEDED** | Interpretive layer; raw endpoint returns geometry only. (Guide interpretation section) |
| `C-16` | Start age equals Bureau number | **RULESET_CANDIDATE** | Computable and comparator-corroborated; age reckoning must be named. (Guide decadal section; iztro palace source) |
| `C-17` | Guide is complete, infallible and original | **BLOCKED** | Contradicted by its limited catalog and unresolved conventions. (Guide line 1075) |
| `C-18` | Earthly-Branch row 7 contains 庚 / 午 | **ERROR** | 庚 is a Heavenly Stem; the seventh Earthly Branch is 午. Store stem, branch and zodiac animal as separate typed IDs. (Guide line 80) |
