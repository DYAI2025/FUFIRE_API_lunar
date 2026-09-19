"""FUF-159: the versioned, secrets-free runtime configuration contract.

Scope of this file is the provider-neutral half of FUF-159 only. It asserts:

* R12 — the contract and ``config_guard`` cannot silently diverge: every env var
  the startup guard reads is inventoried, and every inventoried variable really
  exists in the source tree (no phantom rows).
* R11 — a readback never emits a configured secret's value, prefix or suffix.
  Every secret is set to a unique sentinel and the FULL serialized readback is
  scanned for it, rather than trusting a per-field assertion.
* R13 — the contract resource ships in the distribution via the canonical
  allow-list (``scripts/verify_distribution.py`` + ``pyproject`` package-data),
  not merely as a file in the repository checkout.

The readback is exercised through ``python -m bazi_engine.runtime_contract``
in a SUBPROCESS, because "works from the built distribution/container" is a
claim about the module's ``__main__`` entry point and its import graph, not
about a function call inside an already-warm pytest process.

NOT in scope here and deliberately untested: any concrete Northflank ingress or
trusted-proxy binding. That evidence is FUF-168 and is unresolved.
"""
from __future__ import annotations

import ast
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "bazi_engine" / "resources" / "runtime_contract.v1.json"
SCHEMA_ID = "fufire.runtime-config-contract.v1"

# Unique, obviously-synthetic sentinels. Each one is long and distinctive enough
# that a substring search over the whole readback is a meaningful leak test.
SECRET_SENTINELS: dict[str, str] = {
    "FUFIRE_API_KEYS": "ff_pro_SENTINELAPIKEY7f3a91c0d4e2",
    "FUFIRE_ADMIN_TOKEN": "SENTINELADMINTOKEN5b21ce77a90f",
    "FUFIRE_RL_PEPPER": "SENTINELPEPPER0d4c8ba62fe19037aa5c",
    "ELEVENLABS_TOOL_SECRET": "SENTINELWEBHOOKSECRET3ac70e15bd",
    "SUPERGLUE_API_KEY": "SENTINELSUPERGLUEKEY91fe3c07ab",
    "FUFIRE_KEY_TIER_OVERRIDES": "ff_free_SENTINELOVERRIDE81ca:pro",
    "REDIS_URL": "redis://sentineluser:SENTINELREDISPW4410@redis.invalid:6379/0",
}


# ── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def contract() -> dict[str, Any]:
    from bazi_engine.runtime_contract import load_contract

    return load_contract()


def _readback(env_overrides: dict[str, str]) -> tuple[int, str]:
    """Run the packaged readback CLI in a fresh process. Returns (rc, stdout)."""
    env = dict(os.environ)
    # Start from a clean profile so the test controls every contracted variable.
    for name in _contract_variable_names():
        env.pop(name, None)
    env.update(env_overrides)
    env["PYTHONPATH"] = str(ROOT)
    proc = subprocess.run(
        [sys.executable, "-m", "bazi_engine.runtime_contract", "--readback", "--json"],
        capture_output=True,
        text=True,
        env=env,
        cwd=str(ROOT),
    )
    return proc.returncode, proc.stdout + proc.stderr


def _contract_variable_names() -> list[str]:
    raw = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    return [entry["name"] for entry in raw["variables"]]


# ── Contract shape ───────────────────────────────────────────────────────────

def test_contract_is_loadable_through_the_package_resource_boundary(contract) -> None:
    """The runtime reads the contract from package data, never from ``spec/``."""
    assert contract["schema"] == SCHEMA_ID
    assert re.fullmatch(r"\d+\.\d+\.\d+", contract["contract_version"])
    assert contract["variables"], "contract inventories no variables"


def test_every_contract_record_carries_the_required_fields(contract) -> None:
    required_fields = {
        "name",
        "owner_area",
        "consumer",
        "secret",
        "required_profiles",
        "readback",
        "fail_closed",
        "description",
    }
    for entry in contract["variables"]:
        missing = sorted(required_fields - set(entry))
        assert not missing, f"{entry.get('name')!r} is missing contract fields: {missing}"
        assert entry["consumer"] in {"engine", "uvicorn"}, entry["name"]
        assert entry["readback"] in {"value", "presence"}, entry["name"]
        assert isinstance(entry["secret"], bool), entry["name"]
        assert isinstance(entry["required_profiles"], list), entry["name"]


def test_no_contract_record_stores_a_secret_value(contract) -> None:
    """The contract is an inventory. It must never carry credential material."""
    text = CONTRACT_PATH.read_text(encoding="utf-8")
    for entry in contract["variables"]:
        if not entry["secret"]:
            continue
        # A secret row may declare a minimum length, never an example value.
        assert "example" not in entry, f"{entry['name']} carries an example value"
        assert entry["readback"] == "presence", (
            f"{entry['name']} is secret but its readback policy is not presence-only"
        )
    assert "ff_pro_" not in text and "ff_enterprise_" not in text, (
        "contract file contains key-shaped material"
    )


def test_contract_names_are_unique(contract) -> None:
    names = [entry["name"] for entry in contract["variables"]]
    assert len(names) == len(set(names)), "duplicate variable rows in the contract"


# ── R12 — contract/config-guard drift ────────────────────────────────────────

