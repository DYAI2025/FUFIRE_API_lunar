"""
test_services_geocoding.py — Unit tests for bazi_engine/services/geocoding.py

HTTP calls are mocked — no network required. Tests the parsing logic,
country filtering, and error handling of geocode_place().
"""
from __future__ import annotations

import inspect
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from bazi_engine.services.geocoding import clear_geocode_cache, geocode_place

# ── Cache isolation ────────────────────────────────────────────────────────────
# geocode_place now memoizes candidate lists via geocode_candidates. These unit
# tests reuse the same ("Berlin", "de") key with DIFFERENT mocked payloads, so a
# cached result from one test would leak into the next. Reset before every test.

@pytest.fixture(autouse=True)
def _reset_geocode_cache():
    clear_geocode_cache()
    yield
    clear_geocode_cache()


# ── Mock helpers ──────────────────────────────────────────────────────────────

def _mock_httpx_client(results: list) -> MagicMock:
    """Build a mock httpx.AsyncClient context manager returning given results."""
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"results": results}
    mock_resp.raise_for_status = MagicMock()

    mock_client = MagicMock()
    mock_client.get = AsyncMock(return_value=mock_resp)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    return mock_client


BERLIN_RESULT = {
    "name": "Berlin",
    "latitude": 52.52,
    "longitude": 13.405,
    "timezone": "Europe/Berlin",
    "country_code": "DE",
}

TOKYO_RESULT = {
    "name": "Tokyo",
    "latitude": 35.6762,
    "longitude": 139.6503,
    "timezone": "Asia/Tokyo",
    "country_code": "JP",
}

BERLIN_US_RESULT = {
    "name": "Berlin",
    "latitude": 44.4686,
    "longitude": -71.185,
    "timezone": "America/New_York",
    "country_code": "US",
}


def test_geocode_place_is_async():
    """geocode_place must be a coroutine function to avoid blocking the event loop."""
    assert inspect.iscoroutinefunction(geocode_place), \
           "geocode_place must be async — use httpx.AsyncClient, not urllib"


class TestGeocodePlace:
    @pytest.mark.anyio
    async def test_returns_berlin_coordinates(self):
        with patch("bazi_engine.services.geocoding.httpx.AsyncClient",
                   return_value=_mock_httpx_client([BERLIN_RESULT])):
            result = await geocode_place("Berlin")
        assert result["lat"] == 52.52
        assert result["lon"] == 13.405

    @pytest.mark.anyio
    async def test_returns_timezone(self):
        with patch("bazi_engine.services.geocoding.httpx.AsyncClient",
                   return_value=_mock_httpx_client([BERLIN_RESULT])):
            result = await geocode_place("Berlin")
        assert result["timezone"] == "Europe/Berlin"

    @pytest.mark.anyio
    async def test_returns_name(self):
        with patch("bazi_engine.services.geocoding.httpx.AsyncClient",
                   return_value=_mock_httpx_client([BERLIN_RESULT])):
            result = await geocode_place("Berlin")
        assert result["name"] == "Berlin"

    @pytest.mark.anyio
    async def test_returns_country_code(self):
        with patch("bazi_engine.services.geocoding.httpx.AsyncClient",
                   return_value=_mock_httpx_client([BERLIN_RESULT])):
            result = await geocode_place("Berlin")
        assert result["country_code"] == "DE"

    @pytest.mark.anyio
    async def test_returns_dict_with_required_keys(self):
        with patch("bazi_engine.services.geocoding.httpx.AsyncClient",
                   return_value=_mock_httpx_client([BERLIN_RESULT])):
            result = await geocode_place("Berlin")
        assert {"lat", "lon", "timezone", "name", "country_code"} <= result.keys()

    @pytest.mark.anyio
    async def test_empty_results_raises_value_error(self):
        with patch("bazi_engine.services.geocoding.httpx.AsyncClient",
                   return_value=_mock_httpx_client([])):
            with pytest.raises(ValueError, match="Could not geocode"):
                await geocode_place("NoSuchPlace123")

    @pytest.mark.anyio
    async def test_country_filter_selects_correct_result(self):
        """'Berlin, DE' should return the German Berlin, not the US one."""
        with patch("bazi_engine.services.geocoding.httpx.AsyncClient",
                   return_value=_mock_httpx_client([BERLIN_US_RESULT, BERLIN_RESULT])):
            result = await geocode_place("Berlin, DE")
        assert result["country_code"] == "DE"
        assert result["lat"] == 52.52

    @pytest.mark.anyio
    async def test_country_filter_ignored_if_no_match(self):
        """If no results match the country code, all results are used."""
        with patch("bazi_engine.services.geocoding.httpx.AsyncClient",
                   return_value=_mock_httpx_client([BERLIN_US_RESULT])):
            result = await geocode_place("Berlin, DE")
        # No DE result → falls back to first result
        assert result["country_code"] == "US"

    @pytest.mark.anyio
    async def test_lat_lon_are_floats(self):
        with patch("bazi_engine.services.geocoding.httpx.AsyncClient",
                   return_value=_mock_httpx_client([BERLIN_RESULT])):
            result = await geocode_place("Berlin")
        assert isinstance(result["lat"], float)
        assert isinstance(result["lon"], float)

    @pytest.mark.anyio
    async def test_first_result_used_without_country_filter(self):
        with patch("bazi_engine.services.geocoding.httpx.AsyncClient",
                   return_value=_mock_httpx_client([BERLIN_RESULT, TOKYO_RESULT])):
            result = await geocode_place("Berlin")
        assert result["name"] == "Berlin"

    @pytest.mark.anyio
    async def test_missing_timezone_defaults_to_empty_string(self):
        no_tz = {**BERLIN_RESULT, "timezone": None}
        with patch("bazi_engine.services.geocoding.httpx.AsyncClient",
                   return_value=_mock_httpx_client([no_tz])):
            result = await geocode_place("Berlin")
        assert result["timezone"] == ""

    @pytest.mark.anyio
    async def test_none_results_key_raises(self):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"results": None}
        mock_resp.raise_for_status = MagicMock()
        mock_client = MagicMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        with patch("bazi_engine.services.geocoding.httpx.AsyncClient",
                   return_value=mock_client):
            with pytest.raises(ValueError):
                await geocode_place("Nowhere")
