from datetime import date, datetime, timedelta

_MEAN_YEAR_DAYS = 365.2425  # Gregorian mean year; used only for the sub-year remainder


def add_real_years(base: datetime, years: float) -> date:
    """Return the real Gregorian date `years` real years after `base`.

    Whole years are added on the calendar (leap-aware); the fractional remainder
    is added as `frac * 365.2425` days. Feb-29 anchors clamp to Feb-28 in a
    non-leap target year. Decade spans are therefore ~3652-3653 days, not 3600.
    """
    whole = int(years)
    frac = years - whole
    y = base.year + whole
    try:
        anchored = base.replace(year=y)
    except ValueError:      # base is Feb 29, target year not leap
        anchored = base.replace(year=y, day=28)
    return (anchored + timedelta(days=frac * _MEAN_YEAR_DAYS)).date()
