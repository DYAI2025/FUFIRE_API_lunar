"""FUF-159: pseudonymous identities for the SHARED application limiter.

Before this slice the shared limiter returned the raw API key for authenticated
requests and the raw client address for the IP branch. slowapi writes the key
function's return value into BOTH the limiter storage key
(``__evaluate_limits``: ``args = [limit_key, limit_scope]``) and the
``"ratelimit %s (%s) exceeded at endpoint: %s"`` WARNING log line, so both raw
values were persisted and logged.

Boundary discipline (CLAUDE.md, WS-A PII-leak retro): every privacy claim here
is asserted against the REAL ``bazi_engine.limiter.limiter`` instance — its real
storage object and the real slowapi logger — driven over HTTP by ``TestClient``.
Each leak assertion is CANARIED: the same test first proves that an equivalent
raw-value-keyed limiter genuinely does leak, so a green result cannot come from
an assertion that never had teeth.

R3 runs against the production route table (``GET /v1/transit/now``). R4 needs
a shared-limiter route with NO ``require_api_key`` dependency; the current mount
table has none, so it drives the real limiter and the real ``tier_limit``
dispatcher over a purpose-built ASGI app. The limiter, its storage, its logger
and the HTTP boundary are all real — only the route table is local.

Out of scope, deliberately: any claim that the client address observed here is
the true end-user address behind an ingress. That is FUF-168 and is unresolved.
"""
from __future__ import annotations

import logging
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from starlette.requests import Request

from bazi_engine.app import app
from bazi_engine.auth import TIER_LIMITS, _load_keys
from bazi_engine.limiter import (
    LEGACY_IP_LIMIT,
    MALFORMED_IDENTITY_LIMIT,
    get_rate_limit_key,
    limiter,
    tier_limit,
)

ROOT = Path(__file__).resolve().parents[1]

# RFC 5737 documentation address — never a real client, and distinctive enough
# that a substring search for it is a meaningful leak test.
CLIENT_IP = "203.0.113.11"

# Deliberately long and unmistakable, so a substring hit cannot be a coincidence.
RAW_FREE_KEY = "ff_free_SENTINELRAWKEY6d1f04ba93ce7215"

DIGEST_RE = re.compile(r"^[0-9a-f]{32}$")

TEST_PEPPER_A = "pepper-alpha-0f2b7c1d94ae65380b12cc7745e9aa31"
TEST_PEPPER_B = "pepper-bravo-91cc40e7bd23a6f85107ee31d4b0921f"


# ── Helpers ──────────────────────────────────────────────────────────────────

def _storage_keys(lim: Limiter) -> list[str]:
    """Every key currently held by a limiter's in-memory storage."""
    storage = lim._storage  # noqa: SLF001
    keys: list[str] = list(getattr(storage, "storage", {}).keys())
    keys += list(getattr(storage, "events", {}).keys())
    return [str(k) for k in keys]


def _make_request(*, key: str | None, client_ip: str) -> Request:
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/v1/transit/now",
        "headers": [],
        "query_string": b"",
        "root_path": "",
        "client": (client_ip, 8000),
    }
    request = Request(scope)
    if key is not None:
        request.state.key_info = type(
            "KI", (), {"key": key, "tier": key.split("_")[1]}
        )()
    return request


