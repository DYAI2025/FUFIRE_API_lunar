# Spec SSOT README

This repository contains a contract-first Single Source of Truth (SSOT) under ./spec.

## Structure

- spec/bazodiac_spec_master.md
  Normative text (human-readable), frozen at spec_version 1.0.0-rc0.

- spec/schemas/
  JSON Schemas (Draft-07). These are binding for /validate.

- spec/rulesets/
  Canonical rulesets. The canonical ruleset for this release is:
  - standard_bazi_2026.json

- spec/addenda/
  Policy-heavy addenda (Scientific Compliance, Interpretation Layer).

- spec/tests/
  Acceptance test vectors (TV*) and property tests (PT*).

## Contract is Law

Do not change schemas or error code enums without:
- version bump
- changelog entry
- migration notes
- updated/added tests
