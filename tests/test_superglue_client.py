"""Tests for Superglue hook client."""
import asyncio

import httpx
import pytest
import respx


@pytest.fixture(autouse=True)
def set_token(monkeypatch):
    monkeypatch.setenv("SUPERGLUE_API_KEY", "test-token-123")


@respx.mock
def test_call_hook_success():
    from bazi_engine.services.superglue_client import call_hook

    route = respx.post(
        "https://api.superglue.ai/v1/hooks/bazodiac-elevenlabs-context?token=test-token-123"
    ).mock(return_value=httpx.Response(200, json={"context": "hello"}))

    result = asyncio.run(call_hook("bazodiac-elevenlabs-context", {"user_id": "u_123"}))

    assert result == {"context": "hello"}
    assert route.called


@respx.mock
def test_call_hook_upstream_error():
    from bazi_engine.services.superglue_client import call_hook

    respx.post(
        "https://api.superglue.ai/v1/hooks/bazodiac-daily-transit?token=test-token-123"
    ).mock(return_value=httpx.Response(502, json={"error": "bad gateway"}))

    with pytest.raises(httpx.HTTPStatusError) as exc_info:
        asyncio.run(call_hook("bazodiac-daily-transit", {"user_id": "u_123"}))

    assert exc_info.value.response.status_code == 502


def test_call_hook_missing_token(monkeypatch):
    from bazi_engine.services.superglue_client import SuperglueConfigurationError, call_hook
    monkeypatch.delenv("SUPERGLUE_API_KEY", raising=False)

    with pytest.raises(SuperglueConfigurationError, match="not configured"):
        asyncio.run(call_hook("any-hook", {}))
