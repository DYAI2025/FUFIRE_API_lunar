"""Regression tests: FuFirE rebranding strings are correct."""
from __future__ import annotations

from fastapi.testclient import TestClient

from bazi_engine.app import app

client = TestClient(app)


class TestFuFireBranding:
    """Every user-facing string says FuFirE, not BAFE or bazi_engine_v2."""

    def test_root_service_name(self):
        r = client.get("/")
        assert r.status_code == 200
        data = r.json()
        assert data["service"] == "fufire"

    def test_health_returns_engine_name(self):
        r = client.get("/health")
        assert r.status_code == 200
        data = r.json()
        assert data["engine"] == "FuFirE"
        assert "version" in data

    def test_openapi_title_is_fufire(self):
        r = client.get("/openapi.json")
        assert r.status_code == 200
        data = r.json()
        assert "FuFirE" in data["info"]["title"]

    def test_openapi_description_mentions_fufire(self):
        r = client.get("/openapi.json")
        data = r.json()
        assert "FuFirE" in data["info"]["description"]
