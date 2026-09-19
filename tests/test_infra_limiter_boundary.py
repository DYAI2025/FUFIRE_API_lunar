"""FUF-156A: the dedicated infrastructure-probe limiter behind /health and /ready.

Covers four claims that registry inspection alone cannot make:

* T1 — the infra limiter is storage-isolated from the application limiter.
* T3 — a real request sequence against the real app crosses the limit and gets
  the canonical ``rate_limit_exceeded`` envelope with a correct ``Retry-After``.
* T4 — the raw client address reaches neither the limiter storage keys nor the
  slowapi limit-exceeded logs. Canaried: the same test first proves an
  equivalent raw-IP-keyed limiter *does* leak both.

Boundary discipline (CLAUDE.md, WS-A PII-leak retro): every claim about a
response body or about what gets persisted/logged is asserted at the real
boundary via ``TestClient`` and the real storage object, never on a unit-level
stand-in.
"""
from __future__ import annotations

import logging

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.requests import Request

from bazi_engine.app import app
from bazi_engine.limiter import (
    INFRA_PROBE_LIMIT,
    infra_limiter,
    infra_probe_key,
    limiter,
)

# RFC 5737 documentation address — never a real client, and distinctive enough
# that a substring search for it is a meaningful leak test.
PROBE_IP = "203.0.113.7"

# The four surfaces this slice owns. The remaining three FUF-156 routes
# (GET /api, GET /v1/api, POST /internal/api/webhooks/chart) are deliberately
# out of scope here and are NOT asserted.
INFRA_ROUTES = ("/health", "/v1/health", "/ready", "/v1/ready")


def _parse_limit(limit: str) -> tuple[int, int]:
    """Split ``"120/minute"`` into (amount, window_seconds)."""
    amount, _, per = limit.partition("/")
    seconds = {"second": 1, "minute": 60, "hour": 3600, "day": 86400}[per.strip()]
    return int(amount), seconds


INFRA_LIMIT_AMOUNT, INFRA_LIMIT_WINDOW = _parse_limit(INFRA_PROBE_LIMIT)


def _storage_keys(lim: Limiter) -> list[str]:
    """Every key currently held by a limiter's in-memory storage."""
    return list(getattr(lim._storage, "storage", {}).keys())  # noqa: SLF001


@pytest.fixture
def probe_client() -> TestClient:
    """TestClient that presents a concrete, recognisable client IP."""
    return TestClient(app, client=(PROBE_IP, 12345))


# ── T1 — limiter isolation ───────────────────────────────────────────────────

def test_infra_limiter_uses_memory_storage_independent_of_the_app_limiter() -> None:
    """The infra limiter is memory-backed, separately namespaced, and not Redis."""
    from limits.storage.memory import MemoryStorage

    assert isinstance(infra_limiter._storage, MemoryStorage)  # noqa: SLF001
    assert infra_limiter._storage_uri == "memory://"  # noqa: SLF001
    # Never resolves to Redis, whatever REDIS_URL says.
    assert "redis" not in (infra_limiter._storage_uri or "")  # noqa: SLF001
    # Distinct storage object and distinct key namespace from the app limiter.
    assert infra_limiter._storage is not limiter._storage  # noqa: SLF001
    assert infra_limiter._key_prefix == "fufire_infra_rl:"  # noqa: SLF001
    assert limiter._key_prefix == "fufire_rl:"  # noqa: SLF001
    assert infra_limiter._key_prefix != limiter._key_prefix  # noqa: SLF001


def test_infra_probe_traffic_never_lands_in_application_limiter_storage(
    probe_client: TestClient,
) -> None:
    """Hitting every infra route leaves the application limiter's counters empty."""
    for path in INFRA_ROUTES:
        probe_client.get(path)

    assert _storage_keys(infra_limiter), "infra limiter recorded no counters at all"
    assert _storage_keys(limiter) == [], (
        "infra probes leaked into the application limiter storage: "
        f"{_storage_keys(limiter)}"
    )


def test_each_infra_mount_gets_its_own_bucket(probe_client: TestClient) -> None:
    """slowapi's key_style is 'url', so /health and /v1/health do not share a bucket."""
    for path in INFRA_ROUTES:
        probe_client.get(path)

    keys = _storage_keys(infra_limiter)
    assert len(keys) == len(INFRA_ROUTES), f"expected one bucket per mount, got {keys}"
    for path in INFRA_ROUTES:
        assert any(f"/{path}/" in k for k in keys), f"no bucket scoped to {path}: {keys}"


# ── T3 — real 429 boundary ───────────────────────────────────────────────────

def test_health_returns_canonical_429_envelope_after_the_limit(
    probe_client: TestClient,
) -> None:
    """Requests below the limit succeed; the one above it is a canonical 429."""
    for i in range(INFRA_LIMIT_AMOUNT):
        resp = probe_client.get("/health")
        assert resp.status_code == 200, f"request {i + 1} below the limit returned {resp.status_code}"
        assert resp.json()["engine"] == "FuFirE"

    over = probe_client.get("/health")
    assert over.status_code == 429

    body = over.json()
    assert body["error"] == "rate_limit_exceeded"
    assert body["message"] == "Rate limit exceeded"
    assert body["status"] == 429
    assert body["path"] == "/health"
    assert isinstance(body["detail"], dict)
    assert "request_id" in body and "timestamp" in body

    # Retry-After must match the configured window, not a coincidental constant.
    assert "retry-after" in {k.lower() for k in over.headers}
    assert int(over.headers["Retry-After"]) == INFRA_LIMIT_WINDOW

    # The raw client address must not appear anywhere in the 429 response.
    assert PROBE_IP not in over.text


