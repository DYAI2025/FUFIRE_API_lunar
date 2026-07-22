# Canonical Lunar State V2

`POST /v2/astronomy/lunar-state` resolves a local civil timestamp to one
fold-preserving UTC instant and returns the geocentric state of Sun and Moon,
the corrected eight-phase classification, illumination, and the surrounding
true-new-moon events.

The endpoint is V2-only. There is intentionally no bare legacy alias and no
`/v1/astronomy/lunar-state` route. Existing V1 calculations and response
schemas are unchanged.

## Request

```json
{
  "instant": {
    "datetime_local": "2024-04-08T18:21:00",
    "timezone": "UTC",
    "ambiguousTime": "earlier",
    "nonexistentTime": "error"
  }
}
```

| Field | Contract |
|---|---|
| `datetime_local` | Local ISO 8601 datetime without `Z` or a numeric offset. |
| `timezone` | IANA timezone identifier such as `Europe/Berlin` or `UTC`. |
| `ambiguousTime` | `earlier` (fold 0) or `later` (fold 1) during a DST fall-back. |
| `nonexistentTime` | `error` or `shift_forward` during a DST spring-forward gap. |

The request is geocentric; latitude and longitude are therefore neither
required nor accepted. Topocentric altitude/azimuth, rise/set times, and local
horizon visibility are not part of this contract.

## Response outline

```json
{
  "request_id": "…",
  "schema_version": "lunar-state.v2",
  "instant": {
    "input_local": "2024-04-08T18:21:00",
    "resolved_local": "2024-04-08T18:21:00.000000+00:00",
    "utc": "2024-04-08T18:21:00.000000Z",
    "timezone": "UTC",
    "fold": 0,
    "status": "ok",
    "utc_offset_seconds": 0,
    "dst_offset_seconds": 0,
    "timezone_abbreviation": "UTC",
    "adjusted_minutes": 0,
    "warning_code": null,
    "warning": null
  },
  "lunar_state": {
    "jd_ut": 2460409.264583333,
    "sun": {"longitude_deg": 19.39, "latitude_deg": 0.0, "distance_au": 1.001, "speed_longitude_deg_per_day": 0.98},
    "moon": {"longitude_deg": 19.39, "latitude_deg": 0.35, "distance_au": 0.0024, "speed_longitude_deg_per_day": 15.0, "distance_km": 360000.0},
    "phase": {
      "id": "new_moon",
      "index": 0,
      "name_en": "New Moon",
      "name_de": "Neumond",
      "illumination_fraction": 0.00001,
      "elongation_deg": 0.01,
      "trend": "waxing"
    },
    "lunation": {
      "previous_new_moon_utc": "2024-04-08T18:20:…Z",
      "next_new_moon_utc": "2024-05-08T03:21:…Z",
      "age_days": 0.0001,
      "length_days": 29.37,
      "progress": 0.000003
    },
    "method": {
      "id": "canonical-geocentric-lunar-state-v2",
      "ephemeris_mode": "SWIEPH",
      "reference_frame": "geocentric_apparent_ecliptic_of_date",
      "precision_grade": "high_precision",
      "provider_version": "2.10.03",
      "ephemeris_lock_id": "c2185af9a436e8381bcf2e6584afd793a280ec0a70796c03b54ba9441fe27623",
      "supported_utc_start": "1900-01-01T00:00:00+00:00",
      "supported_utc_end_exclusive": "2100-01-01T00:00:00+00:00",
      "warnings": []
    }
  }
}
```

The numbers above are an abbreviated shape example, not golden reference
values. The generated OpenAPI artifact is authoritative for the complete
response schema.

## Eight-phase rule

Phases are centred on their defining astronomical elongations. Boundaries are
half-open and lie 22.5° on either side of each centre.

| Index | ID | Centre | Interval |
|---:|---|---:|---|
| 0 | `new_moon` | 0° | [337.5°, 360°) ∪ [0°, 22.5°) |
| 1 | `waxing_crescent` | 45° | [22.5°, 67.5°) |
| 2 | `first_quarter` | 90° | [67.5°, 112.5°) |
| 3 | `waxing_gibbous` | 135° | [112.5°, 157.5°) |
| 4 | `full_moon` | 180° | [157.5°, 202.5°) |
| 5 | `waning_gibbous` | 225° | [202.5°, 247.5°) |
| 6 | `last_quarter` | 270° | [247.5°, 292.5°) |
| 7 | `waning_crescent` | 315° | [292.5°, 337.5°) |

## Calculation and failure semantics

1. Resolve local civil time exactly once, preserving `fold`, actual offset,
   DST status, adjustment metadata, and warning code.
2. Derive `JD_UT` once from the aware canonical UTC datetime.
3. Calculate apparent geocentric ecliptic-of-date Sun/Moon positions with the
   configured Swiss Ephemeris mode.
4. Obtain physical lunar phenomena with `pheno_ut(JD_UT, Moon)`.
5. Refine the preceding and following new moon from the longitude difference
   and relative angular speed; publish Moon age and lunation progress.

Offset-bearing local input, invalid IANA zones, and DST gaps under `error`
return `422`. Missing high-precision SE1 files under the production SWIEPH
configuration return `503`; the engine does not silently claim SWIEPH after a
Moshier fallback. Numerical failures return the standard `calculation_error`
envelope.

The supported interval is `1900-01-01T00:00:00Z` inclusive through
`2100-01-01T00:00:00Z` exclusive. A local timestamp is checked after timezone
resolution against that UTC interval; out-of-range input returns `422
input_error`. This is a deliberately conservative public contract inside the
locked `sepl_18`/`semo_18` file era, not a claim about Swiss Ephemeris' maximum
theoretical range.

`high_precision` means the request was computed in attested SWIEPH mode with
the exact package-disclosed ephemeris lock. It intentionally does not say
`exact`: model, time-scale, source-data, and rounding uncertainty still exist.
In non-production development mode, another provider is reported as
`degraded` and the lock ID is `null`.

## Independent phase-time reference gate

The locked test corpus records the four primary phases from the official
[U.S. Naval Observatory phase service](https://aa.usno.navy.mil/data/MoonPhases)
for 1900, 1950, 2000, 2024, and 2099. The published values have one-minute
resolution. CI refines each event with the locked SWIEPH provider and currently
requires agreement within 90 seconds, plus transition and seeded lunation
invariants. The 90-second value is a conservative engineering gate; formal
astronomy/domain-owner approval of that tolerance remains **MISSING**, so a
green technical test alone does not authorize production promotion.

## Compatibility boundary

The historical `bazi_engine.phases.lunar_phase` helper remains unchanged for
existing consumers. It is not the calculation authority for this endpoint.
Consumer migration must be explicit because the corrected phase-centred
boundaries can differ from its legacy 45° start-angle buckets.
