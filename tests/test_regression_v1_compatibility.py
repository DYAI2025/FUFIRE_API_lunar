"""FBP-00-004 / FBP-06-001 — v1 regression compatibility.

Locks the engine's current v1 output to the values recorded in
``tests/fixtures/bazi_baseline_v1.json``. While
``BAZI-PRECISION-V2`` work is in flight, no change is allowed to
silently alter v1 output — every drift must be either:

1. An intentional bugfix with a deviation entry
   (``docs/precision/deviations.md``) and a refreshed baseline, **or**
2. Reverted.

The test does not pin internal implementation details; it pins the
``year/month/day/hour`` pillar strings produced by the engine for a
representative set of boundary-relevant cases (see
``scripts/export_bazi_baseline.py``).

When the engine is intentionally changed, regenerate the baseline:

    python scripts/export_bazi_baseline.py

and document the diff in ``docs/precision/deviations.md``.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
BASELINE_PATH = REPO_ROOT / "tests" / "fixtures" / "bazi_baseline_v1.json"


@pytest.fixture(scope="module")
def baseline() -> dict:
    if not BASELINE_PATH.exists():
        pytest.skip(
            "Baseline file absent — run scripts/export_bazi_baseline.py "
            "to create it (FBP-00-004)."
        )
    return json.loads(BASELINE_PATH.read_text())


def _params(doc: dict) -> list:
    return [
        pytest.param(c, id=c["id"])
        for c in doc.get("cases", [])
    ]


def _build_baseline_or_skip() -> dict:
    if not BASELINE_PATH.exists():
        return {"cases": []}
    return json.loads(BASELINE_PATH.read_text())


@pytest.mark.parametrize("case", _params(_build_baseline_or_skip()))
def test_v1_pillars_unchanged(case):
    """For each recorded case, recomputing must yield identical pillars.

    A failure is a *signal*, not necessarily a defect: investigate, then
    either fix the engine or update the baseline per the release-gate
    policy (``docs/release/bazi_precision_release_gate.md``).

    Note: the ``baseline`` fixture is intentionally not consumed here —
    the parametrize already drives off the same file. The fixture is
    retained for ``test_baseline_ephemeris_recorded`` below.
    """
    from bazi_engine.bazi import compute_bazi
    from bazi_engine.types import BaziInput

    inp_dict = case["input"]
    kwargs = {
        "birth_local": inp_dict["birth_local"],
        "timezone": inp_dict["timezone"],
        "longitude_deg": inp_dict["longitude_deg"],
        "latitude_deg": inp_dict["latitude_deg"],
    }
    for opt in ("time_standard", "day_boundary"):
        if opt in inp_dict:
            kwargs[opt] = inp_dict[opt]

    res = compute_bazi(BaziInput(**kwargs))
    got = {
        "year":  str(res.pillars.year),
        "month": str(res.pillars.month),
        "day":   str(res.pillars.day),
        "hour":  str(res.pillars.hour),
    }
    expected = case["output"]["pillars"]
    assert got == expected, (
        f"v1 regression on case {case['id']!r}. "
        f"Baseline expected {expected}, engine now produces {got}. "
        "If this is an intentional change, refresh the baseline and "
        "log the diff in docs/precision/deviations.md."
    )


def test_baseline_ephemeris_recorded(baseline):
    """The baseline must declare which ephemeris produced it."""
    assert baseline["metadata"]["ephemeris_mode"] in {"SWIEPH", "MOSEPH"}, (
        f"Unknown ephemeris_mode in baseline: "
        f"{baseline['metadata'].get('ephemeris_mode')!r}"
    )


# ── ADR-1 (Increment 2) — no-breaking-change guard ──────────────────────────
#
# The include_trace flag + bazi/trace alias must NOT change the default
# /calculate/bazi response: derivation_trace must still be present by
# default (include_trace defaults to True). This is the HTTP-level
# companion to test_bazi_trace_endpoint::test_include_trace_false_omits_trace.

_ADR1_PAYLOAD = {
    "date": "2024-02-10T14:30:00",
    "tz": "Europe/Berlin",
    "lon": 13.405,
    "lat": 52.52,
}


def _client():
    from fastapi.testclient import TestClient

    from bazi_engine.app import app
    return TestClient(app)


def test_default_bazi_response_unchanged_trace_present():
    """Default /calculate/bazi (no include_trace) keeps the derivation
    trace — ADR-1 must not regress the existing default contract."""
    client = _client()
    r = client.post("/calculate/bazi", json=_ADR1_PAYLOAD)
    if r.status_code != 200:
        pytest.skip("Swiss Ephemeris files not available")
    body = r.json()
    assert body.get("derivation_trace") is not None
    assert set(body["derivation_trace"].keys()) == {
        "year", "month", "day", "hour", "time_resolution", "provenance_ids",
    }


def test_default_bazi_input_echo_omits_include_trace():
    """ADR-1 zero-churn: the new include_trace toggle is NOT echoed in
    response.input — the input block stays byte-identical to pre-ADR-1
    callers. The omission is achieved NOT via Field(exclude=...) on
    BaziRequest, but by typing response.input as a separate BaziInputEcho
    model (which has no include_trace field) and building the echo with
    req.model_dump(exclude={"include_trace"}). include_trace stays a plain
    field on BaziRequest so it remains a single OpenAPI component for the
    B2B/contract tests."""
    client = _client()
    r = client.post("/calculate/bazi", json=_ADR1_PAYLOAD)
    if r.status_code != 200:
        pytest.skip("Swiss Ephemeris files not available")
    assert "include_trace" not in r.json()["input"]
    # Yet the flag is still functional on input.
    r_off = client.post("/calculate/bazi", json={**_ADR1_PAYLOAD, "include_trace": False})
    assert r_off.status_code == 200
    assert r_off.json()["derivation_trace"] is None
    assert "include_trace" not in r_off.json()["input"]
