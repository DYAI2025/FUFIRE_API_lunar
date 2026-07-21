"""
Security findings regression tests.
Each test documents one finding from the 2026-05-16 security assessment.
"""
from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from bazi_engine.app import app

client = TestClient(app, raise_server_exceptions=False)

_API_KEY_HEADERS = {}  # dev-mode: no keys configured → no auth needed


# ── ERR-1: Error envelope consistency ─────────────────────────────────────────

def test_validate_valueerror_returns_structured_envelope():
    """validate.py ValueError must produce error != 'http_error' — a specific code."""
    # An empty payload triggers schema/validation errors in the BAFE layer.
    resp = client.post("/v1/validate", json={}, headers=_API_KEY_HEADERS)
    assert resp.status_code in (422, 500), f"Expected 422 or 500, got {resp.status_code}"
    body = resp.json()
    assert "error" in body, "Missing 'error' key in response"
    assert body["error"] != "http_error", (
        f"validate.py is leaking 'http_error' — expected a specific error code, got: {body}"
    )
    assert "request_id" in body


def test_western_router_500_returns_structured_envelope():
    """western.py unhandled Exception must return a structured envelope, not a bare string detail."""
    with patch("bazi_engine.routers.western.compute_western_chart", side_effect=RuntimeError("boom")):
        resp = client.post(
            "/v1/calculate/western",
            json={
                "date": "1990-06-15T14:30:00",
                "tz": "Europe/Berlin",
                "lon": 13.405,
                "lat": 52.52,
            },
            headers=_API_KEY_HEADERS,
        )
    assert resp.status_code == 500
    body = resp.json()
    assert body.get("error") not in (None, "http_error"), (
        f"western.py returns bare string detail: {body}"
    )
    assert "request_id" in body


# ── Task 2: INPUT-1 — lat/lon range validation ────────────────────────────────

_VALID_BAZI = {"date": "1990-06-15T14:30:00", "tz": "Europe/Berlin", "lon": 13.405, "lat": 52.52}
_VALID_WESTERN = {"date": "1990-06-15T14:30:00", "tz": "Europe/Berlin", "lon": 13.405, "lat": 52.52}
_VALID_FUSION = {"date": "1990-06-15T14:30:00", "tz": "Europe/Berlin", "lon": 13.405, "lat": 52.52}


@pytest.mark.parametrize("endpoint,base_payload,field,bad_value", [
    ("/v1/calculate/bazi",    _VALID_BAZI,    "lat",  91.0),
    ("/v1/calculate/bazi",    _VALID_BAZI,    "lat", -91.0),
    ("/v1/calculate/bazi",    _VALID_BAZI,    "lon", 181.0),
    ("/v1/calculate/bazi",    _VALID_BAZI,    "lon", -181.0),
    ("/v1/calculate/western", _VALID_WESTERN, "lat",  91.0),
    ("/v1/calculate/western", _VALID_WESTERN, "lat", -91.0),
    ("/v1/calculate/western", _VALID_WESTERN, "lon", 181.0),
    ("/v1/calculate/western", _VALID_WESTERN, "lon", -181.0),
    ("/v1/calculate/fusion",  _VALID_FUSION,  "lat",  91.0),
    ("/v1/calculate/fusion",  _VALID_FUSION,  "lat", -91.0),
    ("/v1/calculate/fusion",  _VALID_FUSION,  "lon", 181.0),
    ("/v1/calculate/fusion",  _VALID_FUSION,  "lon", -181.0),
])
def test_out_of_range_lat_lon_returns_422(endpoint, base_payload, field, bad_value):
    payload = {**base_payload, field: bad_value}
    resp = client.post(endpoint, json=payload, headers=_API_KEY_HEADERS)
    assert resp.status_code == 422, (
        f"{endpoint} {field}={bad_value}: expected 422, got {resp.status_code}; body={resp.text[:200]}"
    )


# ── Task 3: RATE-1 — tier-based dynamic rate limits ──────────────────────────
#
# tier_limit(key: str) is called by slowapi with the result of key_func(request).
# The parameter is named "key" (load-bearing: slowapi inspects parameter names
# via inspect.signature to decide whether to pass the key_func result or call
# with no args — see slowapi/wrappers.py LimitGroup.__iter__).

def test_tier_limit_free_tier():
    """Free tier key (ff_free_*) → 5 req/min."""
    from bazi_engine.limiter import tier_limit
    assert tier_limit("ff_free_testkey123") == "5/minute"


def test_tier_limit_starter_tier():
    """Starter tier key (ff_starter_*) → 20 req/min."""
    from bazi_engine.limiter import tier_limit
    assert tier_limit("ff_starter_testkey123") == "20/minute"


def test_tier_limit_pro_tier():
    """Pro tier key (ff_pro_*) → 100 req/min."""
    from bazi_engine.limiter import tier_limit
    assert tier_limit("ff_pro_testkey123") == "100/minute"


