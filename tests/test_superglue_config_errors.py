"""
tests/test_superglue_config_errors.py — TDD "red" step for Task 8.

Documents the *desired* behavior: when SUPERGLUE_API_KEY is absent, every
Superglue proxy endpoint should return HTTP 503 with a safe error body.

Current behavior: the missing key triggers a RuntimeError in
``services/superglue_client.call_hook`` which propagates as an unhandled
500 Internal Server Error.  Task 9 will add the mapping that turns these
xfail tests green.

All tests are marked ``xfail(strict=True)`` so they fail loudly in CI
until Task 9 is implemented.
"""
from __future__ import annotations

import os
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from bazi_engine.app import app
from bazi_engine.auth import _load_keys

# A syntactically-valid API key recognised by auth.py (ff_ prefix → "pro" tier)
_VALID_KEY = "ff_pro_testsecret"

# Routes under test — actual paths as mounted in app.py
_ROUTE_PROFILE = "/v1/profile/testuser"
_ROUTE_DAILY = "/v1/daily/testuser"
_ROUTE_CHART = "/v1/profile/testuser/chart"


@pytest.fixture
def client_no_superglue():
    """TestClient with API-key auth enabled but SUPERGLUE_API_KEY absent.

    * ``FUFIRE_REQUIRE_API_KEYS=true`` + ``FUFIRE_API_KEYS=<key>`` — auth is
      active so we can reach the superglue routes without a 401/403.
    * ``SUPERGLUE_API_KEY`` is explicitly removed from the environment.
    * ``raise_server_exceptions=False`` — keeps the client from re-raising
      the 500 so we can inspect the status code ourselves.
    """
    env_overrides = {
        "FUFIRE_REQUIRE_API_KEYS": "true",
        "FUFIRE_API_KEYS": _VALID_KEY,
        # Include the key so patch.dict registers it and restores the original
        # value on exit; we pop it immediately after to make it truly absent.
        "SUPERGLUE_API_KEY": "",
    }
    with patch.dict(os.environ, env_overrides, clear=False):
        os.environ.pop("SUPERGLUE_API_KEY", None)  # empty string != absent
        _load_keys.cache_clear()  # flush stale lru_cache before the test
        app.openapi_schema = None  # invalidate cached schema
        yield TestClient(app, raise_server_exceptions=False)
        _load_keys.cache_clear()  # restore clean state after the test


# ---------------------------------------------------------------------------
# Tests — verify 503 is returned when SUPERGLUE_API_KEY is absent (Task 9)
# ---------------------------------------------------------------------------


def test_profile_returns_503_when_no_superglue_key(client_no_superglue: TestClient) -> None:
    """GET /v1/profile/{user_id} must respond 503 when the key is absent."""
    resp = client_no_superglue.get(
        _ROUTE_PROFILE,
        headers={"X-API-Key": _VALID_KEY},
    )
    assert resp.status_code == 503, (
        f"Expected 503 Service Unavailable, got {resp.status_code}: {resp.text}"
    )
    body = resp.json()
    assert body.get("error") == "service_unavailable", (
        f"Expected error='service_unavailable' in body, got: {body}"
    )
    # The raw env-var name must NOT be leaked in the response body
    assert "SUPERGLUE_API_KEY" not in resp.text, (
        "Response body leaks the secret env-var name: SUPERGLUE_API_KEY"
    )


def test_daily_returns_503_when_no_superglue_key(client_no_superglue: TestClient) -> None:
    """GET /v1/daily/{user_id} must respond 503 when the key is absent."""
    resp = client_no_superglue.get(
        _ROUTE_DAILY,
        headers={"X-API-Key": _VALID_KEY},
    )
    assert resp.status_code == 503, (
        f"Expected 503 Service Unavailable, got {resp.status_code}: {resp.text}"
    )
    body = resp.json()
    assert body.get("error") == "service_unavailable", (
        f"Expected error='service_unavailable' in body, got: {body}"
    )
    assert "SUPERGLUE_API_KEY" not in resp.text, (
        "Response body leaks the secret env-var name: SUPERGLUE_API_KEY"
    )


def test_chart_trigger_returns_503_when_no_superglue_key(client_no_superglue: TestClient) -> None:
    """POST /v1/profile/{user_id}/chart must respond 503 when the key is absent."""
    resp = client_no_superglue.post(
        _ROUTE_CHART,
        headers={"X-API-Key": _VALID_KEY},
        json={"force_recalculate": False},
    )
    assert resp.status_code == 503, (
        f"Expected 503 Service Unavailable, got {resp.status_code}: {resp.text}"
    )
    body = resp.json()
    assert body.get("error") == "service_unavailable", (
        f"Expected error='service_unavailable' in body, got: {body}"
    )
    assert "SUPERGLUE_API_KEY" not in resp.text, (
        "Response body leaks the secret env-var name: SUPERGLUE_API_KEY"
    )