def _env_names_read_by(path: Path) -> set[str]:
    """Every literal env-var name read via os.getenv/os.environ in ``path``."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            fn = node.func
            name = getattr(fn, "attr", None)
            if name in {"getenv", "get"} and node.args:
                first = node.args[0]
                if isinstance(first, ast.Constant) and isinstance(first.value, str):
                    if first.value.isupper() and "_" in first.value or first.value.isupper():
                        found.add(first.value)
        elif isinstance(node, ast.Subscript):
            idx = node.slice
            if isinstance(idx, ast.Constant) and isinstance(idx.value, str) and idx.value.isupper():
                found.add(idx.value)
    return {n for n in found if re.fullmatch(r"[A-Z][A-Z0-9_]{2,}", n)}


GUARD_SOURCES = (
    "bazi_engine/config_guard.py",
    "bazi_engine/limiter.py",
    "bazi_engine/auth.py",
    "bazi_engine/key_store.py",
    "bazi_engine/runtime_contract.py",
    "start.py",
)


def test_contract_covers_every_env_var_read_by_the_startup_boundary(contract) -> None:
    """A guard that reads a variable the contract does not know about is drift."""
    contracted = {entry["name"] for entry in contract["variables"]}
    uncovered: dict[str, set[str]] = {}
    for rel in GUARD_SOURCES:
        path = ROOT / rel
        missing = _env_names_read_by(path) - contracted
        if missing:
            uncovered[rel] = missing
    assert not uncovered, f"env vars read but not inventoried in the contract: {uncovered}"


def test_contract_has_no_phantom_variables(contract) -> None:
    """Every inventoried name must actually appear in the engine or its runtime."""
    haystacks = [
        (ROOT / "bazi_engine").rglob("*.py"),
        [ROOT / "start.py"],
    ]
    corpus = ""
    for group in haystacks:
        for path in group:
            corpus += path.read_text(encoding="utf-8")
    phantom = [e["name"] for e in contract["variables"] if e["name"] not in corpus]
    assert not phantom, f"contract rows with no consumer in the source tree: {phantom}"


def test_fail_closed_rows_are_enforced_by_config_guard(contract) -> None:
    """Rows declaring startup_abort must be reachable from ``assert_runtime_config``."""
    guard_src = (ROOT / "bazi_engine" / "config_guard.py").read_text(encoding="utf-8")
    contract_src = (ROOT / "bazi_engine" / "runtime_contract.py").read_text(encoding="utf-8")
    combined = guard_src + contract_src
    unenforced = [
        e["name"]
        for e in contract["variables"]
        if e["fail_closed"] == "startup_abort" and e["name"] not in combined
    ]
    assert not unenforced, f"startup_abort rows with no guard reference: {unenforced}"


# ── R13 — packaging ──────────────────────────────────────────────────────────

def test_contract_is_on_the_canonical_distribution_allowlist() -> None:
    sys.path.insert(0, str(ROOT / "scripts"))
    try:
        import verify_distribution  # type: ignore[import-not-found]
    finally:
        sys.path.pop(0)
    assert (
        "bazi_engine/resources/runtime_contract.v1.json"
        in verify_distribution.EXPECTED_JSON_RESOURCES
    )


def test_contract_is_declared_as_package_data() -> None:
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert "runtime_contract.v1.json" in pyproject, (
        "the contract resource is not declared in [tool.setuptools.package-data]"
    )


# ── R11 — secret-safe readback ───────────────────────────────────────────────

def test_readback_emits_the_documented_envelope() -> None:
    rc, out = _readback(
        {
            "FUFIRE_ENV": "dev",
            "EPHEMERIS_MODE": "SWIEPH",
        }
    )
    payload = json.loads(out)
    assert payload["schema"] == SCHEMA_ID
    for field in ("contractVersion", "profile", "engineVersion", "evaluatedAt", "valid"):
        assert field in payload, f"readback envelope is missing {field!r}"
    assert isinstance(payload["variables"], list) and payload["variables"]
    for record in payload["variables"]:
        assert set(record) >= {"name", "configured", "valid", "sourceClass"}
        assert record["sourceClass"] in {"env", "unset"}
    assert rc == 0, out


def test_readback_never_emits_a_configured_secret_value() -> None:
    """R11: scan the COMPLETE serialized readback, not individual fields."""
    env = dict(SECRET_SENTINELS)
    env.update(
        {
            "FUFIRE_ENV": "production",
            "FUFIRE_REQUIRE_API_KEYS": "true",
            "CORS_ALLOWED_ORIGINS": "https://bazodiac.space",
            "FUFIRE_REPLICA_COUNT": "2",
            "FUFIRE_REQUIRE_REDIS": "true",
            "EPHEMERIS_MODE": "SWIEPH",
        }
    )
    _rc, out = _readback(env)

    leaked = [name for name, value in SECRET_SENTINELS.items() if value in out]
    assert not leaked, f"readback leaked secret values for: {leaked}"

    # Prefix/suffix fingerprints are leaks too, not a safe compromise.
    for name, value in SECRET_SENTINELS.items():
        assert value[:8] not in out, f"readback leaked a prefix of {name}"
        assert value[-8:] not in out, f"readback leaked a suffix of {name}"


def test_readback_reports_configured_secrets_as_present_without_value() -> None:
    env = dict(SECRET_SENTINELS)
    env.update({"FUFIRE_ENV": "dev", "EPHEMERIS_MODE": "SWIEPH"})
    _rc, out = _readback(env)
    payload = json.loads(out)
    by_name = {r["name"]: r for r in payload["variables"]}
    for name in SECRET_SENTINELS:
        if name not in by_name:
            continue
        record = by_name[name]
        assert record["configured"] is True, f"{name} reported as unconfigured"
        assert "value" not in record, f"{name} readback record carries a value field"


def test_readback_exits_non_zero_on_a_fail_closed_violation() -> None:
    """A production profile missing its required variables must not exit 0."""
    rc, out = _readback({"FUFIRE_ENV": "production"})
    payload = json.loads(out)
    assert payload["valid"] is False
    assert payload["violations"], "an invalid profile reported no violations"
    assert rc != 0, "fail-closed contract violation exited 0"


def test_readback_marks_non_secret_safe_values_with_their_value() -> None:
    _rc, out = _readback({"FUFIRE_ENV": "staging", "EPHEMERIS_MODE": "SWIEPH"})
    payload = json.loads(out)
    by_name = {r["name"]: r for r in payload["variables"]}
    assert by_name["FUFIRE_ENV"]["value"] == "staging"
    assert payload["profile"] == "production"


# ── Profile classification: one authoritative definition ─────────────────────
#
# The contract owns the FUFIRE_ENV value set. The startup guard and the readback
# both derive from it, so a deployment can never be production-shaped to one and
# development-shaped to the other.


def test_production_profile_values_are_a_subset_of_the_allowed_set(contract) -> None:
    """A production alias outside allowed_values would be unreachable."""
    from bazi_engine.runtime_contract import (
        allowed_fufire_env_values,
        production_fufire_env_values,
    )

    allowed = allowed_fufire_env_values()
    production = production_fufire_env_values()
    assert production, "the contract declares no production profile values"
    assert allowed, "the contract declares no allowed FUFIRE_ENV values"
    assert production <= allowed, (
        f"production aliases outside allowed_values: {sorted(production - allowed)}"
    )


def test_allowed_values_are_declared_in_normalised_form(contract) -> None:
    """The stored set is already the comparison form — no hidden coercion."""
    from bazi_engine.runtime_contract import normalise_fufire_env

    entry = next(e for e in contract["variables"] if e["name"] == "FUFIRE_ENV")
    for value in entry["allowed_values"]:
        assert value == normalise_fufire_env(value), (
            f"contract declares {value!r}, which is not its own normalised form"
        )


def test_readback_and_startup_classify_every_allowed_value_identically(contract) -> None:
    """R12 extended: the two consumers of the contract cannot disagree."""
    from bazi_engine.runtime_contract import (
        allowed_fufire_env_values,
        classify_runtime_profile,
        resolve_profile,
    )

    for value in sorted(allowed_fufire_env_values()):
        env = {"FUFIRE_ENV": value}
        assert resolve_profile(env) == classify_runtime_profile(env), (
            f"readback and startup disagree about FUFIRE_ENV={value!r}"
        )


def test_readback_flags_an_uncontracted_profile_value() -> None:
    """The typo the startup guard now rejects is also invalid on readback.

    Proven through the packaged CLI in a subprocess, so this is a claim about
    the shipped entry point rather than about a warm in-process call.
    """
    rc, out = _readback({"FUFIRE_ENV": "prodcution"})
    payload = json.loads(out)
    by_name = {r["name"]: r for r in payload["variables"]}

    assert by_name["FUFIRE_ENV"]["valid"] is False
    assert by_name["FUFIRE_ENV"]["issue"] == "invalid_value"
    assert payload["valid"] is False
    assert rc != 0, "readback exited 0 for an uncontracted FUFIRE_ENV value"


def test_readback_accepts_a_contracted_development_value() -> None:
    """Canary for the test above: a declared value must NOT be flagged."""
    _rc, out = _readback({"FUFIRE_ENV": "local", "EPHEMERIS_MODE": "SWIEPH"})
    payload = json.loads(out)
    by_name = {r["name"]: r for r in payload["variables"]}

    assert by_name["FUFIRE_ENV"]["valid"] is True
    assert payload["profile"] == "development"


# ── FUF-159: ONE normalisation for startup AND readback ──────────────────────
#
# ``classify_runtime_profile`` compares FUFIRE_ENV through
# ``normalise_fufire_env`` (strip + case-fold). The generic readback validator
# compared the raw, merely-stripped value against ``allowed_values``, so
# ``FUFIRE_ENV=Production`` was a production deployment to the startup guard and
# an ``invalid_value`` to the readback: two answers derived from one contract
# row, which is the divergence this contract exists to make impossible.
#
# The spellings below are DERIVED from the packaged contract. Restating the
# contracted values here would create a second normative alias list — the defect
# class this slice removes.

# Every row the contract marks ``required_profiles: ["production"]`` except
# FUFIRE_ENV itself, so a production spelling is graded against a COMPLETE
# deployment and the only variable under test is how the profile is spelled.
# Necessarily literal: the contract is secrets-free by construction and carries
# no values to derive these from.
PRODUCTION_COMPLETE_ENV: dict[str, str] = {
    "FUFIRE_REQUIRE_API_KEYS": "true",
    "FUFIRE_API_KEYS": "ff_pro_runtime-contract-agreement",
    "CORS_ALLOWED_ORIGINS": "https://bazodiac.space",
    "FUFIRE_REPLICA_COUNT": "1",
    "EPHEMERIS_MODE": "SWIEPH",
}

UNCONTRACTED_ENV_VALUES = ("prodcution", "stage", "productionn", "foo")


def _contract_allowed_env_values() -> list[str]:
    from bazi_engine.runtime_contract import allowed_fufire_env_values

    return sorted(allowed_fufire_env_values())


def _spellings(value: str) -> tuple[str, ...]:
    """Case/whitespace spellings of ONE value — never a different word.

    The letters are fixed; only their case and the surrounding whitespace move,
    so a spelling can never smuggle in a value the contract does not declare.
    Works for a value declared in either case (``production`` or ``SWIEPH``).
    """
    lower = value.lower()
    alternating = "".join(
        char.upper() if index % 2 == 0 else char for index, char in enumerate(lower)
    )
    candidates = (
        value,
        lower,
        value.upper(),
        lower.capitalize(),
        alternating,
        f" {value} ",
        f" {value.upper()} ",
        f"\t{alternating}\n",
    )
    return tuple(dict.fromkeys(candidates))


def _env_spellings(values: tuple[str, ...] | list[str]) -> list[str]:
    return [spelling for value in values for spelling in _spellings(value)]


def _apply(monkeypatch: pytest.MonkeyPatch, env: dict[str, str]) -> None:
    """Put ``env`` into the real process environment for the startup guard."""
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    from bazi_engine.auth import _load_keys
    from bazi_engine.key_store import get_key_store

    _load_keys.cache_clear()
    get_key_store.cache_clear()


@pytest.fixture
def clean_contract_env(monkeypatch: pytest.MonkeyPatch):
    """Drop every contracted variable so the host env cannot mask a result.

    Derived from the contract itself, so a row added tomorrow is cleared too.
    """
    for name in _contract_variable_names():
        monkeypatch.delenv(name, raising=False)
    from bazi_engine.auth import _load_keys
    from bazi_engine.key_store import get_key_store

    _load_keys.cache_clear()
    get_key_store.cache_clear()
    yield monkeypatch
    _load_keys.cache_clear()
    get_key_store.cache_clear()


def test_a_mixed_case_production_value_agrees_across_startup_and_readback(
    clean_contract_env: pytest.MonkeyPatch,
) -> None:
    """FUF-159 regression: ``FUFIRE_ENV=Production`` had two contradictory answers.

    Startup classified it production and ran the full production policy, while
    the readback marked that very row ``invalid_value`` and exited non-zero.
    All three surfaces are asserted in ONE test because the defect is precisely
    that they disagreed — splitting them would let the mismatch pass again.
    """
    from bazi_engine.config_guard import assert_runtime_config
    from bazi_engine.runtime_contract import (
        PROFILE_PRODUCTION,
        classify_runtime_profile,
    )

    env = dict(PRODUCTION_COMPLETE_ENV, FUFIRE_ENV="Production")

    # 1. startup classification
    assert classify_runtime_profile(env) == PROFILE_PRODUCTION

    # 2. startup validation accepts it and runs the production policy
    _apply(clean_contract_env, env)
    assert_runtime_config()

    # 3. readback, through the packaged CLI in a fresh process
    rc, out = _readback(env)
    payload = json.loads(out)
    record = {r["name"]: r for r in payload["variables"]}["FUFIRE_ENV"]

    assert payload["profile"] == PROFILE_PRODUCTION
    assert record["valid"] is True, f"readback rejected what startup accepted: {record}"
    assert "issue" not in record, record
    assert rc == 0, out


@pytest.mark.parametrize("spelling", _env_spellings(_contract_allowed_env_values()))
def test_startup_and_readback_agree_on_every_contracted_spelling(
    clean_contract_env: pytest.MonkeyPatch, spelling: str
) -> None:
    """Classification, startup validation, readback profile and row validity agree.

    Contract-driven: the base values come from the packaged contract's own
    ``FUFIRE_ENV`` row, so this file never becomes a second place that decides
    which profile names are legal.
    """
    from bazi_engine.config_guard import assert_runtime_config
    from bazi_engine.runtime_contract import PROFILE_INVALID, classify_runtime_profile

    env = dict(PRODUCTION_COMPLETE_ENV, FUFIRE_ENV=spelling)

    classification = classify_runtime_profile(env)
    assert classification != PROFILE_INVALID, (
        f"a contracted value spelled {spelling!r} classified invalid"
    )

    _apply(clean_contract_env, env)
    assert_runtime_config()

    rc, out = _readback(env)
    payload = json.loads(out)
    record = {r["name"]: r for r in payload["variables"]}["FUFIRE_ENV"]

    assert payload["profile"] == classification, (
        f"startup says {classification!r} but readback says {payload['profile']!r} "
        f"for FUFIRE_ENV={spelling!r}"
    )
    assert record["valid"] is True, f"FUFIRE_ENV={spelling!r} readback record: {record}"
    assert payload["valid"] is True, payload["violations"]
    assert rc == 0, out


@pytest.mark.parametrize("spelling", _env_spellings(UNCONTRACTED_ENV_VALUES))
def test_normalisation_never_rescues_an_uncontracted_value_on_readback(
    spelling: str,
) -> None:
    """Trimming and case-folding must not become a way in for a typo.

    The canary for the agreement test above: if normalisation had been widened
    into "accept anything that looks close", these would turn green.
    """
    from bazi_engine.runtime_contract import PROFILE_INVALID, classify_runtime_profile

    env = dict(PRODUCTION_COMPLETE_ENV, FUFIRE_ENV=spelling)
    assert classify_runtime_profile(env) == PROFILE_INVALID

    rc, out = _readback(env)
    payload = json.loads(out)
    record = {r["name"]: r for r in payload["variables"]}["FUFIRE_ENV"]

    assert record["valid"] is False, f"FUFIRE_ENV={spelling!r} accepted on readback"
    assert record["issue"] == "invalid_value"
    assert payload["valid"] is False
    assert rc != 0, out


# ── FUF-159: comparison semantics are declared by the contract, per row ──────
#
# The contract has exactly three ``allowed_values`` rows, and each one's REAL
# consumer compares its variable in a specific form:
#
#   FUFIRE_ENV         classify_runtime_profile    strip + lower
#   KEY_STORE_BACKEND  key_store.get_key_store     strip + lower
#   EPHEMERIS_MODE     config_guard / ephemeris    upper (config_guard also strips)
#
# Until this slice the readback knew only the first of those, through a
# code-side ``if name == FUFIRE_ENV`` branch. ``KEY_STORE_BACKEND=MEMORY`` and
# ``EPHEMERIS_MODE=swieph`` therefore ran fine and still failed their own
# preflight. The comparison form is now the row's machine-readable
# ``value_normalization`` field, and every test below pits a REAL consumer
# against the packaged readback CLI in a fresh process. Base values are derived
# from the packaged contract so this file never becomes a second value list.

UNSUPPORTED_KEY_STORE_BACKENDS = ("postgres", "firestore", "foo")
UNSUPPORTED_EPHEMERIS_MODES = ("JPLEPH", "swiss", "foo")

# Captured at import, before ``clean_contract_env`` clears every contracted
# variable. SE_EPHE_PATH is a contract row, but for the backend tests it is the
# host's SE1 location, not a value under test: CI keeps the files ONLY at
# SE_EPHE_PATH (/tmp/ephe), so clearing it strands SWIEPH construction.
_HOST_SE_EPHE_PATH = os.environ.get("SE_EPHE_PATH")


def _row(name: str) -> dict[str, Any]:
    from bazi_engine.runtime_contract import variable

    entry = variable(name)
    assert entry is not None, f"the packaged contract has no {name} row"
    return entry


def _row_values(name: str, field: str = "allowed_values") -> list[str]:
    return [str(value) for value in _row(name).get(field, [])]


def _row_spellings(name: str, *, padded: bool | None = None) -> list[tuple[str, str]]:
    """``(base, spelling)`` pairs for every contracted value of ``name``.

    ``padded`` selects spellings with (True) or without (False) surrounding
    whitespace; None keeps both.
    """
    pairs = [(base, spelling) for base in _row_values(name) for spelling in _spellings(base)]
    if padded is None:
        return pairs
    return [(base, spelling) for base, spelling in pairs if (spelling != spelling.strip()) is padded]


def _row_record(out: str, name: str) -> tuple[dict[str, Any], dict[str, Any]]:
    payload = json.loads(out)
    return payload, {r["name"]: r for r in payload["variables"]}[name]


def _swieph_marks(base: str) -> tuple[pytest.MarkDecorator, ...]:
    # MOSEPH is the one mode SwissEphBackend constructs without SE1 files; every
    # other accepted mode reaches ensure_ephemeris_files().
    return () if base == "MOSEPH" else (pytest.mark.swieph,)


def _apply_with_host_ephemeris(monkeypatch: pytest.MonkeyPatch, env: dict[str, str]) -> None:
    _apply(monkeypatch, env)
    if _HOST_SE_EPHE_PATH is not None:
        monkeypatch.setenv("SE_EPHE_PATH", _HOST_SE_EPHE_PATH)


# ── TDD regressions: one per mismatched row ──────────────────────────────────

def test_uppercase_key_store_backend_agrees_across_key_store_and_readback(
    clean_contract_env: pytest.MonkeyPatch,
) -> None:
    """FUF-159 regression: ``KEY_STORE_BACKEND=MEMORY`` ran and failed preflight.

    ``get_key_store`` strips and lower-cases the value and returns the in-memory
    backend; the readback compared it case-sensitively and reported
    ``invalid_value`` with a non-zero exit.
    """
    from bazi_engine.key_store import InMemoryKeyStore, get_key_store

    env = {"FUFIRE_ENV": "dev", "KEY_STORE_BACKEND": "MEMORY"}

    # 1. the real consumer accepts it and resolves the memory backend
    _apply(clean_contract_env, env)
    assert isinstance(get_key_store(), InMemoryKeyStore)

    # 2. the packaged readback, in a fresh process
    rc, out = _readback(env)
    payload, record = _row_record(out, "KEY_STORE_BACKEND")
    assert record["valid"] is True, f"readback rejected what the key store accepted: {record}"
    assert "issue" not in record, record
    assert payload["valid"] is True, payload["violations"]
    assert rc == 0, out


def test_lowercase_ephemeris_mode_agrees_across_production_guard_and_readback(
    clean_contract_env: pytest.MonkeyPatch,
) -> None:
    """FUF-159 regression: ``EPHEMERIS_MODE=swieph`` passed startup, failed preflight.

    The production guard upper-cases the value and accepts it as SWIEPH, and the
    transit engine resolves it to SWIEPH; the readback compared it
    case-sensitively and graded a complete production deployment invalid.
    """
    from bazi_engine.config_guard import assert_runtime_config
    from bazi_engine.runtime_contract import PROFILE_PRODUCTION
    from bazi_engine.transit import _effective_ephemeris_mode

    env = dict(PRODUCTION_COMPLETE_ENV, FUFIRE_ENV="production", EPHEMERIS_MODE="swieph")

    # 1. the production guard treats it as SWIEPH (it raises for anything else)
    _apply(clean_contract_env, env)
    assert_runtime_config()
    assert _effective_ephemeris_mode() == "SWIEPH"

    # 2. the packaged readback, in a fresh process
    rc, out = _readback(env)
    payload, record = _row_record(out, "EPHEMERIS_MODE")
    assert payload["profile"] == PROFILE_PRODUCTION
    assert record["valid"] is True, f"readback rejected what the guard accepted: {record}"
    assert "issue" not in record, record
    assert payload["valid"] is True, payload["violations"]
    assert rc == 0, out


# ── KEY_STORE_BACKEND parity matrix ──────────────────────────────────────────

@pytest.mark.parametrize(("base", "spelling"), _row_spellings("KEY_STORE_BACKEND"))
def test_key_store_and_readback_agree_on_every_contracted_spelling(
    clean_contract_env: pytest.MonkeyPatch, base: str, spelling: str
) -> None:
    """Every spelling resolves to its base backend AND is readback-valid.

    The expected backend is whatever ``get_key_store`` returns for the base
    value's own spelling, so this test never restates which backends exist.
    """
    from bazi_engine.key_store import get_key_store

    _apply(clean_contract_env, {"FUFIRE_ENV": "dev", "KEY_STORE_BACKEND": base})
    reference = get_key_store()

    env = {"FUFIRE_ENV": "dev", "KEY_STORE_BACKEND": spelling}
    _apply(clean_contract_env, env)
    store = get_key_store()
    assert type(store) is type(reference), (
        f"KEY_STORE_BACKEND={spelling!r} resolved {type(store).__name__}, "
        f"{base!r} resolves {type(reference).__name__}"
    )

    rc, out = _readback(env)
    payload, record = _row_record(out, "KEY_STORE_BACKEND")
    assert record["valid"] is True, f"KEY_STORE_BACKEND={spelling!r} readback record: {record}"
    assert payload["valid"] is True, payload["violations"]
    assert rc == 0, out


@pytest.mark.parametrize("spelling", _env_spellings(UNSUPPORTED_KEY_STORE_BACKENDS))
def test_normalisation_never_admits_an_unsupported_key_store_backend(
    clean_contract_env: pytest.MonkeyPatch, spelling: str
) -> None:
    """Canary: case-folding must not turn an unsupported backend into a valid one."""
    from bazi_engine.key_store import get_key_store

    env = {"FUFIRE_ENV": "dev", "KEY_STORE_BACKEND": spelling}
    _apply(clean_contract_env, env)
    with pytest.raises(ValueError, match="Unsupported KEY_STORE_BACKEND"):
        get_key_store()

    rc, out = _readback(env)
    payload, record = _row_record(out, "KEY_STORE_BACKEND")
    assert record["valid"] is False, f"KEY_STORE_BACKEND={spelling!r} accepted on readback"
    assert record["issue"] == "invalid_value"
    assert payload["valid"] is False
    assert rc != 0, out


@pytest.mark.parametrize(("base", "spelling"), _row_spellings("KEY_STORE_BACKEND"))
def test_key_store_spelling_satisfies_the_production_key_requirement_consistently(
    clean_contract_env: pytest.MonkeyPatch, base: str, spelling: str
) -> None:
    """``satisfied_by`` reads KEY_STORE_BACKEND in the row's declared form too.

    A production deployment without static keys starts only when a key store is
    configured. The readback's ``FUFIRE_API_KEYS`` requirement must reach the
    same verdict for every spelling — accept for the memory spellings, reject
    for the none spellings.
    """
    from bazi_engine.config_guard import assert_runtime_config
    from bazi_engine.key_store import get_key_store

    env = {k: v for k, v in PRODUCTION_COMPLETE_ENV.items() if k != "FUFIRE_API_KEYS"}
    env.update(FUFIRE_ENV="production")

    _apply(clean_contract_env, dict(env, KEY_STORE_BACKEND=base))
    store_configured = get_key_store() is not None

    env["KEY_STORE_BACKEND"] = spelling
    _apply(clean_contract_env, env)
    try:
        assert_runtime_config()
        started = True
    except RuntimeError:
        started = False
    assert started is store_configured, (
        f"startup verdict for KEY_STORE_BACKEND={spelling!r} differs from {base!r}"
    )

    rc, out = _readback(env)
    payload = json.loads(out)
    assert payload["valid"] is started, (
        f"startup {'accepted' if started else 'rejected'} KEY_STORE_BACKEND={spelling!r} "
        f"but readback violations are {payload['violations']}"
    )
    assert (rc == 0) is started, out


# ── EPHEMERIS_MODE parity matrix ─────────────────────────────────────────────

@pytest.mark.parametrize(("base", "spelling"), _row_spellings("EPHEMERIS_MODE"))
def test_production_guard_and_readback_agree_on_every_ephemeris_spelling(
    clean_contract_env: pytest.MonkeyPatch, base: str, spelling: str
) -> None:
    """Normalisation must not bypass the production-only allowlist.

    Every spelling of a production-allowed mode starts and is readback-valid;
    every spelling of any other contracted mode (MOSEPH) is refused by BOTH the
    startup guard and the readback. The production allowlist is read from the
    contract; the guard it is compared against is the real, independent one.
    """
    from bazi_engine.config_guard import assert_runtime_config

    production_allowed = base in _row_values("EPHEMERIS_MODE", "production_allowed_values")
    env = dict(PRODUCTION_COMPLETE_ENV, FUFIRE_ENV="production", EPHEMERIS_MODE=spelling)

    _apply(clean_contract_env, env)
    if production_allowed:
        assert_runtime_config()
    else:
        with pytest.raises(RuntimeError, match="EPHEMERIS_MODE=SWIEPH only"):
            assert_runtime_config()

    rc, out = _readback(env)
    payload, record = _row_record(out, "EPHEMERIS_MODE")
    assert record["valid"] is production_allowed, (
        f"EPHEMERIS_MODE={spelling!r} in production: guard "
        f"{'accepted' if production_allowed else 'rejected'}, readback record {record}"
    )
    if not production_allowed:
        assert record["issue"] == "invalid_value"
    assert payload["valid"] is production_allowed, payload["violations"]
    assert (rc == 0) is production_allowed, out


@pytest.mark.parametrize(
    ("base", "spelling"),
    [
        pytest.param(base, spelling, marks=_swieph_marks(base))
        for base, spelling in _row_spellings("EPHEMERIS_MODE", padded=False)
    ],
)
def test_ephemeris_backend_and_readback_agree_on_every_case_spelling(
    clean_contract_env: pytest.MonkeyPatch, base: str, spelling: str
) -> None:
    """The calculation backend resolves each case spelling to its base mode.

    Outside production both modes are legal, so the readback must accept every
    case spelling the backend accepts.
    """
    from bazi_engine.ephemeris import SwissEphBackend

    env = {"FUFIRE_ENV": "dev", "EPHEMERIS_MODE": spelling}
    _apply_with_host_ephemeris(clean_contract_env, env)
    assert SwissEphBackend().mode == base

    rc, out = _readback(env)
    payload, record = _row_record(out, "EPHEMERIS_MODE")
    assert record["valid"] is True, f"EPHEMERIS_MODE={spelling!r} readback record: {record}"
    assert payload["valid"] is True, payload["violations"]
    assert rc == 0, out


@pytest.mark.xfail(
    strict=True,
    raises=ValueError,
    reason=(
        "FINDING, pre-existing and outside FUF-159 (ephemeris semantics are frozen "
        "for this slice): SwissEphBackend upper-cases EPHEMERIS_MODE without "
        "stripping it, so a padded value the readback accepts — and, for a "
        "production-allowed mode, the production guard too — raises 'Unsupported "
        "ephemeris mode' at first use (/ready then reports ephemeris unavailable). "
        "strict=True turns this red the moment the backend is fixed, so the marker "
        "cannot outlive the defect."
    ),
)
@pytest.mark.parametrize(("base", "spelling"), _row_spellings("EPHEMERIS_MODE", padded=True))
def test_ephemeris_backend_accepts_the_padded_spellings_guard_and_readback_accept(
    clean_contract_env: pytest.MonkeyPatch, base: str, spelling: str
) -> None:
    """The premise is asserted first, so only the backend step can be the xfail.

    A premise failure raises AssertionError or RuntimeError, which
    ``raises=ValueError`` reports as a real failure instead of the known one.
    """
    from bazi_engine.config_guard import assert_runtime_config
    from bazi_engine.ephemeris import SwissEphBackend

    production = base in _row_values("EPHEMERIS_MODE", "production_allowed_values")
    env = (
        dict(PRODUCTION_COMPLETE_ENV, FUFIRE_ENV="production", EPHEMERIS_MODE=spelling)
        if production
        else {"FUFIRE_ENV": "dev", "EPHEMERIS_MODE": spelling}
    )
    _apply_with_host_ephemeris(clean_contract_env, env)
    if production:
        assert_runtime_config()
    rc, out = _readback(env)
    _payload, record = _row_record(out, "EPHEMERIS_MODE")
    assert record["valid"] is True, record
    assert rc == 0, out

    assert SwissEphBackend().mode == base


@pytest.mark.parametrize("spelling", _env_spellings(UNSUPPORTED_EPHEMERIS_MODES))
def test_normalisation_never_admits_an_unsupported_ephemeris_mode(
    clean_contract_env: pytest.MonkeyPatch, spelling: str
) -> None:
    """Canary: case-folding must not turn an unknown backend into a valid one."""
    from bazi_engine.ephemeris import SwissEphBackend

    env = {"FUFIRE_ENV": "dev", "EPHEMERIS_MODE": spelling}
    _apply(clean_contract_env, env)
    with pytest.raises(ValueError, match="Unsupported ephemeris mode"):
        SwissEphBackend()

    rc, out = _readback(env)
    payload, record = _row_record(out, "EPHEMERIS_MODE")
    assert record["valid"] is False, f"EPHEMERIS_MODE={spelling!r} accepted on readback"
    assert record["issue"] == "invalid_value"
    assert payload["valid"] is False
    assert rc != 0, out


# ── Scope of the declared semantics ──────────────────────────────────────────

def test_every_allowed_value_row_declares_its_comparison_form(contract) -> None:
    """No allowed-value row may rely on the implicit default.

    Whoever adds an allowed-value row must decide how its consumer compares it;
    silently inheriting ``exact`` is how two of the three rows drifted.
    """
    undeclared = [
        e["name"]
        for e in contract["variables"]
        if "allowed_values" in e and "value_normalization" not in e
    ]
    assert not undeclared, f"allowed-value rows without value_normalization: {undeclared}"


def test_value_normalization_is_scoped_to_the_rows_that_declare_it(contract) -> None:
    """The readback is NOT case-insensitive: undeclared rows compare exactly.

    ``value_pattern`` rows and every other row keep exact comparison after the
    existing whitespace trim, so a declared form can never widen them.
    """
    from bazi_engine.runtime_contract import normalise_value

    for entry in contract["variables"]:
        declared = entry.get("value_normalization")
        if declared is None:
            assert normalise_value(entry, " SwIePh ") == "SwIePh", entry["name"]
        else:
            assert "allowed_values" in entry, (
                f"{entry['name']} declares {declared!r} without an allowed-value set"
            )


def test_allowed_values_are_declared_in_their_canonical_form(contract) -> None:
    """Every declared value list is already its own comparison form.

    Covers ``allowed_values``, ``production_allowed_values`` and
    ``production_forbidden_values`` on every row, under that row's declared
    normalisation — no hidden coercion of contract-side values.
    """
    from bazi_engine.runtime_contract import normalise_value

    for entry in contract["variables"]:
        for field in ("allowed_values", "production_allowed_values", "production_forbidden_values"):
            for value in entry.get(field, []):
                assert normalise_value(entry, value) == value, (
                    f"{entry['name']}.{field} declares {value!r}, which is not its own "
                    "normalised form"
                )


def test_production_allowed_values_stay_inside_the_allowed_set(contract) -> None:
    for entry in contract["variables"]:
        if "production_allowed_values" not in entry:
            continue
        outside = set(entry["production_allowed_values"]) - set(entry.get("allowed_values", []))
        assert not outside, f"{entry['name']} production values outside allowed_values: {outside}"


def test_profile_classification_uses_the_contract_declared_form(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``normalise_fufire_env`` reads its form from the FUFIRE_ENV row.

    Proven by swapping the row's declared form: a code-side ``.lower()`` would
    ignore the swap and keep returning lower case.
    """
    from bazi_engine import runtime_contract

    row = dict(_row("FUFIRE_ENV"), value_normalization="upper")
    monkeypatch.setattr(
        runtime_contract, "variable", lambda name: row if name == "FUFIRE_ENV" else None
    )
    assert runtime_contract.normalise_fufire_env(" Prod ") == "PROD"


