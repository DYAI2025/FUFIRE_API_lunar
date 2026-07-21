# tests/test_webhook_routes.py
"""
Webhook routing truth tests.

The webhook router is declared with prefix="/api" in webhooks.py and is mounted
at prefix="/internal" in app.py.  The resulting runtime path is therefore:

    /internal/api/webhooks/chart

NOT /internal/webhooks/chart (missing the router-level /api segment) and
NOT /api/webhooks/chart (missing the app-level /internal prefix).

These tests document and enforce that routing reality.
"""
from fastapi.testclient import TestClient

from bazi_engine.app import app

client = TestClient(app)


def test_internal_api_webhook_path_reachable():
    """Runtime webhook path /internal/api/webhooks/chart must return non-404.

    The full path is composed from:
        app.include_router(webhooks.router, prefix="/internal")  # app.py:336
        router = APIRouter(prefix="/api", ...)                   # webhooks.py:24
        @router.post("/webhooks/chart", ...)                     # webhooks.py:96
    => /internal + /api + /webhooks/chart = /internal/api/webhooks/chart
    """
    resp = client.post(
        "/internal/api/webhooks/chart",
        json={"type": "test"},
        headers={"X-Webhook-Secret": "invalid"},
    )
    # Should reach the handler — 401/403/422/503 all acceptable, 404 is not
    assert resp.status_code != 404, (
        f"Webhook not found at /internal/api/webhooks/chart (got {resp.status_code}). "
        "Check that webhooks.router prefix='/api' is still present in webhooks.py "
        "and that app.py mounts it at prefix='/internal'."
    )


def test_short_internal_webhook_path_is_not_routed():
    """The path /internal/webhooks/chart (missing /api segment) must 404.

    This guards against accidental documentation that drops the router-level
    /api prefix and points callers at a non-existent path.
    """
    resp = client.post(
        "/internal/webhooks/chart",
        json={"type": "test"},
        headers={"X-Webhook-Secret": "invalid"},
    )
    assert resp.status_code == 404, (
        f"Expected 404 for /internal/webhooks/chart (missing /api segment), "
        f"got {resp.status_code}. If the route moved, update this test and "
        "the CLAUDE.md routing table."
    )


def test_old_api_webhook_path_not_the_canonical_url():
    """The path /api/webhooks/chart must NOT be the canonical integration URL.

    The /internal prefix is intentional: it gates this endpoint as an
    internal-only surface, separate from the public /v1/* API.
    This test documents the actual behavior of the legacy /api path.
    """
    resp = client.post("/api/webhooks/chart", json={"type": "test"})
    assert resp.status_code == 404, (
        f"/api/webhooks/chart must not be routed (expected 404, got {resp.status_code}). "
        "The canonical path is /internal/api/webhooks/chart."
    )


def test_webhook_route_not_in_public_openapi_schema():
    """Webhook router is include_in_schema=False — must not appear in OpenAPI paths."""
    app.openapi_schema = None
    schema = app.openapi()
    webhook_paths = [p for p in schema.get("paths", {}) if "webhooks" in p]
    assert not webhook_paths, (
        f"Webhook paths unexpectedly in public OpenAPI schema: {webhook_paths}. "
        "Ensure app.include_router(webhooks.router, ..., include_in_schema=False) "
        "is present in app.py."
    )
