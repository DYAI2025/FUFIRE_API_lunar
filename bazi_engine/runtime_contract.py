"""FUF-159 — the versioned, provider-neutral runtime configuration contract.

This module is the single place that reads
``bazi_engine/resources/runtime_contract.v1.json`` and turns it into three
things the rest of the engine consumes:

1. **Fail-closed predicates** for ``config_guard`` (the pepper and proxy-trust
   policies read their normative constraints from the contract, so the file and
   the startup guard cannot drift apart).
2. **A stable pseudonymisation primitive** for the shared rate limiter, so a raw
   API key or a raw client address never becomes a persisted or logged limiter
   identity.
3. **A secret-safe readback** — ``python -m bazi_engine.runtime_contract
   --readback --json`` — that reports what a deployment has configured without
   ever emitting a secret's value, prefix or suffix.

Deliberately stdlib-only apart from the Layer-0 package-resource boundary: the
readback has to work inside the source-free runtime image, and importing the
FastAPI application to answer "is this deployment configured correctly?" would
defeat the purpose.

Provider neutrality is load-bearing. The contract inventories *names, ownership,
required status and allowed shapes*. Which platform supplies which value is a
deployment binding and is not encoded here. In particular this module neither
sets nor widens ``FORWARDED_ALLOW_IPS``: it only makes an unsafe or unevidenced
widening impossible to start. The concrete trusted-proxy binding depends on
ingress evidence that is not yet recorded.
"""
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import logging
import os
import re
import secrets
import sys
from datetime import datetime, timezone
from functools import lru_cache
from typing import Any, Mapping, Optional, Sequence

from .resource_loader import load_json_object_resource

_log = logging.getLogger(__name__)

CONTRACT_SCHEMA_ID = "fufire.runtime-config-contract.v1"
CONTRACT_PACKAGE = "bazi_engine.resources"
CONTRACT_RESOURCE = "runtime_contract.v1.json"

PROFILE_PRODUCTION = "production"
PROFILE_DEVELOPMENT = "development"
# Not a profile a deployment can run under: a declared FUFIRE_ENV value that the
# contract does not list at all. Kept distinct from PROFILE_DEVELOPMENT so a typo
# can never be mistaken for a request for the permissive profile.
PROFILE_INVALID = "invalid"

# Variable names this module references by literal, so the drift gate in
# tests/test_runtime_contract.py can see that the fail-closed rows really do
# have an enforcement site.
ENV_PROFILE = "FUFIRE_ENV"
ENV_RL_PEPPER = "FUFIRE_RL_PEPPER"
ENV_FORWARDED_ALLOW_IPS = "FORWARDED_ALLOW_IPS"
ENV_TRUSTED_PROXY_EVIDENCE_ID = "FUFIRE_TRUSTED_PROXY_EVIDENCE_ID"
ENV_REPLICA_COUNT = "FUFIRE_REPLICA_COUNT"
ENV_REQUIRE_REDIS = "FUFIRE_REQUIRE_REDIS"
ENV_REDIS_URL = "REDIS_URL"
ENV_REDIS_PRIVATE_URL = "REDIS_PRIVATE_URL"

# Length of the hex pseudonym that reaches limiter storage and logs. 128 bits of
# a SHA-256 HMAC: far beyond collision risk for a rate-limit namespace, and short
# enough to keep storage keys readable in an incident.
PSEUDONYM_LENGTH = 32

_TRUTHY = {"1", "true", "yes", "on"}
_DEFAULT_PEPPER_MIN_LENGTH = 32


def _truthy(value: Optional[str]) -> bool:
    return (value or "").strip().lower() in _TRUTHY


# ── Contract access ──────────────────────────────────────────────────────────

@lru_cache(maxsize=1)
def load_contract() -> dict[str, Any]:
    """Load the packaged contract, fail-closed.

    Reads through the Layer-0 resource boundary, so a distribution that shipped
    without the contract raises instead of silently running unvalidated.
    """
    document = load_json_object_resource(CONTRACT_PACKAGE, CONTRACT_RESOURCE)
    if document.get("schema") != CONTRACT_SCHEMA_ID:
        raise RuntimeError(
            f"runtime contract declares schema {document.get('schema')!r}, "
            f"expected {CONTRACT_SCHEMA_ID!r}"
        )
    return document


