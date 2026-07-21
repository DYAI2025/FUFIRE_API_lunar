"""Chinese lunisolar calendar protocol, result type, and swisseph provider.

Two layers live here:

1. The **interface seed** — :class:`ResolvedLunarDate` (frozen, self-validating)
   and the :class:`ChineseLunisolarCalendar` structural :class:`~typing.Protocol`.
   These define *what* a lunisolar conversion returns and the contract every
   provider must satisfy. They depend only on the standard library.

2. The concrete **swisseph-native provider** — :class:`SwissephLunisolarCalendar`
   — implementing the modern Chinese calendar (時憲曆 / Shíxiàn, post-1645):
   中氣-based month numbering anchored on the winter-solstice month (=11) with
   the "first lunar month containing no 中氣" leap rule. It computes purely from
   the ZWDS astronomical primitives (:mod:`bazi_engine.zwds.astro_moon` true new
   moons + :func:`bazi_engine.jieqi.find_crossing` solar-term crossings) and the
   standard library — no third-party lunar/Chinese-calendar library at runtime
   (design pack runtime rule D-1). Importing this module therefore pulls in the
   Level-2/3 astronomy modules; the engine-separation contract
   (``tests/test_import_hierarchy.py``) still holds because those are not the
   BaZi engine (``bazi``/``western``/``fusion``/``impact``).

``ResolvedLunarDate`` is frozen and self-validating: an instance can only ever
hold a numbered lunar month (1..12), a valid day (1..30), and a real lunation
length (29 or 30). Invalid conversions are impossible to represent rather than
merely discouraged.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import List, Optional, Protocol, Tuple, runtime_checkable

from bazi_engine.ephemeris import (
    SwissEphBackend,
    datetime_utc_to_jd_ut,
    jd_ut_to_datetime_utc,
    norm360,
)
from bazi_engine.exc import CalculationError
from bazi_engine.jieqi import find_crossing
from bazi_engine.zwds.astro_moon import previous_new_moon


@dataclass(frozen=True)
class ResolvedLunarDate:
    """A civil date resolved onto the Chinese lunisolar calendar.

    Attributes:
        year_label: The civil year the lunar year is labelled by.
        month: Numbered lunar month, ``1..12``.
        day: Day within the lunation, ``1..30``.
        is_leap_month: ``True`` when this lunation is the leap (intercalary)
            month duplicating ``month``.
        month_length: Number of days in this lunation — ``29`` (short) or
            ``30`` (long).
        calendar_engine_id: Provenance tag identifying the converting engine
            and its data (e.g. ``"fufire-swisseph-shixian.v1"``).
    """

    year_label: int
    month: int
    day: int
    is_leap_month: bool
    month_length: int
    calendar_engine_id: str

    def __post_init__(self) -> None:
        if not 1 <= self.month <= 12:
            raise ValueError(f"month must be in 1..12, got {self.month}")
        if not 1 <= self.day <= 30:
            raise ValueError(f"day must be in 1..30, got {self.day}")
        if self.month_length not in (29, 30):
            raise ValueError(
                f"month_length must be 29 or 30, got {self.month_length}"
            )


@runtime_checkable
class ChineseLunisolarCalendar(Protocol):
    """Structural contract for a deterministic lunisolar calendar provider.

    Any object exposing a ``resolve(date) -> ResolvedLunarDate`` method
    satisfies this protocol by duck typing — no explicit subclassing required.
    Implementations must be local and deterministic at runtime.
    """

    def resolve(self, chart_local_date: date) -> ResolvedLunarDate: ...


# ── Swiss-Ephemeris 時憲曆 provider ───────────────────────────────────────────

_DEFAULT_CALENDAR_ENGINE_ID = "fufire-swisseph-shixian.v1"

# 冬至 (winter solstice) is Sun apparent ecliptic longitude 270° and anchors
# lunar month 11. The 12 中氣 (principal terms) fall on multiples of 30°.
_WINTER_SOLSTICE_LON = 270.0
_ZHONGQI_STEP_DEG = 30.0

# Root-finding accuracy for solar-term crossings (~1 s, same as astro_moon).
_CROSSING_ACCURACY_SECONDS = 1.0

# Seed offset for the backward month-walk: one day past the longest possible
# synodic month (~29.84 d), so ``previous_new_moon`` from the seed lands on the
# immediately-following conjunction (~29.53 d out) with a short backward scan
# rather than a full forward scan, and never overshoots to the one after
# (~59 d out). Unambiguous and much cheaper than a forward search per month.
_NEXT_MONTH_SEED = timedelta(days=30, hours=12)

# Backward span for the "winter solstice on or before" search (> one tropical
# year, so at least one 冬至 is always bracketed in the window).
_SOLSTICE_BACK_SCAN_DAYS = 400.0

# Days before month-11 to seed a reference into the *previous* solstice-to-
# solstice span (used to find the preceding 正月 for the year label).
_PREV_SUI_LOOKBACK = timedelta(days=60)


@dataclass(frozen=True)
class _NumberedSui:
    """One 冬至→冬至 span with every lunation numbered per the 中氣 rule.

    ``months`` lists ``(month_start_utc, month_number, is_leap)`` from the
    opening month-11 (contains the first 冬至) through the closing month-11
    (contains the next 冬至, i.e. the following span's opening month).
    ``zhengyue_start`` is the 正月 (month 1, non-leap) start in this span.
    """

    m11a_start: datetime
    months: Tuple[Tuple[datetime, int, bool], ...]
    zhengyue_start: datetime


class SwissephLunisolarCalendar:
    """Modern Chinese lunisolar calendar (時憲曆 / Shíxiàn, post-1645), swisseph-native.

    Implements :class:`ChineseLunisolarCalendar`. Months run from one true
    new-moon day (inclusive) to the next (exclusive); day 1 is the civil day
    containing the new-moon instant. Month numbers follow the 中氣 the month
    contains, anchored so the month containing 冬至 (Sun = 270°) is month 11.
    A 冬至→冬至 span with 13 lunations has exactly one leap month: the first
    lunation in the span containing no 中氣 — it repeats the preceding month's
    number and sets ``is_leap_month=True``.

    Civil-day boundaries are taken in a fixed local frame: a UTC instant is
    floored to a civil day by adding ``day_boundary_offset_hours`` and taking
    the date (core-seed policy ``local-civil-day.v1``). ``chart_local_date`` is
    assumed to already be in that same local frame.
    """

    def __init__(
        self,
        *,
        day_boundary_offset_hours: float,
        calendar_engine_id: str = _DEFAULT_CALENDAR_ENGINE_ID,
    ) -> None:
        self.day_boundary_offset_hours = day_boundary_offset_hours
        self.calendar_engine_id = calendar_engine_id
        self._offset = timedelta(hours=day_boundary_offset_hours)

    # ── public API ───────────────────────────────────────────────────────────
    def resolve(self, chart_local_date: date) -> ResolvedLunarDate:
        backend = SwissEphBackend()

        # 1-3. The lunation owning the chart day → day-of-month and length.
        month_start = self._month_start_owning_day(chart_local_date)
        next_start = self._next_month_start(month_start)
        ms_day = self._local_day(month_start)
        ns_day = self._local_day(next_start)
        day = (chart_local_date - ms_day).days + 1
        month_length = (ns_day - ms_day).days

        # 4. Month number + leap flag from the enclosing 冬至→冬至 span.
        sui = self._number_sui(chart_local_date, backend)
        number, is_leap = self._lookup_month(sui, month_start)

        # 5. Year label = Gregorian year of the 正月 on or before this month.
        year_label = self._year_label(sui, month_start, backend)

        return ResolvedLunarDate(
            year_label=year_label,
            month=number,
            day=day,
            is_leap_month=is_leap,
            month_length=month_length,
            calendar_engine_id=self.calendar_engine_id,
        )

    # ── day-boundary helpers ─────────────────────────────────────────────────
    def _local_day(self, instant: datetime) -> date:
        """Floor a UTC instant to its civil day in the local (offset) frame."""
        return (instant.astimezone(timezone.utc) + self._offset).date()

    def _local_midnight_utc(self, day: date) -> datetime:
        """UTC instant of 00:00 local (offset frame) on the given civil day."""
        naive_local = datetime(day.year, day.month, day.day)
        return naive_local.replace(tzinfo=timezone.utc) - self._offset

    def _local_noon_utc(self, day: date) -> datetime:
        """UTC instant of 12:00 local (offset frame) on the given civil day."""
        naive_local = datetime(day.year, day.month, day.day, 12)
        return naive_local.replace(tzinfo=timezone.utc) - self._offset

    # ── lunation helpers ─────────────────────────────────────────────────────
    def _month_start_owning_day(self, day: date) -> datetime:
        """New-moon start of the lunation that owns civil ``day``.

        = the latest true new moon whose civil day is ≤ ``day`` (so
        ``day`` lies within ``[day1, next_day1)``).

        ``previous_new_moon`` carries a small forward margin
        (``_BACK_SCAN_MARGIN_DAYS`` ≈ 29 min) so a conjunction essentially *at* its
        seed resolves to itself. When a new moon falls within that margin just
        after local midnight of ``day + 1`` — i.e. its civil day is the *next* day
        — the seeded backward search overshoots forward onto that next-day
        conjunction, which would place ``day`` at day-of-month 0. Guard the
        contract explicitly: if the candidate's civil day is past ``day``, step
        back to the preceding conjunction, the true owner of ``day``. (Overshoot is
        bounded to a single civil day, so this runs at most once.)
        """
        end_of_day_utc = self._local_midnight_utc(day + timedelta(days=1)) - timedelta(seconds=1)
        ms = previous_new_moon(end_of_day_utc)
        while self._local_day(ms) > day:
            ms = previous_new_moon(ms - timedelta(days=1))
        return ms

    def _next_month_start(self, month_start: datetime) -> datetime:
        """New-moon start of the lunation immediately after ``month_start``."""
        return previous_new_moon(month_start + _NEXT_MONTH_SEED)

    # ── solar-term helpers ───────────────────────────────────────────────────
    def _winter_solstice_on_or_before(self, day: date, backend: SwissEphBackend) -> datetime:
        """Latest 冬至 (Sun = 270°) whose civil day is ≤ ``day``."""
        jd_ref = datetime_utc_to_jd_ut(self._local_noon_utc(day))
        jd = jd_ref - _SOLSTICE_BACK_SCAN_DAYS
        last: Optional[datetime] = None
        # Solstices are ~365 d apart, so this loop runs ~2 iterations.
        while True:
            jd_c = find_crossing(
                backend,
                _WINTER_SOLSTICE_LON,
                jd,
                accuracy_seconds=_CROSSING_ACCURACY_SECONDS,
                max_span_days=_SOLSTICE_BACK_SCAN_DAYS + 40.0,
            )
            c_utc = jd_ut_to_datetime_utc(jd_c)
            if self._local_day(c_utc) <= day:
                last = c_utc
                jd = jd_c + 1.0
            else:
                break
        if last is None:  # pragma: no cover - window always brackets a solstice
            raise CalculationError(
                "Failed to bracket a winter solstice on or before the reference day",
                detail={"day": day.isoformat(), "offset_hours": self.day_boundary_offset_hours},
            )
        return last

    def _no_zhongqi(
        self, month_start: datetime, next_start: datetime, backend: SwissEphBackend
    ) -> bool:
        """True iff the lunation ``[month_start, next_start)`` contains no 中氣.

        A 中氣 is a Sun-longitude multiple of 30°. The month contains one iff a
        crossing's civil day falls in ``[day1, next_day1)``. The search starts at
        local-midnight of day 1 (not the new-moon instant) so a 中氣 sharing day 1
        with the new moon is correctly attributed to this month. The wrap at
        330°→0° is handled by :func:`norm360` on the target longitude.
        """
        day1 = self._local_day(month_start)
        next_day1 = self._local_day(next_start)
        jd_start = datetime_utc_to_jd_ut(self._local_midnight_utc(day1))
        sun_lon = backend.sun_lon_deg_ut(jd_start)
        # Next 中氣 longitude strictly ahead of the Sun at day-1 midnight; the
        # -1e-6 nudge treats a Sun essentially *at* a multiple of 30° as that
        # (boundary) term rather than skipping a full 30° to the next one.
        k = math.floor(sun_lon / _ZHONGQI_STEP_DEG - 1e-6)
        target = norm360(_ZHONGQI_STEP_DEG * (k + 1))
        jd_zq = find_crossing(
            backend,
            target,
            jd_start,
            accuracy_seconds=_CROSSING_ACCURACY_SECONDS,
            max_span_days=40.0,
        )
        zq_day = self._local_day(jd_ut_to_datetime_utc(jd_zq))
        return not (day1 <= zq_day < next_day1)

    # ── month numbering (中氣 anchor + no-中氣 leap rule) ─────────────────────
    def _number_sui(self, day: date, backend: SwissEphBackend) -> _NumberedSui:
        """Number every lunation of the 冬至→冬至 span containing ``day``."""
        s1 = self._winter_solstice_on_or_before(day, backend)
        s2 = self._winter_solstice_on_or_before(
            self._local_day(s1) + timedelta(days=370), backend
        )
        m11a_start = self._month_start_owning_day(self._local_day(s1))
        m11b_start = self._month_start_owning_day(self._local_day(s2))

        # Enumerate lunation starts m11a … m11b (inclusive).
        starts: List[datetime] = [m11a_start]
        m11b_day = self._local_day(m11b_start)
        cur = m11a_start
        while self._local_day(cur) < m11b_day:
            cur = self._next_month_start(cur)
            starts.append(cur)

        leap_sui = (len(starts) - 1) == 13  # 13 lunations m11a→m11b ⇒ one leap

        numbered: List[Tuple[datetime, int, bool]] = []
        num = 11
        leap_found = False
        zhengyue_start: Optional[datetime] = None
        for i, ms in enumerate(starts):
            if i == 0:
                numbered.append((ms, 11, False))  # month 11 (contains 冬至)
                continue
            ms_next = starts[i + 1] if i + 1 < len(starts) else self._next_month_start(ms)
            if leap_sui and not leap_found and self._no_zhongqi(ms, ms_next, backend):
                numbered.append((ms, num, True))  # leap: repeats preceding number
                leap_found = True
            else:
                num = (num % 12) + 1  # 11→12→1→2→…
                numbered.append((ms, num, False))
                if num == 1 and zhengyue_start is None:
                    zhengyue_start = ms

        if zhengyue_start is None:  # pragma: no cover - every span has a 正月
            raise CalculationError(
                "Failed to locate 正月 (month 1) in the solstice span",
                detail={"day": day.isoformat()},
            )
        return _NumberedSui(m11a_start, tuple(numbered), zhengyue_start)

    def _lookup_month(self, sui: _NumberedSui, month_start: datetime) -> Tuple[int, bool]:
        target_day = self._local_day(month_start)
        for ms, number, is_leap in sui.months:
            if self._local_day(ms) == target_day:
                return number, is_leap
        raise CalculationError(  # pragma: no cover - target always inside its span
            "Target lunation not found within its enclosing solstice span",
            detail={"target_day": target_day.isoformat()},
        )

    def _year_label(
        self, sui: _NumberedSui, month_start: datetime, backend: SwissEphBackend
    ) -> int:
        """Gregorian year of the 正月 (month 1) on or before ``month_start``."""
        if self._local_day(sui.zhengyue_start) <= self._local_day(month_start):
            return self._local_day(sui.zhengyue_start).year
        # Target is a month-11/12 preceding this span's 正月 → the labelling 正月
        # is the previous span's.
        prev_ref = self._local_day(sui.m11a_start) - _PREV_SUI_LOOKBACK
        prev_sui = self._number_sui(prev_ref, backend)
        return self._local_day(prev_sui.zhengyue_start).year


def build_core_seed_calendar(
    day_boundary_offset_hours: float,
) -> SwissephLunisolarCalendar:
    """Build the core-seed lunisolar calendar (``local-civil-day.v1`` boundary).

    The day boundary follows the chart's own effective-local frame; pass the
    chart's UTC offset in hours (e.g. ``8`` for CST / Asia/Shanghai).
    """
    return SwissephLunisolarCalendar(day_boundary_offset_hours=day_boundary_offset_hours)
