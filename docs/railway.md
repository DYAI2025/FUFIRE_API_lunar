# Railway Deployment (API Service)

This repository ships with a Dockerfile that is ready for Railway.

The Docker build has no GHCR base image or other external container registry dependency: Swiss Ephemeris files are fetched from GitHub and checksum-verified during the Docker build, so you still need network access at build time but not a separate base image at deploy time.

## Quick start

1. Create a new **Railway Project** and add a **Service** from this GitHub repo.
2. Railway detects the `Dockerfile` and builds the container.
3. Set any optional environment variables (see below) and deploy.

The service listens on `PORT` (default `8080`) and exposes:
- `GET /health` for health checks.

## Required environment variables (production)

Set these in the Railway **service variables** (`railway.toml` has no env
mechanism — variables live on the service):

| Variable | Purpose |
| --- | --- |
| `FUFIRE_ENV` | Set to `production` (or `staging` on a staging service). Activates the FUFIRE-006 fail-closed startup guard: the app **refuses to boot** if `FUFIRE_API_KEYS` is empty and no KeyStore backend is configured, instead of silently falling back to the unauthenticated dev-mode bypass. |
| `FUFIRE_API_KEYS` | Comma-separated API keys (`ff_<tier>_<secret>`). |
| `FUFIRE_REQUIRE_API_KEYS` | Independent second belt (unchanged): when truthy, requests on the dev-mode path get `503` instead of the bypass. Recommended `true` in production. |

## Optional environment variables

| Variable | Purpose |
| --- | --- |
| `ELEVENLABS_TOOL_SECRET` | Required only for the `/internal/api/webhooks/chart` endpoint. |
| `SE_EPHE_PATH` | Override ephemeris path if you mount custom ephemeris files. |
| `EPHEMERIS_MODE` | `SWIEPH` (file-based) or `MOSEPH` (offline fallback). Defaults to auto. |

## Notes

- The service defaults to an offline Moshier ephemeris fallback when no Swiss Ephemeris files are present.
- Health checks can use `/health`.
