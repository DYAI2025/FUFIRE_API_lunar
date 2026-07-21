from __future__ import annotations

from math import floor
from typing import List, Optional


def wrap360(x: float) -> float:
    """Wrap to [0, 360)."""
    y = x % 360.0
    if y < 0:
        y += 360.0
    # Guard against 360 due to float quirks
    if y >= 360.0:
        y -= 360.0
    return y

def wrap180(x: float) -> float:
    """Wrap to (-180, 180]."""
    y = wrap360(x + 180.0) - 180.0
    # Map -180 to +180? Spec allows (-180,180]; keep -180 exclusive by mapping -180 -> 180
    if y <= -180.0:
        return 180.0
    return y

def delta_deg(a: float, b: float) -> float:
    """Absolute angular difference in degrees in [0,180]."""
    return abs(wrap180(a - b))

def branch_origin_deg(zi_apex_deg: float, branch_width_deg: float) -> float:
    half = branch_width_deg / 2.0
    return wrap360(zi_apex_deg - half)

def branch_index_shift_boundaries(lambda_deg: float, *, zi_apex_deg: float, branch_width_deg: float) -> int:
    """K1: SHIFT_BOUNDARIES (recommended)."""
    b0 = branch_origin_deg(zi_apex_deg, branch_width_deg)
    x = wrap360(lambda_deg - b0) / branch_width_deg
    return int(floor(x)) % 12

def branch_index_shift_longitudes(
    lambda_deg: float,
    *,
    zi_apex_deg: float,
    branch_width_deg: float,
    phi_apex_offset_deg: float,
) -> int:
    """K2: SHIFT_LONGITUDES (spec-equivalent to K1 if implemented correctly)."""
    b0 = branch_origin_deg(zi_apex_deg, branch_width_deg)
    lambda_apex = wrap360(lambda_deg - phi_apex_offset_deg)
    b0_apex = wrap360(b0 - phi_apex_offset_deg)
    x = wrap360(lambda_apex - b0_apex) / branch_width_deg
    return int(floor(x)) % 12

def branch_index_shift_longitudes_misused(
    lambda_deg: float,
    *,
    zi_apex_deg: float,
    branch_width_deg: float,
    phi_apex_offset_deg: float,
) -> int:
    """
    Intentionally incorrect implementation used ONLY for tests:
    shifts lambda but forgets to shift the branch origin (mixing conventions).
    """
    b0 = branch_origin_deg(zi_apex_deg, branch_width_deg)
    lambda_apex = wrap360(lambda_deg - phi_apex_offset_deg)
    x = wrap360(lambda_apex - b0) / branch_width_deg
    return int(floor(x)) % 12

def nearest_boundary_distance_deg(lambda_deg: float, *, zi_apex_deg: float, branch_width_deg: float) -> float:
    """
    Distance to nearest branch boundary in degrees for HALF_OPEN segmentation.
    Boundaries at b0 + k*width.
    """
    b0 = branch_origin_deg(zi_apex_deg, branch_width_deg)
    pos = wrap360(lambda_deg - b0) / branch_width_deg  # in [0,12)
    frac = pos - floor(pos)  # in [0,1)
    dist = min(frac, 1.0 - frac) * branch_width_deg
    return float(dist)

def hour_branch_index_from_tlst(tlst_hours: float) -> int:
    """
    Spec rule: hour branch = floor(((TLST + 1) mod 24) / 2) with HALF_OPEN intervals.
    Zi: [23, 1), Chou: [1,3), ..., Hai: [21,23)
    """
    x = (tlst_hours + 1.0) % 24.0
    return int(floor(x / 2.0)) % 12

def nearest_hour_boundary_distance_minutes(tlst_hours: float) -> float:
    """
    Distance to nearest hour-branch boundary in minutes.
    Boundaries at odd hours: 1,3,5,...,23 (mod 24).
    """
    # Reduce to [0,24)
    t = tlst_hours % 24.0
    # Find nearest odd hour boundary by checking floor/ceil to odd grid
    # Represent odd boundaries as 2k+1
    lower = (int(floor((t - 1.0) / 2.0)) * 2) + 1
    upper = lower + 2
    # Normalize into [0,24)
    lower = lower % 24
    upper = upper % 24
    # Circular distance
    def circ_dist(a: float, b: float) -> float:
        d = abs(a - b) % 24.0
        return min(d, 24.0 - d)
    dist_h = min(circ_dist(t, float(lower)), circ_dist(t, float(upper)))
    return dist_h * 60.0


def shift_longitudes_equivalence_ok(
    impl_fn,
    *,
    zi_apex_deg: float,
    branch_width_deg: float,
    phi_apex_offset_deg: float,
    sample_lambdas: Optional[List[float]] = None,
) -> bool:
    """
    Mixing detector helper:
    For SHIFT_LONGITUDES, the implementation must be equivalent to the canonical K1 mapping.
    Returns True if equivalent on a deterministic sample set.
    """
    if sample_lambdas is None:
        sample_lambdas = [0.0, 14.999, 15.0, 123.456, 179.999, 180.0, 284.999, 285.0, 359.999]
    for lam in sample_lambdas:
        k1 = branch_index_shift_boundaries(lam, zi_apex_deg=zi_apex_deg, branch_width_deg=branch_width_deg)
        k2 = impl_fn(lam, zi_apex_deg=zi_apex_deg, branch_width_deg=branch_width_deg, phi_apex_offset_deg=phi_apex_offset_deg)
        if k1 != k2:
            return False
    return True
