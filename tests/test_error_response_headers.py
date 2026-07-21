"""
test_error_response_headers.py — TDD step for Task 10.

Verifies that X-Request-ID, X-API-Version, and X-Response-Time-ms are
present on ALL responses, including error responses (401, 404, 422).

Background: Starlette's BaseHTTPMiddleware.dispatch() is documented to
bypass the dispatch path on unhandled exceptions and routing misses in
some versions. These tests guard against regressions where error
responses lose the middleware-injected headers.

Current state (as of Task 10 discovery): all three error paths carry the
required headers — the middleware is working correctly. Tests are written
as strict assertions so any future regression is caught immediately.
"""
from __future__ import annotations

import os

from fastapi.testclient import TestClient

from bazi_engine.app import app
from bazi_engine.auth import _load_keys

_REQUIRED_HEADERS = ("X-Request-ID", "X-API-Version", "X-Response-Time-ms")


def _make_client() -> TestClient:
    """Return a TestClient that does not re-raise server exceptions."""
    return TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# 401 — missing auth on a /v1/ route (POST with no API key)
# ---------------------------------------------------------------------------

def test_standard_headers_on_401() -> None:
    """POST /v1/calculate/bazi without API key → 401 must carry required headers."""
    os.environ["FUFIRE_REQUIRE_API_KEYS"] = "true"
    os.environ["FUFIRE_API_KEYS"] = "ff_pro_testsecret"
    _load_keys.cache_clear()
    try:
        c = _make_client()
        resp = c.post("/v1/calculate/bazi", json={})
    finally:
        os.environ.pop("FUFIRE_REQUIRE_API_KEYS", None)
        os.environ.pop("FUFIRE_API_KEYS", None)
        _load_keys.cache_clear()

    assert resp.status_code == 401, (
        f"expected 401, got {resp.status_code}"
    )
    missing = [h for h in _REQUIRED_HEADERS if h not in resp.headers]
    assert not missing, (
        f"POST /v1/calculate/bazi status=401: missing headers {missing}"
    )


# ---------------------------------------------------------------------------
# 404 — unknown route
# ---------------------------------------------------------------------------

def test_standard_headers_on_404() -> None:
    """GET /nonexistent-route-xyz → 404 must carry required headers."""
    c = _make_client()
    resp = c.get("/nonexistent-route-xyz")

    assert resp.status_code == 404, (
        f"expected 404, got {resp.status_code}"
    )
    missing = [h for h in _REQUIRED_HEADERS if h not in resp.headers]
    assert not missing, (
        f"GET /nonexistent-route-xyz status=404: missing headers {missing}"
    )


# ---------------------------------------------------------------------------
# 422 — valid auth, invalid/missing body
# ---------------------------------------------------------------------------

def test_standard_headers_on_422() -> None:
    """POST /v1/calculate/bazi with empty body → 422 must carry required headers."""
    os.environ["FUFIRE_REQUIRE_API_KEYS"] = "true"
    os.environ["FUFIRE_API_KEYS"] = "ff_pro_testsecret"
    _load_keys.cache_clear()
    try:
        c = _make_client()
        resp = c.post(
            "/v1/calculate/bazi",
            headers={"X-API-Key": "ff_pro_testsecret"},
            json={},
        )
    finally:
        os.environ.pop("FUFIRE_REQUIRE_API_KEYS", None)
        os.environ.pop("FUFIRE_API_KEYS", None)
        _load_keys.cache_clear()

    assert resp.status_code == 422, (
        f"expected 422, got {resp.status_code}"
    )
    missing = [h for h in _REQUIRED_HEADERS if h not in resp.headers]
    assert not missing, (
        f"POST /v1/calculate/bazi status=422: missing headers {missing}"
    )
