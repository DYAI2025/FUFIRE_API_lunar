# FuFirE API Developer Reference

Contract-aligned with OpenAPI `spec/openapi/openapi.json`; updated 2026-07-21.

This document covers the public legacy, `/v1`, and additive `/v2` surfaces.

## 1. API Overview

- **Title:** FuFirE — Fusion Firmament Engine
- **OpenAPI Version:** 3.1.0
- **API Version:** 1.0.0-rc1-20260220
- **Recommended Integration Surface:** `/v1/*`; use the V2 path for canonical lunar state

## 2. Base URL

| Environment | URL |
|---|---|
| Production | `https://bafe-2u0e2a.fly.dev` |
| Local dev | `http://localhost:8080` |

## 3. Authentication

`/v1/*` and `/v2/*` business endpoints require an API key in the `X-API-Key` header:

```
X-API-Key: ff_pro_<your-secret>
```

The key prefix encodes the tier:

| Key prefix | Tier | Requests/day | Requests/min |
|---|---|---|---|
| `ff_free_` | free | 100 | 5 |
| `ff_starter_` | starter | 1 000 | 20 |
| `ff_pro_` | pro | 10 000 | 100 |
| `ff_enterprise_` | enterprise | unlimited | unlimited |

**Public endpoints** (no key required): `/v1/health`, `/v1/ready`, `/v1/`, `/v1/build`, `/v1/api`, `/v1/info/wuxing-mapping`

Legacy endpoints (without `/v1/` prefix) remain available for backward compatibility.

## 4. Standard Response Headers

Every response includes:

| Header | Description |
|---|---|
| `X-Request-ID` | UUID correlation ID — echoed from client when provided |
| `X-API-Version` | Engine build version |
| `X-Response-Time-ms` | Server processing time in milliseconds |

Authenticated `/v1/*` and `/v2/*` business endpoints additionally include rate-limit headers:

| Header | Description |
|---|---|
| `X-RateLimit-Limit` | Requests per minute for the key's tier (`unlimited` for enterprise) |
| `X-RateLimit-Remaining` | Remaining requests in the current window — **present only when a Redis backend is active** (`REDIS_URL` set). In-memory mode (local dev, no Redis) may omit this header. |

Public `/v1` endpoints listed above are not rate-limited and do not include `X-RateLimit-*` headers.

## 5. Quickstart (Time to First Success)

```bash
# Set your API key and base URL
export FUFIRE_API_KEY="ff_free_your_key_here"
export BASE_URL="https://bafe-2u0e2a.fly.dev"

# 1. Verify connectivity
curl -s "$BASE_URL/v1/health" | jq .

# 2. Calculate BaZi pillars for a birthdate
curl -s -X POST "$BASE_URL/v1/calculate/bazi" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $FUFIRE_API_KEY" \
  -d '{"date":"1990-06-15T14:30:00","tz":"Europe/Berlin","lon":13.405,"lat":52.52}' | jq .pillars

# 3. Calculate Western chart for the same birthdate
curl -s -X POST "$BASE_URL/v1/calculate/western" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $FUFIRE_API_KEY" \
  -d '{"date":"1990-06-15T14:30:00","tz":"Europe/Berlin","lon":13.405,"lat":52.52}' | jq .bodies
```

### Python (requests)

```python
import requests

BASE = "https://bafe-2u0e2a.fly.dev/v1"
HEADERS = {"X-API-Key": "ff_free_your_key_here"}

# BaZi pillars
resp = requests.post(f"{BASE}/calculate/bazi", headers=HEADERS, json={
    "date": "1990-06-15T14:30:00",
    "tz": "Europe/Berlin",
    "lon": 13.405,
    "lat": 52.52,
})
resp.raise_for_status()
pillars = resp.json()["pillars"]
print(f"Year: {pillars['year']['stamm']}-{pillars['year']['zweig']}")

# Fusion analysis (same input)
fusion = requests.post(f"{BASE}/calculate/fusion", headers=HEADERS, json={
    "date": "1990-06-15T14:30:00",
    "tz": "Europe/Berlin",
    "lon": 13.405,
    "lat": 52.52,
}).json()
print(f"Harmony Index: {fusion['harmony_index']}")
```

### TypeScript (fetch)

```typescript
const BASE = "https://bafe-2u0e2a.fly.dev/v1";
const API_KEY = "ff_free_your_key_here";

interface BaziResponse {
  pillars: Record<string, { stamm: string; zweig: string; tier: string; element: string }>;
  dates: { birth_local: string; birth_utc: string; lichun_local: string };
  precision: { birth_time_known: boolean; provisional_fields: string[] };
}

async function calculateBazi(date: string, tz: string, lon: number, lat: number): Promise<BaziResponse> {
  const res = await fetch(`${BASE}/calculate/bazi`, {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-API-Key": API_KEY },
    body: JSON.stringify({ date, tz, lon, lat }),
  });
  if (!res.ok) {
    const err = await res.json();
    throw new Error(`${err.error}: ${err.message}`);
  }
  return res.json();
}

// Usage
const chart = await calculateBazi("1990-06-15T14:30:00", "Europe/Berlin", 13.405, 52.52);
console.log("Year pillar:", chart.pillars.year);
```

### Error Handling Pattern

```python
import requests

try:
    resp = requests.post(f"{BASE}/calculate/bazi", headers=HEADERS, json=payload)
    resp.raise_for_status()
    data = resp.json()
except requests.HTTPError as e:
    error = e.response.json()
    if error["error"] == "ephemeris_unavailable":
        # Server-side issue — retry later
        pass
    elif error["error"] == "validation_error":
        # Bad request — fix input
        print(f"Invalid input: {error['message']}")
    elif e.response.status_code == 429:
        # Rate limited — back off
        retry_after = int(e.response.headers.get("Retry-After", 60))
        time.sleep(retry_after)
```

## 6. Error Envelope (Contract)

```json
{
  "error": "string",
  "message": "string",
  "detail": {},
  "status": 422,
  "path": "/v1/calculate/bazi",
  "timestamp": "2026-03-17T00:00:00Z",
  "request_id": "uuid"
}
```

## 7. Endpoint Catalog

