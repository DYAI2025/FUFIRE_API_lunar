"""
auth.py — API key authentication with tier-based access control.

Keys are loaded from FUFIRE_API_KEYS env var (comma-separated).
Key format: ff_<tier>_<random> (e.g., ff_pro_a1b2c3d4e5).
Keys without the prefix are treated as 'free' tier.

Tiers:
  dev        — local development (auth disabled)
  free       — 100 req/day,  5 req/min
  starter    — 1000 req/day, 20 req/min
  pro        — 10000 req/day, 100 req/min
  enterprise — unlimited
"""
from __future__ import annotations

import hmac
import logging
import os
from dataclasses import dataclass
from functools import lru_cache

from fastapi import HTTPException, Request, Security
from fastapi.security import APIKeyHeader

_log = logging.getLogger(__name__)

_API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)

# ── Tier definitions ──────────────────────────────────────────────────────────

TIER_LIMITS: dict[str, tuple[int, int]] = {
    # tier: (requests_per_day, requests_per_minute)
    # 0 = unlimited
    "dev":        (0, 0),
    "free":       (100, 5),
    "starter":    (1_000, 20),
    "pro":        (10_000, 100),
    "enterprise": (0, 0),
}


@dataclass(frozen=True)
class KeyInfo:
    """Metadata resolved from an API key."""
    key: str
    tier: str
    requests_per_day: int
    requests_per_minute: int

    def __repr__(self) -> str:
        # Show only last 4 chars of key to confirm identity without leaking prefix/tier
        suffix = self.key[-4:] if len(self.key) > 4 else "***"
        return f"KeyInfo(key='...{suffix}', tier='{self.tier}', rpm={self.requests_per_minute})"


@lru_cache(maxsize=1)
def _load_tier_overrides() -> dict[str, str]:
    """Load server-side tier overrides from FUFIRE_KEY_TIER_OVERRIDES env var.

    Format: comma-separated ``key:tier`` pairs.
    Example: ``ff_enterprise_abc:starter,ff_free_xyz:pro``

    Overrides take precedence over prefix-based tier detection.
    Call ``_load_tier_overrides.cache_clear()`` to reload after env change.
    """
    raw = os.environ.get("FUFIRE_KEY_TIER_OVERRIDES", "").strip()
    if not raw:
        return {}
    result: dict[str, str] = {}
    for entry in raw.split(","):
        entry = entry.strip()
        if ":" not in entry:
            continue
        key, _, tier = entry.partition(":")
        key = key.strip()
        tier = tier.strip().lower()
        if key and tier in TIER_LIMITS:
            result[key] = tier
    return result


def resolve_key_info(api_key: str) -> KeyInfo:
    """Extract tier from key format ff_<tier>_<secret>, or default to free.

    Tier resolution order:
      1. Server-side override map (FUFIRE_KEY_TIER_OVERRIDES) — highest priority.
      2. Key prefix (``ff_<tier>_...``).
      3. Configured KeyStore (runtime-issued keys), when present.
      4. ``free`` default for unrecognised/legacy keys.

    The store is consulted *only* when prefix detection did not yield a known
    tier, so behaviour with no store configured is unchanged. The store import
    is local to avoid a circular import at module load.
    """
    if api_key == "dev-mode":
        rpd, rpm = TIER_LIMITS["dev"]
        return KeyInfo(key=api_key, tier="dev", requests_per_day=rpd, requests_per_minute=rpm)

    # 1. Server-side override wins over everything.
    overrides = _load_tier_overrides()
    tier = overrides.get(api_key)

    if tier is None:
        # 2. Prefix-based detection (legacy + minted keys both use ff_<tier>_).
        prefix_tier: str | None = None
        if api_key.startswith("ff_"):
            parts = api_key.split("_", 2)
            if len(parts) >= 3 and parts[1] in TIER_LIMITS:
                prefix_tier = parts[1]

        if prefix_tier is not None:
            tier = prefix_tier
        else:
            # 3. Store lookup for keys the prefix could not classify.
            tier = _store_tier_of(api_key) or "free"  # 4. free default

    rpd, rpm = TIER_LIMITS[tier]
    return KeyInfo(key=api_key, tier=tier, requests_per_day=rpd, requests_per_minute=rpm)


def _store_tier_of(api_key: str) -> str | None:
    """Resolve a tier from the configured KeyStore, if any. None when no store
    is configured, the key is unknown, or the resolved tier is not a known tier.
    """
    from .key_store import get_key_store  # local import: avoids import cycle

    store = get_key_store()
    if store is None:
        return None
    tier = store.tier_of(api_key)
    if tier in TIER_LIMITS:
        return tier
    return None


