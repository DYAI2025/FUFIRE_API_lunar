"""Integration tests for Superglue proxy endpoints."""
import httpx
import pytest
import respx
from starlette.testclient import TestClient


@pytest.fixture(autouse=True)
def env(monkeypatch):
    monkeypatch.setenv("SUPERGLUE_API_KEY", "tok_test")
    monkeypatch.setenv("FUFIRE_REQUIRE_API_KEYS", "false")
    monkeypatch.delenv("FUFIRE_API_KEYS", raising=False)
    # Required for CORS middleware initialization
    monkeypatch.setenv(
        "CORS_ALLOWED_ORIGINS",
        "https://bazodiac.space,http://localhost:3000",
    )


@pytest.fixture
def client():
    from bazi_engine.app import app
    return TestClient(app)


@respx.mock
def test_get_profile_returns_superglue_response(client):
    respx.post(
        "https://api.superglue.ai/v1/hooks/bazodiac-elevenlabs-context?token=tok_test"
    ).mock(return_value=httpx.Response(200, json={"user_id": "u_1", "context": "abc"}))

    resp = client.get("/api/profile/u_1")

    assert resp.status_code == 200
    assert resp.json()["user_id"] == "u_1"


@respx.mock
def test_get_daily_returns_superglue_response(client):
    respx.post(
        "https://api.superglue.ai/v1/hooks/bazodiac-daily-transit?token=tok_test"
    ).mock(return_value=httpx.Response(200, json={"date": "2026-04-06", "forecast": "good"}))

    resp = client.get("/api/daily/u_1")

    assert resp.status_code == 200
    assert resp.json()["date"] == "2026-04-06"


@respx.mock
def test_post_chart_returns_superglue_response(client):
    respx.post(
        "https://api.superglue.ai/v1/hooks/bazodiac-user-chart?token=tok_test"
    ).mock(return_value=httpx.Response(200, json={"chart_id": "c_99", "cached": False}))

    resp = client.post("/api/profile/u_1/chart", json={"force_recalculate": False})

    assert resp.status_code == 200
    assert resp.json()["chart_id"] == "c_99"


@respx.mock
def test_post_chart_omitted_body_defaults_to_no_force(client):
    """Omitting the request body must succeed and default force_recalculate=False."""
    route = respx.post(
        "https://api.superglue.ai/v1/hooks/bazodiac-user-chart?token=tok_test"
    ).mock(return_value=httpx.Response(200, json={"chart_id": "c_100", "cached": True}))

    resp = client.post("/api/profile/u_1/chart")

    assert resp.status_code == 200
    assert resp.json()["chart_id"] == "c_100"
    # Verify force_recalculate=false was forwarded
    import json as _json
    body = _json.loads(route.calls.last.request.content)
    assert body["force_recalculate"] is False


@respx.mock
def test_post_chart_force_recalculate_true(client):
    """force_recalculate=true must be forwarded to Superglue."""
    route = respx.post(
        "https://api.superglue.ai/v1/hooks/bazodiac-user-chart?token=tok_test"
    ).mock(return_value=httpx.Response(200, json={"chart_id": "c_101", "cached": False}))

    resp = client.post("/api/profile/u_1/chart", json={"force_recalculate": True})

    assert resp.status_code == 200
    import json as _json
    body = _json.loads(route.calls.last.request.content)
    assert body["force_recalculate"] is True


@respx.mock
def test_get_profile_upstream_502_returns_502(client):
    respx.post(
        "https://api.superglue.ai/v1/hooks/bazodiac-elevenlabs-context?token=tok_test"
    ).mock(return_value=httpx.Response(502))

    resp = client.get("/api/profile/u_1")

    assert resp.status_code == 502


@respx.mock
def test_get_profile_upstream_timeout_returns_504(client):
    respx.post(
        "https://api.superglue.ai/v1/hooks/bazodiac-elevenlabs-context?token=tok_test"
    ).mock(side_effect=httpx.TimeoutException("timeout"))

    resp = client.get("/api/profile/u_1")

    assert resp.status_code == 504


def test_get_profile_rejects_invalid_user_id(client):
    """user_id with special chars should return 422."""
    resp = client.get("/api/profile/bad!user")
    assert resp.status_code == 422


def test_get_daily_rejects_overlength_user_id(client):
    """user_id longer than 128 chars should return 422."""
    resp = client.get(f"/api/daily/{'x' * 129}")
    assert resp.status_code == 422


@respx.mock
def test_v1_profile_path_works(client):
    """v1 route is at /v1/profile/{user_id}, not /v1/api/profile/{user_id}."""
    respx.post(
        "https://api.superglue.ai/v1/hooks/bazodiac-elevenlabs-context?token=tok_test"
    ).mock(return_value=httpx.Response(200, json={"ok": True}))

    resp = client.get("/v1/profile/u_1")
    assert resp.status_code == 200


def test_v1_double_prefix_is_gone(client):
    """The old /v1/api/ double-prefix path must NOT exist."""
    resp = client.get("/v1/api/profile/u_1")
    assert resp.status_code == 404