| Method | Legacy Path | `/v1` Path | Auth on `/v1` | Tags | Operation ID |
|---|---|---|---|---|---|
| GET | `/` | `/v1/` | Public | Info | `read_root__get` |
| GET | `/api` | `/v1/api` | Public | Info | `api_endpoint_api_get` |
| POST | `/internal/api/webhooks/chart` | `-` | Internal | Webhooks | `elevenlabs_chart_webhook_api_webhooks_chart_post` |
| GET | `/build` | `/v1/build` | Public | Info | `build_info_build_get` |
| POST | `/calculate/bazi` | `/v1/calculate/bazi` | API key | BaZi | `calculate_bazi_endpoint_calculate_bazi_post` |
| POST | `/calculate/fusion` | `/v1/calculate/fusion` | API key | Fusion / Wu-Xing | `calculate_fusion_endpoint_calculate_fusion_post` |
| POST | `/calculate/tst` | `/v1/calculate/tst` | API key | Fusion / Wu-Xing | `calculate_tst_endpoint_calculate_tst_post` |
| POST | `/calculate/western` | `/v1/calculate/western` | API key | Western Astrology | `calculate_western_endpoint_calculate_western_post` |
| POST | `/calculate/wuxing` | `/v1/calculate/wuxing` | API key | Fusion / Wu-Xing | `calculate_wuxing_endpoint_calculate_wuxing_post` |
| POST | `/chart` | `-` | Public | Chart | `chart_endpoint_chart_post` | **Deprecated** — internal legacy; use `/v1/calculate/wuxing` or `/v1/calculate/western` instead |
| POST | `/experience/bootstrap` | `/v1/experience/bootstrap` | API key | Experience | `experience_bootstrap_experience_bootstrap_post` |
| POST | `/experience/daily` | `/v1/experience/daily` | API key | Experience | `experience_daily_experience_daily_post` |
| POST | `/experience/signature-delta` | `/v1/experience/signature-delta` | API key | Experience | `experience_signature_delta_experience_signature_delta_post` |
| GET | `/health` | `/v1/health` | Public | Info | `health_check_health_get` |
| GET | `/info/wuxing-mapping` | `/v1/info/wuxing-mapping` | Public | Info | `get_wuxing_mapping_info_wuxing_mapping_get` |
| GET | `/ready` | `/v1/ready` | Public | Info | `readiness_check_ready_get` |
| POST | `/transit/narrative` | `/v1/transit/narrative` | API key | Transit | `transit_narrative_transit_narrative_post` |
| GET | `/transit/now` | `/v1/transit/now` | API key | Transit | `transit_now_transit_now_get` |
| POST | `/transit/state` | `/v1/transit/state` | API key | Transit | `transit_state_transit_state_post` |
| GET | `/transit/timeline` | `/v1/transit/timeline` | API key | Transit | `transit_timeline_transit_timeline_get` |
| POST | `/validate` | `/v1/validate` | API key | Validation | `validate_validate_post` |

### V2-only endpoints

| Method | Path | Auth | Tags | Detail |
|---|---|---|---|---|
| POST | `/v2/astronomy/lunar-state` | API key | Astronomy v2 | [Canonical Lunar State V2](03_lunar_state_v2.md) |

## 8. Example Requests (cURL)

### 8.1 Validate a Full Config

```bash
curl -X POST "$BASE_URL/v1/validate" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $FUFIRE_API_KEY" \
  -d '{
    "validate_level": "FULL",
    "engine_config": {
      "engine_version": "1.0.0-rc1-20260220",
      "parameter_set_id": "standard",
      "deterministic": true,
      "compliance_mode": "RELAXED",
      "bazi_ruleset_id": "standard_bazi_2026",
      "refdata": {
        "refdata_pack_id": "refpack-test-001",
        "refdata_mode": "BUNDLED_OFFLINE",
        "allow_network": false,
        "ephemeris_id": "swisseph-2026",
        "tzdb_version_id": "tzdb-2026a",
        "leaps_source_id": "leaps-iers"
      }
    }
  }'
```

### 7.2 Calculate BaZi

```bash
curl -X POST "$BASE_URL/v1/calculate/bazi" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $FUFIRE_API_KEY" \
  -d '{
    "date": "2024-02-10T14:30:00",
    "tz": "Europe/Berlin",
    "lon": 13.405,
    "lat": 52.52,
    "standard": "CIVIL",
    "boundary": "midnight"
  }'
```

### 7.3 Calculate Fusion Score

```bash
curl -X POST "$BASE_URL/v1/calculate/fusion" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $FUFIRE_API_KEY" \
  -d '{
    "date": "2024-02-10T14:30:00",
    "tz": "Europe/Berlin",
    "lon": 13.405,
    "lat": 52.52
  }'
```

### 7.4 Get Real-Time Transit Snapshot

```bash
curl -X GET "$BASE_URL/v1/transit/now?datetime=2026-03-17T10:00:00Z" \
  -H "X-API-Key: $FUFIRE_API_KEY"
```

### 7.5 Build Daily Experience Payload

```bash
curl -X POST "$BASE_URL/v1/experience/daily" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $FUFIRE_API_KEY" \
  -d '{
    "birth": {
      "date": "1990-05-12",
      "time": "14:30:00",
      "tz": "Europe/Berlin",
      "lat": 52.52,
      "lon": 13.405
    },
    "soulprint_sectors": [0.12,0.03,0.05,0.07,0.09,0.11,0.08,0.06,0.10,0.09,0.11,0.09],
    "quiz_sectors": [0.08,0.06,0.09,0.07,0.10,0.11,0.08,0.05,0.09,0.09,0.10,0.08],
    "target_date": "2026-03-18",
    "locale": "de-DE"
  }'
```

## 9. Exact Endpoint Schemas

For each endpoint below, request/response schemas are shown exactly as they are referenced in OpenAPI.

### GET `/`

- **Operation ID:** `read_root__get`
- **Tag(s):** Info
- **`/v1` mirror:** `/v1/`
- **Auth on `/v1`:** Public

**Request Body Schema:** none

**Responses (exact OpenAPI references)**

| Status | Schema (`application/json`) |
|---|---|
| 200 | `{"$ref": "#/components/schemas/RootResponse"}` |

### GET `/api`

- **Operation ID:** `api_endpoint_api_get`
- **Tag(s):** Info
- **`/v1` mirror:** `/v1/api`
- **Auth on `/v1`:** Public

**Parameters**

| Name | In | Required | Type | Description |
|---|---|---|---|---|
| `datum` | query | true | string | Datum im Format YYYY-MM-DD |
| `zeit` | query | true | string | Zeit im Format HH:MM[:SS] |
| `ort` | query | false | - | Ort als 'lat,lon' |
| `tz` | query | false | string | Timezone name |
| `lon` | query | false | number | Longitude in degrees |
| `lat` | query | false | number | Latitude in degrees |
| `ambiguousTime` | query | false | enum[earlier, later] |  |
| `nonexistentTime` | query | false | enum[error, shift_forward] |  |

**Request Body Schema:** none

**Responses (exact OpenAPI references)**

| Status | Schema (`application/json`) |
|---|---|
| 200 | `{"$ref": "#/components/schemas/ApiResponse"}` |
| 422 | `{"$ref": "#/components/schemas/HTTPValidationError"}` |

### POST `/internal/api/webhooks/chart`

> **Internal path** — ElevenLabs integration only, not a public API surface. Hidden from OpenAPI schema (`include_in_schema=False`).

- **Operation ID:** `elevenlabs_chart_webhook_api_webhooks_chart_post`
- **Tag(s):** Webhooks
- **`/v1` mirror:** n/a
- **Auth on `/v1`:** Internal (HMAC/API-Key/Bearer)

**Parameters**

| Name | In | Required | Type | Description |
|---|---|---|---|---|
| `elevenlabs-signature` | header | false | - |  |
| `x-api-key` | header | false | - |  |
| `authorization` | header | false | - |  |

**Request Body Schema:** none

> Runtime contract note: this endpoint parses raw JSON and validates it against `ElevenLabsChartRequest` in server code.
>
> Expected request payload fields:
> - `birthDate` (string, required, format `YYYY-MM-DD`)
> - `birthTime` (string, optional, format `HH:MM`)
> - `birthPlace` (string, optional)
> - `birthLat` (number, optional)
> - `birthLon` (number, optional)
> - `birthTz` (string, optional)
> - `ambiguousTime` (enum: `earlier` | `later`, optional, default `earlier`)
> - `nonexistentTime` (enum: `error` | `shift_forward`, optional, default `error`)

