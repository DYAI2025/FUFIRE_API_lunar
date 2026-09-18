"""FUF-166 — the real ElevenLabs webhook response contract.

``POST /internal/api/webhooks/chart`` maps the producer's values straight into
``WebhookChartResponse``::

    "cosmicState":    fusion["cosmic_state"]          # producer: float
    "interpretation": fusion["fusion_interpretation"] # producer: str

``WebhookFusionSection`` declared ``cosmicState: str`` and
``interpretation: Dict[str, Any]``, so every valid authenticated request with a
real Fusion calculation failed FastAPI's response validation and the integration
got HTTP 500. No existing test caught it: the routing test only asserts
``!= 404``, and the FUF-156B rate-limit stub reproduced the *broken model shape*
instead of the producer's shape, which made its 200s false-green.

This module closes that gap at the only place the claim can be proven — the real
HTTP boundary:

* the real FastAPI app and its real routing/mount prefixes,
* real webhook HMAC authentication (``require_webhook_auth``),
* the real ``@limiter.limit`` wrapper,
* real ``compute_western_chart`` / ``compute_bazi`` / ``compute_fusion_analysis``,
* real Pydantic response-model validation.

Nothing on that list is stubbed. ``birthLat``/``birthLon``/``birthTz`` are
supplied directly so the request needs no outbound geocoding, and a poisoned
``geocode_place`` proves that it made none.

The client runs with ``raise_server_exceptions=False`` on purpose: that is what
the ElevenLabs integration actually sees. A ``ResponseValidationError`` then
surfaces as the HTTP 500 it really is, rather than as a re-raised exception in
the test process.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import time
from typing import Any, Dict, List

import pytest
from fastapi.testclient import TestClient

import bazi_engine.routers.webhooks as wh
from bazi_engine.app import app
from bazi_engine.routers.webhooks import WebhookChartResponse

WEBHOOK_PATH = "/internal/api/webhooks/chart"
SECRET = "fuf166-contract-secret"

# Direct coordinates + timezone: no birthPlace, therefore no geocoding branch.
BIRTH_PAYLOAD: Dict[str, Any] = {
    "birthDate": "1990-05-15",
    "birthTime": "14:30",
    "birthLat": 52.52,
    "birthLon": 13.405,
    "birthTz": "Europe/Berlin",
}


# ── helpers ──────────────────────────────────────────────────────────────────

def sign(body: bytes, *, secret: str = SECRET) -> str:
    """Build a real ElevenLabs-Signature header: ``t=<ms>,v1=<hex hmac>``."""
    ts = int(time.time() * 1000)
    digest = hmac.new(secret.encode(), f"{ts}.".encode() + body, hashlib.sha256).hexdigest()
    return f"t={ts},v1={digest}"


def post_real(client: TestClient):
    body = json.dumps(BIRTH_PAYLOAD).encode()
    return client.post(
        WEBHOOK_PATH,
        content=body,
        headers={"content-type": "application/json", "elevenlabs-signature": sign(body)},
    )


# ── fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def webhook_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ELEVENLABS_TOOL_SECRET", SECRET)
    monkeypatch.delenv("WEBHOOK_HMAC_ONLY", raising=False)  # default: HMAC-only


@pytest.fixture(autouse=True)
def no_outbound_geocoding(monkeypatch: pytest.MonkeyPatch) -> List[str]:
    """Poison ``geocode_place`` so any outbound lookup is visible, not silent."""
    calls: List[str] = []

    async def forbidden(place: str, *args: Any, **kwargs: Any) -> Dict[str, Any]:
        calls.append(place)
        raise AssertionError(f"outbound geocoding attempted for {place!r}")

    monkeypatch.setattr(wh, "geocode_place", forbidden)
    return calls


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture()
def real_fusion(monkeypatch: pytest.MonkeyPatch) -> List[Dict[str, Any]]:
    """Record the REAL ``compute_fusion_analysis`` output — a pass-through spy.

    This is not a stub: the genuine function runs and its genuine return value
    reaches the router. Recording it lets the assertions below compare the HTTP
    body against the producer's own values instead of against a hand-written
    expectation.
    """
    captured: List[Dict[str, Any]] = []
    producer = wh.compute_fusion_analysis

    def recording(**kwargs: Any) -> Dict[str, Any]:
        result = producer(**kwargs)
        captured.append(result)
        return result

    monkeypatch.setattr(wh, "compute_fusion_analysis", recording)
    return captured


# ── T1: the real authenticated request succeeds ──────────────────────────────

def test_real_authenticated_request_returns_200(
    client: TestClient, no_outbound_geocoding: List[str]
) -> None:
    """A valid HMAC request with a real Fusion calculation must be HTTP 200.

    Before FUF-166 this was HTTP 500: response validation rejected the
    producer's ``cosmic_state`` float against ``cosmicState: str`` and its
    ``fusion_interpretation`` string against ``interpretation: Dict[str, Any]``.
    """
    resp = post_real(client)

    assert resp.status_code == 200, resp.text
    assert no_outbound_geocoding == [], "the request performed outbound geocoding"
    assert set(resp.json()) == {"western", "eastern", "fusion", "summary", "meta"}


# ── T2: the body validates against the declared response model ───────────────

def test_response_validates_against_the_declared_response_model(client: TestClient) -> None:
    resp = post_real(client)
    assert resp.status_code == 200, resp.text

    model = WebhookChartResponse.model_validate(resp.json())
    assert isinstance(model.fusion.cosmicState, float)
    assert isinstance(model.fusion.interpretation, str)


# ── T3: the two disputed field types, at the HTTP boundary ───────────────────

def test_cosmic_state_is_a_float_at_the_http_boundary(client: TestClient) -> None:
    """Asserted on the parsed HTTP body, not on the producer's return value."""
    resp = post_real(client)
    assert resp.status_code == 200, resp.text

    cosmic_state = resp.json()["fusion"]["cosmicState"]
    assert isinstance(cosmic_state, float), (type(cosmic_state).__name__, cosmic_state)
    assert not isinstance(cosmic_state, bool)