def contract_version() -> str:
    return str(load_contract()["contract_version"])


def variables() -> tuple[dict[str, Any], ...]:
    return tuple(load_contract()["variables"])


def variable(name: str) -> Optional[dict[str, Any]]:
    for entry in variables():
        if entry["name"] == name:
            return entry
    return None


def _env(env: Optional[Mapping[str, str]]) -> Mapping[str, str]:
    return os.environ if env is None else env


def normalise_fufire_env(raw: Optional[str]) -> str:
    """Canonical comparison form for a declared profile value."""
    return (raw or "").strip().lower()


def allowed_fufire_env_values() -> frozenset[str]:
    """Every ``FUFIRE_ENV`` value the contract declares legal.

    The contract's ``FUFIRE_ENV`` row owns this set and nothing else may restate
    it. A non-empty value outside it is a typo or a mis-wired deployment.
    """
    entry = variable(ENV_PROFILE) or {}
    return frozenset(
        normalise_fufire_env(str(value)) for value in entry.get("allowed_values", ())
    )


def production_fufire_env_values() -> frozenset[str]:
    """The allowed values that select the fail-closed production profile."""
    profile = load_contract()["profiles"][PROFILE_PRODUCTION]
    return frozenset(
        normalise_fufire_env(str(value)) for value in profile["fufire_env_values"]
    )


def classify_runtime_profile(env: Optional[Mapping[str, str]] = None) -> str:
    """Classify a deployment as production, development or invalid.

    THE authoritative profile classifier: the startup guard and the readback
    both derive from it, so a value can never be production-shaped to one and
    development-shaped to the other.

    An unset value classifies as ``development`` — "no profile declared" is the
    local developer's case, and it is policed separately by
    ``FUFIRE_REQUIRE_EXPLICIT_ENV``, which every container image sets. A
    non-empty value outside the contract's allowed set classifies as
    ``invalid`` and must never be silently served the permissive profile.
    """
    current = normalise_fufire_env(_env(env).get(ENV_PROFILE))
    if not current:
        return PROFILE_DEVELOPMENT
    if current in production_fufire_env_values():
        return PROFILE_PRODUCTION
    if current in allowed_fufire_env_values():
        return PROFILE_DEVELOPMENT
    return PROFILE_INVALID


def unknown_profile_violation(env: Optional[Mapping[str, str]] = None) -> Optional[str]:
    """Return why the declared profile is not a contracted value, or None.

    ``FUFIRE_ENV`` is a non-secret row whose readback policy is ``value``, so
    echoing the rejected value is safe — and it is what makes a typo
    diagnosable from a crash log instead of a silent downgrade.
    """
    if classify_runtime_profile(env) != PROFILE_INVALID:
        return None
    declared = normalise_fufire_env(_env(env).get(ENV_PROFILE))
    allowed = ", ".join(sorted(allowed_fufire_env_values()))
    return (
        f"{ENV_PROFILE}={declared!r} is not a value the runtime contract allows "
        f"({allowed}). A mis-declared profile would silently skip every "
        "production check. Refusing to start (fail-closed)."
    )


def resolve_profile(env: Optional[Mapping[str, str]] = None) -> str:
    """Return the contract profile used by the READBACK payload.

    Derived from ``classify_runtime_profile`` so it cannot drift from the
    startup guard. The readback's ``profile`` field deliberately stays
    two-valued: an invalid value is reported there by the ``FUFIRE_ENV`` row's
    own ``allowed_values`` check (issue ``invalid_value``), which keeps every
    other row's ``required_profiles`` evaluation meaningful instead of grading
    them against a profile the contract has no entry for.
    """
    profile = classify_runtime_profile(env)
    return PROFILE_DEVELOPMENT if profile == PROFILE_INVALID else profile