**Responses (exact OpenAPI references)**

| Status | Schema (`application/json`) |
|---|---|
| 200 | `{"$ref": "#/components/schemas/WebhookChartResponse"}` |
| 422 | `{"$ref": "#/components/schemas/HTTPValidationError"}` |

### GET `/build`

- **Operation ID:** `build_info_build_get`
- **Tag(s):** Info
- **`/v1` mirror:** `/v1/build`
- **Auth on `/v1`:** Public

**Request Body Schema:** none

**Responses (exact OpenAPI references)**

| Status | Schema (`application/json`) |
|---|---|
| 200 | `{"$ref": "#/components/schemas/BuildResponse"}` |

### POST `/calculate/bazi`

- **Operation ID:** `calculate_bazi_endpoint_calculate_bazi_post`
- **Tag(s):** BaZi
- **`/v1` mirror:** `/v1/calculate/bazi`
- **Auth on `/v1`:** API key (`X-API-Key`)

**Request Body Schema (exact OpenAPI reference)**

```json
{
  "$ref": "#/components/schemas/BaziRequest"
}
```

**Responses (exact OpenAPI references)**

| Status | Schema (`application/json`) |
|---|---|
| 200 | `{"$ref": "#/components/schemas/BaziResponse"}` |
| 422 | `{"$ref": "#/components/schemas/HTTPValidationError"}` |

### POST `/calculate/fusion`

- **Operation ID:** `calculate_fusion_endpoint_calculate_fusion_post`
- **Tag(s):** Fusion / Wu-Xing
- **`/v1` mirror:** `/v1/calculate/fusion`
- **Auth on `/v1`:** API key (`X-API-Key`)

**Request Body Schema (exact OpenAPI reference)**

```json
{
  "$ref": "#/components/schemas/FusionRequest"
}
```

**Responses (exact OpenAPI references)**

| Status | Schema (`application/json`) |
|---|---|
| 200 | `{"$ref": "#/components/schemas/FusionResponse"}` |
| 422 | `{"$ref": "#/components/schemas/HTTPValidationError"}` |

### POST `/calculate/tst`

- **Operation ID:** `calculate_tst_endpoint_calculate_tst_post`
- **Tag(s):** Fusion / Wu-Xing
- **`/v1` mirror:** `/v1/calculate/tst`
- **Auth on `/v1`:** API key (`X-API-Key`)

**Request Body Schema (exact OpenAPI reference)**

```json
{
  "$ref": "#/components/schemas/TSTRequest"
}
```

**Responses (exact OpenAPI references)**

| Status | Schema (`application/json`) |
|---|---|
| 200 | `{"$ref": "#/components/schemas/TSTResponse"}` |
| 422 | `{"$ref": "#/components/schemas/HTTPValidationError"}` |

### POST `/calculate/western`

- **Operation ID:** `calculate_western_endpoint_calculate_western_post`
- **Tag(s):** Western Astrology
- **`/v1` mirror:** `/v1/calculate/western`
- **Auth on `/v1`:** API key (`X-API-Key`)

**Request Body Schema (exact OpenAPI reference)**

```json
{
  "$ref": "#/components/schemas/WesternRequest"
}
```

**Responses (exact OpenAPI references)**

| Status | Schema (`application/json`) |
|---|---|
| 200 | `{"$ref": "#/components/schemas/WesternResponse"}` |
| 422 | `{"$ref": "#/components/schemas/HTTPValidationError"}` |

### POST `/calculate/wuxing`

- **Operation ID:** `calculate_wuxing_endpoint_calculate_wuxing_post`
- **Tag(s):** Fusion / Wu-Xing
- **`/v1` mirror:** `/v1/calculate/wuxing`
- **Auth on `/v1`:** API key (`X-API-Key`)

**Request Body Schema (exact OpenAPI reference)**

```json
{
  "$ref": "#/components/schemas/WxRequest"
}
```

**Responses (exact OpenAPI references)**

| Status | Schema (`application/json`) |
|---|---|
| 200 | `{"$ref": "#/components/schemas/WxResponse"}` |
| 422 | `{"$ref": "#/components/schemas/HTTPValidationError"}` |

### POST `/chart`

> **Deprecated** — internal legacy endpoint. New callers should use `/v1/calculate/wuxing` or `/v1/calculate/western` instead. This endpoint remains reachable but has no `/v1` alias and is marked `deprecated: true` in the OpenAPI schema.

- **Operation ID:** `chart_endpoint_chart_post`
- **Tag(s):** Chart
- **`/v1` mirror:** n/a (internal legacy only)
- **Auth on `/v1`:** n/a

**Request Body Schema (exact OpenAPI reference)**

```json
{
  "$ref": "#/components/schemas/ChartRequest"
}
```

**Responses (exact OpenAPI references)**

| Status | Schema (`application/json`) |
|---|---|
| 200 | `{"$ref": "#/components/schemas/ChartResponse"}` |
| 422 | `{"$ref": "#/components/schemas/HTTPValidationError"}` |

### POST `/experience/bootstrap`

- **Operation ID:** `experience_bootstrap_experience_bootstrap_post`
- **Tag(s):** Experience
- **`/v1` mirror:** `/v1/experience/bootstrap`
- **Auth on `/v1`:** API key (`X-API-Key`)

**Request Body Schema (exact OpenAPI reference)**

```json
{
  "$ref": "#/components/schemas/BootstrapRequest"
}
```

**Responses (exact OpenAPI references)**

| Status | Schema (`application/json`) |
|---|---|
| 200 | `{"$ref": "#/components/schemas/BootstrapResponse"}` |
| 422 | `{"$ref": "#/components/schemas/HTTPValidationError"}` |

### POST `/experience/daily`

- **Operation ID:** `experience_daily_experience_daily_post`
- **Tag(s):** Experience
- **`/v1` mirror:** `/v1/experience/daily`
- **Auth on `/v1`:** API key (`X-API-Key`)

**Request Body Schema (exact OpenAPI reference)**

```json
{
  "$ref": "#/components/schemas/DailyRequest"
}
```

**Responses (exact OpenAPI references)**

| Status | Schema (`application/json`) |
|---|---|
| 200 | `{"$ref": "#/components/schemas/DailyResponse"}` |
| 422 | `{"$ref": "#/components/schemas/HTTPValidationError"}` |

### POST `/experience/signature-delta`

- **Operation ID:** `experience_signature_delta_experience_signature_delta_post`
- **Tag(s):** Experience
- **`/v1` mirror:** `/v1/experience/signature-delta`
- **Auth on `/v1`:** API key (`X-API-Key`)

**Request Body Schema (exact OpenAPI reference)**

```json
{
  "$ref": "#/components/schemas/SignatureDeltaRequest"
}
```

**Responses (exact OpenAPI references)**

| Status | Schema (`application/json`) |
|---|---|
| 200 | `{"$ref": "#/components/schemas/SignatureDeltaResponse"}` |
| 422 | `{"$ref": "#/components/schemas/HTTPValidationError"}` |

### GET `/health`

- **Operation ID:** `health_check_health_get`
- **Tag(s):** Info
- **`/v1` mirror:** `/v1/health`
- **Auth on `/v1`:** Public

**Request Body Schema:** none

**Responses (exact OpenAPI references)**

