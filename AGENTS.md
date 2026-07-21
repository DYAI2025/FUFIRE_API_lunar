# AGENTS.md

This file provides guidance to Codex (Codex.ai/code) when working with code in this repository.

## Project Overview

**BaZi Engine / FuFirE** (v1.0.0-rc1) is a deterministic astronomical calculation engine for Chinese astrology (Four Pillars of Destiny) with Western astrology integration. It calculates Year/Month/Day/Hour pillars based on precise astronomical solar-term boundaries using the Swiss Ephemeris.

**Key Characteristics:**
- Deterministic: No randomness, purely astronomical calculations
- Immutable: All dataclasses use `frozen=True`
- Type-safe: Complete type hint coverage (Python 3.10+)
- Functional: Pure functions with no side effects
- Contract-first: JSON Schema (Draft-07) validation for `/validate` endpoint
- **Attestation-first:** Every response carries quality_flags + provenance (ephemeris_mode, tzdb_version_id)

## Development Commands

```bash
# Setup
python3.10 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# Run tests
pytest -q                           # Quick run
pytest -v                           # Verbose
pytest tests/test_golden.py         # Golden vectors only
pytest -k "test_name"               # Pattern matching

# Lint & typecheck (CI uses these)
ruff check bazi_engine/ --output-format=github
mypy bazi_engine --ignore-missing-imports

# Start API server
uvicorn bazi_engine.app:app --reload

# CLI usage
python -m bazi_engine.cli 2024-02-10T14:30:00 --tz Europe/Berlin --lon 13.405 --lat 52.52
python -m bazi_engine.cli 2024-02-10T14:30:00 --json   # JSON output

# Docker
docker build -t bazi_engine . && docker run -p 8080:8080 bazi_engine

# Deploy
railway up --service <name>         # Railway (requires --service once multiple services detected)
```

## Architecture

### Module Hierarchy (import order matters)

```
Level 0: constants.py          # STEMS, BRANCHES, DAY_OFFSET=49
Level 1: types.py              # Pillar, FourPillars, BaziInput, BaziResult
Level 2: ephemeris.py          # SwissEphBackend, EphemerisBackend protocol
         time_utils.py         # parse_local_iso, LocalTimeError
Level 3: jieqi.py              # Solar term calculations, find_crossing()
Level 4: bazi.py               # compute_bazi() - main entry point
         western.py            # compute_western_chart()
         fusion.py             # Wu-Xing vectors, Harmony Index
Level 5: app.py                # FastAPI endpoints
         cli.py                # Command-line interface
         bafe/                 # Contract-first validation subpackage
```

**Critical Rule:** Lower-level modules cannot import higher-level modules. Never import `bazi.py` into ephemeris.py, jieqi.py, or time_utils.py.

### Core Entry Points

