# External Services

**Responsibility**: External integrations — Superglue proxy (ElevenLabs context, daily horoscope, chart trigger), geocoding, soulprint generation, daily content generators.

**Technology**: Python / httpx / Pydantic v2

## Source Mapping

| Module | Role |
|--------|------|
| `bazi_engine/services/superglue_client.py` | `call_hook()` — Superglue API client |
| `bazi_engine/services/auth.py` | API key validation |
| `bazi_engine/services/geocoding.py` | Geocoding service |
| `bazi_engine/services/soulprint.py` | Soulprint generation |
| `bazi_engine/services/daily_*.py` | Daily content generators |
| `bazi_engine/routers/superglue.py` | Superglue proxy endpoints (GET/POST profile, daily, chart) |

## Interfaces

- **HTTP** to Superglue API (`api.superglue.ai`): `call_hook()` with `SUPERGLUE_API_KEY`
- **Python class API**: consumed by `api` component routers
- **HTTP** to geocoding providers (external)

## Constraints

- `SUPERGLUE_API_KEY` required for Superglue hooks — `RuntimeError` if missing
- `WEBHOOK_HMAC_ONLY=true` for ElevenLabs webhook validation
- Superglue proxy responses use `SuperglueProxyResponse(extra="allow")` — open-ended schema
- POST `/profile/{user_id}/chart` body is optional (defaults `force_recalculate=false`)

## Requirements Addressed

ElevenLabs integration, Superglue proxy, geocoding, daily content generation.

## Relevant Decisions

| File | Title | Trigger |
|------|-------|---------|
| — | Superglue proxy response model | When adding Superglue endpoints — use `SuperglueProxyResponse` |
| — | Optional chart request body | POST chart endpoint — body defaults to `force_recalculate=false` |