| Status | Schema (`application/json`) |
|---|---|
| 200 | `{"$ref": "#/components/schemas/HealthResponse"}` |

### GET `/info/wuxing-mapping`

- **Operation ID:** `get_wuxing_mapping_info_wuxing_mapping_get`
- **Tag(s):** Info
- **`/v1` mirror:** `/v1/info/wuxing-mapping`
- **Auth on `/v1`:** Public

**Request Body Schema:** none

**Responses (exact OpenAPI references)**

| Status | Schema (`application/json`) |
|---|---|
| 200 | `{"$ref": "#/components/schemas/WuxingMappingResponse"}` |

### GET `/ready`

- **Operation ID:** `readiness_check_ready_get`
- **Tag(s):** Info
- **`/v1` mirror:** `/v1/ready`
- **Auth on `/v1`:** Public

**Request Body Schema:** none

**Responses (exact OpenAPI references)**

| Status | Schema (`application/json`) |
|---|---|
| 200 | `{"$ref": "#/components/schemas/HealthResponse"}` |

### POST `/transit/narrative`

- **Operation ID:** `transit_narrative_transit_narrative_post`
- **Tag(s):** Transit
- **`/v1` mirror:** `/v1/transit/narrative`
- **Auth on `/v1`:** API key (`X-API-Key`)

**Request Body Schema (exact OpenAPI reference)**

```json
{
  "$ref": "#/components/schemas/NarrativeRequest"
}
```

**Responses (exact OpenAPI references)**

| Status | Schema (`application/json`) |
|---|---|
| 200 | `{"$ref": "#/components/schemas/NarrativeResponse"}` |
| 422 | `{"$ref": "#/components/schemas/HTTPValidationError"}` |

### GET `/transit/now`

- **Operation ID:** `transit_now_transit_now_get`
- **Tag(s):** Transit
- **`/v1` mirror:** `/v1/transit/now`
- **Auth on `/v1`:** API key (`X-API-Key`)

**Parameters**

| Name | In | Required | Type | Description |
|---|---|---|---|---|
| `datetime` | query | false | - | Optional UTC datetime in ISO format. Default: now. |

**Request Body Schema:** none

**Responses (exact OpenAPI references)**

| Status | Schema (`application/json`) |
|---|---|
| 200 | `{"$ref": "#/components/schemas/TransitNowResponse"}` |
| 422 | `{"$ref": "#/components/schemas/HTTPValidationError"}` |

### POST `/transit/state`

- **Operation ID:** `transit_state_transit_state_post`
- **Tag(s):** Transit
- **`/v1` mirror:** `/v1/transit/state`
- **Auth on `/v1`:** API key (`X-API-Key`)

**Request Body Schema (exact OpenAPI reference)**

```json
{
  "$ref": "#/components/schemas/TransitStateRequest"
}
```

**Responses (exact OpenAPI references)**

| Status | Schema (`application/json`) |
|---|---|
| 200 | `{"$ref": "#/components/schemas/TransitStateResponse"}` |
| 422 | `{"$ref": "#/components/schemas/HTTPValidationError"}` |

### GET `/transit/timeline`

- **Operation ID:** `transit_timeline_transit_timeline_get`
- **Tag(s):** Transit
- **`/v1` mirror:** `/v1/transit/timeline`
- **Auth on `/v1`:** API key (`X-API-Key`)

**Parameters**

| Name | In | Required | Type | Description |
|---|---|---|---|---|
| `days` | query | false | integer | Number of days to forecast (1-30). |

**Request Body Schema:** none

**Responses (exact OpenAPI references)**

| Status | Schema (`application/json`) |
|---|---|
| 200 | `{"$ref": "#/components/schemas/TimelineResponse"}` |
| 422 | `{"$ref": "#/components/schemas/HTTPValidationError"}` |

### POST `/validate`

- **Operation ID:** `validate_validate_post`
- **Tag(s):** Validation
- **`/v1` mirror:** `/v1/validate`
- **Auth on `/v1`:** API key (`X-API-Key`)

**Request Body Schema (exact OpenAPI reference)**

```json
{
  "$ref": "#/components/schemas/ValidateRequest"
}
```

**Responses (exact OpenAPI references)**

| Status | Schema (`application/json`) |
|---|---|
| 200 | `{"$ref": "#/components/schemas/ValidateResponse"}` |
| 422 | `{"$ref": "#/components/schemas/ErrorEnvelope"}` |
| 500 | `{"$ref": "#/components/schemas/ErrorEnvelope"}` |

## 8. Schema Appendix (Exact Components)

The following component schemas are directly referenced by endpoint request/response contracts.

### `ApiResponse`

```json
{
  "properties": {
    "sonne": {
      "type": "string",
      "title": "Sonne"
    },
    "input": {
      "additionalProperties": true,
      "type": "object",
      "title": "Input"
    }
  },
  "type": "object",
  "required": [
    "sonne",
    "input"
  ],
  "title": "ApiResponse"
}
```

### `BaziRequest`

```json
{
  "properties": {
    "date": {
      "type": "string",
      "title": "Date",
      "description": "Local ISO8601 datetime"
    },
    "tz": {
      "type": "string",
      "title": "Tz",
      "description": "IANA timezone name",
      "default": "Europe/Berlin"
    },
    "lon": {
      "type": "number",
      "title": "Lon",
      "description": "Longitude in degrees",
      "default": 13.405
    },
    "lat": {
      "type": "number",
      "title": "Lat",
      "description": "Latitude in degrees",
      "default": 52.52
    },
    "standard": {
      "type": "string",
      "enum": [
        "CIVIL",
        "LMT"
      ],
      "title": "Standard",
      "default": "CIVIL"
    },
    "boundary": {
      "type": "string",
      "enum": [
        "midnight",
        "zi"
      ],
      "title": "Boundary",
      "default": "midnight"
    },
    "ambiguousTime": {
      "type": "string",
      "enum": [
        "earlier",
        "later"
      ],
      "title": "Ambiguoustime",
      "default": "earlier"
    },
    "nonexistentTime": {
      "type": "string",
      "enum": [
        "error",
        "shift_forward"
      ],
      "title": "Nonexistenttime",
      "default": "error"
    }
  },
  "type": "object",
  "required": [
    "date"
  ],
  "title": "BaziRequest"
}
```

### `BaziResponse`

```json
{
  "properties": {
    "input": {
      "$ref": "#/components/schemas/BaziRequest"
    },
    "pillars": {
      "$ref": "#/components/schemas/BaziPillarsResponse"
    },
    "chinese": {
      "$ref": "#/components/schemas/ChineseSection"
    },
    "dates": {
      "$ref": "#/components/schemas/BaziDatesResponse"
    },
    "transition": {
      "$ref": "#/components/schemas/BaziTransitionResponse"
    },
    "solar_terms_count": {
      "type": "integer",
      "title": "Solar Terms Count"
    },
    "provenance": {
      "$ref": "#/components/schemas/ProvenanceResponse"
    },
    "derivation_trace": {
      "anyOf": [
        {
          "additionalProperties": true,
          "type": "object"
        },
        {
          "type": "null"
        }
      ],
      "title": "Derivation Trace"
    }
  },
  "type": "object",
  "required": [
    "input",
    "pillars",
    "chinese",
    "dates",
    "transition",
    "solar_terms_count",
    "provenance"
  ],
  "title": "BaziResponse"
}
```

