"""Startup configuration validation — fail-closed production profile.

FUFIRE-006: dev-mode auth bypass (empty FUFIRE_API_KEYS + no KeyStore) is a
feature for local development, but in production a missing/renamed secret
must abort startup instead of silently exposing every protected route.

Deployment wiring: set ``FUFIRE_ENV=production`` in the Railway service
variables. ``FUFIRE_REQUIRE_API_KEYS`` remains supported unchanged as an
independent per-request belt (503 on the dev-mode path in auth.py).
"""
from __future__ import annotations

import os

_PRODUCTION_ENVS = {"production", "prod", "staging"}


def _truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


def assert_production_auth_config() -> None:
    """Raise RuntimeError if a production-profile deployment has no auth config.

    A deployment counts as production when ``FUFIRE_ENV`` is one of
    ``production``/``prod``/``staging`` (case-insensitive). Auth is considered
    configured when either the static ``FUFIRE_API_KEYS`` list is non-empty or
    a KeyStore backend is configured (``KEY_STORE_BACKEND`` != none).

    No-op for any other ``FUFIRE_ENV`` value (including unset) — the local
    dev-mode bypass in ``auth.require_api_key`` keeps working.
    """
    env = os.getenv("FUFIRE_ENV", "").strip().lower()
    if env not in _PRODUCTION_ENVS:
        return
    from bazi_engine.auth import _load_keys, _store_is_configured

    if not _load_keys() and not _store_is_configured():
        raise RuntimeError(
            f"FUFIRE_ENV={env} but auth disabled: FUFIRE_API_KEYS is empty and no "
            "KeyStore is configured. Refusing to start (fail-closed, FUFIRE-006)."
        )


def _assert_production_cors() -> None:
    cors_raw = os.getenv("CORS_ALLOWED_ORIGINS", "").strip()
    origins = [origin.strip() for origin in cors_raw.split(",") if origin.strip()]
    if not origins:
        raise RuntimeError("production profile requires an explicit CORS_ALLOWED_ORIGINS allowlist")
    if "*" in origins or any("localhost" in origin or "127.0.0.1" in origin for origin in origins):
        raise RuntimeError("production CORS_ALLOWED_ORIGINS must contain only explicit non-local origins")


def _production_replica_count() -> int:
    replica_raw = os.getenv("FUFIRE_REPLICA_COUNT", "").strip()
    try:
        replica_count = int(replica_raw)
    except ValueError as exc:
        raise RuntimeError("production profile requires a positive FUFIRE_REPLICA_COUNT") from exc
    if replica_count < 1:
        raise RuntimeError("production profile requires a positive FUFIRE_REPLICA_COUNT")
    return replica_count


def _assert_production_dependencies(replica_count: int) -> None:
    redis_required = _truthy(os.getenv("FUFIRE_REQUIRE_REDIS")) or replica_count > 1
    redis_configured = bool(os.getenv("REDIS_URL") or os.getenv("REDIS_PRIVATE_URL"))
    if redis_required and not redis_configured:
        raise RuntimeError("production profile requires Redis for the selected replica policy")

    ephemeris_mode = os.getenv("EPHEMERIS_MODE", "SWIEPH").strip().upper()
    if ephemeris_mode != "SWIEPH":
        raise RuntimeError("production profile permits EPHEMERIS_MODE=SWIEPH only")


def _assert_release_feature_policy() -> None:
    if _truthy(os.getenv("FUFIRE_ENABLE_KEY_ISSUANCE")):
        raise RuntimeError(
            "production profile disables engine key issuance; use the durable BFF plane"
        )

    if _truthy(os.getenv("FUFIRE_ENABLE_ZWDS")) and not os.getenv(
        "FUFIRE_ZWDS_SIGNOFF_ID", ""
    ).strip():
        raise RuntimeError(
            "production ZWDS requires an explicit FUFIRE_ZWDS_SIGNOFF_ID"
        )

    if _truthy(os.getenv("FUFIRE_ENABLE_HEHUN_MARKETING")):
        raise RuntimeError(
            "production Hehun marketing remains disabled pending release approval"
        )

    if _truthy(os.getenv("FUFIRE_BAZI_PRECISION_V2_DEFAULT")):
        raise RuntimeError(
            "production must not switch BaZi Precision V2 on as the default"
        )


def assert_runtime_config() -> None:
    """Validate the complete deployment profile without exposing secrets.

    Local development remains permissive. Container images set
    ``FUFIRE_REQUIRE_EXPLICIT_ENV=1`` so a deployment cannot accidentally
    start without declaring its environment.
    """
    env = os.getenv("FUFIRE_ENV", "").strip().lower()
    if _truthy(os.getenv("FUFIRE_REQUIRE_EXPLICIT_ENV")) and not env:
        raise RuntimeError("FUFIRE_ENV must be set explicitly for this runtime")
    if env not in _PRODUCTION_ENVS:
        return

    assert_production_auth_config()
    if not _truthy(os.getenv("FUFIRE_REQUIRE_API_KEYS")):
        raise RuntimeError("production profile requires FUFIRE_REQUIRE_API_KEYS=true")

    _assert_production_cors()
    replica_count = _production_replica_count()
    _assert_production_dependencies(replica_count)
    _assert_release_feature_policy()
