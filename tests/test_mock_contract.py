"""Contract tests: verify mock server responses match real API schemas.

Ensures the mock server stays in sync with the production API contract.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tests.mock_server import MOCK_EXCLUSIONS
from tests.mock_server import app as mock_app

mock_client = TestClient(mock_app)

SPEC_PATH = Path(__file__).parent.parent / "spec" / "openapi" / "openapi.json"


@pytest.fixture(scope="module")
def openapi_spec() -> dict:
    return json.loads(SPEC_PATH.read_text())


class TestMockContractAlignment:
    """Mock responses must include the same top-level keys as real snapshots."""

    def test_bazi_response_keys(self):
        r = mock_client.post("/calculate/bazi", json={"date": "2024-01-01T12:00:00"})
        assert r.status_code == 200
        data = r.json()
        assert "pillars" in data
        assert "dates" in data
        assert "precision" in data

    def test_western_response_keys(self):
        r = mock_client.post("/calculate/western", json={"date": "2024-01-01T12:00:00"})
        assert r.status_code == 200
        data = r.json()
        assert "bodies" in data
        assert "houses" in data
        assert "aspects" in data

    def test_fusion_response_keys(self):
        r = mock_client.post("/calculate/fusion", json={"date": "2024-01-01T12:00:00"})
        assert r.status_code == 200
        data = r.json()
        assert "harmony_index" in data
        assert "wu_xing_vectors" in data

    def test_wuxing_response_keys(self):
        r = mock_client.post("/calculate/wuxing", json={"date": "2024-01-01T12:00:00"})
        assert r.status_code == 200
        data = r.json()
        assert "wu_xing_vector" in data
        assert "dominant_element" in data

    def test_bazi_wuxing_response_is_derived_from_frozen_bazi_fixture(self):
        r = mock_client.post("/calculate/bazi/wuxing", json={})

        assert r.status_code == 200
        data = r.json()
        assert data["basis"] == "bazi_four_pillars"
        assert data["quality_flags"]["ephemeris_mode"] == "MOSEPH"
        assert set(data["pillars"]) == {"year", "month", "day", "hour"}
        assert sum(data["wu_xing_vector"].values()) > 0


class TestMockHeaders:
    """Mock server must return the same standard headers as production."""

    STANDARD_HEADERS = ["x-request-id", "x-api-version", "x-response-time-ms"]

    @pytest.mark.parametrize("path", [
        "/calculate/bazi",
        "/calculate/western",
        "/calculate/fusion",
        "/calculate/wuxing",
        "/calculate/tst",
        "/validate",
    ])
    def test_standard_headers_present(self, path: str):
        r = mock_client.post(path, json={})
        for header in self.STANDARD_HEADERS:
            assert header in r.headers, f"Missing header {header} on {path}"

    def test_mock_header_marks_responses(self):
        r = mock_client.post("/calculate/bazi", json={})
        assert r.headers.get("x-mock-server") == "true"


class TestMockInfoEndpoints:
    """Info endpoints must return the same shape."""

    def test_health(self):
        r = mock_client.get("/health")
        assert r.status_code == 200
        assert r.json()["status"] == "healthy"

    def test_root(self):
        r = mock_client.get("/")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ok"
        assert "service" in data

    def test_build(self):
        r = mock_client.get("/build")
        assert r.status_code == 200
        assert "version" in r.json()

    def test_ready(self):
        r = mock_client.get("/ready")
        assert r.status_code == 200


class TestMockV1Mirrors:
    """V1 prefixed routes must also work."""

    @pytest.mark.parametrize("path", [
        "/v1/health",
        "/v1/",
        "/v1/build",
        "/v1/ready",
    ])
    def test_v1_info_endpoints(self, path: str):
        r = mock_client.get(path)
        assert r.status_code == 200

    @pytest.mark.parametrize("path", [
        "/v1/calculate/bazi",
        "/v1/calculate/western",
        "/v1/calculate/fusion",
        "/v1/calculate/wuxing",
        "/v1/calculate/bazi/wuxing",
    ])
    def test_v1_calculation_endpoints(self, path: str):
        r = mock_client.post(path, json={})
        assert r.status_code == 200


class TestMockScenarioControl:
    """Scenario switching must work."""

    def test_list_scenarios(self):
        r = mock_client.get("/mock/scenarios")
        assert r.status_code == 200
        data = r.json()
        assert "default" in data["available"]
        assert "hilat" in data["available"]

    def test_switch_unknown_scenario_returns_404(self):
        r = mock_client.post("/mock/scenario/nonexistent")
        assert r.status_code == 404

    def test_set_latency(self):
        r = mock_client.post("/mock/latency/0")
        assert r.status_code == 200
        assert r.json()["latency_ms"] == 0


class TestMockOpenApiAlignment:
    """Verify mock endpoints cover all paths in the OpenAPI spec."""

    def test_all_calculation_paths_mocked(self, openapi_spec: dict):
        spec_calc_paths = [
            p for p in openapi_spec["paths"]
            if p.startswith("/calculate/") and "post" in openapi_spec["paths"][p]
        ]
        for path in spec_calc_paths:
            r = mock_client.post(path, json={})
            assert r.status_code == 200, f"Mock missing: POST {path}"

    def test_all_info_paths_mocked(self, openapi_spec: dict):
        info_paths = ["/health", "/ready", "/build", "/"]
        for path in info_paths:
            r = mock_client.get(path)
            assert r.status_code == 200, f"Mock missing: GET {path}"

    def test_every_unmocked_v2_path_has_an_explicit_precision_reason(self, openapi_spec: dict):
        v2_post_paths = {
            path for path, operations in openapi_spec["paths"].items()
            if path.startswith("/v2/") and "post" in operations
        }

        assert v2_post_paths == set(MOCK_EXCLUSIONS)
        assert all("real locked ephemeris boundary" in reason for reason in MOCK_EXCLUSIONS.values())
