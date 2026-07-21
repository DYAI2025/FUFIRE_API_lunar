# Runbook: Phase 4 — Enhanced Fusion Quality

## What Phase 4 Added

Four improvements to the existing `/impact/active` and `/experience/daily` endpoints:

| Feature | Where it shows | What changed |
|---------|---------------|--------------|
| Aspect-tightness Wu-Xing amplification | `/impact/active` → `harmony_index`, `top_sector` | Tight aspects (orb < 3°) amplify element weight up to ×1.5 |
| House-based planet weighting | `/impact/active` → `active_planets[].weight` | Angular houses ×1.3, cadent houses ×0.8 |
| Minor aspects (quincunx + semi-sextile) | `/impact/active` → `active_planets[]` | quincunx 150° and semi-sextile 30° now detected |
| Daily template variants + sub-fields | `/experience/daily` → `eastern`, `western`, `fusion` | `jieqi_note` and `weekday_note` are now distinct fields |

No new endpoints. No breaking changes to existing fields.

## Prerequisites

```bash
# Start the API server
uv run uvicorn bazi_engine.app:app --reload --port 8080
```

## Verifying Phase 4 Features

### Feature 1: Aspect-Tightness Amplification

The `harmony_index` and element breakdown are now amplified when transit planets form tight aspects to natal positions. A birth chart with a planet at ~0° Aries tested against a transit date when the Sun is also near 0° Aries will show a higher harmony contribution from Fire/Wood than a loose aspect would.

```bash
# Baseline call — inspect harmony_index and evidence
curl -s -X POST http://localhost:8080/impact/active \
  -H "Content-Type: application/json" \
  -d '{
    "birth": {
      "date": "1990-05-23",
      "time": "14:30",
      "tz": "Europe/Berlin",
      "lat": 52.52,
      "lon": 13.405
    },
    "target_date": "2026-04-14"
  }' | python3 -m json.tool | grep -E '"harmony_index"|"top_sector"|"orb"'
```

**What to verify:**
- `evidence.resonance_formula` mentions "aspect_tightness" or shows per-planet amplified weights
- `active_planets` with `orb < 3.0` contribute more to `top_sector` than those with orb 6–8°
- `harmony_index` reflects the tightest current aspects (0.0–1.0)

### Feature 2: House-Based Planet Weighting

Planets in angular houses (1, 4, 7, 10) get ×1.3 weight; cadent houses (3, 6, 9, 12) get ×0.8.
Succedent houses (2, 5, 8, 11) are unchanged (×1.0).

```bash
curl -s -X POST http://localhost:8080/impact/active \
  -H "Content-Type: application/json" \
  -d '{
    "birth": {
      "date": "1990-05-23",
      "time": "14:30",
      "tz": "Europe/Berlin",
      "lat": 52.52,
      "lon": 13.405
    },
    "target_date": "2026-04-14"
  }' | python3 -m json.tool | python3 -c "
import json, sys
data = json.load(sys.stdin)
for p in data.get('active_planets', []):
    print(p.get('planet'), 'orb:', p.get('orb'), 'weight:', p.get('weight'))
"
```

**What to verify:**
- `weight` varies per planet (not all the same)
- Planets in angular houses show higher weights than those in cadent houses
- Weights are deterministic — same birth + target date always produces the same weights

### Feature 3: Minor Aspects (Quincunx + Semi-Sextile)

Quincunx (150°) and semi-sextile (30°) are now detected with factor 0.5 (half-weight).

```bash
curl -s -X POST http://localhost:8080/impact/active \
  -H "Content-Type: application/json" \
  -d '{
    "birth": {
      "date": "1990-05-23",
      "time": "14:30",
      "tz": "Europe/Berlin",
      "lat": 52.52,
      "lon": 13.405
    },
    "target_date": "2026-04-14"
  }' | python3 -m json.tool | python3 -c "
import json, sys
data = json.load(sys.stdin)
minor = [p for p in data.get('active_planets', []) if p.get('aspect') in ('quincunx', 'semi-sextile')]
print('Minor aspects found:', len(minor))
for p in minor:
    print(' ', p.get('planet'), p.get('aspect'), 'orb:', p.get('orb'))
"
```

**What to verify:**
- Response may include `aspect: "quincunx"` or `aspect: "semi-sextile"` entries (depends on current transits)
- These entries have orb values — quincunx near 150°, semi-sextile near 30°
- Their `weight` is lower than equivalent major aspects (half-factor)

**Note:** Minor aspects appear only when the current transit geometry produces a 150° or 30° separation within the active orb. On many dates, zero minor aspects will be present — that is correct.

### Feature 4: Daily Template Variants + Structured Sub-Fields

The `/experience/daily` response now includes `jieqi_note` and `weekday_note` as top-level fields on each section, separate from the `summary` string.

