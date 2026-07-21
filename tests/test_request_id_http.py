"""FUFIRE-009: X-Request-ID must honour the contract (format: uuid).

``spec/openapi/openapi.json`` declares ``X-Request-ID`` with
``"format": "uuid"`` on every endpoint; the runtime previously echoed
arbitrary client bytes into the response header, the error-envelope
``request_id`` field and the logs.

WS-A convention: all assertions live at the real HTTP boundary via
``TestClient`` — never on middleware internals.
"""
import uuid

from fastapi.testclient import TestClient

from bazi_engine.app import app

client = TestClient(app)


def test_valid_uuid_is_echoed() -> None:
    """A contract-conforming client id round-trips unchanged."""
    rid = str(uuid.uuid4())
    resp = client.get("/health", headers={"X-Request-ID": rid})
    assert resp.status_code == 200
    assert resp.headers["X-Request-ID"] == rid


def test_garbage_request_id_is_replaced_with_fresh_uuid() -> None:
    """Attacker bytes (oversized + markup) must NOT be reflected."""
    garbage = "A" * 4096 + "<script>"
    resp = client.get("/health", headers={"X-Request-ID": garbage})
    echoed = resp.headers["X-Request-ID"]
    assert echoed != garbage
    uuid.UUID(echoed)  # must parse — i.e. NOT the attacker bytes


def test_error_envelope_request_id_is_uuid() -> None:
    """The 422 envelope always carries request_id (app._error_body);
    with a non-UUID client header it must be a freshly minted UUID,
    not the client string."""
    resp = client.post(
        "/calculate/bazi",
        json={"nonsense": True},
        headers={"X-Request-ID": "not-a-uuid"},
    )
    assert resp.status_code == 422
    body = resp.json()
    assert "request_id" in body
    assert body["request_id"] != "not-a-uuid"
    uuid.UUID(body["request_id"])  # contract: format uuid

    # Header and envelope must agree (single trace id per request).
    assert resp.headers["X-Request-ID"] == body["request_id"]
