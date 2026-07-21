"""ZWDS-P1-02 — Swiss-Ephemeris true new-moon (sun–moon conjunction) search.

The lunisolar ZWDS calendar numbers months from *true* new moons — the instants
of geocentric sun–moon conjunction (elongation = 0). This module is the
astronomical primitive: given any UTC instant it finds the surrounding true new
moons. A later task consumes these to number lunar months.

Design mirrors ``bazi_engine.jieqi`` (solar-longitude bisection): a coarse
forward/backward scan brackets the root, then a bisection refines it. Where
``jieqi`` roots the *sun's* ecliptic longitude against a fixed target, this
module roots the *signed sun→moon elongation* against zero.

Signed elongation at a UT Julian Day ``jd``::

    sun_lon  = swe.calc_ut(jd, swe.SUN)[0][0]     # apparent ecliptic lon, deg
    moon_lon = swe.calc_ut(jd, swe.MOON)[0][0]
    elong    = ((moon_lon - sun_lon + 180.0) % 360.0) - 180.0   # in (-180, 180]

``elong`` is 0 at conjunction (new moon), climbs ~+12°/day through the synodic
month, hits +180 at full moon, wraps to −180, then climbs back to 0 at the next
new moon. The new moon is the **upward** zero-crossing (− → +); the full-moon
+180/−180 wrap is a *downward* discontinuity and is additionally rejected by a
small-magnitude guard on both bracket samples.

Ephemeris handling follows the repo idiom: a ``SwissEphBackend`` is constructed
per call (respecting ``SE_EPHE_PATH`` / ``EPHEMERIS_MODE``), and every body
position goes through ``backend.calc_ut`` so the silent-MOSEPH-fallback guard
(FQ-ATT-01) applies here too. Functions are pure/deterministic — no caching.
"""

from __future__ import annotations

from datetime import datetime, timezone

import swisseph as swe

from bazi_engine.ephemeris import (
    SwissEphBackend,
    datetime_utc_to_jd_ut,
    jd_ut_to_datetime_utc,
)
from bazi_engine.exc import CalculationError

# Mean days between successive new moons. Used ONLY to size search windows —
# never returned as the answer (the answer is always a bisected conjunction).
MEAN_SYNODIC_MONTH = 29.530588

# Coarse scan step (days). Near conjunction the elongation moves ~+3°/step, so
# consecutive samples that straddle 0 both sit well inside the guard band.
_COARSE_STEP_DAYS = 0.25
# Reject brackets whose samples are far from 0 (kills the full-moon ±180 wrap,
# whose samples are ~±180, from ever being mistaken for a conjunction root).
_ELONGATION_GUARD_DEG = 30.0
# Bisection target accuracy (~1 s ⇒ ~1.2e-5 day, comfortably < 1e-4 day / 8.6 s).
_BISECTION_ACCURACY_SECONDS = 1.0
_BISECTION_MAX_ITER = 80
# One synodic month plus slack — always enough to bracket exactly one new moon
# in either direction from any seed instant.
_MAX_SCAN_DAYS = MEAN_SYNODIC_MONTH + 2.0
# Small forward margin for the backward search so a conjunction sitting
# essentially AT the seed instant is still bracketed on its upper side. The
# elongation's sign right at conjunction is ambiguous to within a fraction of an
# arcsecond; this margin (~29 min) guarantees the upper sample is positive.
_BACK_SCAN_MARGIN_DAYS = 0.02


def _to_jd_ut(dt_utc: datetime) -> float:
    """Convert a tz-aware datetime to a UT Julian Day (rejects naive input)."""
    if dt_utc.tzinfo is None or dt_utc.utcoffset() is None:
        raise ValueError("dt_utc must be timezone-aware (UTC)")
    return datetime_utc_to_jd_ut(dt_utc.astimezone(timezone.utc))


def _signed_elongation_deg(backend: SwissEphBackend, jd_ut: float) -> float:
    """Signed geocentric sun→moon ecliptic elongation, degrees, in (-180, 180].

    0 at conjunction (new moon), +180 at opposition (full moon). Every position
    is fetched through ``backend.calc_ut`` so the FQ-ATT-01 silent-MOSEPH guard
    covers this call site.
    """
    sun_lon = backend.calc_ut(jd_ut, swe.SUN)[0][0]
    moon_lon = backend.calc_ut(jd_ut, swe.MOON)[0][0]
    return ((moon_lon - sun_lon + 180.0) % 360.0) - 180.0


