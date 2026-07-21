# B2B API Standards (FuFirE)

This document describes the B2B-facing API hardening baseline implemented in the service.

## Versioning

- Legacy routes remain unchanged (for compatibility).
- New integrations should use `/v1/*` routes.

## Authentication

- Protected `/v1/*` business routes require `X-API-Key`.
- Configure keys with `FUFIRE_API_KEYS=key1,key2,...`.
- Strict mode: set `FUFIRE_REQUIRE_API_KEYS=1` to fail closed if keys are missing.

## Traceability

All responses include:

- `X-Request-ID` (client-provided value is echoed if present)
- `X-API-Version`
- `X-Response-Time-ms`

## Error Envelope

All API errors are normalized to a JSON envelope with:

- `error`
- `message`
- `detail`
- `status`
- `path`
- `timestamp`
- `request_id`

## Security Headers

All responses include:

- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `Referrer-Policy: no-referrer`
- `Permissions-Policy: accelerometer=(),camera=(),geolocation=(),microphone=()`

## Readiness and Health

- `GET /health` and `GET /v1/health`: dependency-aware health status.
- `GET /ready` and `GET /v1/ready`: readiness checks for orchestrators; returns `503` when dependencies are degraded.
