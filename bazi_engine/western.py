from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Any, Dict, Optional

import swisseph as swe

from .aspects import compute_aspects
from .constants import AYANAMSHA_MODES
from .ephemeris import SwissEphBackend, datetime_utc_to_jd_ut

_SWE_LOCK = threading.Lock()

PLANETS = {
    "Sun": swe.SUN,
    "Moon": swe.MOON,
    "Mercury": swe.MERCURY,
    "Venus": swe.VENUS,
    "Mars": swe.MARS,
    "Jupiter": swe.JUPITER,
    "Saturn": swe.SATURN,
    "Uranus": swe.URANUS,
    "Neptune": swe.NEPTUNE,
    "Pluto": swe.PLUTO,
    "Chiron": swe.CHIRON,
    "Lilith": swe.MEAN_APOG,
    "NorthNode": swe.MEAN_NODE,
    "TrueNorthNode": swe.TRUE_NODE
}

@dataclass(frozen=True)
class WesternBody:
    name: str
    longitude: float
    latitude: float
    distance: float
    speed_long: float
    is_retrograde: bool
    zodiac_sign: int
    degree_in_sign: float

def compute_western_chart(
    birth_utc_dt: Any,
    lat: float,
    lon: float,
    alt: float = 0.0,
    ephe_path: Optional[str] = None,
    zodiac_mode: str = "tropical",
) -> Dict[str, Any]:
    """
    Compute basic western chart: Planets + Houses.
    Includes True Node, Retrograde status, and High-Latitude fallback.
    """
    backend = SwissEphBackend(ephe_path=ephe_path)
    
    # JD (UT)
    jd_ut = datetime_utc_to_jd_ut(birth_utc_dt)
    
    bodies: Dict[str, Any] = {}

    for name, pid in PLANETS.items():
        try:
            (lon_deg, lat_deg, dist, speed_lon, _, _), _ret = backend.calc_ut(
                jd_ut, pid, extra_flags=swe.FLG_SPEED,
            )
            bodies[name] = {
                "longitude": lon_deg,
                "latitude": lat_deg,
                "distance": dist,
                "speed": speed_lon,
                "is_retrograde": speed_lon < 0,
                "zodiac_sign": int(lon_deg // 30),
                "degree_in_sign": lon_deg % 30
            }
        except swe.Error as e:
            bodies[name] = {"error": str(e)}

    # Houses with Fallback
    # Default: Placidus ('P')
    # Fallback 1: Porphyry ('O') - Good fallback for high latitudes
    # Fallback 2: Whole Sign ('W') - Always works
    
    house_systems = [b'P', b'O', b'W']
    house_system_labels = {b'P': 'placidus', b'O': 'porphyry', b'W': 'whole_sign'}
    requested_sys = house_systems[0]
    cusps = None
    ascmc = None
    used_sys = None
    fallback_reason: Optional[str] = None

    for sys_char in house_systems:
        try:
            c, a = backend.houses(jd_ut, lat, lon, sys_char)
            # Check for validity (sometimes it returns 0s without error if it fails silently)
            if c[1] == 0.0 and c[2] == 0.0:
                 continue
            cusps = c
            ascmc = a
            used_sys = sys_char
            break
        except swe.Error:
            continue
            
    if cusps is None or ascmc is None:
        # Should never happen with Whole Sign, but just in case
        raise RuntimeError("Failed to calculate houses with all attempted systems.")

    # Build house quality metadata
    used_label = house_system_labels.get(used_sys, "unknown") if used_sys is not None else "unknown"
    requested_label = house_system_labels.get(requested_sys, "unknown")
    if used_sys == requested_sys:
        house_quality = {
            "flag": "exact",
            "system": used_label,
            "requested": requested_label,
        }
    else:
        fallback_reason = (
            f"Placidus undefined at latitude {abs(lat):.1f}°"
        )
        house_quality = {
            "flag": "fallback",
            "system": used_label,
            "requested": requested_label,
            "reason": fallback_reason,
        }

    houses = {}
    # Handle different pyswisseph versions/behaviors
    # If len is 12, we assume 0-index. If 13, likely 1-index with 0=0.
    if len(cusps) == 12:
        for i in range(12):
            houses[str(i+1)] = cusps[i]
    else:
        for i in range(1, 13):
            houses[str(i)] = cusps[i]

    angles = {
        "Ascendant": ascmc[0],
        "MC": ascmc[1],
        "Vertex": ascmc[3] if len(ascmc) > 3 else 0.0
    }

    # Apply ayanamsha correction for sidereal modes
    if zodiac_mode in AYANAMSHA_MODES:
        ayanamsha_id = AYANAMSHA_MODES[zodiac_mode]
        with _SWE_LOCK:
            swe.set_sid_mode(ayanamsha_id)
            ayanamsha = swe.get_ayanamsa_ut(jd_ut)
            swe.set_sid_mode(0)  # Reset — prevent global state leakage

        # Adjust body longitudes
        for body_data in bodies.values():
            if "longitude" in body_data:
                adj_lon = (body_data["longitude"] - ayanamsha) % 360
                body_data["longitude"] = adj_lon
                body_data["zodiac_sign"] = int(adj_lon // 30)
                body_data["degree_in_sign"] = adj_lon % 30

        # Adjust house cusps
        for key in houses:
            houses[key] = (houses[key] - ayanamsha) % 360

        # Adjust angles
        for key in angles:
            angles[key] = (angles[key] - ayanamsha) % 360

    # Compute planetary aspects (after any sidereal adjustment)
    aspects = compute_aspects(bodies)

    quality_flags = {
        "house_system_fallback": used_sys != requested_sys,
        "house_system_requested": requested_label,
        "house_system_used": used_label,
        "ephemeris_mode": backend.mode,
    }

    return {
        "jd_ut": jd_ut,
        "house_system": used_sys.decode('utf-8') if used_sys is not None else "unknown",
        "bodies": bodies,
        "houses": houses,
        "angles": angles,
        "house_quality": house_quality,
        "quality_flags": quality_flags,
        "aspects": aspects,
    }
