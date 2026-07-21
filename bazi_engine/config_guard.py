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
