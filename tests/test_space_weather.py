"""Tests for services/space_weather.py — NOAA space weather fetching."""
from __future__ import annotations

import asyncio

import httpx
import pytest
import respx

from bazi_engine.services.space_weather import (
    _DEFAULT_KP,
    _DEFAULT_PRESSURE,
    _KP_URL,
    _SOLAR_WIND_URL,
    _cache,
    _default_space_weather,
    compute_space_weather_score,
    fetch_space_weather,
)


@pytest.fixture(autouse=True)
def clear_cache():
    """Clear the TTL cache before each test."""
    _cache.clear()
    yield
    _cache.clear()


# ── Mock data ───────────────────────────────────────────────────────────────

_MOCK_KP_DATA = [
    ["time_tag", "Kp", "observed"],
    ["2026-04-13 00:00:00", "3.33", "observed"],
    ["2026-04-13 03:00:00", "4.00", "estimated"],
]

_MOCK_SOLAR_WIND_DATA = [
    ["time_tag", "density", "speed", "temperature"],
    ["2026-04-13 00:00:00", "5.0", "400.0", "100000"],
    ["2026-04-13 00:05:00", "6.0", "450.0", "120000"],
]


# ── _default_space_weather ──────────────────────────────────────────────────

class TestDefaultSpaceWeather:
    def test_returns_safe_defaults(self):
        sw = _default_space_weather()
        assert sw.kp_index == _DEFAULT_KP
        assert sw.solar_pressure == _DEFAULT_PRESSURE
        assert sw.storm_active is False
        assert sw.source == "default"
        assert sw.fetched_at is None


# ── compute_space_weather_score ─────────────────────────────────────────────

class TestComputeSpaceWeatherScore:
    def test_calm_weather_low_score(self):
        from bazi_engine.impact_types import SpaceWeather
        sw = SpaceWeather(kp_index=1.0, solar_pressure=1.0)
        score = compute_space_weather_score(sw)
        assert 0.0 <= score <= 0.3

    def test_storm_weather_high_score(self):
        from bazi_engine.impact_types import SpaceWeather
        sw = SpaceWeather(kp_index=8.0, solar_pressure=8.0)
        score = compute_space_weather_score(sw)
        assert score >= 0.7

    def test_max_values_give_one(self):
        from bazi_engine.impact_types import SpaceWeather
        sw = SpaceWeather(kp_index=9.0, solar_pressure=10.0)
        score = compute_space_weather_score(sw)
        assert score == pytest.approx(1.0)

    def test_zero_values_give_zero(self):
        from bazi_engine.impact_types import SpaceWeather
        sw = SpaceWeather(kp_index=0.0, solar_pressure=0.0)
        score = compute_space_weather_score(sw)
        assert score == pytest.approx(0.0)

    def test_score_bounded_zero_one(self):
        from bazi_engine.impact_types import SpaceWeather
        sw = SpaceWeather(kp_index=5.0, solar_pressure=20.0)
        score = compute_space_weather_score(sw)
        assert 0.0 <= score <= 1.0


# ── fetch_space_weather ─────────────────────────────────────────────────────

