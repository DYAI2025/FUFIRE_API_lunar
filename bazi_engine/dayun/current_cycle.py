"""Select the Da-Yun cycle currently active at an as_of date.

Age is computed in real Gregorian mean-year units, consistent with the real
decade dates emitted by the endpoint (see ``dayun/dates.add_real_years``).
Cycles are interpreted as half-open intervals ``[age_start, age_end)`` — lower
bound inclusive, upper exclusive.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Optional, Sequence, Union

_DAYS_PER_YEAR = 365.2425
_SECONDS_PER_DAY = 86_400.0

DateLike = Union[date, datetime, str]


def _normalize_to_datetime(value: DateLike) -> datetime:
    """Coerce ``date``, ``datetime``, or ISO 8601 string into tz-aware ``datetime``.

    Naive datetimes and pure dates are assigned UTC at midnight.
    """
    if isinstance(value, str):
        value = datetime.fromisoformat(value)
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day, tzinfo=timezone.utc)
    raise TypeError(f"Unsupported date-like input: {type(value).__name__}")


def select_current(
    cycles: Sequence[dict],
    *,
    birth: DateLike,
    as_of: DateLike,
) -> Optional[dict]:
    """Return the cycle dict whose ``[age_start, age_end)`` bracket the current age.

    Returns ``None`` when no cycle covers the as_of date (before the first,
    past the last, on an empty list, or when ``as_of`` precedes ``birth``).
    Pure function — does not mutate ``cycles``.
    """
    if not cycles:
        return None

    birth_dt = _normalize_to_datetime(birth)
    as_of_dt = _normalize_to_datetime(as_of)

    delta_seconds = (as_of_dt - birth_dt).total_seconds()
    if delta_seconds < 0:
        return None

    current_age = delta_seconds / _SECONDS_PER_DAY / _DAYS_PER_YEAR

    for cycle in cycles:
        if cycle["age_start"] <= current_age < cycle["age_end"]:
            return cycle
    return None
