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
        # FUF-159 runtime-contract additions
        "FUFIRE_RL_PEPPER",
        "FORWARDED_ALLOW_IPS",
        "FUFIRE_TRUSTED_PROXY_EVIDENCE_ID",
    ):
        monkeypatch.delenv(name, raising=False)
    from bazi_engine.auth import _load_keys
    from bazi_engine.key_store import get_key_store

    _load_keys.cache_clear()
    get_key_store.cache_clear()
    yield
    _load_keys.cache_clear()
    get_key_store.cache_clear()


VALID_PEPPER = "runtime-contract-test-pepper-6e1b0a4c93df275a"


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
    # FUF-159: shared counters now also require a stable limiter pepper. Without
    # one the pseudonymous identities would differ per replica and per restart.
    monkeypatch.setenv("FUFIRE_RL_PEPPER", VALID_PEPPER)

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


# ── FUF-159: stable rate-limit pseudonymisation pepper ───────────────────────
#
# R1/R2. The shared limiter's pseudonymous identities are only stable across
# replicas and restarts when the pepper is operator-supplied. A process-local
# random value is fine for the memory-only infra limiter (its counters reset
# with the process anyway) but would silently shard every shared counter.


def _shared_counter_profile(monkeypatch: pytest.MonkeyPatch) -> None:
    """Production profile whose limiter counters outlive a single process."""
    _valid_single_replica_profile(monkeypatch)
    monkeypatch.setenv("FUFIRE_REPLICA_COUNT", "2")
    monkeypatch.setenv("FUFIRE_REQUIRE_REDIS", "true")
    monkeypatch.setenv("REDIS_URL", "redis://example.invalid:6379/0")


def test_production_shared_counters_require_a_configured_pepper(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _shared_counter_profile(monkeypatch)

    with pytest.raises(RuntimeError, match="FUFIRE_RL_PEPPER"):
        assert_runtime_config()


def test_production_shared_counters_accept_a_strong_pepper(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _shared_counter_profile(monkeypatch)
    monkeypatch.setenv("FUFIRE_RL_PEPPER", VALID_PEPPER)

    assert_runtime_config()


@pytest.mark.parametrize("value", ["", "   ", "\t\n", "short", "x" * 31])
def test_a_weak_or_blank_pepper_fails_closed(
    monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    _shared_counter_profile(monkeypatch)
    monkeypatch.setenv("FUFIRE_RL_PEPPER", value)

    with pytest.raises(RuntimeError, match="FUFIRE_RL_PEPPER"):
        assert_runtime_config()


def test_a_weak_pepper_fails_closed_outside_production_too(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A set-but-unusable secret is never silently ignored, in any profile."""
    monkeypatch.setenv("FUFIRE_ENV", "dev")
    monkeypatch.setenv("FUFIRE_RL_PEPPER", "too-short")

    with pytest.raises(RuntimeError, match="FUFIRE_RL_PEPPER"):
        assert_runtime_config()


def test_no_guard_message_ever_echoes_the_pepper_value(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A fail-closed message must not become the leak it exists to prevent."""
    leaky_value = "SENTINELWEAKPEPPER"
    monkeypatch.setenv("FUFIRE_ENV", "dev")
    monkeypatch.setenv("FUFIRE_RL_PEPPER", leaky_value)

    with pytest.raises(RuntimeError) as excinfo:
        assert_runtime_config()

    assert leaky_value not in str(excinfo.value)


def test_single_replica_production_without_shared_storage_needs_no_pepper(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Counters that die with the process lose nothing to a rotating pepper."""
    _valid_single_replica_profile(monkeypatch)

    assert_runtime_config()


def test_configured_redis_alone_requires_a_pepper(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """One replica plus Redis still means counters that outlive a restart."""
    _valid_single_replica_profile(monkeypatch)
    monkeypatch.setenv("REDIS_URL", "redis://example.invalid:6379/0")

    with pytest.raises(RuntimeError, match="FUFIRE_RL_PEPPER"):
        assert_runtime_config()


# ── FUF-159: proxy-trust configuration guard (no binding, guard only) ────────
#
# R9/R10. This slice does NOT enable proxy trust and does NOT set
# FORWARDED_ALLOW_IPS. It only makes an unsafe or unevidenced widening of that
# value impossible to deploy. The concrete Northflank ingress binding is
# FUF-168 and is unresolved, so no CIDR is asserted anywhere below.

EVIDENCE_ID = "FUF-168-E1-PLACEHOLDER-NOT-A-BINDING"


def test_production_rejects_wildcard_proxy_trust(monkeypatch: pytest.MonkeyPatch) -> None:
    _valid_single_replica_profile(monkeypatch)
    monkeypatch.setenv("FORWARDED_ALLOW_IPS", "*")

    with pytest.raises(RuntimeError, match="FORWARDED_ALLOW_IPS"):
        assert_runtime_config()


def test_production_rejects_wildcard_proxy_trust_even_with_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Evidence can justify a narrow allowlist. It can never justify a wildcard."""
    _valid_single_replica_profile(monkeypatch)
    monkeypatch.setenv("FORWARDED_ALLOW_IPS", "*")
    monkeypatch.setenv("FUFIRE_TRUSTED_PROXY_EVIDENCE_ID", EVIDENCE_ID)

    with pytest.raises(RuntimeError, match="FORWARDED_ALLOW_IPS"):
        assert_runtime_config()


def test_production_rejects_unevidenced_non_default_proxy_trust(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _valid_single_replica_profile(monkeypatch)
    # Documentation-range placeholder. NOT a Northflank ingress claim.
    monkeypatch.setenv("FORWARDED_ALLOW_IPS", "203.0.113.0/24")

    with pytest.raises(RuntimeError, match="FUFIRE_TRUSTED_PROXY_EVIDENCE_ID"):
        assert_runtime_config()


def test_production_accepts_an_evidenced_non_default_proxy_trust(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _valid_single_replica_profile(monkeypatch)
    monkeypatch.setenv("FORWARDED_ALLOW_IPS", "203.0.113.0/24")
    monkeypatch.setenv("FUFIRE_TRUSTED_PROXY_EVIDENCE_ID", EVIDENCE_ID)

    assert_runtime_config()


def test_production_rejects_a_blank_evidence_reference(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _valid_single_replica_profile(monkeypatch)
    monkeypatch.setenv("FORWARDED_ALLOW_IPS", "203.0.113.0/24")
    monkeypatch.setenv("FUFIRE_TRUSTED_PROXY_EVIDENCE_ID", "   ")

    with pytest.raises(RuntimeError, match="FUFIRE_TRUSTED_PROXY_EVIDENCE_ID"):
        assert_runtime_config()


@pytest.mark.parametrize("value", ["127.0.0.1", " 127.0.0.1 "])
def test_production_accepts_the_uvicorn_safe_default_without_evidence(
    monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    """Uvicorn's own default trusts only the loopback peer — unchanged is safe."""
    _valid_single_replica_profile(monkeypatch)
    monkeypatch.setenv("FORWARDED_ALLOW_IPS", value)

    assert_runtime_config()


def test_production_accepts_proxy_trust_left_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    """The shipped state: this slice must not require operators to set anything."""
    _valid_single_replica_profile(monkeypatch)

    assert_runtime_config()
