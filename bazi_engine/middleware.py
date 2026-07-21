"""
middleware.py — FastAPI middleware for request tracing.

Injects a unique X-Request-ID into every request/response.
If the client provides a *valid UUID* X-Request-ID, it is echoed back
(client-side tracing); anything else is replaced with a fresh UUID
(FUFIRE-009 — the OpenAPI contract declares format:uuid).
"""
from __future__ import annotations

import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


def _safe_request_id(raw: str | None) -> str:
    """Return the client id iff it is a canonical UUID, else mint one.

    The OpenAPI contract declares X-Request-ID as format:uuid; anything else
    would put attacker-controlled bytes into response headers, error bodies
    and logs (FUFIRE-009).
    """
    if raw:
        try:
            return str(uuid.UUID(raw))
        except ValueError:
            pass
    return str(uuid.uuid4())


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Inject traceability + hardening headers into every response."""

    def __init__(self, app, *, api_version: str = "unknown") -> None:
        super().__init__(app)
        self.api_version = api_version

    async def dispatch(self, request: Request, call_next) -> Response:
        start = time.perf_counter()
        request_id = _safe_request_id(request.headers.get("X-Request-ID"))
        request.state.request_id = request_id
        response = await call_next(request)

        elapsed_ms = (time.perf_counter() - start) * 1000
        response.headers["X-Request-ID"] = request_id
        response.headers["X-API-Version"] = self.api_version
        response.headers["X-Response-Time-ms"] = f"{elapsed_ms:.2f}"
        # Quota headers for tier-based rate limiting (only on /v1/ routes).
        key_info = getattr(request.state, "key_info", None)
        if key_info is not None and key_info.requests_per_minute > 0:
            response.headers["X-RateLimit-Limit"] = str(key_info.requests_per_minute)
            # X-RateLimit-Remaining is written by slowapi on @limiter.limit() routes.
            # We do NOT set a fallback here — an absent header is more honest than a
            # phantom "full quota" value. Redis-backed per-key counters are tracked in
            # the roadmap for routes without a per-request decorator.
        elif key_info is not None and key_info.requests_per_minute == 0:
            response.headers["X-RateLimit-Limit"] = "unlimited"
        # Basic security hardening for API responses.
        response.headers.setdefault("Content-Security-Policy", "default-src 'none'")
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("Permissions-Policy", "accelerometer=(),camera=(),geolocation=(),microphone=()")
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        return response