# ── Rate-limit pseudonymisation ──────────────────────────────────────────────

def pepper_min_length() -> int:
    entry = variable(ENV_RL_PEPPER) or {}
    constraints = entry.get("constraints") or {}
    return int(constraints.get("min_length", _DEFAULT_PEPPER_MIN_LENGTH))


def rate_limit_pepper_violation(
    env: Optional[Mapping[str, str]] = None, *, required: bool
) -> Optional[str]:
    """Return a secret-free description of why the pepper is unusable, or None.

    Never includes the configured value, a prefix, a suffix or its length — a
    fail-closed message must not become the leak it exists to prevent.
    """
    raw = _env(env).get(ENV_RL_PEPPER)
    minimum = pepper_min_length()
    if raw is None:
        if required:
            return (
                f"{ENV_RL_PEPPER} must be configured: the shared rate limiter's "
                "counters outlive this process, so its pseudonymous identities "
                "need an operator-supplied pepper that is stable across replicas "
                "and restarts."
            )
        return None
    if not raw.strip():
        return f"{ENV_RL_PEPPER} is set but blank; refusing to start (fail-closed)."
    if len(raw.strip()) < minimum:
        return (
            f"{ENV_RL_PEPPER} is shorter than the required minimum of {minimum} "
            "characters; refusing to start (fail-closed)."
        )
    return None


@lru_cache(maxsize=1)
def rate_limit_pepper() -> bytes:
    """Return the HMAC pepper for shared-limiter identities.

    An operator-supplied ``FUFIRE_RL_PEPPER`` is validated and used verbatim.
    With none configured this falls back to a process-local random value, which
    is correct ONLY where limiter counters are themselves process-local: the
    production profile refuses to start without a configured pepper wherever the
    counters are shared (see ``config_guard``).

    Cached for process lifetime, because a pepper that rotated mid-process would
    split one caller's counter in two. Call ``rate_limit_pepper.cache_clear()``
    in tests after changing the environment.
    """
    raw = os.environ.get(ENV_RL_PEPPER)
    if raw is not None and raw.strip():
        violation = rate_limit_pepper_violation(required=False)
        if violation is not None:
            raise RuntimeError(violation)
        return raw.strip().encode("utf-8")
    _log.warning(
        "%s is not configured — using a process-local rate-limit pepper. "
        "Shared/Redis-backed limiter counters would be sharded per process.",
        ENV_RL_PEPPER,
    )
    return secrets.token_bytes(32)


def pseudonymise(raw: str) -> str:
    """Return a stable, non-reversible identity for ``raw``.

    The return value is what slowapi writes into BOTH the limiter storage key
    and the ``"ratelimit %s (%s) exceeded at endpoint: %s"`` WARNING log line,
    so it must never contain the input.
    """
    digest = hmac.new(rate_limit_pepper(), raw.encode("utf-8"), hashlib.sha256)
    return digest.hexdigest()[:PSEUDONYM_LENGTH]


def shared_limiter_counters_outlive_process(
    env: Optional[Mapping[str, str]] = None,
) -> bool:
    """True when shared-limiter counters survive a restart or span replicas.

    Any of these makes a process-local pepper wrong: an explicitly required
    Redis, more than one replica, or a configured Redis connection URI.
    """
    source = _env(env)
    if _truthy(source.get(ENV_REQUIRE_REDIS)):
        return True
    if source.get(ENV_REDIS_URL) or source.get(ENV_REDIS_PRIVATE_URL):
        return True
    raw = (source.get(ENV_REPLICA_COUNT) or "").strip()
    try:
        return int(raw) > 1
    except ValueError:
        return False


# ── Proxy-trust policy (guard only — never a binding) ────────────────────────

