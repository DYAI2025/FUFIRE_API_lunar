"""EffectiveTimeContext — typed decomposition of a birth instant
across the three time standards used by the BaZi engine.

FBP-01-002 / FBP-01-006:

- ``CIVIL`` = legal local time in the IANA timezone (tz-aware).
- ``LMT``   = mean solar time at the given longitude (tz-aware, with a
              constant-offset tzinfo derived purely from longitude;
              NOT DST-sensitive, NOT registered with ``zoneinfo``).
- ``TLST``  = apparent solar time = LMT + equation_of_time. Stored as
              a float hour-of-day plus an integer ``date_rollover``.
              **Not** a tzinfo. TLST is not a legal/civil zone, and
              modeling it as a tzinfo would invite false symmetry with
              CIVIL/LMT.

Dependencies: stdlib + ``bazi_engine.solar_time`` (which is itself
stdlib-only). This module sits at Level 2 and must not import from
``bazi.py``, ``fusion.py``, or any router.

See ``docs/audits/fufire_bazi_precision_pre_audit.md`` §2 and
``docs/plans/2026-05-14-phase1-effective-time-model.md`` for context.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone, tzinfo
from typing import Optional
from zoneinfo import ZoneInfo

from .solar_time import equation_of_time


class _LongitudeMeanTime(tzinfo):
    """A constant-offset ``tzinfo`` for Local Mean Time at a given longitude.

    Not a real IANA zone; never observes DST; offset is purely
    ``longitude_deg × 4 min/° east``. Returned by
    ``EffectiveTimeContext.lmt_local.tzinfo`` so consumers can format
    the value, but the instance is **not** registered with
    ``zoneinfo`` and must not be passed where an IANA zone is required.
    """

    __slots__ = ("_offset",)

    def __init__(self, longitude_deg: float) -> None:
        self._offset = timedelta(minutes=longitude_deg * 4)

    def utcoffset(self, dt: Optional[datetime]) -> timedelta:
        return self._offset

    def dst(self, dt: Optional[datetime]) -> timedelta:
        return timedelta(0)

    def tzname(self, dt: Optional[datetime]) -> str:
        total_min = int(round(self._offset.total_seconds() / 60))
        sign = "+" if total_min >= 0 else "-"
        h, m = divmod(abs(total_min), 60)
        return f"LMT{sign}{h:02d}:{m:02d}"


@dataclass(frozen=True)
class EffectiveTimeContext:
    """All three time standards plus the metadata needed to diagnose
    boundary cases (TLST rollover, EoT magnitude, civil tz offset).

    Frozen by design — mirrors ``BaziInput`` / ``BaziResult`` /
    ``Provenance``. Build via :func:`compute_effective_time_context`.
    """

    civil_local: datetime           # tz-aware, IANA tz
    utc: datetime                   # tz-aware, UTC
    lmt_local: datetime             # tz-aware, constant longitude offset
    tlst_hours: float               # apparent solar hour-of-day, in [0, 24)
    eot_minutes: float              # equation of time, minutes
    tz_offset_minutes: int          # civil_local UTC offset, minutes
    date_rollover: int              # day shift of TLST relative to civil date


def compute_effective_time_context(
    birth_local_iso: str,
    tz_name: str,
    longitude_deg: float,
) -> EffectiveTimeContext:
    """Decompose a civil ISO timestamp + IANA zone + longitude into the
    three time standards.

    The caller is responsible for DST disambiguation upstream — by the
    time this function is invoked, ``birth_local_iso`` is expected to
    be the resolved naive ISO produced by
    :func:`bazi_engine.time_utils.resolve_local_iso`.

    Parameters
    ----------
    birth_local_iso
        Naive ISO 8601 local datetime, e.g. ``"2024-02-10T14:30:00"``.
    tz_name
        IANA timezone name, e.g. ``"Europe/Berlin"``.
    longitude_deg
        Geographic longitude, degrees east (negative = west).

    Returns
    -------
    EffectiveTimeContext
        Immutable record. ``tlst_hours`` is the apparent-solar
        hour-of-day in ``[0, 24)``; if the raw TLST crosses a day
        boundary, ``date_rollover`` records the shift (``+1`` if TLST
        is the next day, ``-1`` if previous day).
    """
    civil_naive = datetime.fromisoformat(birth_local_iso)
    civil_local = civil_naive.replace(tzinfo=ZoneInfo(tz_name))
    utc = civil_local.astimezone(timezone.utc)

    lmt_tz = _LongitudeMeanTime(longitude_deg)
    lmt_local = utc.astimezone(lmt_tz)

    day_of_year = civil_local.timetuple().tm_yday
    eot_min = float(equation_of_time(day_of_year))
    # Civil hours + longitude correction + EoT. Matches the inline
    # formula in ``bazi_engine/routers/fusion.py:264-267``; the
    # endpoint will be migrated to this function in FBP-01-003.
    civil_hours = (
        civil_local.hour
        + civil_local.minute / 60
        + civil_local.second / 3600
    )
    delta_t_long = longitude_deg * 4 / 60
    raw_tlst = civil_hours + delta_t_long + (eot_min / 60)
    tlst_hours = raw_tlst % 24.0
    # Day rollover: integer floor of (raw / 24) so that negative raw
    # values (west of meridian, very early morning civil) produce a
    # ``-1`` rollover rather than a stale positive remainder.
    if raw_tlst >= 0:
        rollover = int(raw_tlst // 24.0)
    else:
        rollover = -int((-raw_tlst + 24.0 - 1e-9) // 24.0)

    tz_off = civil_local.utcoffset()
    tz_off_min = 0 if tz_off is None else int(round(tz_off.total_seconds() / 60))

    return EffectiveTimeContext(
        civil_local=civil_local,
        utc=utc,
        lmt_local=lmt_local,
        tlst_hours=round(tlst_hours, 6),
        eot_minutes=round(eot_min, 4),
        tz_offset_minutes=tz_off_min,
        date_rollover=rollover,
    )
