"""Tests for transit cache behavior: TTL, eviction, isolation, and key generation."""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from bazi_engine.transit import (
    _cache_key,
    _timeline_cache,
    _transit_cache,
    compute_transit_now,
    compute_transit_timeline,
)

# Deterministic mock for swe.calc_ut
MOCK_PLANET_DATA = {
    0: (100.0, 0.0, 1.0, 1.01, 0.0, 0.0),   # Sun
    1: (200.0, 0.0, 0.003, 13.2, 0.0, 0.0),  # Moon
    2: (300.0, 0.0, 0.8, 1.8, 0.0, 0.0),     # Mercury
    3: (50.0, 0.0, 0.7, 1.2, 0.0, 0.0),       # Venus
    4: (150.0, 0.0, 1.5, 0.7, 0.0, 0.0),      # Mars
    5: (250.0, 0.0, 5.0, 0.08, 0.0, 0.0),     # Jupiter
    6: (350.0, 0.0, 9.5, 0.03, 0.0, 0.0),     # Saturn
    7: (40.0, 0.0, 19.2, 0.01, 0.0, 0.0),     # Uranus
    8: (355.0, 0.0, 30.1, 0.005, 0.0, 0.0),   # Neptune
    9: (300.0, 0.0, 33.7, 0.003, 0.0, 0.0),   # Pluto
}

# Different data to detect stale cache (keep longitudes in 0-359 range)
MOCK_PLANET_DATA_ALT = {
    k: ((v[0] + 10) % 360, *v[1:]) for k, v in MOCK_PLANET_DATA.items()
}


def mock_calc_ut(jd_ut, planet_id, flags):
    if planet_id in MOCK_PLANET_DATA:
        return MOCK_PLANET_DATA[planet_id], 0
    raise Exception(f"Unknown planet {planet_id}")


def mock_calc_ut_alt(jd_ut, planet_id, flags):
    if planet_id in MOCK_PLANET_DATA_ALT:
        return MOCK_PLANET_DATA_ALT[planet_id], 0
    raise Exception(f"Unknown planet {planet_id}")


class TestCacheKey:
    """_cache_key truncates to hourly granularity."""

    def test_same_hour_same_key(self):
        dt1 = datetime(2026, 3, 10, 14, 0, 0, tzinfo=timezone.utc)
        dt2 = datetime(2026, 3, 10, 14, 59, 59, tzinfo=timezone.utc)
        assert _cache_key(dt1) == _cache_key(dt2)

    def test_different_hours_different_keys(self):
        dt1 = datetime(2026, 3, 10, 14, 0, 0, tzinfo=timezone.utc)
        dt2 = datetime(2026, 3, 10, 15, 0, 0, tzinfo=timezone.utc)
        assert _cache_key(dt1) != _cache_key(dt2)

    def test_different_days_different_keys(self):
        dt1 = datetime(2026, 3, 10, 14, 0, 0, tzinfo=timezone.utc)
        dt2 = datetime(2026, 3, 11, 14, 0, 0, tzinfo=timezone.utc)
        assert _cache_key(dt1) != _cache_key(dt2)

    def test_different_ephe_path_different_keys(self):
        dt = datetime(2026, 3, 10, 14, 0, 0, tzinfo=timezone.utc)
        assert _cache_key(dt, ephe_path="/path/A") != _cache_key(dt, ephe_path="/path/B")

    def test_different_ephemeris_mode_different_keys(self):
        dt = datetime(2026, 3, 10, 14, 0, 0, tzinfo=timezone.utc)
        assert _cache_key(dt, ephemeris_mode="SWIEPH") != _cache_key(dt, ephemeris_mode="MOSEPH")