def proxy_trust_violation(env: Optional[Mapping[str, str]] = None) -> Optional[str]:
    """Return why the configured proxy trust is unacceptable, or None.

    This never proposes, sets or widens a value. A wildcard is rejected
    unconditionally; any other deviation from the server default requires a
    recorded ingress-evidence reference. No CIDR is assumed or invented here —
    that evidence is owned by a separate, unresolved runtime-evidence task.
    """
    source = _env(env)
    entry = variable(ENV_FORWARDED_ALLOW_IPS) or {}
    raw = source.get(ENV_FORWARDED_ALLOW_IPS)
    if raw is None:
        return None
    value = raw.strip()

    forbidden = {str(v).strip() for v in entry.get("production_forbidden_values", [])}
    if value in forbidden:
        return (
            f"{ENV_FORWARDED_ALLOW_IPS}={value!r} enables wildcard proxy trust: "
            "every caller could then forge the forwarded client address. "
            "Refusing to start (fail-closed)."
        )

    safe_defaults = {str(v).strip() for v in entry.get("safe_default_values", [""])}
    if value in safe_defaults:
        return None

    evidence_name = str(entry.get("evidence_variable", ENV_TRUSTED_PROXY_EVIDENCE_ID))
    if not (source.get(evidence_name) or "").strip():
        return (
            f"{ENV_FORWARDED_ALLOW_IPS} deviates from the server default, so "
            f"{evidence_name} must reference the recorded ingress evidence that "
            "justifies trusting that peer set. Refusing to start (fail-closed)."
        )
    return None


# ── Readback evaluation ──────────────────────────────────────────────────────

def _is_configured(raw: Optional[str]) -> bool:
    return raw is not None and raw.strip() != ""


def _required_here(entry: Mapping[str, Any], profile: str) -> bool:
    return profile in entry.get("required_profiles", [])


def _satisfied_by_alternative(
    entry: Mapping[str, Any], source: Mapping[str, str]
) -> bool:
    for alternative in entry.get("satisfied_by", []):
        value = (source.get(str(alternative)) or "").strip().lower()
        if value and value != "none":
            return True
    return False


def _variable_issue(
    entry: Mapping[str, Any],
    raw: Optional[str],
    profile: str,
    source: Mapping[str, str],
) -> Optional[tuple[str, str]]:
    """Return ``(code, message)`` for the first violated rule, else None."""
    name = entry["name"]
    configured = _is_configured(raw)
    production = profile == PROFILE_PRODUCTION

    if _required_here(entry, profile) and not configured:
        if not _satisfied_by_alternative(entry, source):
            return ("missing_required", f"{name} is required in the {profile} profile")

    if production and entry.get("production_required_truthy") and not _truthy(raw):
        return ("must_be_enabled", f"{name} must be enabled in the {profile} profile")

    if production and entry.get("production_forbidden_truthy") and _truthy(raw):
        return ("forbidden_value", f"{name} must not be enabled in the {profile} profile")

    if not configured:
        return None
    value = _comparison_value(name, str(raw).strip())
    return _configured_value_issue(entry, value, production)


def _comparison_value(name: str, value: str) -> str:
    """Return the form of ``value`` the contract's rules are written against.

    Deliberately NOT a blanket case-fold. ``EPHEMERIS_MODE`` ("SWIEPH"),
    ``KEY_STORE_BACKEND`` ("none") and every ``value_pattern`` row declare their
    shapes in a specific case, and widening all of them at once would weaken
    rules this function exists to enforce.

    ``FUFIRE_ENV`` is the one row with an authoritative normaliser, and reusing
    it here is what keeps the readback's verdict identical to
    ``classify_runtime_profile``'s. Without it ``FUFIRE_ENV=Production`` was a
    production deployment to the startup guard and an ``invalid_value`` to the
    readback — one contract row answering the same question two ways. The alias
    list itself stays in the contract; this only picks the comparison form.
    """
    if name == ENV_PROFILE:
        return normalise_fufire_env(value)
    return value


