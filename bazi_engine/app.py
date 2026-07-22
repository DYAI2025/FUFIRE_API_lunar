"""
app.py — FastAPI application factory.

Creates the FastAPI instance, registers global exception handlers,
and mounts all routers. No business logic lives here.
"""
from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import __version__
from .config_guard import assert_runtime_config
from .error_handlers import register_exception_handlers
from .limiter import limiter
from .middleware import RequestIdMiddleware
from .openapi_ext import _DESCRIPTION, install_custom_openapi
from .routers.registry import mount_all


@asynccontextmanager
async def lifespan(app: FastAPI):
    import logging
    logging.getLogger("uvicorn").info(f"FuFirE starting: {__version__}")
    yield


# FUFIRE-006: fail-closed startup guard — a production-profile deployment
# (FUFIRE_ENV=production|prod|staging) must never boot with auth disabled.
# Runs at module load, before the app exists and before any router mounts.
assert_runtime_config()

app = FastAPI(
    title="FuFirE — Fusion Firmament Engine",
    description=_DESCRIPTION,
    version=__version__,
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_middleware(RequestIdMiddleware, api_version=__version__)

_ALLOWED_ORIGINS_ENV = os.environ.get(
    "CORS_ALLOWED_ORIGINS",
    "https://bazodiac.space,https://www.bazodiac.space,http://localhost:5173,http://localhost:3000",
)
_ALLOWED_ORIGINS = [o.strip() for o in _ALLOWED_ORIGINS_ENV.split(",") if o.strip()]


def _validate_cors_origins(origins: list[str], raw: str) -> None:
    """Raise RuntimeError if origins contains a wildcard.

    Called at module load time to fail fast on misconfiguration.
    Exposed as a function so tests can call it directly without reloading the module.
    """
    if "*" in origins:
        raise RuntimeError(
            "CORS_ALLOWED_ORIGINS must not contain '*' — set explicit origins instead. "
            "Current value: " + raw
        )


_validate_cors_origins(_ALLOWED_ORIGINS, _ALLOWED_ORIGINS_ENV)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["X-API-Key", "X-Request-ID", "Content-Type", "Authorization"],
    expose_headers=["X-Request-ID", "X-API-Version", "X-Response-Time-ms",
                    "X-RateLimit-Limit", "X-RateLimit-Remaining"],
)


# ── Global exception handlers (see bazi_engine/error_handlers.py) ────────────

register_exception_handlers(app)


# ── Routers ──────────────────────────────────────────────────────────────────
# The dual-mount idiom (legacy + /v1) and every per-router special case live in
# one declarative table: bazi_engine/routers/registry.py. Adding an endpoint is
# a router module + one Mount line there — see docs/adding-an-endpoint.md.

mount_all(app)


# ── OpenAPI customization (see bazi_engine/openapi_ext.py) ───────────────────
# Installed AFTER mount_all — the custom generator reads app.routes.

install_custom_openapi(app)


if __name__ == "__main__":
    import uvicorn
    # Local convenience entrypoint (`python -m bazi_engine.app`). Docker and
    # Railway do NOT run this block — they invoke uvicorn on
    # `bazi_engine.app:app` directly. B104 suppressed: bind-all is intentional
    # for containerized use, where the platform proxy fronts external traffic.
    uvicorn.run(app, host="0.0.0.0", port=8080)  # nosec B104
