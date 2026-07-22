from __future__ import annotations

import pytest

from bazi_engine.config_guard import assert_runtime_config


@pytest.fixture(autouse=True)
def _clean_profile_env(monkeypatch: pytest.MonkeyPatch):
    for name in (
        "FUFIRE_ENV",
        "FUFIRE_REQUIRE_EXPLICIT_ENV",
        "FUFIRE_REQUIRE_API_KEYS",
        "FUFIRE_API_KEYS",
        "KEY_STORE_BACKEND",
        "CORS_ALLOWED_ORIGINS",
        "FUFIRE_REPLICA_COUNT",
        "FUFIRE_REQUIRE_REDIS",
        "REDIS_URL",
        "REDIS_PRIVATE_URL",
        "EPHEMERIS_MODE",
        "FUFIRE_ENABLE_KEY_ISSUANCE",
        "FUFIRE_ENABLE_ZWDS",
        "FUFIRE_ZWDS_SIGNOFF_ID",
        "FUFIRE_ENABLE_HEHUN_MARKETING",
        "FUFIRE_BAZI_PRECISION_V2_DEFAULT",
    ):
        monkeypatch.delenv(name, raising=False)
    from bazi_engine.auth import _load_keys
    from bazi_engine.key_store import get_key_store

    _load_keys.cache_clear()
    get_key_store.cache_clear()
    yield
    _load_keys.cache_clear()
    get_key_store.cache_clear()


def _valid_single_replica_profile(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FUFIRE_ENV", "production")
    monkeypatch.setenv("FUFIRE_REQUIRE_API_KEYS", "true")
    monkeypatch.setenv("FUFIRE_API_KEYS", "ff_pro_runtime-test")
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "https://bazodiac.space")
    monkeypatch.setenv("FUFIRE_REPLICA_COUNT", "1")
    from bazi_engine.auth import _load_keys

    _load_keys.cache_clear()


def test_container_profile_rejects_missing_fufire_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FUFIRE_REQUIRE_EXPLICIT_ENV", "true")

    with pytest.raises(RuntimeError, match="FUFIRE_ENV"):
        assert_runtime_config()


def test_production_requires_explicit_auth_enforcement(monkeypatch: pytest.MonkeyPatch) -> None:
    _valid_single_replica_profile(monkeypatch)
    monkeypatch.delenv("FUFIRE_REQUIRE_API_KEYS")

    with pytest.raises(RuntimeError, match="FUFIRE_REQUIRE_API_KEYS"):
        assert_runtime_config()


def test_production_rejects_implicit_localhost_cors(monkeypatch: pytest.MonkeyPatch) -> None:
    _valid_single_replica_profile(monkeypatch)
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "https://bazodiac.space,http://localhost:3000")

    with pytest.raises(RuntimeError, match="non-local origins"):
        assert_runtime_config()


def test_multi_replica_production_requires_redis(monkeypatch: pytest.MonkeyPatch) -> None:
    _valid_single_replica_profile(monkeypatch)
    monkeypatch.setenv("FUFIRE_REPLICA_COUNT", "2")

    with pytest.raises(RuntimeError, match="requires Redis"):
        assert_runtime_config()


def test_valid_single_replica_production_profile(monkeypatch: pytest.MonkeyPatch) -> None:
    _valid_single_replica_profile(monkeypatch)

    assert_runtime_config()


def test_valid_multi_replica_redis_profile(monkeypatch: pytest.MonkeyPatch) -> None:
    _valid_single_replica_profile(monkeypatch)
    monkeypatch.setenv("FUFIRE_REPLICA_COUNT", "2")
    monkeypatch.setenv("FUFIRE_REQUIRE_REDIS", "true")
    monkeypatch.setenv("REDIS_URL", "redis://example.invalid:6379/0")

    assert_runtime_config()


def test_production_rejects_moseph(monkeypatch: pytest.MonkeyPatch) -> None:
    _valid_single_replica_profile(monkeypatch)
    monkeypatch.setenv("EPHEMERIS_MODE", "MOSEPH")

    with pytest.raises(RuntimeError, match="SWIEPH only"):
        assert_runtime_config()


def test_production_rejects_engine_key_issuance(monkeypatch: pytest.MonkeyPatch) -> None:
    _valid_single_replica_profile(monkeypatch)
    monkeypatch.setenv("FUFIRE_ENABLE_KEY_ISSUANCE", "true")

    with pytest.raises(RuntimeError, match="durable BFF plane"):
        assert_runtime_config()


def test_production_zwds_requires_signoff(monkeypatch: pytest.MonkeyPatch) -> None:
    _valid_single_replica_profile(monkeypatch)
    monkeypatch.setenv("FUFIRE_ENABLE_ZWDS", "true")

    with pytest.raises(RuntimeError, match="FUFIRE_ZWDS_SIGNOFF_ID"):
        assert_runtime_config()


def test_production_zwds_accepts_explicit_signoff(monkeypatch: pytest.MonkeyPatch) -> None:
    _valid_single_replica_profile(monkeypatch)
    monkeypatch.setenv("FUFIRE_ENABLE_ZWDS", "true")
    monkeypatch.setenv("FUFIRE_ZWDS_SIGNOFF_ID", "review-2026-07-owner")

    assert_runtime_config()


@pytest.mark.parametrize(
    ("flag", "message"),
    [
        ("FUFIRE_ENABLE_HEHUN_MARKETING", "Hehun marketing"),
        ("FUFIRE_BAZI_PRECISION_V2_DEFAULT", "Precision V2"),
    ],
)
def test_production_rejects_unapproved_surface_switches(
    monkeypatch: pytest.MonkeyPatch, flag: str, message: str
) -> None:
    _valid_single_replica_profile(monkeypatch)
    monkeypatch.setenv(flag, "true")

    with pytest.raises(RuntimeError, match=message):
        assert_runtime_config()