def _configured_value_issue(
    entry: Mapping[str, Any], value: str, production: bool
) -> Optional[tuple[str, str]]:
    name = entry["name"]

    if production and value in {str(v).strip() for v in entry.get("production_forbidden_values", [])}:
        return ("forbidden_value", f"{name} holds a value forbidden in the production profile")

    allowed = entry.get("allowed_values")
    if allowed is not None and value not in {str(v) for v in allowed}:
        return ("invalid_value", f"{name} is outside its allowed value set")

    production_allowed = entry.get("production_allowed_values")
    if production and production_allowed is not None and value not in {str(v) for v in production_allowed}:
        return ("invalid_value", f"{name} is outside the production-allowed value set")

    pattern = entry.get("value_pattern")
    if pattern is not None and not re.fullmatch(str(pattern), value):
        return ("invalid_value", f"{name} does not match its required form")

    return None


def _variable_record(
    entry: Mapping[str, Any],
    raw: Optional[str],
    profile: str,
    issue: Optional[tuple[str, str]],
) -> dict[str, Any]:
    configured = _is_configured(raw)
    record: dict[str, Any] = {
        "name": entry["name"],
        "ownerArea": entry["owner_area"],
        "consumer": entry["consumer"],
        "secret": bool(entry["secret"]),
        "configured": configured,
        "valid": issue is None,
        "sourceClass": "env" if configured else "unset",
        "requiredHere": _required_here(entry, profile),
        "readback": entry["readback"],
        "failClosed": entry["fail_closed"],
    }
    # A value is emitted ONLY for a non-secret row whose readback policy marks it
    # explicitly safe. Secrets never get a value, prefix, suffix or length.
    if configured and not entry["secret"] and entry["readback"] == "value":
        record["value"] = str(raw).strip()
    if issue is not None:
        record["issue"] = issue[0]
    return record


def _cross_variable_violations(
    source: Mapping[str, str], profile: str
) -> list[dict[str, str]]:
    violations: list[dict[str, str]] = []
    pepper_required = profile == PROFILE_PRODUCTION and shared_limiter_counters_outlive_process(source)
    pepper = rate_limit_pepper_violation(source, required=pepper_required)
    if pepper is not None:
        violations.append(
            {"variable": ENV_RL_PEPPER, "code": "pepper_policy", "message": pepper}
        )
    if profile == PROFILE_PRODUCTION:
        proxy = proxy_trust_violation(source)
        if proxy is not None:
            violations.append(
                {
                    "variable": ENV_FORWARDED_ALLOW_IPS,
                    "code": "proxy_trust_policy",
                    "message": proxy,
                }
            )
    return violations


def evaluate(env: Optional[Mapping[str, str]] = None) -> dict[str, Any]:
    """Return the secret-safe readback payload for the current environment."""
    from . import __version__ as engine_version

    source = _env(env)
    profile = resolve_profile(source)

    records: list[dict[str, Any]] = []
    violations: list[dict[str, str]] = []
    for entry in variables():
        raw = source.get(entry["name"])
        issue = _variable_issue(entry, raw, profile, source)
        records.append(_variable_record(entry, raw, profile, issue))
        if issue is not None:
            violations.append(
                {"variable": entry["name"], "code": issue[0], "message": issue[1]}
            )

    violations.extend(_cross_variable_violations(source, profile))

    return {
        "schema": CONTRACT_SCHEMA_ID,
        "contractVersion": contract_version(),
        "profile": profile,
        "engineVersion": engine_version,
        "evaluatedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "valid": not violations,
        "violationCount": len(violations),
        "violations": violations,
        "variables": records,
    }


# ── CLI ──────────────────────────────────────────────────────────────────────

def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m bazi_engine.runtime_contract",
        description="Secret-safe runtime configuration readback (FUF-159).",
    )
    parser.add_argument(
        "--readback",
        action="store_true",
        help="Evaluate the current environment against the packaged contract.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit JSON (the only supported output format).",
    )
    args = parser.parse_args(argv)
    _ = args.readback, args.json

    payload = evaluate()
    print(json.dumps(payload, indent=2, sort_keys=False))
    return 0 if payload["valid"] else 1


if __name__ == "__main__":  # pragma: no cover - exercised via subprocess in tests
    sys.exit(main())
