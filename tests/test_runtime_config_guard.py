from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from bazi_engine.config_guard import assert_runtime_config

ROOT = Path(__file__).resolve().parents[1]


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


# ── FUF-159: unknown runtime profiles must fail closed ───────────────────────
#
# The packaged contract declares FUFIRE_ENV.allowed_values (7 values) with
# fail_closed=startup_abort. A value outside that set is a typo or a mis-wired
# deployment, never a request for the permissive development profile: falling
# through to development would skip EVERY production check (auth enforcement,
# CORS allowlist, Redis, SWIEPH, feature policy, pepper, proxy trust) while the
# operator believes the production guard is active.

UNKNOWN_ENV_VALUES = ["prodcution", "stage", "productionn", "foo"]


@pytest.mark.parametrize("value", UNKNOWN_ENV_VALUES)
def test_unknown_fufire_env_value_fails_closed(
    monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    """A typo must abort startup, never silently select development."""
    monkeypatch.setenv("FUFIRE_REQUIRE_EXPLICIT_ENV", "true")
    monkeypatch.setenv("FUFIRE_ENV", value)

    with pytest.raises(RuntimeError, match="FUFIRE_ENV"):
        assert_runtime_config()


def test_unknown_fufire_env_value_fails_closed_without_explicit_env_flag(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The typo guard is independent of FUFIRE_REQUIRE_EXPLICIT_ENV.

    A deployment that never opted into the explicit-env belt still must not be
    handed the development profile because someone mistyped ``production``.
    """
    monkeypatch.setenv("FUFIRE_ENV", "prodcution")

    with pytest.raises(RuntimeError, match="FUFIRE_ENV"):
        assert_runtime_config()


def _boot_app(env_overrides: dict[str, str]) -> tuple[int, str]:
    """Import the FastAPI app in a FRESH process. Returns ``(rc, output)``.

    ``app.py`` calls ``assert_runtime_config()`` at import time, so the claim
    worth proving is that a mis-declared deployment is REJECTED AT STARTUP —
    not merely that a readback would have called it invalid. That is a property
    of a real process start and cannot be observed from inside an already-warm
    pytest process whose modules are imported and whose caches are populated.
    """
    from bazi_engine.runtime_contract import variables

    env = dict(os.environ)
    # Start from a clean profile so the host environment cannot mask a failure.
    for entry in variables():
        env.pop(entry["name"], None)
    env.update(env_overrides)
    env["PYTHONPATH"] = str(ROOT)
    proc = subprocess.run(
        [sys.executable, "-c", "import bazi_engine.app"],
        capture_output=True,
        text=True,
        env=env,
        cwd=str(ROOT),
    )
    return proc.returncode, proc.stdout + proc.stderr


def test_startup_aborts_on_an_unknown_profile() -> None:
    """The load-bearing claim: the process must not come up at all."""
    rc, out = _boot_app(
        {"FUFIRE_ENV": "prodcution", "FUFIRE_REQUIRE_EXPLICIT_ENV": "1"}
    )

    assert rc != 0, f"app booted with an unknown FUFIRE_ENV value:\n{out}"
    assert "FUFIRE_ENV" in out, out


def test_startup_succeeds_on_a_declared_development_profile() -> None:
    """Canary for the test above: a valid profile must still boot.

    Without this, the rejection test would pass even if importing the app had
    become impossible for an unrelated reason.
    """
    rc, out = _boot_app({"FUFIRE_ENV": "dev", "FUFIRE_REQUIRE_EXPLICIT_ENV": "1"})

    assert rc == 0, f"a declared development profile failed to boot:\n{out}"


# ── FUF-159: contract ↔ startup agreement ────────────────────────────────────
#
# These iterate the PACKAGED CONTRACT rather than a hand-copied list. A test
# that restated the seven values would be a third place to keep in sync — the
# same defect class the repair removed.


def _contract_allowed_env_values() -> list[str]:
    from bazi_engine.runtime_contract import allowed_fufire_env_values

    return sorted(allowed_fufire_env_values())


def _contract_production_env_values() -> list[str]:
    from bazi_engine.runtime_contract import production_fufire_env_values

    return sorted(production_fufire_env_values())


def _contract_development_env_values() -> list[str]:
    production = set(_contract_production_env_values())
    return [v for v in _contract_allowed_env_values() if v not in production]


@pytest.mark.parametrize("value", _contract_allowed_env_values())
def test_every_contracted_value_classifies_as_a_runnable_profile(
    monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    """No value the contract declares legal may classify as invalid."""
    from bazi_engine.runtime_contract import (
        PROFILE_DEVELOPMENT,
        PROFILE_PRODUCTION,
        classify_runtime_profile,
        production_fufire_env_values,
    )

    monkeypatch.setenv("FUFIRE_ENV", value)
    expected = (
        PROFILE_PRODUCTION
        if value in production_fufire_env_values()
        else PROFILE_DEVELOPMENT
    )

    assert classify_runtime_profile() == expected


@pytest.mark.parametrize("value", _contract_production_env_values())
def test_every_contracted_production_alias_enforces_the_production_guard(
    monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    """Classification is not enough: each alias must reach the real checks.

    Dropping a required production variable has to abort for EVERY production
    alias, otherwise one of them is a silent bypass of the whole profile.
    """
    _valid_single_replica_profile(monkeypatch)
    monkeypatch.setenv("FUFIRE_ENV", value)
    monkeypatch.delenv("FUFIRE_REQUIRE_API_KEYS")

    with pytest.raises(RuntimeError, match="FUFIRE_REQUIRE_API_KEYS"):
        assert_runtime_config()


@pytest.mark.parametrize("value", _contract_development_env_values())
def test_contracted_development_aliases_stay_permissive(
    monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    """The permissive local profile survives the repair.

    No auth, no CORS allowlist and no replica count configured — a declared
    development value must still start, or this change would have broken every
    local workflow and the documented ``docker run -e FUFIRE_ENV=dev``.
    """
    monkeypatch.setenv("FUFIRE_REQUIRE_EXPLICIT_ENV", "true")
    monkeypatch.setenv("FUFIRE_ENV", value)

    assert_runtime_config()


@pytest.mark.parametrize("value", UNKNOWN_ENV_VALUES)
def test_unknown_values_classify_invalid(
    monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    from bazi_engine.runtime_contract import PROFILE_INVALID, classify_runtime_profile

    monkeypatch.setenv("FUFIRE_ENV", value)

    assert classify_runtime_profile() == PROFILE_INVALID


def test_an_unset_profile_is_development_not_invalid(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Unset is the local developer's case, policed by the explicit-env belt.

    Treating it as invalid would make ``assert_runtime_config`` raise for every
    developer who never exported FUFIRE_ENV, and would replace the precise
    "must be set explicitly" message with a value-list complaint.
    """
    from bazi_engine.runtime_contract import PROFILE_DEVELOPMENT, classify_runtime_profile

    monkeypatch.delenv("FUFIRE_ENV", raising=False)

    assert classify_runtime_profile() == PROFILE_DEVELOPMENT
    assert_runtime_config()


# ── Case E: normalisation is deterministic and does not widen the set ────────


@pytest.mark.parametrize("raw", [" production ", "Production", "PRODUCTION", "\tstaging\n"])
def test_declared_values_normalise_to_their_contracted_form(
    monkeypatch: pytest.MonkeyPatch, raw: str
) -> None:
    from bazi_engine.runtime_contract import PROFILE_PRODUCTION, classify_runtime_profile

    monkeypatch.setenv("FUFIRE_ENV", raw)

    assert classify_runtime_profile() == PROFILE_PRODUCTION


@pytest.mark.parametrize("raw", [" prodcution ", "PRODCUTION", "  Stage  "])
def test_normalisation_never_rescues_an_uncontracted_value(
    monkeypatch: pytest.MonkeyPatch, raw: str
) -> None:
    """Trimming and lowercasing must not become a way in for a typo."""
    monkeypatch.setenv("FUFIRE_ENV", raw)

    with pytest.raises(RuntimeError, match="FUFIRE_ENV"):
        assert_runtime_config()


def test_config_guard_holds_no_second_profile_value_set() -> None:
    """The design constraint, asserted structurally: ONE authoritative set.

    A literal collection restating the production aliases inside the guard is
    precisely the drift this repair removed — it would let the startup guard
    and the packaged contract disagree again without any test noticing.
    """
    import ast

    tree = ast.parse(
        (ROOT / "bazi_engine" / "config_guard.py").read_text(encoding="utf-8")
    )
    aliases = set(_contract_production_env_values())
    for node in ast.walk(tree):
        if isinstance(node, (ast.Set, ast.List, ast.Tuple)):
            literals = {
                element.value
                for element in node.elts
                if isinstance(element, ast.Constant) and isinstance(element.value, str)
            }
            restated = sorted(literals & aliases)
            assert not restated, (
                f"config_guard.py restates contract profile values {restated}; "
                "the runtime contract is the single authoritative definition"
            )
