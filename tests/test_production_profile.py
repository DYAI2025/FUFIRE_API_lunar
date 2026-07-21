"""FUFIRE-006: FUFIRE_ENV=production must never boot with auth disabled.

The dev-mode auth bypass (empty FUFIRE_API_KEYS + no KeyStore configured) is a
wanted local feature, but in production a missing/renamed secret must abort
startup instead of silently exposing every protected route.
"""
from __future__ import annotations

import pytest

from bazi_engine.config_guard import assert_production_auth_config


@pytest.fixture(autouse=True)
def _reset_auth_caches():
    """auth._load_keys and key_store.get_key_store are lru_cached — clear
    around each test so monkeypatched env vars are actually re-read."""
    from bazi_engine.auth import _load_keys
    from bazi_engine.key_store import get_key_store

    _load_keys.cache_clear()
    get_key_store.cache_clear()
    yield
    _load_keys.cache_clear()
    get_key_store.cache_clear()


def test_production_without_keys_refuses_to_start(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FUFIRE_ENV", "production")
    monkeypatch.delenv("FUFIRE_API_KEYS", raising=False)
    monkeypatch.delenv("KEY_STORE_BACKEND", raising=False)
    with pytest.raises(RuntimeError, match="auth disabled"):
        assert_production_auth_config()


def test_production_with_keys_boots(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FUFIRE_ENV", "production")
    monkeypatch.setenv("FUFIRE_API_KEYS", "ff_pro_testkey123")
    assert_production_auth_config()  # no raise


def test_production_with_key_store_boots(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FUFIRE_ENV", "production")
    monkeypatch.delenv("FUFIRE_API_KEYS", raising=False)
    monkeypatch.setenv("KEY_STORE_BACKEND", "memory")
    assert_production_auth_config()  # no raise — KeyStore counts as auth config


def test_prod_alias_also_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FUFIRE_ENV", "prod")
    monkeypatch.delenv("FUFIRE_API_KEYS", raising=False)
    monkeypatch.delenv("KEY_STORE_BACKEND", raising=False)
    with pytest.raises(RuntimeError, match="auth disabled"):
        assert_production_auth_config()


def test_staging_also_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FUFIRE_ENV", "staging")
    monkeypatch.delenv("FUFIRE_API_KEYS", raising=False)
    monkeypatch.delenv("KEY_STORE_BACKEND", raising=False)
    with pytest.raises(RuntimeError, match="auth disabled"):
        assert_production_auth_config()


def test_dev_env_unaffected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("FUFIRE_ENV", raising=False)
    monkeypatch.delenv("FUFIRE_API_KEYS", raising=False)
    monkeypatch.delenv("KEY_STORE_BACKEND", raising=False)
    assert_production_auth_config()  # no raise — local dev keeps working


def test_explicit_development_env_unaffected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FUFIRE_ENV", "development")
    monkeypatch.delenv("FUFIRE_API_KEYS", raising=False)
    monkeypatch.delenv("KEY_STORE_BACKEND", raising=False)
    assert_production_auth_config()  # no raise
