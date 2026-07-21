# Runbook: Phase 3 — Impact & Daily v2 API

## Prerequisites

```bash
# Start the API server
uvicorn bazi_engine.app:app --reload --port 8080

# Or with Docker
docker build -t fufire . && docker run -p 8080:8080 fufire
```

## New Endpoints

### POST /impact/active

Computes natal-relative planet impacts with BaZi resonance for a target date.

```bash
curl -X POST http://localhost:8080/impact/active \
  -H "Content-Type: application/json" \
  -d '{
    "birth": {
      "date": "1990-05-23",
      "time": "14:30",
      "tz": "Europe/Berlin",
      "lat": 52.52,
      "lon": 13.405
    },
    "target_date": "2026-04-13"
  }'
```

**Expected response fields:**
- `harmony_index` — 0.0 to 1.0 (Wu-Xing cosine coherence)
- `day_mode` — one of: `calm`, `active`, `tense`, `pulse`
- `intensity` — 0.0 to 1.0
- `active_planets[]` — planets with orb ≤ 8° to natal positions
- `space_weather` — Kp index, solar pressure, storm status
- `drivers[]` — exactly 4: geomagnetic, solar, transit, day_field
- `resonance_badges[]` — non-neutral BaZi resonances
- `top_sector` — dominant Wu-Xing element
- `day_master` — natal day master element
- `evidence` — calculation traceability
- `partial` — true if space weather was unavailable

### POST /experience/daily (v2 — include param)

Extended with optional `include=["impact"]` parameter.

**Without include (v1 backwards compatible):**
```bash
curl -X POST http://localhost:8080/experience/daily \
  -H "Content-Type: application/json" \
  -d '{
    "birth": {"date": "1990-05-23", "time": "14:30:00", "tz": "Europe/Berlin", "lat": 52.52, "lon": 13.405},
    "soulprint_sectors": [0.08, 0.09, 0.08, 0.09, 0.08, 0.08, 0.09, 0.08, 0.09, 0.08, 0.08, 0.08],
    "quiz_sectors": [0.08, 0.09, 0.08, 0.09, 0.08, 0.08, 0.09, 0.08, 0.09, 0.08, 0.08, 0.08],
    "target_date": "2026-04-13"
  }'
```
Expected: `impact` field is `null`.

**With include=["impact"] (v2):**
```bash
curl -X POST http://localhost:8080/experience/daily \
  -H "Content-Type: application/json" \
  -d '{
    "birth": {"date": "1990-05-23", "time": "14:30:00", "tz": "Europe/Berlin", "lat": 52.52, "lon": 13.405},
    "soulprint_sectors": [0.08, 0.09, 0.08, 0.09, 0.08, 0.08, 0.09, 0.08, 0.09, 0.08, 0.08, 0.08],
    "quiz_sectors": [0.08, 0.09, 0.08, 0.09, 0.08, 0.08, 0.09, 0.08, 0.09, 0.08, 0.08, 0.08],
    "target_date": "2026-04-13",
    "include": ["impact"]
  }'
```
Expected: `impact` field contains full ImpactResponse.

## Manual Test Scenarios

### 1. Impact endpoint — happy path
- Send valid birth data → verify 200, all fields present
- Check `active_planets` sorted by tightest orb first
- Check `strength` matches orb: high (<3°), medium (3–5°), low (5–8°)
- Check `bazi_resonance.type` is not `neutral` for active planets

### 2. Impact endpoint — validation
- Omit `birth` → 422
- Invalid date format `"23-05-1990"` → 422
- Invalid timezone `"Not/A/Timezone"` → 422
- Latitude > 90 → 422
- Invalid sector keys `{"plasma": 0.5}` → 422

### 3. Impact endpoint — space weather degradation
- If NOAA is down: `partial: true`, `space_weather.source: "default"` or `"noaa_partial"`
- All other fields still computed correctly

### 4. Daily v2 — backwards compatibility
- No `include` field → `impact` is `null`, all v1 fields present
- `include: []` → same as no include
- `include: ["unknown"]` → `impact` is `null` (unknown values ignored)

### 5. Daily v2 — include=["impact"]
- `include: ["impact"]` → `impact` block present with harmony_index, active_planets, etc.
- v1 fields (western, eastern, fusion, meta) all still present
- `impact.evidence.resonance_formula` is populated (traceability)

### 6. V1 route prefix
- Both `/impact/active` and `/v1/impact/active` work
- Both `/experience/daily` and `/v1/experience/daily` support include

## Running Tests

```bash
# All Phase 3 tests
uv run pytest tests/test_impact_types.py tests/test_impact_calc.py tests/test_impact_resonance.py \
  tests/test_impact_harmony.py tests/test_space_weather.py tests/test_impact_router.py \
  tests/test_impact_golden.py tests/test_experience_daily_v2.py -v

# OpenAPI contract verification
uv run python scripts/export_openapi.py --check

# Full suite
uv run pytest tests/ -q
```

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| 422 on valid birth data | Time format mismatch | `/impact/active` accepts `HH:MM`, `/experience/daily` requires `HH:MM:SS` |
| `partial: true` always | NOAA SWPC unreachable | Check network. Space weather cache is 15-min TTL |
| Empty `active_planets` | No transit aspects within 8° | Normal — depends on birth date and target date |
| Golden tests skipped | Missing ephemeris files | Set `SE_EPHE_PATH` to Swiss Ephemeris file directory |
