from __future__ import annotations

from typing import List, Tuple

from .ephemeris import EphemerisBackend, norm360, wrap180
from .exc import CalculationError

SOLAR_TERM_TARGETS_DEG: List[float] = [15.0 * k for k in range(24)]

def _bisection_crossing(
    backend: EphemerisBackend,
    target_lon_deg: float,
    jd_lo: float,
    jd_hi: float,
    accuracy_seconds: float,
    max_iter: int = 80,
) -> float:
    def f(jd_ut: float) -> float:
        return wrap180(backend.sun_lon_deg_ut(jd_ut) - target_lon_deg)

    flo = f(jd_lo)
    fhi = f(jd_hi)
    if flo == 0.0:
        return jd_lo
    if fhi == 0.0:
        return jd_hi
    if flo * fhi > 0.0:
        raise ValueError("Interval does not bracket root")

    tol_days = accuracy_seconds / 86400.0
    lo, hi = jd_lo, jd_hi
    for _ in range(max_iter):
        mid = 0.5 * (lo + hi)
        fmid = f(mid)
        if abs(hi - lo) <= tol_days:
            return mid
        if flo * fmid <= 0.0:
            hi, fhi = mid, fmid
        else:
            lo, flo = mid, fmid
    return 0.5 * (lo + hi)

def find_crossing(
    backend: EphemerisBackend,
    target_lon_deg: float,
    jd_start_ut: float,
    *,
    accuracy_seconds: float,
    max_span_days: float = 40.0,
) -> float:
    direct = backend.solcross_ut(target_lon_deg, jd_start_ut)
    if direct is not None:
        return float(direct)

    step = 1.0
    jd_lo = jd_start_ut
    f_lo = wrap180(backend.sun_lon_deg_ut(jd_lo) - target_lon_deg)

    jd = jd_lo
    for _ in range(int(max_span_days / step) + 1):
        jd_hi = jd + step
        f_hi = wrap180(backend.sun_lon_deg_ut(jd_hi) - target_lon_deg)
        if f_lo == 0.0:
            return jd_lo
        if f_lo * f_hi <= 0.0:
            return _bisection_crossing(backend, target_lon_deg, jd_lo, jd_hi, accuracy_seconds)
        jd_lo, f_lo = jd_hi, f_hi
        jd = jd_hi
    raise CalculationError(
        "Failed to bracket solar longitude crossing",
        detail={"target_lon_deg": target_lon_deg, "jd_start_ut": jd_start_ut},
    )

def compute_month_boundaries_from_lichun(
    backend: EphemerisBackend,
    jd_lichun_ut: float,
    *,
    accuracy_seconds: float,
) -> List[float]:
    bounds: List[float] = [jd_lichun_ut]
    jd_cursor = jd_lichun_ut + 1e-6
    for k in range(1, 13):
        target = norm360(315.0 + 30.0 * k)
        jd_next = find_crossing(backend, target, jd_cursor, accuracy_seconds=accuracy_seconds)
        bounds.append(jd_next)
        jd_cursor = jd_next + 1e-6
    return bounds

def compute_24_solar_terms_for_window(
    backend: EphemerisBackend,
    jd_start_ut: float,
    jd_end_ut: float,
    *,
    accuracy_seconds: float,
) -> List[Tuple[int, float]]:
    out: List[Tuple[int, float]] = []
    for idx, target in enumerate(SOLAR_TERM_TARGETS_DEG):
        jd = find_crossing(backend, target, jd_start_ut, accuracy_seconds=accuracy_seconds, max_span_days=30.0)
        if jd_start_ut <= jd <= jd_end_ut:
            out.append((idx, jd))
    out.sort(key=lambda x: x[1])
    return out