# ── Key loading ───────────────────────────────────────────────────────────────

@lru_cache(maxsize=1)
def _load_keys() -> frozenset[str]:
    """Load valid API keys from FUFIRE_API_KEYS env var (comma-separated).

    Keys are cached for process lifetime. To revoke a key without a process
    restart, call ``_load_keys.cache_clear()`` — the next request will reload
    from the env var.

    For production key rotation: update the Railway variable FUFIRE_API_KEYS,
    then redeploy (which restarts the process and clears the cache automatically).
    """
    raw = os.environ.get("FUFIRE_API_KEYS", "")
    if not raw.strip():
        return frozenset()
    keys = frozenset(k.strip() for k in raw.split(",") if k.strip())
    if any(k.startswith("ff_enterprise_") for k in keys):
        _log.warning(
            "Enterprise-tier API key(s) detected. Ensure access is intentional "
            "and keys are rotated regularly."
        )
    return keys


def _require_keys_explicit() -> bool:
    return os.environ.get("FUFIRE_REQUIRE_API_KEYS", "").strip().lower() in {
        "1", "true", "yes", "on",
    }


def _is_valid_api_key(api_key: str, valid_keys: frozenset[str]) -> bool:
    """Constant-time membership test against the static env-var key list.

    Iterates the full set every call (never short-circuits) so total work does
    not leak which/whether a key matched. Unchanged from the original behaviour.
    """
    matched = False
    for valid in valid_keys:
        matched = hmac.compare_digest(api_key, valid) or matched
    return matched


def _store_is_configured() -> bool:
    """True iff a KeyStore backend is configured (``KEY_STORE_BACKEND`` != none).

    Used to decide whether the dev-mode bypass applies: with a store present,
    an empty ``FUFIRE_API_KEYS`` must NOT silently disable auth.
    """
    from .key_store import get_key_store  # local import: avoids import cycle

    return get_key_store() is not None


def _store_is_valid(api_key: str) -> bool:
    """True iff a KeyStore is configured AND it recognises ``api_key`` as active.

    Returns False (never raises) when no store is configured, so the env-list
    path is fully independent of this. Import is local to avoid an import cycle.
    """
    from .key_store import get_key_store  # local import: avoids import cycle

    store = get_key_store()
    if store is None:
        return False
    try:
        return store.is_valid(api_key)
    except Exception:  # pragma: no cover - store backend failure must not 500 auth
        _log.exception("auth.key_store_error during validation")
        return False


# ── FastAPI dependency ────────────────────────────────────────────────────────

def require_api_key(
    request: Request,
    api_key: str | None = Security(_API_KEY_HEADER),
) -> KeyInfo:
    """FastAPI dependency. Returns KeyInfo with tier metadata, raises 401 otherwise.

    A key is accepted if it is in the static ``FUFIRE_API_KEYS`` list (the
    original path, HMAC constant-time compare) **or**, when a KeyStore backend
    is configured, the store recognises it as an active key.

    Dev-mode bypass (auth disabled) is preserved exactly: it triggers only when
    the env-var key list is empty **and** no store is configured. With a store
    configured, an empty env list no longer silently disables auth — a real
    issued key is required. ``FUFIRE_REQUIRE_API_KEYS`` is honored unchanged.
    The resolved KeyInfo is stored on request.state.key_info for downstream
    middleware (rate limiting, quota headers).
    """
    valid_keys = _load_keys()
    store_configured = _store_is_configured()

    if not valid_keys and not store_configured:
        if _require_keys_explicit():
            raise HTTPException(
                status_code=503,
                detail={
                    "error": "auth_configuration_error",
                    "message": "API key auth is required but FUFIRE_API_KEYS is empty",
                    "detail": {},
                },
            )
        _log.warning("auth.dev_mode path=%s — no api keys configured", request.url.path)
        info = resolve_key_info("dev-mode")
        request.state.key_info = info
        return info

    key_ok = api_key is not None and (
        _is_valid_api_key(api_key, valid_keys) or _store_is_valid(api_key)
    )
    if not key_ok or api_key is None:
        masked = (api_key[:4] + "...") if api_key and len(api_key) > 4 else "missing"
        _log.warning("auth.unauthorized key=%s path=%s", masked, request.url.path)
        raise HTTPException(
            status_code=401,
            detail={
                "error": "unauthorized",
                "message": "Missing or invalid X-API-Key header",
                "detail": {},
            },
            headers={"WWW-Authenticate": "ApiKey"},
        )

    info = resolve_key_info(api_key)
    request.state.key_info = info
    return info