def test_tier_limit_enterprise_tier():
    """Enterprise tier key (ff_enterprise_*) → capped at 10000/min (rpm=0 means unlimited)."""
    from bazi_engine.limiter import tier_limit
    assert tier_limit("ff_enterprise_testkey123") == "10000/minute"


def test_tier_limit_dev_mode():
    """Dev-mode key → capped at 10000/min (rpm=0 means unlimited)."""
    from bazi_engine.limiter import tier_limit
    assert tier_limit("dev-mode") == "10000/minute"


def test_tier_limit_ip_address_returns_legacy_fallback():
    """IP address (legacy route, no API key) → 30/minute fallback.

    Legacy routes key by remote IP, not API key. These should get the
    30/minute legacy fallback, not the free-tier 5/minute rate.
    """
    from bazi_engine.limiter import tier_limit
    assert tier_limit("127.0.0.1") == "30/minute"
    assert tier_limit("192.168.1.100") == "30/minute"


def test_tier_limit_callable_interface_matches_slowapi():
    """tier_limit must have a 'key' parameter so slowapi passes key_func(request) to it.

    slowapi.wrappers.LimitGroup.__iter__ checks:
        if "key" in inspect.signature(limit_provider).parameters:
            limit_raw = limit_provider(key_function(request))
    Without the "key" parameter name, slowapi calls limit_provider() with no args
    (broken ContextVar path).
    """
    import inspect

    from bazi_engine.limiter import tier_limit
    params = inspect.signature(tier_limit).parameters
    assert "key" in params, (
        f"tier_limit must have a 'key' parameter for slowapi callable dispatch; "
        f"found: {list(params.keys())}"
    )


# ── Task 4: CORS-1 + AUTH-1 — security header hardening ─────────────────────

def test_csp_header_present():
    """Every response must include Content-Security-Policy: default-src 'none'."""
    resp = client.get("/health")
    assert "content-security-policy" in resp.headers, (
        "Missing Content-Security-Policy header"
    )
    assert resp.headers["content-security-policy"] == "default-src 'none'", (
        f"Unexpected CSP value: {resp.headers.get('content-security-policy')}"
    )


def test_enterprise_key_warning_logged(caplog):
    """_load_keys() must emit a WARNING when an enterprise key is present."""
    import logging
    from unittest.mock import patch
    with patch.dict("os.environ", {"FUFIRE_API_KEYS": "ff_enterprise_secret123"}):
        # Clear the lru_cache so it re-runs with the patched env
        from bazi_engine.auth import _load_keys
        _load_keys.cache_clear()
        with caplog.at_level(logging.WARNING, logger="bazi_engine.auth"):
            _load_keys()
        _load_keys.cache_clear()  # clean up after test
    assert any("enterprise" in r.message.lower() for r in caplog.records), (
        "Expected a WARNING about enterprise key presence"
    )


# ── Finding #3 (fufire-premium-verification-ci, 2026-07-01): info disclosure ──
# `EphemerisUnavailableError` raised by `ensure_ephemeris_files()` used to put
# `resolved_path` (a server-local filesystem path) into BOTH its client-facing
# message text and its `detail` dict, and `app.py`'s exception handler
# serialized both verbatim into the 503 body on every reachable call site
# (`/health`, `/calculate/*`, `houses()`'s precondition-gate). The
# security-reviewer recommended "redact" (PRD §10) — this proves it is
# actually implemented, not merely recommended.

def test_ephemeris_unavailable_503_does_not_leak_resolved_path(tmp_path, caplog):
    """resolved_path must reach server-side logs only, never the client body."""
    import logging

    from bazi_engine.ephemeris import ensure_ephemeris_files

    empty_dir = tmp_path / "empty_ephe"
    empty_dir.mkdir()
    ensure_ephemeris_files.cache_clear()
    try:
        with patch.dict("os.environ", {"SE_EPHE_PATH": str(empty_dir)}):
            with caplog.at_level(logging.ERROR, logger="bazi_engine.ephemeris"):
                resp = client.post(
                    "/calculate/bazi",
                    json={"date": "1990-06-15T14:30:00", "tz": "Europe/Berlin", "lon": 13.405, "lat": 52.52},
                )
    finally:
        ensure_ephemeris_files.cache_clear()

    assert resp.status_code == 503
    raw_body = resp.text
    assert str(empty_dir) not in raw_body, (
        f"resolved_path leaked into the client-facing 503 body: {raw_body}"
    )
    body = resp.json()
    assert "resolved_path" not in body.get("detail", {}), (
        f"detail must not carry resolved_path: {body.get('detail')}"
    )

    # ...but it must still be visible server-side, for operator debugging.
    assert any(str(empty_dir) in r.message for r in caplog.records), (
        "resolved_path must still be logged server-side (log-only, not client-facing)"
    )
