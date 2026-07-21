"""Task 10 — birth_time_known opt-in contract.

The audit demands that the engine NEVER silently produce ``assumed_day``.
Callers must explicitly opt into degraded precision by setting
``birth_time_known=false`` on the natal input. This test file covers:

1. Default (no birth_time_known field) → backward-compatible "exact" behaviour
   for any valid time supplied by the caller (Phase A consumers preserved).
2. Explicit birth_time_known=True → same as default.
3. Explicit birth_time_known=False → forces chart_type_quality="assumed_day"
   even when a valid time is supplied (caller acknowledged it's a placeholder).
4. The mirroring contract still holds: top-level chart_type_quality and
   nested quality_flags.chart_type_quality always agree.
5. Pydantic rejects garbage values (422) — type safety unchanged.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from bazi_engine.app import app


def _ephemeris_available() -> bool:
    """Probe the calculate endpoint to detect whether ephemeris is wired."""
    client = TestClient(app)
    res = client.post(
        "/v1/calculate/western",
        json={
            "date": "1990-06-15T12:00:00",
            "tz": "UTC",
            "lon": 0.0,
            "lat": 45.0,
        },
    )
    return res.status_code == 200


if not _ephemeris_available():
    pytest.skip("Ephemeris not available", allow_module_level=True)


@pytest.fixture
def client():
    return TestClient(app)


def _payload(birth_extra: dict | None = None) -> dict:
    """Construct a canonical Berlin DailyRequest payload."""
    birth = {
        "date": "1990-06-15",
        "time": "14:30:00",
        "tz": "Europe/Berlin",
        "lat": 52.52,
        "lon": 13.405,
    }
    if birth_extra:
        birth.update(birth_extra)
    return {
        "birth": birth,
        "soulprint_sectors": [0.5] * 12,
        "quiz_sectors": [0.5] * 12,
        "target_date": "2026-05-09",
        "locale": "de-DE",
    }


def test_default_birth_time_known_yields_exact_quality(client):
    """Phase A backward-compat: omitted birth_time_known defaults True → exact."""
    res = client.post("/v1/experience/daily", json=_payload())
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["chart_type_quality"] == "exact"
    assert body["quality_flags"]["chart_type_quality"] == "exact"


def test_explicit_birth_time_known_true_yields_exact(client):
    """Explicit True equals default — no behavioral change."""
    res = client.post("/v1/experience/daily", json=_payload({"birth_time_known": True}))
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["chart_type_quality"] == "exact"
    assert body["quality_flags"]["chart_type_quality"] == "exact"


def test_explicit_birth_time_known_false_forces_assumed_day(client):
    """Audit contract: caller opted into degraded precision → engine honors it,
    even though a valid time is supplied (the audit's exact concern)."""
    res = client.post("/v1/experience/daily", json=_payload({"birth_time_known": False}))
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["chart_type_quality"] == "assumed_day", (
        "birth_time_known=False must force assumed_day regardless of "
        "computed ascendant — silent exact-trust signals are forbidden."
    )
    # Mirroring discipline survives the override
    assert body["quality_flags"]["chart_type_quality"] == "assumed_day"


def test_mirroring_holds_under_all_birth_time_known_values(client):
    """Top-level chart_type_quality and nested quality_flags.chart_type_quality
    must agree, regardless of the birth_time_known value."""
    for opted_value in (True, False):
        res = client.post(
            "/v1/experience/daily",
            json=_payload({"birth_time_known": opted_value}),
        )
        assert res.status_code == 200, res.text
        body = res.json()
        top = body["chart_type_quality"]
        nested = body["quality_flags"]["chart_type_quality"]
        assert top == nested, (
            f"Mirror divergence with birth_time_known={opted_value!r}: "
            f"top={top!r}, nested={nested!r}"
        )


def test_birth_time_known_garbage_value_returns_422(client):
    """Pydantic rejects non-bool values (forward-compatible type safety)."""
    res = client.post("/v1/experience/daily", json=_payload({"birth_time_known": "maybe"}))
    assert res.status_code == 422
    assert "birth_time_known" in res.text
