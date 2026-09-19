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
import re
import secrets
from typing import Optional

from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.requests import Request

from .runtime_contract import PSEUDONYM_LENGTH, pseudonymise

_log = logging.getLogger(__name__)

# ── Shared-limiter rate identities (FUF-159) ─────────────────────────────────
#
# slowapi writes the key function's return value into BOTH the limiter storage
# key (``__evaluate_limits``: ``args = [limit_key, limit_scope]``) and the
# ``"ratelimit %s (%s) exceeded at endpoint: %s"`` WARNING log line. Returning
# the raw API key or the raw client address — as this module did before FUF-159
# — therefore persisted and logged them on every limited request.
#
# The replacement is a STRUCTURED pseudonym rather than a bare digest, because
# ``tier_limit`` receives exactly this string and nothing else: collapsing an
# authenticated identity to an opaque hash would destroy tier resolution and
# silently drop every paid caller to the free-tier ceiling. The tier travels in
# the clear (it is not a secret and not caller-supplied); only the credential is
# pseudonymised.
#
#     authenticated : k:<tier>:<32 hex>
#     address-keyed : ip:<32 hex>
IDENTITY_KEY_PREFIX = "k:"
IDENTITY_IP_PREFIX = "ip:"

# Legacy fallback for unauthenticated, address-keyed routes. Unchanged by
# FUF-159 — this slice moves identities, never numeric policy.
LEGACY_IP_LIMIT = "30/minute"

# Applied when a structured identity does not parse. Deliberately NOT the free
# tier: a malformed authenticated identity is a defect, and silently serving it
# the free-tier ceiling would make that defect indistinguishable from a genuine
# free-tier caller. Strictly below every real tier, and always logged.
MALFORMED_IDENTITY_LIMIT = "1/minute"

_DIGEST_RE = re.compile(r"^[0-9a-f]{%d}$" % PSEUDONYM_LENGTH)


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
    """Return the pseudonymous rate identity for a shared-limiter request.

    Neither the raw API key nor the raw client address ever leaves this
    function — see the structured-identity note at the top of this module for
    why the tier still travels in the clear.

    The parameter name ``request`` is load-bearing: slowapi inspects
    ``inspect.signature(key_func).parameters`` and only passes the request when
    it finds that exact name — otherwise it calls ``key_func()`` with no
    arguments and raises TypeError.
    """
    key_info = getattr(getattr(request, "state", None), "key_info", None)
    if key_info is not None:
        return f"{IDENTITY_KEY_PREFIX}{key_info.tier}:{pseudonymise(key_info.key)}"
    return f"{IDENTITY_IP_PREFIX}{pseudonymise(get_remote_address(request))}"


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


# ── Authenticated ElevenLabs webhook (FUF-156B) ──────────────────────────────
#
# The FuFirE webhook contract exposes ONE logical ElevenLabs integration, so the
# authenticated rate identity is a single constant bucket rather than a
# per-caller one. This is an explicit product decision: keying by IP would
# either shard one integration's quota across a rotating egress pool or, behind
# a shared proxy, fuse unrelated callers into one bucket.
#
# Ceiling rationale: 60/minute is the PO policy for the current product stage —
# one voice agent issuing at most one chart per second. It is deliberately NOT
# derived from the 30/minute anonymous legacy fallback in ``tier_limit``.
#
# This limit rides the SHARED application limiter, not ``infra_limiter``: the
# webhook is production traffic whose counters must stay consistent across
# replicas whenever Redis is configured. Unlike /health and /ready, a webhook
# that fails while Redis is down is correct behaviour, not a lost signal.
WEBHOOK_INTEGRATION_LIMIT = "60/minute"

# The literal, non-secret identity of that single integration. It is a constant
# on purpose: nothing request-derived may reach the limiter key, because slowapi
# writes the key func's return value into BOTH the limiter storage key
# (``__evaluate_limits``: ``args = [limit_key, limit_scope]``) and the
# ``"ratelimit %s (%s) exceeded at endpoint: %s"`` WARNING log line. A key built
# from the HMAC signature, the shared secret, the API-key fallback, the client
# address or the request body would therefore be persisted and logged.
WEBHOOK_INTEGRATION_IDENTITY = "integration:elevenlabs"


