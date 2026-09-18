"""FUF-156B — authenticated rate limit for POST /internal/api/webhooks/chart.

The webhook is HMAC-protected but was completely unlimited: a single valid
signature could drive unbounded geocoding + BaZi + Western + Fusion work.

Two things make this slice non-trivial, and both are asserted here:

1. **Auth must resolve before the limiter accounts a hit.** Otherwise an
   attacker with no credentials at all could exhaust the one legitimate
   integration's bucket just by sending bad signatures. The design relies on
   FastAPI solving a route's dependencies *before* calling the endpoint
   function, and on ``@limiter.limit`` wrapping exactly that endpoint function.
   ``test_invalid_signatures_never_reach_the_limiter`` proves the ordering with
   a spy on ``Limiter._check_request_limit`` — an integer that must be 0.

2. **The rate identity is one constant, non-secret value.** The repository
   exposes ONE logical ElevenLabs integration, not per-client tenants, and
   nothing request-derived (IP, signature, secret, birth data) may enter a
   limiter key, because slowapi writes that value into both the storage key and
   the WARNING log line it emits on every 429.

Downstream astronomy is stubbed in the fixtures below. Everything that this
slice is about — HMAC verification, dependency resolution, SlowAPI accounting
and the error handlers — runs for real, at the real route boundary.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import time
from types import SimpleNamespace
from typing import Any, Dict

import pytest
from fastapi.testclient import TestClient

from bazi_engine.app import app
from bazi_engine.limiter import (
    WEBHOOK_INTEGRATION_IDENTITY,
    WEBHOOK_INTEGRATION_LIMIT,
    infra_limiter,
    limiter,
)
from bazi_engine.types import Pillar

WEBHOOK_PATH = "/internal/api/webhooks/chart"
SECRET = "fuf156b-test-secret"
LIMIT_PER_MINUTE = 60

# Deliberately PII-shaped, so the privacy assertions have something real to miss.
BIRTH_PAYLOAD: Dict[str, Any] = {
    "birthDate": "1990-05-15",
    "birthTime": "14:30",
    "birthPlace": "Berlin, DE",
    "birthLat": 52.52,
    "birthLon": 13.405,
    "birthTz": "Europe/Berlin",
}


# ── helpers ──────────────────────────────────────────────────────────────────

def sign(body: bytes, *, secret: str = SECRET, age_ms: int = 0) -> str:
    """Build a real ElevenLabs-Signature header: ``t=<ms>,v1=<hex hmac>``."""
    ts = int(time.time() * 1000) - age_ms
    digest = hmac.new(secret.encode(), f"{ts}.".encode() + body, hashlib.sha256).hexdigest()
    return f"t={ts},v1={digest}"


def body_bytes(**overrides: Any) -> bytes:
    payload = dict(BIRTH_PAYLOAD)
    payload.update(overrides)
    return json.dumps(payload).encode()


def post(client: TestClient, body: bytes, **headers: str):
    hdrs = {"content-type": "application/json"}
    hdrs.update({k.replace("_", "-"): v for k, v in headers.items()})
    return client.post(WEBHOOK_PATH, content=body, headers=hdrs)


def post_signed(client: TestClient, body: bytes | None = None):
    body = body_bytes() if body is None else body
    return post(client, body, elevenlabs_signature=sign(body))


def make_client(host: str = "testclient") -> TestClient:
    return TestClient(app, client=(host, 50000))


# ── fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def webhook_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ELEVENLABS_TOOL_SECRET", SECRET)
    monkeypatch.delenv("WEBHOOK_HMAC_ONLY", raising=False)  # default: HMAC-only


@pytest.fixture(autouse=True)
def stub_astronomy(monkeypatch: pytest.MonkeyPatch) -> None:
    """Replace the three heavy compute calls with contract-shaped constants.

    Scope note: this isolates ONLY the downstream astronomy. Auth, dependency
    resolution, the limiter, the response model and the error handlers are the
    real ones — they are what this slice changes.
    """
    import bazi_engine.routers.webhooks as wh

    def fake_western(dt_utc, lat, lon):  # noqa: ANN001
        return {
            "bodies": {
                "Sun": {"zodiac_sign": 1, "is_retrograde": False},
                "Moon": {"zodiac_sign": 4, "is_retrograde": False},
                "Mercury": {"zodiac_sign": 2, "is_retrograde": True},
            },
            "angles": {"Ascendant": 95.5},
        }

    def fake_bazi(inp):  # noqa: ANN001
        return SimpleNamespace(
            pillars=SimpleNamespace(
                year=Pillar(0, 0), month=Pillar(1, 1), day=Pillar(2, 2), hour=Pillar(3, 3)
            ),
            solar_year=1990,
            is_before_lichun=False,
            lichun_next_local_dt=None,
        )

    def fake_fusion(**kwargs: Any) -> Dict[str, Any]:
        return {
            "calibration": {
                "h_calibrated": 0.42,
                "h_raw": 0.68,
                "interpretation_band": "Test band",
            },
            # FUF-166: producer-realistic types. compute_fusion_analysis()
            # returns a rounded float here and a narrative string below; the
            # earlier stub encoded the BROKEN response model instead, which
            # made these 200s false-green over a real HTTP 500.
            "cosmic_state": 0.6816,
            "wu_xing_vectors": {
                "western_planets": {"Holz": 1.0, "Feuer": 0.0},
                "bazi_pillars": {"Metall": 1.0, "Wasser": 0.0},
            },
            "elemental_comparison": {"delta": 0.0},
            "fusion_interpretation": "Kalibrierte Kohärenz: 42.00% (Test band)",
        }

    monkeypatch.setattr(wh, "compute_western_chart", fake_western)
    monkeypatch.setattr(wh, "compute_bazi", fake_bazi)
    monkeypatch.setattr(wh, "compute_fusion_analysis", fake_fusion)


# ── W0: registration ─────────────────────────────────────────────────────────

def test_webhook_is_registered_on_the_shared_application_limiter() -> None:
    """60/minute, on the Redis-capable application limiter — not infra_limiter.

    The webhook is production traffic: when the deployment configures Redis its
    counters must be consistent across replicas. That is the opposite of the
    FUF-156A health/readiness decision, and the distinction is load-bearing.
    """
    from bazi_engine.routers.webhooks import elevenlabs_chart_webhook as fn

    key = f"{fn.__module__}.{fn.__qualname__}"
    assert key in limiter._route_limits, f"{key} not on the application limiter"
    assert key not in infra_limiter._route_limits
    assert key not in infra_limiter._dynamic_route_limits

    limits = [str(lim.limit) for lim in limiter._route_limits[key]]
    assert limits == ["60 per 1 minute"], limits
    assert WEBHOOK_INTEGRATION_LIMIT == "60/minute"


# ── W1: auth before limit ────────────────────────────────────────────────────

def test_invalid_signatures_never_reach_the_limiter(monkeypatch: pytest.MonkeyPatch) -> None:
    """70 bad signatures (> the 60/minute limit) must not touch rate accounting.

    The spy count is the machine-checkable claim: an auth check that ran *after*
    the limiter would make this 70, and the assertion below would read 70 != 0.
    """
    calls: list[str] = []
    original = limiter._check_request_limit

    def spy(request, endpoint_func, in_middleware=True):  # noqa: ANN001
        calls.append(request.url.path)
        return original(request, endpoint_func, in_middleware)

    monkeypatch.setattr(limiter, "_check_request_limit", spy)

    client = make_client()
    codes = {post(client, body_bytes(), elevenlabs_signature="t=1,v1=deadbeef").status_code
             for _ in range(LIMIT_PER_MINUTE + 10)}

    assert codes == {401}, codes
    assert len(calls) == 0, f"limiter accounted {len(calls)} unauthenticated requests"


def test_unauthenticated_flood_leaves_the_full_authenticated_quota(monkeypatch: pytest.MonkeyPatch) -> None:
    """After 70 rejected requests a legitimate caller still has all 60 slots."""
    client = make_client()
    for _ in range(LIMIT_PER_MINUTE + 10):
        assert post(client, body_bytes(), elevenlabs_signature="t=1,v1=bad").status_code == 401

    codes = [post_signed(client).status_code for _ in range(LIMIT_PER_MINUTE)]
    assert codes == [200] * LIMIT_PER_MINUTE, sorted(set(codes))
    assert post_signed(client).status_code == 429


# ── W2/W3: the real authenticated 429 boundary ───────────────────────────────

def test_authenticated_requests_are_limited_at_sixty_per_minute() -> None:
    client = make_client()
    codes = [post_signed(client).status_code for _ in range(LIMIT_PER_MINUTE)]
    assert codes == [200] * LIMIT_PER_MINUTE, sorted(set(codes))

    over = post_signed(client)
    assert over.status_code == 429, over.text


def test_authenticated_429_carries_retry_after_and_the_canonical_envelope() -> None:
    client = make_client()
    for _ in range(LIMIT_PER_MINUTE):
        post_signed(client)

    over = post_signed(client)
    assert over.status_code == 429
    assert over.headers["Retry-After"] == "60"

    body = over.json()
    assert body["error"] == "rate_limit_exceeded"
    assert body["status"] == 429
    assert body["path"] == WEBHOOK_PATH
    assert set(body) >= {"error", "message", "detail", "status", "path", "timestamp", "request_id"}


# ── W4: one logical integration ──────────────────────────────────────────────

def test_two_source_addresses_share_one_integration_bucket() -> None:
    """Intentional: the contract exposes ONE ElevenLabs integration.

    An IP-keyed identity would give each source address its own 60/minute bucket
    and the assertion below would read 200 instead of 429.
    """
    first = make_client("198.51.100.7")
    second = make_client("203.0.113.9")

    codes = [post_signed(first).status_code for _ in range(LIMIT_PER_MINUTE)]
    assert codes == [200] * LIMIT_PER_MINUTE, sorted(set(codes))

    crossed = post_signed(second)
    assert crossed.status_code == 429, (
        "a second source address got its own quota — the rate identity is not constant"
    )


# ── W5: secrets and PII ──────────────────────────────────────────────────────

FORBIDDEN = {
    "the shared secret": SECRET,
    "birthDate": BIRTH_PAYLOAD["birthDate"],
    "birthTime": BIRTH_PAYLOAD["birthTime"],
    "birthPlace": BIRTH_PAYLOAD["birthPlace"],
    "birthLat": str(BIRTH_PAYLOAD["birthLat"]),
    "birthLon": str(BIRTH_PAYLOAD["birthLon"]),
    "the client address": "198.51.100.7",
}


def test_limiter_storage_key_is_the_non_secret_integration_identity(caplog: pytest.LogCaptureFixture) -> None:
    client = make_client("198.51.100.7")
    signature_headers: list[str] = []

    with caplog.at_level(logging.DEBUG, logger="slowapi"):
        for _ in range(LIMIT_PER_MINUTE + 1):
            body = body_bytes()
            header = sign(body)
            signature_headers.append(header)
            post(client, body, elevenlabs_signature=header)

    stored = list(limiter._storage.storage)
    assert stored, "no limiter counters were written at all — the test proved nothing"
    assert any(WEBHOOK_INTEGRATION_IDENTITY in k for k in stored), stored

    logs = "\n".join(r.getMessage() for r in caplog.records)
    assert "ratelimit" in logs, "slowapi logged no rate-limit line — nothing was scanned"

    haystack = "\n".join(stored) + "\n" + logs
    for label, value in FORBIDDEN.items():
        assert value not in haystack, f"{label} leaked into limiter storage keys or logs"
    for header in signature_headers:
        assert header not in haystack, "an ElevenLabs-Signature leaked into storage keys or logs"


def test_fallback_credentials_never_enter_the_limiter_key(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Same guarantee for the X-API-Key / Bearer fallbacks when HMAC-only is off."""
    monkeypatch.setenv("WEBHOOK_HMAC_ONLY", "false")
    client = make_client()

    with caplog.at_level(logging.DEBUG, logger="slowapi"):
        for _ in range(LIMIT_PER_MINUTE + 1):
            post(client, body_bytes(), x_api_key=SECRET, authorization=f"Bearer {SECRET}")

    haystack = "\n".join(limiter._storage.storage) + "\n" + "\n".join(
        r.getMessage() for r in caplog.records
    )
    assert WEBHOOK_INTEGRATION_IDENTITY in haystack
    assert SECRET not in haystack
    assert f"Bearer {SECRET}" not in haystack


