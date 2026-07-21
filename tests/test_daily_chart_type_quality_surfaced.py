"""Task 5: Surface ``chart_type_quality`` at the top level of /v1/experience/daily.

B2B integrators (Bazodiac frontend, ElevenLabs proxy) need to know whether
the chart is "exact" (real Ascendant), "approximate", or "assumed_day"
(fallback default) without having to dig into a fusion sub-tree. This test
asserts that the daily response surfaces ``chart_type_quality`` at the top
level, mirroring the value in ``fusion.contribution_ledger.chart_type_quality``
(when present in the natal fusion). The nested location must remain
unchanged in upstream endpoints — this is purely additive at the experience
layer.

Note: the daily endpoint itself never embedded ``contribution_ledger`` in
its response (it composes ``DailyFusion`` from ``daily_fusion.py``, not the
raw ``compute_fusion_analysis`` output). The natal fusion is computed inside
``_compute_astro_profile`` and that ledger is the source of truth — Task 5
mirrors its ``chart_type_quality`` to the top level so callers don't need
the natal fusion payload to know whether the chart is trustworthy.
"""

from __future__ import annotations

import pytest
from starlette.testclient import TestClient

pytestmark = pytest.mark.swieph


@pytest.fixture(autouse=True)
def env(monkeypatch):
    monkeypatch.setenv("FUFIRE_REQUIRE_API_KEYS", "false")
    monkeypatch.delenv("FUFIRE_API_KEYS", raising=False)


@pytest.fixture
def client():
    from bazi_engine.app import app
    return TestClient(app)


def _berlin_daily_body() -> dict:
    return {
        "birth": {
            "date": "1990-06-15",
            "time": "14:30:00",
            "tz": "Europe/Berlin",
            "lat": 52.52,
            "lon": 13.405,
        },
        "soulprint_sectors": [0.08, 0.09, 0.08, 0.09, 0.08, 0.08, 0.09, 0.08, 0.09, 0.08, 0.08, 0.08],
        "quiz_sectors": [0.08, 0.09, 0.08, 0.09, 0.08, 0.08, 0.09, 0.08, 0.09, 0.08, 0.08, 0.08],
        "target_date": "2026-04-13",
    }


def test_compute_astro_profile_exposes_chart_type_quality_in_natal_fusion():
    """The lower-level helper must expose chart_type_quality via the natal
    fusion payload. This is the source of truth that the daily handler
    mirrors to the top-level field."""
    from bazi_engine.routers.experience import BirthInput, _compute_astro_profile

    profile = _compute_astro_profile(
        BirthInput(
            date="1990-06-15",
            time="14:30:00",
            tz="Europe/Berlin",
            lat=52.52,
            lon=13.405,
        )
    )
    fusion = profile.get("fusion") or {}
    ledger = fusion.get("contribution_ledger") or {}
    nested = ledger.get("chart_type_quality")
    assert nested in {"exact", "assumed_day"}, (
        f"natal fusion contribution_ledger.chart_type_quality must be a "
        f"recognised enum value, got {nested!r}"
    )
    # Berlin midday + Ascendant resolved → "exact" is the only correct answer.
    assert nested == "exact"


def test_daily_response_surfaces_chart_type_quality_at_top_level(client):
    """Top-level field must be present and must mirror the natal fusion's
    chart_type_quality value (sourced, never recomputed from scratch)."""
    body = _berlin_daily_body()

    # Hit the v1 path the B2B integrators actually call.
    resp = client.post("/v1/experience/daily", json=body)
    assert resp.status_code == 200, resp.text
    payload = resp.json()

    assert "chart_type_quality" in payload, (
        "Top-level chart_type_quality field is missing from the daily "
        "response. B2B integrators rely on this for trust signalling."
    )
    top_level = payload["chart_type_quality"]
    assert top_level in {"exact", "assumed_day"}, (
        f"chart_type_quality must be one of the documented enum values, "
        f"got {top_level!r}"
    )

    # Source-of-truth check: derive the same chart from the lower-level
    # helper and confirm the daily endpoint mirrored it exactly.
    from bazi_engine.routers.experience import BirthInput, _compute_astro_profile
    profile = _compute_astro_profile(
        BirthInput(**body["birth"])
    )
    nested = (profile.get("fusion") or {}).get("contribution_ledger", {}).get(
        "chart_type_quality"
    )
    assert top_level == nested, (
        f"Top-level chart_type_quality ({top_level!r}) must mirror the "
        f"natal fusion contribution_ledger value ({nested!r})."
    )


def test_daily_response_chart_type_quality_via_legacy_path(client):
    """The legacy unprefixed /experience/daily must surface the same field
    so existing consumers that haven't migrated to /v1 still get it."""
    body = _berlin_daily_body()
    resp = client.post("/experience/daily", json=body)
    assert resp.status_code == 200, resp.text
    payload = resp.json()
    assert payload.get("chart_type_quality") == "exact"