class TestFetchSpaceWeather:
    @respx.mock
    def test_successful_fetch(self):
        respx.get(_KP_URL).mock(return_value=httpx.Response(200, json=_MOCK_KP_DATA))
        respx.get(_SOLAR_WIND_URL).mock(return_value=httpx.Response(200, json=_MOCK_SOLAR_WIND_DATA))

        sw, partial = asyncio.run(fetch_space_weather())

        assert partial is False
        assert sw.source == "noaa"
        assert sw.kp_index == 4.0
        assert sw.solar_pressure > 0
        assert sw.fetched_at is not None
        assert sw.storm_active is False

    @respx.mock
    def test_kp_above_5_triggers_storm(self):
        storm_kp = [
            ["time_tag", "Kp", "observed"],
            ["2026-04-13 00:00:00", "6.5", "observed"],
        ]
        respx.get(_KP_URL).mock(return_value=httpx.Response(200, json=storm_kp))
        respx.get(_SOLAR_WIND_URL).mock(return_value=httpx.Response(200, json=_MOCK_SOLAR_WIND_DATA))

        sw, partial = asyncio.run(fetch_space_weather())

        assert sw.storm_active is True
        assert sw.kp_index == 6.5

    @respx.mock
    def test_kp_503_degrades_independently(self):
        """Kp fails but solar wind succeeds — partial=True, pressure is real."""
        respx.get(_KP_URL).mock(return_value=httpx.Response(503))
        respx.get(_SOLAR_WIND_URL).mock(return_value=httpx.Response(200, json=_MOCK_SOLAR_WIND_DATA))

        sw, partial = asyncio.run(fetch_space_weather())

        assert partial is True
        assert sw.kp_index == _DEFAULT_KP  # fell back
        assert sw.solar_pressure > 0  # real data

    @respx.mock
    def test_solar_wind_timeout_degrades_independently(self):
        """Solar wind times out but Kp succeeds — partial=True, kp is real."""
        respx.get(_KP_URL).mock(return_value=httpx.Response(200, json=_MOCK_KP_DATA))
        respx.get(_SOLAR_WIND_URL).mock(side_effect=httpx.TimeoutException("timeout"))

        sw, partial = asyncio.run(fetch_space_weather())

        assert partial is True
        assert sw.kp_index == 4.0  # real data
        assert sw.solar_pressure == _DEFAULT_PRESSURE  # fell back

    @respx.mock
    def test_both_fail_returns_full_default(self):
        respx.get(_KP_URL).mock(side_effect=httpx.ConnectError("no route"))
        respx.get(_SOLAR_WIND_URL).mock(side_effect=httpx.ConnectError("no route"))

        sw, partial = asyncio.run(fetch_space_weather())

        assert partial is True
        assert sw.kp_index == _DEFAULT_KP
        assert sw.solar_pressure == _DEFAULT_PRESSURE

    @respx.mock
    def test_result_is_cached(self):
        route = respx.get(_KP_URL).mock(return_value=httpx.Response(200, json=_MOCK_KP_DATA))
        respx.get(_SOLAR_WIND_URL).mock(return_value=httpx.Response(200, json=_MOCK_SOLAR_WIND_DATA))

        sw1, _ = asyncio.run(fetch_space_weather())
        sw2, _ = asyncio.run(fetch_space_weather())

        assert sw1.kp_index == sw2.kp_index
        assert route.call_count == 1

    @respx.mock
    def test_malformed_kp_data_falls_back(self):
        bad_kp = [
            ["time_tag", "Kp", "observed"],
            ["2026-04-13 00:00:00", "not_a_number", "observed"],
        ]
        respx.get(_KP_URL).mock(return_value=httpx.Response(200, json=bad_kp))
        respx.get(_SOLAR_WIND_URL).mock(return_value=httpx.Response(200, json=_MOCK_SOLAR_WIND_DATA))

        sw, partial = asyncio.run(fetch_space_weather())

        assert sw.kp_index == _DEFAULT_KP

    @respx.mock
    def test_empty_data_rows_falls_back(self):
        """NOAA returns only header row — no data."""
        empty_kp = [["time_tag", "Kp", "observed"]]
        empty_wind = [["time_tag", "density", "speed", "temperature"]]
        respx.get(_KP_URL).mock(return_value=httpx.Response(200, json=empty_kp))
        respx.get(_SOLAR_WIND_URL).mock(return_value=httpx.Response(200, json=empty_wind))

        sw, partial = asyncio.run(fetch_space_weather())

        assert sw.kp_index == _DEFAULT_KP
        assert sw.solar_pressure == _DEFAULT_PRESSURE

    @respx.mock
    def test_frozen_result(self):
        respx.get(_KP_URL).mock(return_value=httpx.Response(200, json=_MOCK_KP_DATA))
        respx.get(_SOLAR_WIND_URL).mock(return_value=httpx.Response(200, json=_MOCK_SOLAR_WIND_DATA))

        sw, _ = asyncio.run(fetch_space_weather())
        with pytest.raises(Exception):
            sw.kp_index = 9.0
