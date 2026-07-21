# 🔄 SDLC — BaZi Engine (FuFirE) v1.0.0-rc1

> Software Development Lifecycle Dashboard — initialized 2026-03-30

---

## 📊 Project Vitals

| Metric | Value |
|--------|-------|
| **Version** | `1.0.0-rc1-20260220` |
| **Python** | 3.10 / 3.11 / 3.12 (CI matrix) |
| **Source LOC** | ~9,025 (bazi_engine/) |
| **Test Files** | 66 |
| **Test Cases** | 1,719 |
| **Coverage Gate** | ≥ 75% (CI enforced) |
| **Complexity Gate** | CC > 15 blocked |
| **Branch** | `main` (single trunk) |
| **Deploy Target** | Fly.io (`bafe-2u0e2a`, region: `ams`) |
| **Container** | Python 3.11-slim, multi-stage (ephe-base + app) |

---

## 🏗️ Architecture Summary

```
┌─────────────────────────────────────────────────────────┐
│  FastAPI App (app.py)                                   │
│  ├── /calculate/bazi    → bazi.py:compute_bazi()        │
│  ├── /calculate/western → western.py                    │
│  ├── /calculate/fusion  → fusion.py                     │
│  ├── /calculate/tst     → solar_time.py                 │
│  ├── /validate          → bafe/service.py               │
│  └── /api/*             → webhooks, zodiac, transit     │
├─────────────────────────────────────────────────────────┤
│  Core: ephemeris.py → jieqi.py → bazi.py → fusion.py   │
│  Auth: auth.py + middleware.py + limiter.py (Redis)     │
│  Contract: bafe/ (JSON Schema Draft-07 validation)      │
│  Spec: spec/openapi/openapi.json (Source of Truth)      │
└─────────────────────────────────────────────────────────┘
```

---

## ✅ CI/CD Pipeline

### GitHub Actions (`ci.yml`)

| Job | Gate | Status |
|-----|------|--------|
| **test** | pytest + coverage ≥ 75% | 3-version matrix |
| **typecheck** | mypy (strict imports) | Python 3.11 |
| **lint** | ruff check | Python 3.11 |
| **complexity** | radon CC ≤ 15 | Python 3.11 |
| **codegen** | OpenAPI → TS client compiles | Node 20 |

### Additional Checks
- **OpenAPI drift detection** — `python scripts/export_openapi.py --check`
- **Snapshot stability** — auto-generated on CI if missing
- **Ephe base image** — separate workflow (`build-ephe-base.yml`)

### Deployment
```
Fly.io (auto-stop/auto-start machines)
├── FUFIRE_REQUIRE_API_KEYS=true
├── WEBHOOK_HMAC_ONLY=true
├── HTTPS forced, port 8080
└── 1 shared CPU, 2GB RAM
```

---

## 📁 Source Modules (18 modules)

| Module | Layer | Responsibility |
|--------|-------|----------------|
| `constants.py` | L0 | Stems, Branches, DAY_OFFSET=49 |
| `types.py` | L1 | Frozen dataclasses: Pillar, FourPillars, BaziResult |
| `ephemeris.py` | L2 | SwissEphBackend (pyswisseph) |
| `time_utils.py` | L2 | ISO parse, DST, LocalTimeError |
| `jieqi.py` | L3 | Solar term crossings |
| `solar_time.py` | L3 | True Solar Time |
| `bazi.py` | L4 | 9-step compute_bazi() pipeline |
| `western.py` | L4 | Planetary positions |
| `fusion.py` | L4 | Wu-Xing vectors, Harmony Index |
| `aspects.py` | L4 | Per-planet orb tables |
| `transit.py` | L4 | Outer planets transit events |
| `narrative.py` | L4 | Interpretive text generation |
| `provenance.py` | L4 | Calculation provenance tracking |
| `auth.py` | L5 | API key authentication |
| `middleware.py` | L5 | Request middleware |
| `limiter.py` | L5 | Redis-backed rate limiting |
| `app.py` | L5 | FastAPI endpoints |
| `cli.py` | L5 | CLI interface |
| `bafe/` | L5 | Contract-first validation subpackage |
| `exc.py` | — | Custom exception hierarchy |

