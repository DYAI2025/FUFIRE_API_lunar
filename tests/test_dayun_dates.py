"""Unit tests for bazi_engine.dayun.dates.add_real_years (SF-1).

Locks the real-Gregorian-year calendar helper that replaces the buggy
360-day "ritual year" date arithmetic in the Da-Yun endpoint. Whole years
advance leap-aware on the calendar; the sub-year remainder is added as
frac * 365.2425 days, so decade spans are ~3652-3653 days, not 3600.
"""
from __future__ import annotations

from datetime import date, datetime

from bazi_engine.dayun.dates import add_real_years


def test_whole_year_add_lands_on_same_calendar_day():
    """+10.0 real years advances the calendar year, keeping month/day."""
    base = datetime(1987, 7, 4, 21, 30)
    assert add_real_years(base, 10.0) == date(1997, 7, 4)


def test_fractional_add_within_one_day_of_base_plus_182():
    """+0.5 real years ≈ base + 182 days (365.2425/2), within ±1 day."""
    base = datetime(1990, 6, 15)
    result = add_real_years(base, 0.5)
    expected = (base + __import__("datetime").timedelta(days=182)).date()
    assert abs((result - expected).days) <= 1


def test_decade_span_is_real_gregorian_not_360():
    """A real decade spans ~3652-3653 days (not the old 3600), leap-aware."""
    base = datetime(1990, 6, 15)
    span = (add_real_years(base, 10) - add_real_years(base, 0)).days
    assert 3652 <= span <= 3653


def test_feb_29_anchor_clamps_to_feb_28_in_non_leap_year():
    """Feb-29 base + 1.0 year clamps to Feb-28 when the target year isn't leap."""
    base = datetime(2000, 2, 29)
    assert add_real_years(base, 1.0) == date(2001, 2, 28)
