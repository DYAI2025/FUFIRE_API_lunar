# API Layer

**Responsibility**: FastAPI application — routers, middleware, rate limiting, auth, OpenAPI contract, CLI interface.

**Technology**: Python / FastAPI / slowapi / Pydantic v2

## Source Mapping

API code lives in `bazi_engine/` (Level 5 of the module hierarchy):

| Module | Role |
|--------|------|
| `app.py` | Factory — mounts all routers, no business logic |
| `cli.py` | Command-line interface |
| `middleware.py` | `RequestIdMiddleware`, X-Request-ID, hardening headers |
| `limiter.py` | slowapi rate limiter (Redis or in-memory fallback) |
| `routers/bazi.py` | `/calculate/bazi`, `/calculate/tst` |
| `routers/western.py` | `/calculate/western`, `/calculate/wuxing` |
| `routers/fusion.py` | `/calculate/fusion` |
| `routers/transit.py` | `/transit/now`, `/transit/timeline`, `/transit/state`, `/transit/narrative` |
| `routers/experience.py` | `/experience/bootstrap`, `/experience/signature-delta`, `/experience/daily` |
| `routers/validate.py` | `/validate` |
| `routers/chart.py` | `/api/chart` |
| `routers/webhooks.py` | `/api/webhooks/chart` (ElevenLabs, HMAC-verified) |
| `routers/info.py` | `/health`, `/api` |
| `routers/shared.py` | Shared Pydantic models/deps |

## Interfaces

- **REST API** (HTTP): serves all endpoints to frontend (Bazodiac) and external consumers
- **Python class API**: consumes `engine` component for calculations
- **Python class API**: consumes `services` component for external integrations
- **Python class API**: consumes `bafe` component for `/validate`

## Constraints

- Business logic belongs in engine/services, NOT in routers or `app.py`
- Endpoints are frozen — do not change paths or response structures
- OpenAPI spec (`spec/openapi/openapi.json`) must be regenerated after any endpoint change
- All endpoints must handle `LocalTimeError` for DST edge cases
- V1 routes enforce API key auth when `FUFIRE_REQUIRE_API_KEYS=true`

## Requirements Addressed

HTTP API surface, rate limiting, authentication, CORS, OpenAPI contract compliance, webhook integration.

## Relevant Decisions

| File | Title | Trigger |
|------|-------|---------|
| — | OpenAPI contract-first | After any endpoint/model change — run `export_openapi.py` |
| — | Router-only architecture | When adding endpoints — `app.py` is a thin factory |
| — | Rate limiting degradation | When `REDIS_URL` absent — in-memory fallback |