def webhook_integration_key(request: Request) -> str:
    """Return the constant rate identity of the one logical ElevenLabs integration.

    The request is deliberately unread. The parameter name ``request`` is
    load-bearing all the same: slowapi inspects
    ``inspect.signature(key_func).parameters`` and only passes the request when
    it finds that exact name — otherwise it calls ``key_func()`` with no
    arguments and raises TypeError.

    Quota is only ever consumed by an already-authenticated request: the route's
    auth dependency resolves before the limiter wrapper runs, so unauthenticated
    traffic cannot drain this bucket (see tests/test_webhook_rate_limit.py).
    """
    return WEBHOOK_INTEGRATION_IDENTITY


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


# Enterprise/dev tiers carry ``requests_per_minute=0`` (meaning unlimited);
# they are capped so slowapi storage never sees an unbounded window.
UNLIMITED_TIER_CAP = "10000/minute"


def _rpm_to_limit(requests_per_minute: int) -> str:
    if requests_per_minute == 0:
        return UNLIMITED_TIER_CAP
    return f"{requests_per_minute}/minute"


def _malformed_identity(reason: str) -> str:
    """Fail closed on an unparseable identity — but never silently.

    The identity itself is deliberately NOT logged: on a rollback boundary a
    malformed value is exactly where raw credential material could appear.
    """
    _log.warning("limiter.malformed_identity reason=%s applying=%s", reason, MALFORMED_IDENTITY_LIMIT)
    return MALFORMED_IDENTITY_LIMIT


def _structured_key_limit(identity: str) -> str:
    """Resolve ``k:<tier>:<digest>`` without ever consulting resolve_key_info.

    The digest is a pseudonym, not a key: feeding it to the key resolver would
    classify every authenticated caller as free tier.
    """
    from .auth import TIER_LIMITS

    parts = identity.split(":")
    if len(parts) != 3:
        return _malformed_identity("field_count")
    _, tier, digest = parts
    if tier not in TIER_LIMITS:
        return _malformed_identity("unknown_tier")
    if not _DIGEST_RE.match(digest):
        return _malformed_identity("bad_digest")
    return _rpm_to_limit(TIER_LIMITS[tier][1])


def _legacy_raw_limit(key: str) -> str:
    """Parse the pre-FUF-159 raw identity forms, so a revert stays narrow."""
    try:
        ipaddress.ip_address(key)
        return LEGACY_IP_LIMIT
    except ValueError:
        pass
    from .auth import resolve_key_info

    return _rpm_to_limit(resolve_key_info(key).requests_per_minute)


def tier_limit(key: str) -> str:
    """Return the rate limit string for the given rate-limit key.

    slowapi calls this with the result of ``key_func(request)``. The parameter
    name ``key`` is load-bearing: slowapi's ``LimitGroup.__iter__`` inspects
    ``inspect.signature(callable).parameters`` and, if it finds a parameter
    named ``"key"``, calls ``callable(key_func(request))`` instead of
    ``callable()`` (the zero-argument form the old ContextVar approach relied
    on incorrectly).

    Two identity generations are accepted:

    * **Structured (current)** — ``k:<tier>:<digest>`` and ``ip:<digest>``, as
      produced by ``get_rate_limit_key``. The tier is read directly from the
      identity; the digest is never resolved as a key.
    * **Raw (pre-FUF-159)** — a bare ``ff_<tier>_<secret>`` key, ``dev-mode``,
      or a bare IP address. Kept so reverting the key function alone restores
      the previous behaviour without a second coordinated change.

    Numeric policy is unchanged by FUF-159: free/starter/pro/enterprise and the
    legacy address fallback all keep the ceilings they had before.
    """
    if key.startswith(IDENTITY_KEY_PREFIX):
        return _structured_key_limit(key)
    if key.startswith(IDENTITY_IP_PREFIX):
        digest = key[len(IDENTITY_IP_PREFIX):]
        return LEGACY_IP_LIMIT if _DIGEST_RE.match(digest) else _malformed_identity("bad_digest")
    return _legacy_raw_limit(key)


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