def test_exhausting_health_leaves_the_other_infra_mounts_answerable(
    probe_client: TestClient,
) -> None:
    """A per-route bucket means a hot /health cannot take /ready down with it."""
    for _ in range(INFRA_LIMIT_AMOUNT):
        probe_client.get("/health")
    assert probe_client.get("/health").status_code == 429

    assert probe_client.get("/v1/health").status_code == 200
    # /ready answers 200 when healthy and 503 when a dependency is degraded —
    # either is the readiness contract; 429 would mean a shared bucket.
    assert probe_client.get("/ready").status_code in (200, 503)


def test_ready_also_enforces_the_limit(probe_client: TestClient) -> None:
    """The limit is real on /ready too, not only on /health."""
    for _ in range(INFRA_LIMIT_AMOUNT):
        assert probe_client.get("/ready").status_code in (200, 503)

    over = probe_client.get("/ready")
    assert over.status_code == 429
    assert over.json()["error"] == "rate_limit_exceeded"


# ── T4 — privacy (canary first, then the real proof) ─────────────────────────

def _build_raw_ip_canary_app() -> tuple[FastAPI, Limiter]:
    """An equivalent limiter that keys on the raw remote address.

    This is the construction FUF-156A rejects. It exists so the leak it causes
    is demonstrated, not assumed — a privacy assertion that has never been seen
    to fail proves nothing.
    """
    canary_limiter = Limiter(
        key_func=get_remote_address,
        storage_uri="memory://",
        in_memory_fallback_enabled=False,
        key_prefix="canary_rl:",
    )
    canary_app = FastAPI()

    @canary_app.get("/probe")
    @canary_limiter.limit("1/minute")
    def probe(request: Request) -> dict:  # noqa: ARG001 - required by slowapi
        return {"ok": True}

    return canary_app, canary_limiter


def test_canary_a_raw_ip_key_leaks_the_client_address_into_storage_and_logs(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """CANARY: prove the failure mode is real before asserting it is absent."""
    canary_app, canary_limiter = _build_raw_ip_canary_app()
    client = TestClient(canary_app, client=(PROBE_IP, 12345))

    with caplog.at_level(logging.WARNING, logger="slowapi"):
        assert client.get("/probe").status_code == 200
        # Second call trips the 1/minute limit and emits slowapi's WARNING.
        client.get("/probe")

    leaked_keys = [k for k in _storage_keys(canary_limiter) if PROBE_IP in k]
    assert leaked_keys, (
        "canary did not reproduce the storage leak — the leak test below would "
        f"be vacuous. keys={_storage_keys(canary_limiter)}"
    )

    limit_logs = [r.getMessage() for r in caplog.records if r.name == "slowapi"]
    assert any(PROBE_IP in m for m in limit_logs), (
        f"canary did not reproduce the log leak — logs={limit_logs}"
    )


def test_infra_limiter_storage_keys_carry_no_raw_client_address(
    probe_client: TestClient,
) -> None:
    """The real limiter: pseudonymous key in storage, raw address absent."""
    probe_client.get("/health")

    keys = _storage_keys(infra_limiter)
    assert keys, "no infra counters were written"
    for key in keys:
        assert PROBE_IP not in key, f"raw client address in limiter storage key: {key}"
        assert "ip:" in key, f"expected a pseudonymous ip: segment in {key}"
    assert any(k.startswith("LIMITER/fufire_infra_rl:") for k in keys), keys


def test_infra_limit_exceeded_logs_carry_no_raw_client_address(
    probe_client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    """slowapi logs the key func's output — so the pseudonym is what gets logged."""
    with caplog.at_level(logging.WARNING, logger="slowapi"):
        for _ in range(INFRA_LIMIT_AMOUNT + 1):
            probe_client.get("/health")

    limit_logs = [r.getMessage() for r in caplog.records if r.name == "slowapi"]
    assert any("exceeded at endpoint" in m for m in limit_logs), (
        f"no slowapi limit-exceeded log was captured — logs={limit_logs}"
    )
    for message in limit_logs:
        assert PROBE_IP not in message, f"raw client address in limiter log: {message}"


def test_infra_probe_key_is_deterministic_and_separates_clients() -> None:
    """Same address -> same pseudonym for the process lifetime; different -> different."""

    def _request(host: str) -> Request:
        return Request(
            {
                "type": "http",
                "http_version": "1.1",
                "method": "GET",
                "path": "/health",
                "headers": [],
                "client": (host, 12345),
            }
        )

    first = infra_probe_key(_request(PROBE_IP))
    second = infra_probe_key(_request(PROBE_IP))
    other = infra_probe_key(_request("198.51.100.4"))

    assert first == second, "pseudonym is not stable within the process"
    assert first != other, "two distinct clients collapsed into one bucket"
    assert PROBE_IP not in first
    assert first.startswith("ip:")
    # 32 hex characters of an HMAC-SHA256 digest, prefixed with "ip:".
    assert len(first) == len("ip:") + 32
    int(first[3:], 16)  # raises if the digest is not hex