def _is_upward_conjunction_bracket(e_lo: float, e_hi: float) -> bool:
    """True iff ``[e_lo, e_hi]`` brackets an upward (− → +) zero-crossing near 0.

    The magnitude guard on both samples excludes the full-moon +180/−180 wrap.
    """
    return (
        abs(e_lo) < _ELONGATION_GUARD_DEG
        and abs(e_hi) < _ELONGATION_GUARD_DEG
        and e_lo <= 0.0 <= e_hi
    )


def _bisect_conjunction(backend: SwissEphBackend, jd_lo: float, jd_hi: float) -> float:
    """Bisect ``[jd_lo, jd_hi]`` (elongation ≤ 0 at lo, ≥ 0 at hi) to the root.

    Elongation is monotonic-increasing across a new moon, so a plain sign
    bisection converges. Mirrors ``jieqi._bisection_crossing`` in spirit.
    """
    tol_days = _BISECTION_ACCURACY_SECONDS / 86400.0
    lo, hi = jd_lo, jd_hi
    f_lo = _signed_elongation_deg(backend, lo)
    if f_lo == 0.0:
        return lo
    for _ in range(_BISECTION_MAX_ITER):
        if abs(hi - lo) <= tol_days:
            break
        mid = 0.5 * (lo + hi)
        f_mid = _signed_elongation_deg(backend, mid)
        if f_mid == 0.0:
            return mid
        if f_lo * f_mid < 0.0:
            hi = mid
        else:
            lo, f_lo = mid, f_mid
    return 0.5 * (lo + hi)


def next_new_moon(dt_utc: datetime) -> datetime:
    """Return the first true new moon at/after ``dt_utc`` as tz-aware UTC.

    Scans forward in coarse steps to bracket the next upward elongation
    zero-crossing, then bisects to ~1 s.
    """
    backend = SwissEphBackend()
    jd_lo = _to_jd_ut(dt_utc)
    e_lo = _signed_elongation_deg(backend, jd_lo)
    steps = int(_MAX_SCAN_DAYS / _COARSE_STEP_DAYS) + 1
    for _ in range(steps):
        jd_hi = jd_lo + _COARSE_STEP_DAYS
        e_hi = _signed_elongation_deg(backend, jd_hi)
        if _is_upward_conjunction_bracket(e_lo, e_hi):
            return jd_ut_to_datetime_utc(_bisect_conjunction(backend, jd_lo, jd_hi))
        jd_lo, e_lo = jd_hi, e_hi
    raise CalculationError(
        "Failed to bracket next new moon within one synodic month",
        detail={"seed_utc": dt_utc.isoformat(), "max_scan_days": _MAX_SCAN_DAYS},
    )


def previous_new_moon(dt_utc: datetime) -> datetime:
    """Return the most recent true new moon at/before ``dt_utc`` as tz-aware UTC.

    Scans backward in coarse steps to bracket the nearest preceding upward
    elongation zero-crossing, then bisects to ~1 s. A tiny forward margin lets a
    conjunction sitting essentially at ``dt_utc`` resolve to itself.
    """
    backend = SwissEphBackend()
    jd_hi = _to_jd_ut(dt_utc) + _BACK_SCAN_MARGIN_DAYS
    e_hi = _signed_elongation_deg(backend, jd_hi)
    steps = int((_MAX_SCAN_DAYS + _BACK_SCAN_MARGIN_DAYS) / _COARSE_STEP_DAYS) + 1
    for _ in range(steps):
        jd_lo = jd_hi - _COARSE_STEP_DAYS
        e_lo = _signed_elongation_deg(backend, jd_lo)
        if _is_upward_conjunction_bracket(e_lo, e_hi):
            return jd_ut_to_datetime_utc(_bisect_conjunction(backend, jd_lo, jd_hi))
        jd_hi, e_hi = jd_lo, e_lo
    raise CalculationError(
        "Failed to bracket previous new moon within one synodic month",
        detail={"seed_utc": dt_utc.isoformat(), "max_scan_days": _MAX_SCAN_DAYS},
    )
