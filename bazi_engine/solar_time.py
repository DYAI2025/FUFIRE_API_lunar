"""
solar_time.py — Level 2: Pure solar time mathematics.

No internal imports. Provides:
  - equation_of_time()    Equation of Time in minutes (astronomical approximation)
  - true_solar_time()     Civil time → True Solar Time conversion

Extracted from fusion.py so that bafe/time_model.py (Level 5) can import
this without depending on the full fusion module (Level 4).
"""
from __future__ import annotations

from math import cos, pi, radians, sin
from typing import Optional


def equation_of_time(day_of_year: int, use_precise: bool = True) -> float:
    """
    Calculate Equation of Time (E_t) in minutes.

    The Equation of Time quantifies the discrepancy between
    apparent solar time and mean solar time due to:
    1. Earth's elliptical orbit (eccentricity effect)
    2. Earth's axial tilt (obliquity effect)

    Args:
        day_of_year: Day number (1-366)
        use_precise: If True, use more accurate formula with both effects

    Returns:
        Equation of Time in minutes (can be positive or negative)
        Range: approximately -14.2 to +16.4 minutes

    Formula (standard approximation):
        E_t = 9.87*sin(2B) - 7.53*cos(B) - 1.5*sin(B)
        where B = 360*(N-81)/365 degrees

    More precise formula separates eccentricity and obliquity effects.
    """
    if use_precise:
        # More accurate formula using both eccentricity and obliquity
        # Reference: NOAA Solar Calculator / Astronomical Algorithms
        gamma = 2 * pi * (day_of_year - 1) / 365.0
        E = 229.18 * (
            0.000075
            + 0.001868 * cos(gamma)
            - 0.032077 * sin(gamma)
            - 0.014615 * cos(2 * gamma)
            - 0.040849 * sin(2 * gamma)
        )
        return round(E, 3)
    else:
        B = 360 * (day_of_year - 81) / 365
        B_rad = radians(B)
        E = (
            9.87 * sin(2 * B_rad)
            - 7.53 * cos(B_rad)
            - 1.5 * sin(B_rad)
        )
        return round(E, 2)


def true_solar_time(
    civil_time_hours: float,
    longitude_deg: float,
    day_of_year: int,
    timezone_offset_hours: Optional[float] = None,
) -> float:
    """
    Calculate True Solar Time (TST) from civil time.

    TST = Local Mean Time + Equation of Time
    LMT = UTC + (longitude / 15) hours

    For civil time with a timezone:
    TST = civil_time - tz_offset + (longitude/15) + E_t

    Args:
        civil_time_hours: Local civil time in hours (e.g., 14.5 = 14:30)
        longitude_deg: Longitude (positive = east, negative = west)
        day_of_year: Day of year (1-366)
        timezone_offset_hours: Timezone offset from UTC in hours (e.g., +1 for CET).
                              If None, treats input as LMT.

    Returns:
        True Solar Time in hours (0-24)
    """
    if timezone_offset_hours is not None:
        utc_hours = civil_time_hours - timezone_offset_hours
        lmt_hours = utc_hours + (longitude_deg / 15.0)
    else:
        lmt_hours = civil_time_hours

    E_t = equation_of_time(day_of_year) / 60.0
    TST = lmt_hours + E_t

    while TST < 0:
        TST += 24
    while TST >= 24:
        TST -= 24

    return round(TST, 4)
