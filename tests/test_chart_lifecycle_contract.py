"""
tests/test_chart_lifecycle_contract.py

Ensures /api/chart lifecycle policy: accessible but deprecated and NOT duplicated at /v1.
"""
import pytest
from fastapi.testclient import TestClient

from bazi_engine.app import app

client = TestClient(app, raise_server_exceptions=False)


def test_chart_endpoint_reachable_at_legacy_path():
    """POST /chart must be reachable (non-404) — internal legacy endpoint."""
    resp = client.post("/chart", json={})
    assert resp.status_code != 404, (
        f"Legacy /chart returned 404 — should be reachable (got {resp.status_code})"
    )


def test_chart_endpoint_not_at_v1_path():
    """POST /v1/chart must NOT exist — /chart has no v1 alias."""
    resp = client.post("/v1/chart", json={})
    assert resp.status_code == 404, (
        f"/v1/chart should not exist but got {resp.status_code}"
    )


def test_chart_operation_marked_deprecated_in_schema():
    """If /chart appears in OpenAPI schema, it must be marked deprecated."""
    schema = app.openapi()
    # Find chart path — could be /chart or /api/chart
    chart_path = None
    for path in schema.get("paths", {}):
        if "chart" in path.lower() and "webhook" not in path.lower() and "superglue" not in path.lower() and "profile" not in path.lower():
            chart_path = path
            break
    if chart_path is None:
        pytest.skip("Chart endpoint not in public schema (include_in_schema=False) — acceptable")
    op = schema["paths"][chart_path].get("post", {})
    assert op.get("deprecated") is True, (
        f"Chart operation at {chart_path} is in public schema but not marked deprecated=True"
    )
