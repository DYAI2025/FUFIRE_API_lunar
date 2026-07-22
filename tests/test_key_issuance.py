"""
test_key_issuance.py — KeyStore abstraction + POST /v1/admin/keys issuance.

Covers:
  * KeyStore backends (none/memory) + unsupported-backend factory selection.
  * Validator composition: env-list OR store; tier resolution order.
  * Admin issuance endpoint: 503/401/400 gating, free-only, idempotency.
  * Anti-mockup proof: an ISSUED key immediately authenticates a protected
    /v1 endpoint in-process; a NON-issued key still 401s.
  * Zero-regression guard: with no store, behaviour is unchanged.

These tests scrupulously reset the cached factory and the env-key cache in
setup/teardown so they never leak the memory store into the rest of the suite
(which must run with KEY_STORE_BACKEND unset → byte-identical legacy behaviour).
"""
from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

# ── Env / cache hygiene ───────────────────────────────────────────────────────

def _reset_caches() -> None:
    from bazi_engine.auth import _load_keys, _load_tier_overrides
    from bazi_engine.key_store import get_key_store

    _load_keys.cache_clear()
    _load_tier_overrides.cache_clear()
    get_key_store.cache_clear()


@pytest.fixture
def clean_env():
    """Snapshot + restore the env vars these tests mutate."""
    keys = ("KEY_STORE_BACKEND", "FUFIRE_ADMIN_TOKEN", "FUFIRE_API_KEYS",
            "FUFIRE_REQUIRE_API_KEYS", "FUFIRE_KEY_TIER_OVERRIDES",
            "FUFIRE_ENABLE_KEY_ISSUANCE")
    saved = {k: os.environ.get(k) for k in keys}
    for k in keys:
        os.environ.pop(k, None)
    os.environ["FUFIRE_ENABLE_KEY_ISSUANCE"] = "true"
    _reset_caches()
    yield
    for k, v in saved.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v
    _reset_caches()


def _fresh_client() -> TestClient:
    # Import inside so the module-level app picks up current env/caches.
    from bazi_engine.app import app
    return TestClient(app, raise_server_exceptions=True)


# ── KeyStore unit tests ───────────────────────────────────────────────────────

class TestKeyStoreFactory:
    def test_default_backend_is_none(self, clean_env):
        from bazi_engine.key_store import get_key_store
        assert get_key_store() is None

    def test_explicit_none_is_none(self, clean_env):
        from bazi_engine.key_store import get_key_store
        os.environ["KEY_STORE_BACKEND"] = "none"
        get_key_store.cache_clear()
        assert get_key_store() is None

    def test_memory_backend_selected(self, clean_env):
        from bazi_engine.key_store import InMemoryKeyStore, get_key_store
        os.environ["KEY_STORE_BACKEND"] = "memory"
        get_key_store.cache_clear()
        assert isinstance(get_key_store(), InMemoryKeyStore)

    def test_unknown_backend_raises(self, clean_env):
        from bazi_engine.key_store import get_key_store
        os.environ["KEY_STORE_BACKEND"] = "bogus"
        get_key_store.cache_clear()
        with pytest.raises(ValueError):
            get_key_store()

    def test_factory_is_singleton(self, clean_env):
        from bazi_engine.key_store import get_key_store
        os.environ["KEY_STORE_BACKEND"] = "memory"
        get_key_store.cache_clear()
        assert get_key_store() is get_key_store()