@pytest.fixture
def free_key_env(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("FUFIRE_API_KEYS", RAW_FREE_KEY)
    monkeypatch.delenv("KEY_STORE_BACKEND", raising=False)
    _load_keys.cache_clear()
    yield
    _load_keys.cache_clear()


# ── Identity shape — raw values never leave the key function ─────────────────

def test_authenticated_identity_is_structured_and_pseudonymous() -> None:
    identity = get_rate_limit_key(_make_request(key=RAW_FREE_KEY, client_ip=CLIENT_IP))

    assert identity != RAW_FREE_KEY
    assert RAW_FREE_KEY not in identity
    assert CLIENT_IP not in identity

    scheme, tier, digest = identity.split(":")
    assert scheme == "k"
    assert tier == "free"
    assert DIGEST_RE.match(digest), identity


def test_ip_identity_is_structured_and_pseudonymous() -> None:
    identity = get_rate_limit_key(_make_request(key=None, client_ip=CLIENT_IP))

    assert identity != CLIENT_IP
    assert CLIENT_IP not in identity
    scheme, digest = identity.split(":")
    assert scheme == "ip"
    assert DIGEST_RE.match(digest), identity


def test_identity_is_stable_within_a_process() -> None:
    first = get_rate_limit_key(_make_request(key=RAW_FREE_KEY, client_ip=CLIENT_IP))
    second = get_rate_limit_key(_make_request(key=RAW_FREE_KEY, client_ip=CLIENT_IP))
    assert first == second


def test_distinct_raw_keys_get_distinct_pseudonyms() -> None:
    a = get_rate_limit_key(_make_request(key="ff_free_aaaa1111", client_ip=CLIENT_IP))
    b = get_rate_limit_key(_make_request(key="ff_free_bbbb2222", client_ip=CLIENT_IP))
    assert a != b


# ── R3 — raw API key privacy at the real boundary ────────────────────────────

def test_raw_api_key_reaches_neither_limiter_storage_nor_logs(
    free_key_env, caplog: pytest.LogCaptureFixture
) -> None:
    """Drive the real app past the free-tier limit and inspect both channels."""
    client = TestClient(app, client=(CLIENT_IP, 12345))
    headers = {"X-API-Key": RAW_FREE_KEY}
    free_rpm = TIER_LIMITS["free"][1]

    with caplog.at_level(logging.WARNING):
        statuses = [
            client.get("/v1/transit/now", headers=headers).status_code
            for _ in range(free_rpm + 1)
        ]

    assert statuses[-1] == 429, f"free tier never hit its limit: {statuses}"

    keys = _storage_keys(limiter)
    assert keys, "the shared limiter recorded no counters at all"
    assert not any(RAW_FREE_KEY in k for k in keys), (
        f"raw API key persisted in limiter storage keys: {keys}"
    )
    # limits builds the storage key as "LIMITER/<prefix>/<identity>/<path>/...".
    assert any("fufire_rl:/k:free:" in k for k in keys), (
        f"no pseudonymous free-tier counter recorded: {keys}"
    )

    log_text = caplog.text
    assert "ratelimit" in log_text, "slowapi never logged the limit-exceeded event"
    assert RAW_FREE_KEY not in log_text, "raw API key leaked into the slowapi warning log"


def test_canary_a_raw_key_keyed_limiter_does_leak(caplog: pytest.LogCaptureFixture) -> None:
    """Prove the two channels above genuinely expose a raw key when one is used.

    Without this, ``test_raw_api_key_reaches_neither...`` could pass simply
    because neither channel ever contains anything.
    """
    leaky = Limiter(
        key_func=lambda request: request.headers.get("X-API-Key", "anonymous"),
        storage_uri="memory://",
        in_memory_fallback_enabled=False,
        key_prefix="canary_raw_key_rl:",
    )
    leaky_app = FastAPI()
    leaky_app.state.limiter = leaky
    leaky_app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    @leaky_app.get("/canary")
    @leaky.limit("2/minute")
    def canary(request: Request) -> dict:  # noqa: ARG001
        return {"ok": True}

    client = TestClient(leaky_app, client=(CLIENT_IP, 12345))
    with caplog.at_level(logging.WARNING):
        statuses = [
            client.get("/canary", headers={"X-API-Key": RAW_FREE_KEY}).status_code
            for _ in range(3)
        ]

    assert statuses[-1] == 429
    assert any(RAW_FREE_KEY in k for k in _storage_keys(leaky)), (
        "canary limiter did not persist the raw key — the storage probe is blind"
    )
    assert RAW_FREE_KEY in caplog.text, (
        "canary limiter did not log the raw key — the log probe is blind"
    )


# ── R4 — raw client IP privacy on the shared limiter ─────────────────────────

def _ip_probe_app() -> FastAPI:
    probe = FastAPI()
    probe.state.limiter = limiter
    probe.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    @probe.get("/shared-ip-probe")
    @limiter.limit(tier_limit)
    def shared_ip_probe(request: Request) -> dict:  # noqa: ARG001
        return {"ok": True}

    return probe


def test_raw_client_ip_reaches_neither_limiter_storage_nor_logs(
    caplog: pytest.LogCaptureFixture,
) -> None:
    client = TestClient(_ip_probe_app(), client=(CLIENT_IP, 12345))
    budget = int(LEGACY_IP_LIMIT.split("/")[0])

    with caplog.at_level(logging.WARNING):
        statuses = [client.get("/shared-ip-probe").status_code for _ in range(budget + 1)]

    assert statuses[-1] == 429, f"IP branch never hit the legacy fallback: {statuses}"

    keys = _storage_keys(limiter)
    assert keys, "the shared limiter recorded no counters at all"
    assert not any(CLIENT_IP in k for k in keys), (
        f"raw client IP persisted in limiter storage keys: {keys}"
    )
    assert any("fufire_rl:/ip:" in k for k in keys), (
        f"no pseudonymous IP counter recorded: {keys}"
    )
    assert "ratelimit" in caplog.text
    assert CLIENT_IP not in caplog.text, "raw client IP leaked into the slowapi warning log"


def test_canary_a_raw_ip_keyed_limiter_does_leak(caplog: pytest.LogCaptureFixture) -> None:
    leaky = Limiter(
        key_func=get_remote_address,
        storage_uri="memory://",
        in_memory_fallback_enabled=False,
        key_prefix="canary_raw_ip_rl:",
    )
    leaky_app = FastAPI()
    leaky_app.state.limiter = leaky
    leaky_app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    @leaky_app.get("/canary-ip")
    @leaky.limit("2/minute")
    def canary_ip(request: Request) -> dict:  # noqa: ARG001
        return {"ok": True}

    client = TestClient(leaky_app, client=(CLIENT_IP, 12345))
    with caplog.at_level(logging.WARNING):
        statuses = [client.get("/canary-ip").status_code for _ in range(3)]

    assert statuses[-1] == 429
    assert any(CLIENT_IP in k for k in _storage_keys(leaky)), (
        "canary limiter did not persist the raw IP — the storage probe is blind"
    )
    assert CLIENT_IP in caplog.text, (
        "canary limiter did not log the raw IP — the log probe is blind"
    )


# ── R5 / R6 — pepper-derived pseudonym stability across processes ────────────

def _pseudonym_in_subprocess(pepper: str, raw: str) -> str:
    env = dict(os.environ)
    env["FUFIRE_RL_PEPPER"] = pepper
    env["PYTHONPATH"] = str(ROOT)
    proc = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys;"
            "from bazi_engine.runtime_contract import pseudonymise;"
            "print(pseudonymise(sys.argv[1]))",
            raw,
        ],
        capture_output=True,
        text=True,
        env=env,
        cwd=str(ROOT),
    )
    assert proc.returncode == 0, proc.stderr
    return proc.stdout.strip()