### `BootstrapRequest`

```json
{
  "properties": {
    "birth": {
      "$ref": "#/components/schemas/BirthInput"
    },
    "locale": {
      "type": "string",
      "title": "Locale",
      "default": "de-DE"
    }
  },
  "type": "object",
  "required": [
    "birth"
  ],
  "title": "BootstrapRequest"
}
```

### `BootstrapResponse`

```json
{
  "properties": {
    "profile": {
      "$ref": "#/components/schemas/ProfileSummary"
    },
    "soulprint_sectors": {
      "items": {
        "type": "number"
      },
      "type": "array",
      "maxItems": 12,
      "minItems": 12,
      "title": "Soulprint Sectors"
    },
    "signature_blueprint": {
      "$ref": "#/components/schemas/SignatureBlueprint"
    },
    "meta": {
      "$ref": "#/components/schemas/MetaInfo"
    }
  },
  "type": "object",
  "required": [
    "profile",
    "soulprint_sectors",
    "signature_blueprint",
    "meta"
  ],
  "title": "BootstrapResponse"
}
```

### `BuildResponse`

```json
{
  "properties": {
    "version": {
      "type": "string",
      "title": "Version"
    },
    "railway_commit_sha": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Railway Commit Sha"
    },
    "railway_deploy_id": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Railway Deploy Id"
    },
    "fly_alloc_id": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Fly Alloc Id"
    },
    "fly_region": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Fly Region"
    }
  },
  "type": "object",
  "required": [
    "version"
  ],
  "title": "BuildResponse"
}
```

### `ChartRequest`

```json
{
  "properties": {
    "local_datetime": {
      "type": "string",
      "title": "Local Datetime",
      "description": "ISO 8601 local datetime"
    },
    "tz_id": {
      "type": "string",
      "title": "Tz Id",
      "description": "IANA timezone name",
      "default": "Europe/Berlin"
    },
    "geo_lon_deg": {
      "type": "number",
      "title": "Geo Lon Deg",
      "description": "Geographic longitude in degrees",
      "default": 13.405
    },
    "geo_lat_deg": {
      "type": "number",
      "title": "Geo Lat Deg",
      "description": "Geographic latitude in degrees",
      "default": 52.52
    },
    "dst_policy": {
      "type": "string",
      "enum": [
        "error",
        "earlier",
        "later"
      ],
      "title": "Dst Policy",
      "default": "error"
    },
    "bodies": {
      "anyOf": [
        {
          "items": {
            "type": "string"
          },
          "type": "array"
        },
        {
          "type": "null"
        }
      ],
      "title": "Bodies",
      "description": "Filter planetary bodies (default: all)"
    },
    "include_validation": {
      "type": "boolean",
      "title": "Include Validation",
      "default": false
    },
    "time_standard": {
      "type": "string",
      "enum": [
        "CIVIL",
        "LMT"
      ],
      "title": "Time Standard",
      "default": "CIVIL"
    },
    "day_boundary": {
      "type": "string",
      "enum": [
        "midnight",
        "zi"
      ],
      "title": "Day Boundary",
      "default": "midnight"
    }
  },
  "type": "object",
  "required": [
    "local_datetime"
  ],
  "title": "ChartRequest"
}
```

### `ChartResponse`

```json
{
  "properties": {
    "engine_version": {
      "type": "string",
      "title": "Engine Version"
    },
    "parameter_set_id": {
      "type": "string",
      "title": "Parameter Set Id"
    },
    "time_scales": {
      "$ref": "#/components/schemas/TimeScales"
    },
    "positions": {
      "items": {
        "$ref": "#/components/schemas/Position"
      },
      "type": "array",
      "title": "Positions"
    },
    "bazi": {
      "$ref": "#/components/schemas/BaziSection"
    },
    "wuxing": {
      "$ref": "#/components/schemas/WuXingSection"
    },
    "houses": {
      "additionalProperties": {
        "type": "number"
      },
      "type": "object",
      "title": "Houses"
    },
    "angles": {
      "additionalProperties": {
        "type": "number"
      },
      "type": "object",
      "title": "Angles"
    },
    "validation": {
      "anyOf": [
        {
          "$ref": "#/components/schemas/ValidationResult"
        },
        {
          "type": "null"
        }
      ]
    }
  },
  "type": "object",
  "required": [
    "engine_version",
    "parameter_set_id",
    "time_scales",
    "positions",
    "bazi",
    "wuxing",
    "houses",
    "angles"
  ],
  "title": "ChartResponse"
}
```

### `DailyRequest`

```json
{
  "properties": {
    "birth": {
      "$ref": "#/components/schemas/BirthInput"
    },
    "soulprint_sectors": {
      "items": {
        "type": "number"
      },
      "type": "array",
      "maxItems": 12,
      "minItems": 12,
      "title": "Soulprint Sectors"
    },
    "quiz_sectors": {
      "items": {
        "type": "number"
      },
      "type": "array",
      "maxItems": 12,
      "minItems": 12,
      "title": "Quiz Sectors"
    },
    "target_date": {
      "type": "string",
      "pattern": "^\\d{4}-\\d{2}-\\d{2}$",
      "title": "Target Date"
    },
    "locale": {
      "type": "string",
      "title": "Locale",
      "default": "de-DE"
    }
  },
  "type": "object",
  "required": [
    "birth",
    "soulprint_sectors",
    "quiz_sectors",
    "target_date"
  ],
  "title": "DailyRequest"
}
```

### `DailyResponse`

```json
{
  "properties": {
    "date": {
      "type": "string",
      "title": "Date"
    },
    "western": {
      "$ref": "#/components/schemas/DailySection"
    },
    "eastern": {
      "$ref": "#/components/schemas/DailySection"
    },
    "fusion": {
      "$ref": "#/components/schemas/DailyFusion"
    },
    "meta": {
      "$ref": "#/components/schemas/MetaInfo"
    }
  },
  "type": "object",
  "required": [
    "date",
    "western",
    "eastern",
    "fusion",
    "meta"
  ],
  "title": "DailyResponse"
}
```

### `ErrorEnvelope`

```json
{
  "type": "object",
  "properties": {
    "error": {
      "type": "string"
    },
    "message": {
      "type": "string"
    },
    "detail": {
      "type": "object"
    },
    "status": {
      "type": "integer"
    },
    "path": {
      "type": "string"
    },
    "timestamp": {
      "type": "string"
    },
    "request_id": {
      "type": "string"
    }
  },
  "required": [
    "error",
    "message",
    "request_id"
  ]
}
```

### `FusionRequest`

```json
{
  "properties": {
    "date": {
      "type": "string",
      "title": "Date",
      "description": "ISO 8601 local date time"
    },
    "tz": {
      "type": "string",
      "title": "Tz",
      "description": "Timezone name",
      "default": "Europe/Berlin"
    },
    "lon": {
      "type": "number",
      "title": "Lon",
      "description": "Longitude in degrees"
    },
    "lat": {
      "type": "number",
      "title": "Lat",
      "description": "Latitude in degrees"
    },
    "ambiguousTime": {
      "type": "string",
      "enum": [
        "earlier",
        "later"
      ],
      "title": "Ambiguoustime",
      "default": "earlier"
    },
    "nonexistentTime": {
      "type": "string",
      "enum": [
        "error",
        "shift_forward"
      ],
      "title": "Nonexistenttime",
      "default": "error"
    },
    "bazi_pillars": {
      "anyOf": [
        {
          "additionalProperties": {
            "additionalProperties": {
              "type": "string"
            },
            "type": "object"
          },
          "type": "object"
        },
        {
          "type": "null"
        }
      ],
      "title": "Bazi Pillars",
      "description": "BaZi pillars (auto-computed if omitted)"
    }
  },
  "type": "object",
  "required": [
    "date",
    "lon",
    "lat"
  ],
  "title": "FusionRequest"
}
```

