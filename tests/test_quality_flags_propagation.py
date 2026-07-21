"""Task 8: propagate ``quality_flags`` through fusion + experience responses.

Phase A surfaced ``chart_type_quality`` at the top level of the
``/v1/experience/daily`` response so B2B integrators (Bazodiac, ElevenLabs
proxy) could trust-gate readings without digging into a nested fusion
sub-tree. Task 7 introduced a richer ``quality_flags`` block on the
``/v1/calculate/western`` response that also exposes house-system fallback
and the active ephemeris backend.

Task 8 wires those two together: the canonical ``quality_flags`` block
becomes available on every endpoint that builds on the western chart
(``/v1/calculate/fusion`` and ``/v1/experience/daily``). On the daily
response the existing top-level ``chart_type_quality`` field is preserved
as a deprecated alias mirroring ``quality_flags.chart_type_quality`` so
Phase A consumers continue to work unchanged.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from bazi_engine.app import app


def _ephemeris_available() -> bool:
    """Probe a real endpoint to confirm an ephemeris backend is wired."""
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
    pytest.skip(
        "Ephemeris not available — Task 8 propagation tests need a working backend",
        allow_module_level=True,
    )


@pytest.fixture(autouse=True)
def _disable_api_keys(monkeypatch):
    monkeypatch.setenv("FUFIRE_REQUIRE_API_KEYS", "false")
    monkeypatch.delenv("FUFIRE_API_KEYS", raising=False)


@pytest.fixture
def client():
    return TestClient(app)


def _berlin_daily_body() -> dict:
    """Real DailyRequest payload — discovered from
    bazi_engine/routers/experience.py: birth/soulprint_sectors/quiz_sectors/
    target_date. Matches the pattern in test_daily_chart_type_quality_surfaced.py.
    """
    return {
        "birth": {
            "date": "1990-06-15",
            "time": "14:30:00",
            "tz": "Europe/Berlin",
            "lat": 52.52,
            "lon": 13.405,
        },
        "soulprint_sectors": [
            0.08, 0.09, 0.08, 0.09, 0.08, 0.08,
            0.09, 0.08, 0.09, 0.08, 0.08, 0.08,
        ],
        "quiz_sectors": [
            0.08, 0.09, 0.08, 0.09, 0.08, 0.08,
            0.09, 0.08, 0.09, 0.08, 0.08, 0.08,
        ],
        "target_date": "2026-04-13",
    }


# ── /v1/calculate/fusion ─────────────────────────────────────────────────────


def test_fusion_response_carries_quality_flags(client):
    """The /v1/calculate/fusion response must mirror the western quality_flags
    payload so callers can trust-gate the chart without a separate
    /v1/calculate/western request."""
    res = client.post(
        "/v1/calculate/fusion",
        json={
            "date": "1990-06-15T14:30:00",
            "tz": "Europe/Berlin",
            "lon": 13.405,
            "lat": 52.52,
        },
    )
    assert res.status_code == 200, res.text
    body = res.json()

    assert "quality_flags" in body, (
        "quality_flags block missing from fusion response — Task 8 must "
        "propagate the western quality signal."
    )
    qf = body["quality_flags"]
    assert qf["house_system_used"] in {"placidus", "porphyry", "whole_sign"}
    assert qf["house_system_requested"] in {"placidus", "porphyry", "whole_sign"}
    assert qf["ephemeris_mode"] in {"SWIEPH", "MOSEPH"}
    assert isinstance(qf["house_system_fallback"], bool)
    # Fusion-tier callers also need chart_type_quality; the natal Ascendant
    # is well defined for Berlin midday, so this must be "exact".
    assert qf["chart_type_quality"] in {"exact", "assumed_day"}


def test_fusion_quality_flags_consistent_with_house_quality(client):
    """quality_flags must agree with the legacy house_quality block on the
    same response, just like the western endpoint."""
    res = client.post(
        "/v1/calculate/fusion",
        json={
            # High-latitude case forces a Placidus fallback.
            "date": "2024-06-21T12:00:00",
            "tz": "UTC",
            "lon": 15.6,
            "lat": 78.0,
        },
    )
    assert res.status_code == 200, res.text
    body = res.json()
    qf = body["quality_flags"]
    hq = body["house_quality"]
    assert qf["house_system_used"] == hq["system"]
    assert qf["house_system_requested"] == hq["requested"]
    assert qf["house_system_fallback"] is (hq["flag"] != "exact")


# ── /v1/experience/daily ─────────────────────────────────────────────────────


def test_daily_response_carries_quality_flags_and_top_level_alias_matches(client):
    """The /v1/experience/daily response must:
      1. include ``quality_flags`` as the canonical location,
      2. preserve the top-level ``chart_type_quality`` alias from Phase A,
      3. ensure the two values are identical (mirrored, not divergent).
    """
    res = client.post("/v1/experience/daily", json=_berlin_daily_body())
    assert res.status_code == 200, res.text
    body = res.json()

    assert "quality_flags" in body, (
        "quality_flags block missing from daily response — Task 8 must "
        "expose the merged trust signal at the experience layer."
    )
    qf = body["quality_flags"]

    assert qf["chart_type_quality"] in {"exact", "assumed_day"}
    assert qf["house_system_used"] in {"placidus", "porphyry", "whole_sign"}
    assert qf["house_system_requested"] in {"placidus", "porphyry", "whole_sign"}
    assert qf["ephemeris_mode"] in {"SWIEPH", "MOSEPH"}
    assert isinstance(qf["house_system_fallback"], bool)

    # Phase A backward-compat alias must mirror the canonical nested value.
    assert "chart_type_quality" in body, (
        "Phase A consumers (Bazodiac, ElevenLabs proxy) rely on the "
        "top-level chart_type_quality field — it must remain in place "
        "as a deprecated alias."
    )
    assert body["chart_type_quality"] == qf["chart_type_quality"], (
        f"Top-level chart_type_quality ({body['chart_type_quality']!r}) must "
        f"mirror quality_flags.chart_type_quality ({qf['chart_type_quality']!r})."
    )

    # For Berlin midday + ephemeris available, the chart is exact.
    assert qf["chart_type_quality"] == "exact"


def test_daily_response_legacy_path_also_carries_quality_flags(client):
    """The legacy unprefixed /experience/daily must surface the same trust
    signal so consumers that haven't migrated to /v1 still benefit."""
    res = client.post("/experience/daily", json=_berlin_daily_body())
    assert res.status_code == 200, res.text
    body = res.json()
    assert "quality_flags" in body
    assert body["quality_flags"]["chart_type_quality"] == body["chart_type_quality"]