1. **BaZi Calculation:** `bazi_engine/bazi.py:compute_bazi()` - Main 9-step pipeline
2. **Western Chart:** `bazi_engine/western.py:compute_western_chart()` - Planetary positions
3. **Fusion Analysis:** `bazi_engine/fusion.py:compute_fusion_analysis()` - Wu-Xing + Western integration
4. **Contract Validator:** `bazi_engine/bafe/service.py:validate_request()` - Schema-validated API

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/calculate/bazi` | POST | Four Pillars calculation |
| `/calculate/western` | POST | Western planetary positions |
| `/calculate/fusion` | POST | Wu-Xing + Western harmony analysis |
| `/calculate/wuxing` | POST | Wu-Xing vector from planets |
| `/calculate/tst` | POST | True Solar Time calculation |
| `/validate` | POST | Contract-first validator (JSON Schema Draft-07) |
| `/api` | GET | Simple zodiac lookup |
| `/api/webhooks/chart` | POST | ElevenLabs agent integration |

### BAFE Subpackage (Contract-First Core)

The `bazi_engine/bafe/` subpackage implements spec-conform validation:
- `service.py` - Main `validate_request()` function
- `mapping.py` - Branch coordinate conventions (SHIFT_BOUNDARIES, SHIFT_LONGITUDES)
- `refdata.py` - Reference data policy checks
- `time_model.py` - Time evaluation
- `ruleset_loader.py` - Loads rulesets from `spec/rulesets/`
- `canonical_json.py` - Deterministic config fingerprints
- `kernel.py` - Soft branch weights computation
- `harmonics.py` - Harmonic analysis utilities
- `errors.py` - Contract-bound error codes and issue factory

Schemas live in `spec/schemas/` (ValidateRequest.schema.json, ValidateResponse.schema.json).

## Critical Domain Concepts

### Year Boundary (LiChun)
- Year changes at 315° solar longitude (~Feb 3-5)
- Birth before LiChun uses previous year's pillar
- Timezone-sensitive: Berlin LiChun ≠ Beijing LiChun

### Day Pillar Calibration
```python
DAY_OFFSET = 49  # in constants.py - DO NOT MODIFY unless recalibrating
```
Formula: `sexagenary_day_index = (JDN + 49) % 60`

### DST Handling
- `LocalTimeError` raised for nonexistent/ambiguous times when `strict_local_time=True`
- Use `fold=0` or `fold=1` for ambiguous fall-back times
- Set `strict_local_time=False` for lenient mode

### Swiss Ephemeris
- Required files: sepl_18.se1, semo_18.se1, seplm06.se1
- Default path: `/usr/local/share/swisseph`
- Set via `SE_EPHE_PATH` env var or `ephe_path` parameter
- Error "SwissEph file not found" = missing ephemeris data

## Testing

CI runs on Python 3.10, 3.11, 3.12. Tests skip gracefully if ephemeris files are missing.

| Test File | What It Covers |
|-----------|----------------|
| `test_golden.py` | Known correct pillar results |
| `test_golden_vectors.py` | Edge cases (high latitude, LMT, zi boundary) |
| `test_invariants.py` | Structural properties (DAY_OFFSET validation) |
| `test_api.py` | Contract schema validation, BAFE mapping |
| `test_endpoints.py` | FastAPI endpoint integration |
| `test_fusion.py` | Wu-Xing fusion analysis |
| `test_properties.py` | Generative/property-based testing |
| `test_time_utils.py` | DST, timezone edge cases |
| `test_western.py` | Western chart calculations |
| `test_constants.py` | Constants integrity |

## Code Conventions

- All dataclasses: `@dataclass(frozen=True)` - immutability enforced
- Type hints: `from __future__ import annotations` at file top
- Imports: stdlib → third-party → local (three groups)
- Pure functions: No side effects, no global state modification
- Constants: Use `bazi_engine/constants.py`, never hardcode

## Key Files Quick Reference

| File | Purpose |
|------|---------|
| `bazi_engine/bazi.py` | `compute_bazi()` - main calculation |
| `bazi_engine/types.py` | All data structures |
| `bazi_engine/constants.py` | STEMS, BRANCHES, DAY_OFFSET, ANIMALS |
| `bazi_engine/fusion.py` | Wu-Xing vectors, harmony index, equation of time |
| `bazi_engine/app.py` | FastAPI REST API |
| `bazi_engine/bafe/service.py` | Contract-first validator |
| `spec/schemas/` | JSON Schema definitions |
| `spec/rulesets/standard_bazi_2026.json` | Canonical BaZi ruleset |
| `tests/test_golden.py` | Golden vector tests |

## OpenAPI Contract

**`spec/openapi/openapi.json`** is the API contract (Source of Truth). See `CONTRACT.md` for details.

- All 13 endpoints have typed request/response schemas
- `/validate` references `spec/schemas/ValidateRequest.schema.json` and `ValidateResponse.schema.json`
- CI checks for drift: `python scripts/export_openapi.py --check`
- After any endpoint/schema change: `python scripts/export_openapi.py` to regenerate
- `bazi_engine.__version__` is the single source for version strings

## Gotchas

1. **Circular imports:** Respect module hierarchy strictly
2. **Immutability:** Never remove `frozen=True` from dataclasses
3. **DAY_OFFSET:** Changing breaks day pillar accuracy
4. **DST:** Always handle `LocalTimeError` in API endpoints
5. **Ephemeris:** Tests skip without explicit `SE_EPHE_PATH` setup
6. **Contract tests:** BAFE validation requires `spec/` schemas to exist
7. **OpenAPI drift:** Always run `python scripts/export_openapi.py` after changing endpoints or models
8. **Endpoints are frozen:** Do not change existing endpoint paths or response structures — other services depend on them
