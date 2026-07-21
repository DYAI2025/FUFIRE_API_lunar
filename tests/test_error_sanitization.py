"""Tests that API error responses never leak internal details."""
from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from bazi_engine.app import app

client = TestClient(app)

BAZI_PAYLOAD = {
    "date": "2024-02-10T14:30:00",
    "tz": "Europe/Berlin",
    "lon": 13.405,
    "lat": 52.52,
}

# Map each endpoint to the router module that owns resolve_local_iso
_ENDPOINT_PATCH_TARGETS = {
    "/calculate/bazi": "bazi_engine.routers.bazi.resolve_local_iso",
    "/calculate/western": "bazi_engine.routers.western.resolve_local_iso",
    "/calculate/fusion": "bazi_engine.routers.fusion.resolve_local_iso",
    "/calculate/wuxing": "bazi_engine.routers.fusion.resolve_local_iso",
}


class TestErrorSanitization:
    """Verify that 500 responses never contain raw exception text."""

    @pytest.mark.parametrize("endpoint", [
        "/calculate/bazi",
        "/calculate/western",
        "/calculate/fusion",
        "/calculate/wuxing",
    ])
    def test_500_does_not_leak_exception_message(self, endpoint):
        """Internal errors must not echo raw Python exceptions to clients."""
        secret_msg = "SECRET_INTERNAL_PATH_/opt/ephemeris/sepl_18.se1"
        target = _ENDPOINT_PATCH_TARGETS[endpoint]

        with patch(target, side_effect=RuntimeError(secret_msg)):
            r = client.post(endpoint, json=BAZI_PAYLOAD)

        assert r.status_code == 500
        body = r.json()
        assert secret_msg not in str(body), (
            f"Error response leaked internal exception: {body}"
        )