class TestInMemoryKeyStore:
    def test_issue_returns_canonical_format(self, clean_env):
        from bazi_engine.key_store import InMemoryKeyStore
        store = InMemoryKeyStore()
        key = store.issue("free", "landing", "jti-aaa")
        assert key.startswith("ff_free_")
        # ff_free_ + 32 hex chars (secrets.token_hex(16))
        assert len(key) == len("ff_free_") + 32

    def test_issue_idempotent_on_jti(self, clean_env):
        from bazi_engine.key_store import InMemoryKeyStore
        store = InMemoryKeyStore()
        k1 = store.issue("free", "landing", "jti-same")
        k2 = store.issue("free", "landing", "jti-same")
        assert k1 == k2
        # exactly one stored
        assert sum(1 for _ in store._by_key) == 1  # noqa: SLF001

    def test_is_valid_and_tier_of(self, clean_env):
        from bazi_engine.key_store import InMemoryKeyStore
        store = InMemoryKeyStore()
        key = store.issue("free", "x", "jti-1")
        assert store.is_valid(key) is True
        assert store.tier_of(key) == "free"

    def test_unknown_key_invalid(self, clean_env):
        from bazi_engine.key_store import InMemoryKeyStore
        store = InMemoryKeyStore()
        assert store.is_valid("ff_free_deadbeef") is False
        assert store.tier_of("ff_free_deadbeef") is None

    def test_find_by_jti(self, clean_env):
        from bazi_engine.key_store import InMemoryKeyStore
        store = InMemoryKeyStore()
        key = store.issue("free", "x", "jti-find")
        assert store.find_by_jti("jti-find") == key
        assert store.find_by_jti("nope") is None

    def test_mint_rejects_unknown_tier(self, clean_env):
        from bazi_engine.key_store import mint_key
        with pytest.raises(ValueError):
            mint_key("platinum")


class TestUnsupportedKeyStoreBackends:
    """Unsupported backend selections must fail predictably and safely."""

    def test_module_imports_without_firestore_dependency(self, clean_env):
        import sys

        import bazi_engine.key_store as ks

        assert not hasattr(ks, "FirestoreKeyStore")
        assert "google.cloud.firestore" not in sys.modules

    def test_firestore_backend_fails_with_controlled_error(self, clean_env):
        from bazi_engine.key_store import get_key_store

        os.environ["KEY_STORE_BACKEND"] = "firestore"
        get_key_store.cache_clear()
        try:
            with pytest.raises(ValueError) as exc_info:
                get_key_store()
        except ModuleNotFoundError as exc:  # pragma: no cover - regression clarity
            pytest.fail(f"firestore backend raised ModuleNotFoundError: {exc}")

        message = str(exc_info.value)
        assert "Unsupported KEY_STORE_BACKEND='firestore'" in message
        assert "Supported backends: none, memory" in message
        assert "Firestore is not supported" in message
        assert "Expected one of" not in message
        assert "none, memory, firestore" not in message
        assert "google-cloud-firestore" not in message

    def test_unknown_backend_fails_with_current_supported_values(self, clean_env):
        from bazi_engine.key_store import get_key_store

        os.environ["KEY_STORE_BACKEND"] = "bogus"
        get_key_store.cache_clear()
        with pytest.raises(ValueError) as exc_info:
            get_key_store()

        message = str(exc_info.value)
        assert "Unsupported KEY_STORE_BACKEND='bogus'" in message
        assert "Supported backends: none, memory" in message
        assert "none, memory, firestore" not in message


# ── Validator composition ─────────────────────────────────────────────────────