```bash
curl -s -X POST http://localhost:8080/experience/daily \
  -H "Content-Type: application/json" \
  -d '{
    "birth": {"date": "1990-05-23", "time": "14:30:00", "tz": "Europe/Berlin", "lat": 52.52, "lon": 13.405},
    "soulprint_sectors": [0.08, 0.09, 0.08, 0.09, 0.08, 0.08, 0.09, 0.08, 0.09, 0.08, 0.08, 0.08],
    "quiz_sectors": [0.08, 0.09, 0.08, 0.09, 0.08, 0.08, 0.09, 0.08, 0.09, 0.08, 0.08, 0.08],
    "target_date": "2026-04-14"
  }' | python3 -m json.tool | python3 -c "
import json, sys
data = json.load(sys.stdin)
for section in ['eastern', 'western', 'fusion']:
    s = data.get(section, {})
    print(f'--- {section} ---')
    print('  summary:', s.get('summary', '')[:80])
    print('  jieqi_note:', s.get('jieqi_note'))
    print('  weekday_note:', s.get('weekday_note'))
"
```

**What to verify:**
- `eastern.jieqi_note` — non-empty string with seasonal flavor (e.g., "Feuer-Energie steigt...")
- `eastern.weekday_note` — includes weekday name and planetary ruler (e.g., "Dienstag (Mars): ...")
- `western.weekday_note` — same weekday note
- `fusion.jieqi_note` — mentions the active solar term
- `fusion.weekday_note` — mentions the weekday
- `summary` fields are shorter than before (no longer include jieqi/weekday text inline)
- `eastern.evidence.jieqi` — the Jieqi name (e.g., "Qingming")
- `eastern.evidence.weekday` — the German weekday name

### Feature 4b: Daily Summary Variant Rotation

The summary wording rotates deterministically by day-of-year. On consecutive days, the phrasing will differ even for the same birth data.

```bash
# Compare summaries across two dates
for DATE in 2026-04-14 2026-07-15 2026-12-21; do
  echo "=== $DATE ==="
  curl -s -X POST http://localhost:8080/experience/daily \
    -H "Content-Type: application/json" \
    -d "{\"birth\":{\"date\":\"1990-05-23\",\"time\":\"14:30:00\",\"tz\":\"Europe/Berlin\",\"lat\":52.52,\"lon\":13.405},\"soulprint_sectors\":[0.083,0.083,0.083,0.083,0.083,0.083,0.083,0.083,0.083,0.083,0.083,0.083],\"quiz_sectors\":[0.083,0.083,0.083,0.083,0.083,0.083,0.083,0.083,0.083,0.083,0.083,0.083],\"target_date\":\"$DATE\"}" \
    | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['eastern']['summary'][:100])"
done
```

**What to verify:**
- Summaries differ across dates (different jieqi and variant selected)
- Same date always produces the same summary (deterministic)

## Running Phase 4 Tests

```bash
# Aspect-tightness amplification
uv run pytest tests/test_aspects.py tests/test_impact_harmony.py -v

# House-based weighting
uv run pytest tests/test_impact_calc.py -k "house" -v

# Minor aspects
uv run pytest tests/test_aspects.py -k "minor or quincunx or semi" -v

# Daily template variants + sub-fields
uv run pytest tests/test_daily_templates.py tests/test_daily_eastern.py \
  tests/test_daily_western.py tests/test_daily_fusion.py -v

# All Phase 4 related tests
uv run pytest tests/test_aspects.py tests/test_impact_harmony.py tests/test_impact_calc.py \
  tests/test_daily_templates.py tests/test_daily_eastern.py tests/test_daily_western.py \
  tests/test_daily_fusion.py tests/test_daily_eastern_jieqi.py -v

# OpenAPI contract check
uv run python scripts/export_openapi.py --check

# Full suite
uv run pytest tests/ -q
```

## Backwards Compatibility

All Phase 4 changes are **additive**:

| Change | Backwards compatible? |
|--------|-----------------------|
| `jieqi_note` / `weekday_note` fields | Yes — optional fields, absent = null |
| `jieqi` / `weekday` in `DailyEvidence` | Yes — optional, null if not provided |
| Minor aspects in `active_planets` | Yes — new entries appear only when geometry matches |
| Tighter `harmony_index` values | Yes — same field, improved accuracy |
| House weight multipliers | Yes — same `weight` field, new multiplier applied |

Clients that don't read the new fields are unaffected.

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `jieqi_note` is null | Old cached response or wrong endpoint version | Ensure server is running latest code; clear any proxy cache |
| No minor aspects ever appear | Normal — geometry-dependent | Minor aspects (30°, 150°) are rare; test with a specific birth date known to produce them |
| `harmony_index` changed vs. Phase 3 | Expected — tightness amplification and house weights refine it | This is the intended improvement |
| `evidence.jieqi` missing | Eastern evidence not populated | Check `generate_eastern_daily` is returning the `evidence.jieqi` field |
