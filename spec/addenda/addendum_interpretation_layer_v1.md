# Addendum: Interpretation Layer v1 (Fact / Rules / Narrative)

addendum_id: ADD-INT-001
status: PROPOSED
applies_to_spec_version: ">=1.0.0-rc0"
patch_id: PATCH-INT-001
breaking_change: false

## 0. Purpose

This addendum enforces that interpretation output is:

- optional
- deterministic
- strictly derived from numeric features
- explicitly separated from astronomical facts and symbolic rule outputs

It also enforces "claim boundaries":

- no statement is presented as scientific proof of metaphysical assertions

## 1. Layer Model (Schema-level)

MUST:

- Any response that includes interpretation MUST separate three layers:
  1) facts: astronomical/time outputs (UTC/UT1/TT, TLST, ephemeris positions, provenance)
  2) rules: discrete mappings (BaZi pillars, branch mapping, weights, harmonics features)
  3) interpretations: text statements

SHOULD:

- If include_interpretation=false, engine still returns valid facts/rules.

## 2. Statement Provenance

MUST:

- Each interpretation statement MUST contain:
  - statement_id (stable)
  - template_id (optional)
  - feature_refs: array of concrete feature keys (non-empty)
  - interpretation_ruleset_id + version
  - bazi_ruleset_id + version
  - provenance echo: engine_version, parameter_set_id, refdata_pack_id, config_fingerprint
  - stability_flags snapshot (boundary/time/refdata warnings)

If feature_refs is empty or missing:

- /validate MUST fail with error `INTERP_MISSING_FEATURE_REFS`

If include_interpretation=true but interpretation_ruleset_id missing:

- /validate MUST fail with error `INTERP_RULESET_ID_MISSING`

## 3. Claim Boundaries (Safety / Honesty Policy)

MUST NOT:

- Output any claim as scientific fact that the engine "proves" metaphysical assertions.

MUST:

- Include a short disclaimer (configurable string) when interpretation is enabled, e.g.:
  - "Symbolische, regelbasierte Ableitung; keine wissenschaftliche Faktbehauptung."
- Provide "why this statement" explainability:
  - feature_refs is the minimum requirement
  - optional: include threshold/logic references

## 4. Ambiguity Handling (Boundary + Time uncertainty)

MUST:

- If validation flags include any of:
  - DST fold/gap
  - tlst_quality=degraded/missing
  - classification_unstable near boundary
then InterpretationEngine MUST either:
  - produce a cautious variant, or
  - suppress the statement, or
  - present multiple conditional variants labeled A/B

## 5. Required Repo Artifacts

### 5.1 Rulesets (spec/rulesets/)

MUST (only if interpretation is shipped):

- interp_core_v1.json
  - versioned
  - thresholds/templates live here, not in code

### 5.2 Schemas (spec/schemas/)

SHOULD:

- InterpretationResponse.schema.json (once endpoint is live)
- Extend ValidateResponse.schema.json with:
  - INTERP_MISSING_FEATURE_REFS
  - INTERP_RULESET_ID_MISSING

## 6. Definition of Done (DoD)

- For any statement returned:
  - feature_refs is non-empty
  - statement is reproducible with same feature vector + ruleset
- Disabling interpretation does not change facts/rules
- /validate catches missing feature_refs and missing ruleset id as errors

1) Master spec: Addenda Registry Snippet

Datei: spec/bazodiac_spec_master.md (Snippet zum Einfuegen)

## Addenda Registry (normative)

This master spec is normative. The following addenda are normative unless stated otherwise:

- ADD-SCI-001: Scientific Compliance (time scales, refdata integrity, frames, edge cases, reproducibility)
  - File: addenda/addendum_scientific_compliance_v1.md
  - Applies to: spec_version 1.0.0-rc0+

- ADD-INT-001: Interpretation Layer (fact/rules/narrative separation, feature_refs, claim boundaries)
  - File: addenda/addendum_interpretation_layer_v1.md
  - Applies to: spec_version 1.0.0-rc0+

1) Changelog Snippet

Datei: spec/changelog.md (Snippet)

## [1.0.0-rc0] - YYYY-MM-DD

### Added

- ADD-SCI-001 Scientific Compliance Addendum v1
- ADD-INT-001 Interpretation Layer Addendum v1

1) Schema-Patch: Error Codes erweitern (ValidateResponse)

Ihr habt aktuell schon Codes wie INTERP_DERIVATION_EMPTY und INTERP_LINT_FAIL. Das neue Addendum verlangt zusaetzlich:

INTERP_MISSING_FEATURE_REFS

INTERP_RULESET_ID_MISSING

Empfehlung (praezise, stabil):

Behalten: INTERP_LINT_FAIL

Deprecate/alias: INTERP_DERIVATION_EMPTY -> ersetzt durch INTERP_MISSING_FEATURE_REFS

Validator darf intern beide erkennen, soll aber nach aussen bevorzugt INTERP_MISSING_FEATURE_REFS ausgeben.

Patch-Snippet fuer schemas/ValidateResponse.schema.json

(Ergaenzung der ErrorCode.enum Liste)

{
  "definitions": {
    "ErrorCode": {
      "type": "string",
      "enum": [
        "... existing codes ...",
        "INTERP_MISSING_FEATURE_REFS",
        "INTERP_RULESET_ID_MISSING"
      ]
    }
  }
}

Und in /validate Logik:

Wenn statement feature_refs missing/empty -> INTERP_MISSING_FEATURE_REFS

Wenn include_interpretation=true und ruleset id missing -> INTERP_RULESET_ID_MISSING

Wenn claim-linter fail -> INTERP_LINT_FAIL

Was sich dadurch verbessert (kurz, konkret)

Eure Addenda sind jetzt repo-faehig, normativ, phase-mapped.

/validate bekommt eindeutige neue Errors fuer Interpretation-Contracts.

Interpretation bleibt sauber pluginfaehig, ohne Fakten/Regeln zu beeinflussen.

Keine "versteckten" Netz-Zugriffe: RefData Guard ist jetzt als MUST festgenagelt.