class TestValidatorComposition:
    def test_env_key_still_valid_with_no_store(self, clean_env):
        from bazi_engine.auth import _is_valid_api_key, _load_keys, _store_is_valid
        os.environ["FUFIRE_API_KEYS"] = "env-key-1,env-key-2"
        _load_keys.cache_clear()
        keys = _load_keys()
        assert _is_valid_api_key("env-key-1", keys) is True
        # store path is inert when no store configured
        assert _store_is_valid("env-key-1") is False

    def test_store_key_valid_when_store_configured(self, clean_env):
        from bazi_engine.auth import _store_is_valid
        from bazi_engine.key_store import get_key_store
        os.environ["KEY_STORE_BACKEND"] = "memory"
        get_key_store.cache_clear()
        key = get_key_store().issue("free", "x", "jti-v")
        assert _store_is_valid(key) is True
        assert _store_is_valid("ff_free_notissued") is False

    def test_tier_of_issued_free_key_is_free(self, clean_env):
        """resolve_key_info resolves a store-issued key's tier (prefix path)."""
        from bazi_engine.auth import resolve_key_info
        from bazi_engine.key_store import get_key_store
        os.environ["KEY_STORE_BACKEND"] = "memory"
        get_key_store.cache_clear()
        key = get_key_store().issue("free", "x", "jti-tier")
        info = resolve_key_info(key)
        assert info.tier == "free"
        # rate-limit tier resolves to free's per-minute quota
        assert info.requests_per_minute == 5

    def test_store_tier_used_for_nonprefixed_key(self, clean_env):
        """A key the prefix can't classify falls through to the store tier."""
        from bazi_engine.auth import _store_tier_of, resolve_key_info
        from bazi_engine.key_store import InMemoryKeyStore, get_key_store
        os.environ["KEY_STORE_BACKEND"] = "memory"
        get_key_store.cache_clear()
        store = get_key_store()
        assert isinstance(store, InMemoryKeyStore)
        # Inject a non-ff_ key directly to exercise the store-tier branch.
        store._by_key["legacy-issued"] = {"tier": "pro", "label": "", "jti": "j", "active": True}  # noqa: SLF001
        store._by_jti["j"] = "legacy-issued"  # noqa: SLF001
        assert _store_tier_of("legacy-issued") == "pro"
        assert resolve_key_info("legacy-issued").tier == "pro"

    def test_ratelimit_tier_resolves_for_issued_key(self, clean_env):
        from bazi_engine.key_store import get_key_store
        from bazi_engine.limiter import tier_limit
        os.environ["KEY_STORE_BACKEND"] = "memory"
        get_key_store.cache_clear()
        key = get_key_store().issue("free", "x", "jti-rl")
        # free → 5/minute (prefix-resolved)
        assert tier_limit(key) == "5/minute"


# ── Admin issuance endpoint ───────────────────────────────────────────────────

class TestAdminIssuanceGating:
    def test_503_when_no_store_even_with_admin_token(self, clean_env):
        os.environ["FUFIRE_ADMIN_TOKEN"] = "admin-secret"
        # no KEY_STORE_BACKEND → no store
        _reset_caches()
        c = _fresh_client()
        r = c.post("/v1/admin/keys",
                   headers={"X-Admin-Token": "admin-secret"},
                   json={"tier": "free", "label": "x", "jti": "j1"})
        assert r.status_code == 503
        # The global exception handler flattens HTTPException.detail into the
        # standard ErrorEnvelope (error/message at top level).
        assert r.json()["message"] == "key issuance not configured"

    def test_503_when_store_but_no_admin_token(self, clean_env):
        os.environ["KEY_STORE_BACKEND"] = "memory"
        # no FUFIRE_ADMIN_TOKEN
        _reset_caches()
        c = _fresh_client()
        r = c.post("/v1/admin/keys",
                   headers={"X-Admin-Token": "whatever"},
                   json={"tier": "free", "label": "x", "jti": "j1"})
        assert r.status_code == 503
        assert r.json()["message"] == "key issuance not configured"

    def test_401_wrong_admin_token(self, clean_env):
        os.environ["KEY_STORE_BACKEND"] = "memory"
        os.environ["FUFIRE_ADMIN_TOKEN"] = "right-token"
        _reset_caches()
        c = _fresh_client()
        r = c.post("/v1/admin/keys",
                   headers={"X-Admin-Token": "wrong-token"},
                   json={"tier": "free", "label": "x", "jti": "j1"})
        assert r.status_code == 401

    def test_401_missing_admin_token(self, clean_env):
        os.environ["KEY_STORE_BACKEND"] = "memory"
        os.environ["FUFIRE_ADMIN_TOKEN"] = "right-token"
        _reset_caches()
        c = _fresh_client()
        r = c.post("/v1/admin/keys",
                   json={"tier": "free", "label": "x", "jti": "j1"})
        assert r.status_code == 401

    def test_non_free_tier_rejected(self, clean_env):
        os.environ["KEY_STORE_BACKEND"] = "memory"
        os.environ["FUFIRE_ADMIN_TOKEN"] = "right-token"
        _reset_caches()
        c = _fresh_client()
        r = c.post("/v1/admin/keys",
                   headers={"X-Admin-Token": "right-token"},
                   json={"tier": "pro", "label": "x", "jti": "j1"})
        assert r.status_code == 400
        assert r.json()["error"] == "tier_not_allowed"

    def test_issue_returns_key_and_tier(self, clean_env):
        os.environ["KEY_STORE_BACKEND"] = "memory"
        os.environ["FUFIRE_ADMIN_TOKEN"] = "right-token"
        _reset_caches()
        c = _fresh_client()
        r = c.post("/v1/admin/keys",
                   headers={"X-Admin-Token": "right-token"},
                   json={"tier": "free", "label": "landing", "jti": "j-new"})
        assert r.status_code == 200
        body = r.json()
        assert body["tier"] == "free"
        assert body["key"].startswith("ff_free_")
        assert set(body.keys()) == {"key", "tier"}

    def test_idempotent_same_jti_same_key(self, clean_env):
        os.environ["KEY_STORE_BACKEND"] = "memory"
        os.environ["FUFIRE_ADMIN_TOKEN"] = "right-token"
        _reset_caches()
        c = _fresh_client()
        hdr = {"X-Admin-Token": "right-token"}
        body = {"tier": "free", "label": "x", "jti": "j-idem"}
        r1 = c.post("/v1/admin/keys", headers=hdr, json=body)
        r2 = c.post("/v1/admin/keys", headers=hdr, json=body)
        assert r1.status_code == 200 and r2.status_code == 200
        assert r1.json()["key"] == r2.json()["key"]
        # exactly one stored
        from bazi_engine.key_store import get_key_store
        store = get_key_store()
        assert sum(1 for _ in store._by_key) == 1  # noqa: SLF001


