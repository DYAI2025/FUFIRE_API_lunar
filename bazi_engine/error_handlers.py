"""
error_handlers.py — global exception handlers extracted from app.py (Phase 3, Task 3.22).

Pure move: the error-envelope helpers and all eight exception handlers.
Single public entry point: ``register_exception_handlers(app)``.
"""
from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, Request
from fastapi import HTTPException as FastAPIHTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from starlette.exceptions import HTTPException as StarletteHTTPException

from .exc import BaziEngineError, EphemerisUnavailableError
from .services.superglue_client import SuperglueConfigurationError


def _get_request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "unknown")


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _error_body(
    request: Request,
    *,
    status: int,
    error: str,
    message: str,
    detail: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "error": error,
        "message": message,
        "detail": detail or {},
        "status": status,
        "path": str(request.url.path),
        "timestamp": _utc_now_iso(),
        "request_id": _get_request_id(request),
    }


def register_exception_handlers(app: FastAPI) -> None:
    """Register all global exception handlers on ``app``."""

    @app.exception_handler(RateLimitExceeded)
    async def rate_limit_error_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
        # Keep response JSON-shaped and traceable, including request_id.
        body = _error_body(
            request,
            status=429,
            error="rate_limit_exceeded",
            message="Rate limit exceeded",
            detail={"limit": str(exc.detail)},
        )
        return JSONResponse(
            status_code=429,
            content=body,
            headers={"Retry-After": "60"},
        )

    @app.exception_handler(BaziEngineError)
    async def bazi_engine_error_handler(request: Request, exc: BaziEngineError) -> JSONResponse:
        data = exc.to_dict()
        body = _error_body(
            request,
            status=exc.http_status,
            error=data.get("error", "internal_error"),
            message=data.get("message", "Internal error"),
            detail=data.get("detail") if isinstance(data.get("detail"), dict) else {},
        )
        return JSONResponse(status_code=exc.http_status, content=body)

    @app.exception_handler(EphemerisUnavailableError)
    async def ephemeris_error_handler(request: Request, exc: EphemerisUnavailableError) -> JSONResponse:
        data = exc.to_dict()
        body = _error_body(
            request,
            status=503,
            error=data.get("error", "ephemeris_unavailable"),
            message=data.get("message", "Ephemeris unavailable"),
            detail=data.get("detail") if isinstance(data.get("detail"), dict) else {},
        )
        return JSONResponse(status_code=503, content=body)

    @app.exception_handler(SuperglueConfigurationError)
    async def superglue_config_error_handler(
        request: Request, exc: SuperglueConfigurationError
    ) -> JSONResponse:
        body = _error_body(
            request,
            status=503,
            error="service_unavailable",
            message="Superglue service is not configured",
        )
        return JSONResponse(status_code=503, content=body)

    @app.exception_handler(RequestValidationError)
    async def request_validation_error_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        """Override default handler to (a) strip the raw request echo Pydantic
        attaches to every error (``input``/``url``/``ctx``) so untrusted birth
        data / secrets are never reflected back into the response or any upstream
        proxy log, and (b) sanitize values that stdlib json cannot serialize
        (NaN/Inf floats, Exception objects in a Pydantic error ctx)."""
        import json as _json

        # Keys Pydantic v2 adds to every error dict that can carry the raw,
        # attacker-/PII-controlled request value — never surface them.
        _PII_ECHO_KEYS = frozenset({"input", "url", "ctx"})

        def _redact_errors(errors):
            return [
                {k: v for k, v in err.items() if k not in _PII_ECHO_KEYS}
                for err in errors
            ]

        def _sanitize(obj, *, _depth: int = 0, _max_depth: int = 20):
            if _depth >= _max_depth:
                return "<nested>"
            if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
                return None
            if isinstance(obj, dict):
                return {k: _sanitize(v, _depth=_depth + 1) for k, v in obj.items()}
            if isinstance(obj, (list, tuple)):
                return [_sanitize(v, _depth=_depth + 1) for v in obj]
            # Catch non-serializable objects (e.g. ValueError in Pydantic ctx)
            try:
                _json.dumps(obj)
            except (TypeError, ValueError):
                return str(obj)
            return obj

        return JSONResponse(
            status_code=422,
            content=_sanitize(
                _error_body(
                    request,
                    status=422,
                    error="validation_error",
                    message="Request validation failed",
                    detail={"errors": _redact_errors(exc.errors())},
                )
            ),
        )

    @app.exception_handler(FileNotFoundError)
    async def file_not_found_handler(request: Request, exc: FileNotFoundError) -> JSONResponse:
        return JSONResponse(
            status_code=503,
            content=_error_body(
                request,
                status=503,
                error="ephemeris_unavailable",
                message=str(exc),
            ),
        )

    @app.exception_handler(FastAPIHTTPException)
    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(
        request: Request, exc: FastAPIHTTPException | StarletteHTTPException
    ) -> JSONResponse:
        detail = exc.detail
        if isinstance(detail, dict):
            body = dict(detail)
            body.setdefault("error", "http_error")
            body.setdefault("message", str(body.get("error", "HTTP error")))
            body.setdefault("detail", {})
            body.setdefault("status", exc.status_code)
            body.setdefault("path", str(request.url.path))
            body.setdefault("timestamp", _utc_now_iso())
            body.setdefault("request_id", _get_request_id(request))
        else:
            body = _error_body(
                request,
                status=exc.status_code,
                error="http_error",
                message=str(detail),
            )
        return JSONResponse(
            status_code=exc.status_code,
            content=body,
            headers=getattr(exc, "headers", None),
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, _exc: Exception) -> JSONResponse:
        # Never leak internals on unhandled failures.
        body = _error_body(
            request,
            status=500,
            error="internal_error",
            message="Internal server error",
        )
        return JSONResponse(status_code=500, content=body)
