"""
limiter.py — Shared slowapi Limiter instance with key-based rate limiting.

V1 routes: keyed by API key (from request.state.key_info).
Legacy routes: keyed by remote IP address (backward compat).

Storage:
  - If REDIS_URL is set: uses Redis for persistent, cross-worker counters.
  - Otherwise: in-memory storage (single-worker only, lost on restart).
  - A configured/required Redis never silently falls back to process memory.

Infrastructure probes (/health, /ready) use a SEPARATE, memory-only limiter —
see ``infra_limiter`` below.
"""
from __future__ import annotations

import hashlib
import hmac
import ipaddress
import logging
import os
import secrets
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


# ── Infrastructure probe limiter (FUF-156A) ──────────────────────────────────
#
# /health and /ready must stay answerable while Redis is down: that outage is
# precisely what a readiness probe exists to report, and it must surface as the
# structured 503 dependency payload, not as an opaque limiter 500. The shared
# application limiter cannot provide that — with a required Redis unreachable,
# its ``.hit()`` raises, and because ``in_memory_fallback_enabled=False`` and
# slowapi's ``_swallow_errors`` defaults to False, ``_check_request_limit``
# re-raises straight into the request. So infrastructure probes get their own
# limiter, pinned to process memory, that never reads REDIS_URL at all.
#
# Ceiling rationale: Northflank supports at most three health-check types and
# documents a 10-second minimum probe period, i.e. at most 18 platform checks
# per minute per container. 120/minute leaves ample operational headroom while
# still bounding abusive polling of a route that runs a live ephemeris call.
INFRA_PROBE_LIMIT = "120/minute"

# Process-local pepper, generated once per process. Deliberately NOT an env var:
# the counters it pseudonymises are themselves process-local (MemoryStorage) and
# reset on restart, so a pseudonym that rotates with the process loses nothing.
# A Redis-stable, operator-supplied pepper belongs with the shared limiter, not
# here.
_INFRA_PEPPER: bytes = secrets.token_bytes(32)


def infra_probe_key(request: Request) -> str:
    """Return a pseudonymous, process-stable rate-limit key for an infra probe.

    The raw client address never leaves this function. slowapi writes the key
    func's return value into BOTH the limiter storage key
    (``__evaluate_limits``: ``args = [limit_key, limit_scope]``) and the
    ``"ratelimit %s (%s) exceeded at endpoint: %s"`` WARNING log line, so
    returning ``get_remote_address(request)`` directly would persist and log a
    raw IP on every probe.

    The parameter name ``request`` is load-bearing: slowapi inspects
    ``inspect.signature(key_func).parameters`` and only passes the request when
    it finds that exact name — otherwise it calls ``key_func()`` with no
    arguments and raises TypeError.
    """
    remote = get_remote_address(request)
    digest = hmac.new(_INFRA_PEPPER, remote.encode("utf-8"), hashlib.sha256)
    return "ip:" + digest.hexdigest()[:32]


infra_limiter = Limiter(
    key_func=infra_probe_key,
    # Memory-only by construction: an explicit storage_uri wins over any
    # environment-derived default, so this limiter can never resolve to Redis.
    storage_uri="memory://",
    # No fallback is meaningful for a limiter whose storage is already the
    # fallback; keeping it False also keeps the semantics identical to the
    # application limiter.
    in_memory_fallback_enabled=False,
    # Separate namespace, so infra counters can never collide with or be reset
    # alongside application-tier counters.
    key_prefix="fufire_infra_rl:",
)


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

    Covers BOTH the application limiter and the infrastructure probe limiter —
    they hold separate storages, so resetting one leaves the other's counters to
    leak across tests.

    Accesses ``_storage`` (a limits.storage.MemoryStorage). The private
    attribute is isolated here so test code stays clean.
    """
    for lim in (limiter, infra_limiter):
        storage = lim._storage  # noqa: SLF001
        reset_method = getattr(storage, "reset", None)
        if callable(reset_method):
            try:
                reset_method()
            except Exception:
                # Best-effort reset: ignore errors to keep tests resilient
                pass