def test_satisfied_by_reads_the_alternative_in_its_declared_form(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``satisfied_by`` compares the alternative through that row's own form.

    Proven by swapping the KEY_STORE_BACKEND row to ``exact``: the packaged
    ``lower`` form reads ``NONE`` as the null backend, ``exact`` does not. A
    code-side ``.strip().lower()`` would answer the same under both forms.
    """
    from bazi_engine import runtime_contract

    entry = _row("FUFIRE_API_KEYS")
    assert entry["satisfied_by"] == ["KEY_STORE_BACKEND"]
    source = {"KEY_STORE_BACKEND": " NONE "}

    assert runtime_contract._satisfied_by_alternative(entry, source) is False

    exact_row = {k: v for k, v in _row("KEY_STORE_BACKEND").items() if k != "value_normalization"}
    monkeypatch.setattr(
        runtime_contract,
        "variable",
        lambda name: exact_row if name == "KEY_STORE_BACKEND" else None,
    )
    assert runtime_contract._satisfied_by_alternative(entry, source) is True


def test_contract_version_records_the_normalization_semantics(contract) -> None:
    """Adding normative comparison metadata is a minor contract revision."""
    major, minor, _patch = (int(part) for part in contract["contract_version"].split("."))
    assert any("value_normalization" in e for e in contract["variables"])
    assert (major, minor) >= (1, 1), contract["contract_version"]


# ── Contract self-validation: malformed metadata fails closed ────────────────

def _mutated_contract(mutate) -> dict[str, Any]:
    import copy

    document = copy.deepcopy(json.loads(CONTRACT_PATH.read_text(encoding="utf-8")))
    mutate(document)
    return document


def _set_row(document: dict[str, Any], name: str, **fields: Any) -> None:
    next(e for e in document["variables"] if e["name"] == name).update(fields)


def _lowercase_every_row(document: dict[str, Any]) -> None:
    for entry in document["variables"]:
        entry["value_normalization"] = "lower"


def _drop_a_vocabulary_entry_still_in_use(document: dict[str, Any]) -> None:
    # Sets the row explicitly, so the case does not depend on which form the
    # packaged EPHEMERIS_MODE row happens to declare.
    _set_row(document, "EPHEMERIS_MODE", value_normalization="upper")
    document["value_normalizations"].pop("upper")


# case -> (mutation, the rejection message it must produce). Each mutation sets
# every field its rule depends on, so no case can pass by tripping a DIFFERENT
# rule because of whatever the packaged rows happen to declare.
MALFORMED_CONTRACTS = {
    "unknown_row_token": (
        lambda d: _set_row(d, "KEY_STORE_BACKEND", value_normalization="casefold"),
        "KEY_STORE_BACKEND declares unsupported value_normalization 'casefold'",
    ),
    "non_string_row_token": (
        lambda d: _set_row(d, "KEY_STORE_BACKEND", value_normalization=None),
        "KEY_STORE_BACKEND declares unsupported value_normalization None",
    ),
    "vocabulary_missing": (
        lambda d: d.pop("value_normalizations"),
        "must declare a value_normalizations vocabulary",
    ),
    "vocabulary_without_default": (
        lambda d: d["value_normalizations"].pop("exact"),
        "must declare a value_normalizations vocabulary",
    ),
    "vocabulary_names_unimplemented_form": (
        lambda d: d["value_normalizations"].update(title="x"),
        r"does not implement: \['title'\]",
    ),
    "row_token_outside_vocabulary": (
        _drop_a_vocabulary_entry_still_in_use,
        "EPHEMERIS_MODE declares unsupported value_normalization 'upper'",
    ),
    "non_canonical_allowed_value": (
        lambda d: _set_row(
            d, "EPHEMERIS_MODE", value_normalization="upper", allowed_values=["swieph", "MOSEPH"]
        ),
        "allowed_values value 'swieph', which is not canonical under value_normalization 'upper'",
    ),
    "padded_allowed_value": (
        lambda d: _set_row(
            d, "KEY_STORE_BACKEND", value_normalization="lower", allowed_values=[" none", "memory"]
        ),
        "allowed_values value ' none', which is not canonical",
    ),
    "non_canonical_production_allowed_value": (
        lambda d: _set_row(
            d,
            "EPHEMERIS_MODE",
            value_normalization="upper",
            allowed_values=["SWIEPH", "MOSEPH"],
            production_allowed_values=["swieph"],
        ),
        "production_allowed_values value 'swieph', which is not canonical",
    ),
    "production_allowed_outside_allowed": (
        lambda d: _set_row(
            d,
            "EPHEMERIS_MODE",
            allowed_values=["SWIEPH", "MOSEPH"],
            production_allowed_values=["JPLEPH"],
        ),
        r"EPHEMERIS_MODE permits production values outside its allowed_values: \['JPLEPH'\]",
    ),
    "production_allowed_without_allowed": (
        lambda d: _set_row(d, "PORT", production_allowed_values=["8080"]),
        r"PORT permits production values outside its allowed_values: \['8080'\]",
    ),
    "normalization_without_allowed_values": (
        lambda d: _set_row(d, "FUFIRE_REPLICA_COUNT", value_normalization="lower"),
        "FUFIRE_REPLICA_COUNT declares value_normalization 'lower' without an allowed_values set",
    ),
    "every_row_lowercased": (
        _lowercase_every_row,
        "declares value_normalization 'lower' without an allowed_values set",
    ),
    "string_value_list": (
        lambda d: _set_row(d, "KEY_STORE_BACKEND", allowed_values="nonememory"),
        "KEY_STORE_BACKEND declares allowed_values as str, not a list",
    ),
    "null_value_list": (
        lambda d: _set_row(d, "EPHEMERIS_MODE", production_allowed_values=None),
        "EPHEMERIS_MODE declares production_allowed_values as NoneType, not a list",
    ),
    "nameless_row": (
        lambda d: d["variables"].append({"owner_area": "x"}),
        "must declare variables as a list of rows that each carry a string name",
    ),
    "non_object_row": (
        lambda d: d["variables"].append("KEY_STORE_BACKEND"),
        "must declare variables as a list of rows that each carry a string name",
    ),
    "satisfied_by_names_no_row": (
        lambda d: _set_row(d, "FUFIRE_API_KEYS", satisfied_by=["KEY_STORE_BACKND"]),
        r"FUFIRE_API_KEYS is satisfied_by \['KEY_STORE_BACKND'\], which does not name",
    ),
    "production_profile_value_not_canonical": (
        lambda d: d["profiles"]["production"].update(fufire_env_values=["Production"]),
        r"production profile values \['Production'\] are not FUFIRE_ENV allowed values",
    ),
    "production_profile_value_outside_allowed": (
        lambda d: d["profiles"]["production"].update(fufire_env_values=["live"]),
        r"production profile values \['live'\] are not FUFIRE_ENV allowed values",
    ),
    # An empty or non-list alias set would classify FUFIRE_ENV=production as
    # development and skip every production check.
    "production_profile_values_empty": (
        lambda d: d["profiles"]["production"].update(fufire_env_values=[]),
        "production profile must list at least one FUFIRE_ENV value",
    ),
    "production_profile_values_not_a_list": (
        lambda d: d["profiles"]["production"].update(fufire_env_values="production"),
        "production profile must list at least one FUFIRE_ENV value",
    ),
}


def test_the_packaged_contract_passes_its_own_validation() -> None:
    """Canary for the malformed cases below: the real contract is accepted."""
    from bazi_engine.runtime_contract import validate_contract

    validate_contract(_mutated_contract(lambda d: None))


@pytest.mark.parametrize("case", sorted(MALFORMED_CONTRACTS))
def test_malformed_normalization_metadata_is_rejected(case: str) -> None:
    from bazi_engine.runtime_contract import validate_contract

    mutate, message = MALFORMED_CONTRACTS[case]
    with pytest.raises(RuntimeError, match=f"^runtime contract .*{message}"):
        validate_contract(_mutated_contract(mutate))


@pytest.mark.parametrize(
    "case",
    [
        "unknown_row_token",
        "vocabulary_missing",
        "every_row_lowercased",
        "production_profile_values_empty",
    ],
)
def test_load_contract_fails_closed_on_malformed_metadata(
    monkeypatch: pytest.MonkeyPatch, case: str
) -> None:
    """The validation sits on the LOAD path, not only in a helper tests call.

    ``load_contract`` backs the startup guard and the readback, so a malformed
    contract aborts both instead of loading with a silently-defaulted form.
    """
    from bazi_engine import runtime_contract

    mutate, message = MALFORMED_CONTRACTS[case]
    document = _mutated_contract(mutate)
    monkeypatch.setattr(
        runtime_contract, "load_json_object_resource", lambda package, resource: document
    )
    runtime_contract.load_contract.cache_clear()
    try:
        with pytest.raises(RuntimeError, match=f"^runtime contract .*{message}"):
            runtime_contract.load_contract()
    finally:
        runtime_contract.load_contract.cache_clear()


def test_normalise_value_refuses_an_unsupported_form_at_use() -> None:
    """Second line of defence for a row that bypassed load-time validation."""
    from bazi_engine.runtime_contract import normalise_value

    with pytest.raises(RuntimeError, match="value_normalization"):
        normalise_value({"name": "X", "value_normalization": "casefold"}, "value")


# ── FUF-159: presence semantics are declared by the contract, per row ───────
#
# The readback used ONE notion of "configured" for every row: a value that is
# non-blank after trimming. Three consumers read presence differently, and each
# difference let the readback go green on a deployment the real startup refuses:
#
#   R1  FUFIRE_ENV       required whenever FUFIRE_REQUIRE_EXPLICIT_ENV is truthy,
#                        in EVERY profile — the readback only knew "required in
#                        production", so an unset profile was a valid development
#                        deployment to the readback and a startup abort to the guard.
#   R2  FUFIRE_API_KEYS  auth._load_keys splits on commas and drops blank items, so
#                        "," is ZERO keys and production refuses to start; the
#                        readback saw a non-blank string and called it configured.
#   R3  EPHEMERIS_MODE   the production guard's SWIEPH default applies only when the
#                        variable is ABSENT; a set-but-blank value reaches the guard
#                        as "" and is refused. The readback read blank as unset.
#
# The same measurement (a differential sweep of startup against readback) found
# two more rows in this exact class, fixed with the same vocabulary:
#
#   FUFIRE_ZWDS_SIGNOFF_ID  required in production whenever FUFIRE_ENABLE_ZWDS is truthy
#   CORS_ALLOWED_ORIGINS    parsed as a comma list; "," is an empty allowlist
#
# Every test below pits the REAL consumer against the packaged readback CLI in a
# fresh process, and asserts the consumer's verdict FIRST: agreement in the
# wrong direction (both accepting a broken deployment) cannot pass.


def _startup_verdict(monkeypatch: pytest.MonkeyPatch, env: dict[str, str]) -> tuple[bool, str]:
    """Run the real startup guard against ``env``. Returns (started, reason)."""
    from bazi_engine.config_guard import assert_runtime_config

    _apply(monkeypatch, env)
    try:
        assert_runtime_config()
    except RuntimeError as exc:
        return False, str(exc)
    return True, ""


def _assert_readback_agrees(started: bool, reason: str, env: dict[str, str]) -> dict[str, Any]:
    rc, out = _readback(env)
    payload = json.loads(out)
    assert payload["valid"] is started, (
        f"startup {'accepted' if started else f'refused ({reason})'} this deployment but "
        f"the readback reports valid={payload['valid']} with violations {payload['violations']}"
    )
    assert (rc == 0) is started, out
    return payload


def _record(payload: dict[str, Any], name: str) -> dict[str, Any]:
    return {r["name"]: r for r in payload["variables"]}[name]


def _production(**overrides: str | None) -> dict[str, str]:
    """A complete production deployment; ``None`` removes a variable."""
    env = dict(PRODUCTION_COMPLETE_ENV, FUFIRE_ENV="production")
    for name, value in overrides.items():
        if value is None:
            env.pop(name, None)
        else:
            env[name] = value
    return env


TRUTHY_FLAG_SPELLINGS = ("1", "true", "TRUE", " yes ", "on")
FALSY_FLAG_SPELLINGS = (None, "", "  ", "0", "false", "off")
ABSENT_OR_BLANK = (None, "", "   ")


# ── R1 — explicit environment requirement ────────────────────────────────────

def test_explicit_env_requirement_agrees_across_startup_and_readback(
    clean_contract_env: pytest.MonkeyPatch,
) -> None:
    """R1 (FUF-159): FUFIRE_REQUIRE_EXPLICIT_ENV=true without FUFIRE_ENV.

    Every container image bakes the flag, so this is exactly the deployment
    that forgot to declare its profile. Startup refuses it; the readback must.
    """
    env = {"FUFIRE_REQUIRE_EXPLICIT_ENV": "true"}

    started, reason = _startup_verdict(clean_contract_env, env)
    assert started is False
    assert "FUFIRE_ENV must be set explicitly" in reason

    payload = _assert_readback_agrees(started, reason, env)
    record = _record(payload, "FUFIRE_ENV")
    assert record["valid"] is False, record
    assert record["issue"] == "missing_required", record
    assert record["requiredHere"] is True, record


@pytest.mark.parametrize("profile", ABSENT_OR_BLANK)
@pytest.mark.parametrize("flag", TRUTHY_FLAG_SPELLINGS)
def test_every_truthy_explicit_env_flag_requires_a_declared_profile(
    clean_contract_env: pytest.MonkeyPatch, flag: str, profile: str | None
) -> None:
    env = {"FUFIRE_REQUIRE_EXPLICIT_ENV": flag}
    if profile is not None:
        env["FUFIRE_ENV"] = profile

    started, reason = _startup_verdict(clean_contract_env, env)
    assert started is False, f"flag={flag!r} profile={profile!r} started"

    payload = _assert_readback_agrees(started, reason, env)
    assert _record(payload, "FUFIRE_ENV")["issue"] == "missing_required"


@pytest.mark.parametrize("flag", FALSY_FLAG_SPELLINGS)
def test_local_development_without_the_explicit_env_flag_stays_valid(
    clean_contract_env: pytest.MonkeyPatch, flag: str | None
) -> None:
    """Canary: the permissive local case must not become a violation."""
    env = {} if flag is None else {"FUFIRE_REQUIRE_EXPLICIT_ENV": flag}

    started, reason = _startup_verdict(clean_contract_env, env)
    assert started is True, reason

    payload = _assert_readback_agrees(started, reason, env)
    record = _record(payload, "FUFIRE_ENV")
    assert record["valid"] is True, record
    assert record["requiredHere"] is False, record


@pytest.mark.parametrize(
    "env",
    [
        pytest.param({"FUFIRE_REQUIRE_EXPLICIT_ENV": "true", "FUFIRE_ENV": "dev"}, id="dev"),
        pytest.param(
            {"FUFIRE_REQUIRE_EXPLICIT_ENV": "true", "FUFIRE_ENV": "Local"}, id="local-mixed-case"
        ),
        pytest.param(dict(_production(), FUFIRE_REQUIRE_EXPLICIT_ENV="1"), id="production"),
    ],
)
def test_an_explicitly_declared_profile_satisfies_the_explicit_env_flag(
    clean_contract_env: pytest.MonkeyPatch, env: dict[str, str]
) -> None:
    started, reason = _startup_verdict(clean_contract_env, env)
    assert started is True, reason
    _assert_readback_agrees(started, reason, env)


def test_explicit_env_flag_does_not_rescue_an_uncontracted_profile(
    clean_contract_env: pytest.MonkeyPatch,
) -> None:
    """Present is not enough: the declared profile must also be a contracted one."""
    env = {"FUFIRE_REQUIRE_EXPLICIT_ENV": "true", "FUFIRE_ENV": "prodcution"}

    started, reason = _startup_verdict(clean_contract_env, env)
    assert started is False

    payload = _assert_readback_agrees(started, reason, env)
    assert _record(payload, "FUFIRE_ENV")["issue"] == "invalid_value"


# ── R2 — semantically empty API-key lists ────────────────────────────────────

SEMANTICALLY_EMPTY_KEY_LISTS = ("", " ", ",", ",,", " , , ")
CONFIGURED_KEY_LISTS = ("ff_free_abc", "ff_free_abc,", ",ff_free_abc", "ff_free_abc,ff_pro_xyz")


def test_comma_only_api_keys_agree_across_auth_loader_startup_and_readback(
    clean_contract_env: pytest.MonkeyPatch,
) -> None:
    """R2 (FUF-159): FUFIRE_API_KEYS="," is zero keys to the auth loader."""
    from bazi_engine.auth import _load_keys

    env = _production(FUFIRE_API_KEYS=",", KEY_STORE_BACKEND="none")

    started, reason = _startup_verdict(clean_contract_env, env)
    assert _load_keys() == frozenset()
    assert started is False
    assert "auth disabled" in reason

    payload = _assert_readback_agrees(started, reason, env)
    record = _record(payload, "FUFIRE_API_KEYS")
    assert record["configured"] is False, record
    assert record["issue"] == "missing_required", record


@pytest.mark.parametrize("keys", SEMANTICALLY_EMPTY_KEY_LISTS)
def test_no_semantically_empty_key_list_satisfies_production(
    clean_contract_env: pytest.MonkeyPatch, keys: str
) -> None:
    from bazi_engine.auth import _load_keys

    env = _production(FUFIRE_API_KEYS=keys, KEY_STORE_BACKEND="none")

    started, reason = _startup_verdict(clean_contract_env, env)
    assert _load_keys() == frozenset(), f"FUFIRE_API_KEYS={keys!r} loaded keys"
    assert started is False

    payload = _assert_readback_agrees(started, reason, env)
    record = _record(payload, "FUFIRE_API_KEYS")
    assert record["configured"] is False, record
    assert record["issue"] == "missing_required", record


@pytest.mark.parametrize("keys", CONFIGURED_KEY_LISTS)
def test_a_real_key_list_satisfies_production_without_being_echoed(
    clean_contract_env: pytest.MonkeyPatch, keys: str
) -> None:
    from bazi_engine.auth import _load_keys

    env = _production(FUFIRE_API_KEYS=keys, KEY_STORE_BACKEND="none")

    started, reason = _startup_verdict(clean_contract_env, env)
    assert _load_keys(), f"FUFIRE_API_KEYS={keys!r} loaded no keys"
    assert started is True, reason

    payload = _assert_readback_agrees(started, reason, env)
    record = _record(payload, "FUFIRE_API_KEYS")
    assert record["configured"] is True, record
    assert "value" not in record, record
    serialized = json.dumps(payload)
    for key in (k.strip() for k in keys.split(",") if k.strip()):
        assert key not in serialized, "the readback echoed a configured API key"


@pytest.mark.parametrize("keys", (None, *SEMANTICALLY_EMPTY_KEY_LISTS))
def test_a_configured_key_store_still_satisfies_production(
    clean_contract_env: pytest.MonkeyPatch, keys: str | None
) -> None:
    """The KeyStore alternative is unchanged by the key-list presence rule."""
    env = _production(FUFIRE_API_KEYS=keys, KEY_STORE_BACKEND="memory")

    started, reason = _startup_verdict(clean_contract_env, env)
    assert started is True, reason
    _assert_readback_agrees(started, reason, env)


# ── R3 — blank ephemeris mode ────────────────────────────────────────────────

BLANK_SPELLINGS = ("", " ", "\t")


def test_blank_ephemeris_mode_agrees_across_production_guard_and_readback(
    clean_contract_env: pytest.MonkeyPatch,
) -> None:
    """R3 (FUF-159): the guard's SWIEPH default applies to an ABSENT value only."""
    env = _production(EPHEMERIS_MODE="")

    started, reason = _startup_verdict(clean_contract_env, env)
    assert started is False
    assert "EPHEMERIS_MODE=SWIEPH only" in reason

    payload = _assert_readback_agrees(started, reason, env)
    record = _record(payload, "EPHEMERIS_MODE")
    assert record["valid"] is False, record
    assert record["issue"] == "blank_value", record


@pytest.mark.parametrize("blank", BLANK_SPELLINGS)
def test_every_blank_ephemeris_spelling_is_refused_in_production(
    clean_contract_env: pytest.MonkeyPatch, blank: str
) -> None:
    env = _production(EPHEMERIS_MODE=blank)

    started, reason = _startup_verdict(clean_contract_env, env)
    assert started is False, f"EPHEMERIS_MODE={blank!r} started in production"

    payload = _assert_readback_agrees(started, reason, env)
    assert _record(payload, "EPHEMERIS_MODE")["issue"] == "blank_value"


def test_unset_ephemeris_mode_follows_the_production_default(
    clean_contract_env: pytest.MonkeyPatch,
) -> None:
    """Canary: ABSENT keeps the guard's SWIEPH default — valid to both."""
    env = _production(EPHEMERIS_MODE=None)

    started, reason = _startup_verdict(clean_contract_env, env)
    assert started is True, reason

    payload = _assert_readback_agrees(started, reason, env)
    assert _record(payload, "EPHEMERIS_MODE")["valid"] is True


def test_blank_ephemeris_mode_outside_production_keeps_its_current_verdict(
    clean_contract_env: pytest.MonkeyPatch,
) -> None:
    """The blank rule is production-scoped because the refusing consumer is.

    Outside production no startup check reads EPHEMERIS_MODE, so the readback
    must not invent one.
    """
    env = {"FUFIRE_ENV": "dev", "EPHEMERIS_MODE": ""}

    started, reason = _startup_verdict(clean_contract_env, env)
    assert started is True, reason
    _assert_readback_agrees(started, reason, env)


@pytest.mark.swieph
def test_the_backend_reads_an_empty_ephemeris_mode_as_its_default(
    clean_contract_env: pytest.MonkeyPatch,
) -> None:
    """Evidence for the scope above: the calculation backend accepts ``""``."""
    from bazi_engine.ephemeris import SwissEphBackend

    _apply_with_host_ephemeris(clean_contract_env, {"FUFIRE_ENV": "dev", "EPHEMERIS_MODE": ""})
    assert SwissEphBackend().mode == "SWIEPH"


@pytest.mark.xfail(
    strict=True,
    raises=ValueError,
    reason=(
        "FINDING, same root cause as the padded-spelling xfail above and outside this "
        "slice (ephemeris.py is frozen): outside production a whitespace-only "
        "EPHEMERIS_MODE is valid to startup and readback alike — no startup check reads "
        "it there — but SwissEphBackend does not strip it and raises 'Unsupported "
        "ephemeris mode' at first use. strict=True turns this red once the backend strips."
    ),
)
@pytest.mark.swieph
@pytest.mark.parametrize("blank", [b for b in BLANK_SPELLINGS if b])
def test_the_backend_reads_a_whitespace_only_ephemeris_mode_as_its_default(
    clean_contract_env: pytest.MonkeyPatch, blank: str
) -> None:
    """The premise is asserted first, so only the backend step can be the xfail."""
    from bazi_engine.ephemeris import SwissEphBackend

    env = {"FUFIRE_ENV": "dev", "EPHEMERIS_MODE": blank}
    started, reason = _startup_verdict(clean_contract_env, env)
    assert started is True, reason
    _assert_readback_agrees(started, reason, env)

    _apply_with_host_ephemeris(clean_contract_env, env)
    assert SwissEphBackend().mode == "SWIEPH"


# ── Same class, found by the sweep: ZWDS sign-off and the CORS allowlist ─────

@pytest.mark.parametrize("signoff", ABSENT_OR_BLANK)
@pytest.mark.parametrize("flag", TRUTHY_FLAG_SPELLINGS)
def test_production_zwds_without_a_sign_off_agrees_across_startup_and_readback(
    clean_contract_env: pytest.MonkeyPatch, flag: str, signoff: str | None
) -> None:
    env = _production(FUFIRE_ENABLE_ZWDS=flag, FUFIRE_ZWDS_SIGNOFF_ID=signoff)

    started, reason = _startup_verdict(clean_contract_env, env)
    assert started is False
    assert "FUFIRE_ZWDS_SIGNOFF_ID" in reason

    payload = _assert_readback_agrees(started, reason, env)
    record = _record(payload, "FUFIRE_ZWDS_SIGNOFF_ID")
    assert record["issue"] == "missing_required", record
    assert record["requiredHere"] is True, record


@pytest.mark.parametrize(
    ("env", "required_here"),
    [
        pytest.param(
            _production(FUFIRE_ENABLE_ZWDS="true", FUFIRE_ZWDS_SIGNOFF_ID="REL-42"),
            True,
            id="production-signed-off",
        ),
        pytest.param(_production(FUFIRE_ENABLE_ZWDS="false"), False, id="production-disabled"),
        pytest.param({"FUFIRE_ENV": "dev", "FUFIRE_ENABLE_ZWDS": "true"}, False, id="dev-unsigned"),
    ],
)
def test_zwds_sign_off_rule_stays_scoped_to_enabled_production(
    clean_contract_env: pytest.MonkeyPatch, env: dict[str, str], required_here: bool
) -> None:
    started, reason = _startup_verdict(clean_contract_env, env)
    assert started is True, reason
    payload = _assert_readback_agrees(started, reason, env)
    assert _record(payload, "FUFIRE_ZWDS_SIGNOFF_ID")["requiredHere"] is required_here


@pytest.mark.parametrize("origins", (",", ",,", " , , "))
def test_comma_only_cors_allowlist_agrees_across_startup_and_readback(
    clean_contract_env: pytest.MonkeyPatch, origins: str
) -> None:
    env = _production(CORS_ALLOWED_ORIGINS=origins)

    started, reason = _startup_verdict(clean_contract_env, env)
    assert started is False
    assert "explicit CORS_ALLOWED_ORIGINS allowlist" in reason

    payload = _assert_readback_agrees(started, reason, env)
    record = _record(payload, "CORS_ALLOWED_ORIGINS")
    assert record["configured"] is False, record
    assert record["issue"] == "missing_required", record


@pytest.mark.parametrize("origins", ("https://bazodiac.space,", ",https://bazodiac.space"))
def test_a_cors_allowlist_with_stray_commas_stays_valid(
    clean_contract_env: pytest.MonkeyPatch, origins: str
) -> None:
    env = _production(CORS_ALLOWED_ORIGINS=origins)

    started, reason = _startup_verdict(clean_contract_env, env)
    assert started is True, reason
    _assert_readback_agrees(started, reason, env)


# ── The verdicts follow the contract metadata, not variable names ────────────
#
# In-process, against a contract document swapped in on the load path. Removing
# a row's metadata must flip the verdict back (so the packaged verdict comes
# from the metadata), and moving it onto an unrelated row must move the rule
# with it (so the evaluator implements a vocabulary, not a name map).


@pytest.fixture
def contract_document(monkeypatch: pytest.MonkeyPatch):
    """Yield a function that swaps a mutated contract onto the load path."""
    from bazi_engine import runtime_contract

    def install(mutate) -> None:
        document = _mutated_contract(mutate)
        monkeypatch.setattr(
            runtime_contract, "load_json_object_resource", lambda package, resource: document
        )
        runtime_contract.load_contract.cache_clear()

    yield install
    runtime_contract.load_contract.cache_clear()


def _drop_field(name: str, field: str):
    def mutate(document: dict[str, Any]) -> None:
        next(e for e in document["variables"] if e["name"] == name).pop(field)

    return mutate


def _evaluate(env: dict[str, str]) -> dict[str, Any]:
    from bazi_engine.runtime_contract import evaluate

    return evaluate(env)


PRESENCE_METADATA_CASES = {
    # case: (row, field, env the packaged contract refuses)
    "explicit_env": (
        "FUFIRE_ENV",
        "required_when_truthy",
        {"FUFIRE_REQUIRE_EXPLICIT_ENV": "true"},
    ),
    "api_key_list": (
        "FUFIRE_API_KEYS",
        "presence_semantics",
        _production(FUFIRE_API_KEYS=",", KEY_STORE_BACKEND="none"),
    ),
    "blank_ephemeris": (
        "EPHEMERIS_MODE",
        "production_blank_policy",
        _production(EPHEMERIS_MODE=""),
    ),
    "zwds_sign_off": (
        "FUFIRE_ZWDS_SIGNOFF_ID",
        "production_required_when_truthy",
        _production(FUFIRE_ENABLE_ZWDS="true"),
    ),
    "cors_list": (
        "CORS_ALLOWED_ORIGINS",
        "presence_semantics",
        _production(CORS_ALLOWED_ORIGINS=","),
    ),
}


@pytest.mark.parametrize("case", sorted(PRESENCE_METADATA_CASES))
def test_the_verdict_comes_from_the_row_metadata(contract_document, case: str) -> None:
    row, field, env = PRESENCE_METADATA_CASES[case]

    violations = _evaluate(env)["violations"]
    assert [v["variable"] for v in violations] == [row], violations

    contract_document(_drop_field(row, field))
    assert _evaluate(env)["valid"] is True, (
        f"removing {row}.{field} did not change the verdict — the rule is not "
        "carried by the contract"
    )


def test_list_presence_moves_with_the_metadata(contract_document) -> None:
    """``presence_semantics`` on an unrelated required row governs that row."""
    env = {"FUFIRE_ENV": "production", "FUFIRE_REPLICA_COUNT": ","}
    assert "FUFIRE_REPLICA_COUNT" in {
        v["variable"] for v in _evaluate(env)["violations"] if v["code"] == "invalid_value"
    }

    def mutate(document: dict[str, Any]) -> None:
        row = next(e for e in document["variables"] if e["name"] == "FUFIRE_REPLICA_COUNT")
        row.pop("value_pattern")
        row["presence_semantics"] = "comma_separated_non_empty_items"

    contract_document(mutate)
    codes = {(v["variable"], v["code"]) for v in _evaluate(env)["violations"]}
    assert ("FUFIRE_REPLICA_COUNT", "missing_required") in codes, codes


def test_blank_policy_moves_with_the_metadata(contract_document) -> None:
    env = {"FUFIRE_ENV": "production", "PORT": ""}
    assert "PORT" not in {v["variable"] for v in _evaluate(env)["violations"]}

    contract_document(lambda d: _set_row(d, "PORT", production_blank_policy="invalid"))
    codes = {(v["variable"], v["code"]) for v in _evaluate(env)["violations"]}
    assert ("PORT", "blank_value") in codes, codes

    # ...and it stays production-scoped wherever it is declared.
    assert "PORT" not in {
        v["variable"] for v in _evaluate({"FUFIRE_ENV": "dev", "PORT": ""})["violations"]
    }


# field -> {profile env: required while the flag is truthy?}
CONDITIONAL_FIELD_SCOPES = {
    "required_when_truthy": {"dev": True, "production": True},
    "production_required_when_truthy": {"dev": False, "production": True},
}


@pytest.mark.parametrize("field", sorted(CONDITIONAL_FIELD_SCOPES))
def test_conditional_requirement_moves_with_the_metadata(contract_document, field: str) -> None:
    """Each conditional field, moved onto an unrelated row and flag, carries its
    rule and its profile scope with it — a hard-coded flag name cannot pass."""
    bases = {"dev": {"FUFIRE_ENV": "dev"}, "production": _production()}
    for base in bases.values():
        assert _evaluate(dict(base, WEBHOOK_HMAC_ONLY="true"))["valid"] is True

    contract_document(
        lambda d: _set_row(d, "ELEVENLABS_TOOL_SECRET", **{field: "WEBHOOK_HMAC_ONLY"})
    )
    for profile, required in CONDITIONAL_FIELD_SCOPES[field].items():
        payload = _evaluate(dict(bases[profile], WEBHOOK_HMAC_ONLY="true"))
        codes = {(v["variable"], v["code"]) for v in payload["violations"]}
        expected = {("ELEVENLABS_TOOL_SECRET", "missing_required")} if required else set()
        assert codes == expected, f"{field} in {profile}: {codes}"
        assert _record(payload, "ELEVENLABS_TOOL_SECRET")["requiredHere"] is required
        # A falsy flag never requires the row, in any profile.
        falsy = _evaluate(dict(bases[profile], WEBHOOK_HMAC_ONLY="false"))
        assert falsy["valid"] is True, f"{field} in {profile}: {falsy['violations']}"


def test_contract_version_records_the_presence_semantics(contract) -> None:
    """Adding normative presence metadata is another minor contract revision."""
    major, minor, _patch = (int(part) for part in contract["contract_version"].split("."))
    assert any("presence_semantics" in e for e in contract["variables"])
    assert (major, minor) >= (1, 2), contract["contract_version"]


# ── Contract self-validation for the presence vocabulary ─────────────────────

MALFORMED_PRESENCE_CONTRACTS = {
    "presence_vocabulary_missing": (
        lambda d: d.pop("presence_semantics"),
        "must declare a presence_semantics vocabulary",
    ),
    "presence_vocabulary_without_default": (
        lambda d: d["presence_semantics"].pop("non_blank"),
        "must declare a presence_semantics vocabulary",
    ),
    "presence_vocabulary_names_unimplemented_form": (
        lambda d: d["presence_semantics"].update(json_array="x"),
        r"presence semantics this engine does not implement: \['json_array'\]",
    ),
    "unknown_presence_token": (
        lambda d: _set_row(d, "FUFIRE_API_KEYS", presence_semantics="semicolon_list"),
        "FUFIRE_API_KEYS declares unsupported presence_semantics 'semicolon_list'",
    ),
    "non_string_presence_token": (
        lambda d: _set_row(d, "FUFIRE_API_KEYS", presence_semantics=["comma"]),
        r"FUFIRE_API_KEYS declares unsupported presence_semantics \['comma'\]",
    ),
    "list_presence_on_a_closed_value_set": (
        lambda d: _set_row(d, "KEY_STORE_BACKEND", presence_semantics="comma_separated_non_empty_items"),
        "KEY_STORE_BACKEND reads its value as a list but also declares allowed_values",
    ),
    "list_presence_on_a_value_pattern": (
        lambda d: _set_row(d, "PORT", presence_semantics="comma_separated_non_empty_items"),
        "PORT reads its value as a list but also declares value_pattern",
    ),
    "list_presence_on_a_flag": (
        lambda d: _set_row(
            d, "FUFIRE_REQUIRE_API_KEYS", presence_semantics="comma_separated_non_empty_items"
        ),
        "FUFIRE_REQUIRE_API_KEYS reads its value as a list but also declares production_required_truthy",
    ),
    "list_presence_on_a_forbidden_flag": (
        lambda d: _set_row(
            d, "FUFIRE_ENABLE_KEY_ISSUANCE", presence_semantics="comma_separated_non_empty_items"
        ),
        "FUFIRE_ENABLE_KEY_ISSUANCE reads its value as a list but also declares production_forbidden_truthy",
    ),
    # Reachable without allowed_values: an empty production list passes the
    # subset rule, so only the clash rule can refuse it.
    "list_presence_on_a_production_allowlist": (
        lambda d: _set_row(
            d,
            "BUILD_VERSION",
            presence_semantics="comma_separated_non_empty_items",
            production_allowed_values=[],
        ),
        "BUILD_VERSION reads its value as a list but also declares production_allowed_values",
    ),
    "blank_vocabulary_missing": (
        lambda d: d.pop("blank_policies"),
        "must declare a blank_policies vocabulary",
    ),
    "blank_vocabulary_without_default": (
        lambda d: d["blank_policies"].pop("unset"),
        "must declare a blank_policies vocabulary",
    ),
    "blank_vocabulary_names_unimplemented_policy": (
        lambda d: d["blank_policies"].update(warn="x"),
        r"blank policies this engine does not implement: \['warn'\]",
    ),
    "unknown_blank_policy": (
        lambda d: _set_row(d, "EPHEMERIS_MODE", production_blank_policy="reject"),
        "EPHEMERIS_MODE declares unsupported production_blank_policy 'reject'",
    ),
    "non_string_blank_policy": (
        lambda d: _set_row(d, "EPHEMERIS_MODE", production_blank_policy=True),
        "EPHEMERIS_MODE declares unsupported production_blank_policy True",
    ),
    "conditional_requirement_names_no_row": (
        lambda d: _set_row(d, "FUFIRE_ENV", required_when_truthy="FUFIRE_REQUIRE_EXPLICT_ENV"),
        "FUFIRE_ENV is required_when_truthy 'FUFIRE_REQUIRE_EXPLICT_ENV', which does not name another contract row",
    ),
    "production_conditional_requirement_names_no_row": (
        lambda d: _set_row(
            d, "FUFIRE_ZWDS_SIGNOFF_ID", production_required_when_truthy="FUFIRE_ENABLE_ZWD"
        ),
        "FUFIRE_ZWDS_SIGNOFF_ID is production_required_when_truthy 'FUFIRE_ENABLE_ZWD', which does not name",
    ),
    "conditional_requirement_as_a_list": (
        lambda d: _set_row(d, "FUFIRE_ENV", required_when_truthy=["FUFIRE_REQUIRE_EXPLICIT_ENV"]),
        r"FUFIRE_ENV is required_when_truthy \['FUFIRE_REQUIRE_EXPLICIT_ENV'\], which does not name",
    ),
    "conditional_requirement_as_null": (
        lambda d: _set_row(d, "FUFIRE_ENV", required_when_truthy=None),
        "FUFIRE_ENV is required_when_truthy None, which does not name",
    ),
    "conditional_requirement_as_empty_string": (
        lambda d: _set_row(d, "FUFIRE_ENV", required_when_truthy=""),
        "FUFIRE_ENV is required_when_truthy '', which does not name",
    ),
    "conditional_requirement_on_itself": (
        lambda d: _set_row(d, "FUFIRE_ENV", required_when_truthy="FUFIRE_ENV"),
        "FUFIRE_ENV is required_when_truthy 'FUFIRE_ENV', which does not name another contract row",
    ),
    # A scalar secret, so the secret rule is exercised on its own and not via
    # the list-row rule (FUFIRE_API_KEYS would trip both).
    "conditional_requirement_on_a_secret": (
        lambda d: _set_row(d, "ELEVENLABS_TOOL_SECRET", required_when_truthy="FUFIRE_ADMIN_TOKEN"),
        "ELEVENLABS_TOOL_SECRET is required_when_truthy 'FUFIRE_ADMIN_TOKEN', a secret row",
    ),
    # The referencing row comes BEFORE its flag row, whose own token is malformed:
    # the flag row's error must surface, not a TypeError from the cross-row check.
    "conditional_requirement_on_a_row_with_a_malformed_token": (
        lambda d: (
            _set_row(d, "FUFIRE_ENV", required_when_truthy="FUFIRE_ENABLE_ZWDS"),
            _set_row(d, "FUFIRE_ENABLE_ZWDS", presence_semantics=["list"]),
        ),
        r"FUFIRE_ENABLE_ZWDS declares unsupported presence_semantics \['list'\]",
    ),
    "duplicate_row_name": (
        lambda d: d["variables"].append(
            dict(next(e for e in d["variables"] if e["name"] == "KEY_STORE_BACKEND"))
        ),
        r"declares duplicate variable rows \['KEY_STORE_BACKEND'\]",
    ),
    "conditional_requirement_on_a_list_row": (
        lambda d: _set_row(d, "FUFIRE_ZWDS_SIGNOFF_ID", required_when_truthy="CORS_ALLOWED_ORIGINS"),
        "FUFIRE_ZWDS_SIGNOFF_ID is required_when_truthy 'CORS_ALLOWED_ORIGINS', a list-valued row",
    ),
    "conditional_vocabulary_missing": (
        lambda d: d.pop("conditional_requirements"),
        "must declare a conditional_requirements vocabulary naming exactly the implemented fields",
    ),
    "conditional_vocabulary_names_unimplemented_field": (
        lambda d: d["conditional_requirements"].update(staging_required_when_truthy="x"),
        r"must declare a conditional_requirements vocabulary .*'staging_required_when_truthy'",
    ),
    "conditional_vocabulary_drops_an_implemented_field": (
        lambda d: d["conditional_requirements"].pop("production_required_when_truthy"),
        r"must declare a conditional_requirements vocabulary .*not \['required_when_truthy'\]",
    ),
    # A misspelt field would silently drop the rule it was meant to declare.
    "misspelt_blank_policy_field": (
        lambda d: _set_row(d, "EPHEMERIS_MODE", production_blank_polcy="invalid"),
        r"EPHEMERIS_MODE declares unknown fields \['production_blank_polcy'\]",
    ),
    "misspelt_conditional_requirement_field": (
        lambda d: _set_row(d, "FUFIRE_ENV", required_when_truthyy="FUFIRE_REQUIRE_EXPLICIT_ENV"),
        r"FUFIRE_ENV declares unknown fields \['required_when_truthyy'\]",
    ),
}


def test_the_packaged_contract_declares_every_presence_vocabulary() -> None:
    """Canary for the malformed cases below: the real contract is accepted."""
    from bazi_engine.runtime_contract import validate_contract

    document = _mutated_contract(lambda d: None)
    assert "non_blank" in document["presence_semantics"]
    assert "unset" in document["blank_policies"]
    assert set(document["conditional_requirements"]) == {
        "required_when_truthy",
        "production_required_when_truthy",
    }
    validate_contract(document)


@pytest.mark.parametrize("case", sorted(MALFORMED_PRESENCE_CONTRACTS))
def test_malformed_presence_metadata_is_rejected(case: str) -> None:
    from bazi_engine.runtime_contract import validate_contract

    mutate, message = MALFORMED_PRESENCE_CONTRACTS[case]
    with pytest.raises(RuntimeError, match=f"^runtime contract .*{message}"):
        validate_contract(_mutated_contract(mutate))


@pytest.mark.parametrize(
    "case",
    [
        "unknown_presence_token",
        "unknown_blank_policy",
        "conditional_requirement_names_no_row",
        "misspelt_blank_policy_field",
    ],
)
def test_load_contract_fails_closed_on_malformed_presence_metadata(
    contract_document, case: str
) -> None:
    """On the LOAD path, so the startup guard and the readback both abort."""
    from bazi_engine import runtime_contract

    mutate, message = MALFORMED_PRESENCE_CONTRACTS[case]
    contract_document(mutate)
    with pytest.raises(RuntimeError, match=f"^runtime contract .*{message}"):
        runtime_contract.load_contract()


@pytest.mark.parametrize(
    ("row", "match"),
    [
        ({"name": "X", "presence_semantics": "semicolon_list"}, "unsupported presence_semantics"),
        ({"name": "X", "production_blank_policy": "reject"}, "unsupported production_blank_policy"),
        ({"name": "X", "required_when_truthy": ["FLAG"]}, "malformed required_when_truthy"),
        ({"name": "X", "production_required_when_truthy": ""}, "malformed production_required_when_truthy"),
    ],
)
def test_presence_metadata_is_refused_at_use_when_it_bypassed_validation(
    row: dict[str, Any], match: str
) -> None:
    """Second line of defence for a row that bypassed load-time validation."""
    from bazi_engine.runtime_contract import PROFILE_PRODUCTION, _variable_issue

    with pytest.raises(RuntimeError, match=match):
        _variable_issue(row, "", PROFILE_PRODUCTION, {"FLAG": "true"})