### `FusionResponse`

```json
{
  "properties": {
    "input": {
      "additionalProperties": true,
      "type": "object",
      "title": "Input"
    },
    "wu_xing_vectors": {
      "additionalProperties": {
        "additionalProperties": {
          "type": "number"
        },
        "type": "object"
      },
      "type": "object",
      "title": "Wu Xing Vectors"
    },
    "harmony_index": {
      "additionalProperties": true,
      "type": "object",
      "title": "Harmony Index"
    },
    "calibration": {
      "anyOf": [
        {
          "additionalProperties": true,
          "type": "object"
        },
        {
          "type": "null"
        }
      ],
      "title": "Calibration"
    },
    "elemental_comparison": {
      "additionalProperties": {
        "additionalProperties": {
          "type": "number"
        },
        "type": "object"
      },
      "type": "object",
      "title": "Elemental Comparison"
    },
    "cosmic_state": {
      "type": "number",
      "title": "Cosmic State"
    },
    "fusion_interpretation": {
      "type": "string",
      "title": "Fusion Interpretation"
    },
    "contribution_ledger": {
      "anyOf": [
        {
          "additionalProperties": true,
          "type": "object"
        },
        {
          "type": "null"
        }
      ],
      "title": "Contribution Ledger"
    },
    "house_quality": {
      "anyOf": [
        {
          "$ref": "#/components/schemas/HouseQuality"
        },
        {
          "type": "null"
        }
      ]
    },
    "provenance": {
      "$ref": "#/components/schemas/ProvenanceResponse"
    }
  },
  "type": "object",
  "required": [
    "input",
    "wu_xing_vectors",
    "harmony_index",
    "elemental_comparison",
    "cosmic_state",
    "fusion_interpretation",
    "provenance"
  ],
  "title": "FusionResponse"
}
```

### `HTTPValidationError`

```json
{
  "properties": {
    "detail": {
      "items": {
        "$ref": "#/components/schemas/ValidationError"
      },
      "type": "array",
      "title": "Detail"
    }
  },
  "type": "object",
  "title": "HTTPValidationError"
}
```

### `HealthResponse`

```json
{
  "properties": {
    "status": {
      "type": "string",
      "title": "Status"
    },
    "engine": {
      "type": "string",
      "title": "Engine",
      "default": "FuFirE"
    },
    "version": {
      "type": "string",
      "title": "Version",
      "default": ""
    },
    "dependencies": {
      "additionalProperties": true,
      "type": "object",
      "title": "Dependencies",
      "default": {}
    }
  },
  "type": "object",
  "required": [
    "status"
  ],
  "title": "HealthResponse"
}
```

### `NarrativeRequest`

```json
{
  "properties": {
    "transit_state": {
      "$ref": "#/components/schemas/TransitStateInput"
    }
  },
  "type": "object",
  "required": [
    "transit_state"
  ],
  "title": "NarrativeRequest"
}
```

### `NarrativeResponse`

```json
{
  "properties": {
    "headline": {
      "type": "string",
      "title": "Headline"
    },
    "body": {
      "type": "string",
      "title": "Body"
    },
    "advice": {
      "type": "string",
      "title": "Advice"
    },
    "pushworthy": {
      "type": "boolean",
      "title": "Pushworthy"
    },
    "push_text": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Push Text"
    }
  },
  "type": "object",
  "required": [
    "headline",
    "body",
    "advice",
    "pushworthy"
  ],
  "title": "NarrativeResponse"
}
```

### `RootResponse`

```json
{
  "properties": {
    "status": {
      "type": "string",
      "title": "Status"
    },
    "service": {
      "type": "string",
      "title": "Service"
    },
    "version": {
      "type": "string",
      "title": "Version"
    }
  },
  "type": "object",
  "required": [
    "status",
    "service",
    "version"
  ],
  "title": "RootResponse"
}
```

### `SignatureDeltaRequest`

```json
{
  "properties": {
    "soulprint_sectors": {
      "items": {
        "type": "number"
      },
      "type": "array",
      "maxItems": 12,
      "minItems": 12,
      "title": "Soulprint Sectors"
    },
    "signature_blueprint": {
      "$ref": "#/components/schemas/SignatureBlueprint"
    },
    "quiz_answer": {
      "$ref": "#/components/schemas/QuizAnswer"
    }
  },
  "type": "object",
  "required": [
    "soulprint_sectors",
    "signature_blueprint",
    "quiz_answer"
  ],
  "title": "SignatureDeltaRequest"
}
```

### `SignatureDeltaResponse`

```json
{
  "properties": {
    "quiz_sectors": {
      "items": {
        "type": "number"
      },
      "type": "array",
      "maxItems": 12,
      "minItems": 12,
      "title": "Quiz Sectors"
    },
    "signature_delta": {
      "$ref": "#/components/schemas/SignatureDelta"
    },
    "signature_blueprint": {
      "$ref": "#/components/schemas/SignatureBlueprint"
    }
  },
  "type": "object",
  "required": [
    "quiz_sectors",
    "signature_delta",
    "signature_blueprint"
  ],
  "title": "SignatureDeltaResponse"
}
```

### `TSTRequest`

```json
{
  "properties": {
    "date": {
      "type": "string",
      "title": "Date",
      "description": "ISO 8601 local date time"
    },
    "tz": {
      "type": "string",
      "title": "Tz",
      "description": "Timezone name",
      "default": "Europe/Berlin"
    },
    "lon": {
      "type": "number",
      "title": "Lon",
      "description": "Longitude in degrees"
    },
    "ambiguousTime": {
      "type": "string",
      "enum": [
        "earlier",
        "later"
      ],
      "title": "Ambiguoustime",
      "default": "earlier"
    },
    "nonexistentTime": {
      "type": "string",
      "enum": [
        "error",
        "shift_forward"
      ],
      "title": "Nonexistenttime",
      "default": "error"
    }
  },
  "type": "object",
  "required": [
    "date",
    "lon"
  ],
  "title": "TSTRequest"
}
```

### `TSTResponse`

```json
{
  "properties": {
    "input": {
      "additionalProperties": true,
      "type": "object",
      "title": "Input"
    },
    "civil_time_hours": {
      "type": "number",
      "title": "Civil Time Hours"
    },
    "longitude_correction_hours": {
      "type": "number",
      "title": "Longitude Correction Hours"
    },
    "equation_of_time_hours": {
      "type": "number",
      "title": "Equation Of Time Hours"
    },
    "true_solar_time_hours": {
      "type": "number",
      "title": "True Solar Time Hours"
    },
    "true_solar_time_formatted": {
      "type": "string",
      "title": "True Solar Time Formatted"
    },
    "provenance": {
      "$ref": "#/components/schemas/ProvenanceResponse"
    }
  },
  "type": "object",
  "required": [
    "input",
    "civil_time_hours",
    "longitude_correction_hours",
    "equation_of_time_hours",
    "true_solar_time_hours",
    "true_solar_time_formatted",
    "provenance"
  ],
  "title": "TSTResponse"
}
```

