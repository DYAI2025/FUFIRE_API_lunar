# BAFE — Contract-First Validation

**Responsibility**: JSON Schema (Draft-07) validation engine for the `/validate` endpoint — request orchestration, branch coordinate mapping, reference data policy checks, time evaluation, ruleset loading, canonical JSON fingerprints, soft branch weights, harmonic analysis.

**Technology**: Python / jsonschema / Pydantic v2

## Source Mapping

All code in `bazi_engine/bafe/`:

| Module | Role |
|--------|------|
| `service.py` | Main `validate_request()` orchestrator |
| `mapping.py` | Branch coordinate conventions (SHIFT_BOUNDARIES, SHIFT_LONGITUDES) |
| `refdata.py` | Reference data policy checks |
| `time_model.py` | Time evaluation |
| `ruleset_loader.py` | Loads rulesets from `spec/rulesets/` |
| `canonical_json.py` | Deterministic config fingerprints |
| `kernel.py` | Soft branch weights |
| `harmonics.py` | Harmonic analysis utilities |
| `errors.py` | Contract-bound error codes and issue factory |

## Interfaces

- **Python class API**: `validate_request()` consumed by `api` component (`routers/validate.py`)
- **File system**: reads JSON schemas from `spec/schemas/` and rulesets from `spec/rulesets/`

## Schemas

- `spec/schemas/ValidateRequest.schema.json`
- `spec/schemas/ValidateResponse.schema.json`
- `spec/rulesets/standard_bazi_2026.json`

## Constraints

- Contract-first: the JSON Schema is the source of truth, not the Python code
- `ErrorEnvelope` schema must exist in OpenAPI spec
- Request/response definitions must be hoisted to `components/schemas` for codegen compatibility

## Requirements Addressed

Input validation, contract compliance, error reporting with structured error codes.

## Relevant Decisions

| File | Title | Trigger |
|------|-------|---------|
| — | Contract-first validation | When modifying `/validate` — schema is source of truth |
| — | Hoisted schema definitions | Codegen compatibility — definitions in `components/schemas` |