class TestWeakAdminTokenWarning:
    """Fix 2 (defense-in-depth): warn once if FUFIRE_ADMIN_TOKEN is weak (<32)."""

    def _reset_warned_flag(self) -> None:
        # The one-time guard lives on the admin module; reset it so each test
        # observes the first-use warning independently.
        import bazi_engine.routers.admin as admin_mod
        admin_mod._WEAK_TOKEN_WARNED = False  # noqa: SLF001

    def test_weak_token_logs_warning_once(self, clean_env, caplog):
        import logging
        os.environ["KEY_STORE_BACKEND"] = "memory"
        os.environ["FUFIRE_ADMIN_TOKEN"] = "short-token"  # len 11 < 32
        _reset_caches()
        self._reset_warned_flag()
        c = _fresh_client()
        hdr = {"X-Admin-Token": "short-token"}
        body = {"tier": "free", "label": "x", "jti": "j-weak"}
        with caplog.at_level(logging.WARNING, logger="bazi_engine.routers.admin"):
            c.post("/v1/admin/keys", headers=hdr, json={**body, "jti": "j-weak-1"})
            c.post("/v1/admin/keys", headers=hdr, json={**body, "jti": "j-weak-2"})
        weak_warnings = [
            r for r in caplog.records
            if "FUFIRE_ADMIN_TOKEN is short" in r.getMessage()
        ]
        assert len(weak_warnings) == 1, (
            f"expected exactly one weak-token warning, got {len(weak_warnings)}"
        )
        # The token value must never appear in the log.
        assert "short-token" not in caplog.text

    def test_strong_token_logs_no_warning(self, clean_env, caplog):
        import logging
        import secrets
        os.environ["KEY_STORE_BACKEND"] = "memory"
        strong = secrets.token_urlsafe(32)  # >= 32 chars, high entropy
        assert len(strong) >= 32
        os.environ["FUFIRE_ADMIN_TOKEN"] = strong
        _reset_caches()
        self._reset_warned_flag()
        c = _fresh_client()
        with caplog.at_level(logging.WARNING, logger="bazi_engine.routers.admin"):
            c.post("/v1/admin/keys",
                   headers={"X-Admin-Token": strong},
                   json={"tier": "free", "label": "x", "jti": "j-strong"})
        weak_warnings = [
            r for r in caplog.records
            if "FUFIRE_ADMIN_TOKEN is short" in r.getMessage()
        ]
        assert weak_warnings == [], "strong token must not trigger the weak-token warning"

    def test_exactly_32_char_token_is_not_weak(self, clean_env, caplog):
        """Boundary: len == 32 is acceptable (warn only on len < 32)."""
        import logging
        os.environ["KEY_STORE_BACKEND"] = "memory"
        token32 = "a" * 32
        os.environ["FUFIRE_ADMIN_TOKEN"] = token32
        _reset_caches()
        self._reset_warned_flag()
        c = _fresh_client()
        with caplog.at_level(logging.WARNING, logger="bazi_engine.routers.admin"):
            c.post("/v1/admin/keys",
                   headers={"X-Admin-Token": token32},
                   json={"tier": "free", "label": "x", "jti": "j-32"})
        weak_warnings = [
            r for r in caplog.records
            if "FUFIRE_ADMIN_TOKEN is short" in r.getMessage()
        ]
        assert weak_warnings == [], "a 32-char token is not weak"