### `TimelineResponse`

```json
{
  "properties": {
    "days": {
      "items": {
        "$ref": "#/components/schemas/TimelineDayResponse"
      },
      "type": "array",
      "title": "Days"
    }
  },
  "type": "object",
  "required": [
    "days"
  ],
  "title": "TimelineResponse"
}
```

### `TransitNowResponse`

```json
{
  "properties": {
    "computed_at": {
      "type": "string",
      "title": "Computed At"
    },
    "planets": {
      "additionalProperties": {
        "$ref": "#/components/schemas/PlanetPosition"
      },
      "type": "object",
      "title": "Planets"
    },
    "sector_intensity": {
      "items": {
        "type": "number"
      },
      "type": "array",
      "title": "Sector Intensity"
    }
  },
  "type": "object",
  "required": [
    "computed_at",
    "planets",
    "sector_intensity"
  ],
  "title": "TransitNowResponse"
}
```

### `TransitStateRequest`

```json
{
  "properties": {
    "soulprint_sectors": {
      "items": {
        "type": "number"
      },
      "type": "array",
      "maxItems": 12,
      "minItems": 12,
      "title": "Soulprint Sectors"
    },
    "quiz_sectors": {
      "items": {
        "type": "number"
      },
      "type": "array",
      "maxItems": 12,
      "minItems": 12,
      "title": "Quiz Sectors"
    }
  },
  "type": "object",
  "required": [
    "soulprint_sectors",
    "quiz_sectors"
  ],
  "title": "TransitStateRequest"
}
```

### `TransitStateResponse`

```json
{
  "properties": {
    "schema": {
      "type": "string",
      "title": "Schema"
    },
    "generated_at": {
      "type": "string",
      "title": "Generated At"
    },
    "ring": {
      "$ref": "#/components/schemas/RingSectors"
    },
    "transit_contribution": {
      "$ref": "#/components/schemas/TransitContribution"
    },
    "delta": {
      "$ref": "#/components/schemas/Delta"
    },
    "events": {
      "items": {
        "additionalProperties": true,
        "type": "object"
      },
      "type": "array",
      "title": "Events"
    }
  },
  "type": "object",
  "required": [
    "schema",
    "generated_at",
    "ring",
    "transit_contribution",
    "delta",
    "events"
  ],
  "title": "TransitStateResponse"
}
```

### `ValidateRequest`

```json
{
  "additionalProperties": false,
  "properties": {
    "bazi_pillars_override": {
      "additionalProperties": false,
      "description": "Optional override of BaZi pillars (skips anchor dependency).",
      "properties": {
        "pillars": {
          "items": {
            "$ref": "#/components/schemas/Pillar"
          },
          "maxItems": 4,
          "minItems": 4,
          "type": "array"
        }
      },
      "type": [
        "object",
        "null"
      ]
    },
    "birth_event": {
      "$ref": "#/components/schemas/BirthEvent"
    },
    "engine_config": {
      "$ref": "#/components/schemas/EngineConfig"
    },
    "now_utc_override": {
      "description": "For deterministic tests: fixed 'now' used for expiry checks.",
      "format": "date-time",
      "type": [
        "string",
        "null"
      ]
    },
    "positions_override": {
      "additionalProperties": false,
      "description": "Optional override of western body positions (skips ephemeris).",
      "properties": {
        "bodies": {
          "items": {
            "$ref": "#/components/schemas/BodyPosition"
          },
          "type": "array"
        },
        "time_scale": {
          "enum": [
            "TT",
            "UTC",
            "UT1"
          ],
          "type": "string"
        }
      },
      "type": [
        "object",
        "null"
      ]
    },
    "refdata_manifest_inline": {
      "$ref": "#/components/schemas/RefDataManifest"
    },
    "refdata_pack_id": {
      "type": "string"
    },
    "ruleset_id": {
      "type": "string"
    },
    "ruleset_inline": {
      "$ref": "#/components/schemas/BaZiRuleset"
    },
    "validate_level": {
      "default": "FULL",
      "enum": [
        "BASIC",
        "FULL"
      ],
      "type": "string"
    }
  },
  "required": [
    "engine_config"
  ],
  "title": "ValidateRequest",
  "type": "object"
}
```

### `ValidateResponse`

```json
{
  "additionalProperties": false,
  "properties": {
    "compliance_components": {
      "additionalProperties": false,
      "properties": {
        "DISCRETIZATION": {
          "$ref": "#/components/schemas/ComponentStatus"
        },
        "EPHEMERIS": {
          "$ref": "#/components/schemas/ComponentStatus"
        },
        "FRAMES": {
          "$ref": "#/components/schemas/ComponentStatus"
        },
        "INTERPRETATION_POLICY": {
          "$ref": "#/components/schemas/ComponentStatus"
        },
        "REFDATA": {
          "$ref": "#/components/schemas/ComponentStatus"
        },
        "REPRODUCIBILITY": {
          "$ref": "#/components/schemas/ComponentStatus"
        },
        "TIME": {
          "$ref": "#/components/schemas/ComponentStatus"
        }
      },
      "required": [
        "REFDATA",
        "TIME",
        "FRAMES",
        "EPHEMERIS",
        "DISCRETIZATION",
        "REPRODUCIBILITY",
        "INTERPRETATION_POLICY"
      ],
      "type": "object"
    },
    "compliance_status": {
      "enum": [
        "COMPLIANT",
        "DEGRADED",
        "NON_COMPLIANT"
      ],
      "type": "string"
    },
    "errors": {
      "items": {
        "$ref": "#/components/schemas/Issue"
      },
      "type": "array"
    },
    "evidence": {
      "additionalProperties": false,
      "properties": {
        "discretization": {
          "$ref": "#/components/schemas/DiscretizationEvidence"
        },
        "ephemeris": {
          "$ref": "#/components/schemas/EphemerisEvidence"
        },
        "frames": {
          "$ref": "#/components/schemas/FramesEvidence"
        },
        "interpretation": {
          "$ref": "#/components/schemas/InterpEvidence"
        },
        "refdata": {
          "$ref": "#/components/schemas/RefDataEvidence"
        },
        "reproducibility": {
          "$ref": "#/components/schemas/ReproEvidence"
        },
        "time": {
          "$ref": "#/components/schemas/TimeEvidence"
        }
      },
      "required": [
        "refdata",
        "time",
        "discretization",
        "reproducibility"
      ],
      "type": "object"
    },
    "warnings": {
      "items": {
        "$ref": "#/components/schemas/Issue"
      },
      "type": "array"
    }
  },
  "required": [
    "compliance_status",
    "compliance_components",
    "errors",
    "warnings",
    "evidence"
  ],
  "title": "ValidateResponse",
  "type": "object"
}
```

### `WebhookChartResponse`

```json
{
  "properties": {
    "western": {
      "$ref": "#/components/schemas/WebhookWesternSection"
    },
    "eastern": {
      "$ref": "#/components/schemas/WebhookEasternSection"
    },
    "fusion": {
      "$ref": "#/components/schemas/WebhookFusionSection"
    },
    "summary": {
      "$ref": "#/components/schemas/WebhookSummary"
    },
    "meta": {
      "additionalProperties": true,
      "type": "object",
      "title": "Meta"
    }
  },
  "type": "object",
  "required": [
    "western",
    "eastern",
    "fusion",
    "summary",
    "meta"
  ],
  "title": "WebhookChartResponse"
}
```

