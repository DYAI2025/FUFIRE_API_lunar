"""Da-Yun jieqi anchor resolver.

Thin adapter over :mod:`bazi_engine.jieqi` (solar-term crossing engine) that
returns the nearest jieqi anchor in a requested flow direction from a birth
datetime, along with the time delta from birth to that anchor.

The adapter exists for the `/calculate/bazi/dayun` endpoint and is consumed
by the start-age converter (TASK-DY-008) and the endpoint handler
(TASK-DY-010).

Naming convention
-----------------
The underlying engine uses single-word Pinyin (``"Xiaoshu"``, ``"Lichun"``)
in :data:`bazi_engine.phases.jieqi_phase.JIEQI_PHASES`.  The Da-Yun response
schema (``$defs.JieqiEnum``) requires the space-separated two-syllable form
(``"Xiao Shu"``, ``"Li Chun"``).  The translation table below is the single
source of the schema vocabulary in this module.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from ..ephemeris import (
    EphemerisBackend,
    SwissEphBackend,
    datetime_utc_to_jd_ut,
    jd_ut_to_datetime_utc,
)
from ..exc import InputError
from ..jieqi import find_crossing

# Schema-form Pinyin names ordered by jieqi index 0..23 starting at Li Chun
# (315° solar longitude).  Order matches `JIEQI_PHASES` in
# `bazi_engine/phases/jieqi_phase.py` and the `JieqiEnum` in
# `schemas/calculate/bazi/dayun.response.schema.json`.
_JIEQI_NAMES_SCHEMA_FORM = [
    "Li Chun", "Yu Shui", "Jing Zhe", "Chun Fen",
    "Qing Ming", "Gu Yu", "Li Xia", "Xiao Man",
    "Mang Zhong", "Xia Zhi", "Xiao Shu", "Da Shu",
    "Li Qiu", "Chu Shu", "Bai Lu", "Qiu Fen",
    "Han Lu", "Shuang Jiang", "Li Dong", "Xiao Xue",
    "Da Xue", "Dong Zhi", "Xiao Han", "Da Han",
]

# Bisection accuracy for the underlying ephemeris crossing solver.
_ACCURACY_SECONDS = 1.0

# Half-window (days) for the local jieqi scan around birth.  Maximum gap
# between consecutive jieqi is ~16 days, so 30 days is a safe envelope.
_WINDOW_HALF_DAYS = 30.0


def resolve_jieqi_anchor(
    birth_local: datetime,
    direction: str,
    *,
    backend: Optional[EphemerisBackend] = None,
) -> dict:
    """Return the nearest jieqi anchor in the given direction from ``birth_local``.

    Args:
        birth_local: Birth datetime; MUST be tz-aware.
        direction:   ``"forward"`` (nearest jieqi strictly AFTER birth) or
                     ``"backward"`` (nearest jieqi strictly BEFORE birth).
        backend:     Optional :class:`EphemerisBackend`; defaults to
                     :class:`SwissEphBackend`.

    Returns:
        ``{"name": str, "direction": str, "local_dt": str, "delta": {...}}``
        where ``name`` is the schema-form Pinyin (``"Xiao Shu"``),
        ``direction`` is ``"next"``/``"previous"`` mirroring the input,
        ``local_dt`` is the anchor ISO 8601 datetime in ``birth_local``'s
        timezone, and ``delta`` contains non-negative ``days``/``hours``/
        ``minutes`` from birth to the anchor (sub-minute precision dropped).

    Raises:
        InputError: if ``birth_local`` is naive or ``direction`` is not one
            of ``"forward"`` / ``"backward"``.
    """
    if birth_local.tzinfo is None:
        raise InputError(
            "birth_local must be a tz-aware datetime (naive datetime rejected)",
            detail={"got_tzinfo": None},
        )
    if direction not in ("forward", "backward"):
        raise InputError(
            "direction must be 'forward' or 'backward'",
            detail={"got_direction": direction},
        )

    if backend is None:
        backend = SwissEphBackend()

    # Convert birth to UTC JD.
    birth_utc = birth_local.astimezone(timezone.utc)
    birth_jd = datetime_utc_to_jd_ut(birth_utc)

    # Scan a ±_WINDOW_HALF_DAYS window around birth for all 24 jieqi
    # longitude crossings.  For each target longitude we ask `find_crossing`
    # for the first crossing on/after the window start.  Because consecutive
    # jieqi for a given longitude are ~365 days apart, each longitude yields
    # at most one crossing inside the window.
    window_start_jd = birth_jd - _WINDOW_HALF_DAYS
    window_end_jd = birth_jd + _WINDOW_HALF_DAYS

    crossings: list[tuple[int, float]] = []  # (phase_idx, jd_ut)
    for phase_idx, name in enumerate(_JIEQI_NAMES_SCHEMA_FORM):
        # Target longitude for this phase: Li Chun=315°, then +15° each step.
        target_lon = (315.0 + 15.0 * phase_idx) % 360.0
        try:
            jd = find_crossing(
                backend,
                target_lon,
                window_start_jd,
                accuracy_seconds=_ACCURACY_SECONDS,
                max_span_days=2 * _WINDOW_HALF_DAYS,
            )
        except Exception:
            # find_crossing raises CalculationError if it can't bracket
            # within the span.  Skip — this longitude doesn't cross inside
            # our window.
            continue
        if window_start_jd <= jd <= window_end_jd:
            crossings.append((phase_idx, jd))

    if not crossings:
        # Shouldn't happen — within ~30 days of any date there's always at
        # least one jieqi crossing.  Surface as InputError so callers see a
        # clean envelope rather than a swallowed engine failure.
        raise InputError(
            "no jieqi crossing found in ±30-day window around birth",
            detail={"birth_jd_ut": birth_jd},
        )

    if direction == "forward":
        # Strictly after birth.
        candidates = [(idx, jd) for (idx, jd) in crossings if jd > birth_jd]
        if not candidates:
            raise InputError(
                "no jieqi crossing found strictly after birth in the search window",
                detail={"birth_jd_ut": birth_jd},
            )
        anchor_idx, anchor_jd = min(candidates, key=lambda x: x[1])
        out_direction = "next"
    else:  # backward
        candidates = [(idx, jd) for (idx, jd) in crossings if jd < birth_jd]
        if not candidates:
            raise InputError(
                "no jieqi crossing found strictly before birth in the search window",
                detail={"birth_jd_ut": birth_jd},
            )
        anchor_idx, anchor_jd = max(candidates, key=lambda x: x[1])
        out_direction = "previous"

    # Anchor → datetime in birth's local tz.  The bisection solver is only
    # accurate to ~1 second so sub-second precision is meaningless noise.
    anchor_utc = jd_ut_to_datetime_utc(anchor_jd).replace(microsecond=0)
    anchor_local = anchor_utc.astimezone(birth_local.tzinfo)

    # Delta in UTC to avoid DST artifacts; non-negative; sub-minute dropped.
    delta_seconds_total = abs((anchor_utc - birth_utc).total_seconds())
    total_minutes = int(delta_seconds_total // 60)  # floor toward zero
    days, rem_minutes = divmod(total_minutes, 24 * 60)
    hours, minutes = divmod(rem_minutes, 60)

    return {
        "name": _JIEQI_NAMES_SCHEMA_FORM[anchor_idx],
        "direction": out_direction,
        "local_dt": anchor_local.isoformat(),
        "delta": {
            "days": days,
            "hours": hours,
            "minutes": minutes,
        },
    }
