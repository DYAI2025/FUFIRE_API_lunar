# Python distribution resource inventory

Status: implemented, automated review pending.

The repository-level files below remain the reviewable contract sources.  The
package-level copies are immutable build mirrors used by installed wheels,
sdists, and the runtime image.  `tests/test_package_resources.py` compares the
decoded JSON documents exactly, so a semantic source change without its
runtime mirror fails CI while an end-of-file newline remains irrelevant.

| Runtime owner | Repository authority | Installed package resource | Runtime consumer |
|---|---|---|---|
| Ephemeris | `ephemeris.lock.json` | `bazi_engine/resources/ephemeris.lock.json` | Lunar provenance/attestation |
| BAFE | `spec/schemas/ValidateRequest.schema.json` | `bazi_engine/resources/schemas/ValidateRequest.schema.json` | request validator |
| BAFE | `spec/schemas/ValidateResponse.schema.json` | `bazi_engine/resources/schemas/ValidateResponse.schema.json` | response self-check |
| HTTP/OpenAPI | `spec/schemas/ErrorEnvelope.schema.json` | `bazi_engine/resources/schemas/ErrorEnvelope.schema.json` | OpenAPI patcher |
| ZWDS | `spec/schemas/zwds/ZwdsRequest.schema.json` | `bazi_engine/resources/schemas/zwds/ZwdsRequest.schema.json` | conditional request validator |
| ZWDS | `spec/schemas/zwds/ZwdsRawResponse.schema.json` | `bazi_engine/resources/schemas/zwds/ZwdsRawResponse.schema.json` | distribution contract/reference |
| BaZi | `spec/rulesets/standard_bazi_2026.json` | `bazi_engine/resources/rulesets/standard_bazi_2026.json` | ruleset loader |
| Quiz | package authority | `bazi_engine/data/affinity_map.json` | affinity resolver |
| ZWDS | package authority | `bazi_engine/data/zwds/rulesets/zwds.fufire.core-seed.v1/*.json` | hash-locked ruleset repository |

`spec/schemas/refdata_manifest.schema.json` is not read at runtime and is
therefore deliberately excluded.  The whole `spec/` tree is not shipped as an
implicit fallback.  Missing, unreadable, malformed, or wrongly shaped required
resources fail closed during import or first use; only an unknown quiz keyword
retains its documented uniform business fallback.