### `WesternRequest`

```json
{
  "properties": {
    "date": {
      "type": "string",
      "title": "Date",
      "description": "Local ISO8601 datetime"
    },
    "tz": {
      "type": "string",
      "title": "Tz",
      "description": "IANA timezone name",
      "default": "Europe/Berlin"
    },
    "lon": {
      "type": "number",
      "title": "Lon",
      "description": "Longitude in degrees",
      "default": 13.405
    },
    "lat": {
      "type": "number",
      "title": "Lat",
      "description": "Latitude in degrees",
      "default": 52.52
    },
    "ambiguousTime": {
      "type": "string",
      "enum": [
        "earlier",
        "later"
      ],
      "title": "Ambiguoustime",
      "default": "earlier"
    },
    "nonexistentTime": {
      "type": "string",
      "enum": [
        "error",
        "shift_forward"
      ],
      "title": "Nonexistenttime",
      "default": "error"
    },
    "zodiac_mode": {
      "anyOf": [
        {
          "type": "string",
          "pattern": "^(tropical|sidereal_lahiri|sidereal_fagan_bradley|sidereal_raman)$"
        },
        {
          "type": "null"
        }
      ],
      "title": "Zodiac Mode",
      "description": "Zodiac reference frame. Default: tropical.",
      "default": "tropical"
    }
  },
  "type": "object",
  "required": [
    "date"
  ],
  "title": "WesternRequest"
}
```

### `WesternResponse`

```json
{
  "properties": {
    "jd_ut": {
      "type": "number",
      "title": "Jd Ut"
    },
    "house_system": {
      "type": "string",
      "title": "House System"
    },
    "bodies": {
      "additionalProperties": {
        "$ref": "#/components/schemas/WesternBodyResponse"
      },
      "type": "object",
      "title": "Bodies"
    },
    "houses": {
      "anyOf": [
        {
          "additionalProperties": {
            "type": "number"
          },
          "type": "object"
        },
        {
          "type": "null"
        }
      ],
      "title": "Houses"
    },
    "angles": {
      "anyOf": [
        {
          "additionalProperties": {
            "type": "number"
          },
          "type": "object"
        },
        {
          "type": "null"
        }
      ],
      "title": "Angles"
    },
    "aspects": {
      "items": {
        "$ref": "#/components/schemas/AspectResponse"
      },
      "type": "array",
      "title": "Aspects",
      "default": []
    },
    "house_quality": {
      "$ref": "#/components/schemas/HouseQuality"
    },
    "provenance": {
      "$ref": "#/components/schemas/ProvenanceResponse"
    }
  },
  "type": "object",
  "required": [
    "jd_ut",
    "house_system",
    "bodies",
    "house_quality",
    "provenance"
  ],
  "title": "WesternResponse"
}
```

### `WuxingMappingResponse`

```json
{
  "properties": {
    "mapping": {
      "additionalProperties": true,
      "type": "object",
      "title": "Mapping"
    },
    "order": {
      "items": {},
      "type": "array",
      "title": "Order"
    },
    "description": {
      "additionalProperties": {
        "type": "string"
      },
      "type": "object",
      "title": "Description"
    }
  },
  "type": "object",
  "required": [
    "mapping",
    "order",
    "description"
  ],
  "title": "WuxingMappingResponse"
}
```

### `WxRequest`

```json
{
  "properties": {
    "date": {
      "type": "string",
      "title": "Date",
      "description": "ISO 8601 local date time"
    },
    "tz": {
      "type": "string",
      "title": "Tz",
      "description": "Timezone name",
      "default": "Europe/Berlin"
    },
    "lon": {
      "type": "number",
      "title": "Lon",
      "description": "Longitude in degrees"
    },
    "lat": {
      "type": "number",
      "title": "Lat",
      "description": "Latitude in degrees"
    },
    "ambiguousTime": {
      "type": "string",
      "enum": [
        "earlier",
        "later"
      ],
      "title": "Ambiguoustime",
      "default": "earlier"
    },
    "nonexistentTime": {
      "type": "string",
      "enum": [
        "error",
        "shift_forward"
      ],
      "title": "Nonexistenttime",
      "default": "error"
    }
  },
  "type": "object",
  "required": [
    "date",
    "lon",
    "lat"
  ],
  "title": "WxRequest"
}
```

### `WxResponse`

```json
{
  "properties": {
    "input": {
      "additionalProperties": true,
      "type": "object",
      "title": "Input"
    },
    "wu_xing_vector": {
      "additionalProperties": {
        "type": "number"
      },
      "type": "object",
      "title": "Wu Xing Vector"
    },
    "dominant_element": {
      "type": "string",
      "title": "Dominant Element"
    },
    "equation_of_time": {
      "type": "number",
      "title": "Equation Of Time"
    },
    "true_solar_time": {
      "type": "number",
      "title": "True Solar Time"
    },
    "contribution_ledger": {
      "anyOf": [
        {
          "additionalProperties": true,
          "type": "object"
        },
        {
          "type": "null"
        }
      ],
      "title": "Contribution Ledger"
    },
    "provenance": {
      "$ref": "#/components/schemas/ProvenanceResponse"
    }
  },
  "type": "object",
  "required": [
    "input",
    "wu_xing_vector",
    "dominant_element",
    "equation_of_time",
    "true_solar_time",
    "provenance"
  ],
  "title": "WxResponse"
}
```

## 10. Mock Server (Development)

A standalone mock server serves deterministic snapshot responses without ephemeris dependencies:

```bash
# Start mock server
python tests/mock_server.py --port 8081

# Use a different scenario (default, lichun, hilat, zi)
python tests/mock_server.py --port 8081 --scenario hilat

# Simulate 200ms latency
python tests/mock_server.py --port 8081 --latency 200

# Chaos mode: 10% random 500 errors
MOCK_FAIL_RATE=0.1 python tests/mock_server.py --port 8081
```

Runtime scenario switching:

```bash
curl -X POST localhost:8081/mock/scenario/hilat
curl -X POST localhost:8081/mock/latency/500
curl localhost:8081/mock/scenarios   # list all
```

The mock server returns an `X-Mock-Server: true` header on all responses.

## 11. Troubleshooting

| Error | Cause | Fix |
|-------|-------|-----|
| `ephemeris_unavailable` (503) | Swiss Ephemeris files missing on server | Set `SE_EPHE_PATH` or use the mock server |
| `validation_error` (422) | Request body doesn't match schema | Check `detail` field for specifics |
| 401 Unauthorized | Missing or invalid `X-API-Key` | Verify key prefix matches tier (`ff_free_`, `ff_pro_`, etc.) |
| 429 Too Many Requests | Rate limit exceeded | Check `X-RateLimit-Remaining` header; back off per `Retry-After` |
| `LocalTimeError` in response | Ambiguous/nonexistent local time (DST) | Set `ambiguousTime: "earlier"` or `nonexistentTime: "shift_forward"` |
| Different pillars for same date | Timezone or LiChun boundary | Year changes at ~Feb 4 (solar longitude 315°), not Jan 1 |