class TestAntiMockupIssuedKeyAuthenticates:
    """The make-or-break proof: an issued key immediately authenticates."""

    def test_issued_key_passes_protected_endpoint_and_unissued_401s(self, clean_env):
        os.environ["KEY_STORE_BACKEND"] = "memory"
        os.environ["FUFIRE_ADMIN_TOKEN"] = "right-token"
        # NOTE: deliberately NO FUFIRE_API_KEYS — proving the store alone
        # enables auth (and that empty env list does not silently dev-mode).
        _reset_caches()
        c = _fresh_client()

        # 1. Mint a real key via the admin endpoint.
        issue = c.post("/v1/admin/keys",
                       headers={"X-Admin-Token": "right-token"},
                       json={"tier": "free", "label": "e2e", "jti": "j-e2e"})
        assert issue.status_code == 200
        issued_key = issue.json()["key"]

        # 2. That key immediately authenticates a protected /v1 endpoint.
        ok = c.post("/v1/calculate/bazi", json={}, headers={"X-API-Key": issued_key})
        assert ok.status_code != 401, f"issued key was rejected: {ok.status_code} {ok.text[:200]}"
        # 422 (bad body) is fine — it proves we got PAST auth into validation.
        assert ok.status_code in (200, 422)

        # 3. A key that was never issued is still rejected.
        bad = c.post("/v1/calculate/bazi", json={},
                     headers={"X-API-Key": "ff_free_neverissued0000000000000000"})
        assert bad.status_code == 401

        # 4. No key at all → 401 (store configured ⇒ no dev-mode bypass).
        none = c.post("/v1/calculate/bazi", json={})
        assert none.status_code == 401


# ── Zero-regression guard (store OFF) ──────────────────────────────────────────

class TestZeroRegressionStoreOff:
    """With KEY_STORE_BACKEND unset, behaviour is byte-identical to legacy."""

    def test_dev_mode_bypass_when_empty_env_and_no_store(self, clean_env):
        # No FUFIRE_API_KEYS, no store, no strict flag → dev-mode (auth disabled).
        _reset_caches()
        c = _fresh_client()
        r = c.post("/v1/calculate/bazi", json={})
        # dev-mode: not 401 (auth bypassed). 422 for empty body is expected.
        assert r.status_code != 401

    def test_env_list_only_still_enforces_401(self, clean_env):
        os.environ["FUFIRE_API_KEYS"] = "legacy-key-1"
        _reset_caches()
        c = _fresh_client()
        assert c.post("/v1/calculate/bazi", json={}).status_code == 401
        ok = c.post("/v1/calculate/bazi", json={}, headers={"X-API-Key": "legacy-key-1"})
        assert ok.status_code != 401

    def test_strict_mode_503_unchanged_with_no_store(self, clean_env):
        os.environ["FUFIRE_REQUIRE_API_KEYS"] = "1"
        os.environ["FUFIRE_API_KEYS"] = ""
        _reset_caches()
        c = _fresh_client()
        r = c.post("/v1/calculate/bazi", json={})
        assert r.status_code == 503
        assert r.json().get("error") == "auth_configuration_error"

    def test_admin_endpoint_503_with_no_store_no_token(self, clean_env):
        _reset_caches()
        c = _fresh_client()
        r = c.post("/v1/admin/keys", json={"tier": "free", "label": "x", "jti": "j"})
        assert r.status_code == 503
