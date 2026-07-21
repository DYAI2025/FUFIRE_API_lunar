"""
limiter.py — Shared slowapi Limiter instance with key-based rate limiting.

V1 routes: keyed by API key (from request.state.key_info).
Legacy routes: keyed by remote IP address (backward compat).

Storage:
  - If REDIS_URL is set: uses Redis for persistent, cross-worker counters.
  - Otherwise: in-memory storage (single-worker only, lost on restart).
  - A configured/required Redis never silently falls back to process memory.
"""
from __future__ import annotations

import ipaddress
import logging
import os
from typing import Optional

from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.requests import Request

_log = logging.getLogger(__name__)


def _truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


def _replica_count() -> int | None:
    raw = os.environ.get("FUFIRE_REPLICA_COUNT", "").strip()
    if not raw:
        return None
    try:
        value = int(raw)
    except ValueError:
        return None
    return value if value > 0 else None


def get_rate_limit_key(request: Request) -> str:
    """Extract rate limit key: API key for /v1/, IP for legacy routes."""
    key_info = getattr(getattr(request, "state", None), "key_info", None)
    if key_info is not None:
        return key_info.key
    return get_remote_address(request)


def _resolve_storage_uri() -> Optional[str]:
    """Resolve Redis URI from environment.

    Checks (in order): REDIS_URL, REDIS_PRIVATE_URL, UPSTASH_REDIS_REST_URL.
    Returns None for in-memory fallback.
    """
    for env_var in ("REDIS_URL", "REDIS_PRIVATE_URL"):
        url = os.environ.get(env_var)
        if url:
            _log.info("Rate limiter using Redis storage from %s", env_var)
            return url
    return None


_storage_uri = _resolve_storage_uri()
_redis_is_required = (
    _storage_uri is not None
    or _truthy(os.environ.get("FUFIRE_REQUIRE_REDIS"))
    or (_replica_count() or 0) > 1
)

limiter = Limiter(
    key_func=get_rate_limit_key,
    storage_uri=_storage_uri,
    # A configured or required Redis is part of correctness, because
    # per-process fallback counters are not globally consistent.
    in_memory_fallback_enabled=False,
    key_prefix="fufire_rl:",
)

if _storage_uri is None:
    _log.info("Rate limiter using in-memory storage (no REDIS_URL configured)")


def get_storage_status() -> dict:
    """Return storage health info for /health endpoint.

    Returns:
        A secret-safe status mapping. Connection URIs are never returned.
    """
    if _storage_uri is None:
        status = "unavailable" if _redis_is_required else "ok"
        return {
            "type": "memory",
            "status": status,
            "required": _redis_is_required,
            "configured": False,
        }

    try:
        # Attempt a lightweight check on the underlying limits storage
        storage = getattr(limiter, "_storage", None)
        if storage is not None:
            # limits.storage.RedisStorage has a .check() method
            check = getattr(storage, "check", None)
            if callable(check) and check():
                return {"type": "redis", "status": "ok", "required": True, "configured": True}
        return {"type": "redis", "status": "degraded", "required": True, "configured": True}
    except Exception:
        return {"type": "redis", "status": "unavailable", "required": True, "configured": True}


def tier_limit(key: str) -> str:
    """Return the rate limit string for the given rate-limit key.

    slowapi calls this with the result of key_func(request) — i.e. the API
    key string (for V1 routes) or the client IP address (for legacy routes).
    The parameter name ``key`` is load-bearing: slowapi's LimitGroup.__iter__
    inspects ``inspect.signature(callable).parameters`` and, if it finds a
    parameter named ``"key"``, calls ``callable(key_func(request))`` instead
    of ``callable()`` (which is the zero-argument form that the previous
    ContextVar approach relied on incorrectly).

    API keys follow the ``ff_<tier>_<secret>`` format, so resolve_key_info
    can extract the tier from the key string directly.  IP addresses don't
    match the prefix pattern and are treated as the 'free' tier.

    Enterprise keys use ``requests_per_minute=0`` (meaning unlimited);
    they are capped at 10 000/minute so slowapi storage never sees an
    unbounded window.
    """
    # Legacy (unauthenticated) routes are keyed by IP address — apply 30/minute fallback
    try:
        ipaddress.ip_address(key)
        return "30/minute"
    except ValueError:
        pass
    from .auth import resolve_key_info
    info = resolve_key_info(key)
    rpm = info.requests_per_minute
    if rpm == 0:
        return "10000/minute"  # dev/enterprise: effectively unlimited
    return f"{rpm}/minute"


def reset_limiter_storage() -> None:
    """Reset in-memory rate limit counters. Call in test teardown only.

    Accesses limiter._storage (a limits.storage.MemoryStorage). The private
    attribute is isolated here so test code stays clean.
    """
    storage = limiter._storage  # noqa: SLF001
    reset_method = getattr(storage, "reset", None)
    if callable(reset_method):
        try:
            reset_method()
        except Exception:
            # Best-effort reset: ignore errors to keep tests resilient
            pass