def test_interpretation_is_a_string_at_the_http_boundary(client: TestClient) -> None:
    resp = post_real(client)
    assert resp.status_code == 200, resp.text

    interpretation = resp.json()["fusion"]["interpretation"]
    assert isinstance(interpretation, str), (type(interpretation).__name__, interpretation)
    assert interpretation.strip(), "the narrative string is empty"


# ── T4: FUF-147 claim safety is untouched ────────────────────────────────────

def test_fuf147_claim_safety_fields_stay_calibrated(
    client: TestClient, real_fusion: List[Dict[str, Any]]
) -> None:
    """The voice-facing values must still come from ``calibration``, not from raw H.

    ``harmonyIndex`` is the calibrated value, ``harmonyIndexRaw`` stays exposed
    separately as the labeled expert diagnostic, and ``harmonyInterpretation`` is
    the calibrated band — never a threshold verdict on the raw index.
    """
    resp = post_real(client)
    assert resp.status_code == 200, resp.text

    assert len(real_fusion) == 1, "the real producer did not run exactly once"
    calibration = real_fusion[0]["calibration"]
    raw_harmony = real_fusion[0]["harmony_index"]["harmony_index"]
    fusion = resp.json()["fusion"]

    assert fusion["harmonyIndex"] == pytest.approx(calibration["h_calibrated"])
    assert fusion["harmonyIndexRaw"] == pytest.approx(calibration["h_raw"])
    assert calibration["h_raw"] == pytest.approx(raw_harmony)
    assert fusion["harmonyInterpretation"] == calibration["interpretation_band"]

    # The raw index is empirically >= 0.5 and must not be the spoken judgment.
    assert fusion["harmonyIndex"] != pytest.approx(raw_harmony), (
        "harmonyIndex collapsed onto the raw harmony index — FUF-147 containment lost"
    )
    assert 0.0 <= fusion["harmonyIndex"] <= 1.0
    assert resp.json()["summary"]["harmonie"] == f"{calibration['h_calibrated']:.0%}"


# ── T5: the narrative stays the producer's own string ────────────────────────

def test_interpretation_is_the_producers_narrative_verbatim(
    client: TestClient, real_fusion: List[Dict[str, Any]]
) -> None:
    """Not wrapped, not replaced, not re-derived — byte-identical to the producer."""
    resp = post_real(client)
    assert resp.status_code == 200, resp.text

    assert len(real_fusion) == 1
    produced = real_fusion[0]["fusion_interpretation"]
    assert isinstance(produced, str)
    assert resp.json()["fusion"]["interpretation"] == produced
