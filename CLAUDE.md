# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**FuFirE — Fusion Firmament Engine** is a deterministic astronomical calculation engine for Chinese astrology (Four Pillars of Destiny / BaZi) with Western astrology integration. Calculates Year/Month/Day/Hour pillars based on precise solar-term boundaries using Swiss Ephemeris.

Versioning has two independent axes: (1) the **package/release version** in `pyproject.toml`, owned by [release-please](https://github.com/googleapis/release-please) (`release-please-config.json`) — it opens a release PR from Conventional Commit messages on every push to `main`; merging it bumps the version, tags a GitHub Release, and updates `CHANGELOG.md`. Never hand-edit `pyproject.toml`'s version. (2) the **engine build label** `bazi_engine/__init__.py` `__version__` (e.g. `1.0.0-rc1-20260220`), used in API responses, the OpenAPI spec, and baked into golden snapshot fixtures — still bumped manually, deliberately, alongside a snapshot regeneration, when you want to move the engine's own build marker. Regenerate the OpenAPI spec (`python scripts/export_openapi.py`) after changing `__version__`.

**Key Characteristics:**
- Deterministic: No randomness, purely astronomical calculations
- Immutable: All dataclasses use `frozen=True`
- Type-safe: Complete type hint coverage (Python 3.10+)
- Functional: Pure functions with no side effects
- Contract-first: JSON Schema (Draft-07) validation for `/validate` endpoint

### Current State

The project is in the **Code phase** (mature). The engine is production-deployed on **Railway** (auto-deploys on push to `main` via `Dockerfile` + `railway.toml`) with ~1500 passing tests, full OpenAPI contract coverage, and CI on Python 3.10–3.12. Fly.io is **decommissioned** — all Fly config has been removed from the repo; Railway is the sole deployment target.

4 components identified: engine, api, services, bafe; per-component directories created in `3-code/`.

Current work focuses on:
- Superglue proxy integration (ElevenLabs/Bazodiac frontend)
- Dashboard redesign API endpoints (`/impact/active`, `/experience/daily` v2)
- Transit interpretation ownership migration from Signatur to Dashboard

Implementation plan created (2026-04-13): 5 phases, 34 tasks.

- **Phases 1–2:** ✅ Complete (13/13 — correctness, billing, provenance)
- **Phase 3:** ✅ Complete — 11/11 tasks done (Impact & Daily v2 API, PRD P0-3/P0-4)
- **Phase 4:** ✅ Complete — 5/5 tasks done (Enhanced Fusion Quality)
- **Phase 5:** In progress — 4/5 tasks done (planetary dignities, decanates & Egyptian terms, fixed star conjunctions, Ke-cycle Wu-Xing; enterprise differentiation)

**BAZI-PRECISION-V2** (high-risk SDLC change, phased, test-first, review-gated — implementation progress: 20/44 tasks done):
- **Phase 0:** ✅ Complete — 8/8 tasks done (baseline, golden schema, deviation register, release gates; 2026-05-17)
- **Phase 1:** ✅ Complete — 5/5 tasks done (Effective Time Model: CIVIL/LMT/TLST)
- **Phase 2:** In progress — 2/8 tasks done (BaZi Core; FBP-02-002/003/007 need domain reviewer — DEV-2026-004; FBP-02-006 ✅ deprecated)
- **Phases 3–7:** Not started (blocked until Phase 2 domain review complete)

## Development Commands

```bash
# Setup
python3.10 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# Run tests
pytest -q                                     # Quick run
pytest -v                                     # Verbose
pytest tests/test_golden.py                   # Golden vectors only
pytest -k "test_name"                         # Pattern matching
pytest -v --cov=bazi_engine --cov-fail-under=75   # With coverage (CI threshold)

# Lint & typecheck (CI uses these)
ruff check bazi_engine/ --output-format=github
mypy bazi_engine --ignore-missing-imports

# Start API server
uvicorn bazi_engine.app:app --reload --port 8080

# CLI usage
python -m bazi_engine.cli 2024-02-10T14:30:00 --tz Europe/Berlin --lon 13.405 --lat 52.52
python -m bazi_engine.cli 2024-02-10T14:30:00 --json   # JSON output

# OpenAPI contract
python scripts/export_openapi.py              # Regenerate after endpoint changes
python scripts/export_openapi.py --check      # CI drift check

# Docker (multi-stage: ephe stage downloads & SHA-verifies ephemeris, then app stage)
docker build -t bazi_engine . && docker run -p 8080:8080 bazi_engine

# Deploy
git push origin main                          # Railway auto-deploys (Dockerfile + railway.toml)
# Healthcheck: GET /health; start cmd in railway.toml uses $PORT
```

## Architecture

### Module Hierarchy (import direction: top → bottom only)

```
Level 0: constants.py              # STEMS, BRANCHES, DAY_OFFSET=49
Level 1: types.py                  # Pillar, FourPillars, BaziInput, BaziResult (frozen)
         exc.py                    # BaziEngineError, EphemerisUnavailableError
Level 2: ephemeris.py              # SwissEphBackend, EphemerisBackend protocol
         time_utils.py             # parse_local_iso, LocalTimeError
         solar_time.py             # True Solar Time calculations
Level 3: jieqi.py                  # Solar term calculations, find_crossing() bisection
Level 4: bazi.py                   # compute_bazi() — main 9-step pipeline
         western.py                # compute_western_chart() — planetary positions
         fusion.py                 # Wu-Xing vectors, Harmony Index, equation of time
         transit.py                # Real-time planetary transit (TTLCache per hour)
         aspects.py                # Aspect calculations between planets
         dignities.py              # Planetary dignities (Phase 5 — enterprise differentiator)
         narrative.py              # Text generation from transit state
         provenance.py             # Calculation provenance/audit trail
         impact.py                 # Active-planet/natal impact engine (PRD P0-3)
         impact_harmony.py         # Harmony index, day_mode, drivers
         impact_resonance.py       # BaZi resonance per planet
         impact_types.py           # Impact Pydantic models
         auth.py                   # Top-level API key utilities (distinct from services/auth.py)
         wuxing/                   # Wu-Xing subpackage (constants, vector, analysis, calibration, zones)
         phases/                   # Lunar/Jieqi phase calculations
         match/                    # BaZi-Hehun pair-analysis subpackage (individual.py, textblocks.py, …) — imports Levels 0–4 only, never routers/app
         research/                 # Dataset generator and pattern analysis
Level 5: app.py                    # Thin FastAPI factory (~100 LOC): guard → app → middleware → handlers → mount_all → openapi
         openapi_ext.py            # OpenAPI post-processing (install_custom_openapi) — extracted from app.py
         error_handlers.py         # Global exception handlers (register_exception_handlers) — extracted from app.py
         config_guard.py           # assert_production_auth_config() — fail-closed production startup (FUFIRE-006)
         cli.py                    # Command-line interface
         middleware.py             # RequestIdMiddleware (X-Request-ID validated as UUID + hardening headers)
         limiter.py                # slowapi Limiter; Redis if REDIS_URL set, else in-memory
         routers/                  # One router module per domain (see below); registry.py = declarative mount table
         services/                 # auth, geocoding, soulprint, daily_{eastern,western,fusion,templates},
                                   # signature_blueprint, quiz_affinity, space_weather, superglue_client
         bafe/                     # Contract-first validation subpackage
```

**Critical Rule:** Lower-level modules must never import higher-level modules.

> **Carve-out:** ``bafe.ruleset_loader`` is a pure data-loader (JSON
> read + typed accessors, no side effects). ``bazi.py`` and
> ``bazi_rules.py`` import from it despite the nominal Level-5
> placement; logically it sits at Level 3. ``tests/test_import_hierarchy.py``
> does not enforce a violation for this import.

### Router Structure (`bazi_engine/routers/`)

`app.py` is a thin factory (~100 LOC): production-auth guard → `FastAPI(...)` → middleware/CORS → `register_exception_handlers` → `mount_all` → `install_custom_openapi`. No business logic and no mount/OpenAPI/handler detail lives in `app.py` — those are in `routers/registry.py`, `openapi_ext.py`, and `error_handlers.py`. The mount registry mounts every router twice — once at the legacy unprefixed path and once at `/v1/*` (the API-key-authenticated public surface).

| Router | Endpoints (under `/v1/`) |
|--------|--------------------------|
| `bazi.py` | `/calculate/bazi`, `/calculate/tst` |
| `dayun.py` | `/calculate/bazi/dayun` |
| `western.py` | `/calculate/western`, `/calculate/wuxing` |
| `fusion.py` | `/calculate/fusion` |
| `transit.py` | `/transit/now`, `/transit/timeline`, `/transit/state`, `/transit/narrative` |
| `experience.py` | `/experience/bootstrap`, `/experience/signature-delta`, `/experience/daily` |
| `impact.py` | `/impact/active` (PRD P0-3 dashboard) |
| `geocode.py` | `/geocode` (REQ-001, fufire-domain-ownership) |
| `personalize.py` | `/personalize` — aggregates bazi+western+fusion+geocode (REQ-002/003) |
| `chronometry.py` | `/chronometry/resolve` (beta) |
| `superglue.py` | `/api/superglue/*` (proxy for ElevenLabs/Bazodiac frontend) |
| `validate.py` | `/validate` |
| `chart.py` | `/api/chart` (mounted only on legacy path, no `/v1` alias) |
| `admin.py` | mounted only under `/v1` (no legacy alias) — key-issuance/admin ops |
| `match.py` | `/v1/match/bazi-hehun` — mounted `/v1`-ONLY per DECISION-001 (`docs/plans/2026-07-02-bazi-hehun.md`); deliberate deviation from the dual-mount idiom, no legacy unversioned mount |
| `info.py` | `/health`, `/api` |
| `webhooks.py` | mounted at `/internal/api/webhooks/*`, `include_in_schema=False`, HMAC-verified |
| `shared.py` | Shared Pydantic models/deps (not a router) |

**Mount idiom:** adding a router = one `Mount(...)` row in `bazi_engine/routers/registry.py` (the single source of the dual-mount idiom), so it appears at both `/<path>` and `/v1/<path>` — downstream API key consumers only call `/v1/*`. Full checklist in `docs/adding-an-endpoint.md`. Deviations (public, `/v1`-only, internal) are existing rows to copy.

### BAFE Subpackage (Contract-First Core)

`bazi_engine/bafe/` implements JSON Schema Draft-07 validation for `/validate`:
- `service.py` — Main `validate_request()` orchestrator
- `mapping.py` — Branch coordinate conventions (SHIFT_BOUNDARIES, SHIFT_LONGITUDES)
- `refdata.py` — Reference data policy checks
- `time_model.py` — Time evaluation
- `ruleset_loader.py` — Loads rulesets from `spec/rulesets/`
- `canonical_json.py` — Deterministic config fingerprints
- `kernel.py` — Soft branch weights
- `harmonics.py` — Harmonic analysis utilities
- `errors.py` — Contract-bound error codes and issue factory

Schemas: `spec/schemas/ValidateRequest.schema.json`, `ValidateResponse.schema.json`
Ruleset: `spec/rulesets/standard_bazi_2026.json`

### Wu-Xing Subpackage (`bazi_engine/wuxing/`)

Dedicated subpackage for Five Elements calculations:
- `constants.py` — Element constants and mappings
- `vector.py` — Wu-Xing vector computations
- `analysis.py` — Element balance analysis
- `calibration.py` — Calibration data
- `zones.py` — Zone-based analysis

## Critical Domain Concepts

### Year Boundary (LiChun)
- Year changes at 315° solar longitude (~Feb 3-5), not Jan 1
- Birth before LiChun uses previous year's pillar
- Timezone-sensitive: Berlin LiChun ≠ Beijing LiChun

### Day Pillar Calibration
```python
# Pre-FBP-02-001 source of truth (kept as a Phase-1 baseline reference):
DAY_OFFSET = 49  # in constants.py

# FBP-02-001 (Phase 2) — the canonical engine path now derives the
# offset from the ruleset's day_cycle_anchor:
from bazi_engine.bazi_rules import day_offset_from_ruleset, load_default_ruleset
calculated_offset = day_offset_from_ruleset(load_default_ruleset())
# yields 49 for the shipped standard_bazi_2026 ruleset; will change
# automatically when FBP-02-002 verifies/corrects the anchor.
```
Formula: `sexagenary_day_index = (JDN + 49) % 60`

### DST Handling
- `LocalTimeError` raised for nonexistent/ambiguous times when `strict_local_time=True`
- Use `fold=0`/`fold=1` for ambiguous fall-back times
- Set `strict_local_time=False` for lenient mode

### Swiss Ephemeris
- Required files: sepl_18.se1, semo_18.se1, seas_18.se1, seplm06.se1
- Default path: `/usr/local/share/swisseph`
- Set via `SE_EPHE_PATH` env var or `ephe_path` parameter
- Error "SwissEph file not found" = missing ephemeris data
- Transit calculations use `TTLCache` (1-hour TTL) — `ADR-1`
- Docker: multi-stage build downloads & SHA256-verifies all four ephemeris files at build time (no runtime fetching)

### Auth & Rate Limiting
- `FUFIRE_REQUIRE_API_KEYS=true` — enforces API key auth on V1 routes (`services/auth.py`)
- `WEBHOOK_HMAC_ONLY=true` — HMAC-only webhook validation (ElevenLabs)
- `REDIS_URL` — optional; rate-limiting degrades to in-memory if absent (`limiter.py`)
- V1 routes: rate-keyed by API key; legacy routes: keyed by remote IP

## Testing

CI runs on Python 3.10, 3.11, 3.12. Tests skip gracefully if ephemeris files are missing.

**Conventions (2026-07-08, from the WS-A PII-leak retro):**
- Claims about HTTP response bodies (PII scrubbing, error envelopes, field presence/absence)
  MUST be asserted at the real boundary via `TestClient` on `resp.text`/`resp.json()`.
  Unit-level assertions on the exception object (`str(excinfo.value)`) do NOT count as
  boundary proof — that exact gap let a live PII leak survive two "product-wide" fixes
  (see `tests/test_dst_pii_http.py` for the pattern).
- Tests must never depend on local git ref names (`git show main:...`) — PR CI checkouts
  are detached/shallow without a `main` ref. Use a ref fallback chain plus a visible
  `pytest.skip`, as in `tests/test_match_service_boundary.py`.

Key test files beyond the basics:
- `test_golden.py`, `test_golden_vectors.py` — Pillar correctness
- `test_transit.py`, `test_transit_golden.py`, `test_transit_validation.py` — Transit API
- `test_wuxing_*.py` — Wu-Xing subpackage
- `test_aspects.py` — Aspect calculations
- `test_phases.py` — Lunar/Jieqi phases
- `test_snapshot_stability.py` — Snapshot regression
- `test_import_hierarchy.py` — Enforces module import rules
- `test_openapi_contract.py` — OpenAPI drift detection
- `test_rebrand.py` — FuFirE name consistency

## OpenAPI Contract

**`spec/openapi/openapi.json`** is the source of truth.
- CI checks for drift: `python scripts/export_openapi.py --check`
- Regenerate after any endpoint/model change: `python scripts/export_openapi.py`
- `bazi_engine.__version__` is the single source for version strings
- **Endpoints are frozen** — do not change paths or response structures (downstream services depend on them)

## Gotchas

1. **Circular imports:** Respect module hierarchy strictly (`test_import_hierarchy.py` enforces this)
2. **Immutability:** Never remove `frozen=True` from dataclasses
3. **DAY_OFFSET:** Changing breaks day pillar accuracy for all historical dates
4. **Router architecture:** Business logic belongs in domain modules, not in `routers/` or `app.py`
5. **DST:** Always handle `LocalTimeError` in API endpoints
6. **Ephemeris:** Tests skip without explicit `SE_EPHE_PATH` setup; Docker verifies SHA256 checksums — if upstream ephe files change the build fails
7. **OpenAPI drift:** Run `python scripts/export_openapi.py` after any endpoint change
8. **Experience router:** High-level user-facing endpoints in `routers/experience.py` orchestrate `bazi`, `western`, `fusion`, and `services/soulprint.py` — changes there can cascade widely
9. **Two `auth` modules:** `bazi_engine/auth.py` (top-level helpers) and `bazi_engine/services/auth.py` (FastAPI dependency for API-key enforcement). Don't conflate them; the router dependency comes from `services/auth.py`
10. **Daily v2 endpoints:** `services/daily_eastern.py`, `daily_western.py`, `daily_fusion.py` are composed by `services/daily_templates.py` — the template layer owns the public response shape, so update templates when adding fields
11. **Geocode confidence/candidates:** `services/geocoding.py` is the single source of truth for confidence scoring and candidate projection; both `routers/geocode.py` and `routers/personalize.py` call into it rather than duplicating logic — extend there, not in the routers
