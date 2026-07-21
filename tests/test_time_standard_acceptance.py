"""FBP-01-001 — TLST is accepted at the API boundary.

Phase-1 contract (router-clamp, Option 2):
- ``/calculate/bazi`` and ``/api/chart`` accept ``CIVIL``, ``LMT``, and
  ``TLST`` for ``standard`` / ``time_standard``.
- ``INVALID`` values still return 422.
- When a TLST request reaches the engine, the router clamps it to
  ``LMT`` so pillar derivation stays in known territory. The
  derivation trace records both ``time_standard_requested`` (the user's
  original choice) and ``time_standard_used`` (what the engine saw).
- DEV-2026-001 (``true_solar_time_used`` mislabel) is NOT fixed here
  — that's FBP-03-002. Phase 1 only adds the requested/used split.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from bazi_engine.app import app

client = TestClient(app)

BASE = {
    "date": "2024-02-10T14:30:00",
    "tz": "Europe/Berlin",
    "lon": 13.405,
    "lat": 52.52,
}


def _ephemeris_available() -> bool:
    r = client.post("/calculate/bazi", json=BASE)
    return r.status_code == 200


_HAS_ENGINE = _ephemeris_available()
_skip_no_engine = pytest.mark.skipif(
    not _HAS_ENGINE,
    reason="engine call requires working ephemeris path",
)


@pytest.mark.parametrize("std", ["CIVIL", "LMT", "TLST"])
def test_calculate_bazi_accepts_time_standard(std):
    """The API must not 422-reject any of the three legal time standards.

    Asserts both `!= 404` (route must resolve — guards against the
    chart-test-style vacuous pass) and `!= 422` (Pydantic must accept
    the literal). Downstream engine-call failures (e.g. 503 with
    missing ephemeris) are acceptable.
    """
    r = client.post("/calculate/bazi", json={**BASE, "standard": std})
    assert r.status_code not in {404, 422}, r.text


def test_calculate_bazi_rejects_unknown_time_standard():
    r = client.post("/calculate/bazi", json={**BASE, "standard": "UTC"})
    assert r.status_code == 422


@_skip_no_engine
def test_tlst_request_records_requested_and_used_in_trace():
    """FBP-02-005 (Phase 2): with the router clamp removed, the trace
    records ``time_standard_used == time_standard_requested == "TLST"``
    for a TLST request. The requested/used split is still emitted for
    backward compatibility with Phase-1 consumers."""
    r = client.post("/calculate/bazi", json={**BASE, "standard": "TLST"})
    assert r.status_code == 200, r.text
    trace = r.json().get("derivation_trace")
    assert trace is not None
    hour = trace.get("hour", {})
    assert hour.get("time_standard_requested") == "TLST"
    assert hour.get("time_standard_used") == "TLST"


@_skip_no_engine
@pytest.mark.parametrize("std", ["CIVIL", "LMT"])
def test_non_tlst_request_records_unclamped_used(std):
    """For CIVIL and LMT, requested == used (no clamp)."""
    r = client.post("/calculate/bazi", json={**BASE, "standard": std})
    assert r.status_code == 200, r.text
    hour = r.json()["derivation_trace"]["hour"]
    assert hour["time_standard_requested"] == std
    assert hour["time_standard_used"] == std


@_skip_no_engine
def test_tlst_pillars_may_differ_from_lmt_phase2():
    """Phase 2 (FBP-02-005): the router clamp is gone, so TLST and LMT
    can produce different pillars when the longitude offset + EoT
    push the hour-of-day across a 2-hour Zi/Chou/Yin/… bin boundary.

    This particular fixture (Berlin near the CET standard meridian)
    is *not* a boundary case — TLST and LMT happen to land in the
    same bin — so the pillars match. The point of this test is to
    confirm the two surfaces still produce a valid pillar response
    each; the boundary-case divergence is in
    tests/test_bazi_tlst_hour_pillar.py.
    """
    r_lmt  = client.post("/calculate/bazi", json={**BASE, "standard": "LMT"})
    r_tlst = client.post("/calculate/bazi", json={**BASE, "standard": "TLST"})
    assert r_lmt.status_code == 200
    assert r_tlst.status_code == 200
    # Each response must be a complete BaziResponse; every pillar must
    # be a dict with valid stem (``stamm``) and branch (``zweig``).
    from bazi_engine.constants import BRANCHES, STEMS
    for label, body in (("LMT", r_lmt.json()), ("TLST", r_tlst.json())):
        for key, pillar in body["pillars"].items():
            assert pillar["stamm"] in STEMS, f"{label}/{key}: bad stem {pillar!r}"
            assert pillar["zweig"] in BRANCHES, f"{label}/{key}: bad branch {pillar!r}"


_CHART_VALID_PAYLOAD = {
    "local_datetime": "2024-02-10T14:30:00",
    "tz_id": "Europe/Berlin",
    "geo_lon_deg": 13.405,
    "geo_lat_deg": 52.52,
}


@pytest.mark.parametrize("std", ["CIVIL", "LMT", "TLST"])
def test_chart_accepts_time_standard(std):
    """The chart endpoint must also accept TLST (its Literal is separate).

    History: this test previously posted to the wrong path
    (``/api/chart`` — the actual route is ``/chart``) with a wrong
    field name (``birth_local`` — the model expects ``local_datetime``),
    and asserted only ``!= 422``. Result: every call returned 404 and
    the assertion passed without exercising the endpoint, which masked
    the C-P1-1 regression (chart.py:51 literal not actually widened).
    Both the path/field bug and the loose assertion are fixed here.
    """
    payload = {**_CHART_VALID_PAYLOAD, "time_standard": std}
    r = client.post("/chart", json=payload)
    # Route MUST resolve (no 404 — that was the old vacuous case).
    assert r.status_code != 404, (
        f"/chart returned 404 — wrong path. status={r.status_code} body={r.text[:200]}"
    )
    # Pydantic MUST accept the value (no 422 — that's the actual
    # regression C-P1-1 was guarding against).
    assert r.status_code != 422, (
        f"Pydantic rejected time_standard={std!r}: {r.text[:200]}"
    )


def _chart_engine_available() -> bool:
    """Phase-1 router clamp: a 503 (e.g. missing ephemeris) means we
    can't read the response body, so the requested-vs-used assertion
    is skipped. A 200 with `bazi` block means we can verify."""
    r = client.post("/chart", json={**_CHART_VALID_PAYLOAD, "time_standard": "CIVIL"})
    return r.status_code == 200


_HAS_CHART_ENGINE = _chart_engine_available()
_skip_chart = pytest.mark.skipif(
    not _HAS_CHART_ENGINE,
    reason="/chart engine call failed (likely missing ephemeris) — cannot verify response body",
)


@_skip_chart
def test_chart_response_surfaces_tlst_after_phase2(monkeypatch):
    """FBP-02-005 (Phase 2): with the router clamp removed, a TLST
    request must report ``time_standard_used == "TLST"`` in the chart
    response. The requested/used split is kept for backward
    compatibility with Phase-1 consumers."""
    r = client.post("/chart", json={**_CHART_VALID_PAYLOAD, "time_standard": "TLST"})
    assert r.status_code == 200, r.text
    bazi = r.json().get("bazi", {})
    assert bazi.get("time_standard_requested") == "TLST"
    assert bazi.get("time_standard_used") == "TLST", (
        "Phase-2 removes the router clamp; chart response must now "
        "record time_standard_used=TLST for TLST requests."
    )


@_skip_chart
@pytest.mark.parametrize("std", ["CIVIL", "LMT"])
def test_chart_response_records_unclamped_used(std):
    """For non-TLST requests, requested == used (no clamp)."""
    r = client.post("/chart", json={**_CHART_VALID_PAYLOAD, "time_standard": std})
    assert r.status_code == 200, r.text
    bazi = r.json()["bazi"]
    assert bazi["time_standard_requested"] == std
    assert bazi["time_standard_used"] == std


def test_chart_rejects_invalid_time_standard():
    """Sanity: an unknown time_standard value still 422s.

    Without this assertion, the positive test above could pass for
    reasons unrelated to TLST acceptance (e.g. if the field name were
    silently ignored by the model).
    """
    payload = {**_CHART_VALID_PAYLOAD, "time_standard": "UTC"}
    r = client.post("/chart", json=payload)
    assert r.status_code == 422, (
        f"Expected 422 for invalid time_standard, got {r.status_code}: {r.text[:200]}"
    )
