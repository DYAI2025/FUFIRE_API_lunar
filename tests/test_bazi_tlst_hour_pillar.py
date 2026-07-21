"""FBP-02-005 — TLST-derived hour pillar.

When a request opts into ``time_standard="TLST"``, the hour pillar
must be derived from True Local Solar Time (LMT + equation_of_time)
rather than from civil clock time. Concretely:

- At the timezone's standard meridian (e.g. 0° for UTC, 15° for CET),
  TLST equals LMT within ≈ 17 min of EoT. The hour-branch can still
  differ at the edge of a 2-hour Zi/Chou/Yin/… bin.
- For longitudes far from the standard meridian (e.g. Madrid at
  ~−3.7° in the CET zone, ~75 min west of meridian), TLST shifts the
  hour-of-day enough that the hour branch differs from LMT for
  birth times near a bin boundary.

Boundary case empirically verified pre-implementation:
Madrid 2024-02-22 02:00 civil →
  LMT chart_local: 00:45 → hour branch index 0 (Zi)
  TLST hours: 1.522 (EoT ≈ -13.86 min) → hour branch index 1 (Chou)
After Phase-2 these must produce different hour pillars.

The ``/calculate/bazi`` response shape returns each pillar as a dict
``{"stamm": "...", "zweig": "...", "tier": "...", "element": "..."}``,
so the assertions compare those dicts directly.
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from bazi_engine.app import app

client = TestClient(app)


def _post(payload: dict) -> dict:
    r = client.post("/calculate/bazi", json=payload)
    assert r.status_code == 200, r.text
    return r.json()


# Madrid: longitude ≈ -3.70°, in CET (standard meridian 15°), so
# LMT trails CIVIL by ~75 min and TLST trails LMT by EoT minutes.
# A birth at 02:00 civil on 2024-02-22 (EoT ≈ -13.86 min) puts
# LMT at ~00:45 (hour branch 0 = Zi) and TLST at ~01:31
# (hour branch 1 = Chou). So the hour pillar must differ once
# the Phase-1 clamp is removed.
_MADRID_BASE = {
    "date": "2024-02-22T02:00:00",
    "tz": "Europe/Madrid",
    "lon": -3.7038,
    "lat": 40.4168,
    "boundary": "midnight",
}


def test_madrid_boundary_case_tlst_hour_branch_differs_from_lmt():
    """Madrid late-Feb 02:00 civil: TLST hour branch ≠ LMT hour branch."""
    tlst = _post({**_MADRID_BASE, "standard": "TLST"})
    lmt = _post({**_MADRID_BASE, "standard": "LMT"})
    assert tlst["pillars"]["hour"] != lmt["pillars"]["hour"], (
        f"Expected hour-branch divergence at the Madrid boundary case; "
        f"got TLST={tlst['pillars']['hour']!r} LMT={lmt['pillars']['hour']!r}"
    )


def test_civil_request_unchanged_after_phase2():
    """A CIVIL request must produce the same hour pillar in Phase 2 as
    it did pre-FBP-02-005. Regression guard on the legacy default path.

    02:00 civil on Feb 22 in Europe/Madrid: hour=2 →
    branch_index = (2+1)//2 % 12 = 1 (Chou).
    """
    civil = _post({**_MADRID_BASE, "standard": "CIVIL"})
    assert civil["pillars"]["hour"]["zweig"] == "Chou", (
        f"Civil hour pillar at 02:00 must have zweig=Chou (branch=1); got "
        f"{civil['pillars']['hour']!r}"
    )


def test_tlst_request_no_longer_clamped_in_trace():
    """Post-FBP-02-005 the trace must record time_standard_used == TLST
    for a TLST request, not LMT (which was the Phase-1 clamp signature)."""
    r = client.post("/calculate/bazi", json={**_MADRID_BASE, "standard": "TLST"})
    assert r.status_code == 200, r.text
    hour_trace = r.json()["derivation_trace"]["hour"]
    assert hour_trace["time_standard_requested"] == "TLST"
    assert hour_trace["time_standard_used"] == "TLST", (
        "Phase-2 must remove the router clamp; trace should show "
        "time_standard_used=TLST, not LMT."
    )
