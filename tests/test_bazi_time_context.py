"""FBP-01-002 / FBP-01-006 — EffectiveTimeContext spec.

Properties enforced here:
- civil, utc are tz-aware datetimes.
- lmt_local is a tz-aware datetime in a *constant-offset* zone derived
  from longitude (NOT IANA, NOT DST-sensitive).
- tlst_hours is a float in [0, 24).
- date_rollover is the integer day shift relative to civil local date.
- TLST is NOT modeled as a tzinfo — there is no ``tlst_local`` field
  with a TLST tzinfo (FBP-01-006).
- The TLST formula matches the inline formula currently in
  ``bazi_engine/routers/fusion.py`` for ``/calculate/tst``
  (precondition for FBP-01-003 refactor).
"""
from __future__ import annotations

import math
from datetime import datetime, timezone

import pytest

from bazi_engine.time_context import (
    compute_effective_time_context,
)


def test_civil_and_utc_are_tz_aware():
    ctx = compute_effective_time_context(
        birth_local_iso="2024-02-10T14:30:00",
        tz_name="Europe/Berlin",
        longitude_deg=13.4050,
    )
    assert ctx.civil_local.tzinfo is not None
    assert ctx.utc.tzinfo == timezone.utc


def test_lmt_uses_longitude_offset_not_iana():
    """LMT is mean solar time at the given longitude (4 min/° east)."""
    ctx = compute_effective_time_context(
        birth_local_iso="2024-02-10T14:30:00",
        tz_name="Europe/Berlin",
        longitude_deg=13.4050,
    )
    expected_offset_min = 13.4050 * 4  # 53.62
    actual_offset_min = ctx.lmt_local.utcoffset().total_seconds() / 60
    assert math.isclose(actual_offset_min, expected_offset_min, abs_tol=0.1)


def test_tlst_is_not_a_tzinfo():
    """Stored as float hours + day offset, not as a datetime with tlst tzinfo."""
    ctx = compute_effective_time_context(
        birth_local_iso="2024-02-10T14:30:00",
        tz_name="Europe/Berlin",
        longitude_deg=13.4050,
    )
    assert isinstance(ctx.tlst_hours, float)
    assert 0.0 <= ctx.tlst_hours < 24.0
    assert not hasattr(ctx, "tlst_local"), (
        "TLST must not be modeled as a tzinfo. See FBP-01-006."
    )


def test_eot_minutes_matches_solar_time_module():
    """EoT must come from solar_time.equation_of_time, not be re-derived."""
    from bazi_engine.solar_time import equation_of_time
    ctx = compute_effective_time_context(
        birth_local_iso="2024-06-21T12:00:00",
        tz_name="UTC",
        longitude_deg=0.0,
    )
    day_of_year = 173  # June 21
    assert math.isclose(
        ctx.eot_minutes, equation_of_time(day_of_year), abs_tol=0.5
    )


def test_tlst_formula_matches_calculate_tst_endpoint():
    """FBP-01-003 precondition: same input must produce the same TLST hours
    as the inline formula in ``fusion.py:264-267`` currently uses."""
    from bazi_engine.solar_time import equation_of_time
    iso = "2024-06-21T12:00:00"
    tz = "Europe/Berlin"
    lon = 13.4050

    ctx = compute_effective_time_context(iso, tz, lon)
    civil_dt = datetime.fromisoformat(iso)
    civil_hours = civil_dt.hour + civil_dt.minute / 60 + civil_dt.second / 3600
    delta_t_long = lon * 4 / 60
    E_t = equation_of_time(civil_dt.timetuple().tm_yday) / 60
    expected = (civil_hours + delta_t_long + E_t) % 24
    assert math.isclose(ctx.tlst_hours, expected, abs_tol=1e-3), (
        f"EffectiveTimeContext.tlst_hours = {ctx.tlst_hours}, "
        f"fusion.py formula = {expected}"
    )


def test_date_rollover_when_tlst_crosses_midnight():
    """A civil time near midnight + far-east longitude pushes TLST past 24h.
    The context must record the day shift instead of dropping it via modulo.
    """
    # Civil 23:30 UTC at +30° E → LMT ≈ 01:30 next day.
    ctx = compute_effective_time_context(
        birth_local_iso="2024-06-15T23:30:00",
        tz_name="UTC",
        longitude_deg=30.0,
    )
    assert ctx.date_rollover == 1


def test_tz_offset_recorded_for_civil():
    """Civil offset must match the IANA zone's offset for that instant."""
    ctx = compute_effective_time_context(
        birth_local_iso="2024-06-15T12:00:00",
        tz_name="Europe/Berlin",
        longitude_deg=13.4050,
    )
    # CEST in June = UTC+2
    assert ctx.tz_offset_minutes == 120


def test_effective_time_context_is_frozen():
    """Immutability invariant — mirrors BaziInput / BaziResult / Provenance."""
    ctx = compute_effective_time_context(
        birth_local_iso="2024-02-10T14:30:00",
        tz_name="Europe/Berlin",
        longitude_deg=13.4050,
    )
    with pytest.raises(Exception):
        ctx.civil_local = None  # type: ignore[misc]


def test_lmt_tzname_includes_offset_signature():
    """The LMT tzinfo's tzname is informative (no IANA identity stolen)."""
    ctx = compute_effective_time_context(
        birth_local_iso="2024-02-10T14:30:00",
        tz_name="Europe/Berlin",
        longitude_deg=13.4050,
    )
    name = ctx.lmt_local.tzname() or ""
    assert "LMT" in name, name
