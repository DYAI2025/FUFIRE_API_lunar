"""FBP-01-003 — ``/calculate/tst`` must agree with EffectiveTimeContext.

The endpoint historically inlined its own TLST formula
(``fusion.py:264-267``). After the refactor it delegates to
:func:`bazi_engine.time_context.compute_effective_time_context`. The
tests here guard against any future drift: same input ⇒ same TLST
hours and same EoT.
"""
from __future__ import annotations

import math

import pytest
from fastapi.testclient import TestClient

from bazi_engine.app import app
from bazi_engine.time_context import compute_effective_time_context

client = TestClient(app)

CASES = [
    {"date": "2024-06-21T12:00:00", "tz": "Europe/Berlin", "lon": 13.4050},
    {"date": "2024-12-21T12:00:00", "tz": "Europe/Berlin", "lon": 13.4050},
    {"date": "2024-03-20T06:00:00", "tz": "Asia/Tokyo",    "lon": 139.69},
    {"date": "2024-09-22T18:30:00", "tz": "UTC",           "lon": 0.0},
    {"date": "2024-11-04T08:15:00", "tz": "America/New_York", "lon": -74.00},
]


@pytest.mark.parametrize("payload", CASES, ids=lambda p: f"{p['tz']}@{p['date']}")
def test_tst_endpoint_matches_effective_time_context(payload):
    r = client.post("/calculate/tst", json=payload)
    assert r.status_code == 200, r.text
    body = r.json()
    ctx = compute_effective_time_context(
        birth_local_iso=payload["date"],
        tz_name=payload["tz"],
        longitude_deg=payload["lon"],
    )
    # Endpoint rounds to 4 decimals; tolerance generous enough to
    # survive that without admitting actual drift.
    assert math.isclose(
        body["true_solar_time_hours"], ctx.tlst_hours, abs_tol=1e-3
    ), (body["true_solar_time_hours"], ctx.tlst_hours)
    assert math.isclose(
        body["equation_of_time_hours"], ctx.eot_minutes / 60.0, abs_tol=1e-3
    )


def test_tst_endpoint_input_echoes_request():
    r = client.post("/calculate/tst", json=CASES[0])
    body = r.json()
    assert body["input"]["date"] == CASES[0]["date"]
    assert body["input"]["tz"] == CASES[0]["tz"]
    assert body["input"]["lon"] == CASES[0]["lon"]
