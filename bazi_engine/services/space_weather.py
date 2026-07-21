"""
services/space_weather.py — NOAA space weather data fetching.

Fetches planetary Kp index and solar wind dynamic pressure from NOAA's
Space Weather Prediction Center (SWPC) JSON APIs. Results are cached
for 15 minutes.

On network failure or 503, returns a default SpaceWeather with
partial=True so the Impact endpoint can degrade gracefully.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

import httpx
from cachetools import TTLCache

from ..impact_types import SpaceWeather

logger = logging.getLogger(__name__)

# NOAA SWPC public JSON endpoints (no API key required)
_KP_URL = "https://services.swpc.noaa.gov/products/noaa-planetary-k-index-forecast.json"
_SOLAR_WIND_URL = "https://services.swpc.noaa.gov/products/solar-wind/plasma-5-minute.json"

# 15-minute TTL cache — stores (SpaceWeather, partial) tuple
_cache: TTLCache = TTLCache(maxsize=4, ttl=900)

_DEFAULT_TIMEOUT = 5.0  # seconds
_DEFAULT_KP = 2.0
_DEFAULT_PRESSURE = 1.5

# Proton mass factor for dynamic pressure: P_dyn = m_p * n * v^2
# Units: density in cm^-3, speed in km/s → result in nPa
_PROTON_MASS_NPA_FACTOR = 1.6726e-6

_USER_AGENT = "fufire-bazi-engine/1.0"


def _default_space_weather() -> SpaceWeather:
    """Return a safe default when NOAA data is unavailable."""
    return SpaceWeather(
        kp_index=_DEFAULT_KP,
        solar_pressure=_DEFAULT_PRESSURE,
        storm_active=False,
        source="default",
        fetched_at=None,
    )


async def _fetch_kp_index(client: httpx.AsyncClient) -> tuple[float, bool]:
    """Fetch the latest Kp index from NOAA forecast endpoint.

    Returns (kp_value, failed). failed=True means the value is a default.
    """
    try:
        resp = await client.get(_KP_URL, timeout=_DEFAULT_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        for row in reversed(data[1:]):
            try:
                kp = float(row[1])
                if 0 <= kp <= 9:
                    return kp, False
            except (ValueError, IndexError, TypeError):
                continue
    except (httpx.HTTPStatusError, httpx.TimeoutException, httpx.ConnectError) as exc:
        logger.warning("NOAA Kp fetch failed: %s — using default", exc)
    except Exception as exc:
        logger.error("Unexpected error fetching Kp index: %s", exc)
    return _DEFAULT_KP, True


async def _fetch_solar_wind_pressure(client: httpx.AsyncClient) -> tuple[float, bool]:
    """Fetch the latest solar wind dynamic pressure from NOAA.

    Returns (pressure_npa, failed). failed=True means the value is a default.
    NOAA plasma endpoint may use -99999 as sentinel for missing data;
    the density > 0 and speed > 0 checks reject these.
    """
    try:
        resp = await client.get(_SOLAR_WIND_URL, timeout=_DEFAULT_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        for row in reversed(data[1:]):
            try:
                density = float(row[1])
                speed = float(row[2])
                if density > 0 and speed > 0:
                    pressure = _PROTON_MASS_NPA_FACTOR * density * speed * speed
                    return round(pressure, 2), False
            except (ValueError, IndexError, TypeError):
                continue
    except (httpx.HTTPStatusError, httpx.TimeoutException, httpx.ConnectError) as exc:
        logger.warning("NOAA solar wind fetch failed: %s — using default", exc)
    except Exception as exc:
        logger.error("Unexpected error fetching solar wind: %s", exc)
    return _DEFAULT_PRESSURE, True


async def fetch_space_weather() -> tuple[SpaceWeather, bool]:
    """Fetch current space weather data from NOAA.

    Both NOAA endpoints are fetched concurrently. Each degrades
    independently — a Kp failure does not discard a successful
    solar wind result, and vice versa.

    Returns:
        Tuple of (SpaceWeather, partial). partial=True means at least
        one data source was unavailable and defaults were used.
    """
    cache_key = "space_weather"
    cached = _cache.get(cache_key)
    if cached is not None:
        sw, partial = cached
        return sw, partial

    try:
        async with httpx.AsyncClient(headers={"User-Agent": _USER_AGENT}) as client:
            (kp, kp_failed), (pressure, pressure_failed) = await asyncio.gather(
                _fetch_kp_index(client),
                _fetch_solar_wind_pressure(client),
            )

        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        partial = kp_failed or pressure_failed
        sw = SpaceWeather(
            kp_index=kp,
            solar_pressure=pressure,
            storm_active=kp >= 5.0,
            source="noaa" if not partial else "noaa_partial",
            fetched_at=now,
        )
        _cache[cache_key] = (sw, partial)
        return sw, partial

    except Exception as exc:
        logger.error("Unexpected error in space weather orchestration: %s", exc)
        return _default_space_weather(), True


def compute_space_weather_score(sw: SpaceWeather) -> float:
    """Normalize space weather into a 0-1 impact score.

    Kp contributes 60%, solar pressure 40%.
    Kp 0-9 maps linearly to 0-1.
    Pressure normalized with typical range 0-10 nPa.
    """
    kp_score = sw.kp_index / 9.0
    pressure_score = min(sw.solar_pressure / 10.0, 1.0)
    return round(kp_score * 0.6 + pressure_score * 0.4, 4)