# ── W6: auth regression ──────────────────────────────────────────────────────

def test_missing_tool_secret_is_still_503(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ELEVENLABS_TOOL_SECRET", raising=False)
    resp = post_signed(make_client())
    assert resp.status_code == 503
    assert resp.json()["error"] == "service_unavailable"


def test_invalid_hmac_is_still_401() -> None:
    resp = post(make_client(), body_bytes(), elevenlabs_signature="t=1,v1=nope")
    assert resp.status_code == 401
    assert resp.json()["error"] == "unauthorized"


def test_stale_hmac_is_rejected() -> None:
    """Replay protection: a correctly-signed body outside the 5-minute window."""
    body = body_bytes()
    resp = post(make_client(), body, elevenlabs_signature=sign(body, age_ms=600_000))
    assert resp.status_code == 401


def test_signature_over_a_different_body_is_rejected() -> None:
    """The authenticated bytes and the parsed bytes must be the same bytes."""
    signed_for = body_bytes(birthDate="1990-05-15")
    sent = body_bytes(birthDate="1999-01-01")
    resp = post(make_client(), sent, elevenlabs_signature=sign(signed_for))
    assert resp.status_code == 401


def test_valid_hmac_is_accepted_and_returns_the_chart_contract() -> None:
    resp = post_signed(make_client())
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert set(body) == {"western", "eastern", "fusion", "summary", "meta"}
    assert body["meta"]["location"]["lat"] == BIRTH_PAYLOAD["birthLat"]


def test_hmac_only_defaults_to_true_so_api_key_alone_is_rejected() -> None:
    resp = post(make_client(), body_bytes(), x_api_key=SECRET)
    assert resp.status_code == 401


def test_api_key_fallback_still_works_when_hmac_only_is_false(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WEBHOOK_HMAC_ONLY", "false")
    assert post(make_client(), body_bytes(), x_api_key=SECRET).status_code == 200


def test_bearer_fallback_still_works_when_hmac_only_is_false(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WEBHOOK_HMAC_ONLY", "false")
    assert post(
        make_client(), body_bytes(), authorization=f"Bearer {SECRET}"
    ).status_code == 200


def test_malformed_body_under_valid_auth_is_still_400() -> None:
    body = b"{not json"
    resp = post(make_client(), body, elevenlabs_signature=sign(body))
    assert resp.status_code == 400
    assert resp.json()["error"] == "invalid_request"
