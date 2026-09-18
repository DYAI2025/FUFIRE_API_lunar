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
