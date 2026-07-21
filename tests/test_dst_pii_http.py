"""HTTP-boundary regression: DST strict-mode PII must never reach the client body.

Companion to tests/test_time_utils_dst_pii.py (which pins the message strings at the
unit level). This file proves the leak is closed at the *live route* boundary — the
place it actually reaches an API consumer.

`parse_local_iso()`'s strict round-trip raise used to interpolate the raw birth
instant, the timezone name, AND the normalized round-trip instant into its
`LocalTimeError` message, which `app.py`'s `bazi_engine_error_handler` serializes
verbatim into the client-facing 422 body. It is reachable on every route that builds
`BaziInput` from the raw request date with the default `strict_local_time=True` and no
`resolve_local_iso` pre-resolution:

  * POST /v1/impact/active
  * POST /v1/experience/bootstrap
  * POST /v1/calculate/bazi/dayun

`/v1/calculate/bazi` is included as a regression anchor: it *does* pre-resolve via
`resolve_local_iso` (whose sibling messages were already scrubbed in e5d4207), so it
must stay clean too.

A spring-forward gap (Europe/Berlin 2024-03-31 02:30 — the 02:00→03:00 jump) is a real
nonexistent local time whose strict round-trip normalizes to 03:30.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from bazi_engine.app import app

# The three PII substrings that must never appear in a client-facing error body.
_RAW_INSTANT = "2024-03-31T02:30:00"   # the subject's exact birth instant
_RAW_TZ = "Europe/Berlin"              # the subject's timezone
_ROUNDTRIP_INSTANT = "2024-03-31T03:30:00"  # normalized round-trip (also PII-derived)


@pytest.fixture(autouse=True)
def _dev_mode_no_api_key(monkeypatch):
    """Force dev-mode auth bypass so /v1/* routes are reachable without a key.

    Mirrors tests/test_attestation_contract.py::_no_api_key_enforcement, plus a
    _load_keys cache_clear so a prior test that populated FUFIRE_API_KEYS cannot
    leak an enforced key list into this module (see test_security_findings.py's
    enterprise-key test, which mutates that env + cache).
    """
    monkeypatch.setenv("FUFIRE_REQUIRE_API_KEYS", "false")
    monkeypatch.delenv("FUFIRE_API_KEYS", raising=False)
    from bazi_engine.auth import _load_keys

    _load_keys.cache_clear()
    yield
    _load_keys.cache_clear()


@pytest.fixture
def client() -> TestClient:
    return TestClient(app, raise_server_exceptions=False)


# (route, json payload) — each payload encodes the spring-forward-gap birth instant
# in whatever shape that route's request schema expects.
_DST_GAP_ROUTES = {
    # strict-mode leak sites (no resolve_local_iso pre-resolution) ────────────
    "impact_active": (
        "/v1/impact/active",
        {
            "birth": {
                "date": "2024-03-31",
                "time": "02:30:00",
                "tz": "Europe/Berlin",
                "lat": 52.52,
                "lon": 13.405,
            }
        },
    ),
    "experience_bootstrap": (
        "/v1/experience/bootstrap",
        {
            "birth": {
                "date": "2024-03-31",
                "time": "02:30:00",
                "tz": "Europe/Berlin",
                "lat": 52.52,
                "lon": 13.405,
            }
        },
    ),
    "calculate_bazi_dayun": (
        "/v1/calculate/bazi/dayun",
        {
            "date": "2024-03-31T02:30:00",
            "tz": "Europe/Berlin",
            "lat": 52.52,
            "lon": 13.405,
            "direction_method": "explicit",
            "flow_direction": "forward",
        },
    ),
    # regression anchor — already scrubbed (resolve_local_iso path), must stay clean
    "calculate_bazi": (
        "/v1/calculate/bazi",
        {
            "date": "2024-03-31T02:30:00",
            "tz": "Europe/Berlin",
            "lon": 13.405,
            "lat": 52.52,
        },
    ),
}


@pytest.mark.parametrize("route_id", sorted(_DST_GAP_ROUTES))
def test_dst_gap_error_body_omits_pii(client, route_id):
    path, payload = _DST_GAP_ROUTES[route_id]
    resp = client.post(path, json=payload)

    # A nonexistent local time is a client input error, not a server fault.
    assert 400 <= resp.status_code < 500, (
        f"{path}: expected a 4xx for a DST spring-forward gap, got "
        f"{resp.status_code}; body={resp.text[:300]}"
    )

    body = resp.text
    assert _RAW_INSTANT not in body, (
        f"{path}: raw birth instant leaked into the client-facing error body: {body}"
    )
    assert _RAW_TZ not in body, (
        f"{path}: raw timezone leaked into the client-facing error body: {body}"
    )
    assert _ROUNDTRIP_INSTANT not in body, (
        f"{path}: normalized round-trip instant leaked into the client-facing "
        f"error body: {body}"
    )


# ── FIX-3: format-error / unknown-tz raises must not echo caller input ────────
#
# time_utils' "Invalid date/time format" and "Unknown timezone" raises used to
# echo the (injection-sanitized but otherwise raw) birth_local_iso / tz_name
# back into client-facing 422 bodies. A malformed birth string is still a birth
# instant, and the tz is location PII — same finding class as the DST scrub
# above. One representative route per leaking function:
#   * /v1/calculate/bazi/dayun + /v1/experience/bootstrap → parse_local_iso
#     (BaziInput built from the raw request date/tz, no pre-resolution)
#   * /v1/calculate/bazi → resolve_local_iso (pre-resolves before compute_bazi)

_MALFORMED_DATE = "31.03.2024 02:30"   # survives the char-whitelist sanitizer
_BOGUS_TZ = "Mars/Olympus"             # survives the char-whitelist sanitizer

_ECHO_ROUTES = {
    # malformed birth string → format-error raise
    "dayun_malformed_date": (
        "/v1/calculate/bazi/dayun",
        {
            "date": _MALFORMED_DATE,
            "tz": "Europe/Berlin",
            "lat": 52.52,
            "lon": 13.405,
            "direction_method": "explicit",
            "flow_direction": "forward",
        },
        _MALFORMED_DATE,
    ),
    "bazi_malformed_date": (
        "/v1/calculate/bazi",
        {"date": _MALFORMED_DATE, "tz": "Europe/Berlin", "lon": 13.405, "lat": 52.52},
        _MALFORMED_DATE,
    ),
    # bogus tz name → unknown-timezone raise
    "bootstrap_bogus_tz": (
        "/v1/experience/bootstrap",
        {
            "birth": {
                "date": "1990-06-15",
                "time": "14:30:00",
                "tz": _BOGUS_TZ,
                "lat": 52.52,
                "lon": 13.405,
            }
        },
        _BOGUS_TZ,
    ),
    "bazi_bogus_tz": (
        "/v1/calculate/bazi",
        {"date": "1990-06-15T14:30:00", "tz": _BOGUS_TZ, "lon": 13.405, "lat": 52.52},
        _BOGUS_TZ,
    ),
}


@pytest.mark.parametrize("route_id", sorted(_ECHO_ROUTES))
def test_format_and_tz_error_bodies_do_not_echo_caller_input(client, route_id):
    path, payload, sentinel = _ECHO_ROUTES[route_id]
    resp = client.post(path, json=payload)

    assert 400 <= resp.status_code < 500, (
        f"{path}: expected a 4xx for invalid input, got "
        f"{resp.status_code}; body={resp.text[:300]}"
    )
    assert sentinel not in resp.text, (
        f"{path}: caller input {sentinel!r} echoed into the client-facing "
        f"error body: {resp.text}"
    )
