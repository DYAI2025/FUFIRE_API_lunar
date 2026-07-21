"""
key_store.py — Pluggable persistence backend for minted API keys.

The legacy auth path validates keys against a static, comma-separated
``FUFIRE_API_KEYS`` env var (see ``auth.py``). That path is unchanged and
remains the default. This module adds an *optional* second source of truth so
an authorized caller can mint a real, immediately-valid key at runtime
(e.g. automated key issuance from the landing page).

Backends are selected by the ``KEY_STORE_BACKEND`` env var:

    none      (DEFAULT) — no store. Behaviour is byte-identical to the
                          historical env-list-only validator.
    memory    — in-process dict. For tests and local dev.

Firestore is intentionally unsupported in this Railway deployment profile.
The intended production persistence direction is a real Postgres/Supabase
backend, which is planned separately and is not implemented here.

Key format is the existing ``ff_<tier>_<hex>`` (see ``scripts/generate_api_key``):
``secrets.token_hex(16)`` → 128 bits of entropy.

Design notes
------------
* ``get_key_store()`` is memoised so the validator and the issuance endpoint
  share one instance per process (the in-memory backend would be useless
  otherwise). Call ``get_key_store.cache_clear()`` in tests after changing
  ``KEY_STORE_BACKEND``.
* Stores never log the key material. Callers log only ``jti`` + ``tier``.
"""
from __future__ import annotations

import logging
import os
import secrets
import threading
from abc import ABC, abstractmethod
from functools import lru_cache
from typing import Optional

_log = logging.getLogger(__name__)

# Tiers a store is allowed to mint. Mirrors auth.TIER_LIMITS but kept local to
# avoid a circular import (auth imports nothing from here at module load).
#
# IMPORTANT (tier-drift guard): this set is a *format/validity* check for
# mint_key — it is NOT the authorization boundary for the public issuance
# endpoint. The AUTHORITATIVE control over which tiers a caller may obtain is
# the allow-list in routers/admin.py (``_ALLOWED_ISSUANCE_TIERS`` — currently
# ``free``-only). Widening ``_MINTABLE_TIERS`` here does NOT grant any new tier
# through the HTTP endpoint, and it must never be widened without re-checking
# that admin.py allow-list, or a paid tier could become publicly self-mintable.
_MINTABLE_TIERS = frozenset({"free", "starter", "pro", "enterprise"})


def mint_key(tier: str) -> str:
    """Mint a key in the canonical ``ff_<tier>_<32-hex>`` format.

    128 bits of entropy via ``secrets.token_hex(16)`` — identical to
    ``scripts/generate_api_key.generate_key``. Raises ``ValueError`` for an
    unknown tier so a typo can never produce an un-tierable key.
    """
    if tier not in _MINTABLE_TIERS:
        raise ValueError(f"Invalid tier: {tier!r}. Must be one of {sorted(_MINTABLE_TIERS)}")
    return f"ff_{tier}_{secrets.token_hex(16)}"


class KeyStore(ABC):
    """Abstract persistence + lookup for runtime-issued API keys."""

    @abstractmethod
    def issue(self, tier: str, label: str, jti: str) -> str:
        """Mint, persist, and return a new ``ff_<tier>_<hex>`` key.

        Idempotent on ``jti``: if a key was already issued for this ``jti``,
        the SAME key is returned and nothing new is minted.
        """

    @abstractmethod
    def is_valid(self, key: str) -> bool:
        """True iff ``key`` is an active, persisted key in this store."""

    @abstractmethod
    def tier_of(self, key: str) -> Optional[str]:
        """Return the persisted tier for ``key``, or ``None`` if unknown."""

    @abstractmethod
    def find_by_jti(self, jti: str) -> Optional[str]:
        """Return the key previously issued for ``jti``, or ``None``."""


class InMemoryKeyStore(KeyStore):
    """Dict-backed store for tests and local dev. Thread-safe, non-persistent."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        # key -> {"tier", "label", "jti", "active"}
        self._by_key: dict[str, dict] = {}
        # jti -> key
        self._by_jti: dict[str, str] = {}

    def issue(self, tier: str, label: str, jti: str) -> str:
        with self._lock:
            existing = self._by_jti.get(jti)
            if existing is not None:
                return existing  # idempotent: same jti → same key
            key = mint_key(tier)
            self._by_key[key] = {"tier": tier, "label": label, "jti": jti, "active": True}
            self._by_jti[jti] = key
            return key

    def is_valid(self, key: str) -> bool:
        rec = self._by_key.get(key)
        if rec is None:
            return False
        return bool(rec.get("active", False))

    def tier_of(self, key: str) -> Optional[str]:
        rec = self._by_key.get(key)
        if rec is None or not rec.get("active", False):
            return None
        return rec.get("tier")

    def find_by_jti(self, jti: str) -> Optional[str]:
        return self._by_jti.get(jti)


@lru_cache(maxsize=1)
def get_key_store() -> Optional[KeyStore]:
    """Return the configured KeyStore, or ``None`` when no store is configured.

    Selected by ``KEY_STORE_BACKEND`` ∈ {``none`` (DEFAULT), ``memory``}.
    ``None`` means the validator falls back to env-list-only behaviour —
    byte-identical to before this module existed.

    ``firestore`` is intentionally unsupported and fails with a controlled
    configuration error instead of importing an optional dependency.

    Memoised: the in-memory backend must be a singleton to be useful. Call
    ``get_key_store.cache_clear()`` after mutating the env var in tests.
    """
    backend = os.environ.get("KEY_STORE_BACKEND", "none").strip().lower()
    if backend in ("", "none"):
        return None
    if backend == "memory":
        _log.info("KeyStore backend: in-memory (non-persistent)")
        return InMemoryKeyStore()
    if backend == "firestore":
        raise ValueError(
            "Unsupported KEY_STORE_BACKEND='firestore'. Firestore is not supported "
            "in this deployment profile. Supported backends: none, memory. "
            "Planned production backend: postgres."
        )
    raise ValueError(
        f"Unsupported KEY_STORE_BACKEND={backend!r}. Supported backends: none, memory. "
        "Planned production backend: postgres."
    )