def test_same_key_same_pepper_yields_the_same_pseudonym_in_two_processes() -> None:
    first = _pseudonym_in_subprocess(TEST_PEPPER_A, RAW_FREE_KEY)
    second = _pseudonym_in_subprocess(TEST_PEPPER_A, RAW_FREE_KEY)
    assert DIGEST_RE.match(first), first
    assert first == second, "pseudonym is not stable across replicas/restarts"


def test_same_key_different_pepper_yields_a_different_pseudonym() -> None:
    a = _pseudonym_in_subprocess(TEST_PEPPER_A, RAW_FREE_KEY)
    b = _pseudonym_in_subprocess(TEST_PEPPER_B, RAW_FREE_KEY)
    assert a != b, "pseudonym does not depend on the configured pepper"


def test_pseudonym_never_contains_the_raw_input() -> None:
    digest = _pseudonym_in_subprocess(TEST_PEPPER_A, RAW_FREE_KEY)
    assert RAW_FREE_KEY not in digest
    assert digest != RAW_FREE_KEY


# ── R7 — tier semantics unchanged ────────────────────────────────────────────

EXPECTED_TIER_LIMITS = {
    "free": "5/minute",
    "starter": "20/minute",
    "pro": "100/minute",
    "enterprise": "10000/minute",
    "dev": "10000/minute",
}


@pytest.mark.parametrize(("tier", "expected"), sorted(EXPECTED_TIER_LIMITS.items()))
def test_structured_identity_preserves_every_tier_limit(tier: str, expected: str) -> None:
    identity = f"k:{tier}:{'a' * 32}"
    assert tier_limit(identity) == expected


@pytest.mark.parametrize(("tier", "expected"), sorted(EXPECTED_TIER_LIMITS.items()))
def test_legacy_raw_identity_still_resolves_the_same_tier_limit(
    tier: str, expected: str
) -> None:
    """Rollback compatibility: the previous raw-key identity must still parse."""
    raw = "dev-mode" if tier == "dev" else f"ff_{tier}_rollbackcompat"
    assert tier_limit(raw) == expected


def test_structured_ip_identity_keeps_the_legacy_fallback_limit() -> None:
    assert tier_limit(f"ip:{'b' * 32}") == LEGACY_IP_LIMIT


def test_legacy_raw_ip_identity_keeps_the_legacy_fallback_limit() -> None:
    assert tier_limit("127.0.0.1") == LEGACY_IP_LIMIT
    assert tier_limit("192.168.1.100") == LEGACY_IP_LIMIT


def test_tier_limit_still_exposes_the_key_parameter_slowapi_requires() -> None:
    import inspect

    assert "key" in inspect.signature(tier_limit).parameters


# ── R8 — malformed structured identities ─────────────────────────────────────

MALFORMED = [
    "k:",
    "k::",
    "k:free:",
    "k:free",
    "k:free:not-a-digest",
    "k:free:" + "a" * 31,
    "k:free:" + "A" * 32,
    "k:nosuchtier:" + "a" * 32,
    "k:free:aaaa:bbbb",
    "ip:",
    "ip:not-a-digest",
]


@pytest.mark.parametrize("identity", MALFORMED)
def test_malformed_structured_identity_is_not_silently_downgraded(identity: str) -> None:
    resolved = tier_limit(identity)
    assert resolved == MALFORMED_IDENTITY_LIMIT, (
        f"{identity!r} resolved to {resolved!r} instead of the explicit "
        "malformed-identity limit"
    )
    assert resolved != EXPECTED_TIER_LIMITS["free"], (
        "a malformed authenticated identity silently became the free tier"
    )


def test_malformed_identity_limit_is_stricter_than_every_tier() -> None:
    malformed_rpm = int(MALFORMED_IDENTITY_LIMIT.split("/")[0])
    tier_rpms = [int(v.split("/")[0]) for v in EXPECTED_TIER_LIMITS.values()]
    assert malformed_rpm < min(tier_rpms)


def test_malformed_identity_is_logged(caplog: pytest.LogCaptureFixture) -> None:
    """Fail-closed, but never silent — the operator must be able to see it."""
    with caplog.at_level(logging.WARNING, logger="bazi_engine.limiter"):
        tier_limit("k:free:not-a-digest")
    assert "malformed" in caplog.text.lower()
