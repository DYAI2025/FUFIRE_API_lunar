"""FUF-156A / T5: a dead Redis must not turn /health or /ready into an opaque 500.

The limiter globals resolve at module import time (``bazi_engine/limiter.py``
reads REDIS_URL and constructs both Limiter objects at import), so an outage
scenario cannot be simulated by monkeypatching an already-imported module. Each
case therefore runs in a fresh subprocess with the environment set before the
first import.

The meaningful failure case is a *required, configured, unreachable* Redis: the
shared application limiter's ``.hit()`` raises, and because
``in_memory_fallback_enabled=False`` and slowapi's ``_swallow_errors`` defaults
to False, ``_check_request_limit`` re-raises straight into the request. This
module canaries that on a shared-limiter route first, so the /health and /ready
assertions are not vacuous.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

# Port 1 is privileged and never listening — connections are refused promptly.
DEAD_REDIS_URL = "redis://127.0.0.1:1/0"

_DRIVER = '''
import json, sys
from fastapi.testclient import TestClient
from bazi_engine.app import app
from bazi_engine.limiter import infra_limiter, limiter

out = {
    "app_limiter_storage": type(limiter._storage).__name__,
    "infra_limiter_storage": type(infra_limiter._storage).__name__,
    "redis_reachable": None,
    "responses": {},
}
try:
    out["redis_reachable"] = bool(limiter._storage.check())
except Exception as exc:
    out["redis_reachable"] = f"check raised: {type(exc).__name__}"

client = TestClient(app, client=("203.0.113.9", 4321), raise_server_exceptions=False)

for label, path in (
    ("health", "/health"),
    ("v1_health", "/v1/health"),
    ("ready", "/ready"),
    ("v1_ready", "/v1/ready"),
    ("shared_limiter_canary", "/transit/now"),
):
    try:
        resp = client.get(path)
        body = resp.text
        out["responses"][label] = {
            "status": resp.status_code,
            "body": body[:2000],
        }
    except Exception as exc:
        out["responses"][label] = {
            "status": "raised",
            "body": f"{type(exc).__name__}: {exc}"[:2000],
        }

print("___JSON___" + json.dumps(out))
'''


def _run_with_dead_redis() -> dict:
    env = dict(os.environ)
    env["REDIS_URL"] = DEAD_REDIS_URL
    env["FUFIRE_REQUIRE_REDIS"] = "true"
    env["PYTHONPATH"] = str(ROOT) + os.pathsep + env.get("PYTHONPATH", "")
    # Keep the child on the same ephemeris backend as the parent session so the
    # dependency payload is comparable (MOSEPH locally, SWIEPH in CI).
    if os.environ.get("EPHEMERIS_MODE"):
        env["EPHEMERIS_MODE"] = os.environ["EPHEMERIS_MODE"]

    proc = subprocess.run(
        [sys.executable, "-c", _DRIVER],
        cwd=str(ROOT),
        env=env,
        capture_output=True,
        text=True,
        timeout=300,
    )
    marker = "___JSON___"
    if marker not in proc.stdout:
        pytest.fail(
            "subprocess produced no result payload.\n"
            f"returncode={proc.returncode}\nstdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
        )
    return json.loads(proc.stdout.split(marker, 1)[1].strip())


@pytest.fixture(scope="module")
def outage() -> dict:
    return _run_with_dead_redis()


def test_setup_the_outage_is_real(outage: dict) -> None:
    """Precondition: Redis really is configured, required, and unreachable."""
    assert outage["app_limiter_storage"] == "RedisStorage", outage
    assert outage["redis_reachable"] is False or isinstance(
        outage["redis_reachable"], str
    ), outage
    assert outage["infra_limiter_storage"] == "MemoryStorage", outage


def test_canary_a_shared_limiter_route_does_break_under_the_outage(outage: dict) -> None:
    """CANARY: prove the isolation is load-bearing, not decorative.

    A route on the shared application limiter cannot serve its normal response
    while Redis is dead. If this ever goes green with a 200, the /health and
    /ready assertions below stop proving anything and this module must be
    re-derived.
    """
    canary = outage["responses"]["shared_limiter_canary"]
    assert canary["status"] != 200, (
        "the shared application limiter served a normal response with Redis dead — "
        f"the isolation proven below is no longer meaningful: {canary}"
    )


@pytest.mark.parametrize("label", ["health", "v1_health"])
def test_health_stays_answerable_and_never_opaque_500(outage: dict, label: str) -> None:
    """/health keeps answering its own contract; the limiter adds no 500."""
    resp = outage["responses"][label]
    assert resp["status"] == 200, resp
    payload = json.loads(resp["body"])
    assert payload["engine"] == "FuFirE"
    # The outage is reported structurally, in the dependency block.
    assert payload["dependencies"]["rate_limiter"]["status"] in ("degraded", "unavailable"), payload
    assert payload["status"] == "degraded", payload


@pytest.mark.parametrize("label", ["ready", "v1_ready"])
def test_ready_preserves_its_structured_dependency_failure(outage: dict, label: str) -> None:
    """/ready still returns the 503 readiness contract — not a limiter 500."""
    resp = outage["responses"][label]
    assert resp["status"] == 503, (
        "readiness must report a degraded dependency as its structured 503, "
        f"not as an opaque limiter failure: {resp}"
    )
    payload = json.loads(resp["body"])
    assert payload["status"] == "degraded", payload
    assert payload["engine"] == "FuFirE"
    assert payload["dependencies"]["rate_limiter"]["status"] in ("degraded", "unavailable"), payload
    assert payload["dependencies"]["rate_limiter"]["required"] is True, payload
    # The readiness body must not carry an error envelope from the limiter.
    assert "rate_limit_exceeded" not in resp["body"]


def test_no_infra_probe_response_is_a_server_error(outage: dict) -> None:
    """None of the four infra mounts degrade into 5xx-other or an exception."""
    for label in ("health", "v1_health", "ready", "v1_ready"):
        resp = outage["responses"][label]
        assert resp["status"] != "raised", f"{label} raised: {resp}"
        assert resp["status"] in (200, 503), f"{label} returned {resp['status']}: {resp}"