class TestTransitCacheHit:
    """Cache should return identical results for same hour."""

    def test_second_call_returns_cached_result(self):
        dt = datetime(2026, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        with patch("bazi_engine.transit.swe.calc_ut", side_effect=mock_calc_ut):
            result1 = compute_transit_now(dt_utc=dt)
            # Replace mock with different data — if cache works, result stays same
        with patch("bazi_engine.transit.swe.calc_ut", side_effect=mock_calc_ut_alt):
            result2 = compute_transit_now(dt_utc=dt)

        assert result1 == result2, "Second call should return cached result"

    def test_different_hour_computes_fresh(self):
        dt1 = datetime(2026, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        dt2 = datetime(2026, 6, 15, 13, 0, 0, tzinfo=timezone.utc)
        with patch("bazi_engine.transit.swe.calc_ut", side_effect=mock_calc_ut):
            result1 = compute_transit_now(dt_utc=dt1)
        with patch("bazi_engine.transit.swe.calc_ut", side_effect=mock_calc_ut_alt):
            result2 = compute_transit_now(dt_utc=dt2)

        # Different hour → different computation → different longitude
        assert result1["planets"]["sun"]["longitude"] != result2["planets"]["sun"]["longitude"]

    def test_same_hour_different_ephe_path_computes_fresh(self):
        dt = datetime(2026, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        with patch.dict(os.environ, {"EPHEMERIS_MODE": "MOSEPH"}):
            with patch("bazi_engine.transit.swe.calc_ut", side_effect=mock_calc_ut):
                result1 = compute_transit_now(dt_utc=dt, ephe_path="/path/A")
            with patch("bazi_engine.transit.swe.calc_ut", side_effect=mock_calc_ut_alt):
                result2 = compute_transit_now(dt_utc=dt, ephe_path="/path/B")

        assert result1["planets"]["sun"]["longitude"] != result2["planets"]["sun"]["longitude"]


class TestTransitCacheClear:
    """conftest.py clear_transit_caches fixture should isolate tests."""

    def test_cache_is_empty_at_start(self):
        """autouse fixture in conftest should clear cache before each test."""
        assert len(_transit_cache) == 0
        assert len(_timeline_cache) == 0

    def test_cache_populated_after_call(self):
        dt = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        with patch("bazi_engine.transit.swe.calc_ut", side_effect=mock_calc_ut):
            compute_transit_now(dt_utc=dt)
        assert len(_transit_cache) == 1


class TestTimelineCache:
    """Timeline cache behavior."""

    def test_timeline_cached_by_start_and_days(self):
        dt = datetime(2026, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        with patch("bazi_engine.transit.swe.calc_ut", side_effect=mock_calc_ut):
            r1 = compute_transit_timeline(days=3, start_utc=dt)
        with patch("bazi_engine.transit.swe.calc_ut", side_effect=mock_calc_ut_alt):
            r2 = compute_transit_timeline(days=3, start_utc=dt)

        assert r1 == r2, "Same start+days should return cached result"

    def test_different_days_count_not_cached(self):
        dt = datetime(2026, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        with patch("bazi_engine.transit.swe.calc_ut", side_effect=mock_calc_ut):
            r1 = compute_transit_timeline(days=3, start_utc=dt)
            r2 = compute_transit_timeline(days=5, start_utc=dt)

        assert len(r1["days"]) == 3
        assert len(r2["days"]) == 5

    def test_same_day_different_start_time_not_cached(self):
        dt1 = datetime(2026, 6, 15, 0, 0, 0, tzinfo=timezone.utc)
        dt2 = datetime(2026, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        with patch("bazi_engine.transit.swe.calc_ut", side_effect=mock_calc_ut):
            r1 = compute_transit_timeline(days=1, start_utc=dt1)
        with patch("bazi_engine.transit.swe.calc_ut", side_effect=mock_calc_ut_alt):
            r2 = compute_transit_timeline(days=1, start_utc=dt2)

        assert r1["days"][0]["planets"]["sun"]["longitude"] != r2["days"][0]["planets"]["sun"]["longitude"]

    def test_same_start_different_ephe_path_not_cached(self):
        dt = datetime(2026, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        with patch.dict(os.environ, {"EPHEMERIS_MODE": "MOSEPH"}):
            with patch("bazi_engine.transit.swe.calc_ut", side_effect=mock_calc_ut):
                r1 = compute_transit_timeline(days=1, start_utc=dt, ephe_path="/path/A")
            with patch("bazi_engine.transit.swe.calc_ut", side_effect=mock_calc_ut_alt):
                r2 = compute_transit_timeline(days=1, start_utc=dt, ephe_path="/path/B")

        assert r1["days"][0]["planets"]["sun"]["longitude"] != r2["days"][0]["planets"]["sun"]["longitude"]


class TestCacheMaxSize:
    """Cache should evict entries when maxsize is reached."""

    def test_transit_cache_maxsize_64(self):
        assert _transit_cache.maxsize == 64

    def test_timeline_cache_maxsize_16(self):
        assert _timeline_cache.maxsize == 16

    def test_eviction_on_overflow(self):
        """Fill beyond maxsize — oldest entries should be evicted."""
        base = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        with patch("bazi_engine.transit.swe.calc_ut", side_effect=mock_calc_ut):
            for i in range(70):  # > maxsize of 64
                dt = base + timedelta(hours=i)
                compute_transit_now(dt_utc=dt)

        # Cache should not exceed maxsize
        assert len(_transit_cache) <= 64


class TestSectorBounds:
    """Verify sector index stays within 0-11."""

    def test_longitude_360_does_not_overflow(self):
        """lon_deg=360.0 should map to sector 0, not sector 12."""
        mock_data = {
            0: (360.0, 0.0, 1.0, 1.0, 0.0, 0.0),
            1: (359.9, 0.0, 0.003, 13.2, 0.0, 0.0),
            2: (0.0, 0.0, 0.8, 1.8, 0.0, 0.0),
            3: (90.0, 0.0, 0.7, 1.2, 0.0, 0.0),
            4: (180.0, 0.0, 1.5, 0.7, 0.0, 0.0),
            5: (270.0, 0.0, 5.0, 0.08, 0.0, 0.0),
            6: (330.0, 0.0, 9.5, 0.03, 0.0, 0.0),
            7: (45.0, 0.0, 19.2, 0.01, 0.0, 0.0),
            8: (350.0, 0.0, 30.1, 0.005, 0.0, 0.0),
            9: (295.0, 0.0, 33.7, 0.003, 0.0, 0.0),
        }
        def mock_calc(jd, pid, flags):
            return mock_data[pid], 0

        dt = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        with patch("bazi_engine.transit.swe.calc_ut", side_effect=mock_calc):
            result = compute_transit_now(dt_utc=dt)
        assert result["planets"]["sun"]["sector"] == 0
        assert result["planets"]["sun"]["sign"] == "aries"
