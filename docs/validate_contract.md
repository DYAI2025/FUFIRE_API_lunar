# /validate Contract Guide

Single Source of Truth:
- Request schema: spec/schemas/ValidateRequest.schema.json
- Response schema: spec/schemas/ValidateResponse.schema.json

## Purpose

/validate is a contract-first endpoint to verify:
- configuration correctness
- refdata policy compliance (offline + verification)
- time/DST policy correctness (fold/gap)
- discretization conventions (SHIFT_BOUNDARIES / SHIFT_LONGITUDES)
- determinism (config_fingerprint)

## Determinism

For deterministic CI and reproducible validation, always provide:

- now_utc_override: an ISO-8601 UTC timestamp with Z suffix.

## Ruleset

This release ships the canonical ruleset:
- spec/rulesets/standard_bazi_2026.json

Anchor gating:
- If anchor_verification != "verified", STRICT compliance_mode MUST gate (error MISSING_DAY_CYCLE_ANCHOR).
- In RELAXED/DEV mode the engine emits a warning (same code) and marks component DEGRADED.

## RefData

No implicit downloads are performed by the engine.
Offline modes require an explicit manifest (inline or mounted).