---

## 🧪 Test Coverage Map (66 files, 1,719 cases)

### Core Engine
- `test_golden.py` / `test_golden_vectors.py` — Known-correct pillar results
- `test_invariants.py` — Structural properties, DAY_OFFSET
- `test_calibration.py` / `test_h_calibrated.py` — Precision calibration
- `test_lichun_transitions.py` — Year boundary edge cases
- `test_import_hierarchy.py` — Module layer enforcement

### Astronomy & Western
- `test_western.py` / `test_aspects.py` / `test_aspects_negative.py`
- `test_transit.py` / `test_transit_golden.py` / `test_transit_validation.py`
- `test_daily_western.py` / `test_daily_eastern.py` / `test_daily_eastern_jieqi.py`
- `test_mercury_quality.py`

### Fusion & Wu-Xing
- `test_fusion.py` / `test_integration_fusion.py` / `test_daily_fusion.py`
- `test_wuxing_*.py` (4 files) — Vectors, zones, constants, analysis

### API & Contract
- `test_api.py` / `test_endpoints.py` / `test_endpoint_negative.py`
- `test_openapi_contract.py` / `test_mock_contract.py`
- `test_experience_endpoints.py` / `test_experience_schemas.py`
- `test_b2b_api_audit.py` / `test_b2b_infra.py`

### Security & Infrastructure
- `test_error_sanitization.py` / `test_error_handling.py`
- `test_services_auth.py` / `test_services_geocoding.py`
- `test_snapshot_stability.py` / `test_requirements_lock.py`

---

## 📋 SDLC Workflow

### 1. Plan
- Spec docs in `spec/` (master spec, addenda, product roadmap)
- Sprint plans in `spec/FuFirE_B2B_Sprint_Plan_v1.docx`
- Architecture docs in `docs/plans/`, `docs/fusion/`

### 2. Develop
```bash
source .venv/bin/activate
# Feature branch → implement → tests pass → PR
pytest -v --tb=short
ruff check bazi_engine/
mypy bazi_engine --ignore-missing-imports
```

### 3. Verify (CI Gates)
- ✅ 1,719 tests across 3 Python versions
- ✅ Type checking (mypy)
- ✅ Lint (ruff)
- ✅ Complexity (radon CC ≤ 15)
- ✅ OpenAPI drift check
- ✅ TS client codegen compiles

### 4. Deploy
```bash
flyctl deploy           # Production (Fly.io Amsterdam)
# OR
docker build -t bazi_engine . && docker run -p 8080:8080 bazi_engine
```

### 5. Monitor
- Rate limiting (Redis-backed, graceful fallback)
- API key authentication enforced
- HMAC webhook validation
- Error sanitization (no internal details leaked)

---

## ⚠️ Known Constraints & Risks

| Risk | Mitigation |
|------|------------|
| Swiss Ephemeris files required | CI caches; Docker multi-stage with ephe-base image |
| `DAY_OFFSET=49` is sacred | test_invariants.py enforces; AGENTS.md documents |
| DST ambiguity | `LocalTimeError` + `strict_local_time` flag |
| Circular imports | test_import_hierarchy.py enforces layer ordering |
| OpenAPI drift | CI gate: `export_openapi.py --check` |
| Immutability | All dataclasses `frozen=True`; convention in AGENTS.md |

---

## 🎯 Current State: RC1

**Release Candidate 1** — Feature-complete for core BaZi + Western + Fusion.

### Recent Milestones
- ✅ B2B API audit — input sanitization + 63-test audit suite
- ✅ Redis-backed rate limiting with graceful fallback
- ✅ Precise Jieqi via Swiss Ephemeris solar longitude
- ✅ Differentiated per-planet orb table for aspects
- ✅ Outer planets (Uranus/Neptune/Pluto) transit support
- ✅ CI upgraded to Node.js 24 compatible actions

### Next Steps (from roadmap)
- [ ] GA release (v1.0.0)
- [ ] Performance benchmarks
- [ ] SDK distribution (TypeScript client from codegen)
- [ ] Extended documentation site

---

*Generated by SDLC-init • Last updated: 2026-03-30*
