"""
test_error_handling.py — Verifies that exceptions map to correct HTTP status codes.

Tests the global exception handler chain in app.py:
  BaziEngineError subclasses → specific HTTP codes (422, 503, 500, 501)
  LocalTimeError (DST)        → 422
  EphemerisUnavailableError   → 503
  CalculationError            → 500
  NotSupportedError           → 501

Also tests the exception hierarchy itself (pure unit tests, no HTTP).
"""
from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from bazi_engine.app import app
from bazi_engine.exc import (
    BaziEngineError,
    CalculationError,
    EphemerisUnavailableError,
    InputError,
    NotSupportedError,
)
from bazi_engine.time_utils import LocalTimeError

client = TestClient(app, raise_server_exceptions=False)


# ============================================================================
# Unit tests — exception hierarchy (no HTTP, no I/O)
# ============================================================================

class TestExceptionHierarchy:
    """Verifies exc.py structure and MRO."""

    def test_input_error_is_bazi_engine_error(self):
        e = InputError("bad input")
        assert isinstance(e, BaziEngineError)

    def test_ephemeris_error_is_bazi_engine_error(self):
        e = EphemerisUnavailableError("missing files")
        assert isinstance(e, BaziEngineError)

    def test_calculation_error_is_bazi_engine_error(self):
        e = CalculationError("solver failed")
        assert isinstance(e, BaziEngineError)

    def test_not_supported_error_is_bazi_engine_error(self):
        e = NotSupportedError("skyfield not implemented")
        assert isinstance(e, BaziEngineError)

    def test_http_status_codes(self):
        assert InputError.http_status == 422
        assert EphemerisUnavailableError.http_status == 503
        assert CalculationError.http_status == 500
        assert NotSupportedError.http_status == 501

    def test_error_codes_are_strings(self):
        assert isinstance(InputError.error_code, str)
        assert isinstance(EphemerisUnavailableError.error_code, str)

    def test_to_dict_has_required_keys(self):
        e = InputError("bad date", detail={"field": "birth_local"})
        d = e.to_dict()
        assert "error" in d
        assert "message" in d
        assert "detail" in d
        assert d["detail"]["field"] == "birth_local"

    def test_detail_defaults_to_empty_dict(self):
        e = CalculationError("numerical failure")
        assert e.detail == {}

    def test_message_preserved(self):
        e = EphemerisUnavailableError("files not found")
        assert str(e) == "files not found"
        assert e.to_dict()["message"] == "files not found"


class TestLocalTimeErrorMRO:
    """LocalTimeError must be both InputError and ValueError."""

    def test_is_input_error(self):
        e = LocalTimeError("DST gap")
        assert isinstance(e, InputError)

    def test_is_value_error(self):
        """Backwards compatibility: old code that catches ValueError still works."""
        e = LocalTimeError("ambiguous time")
        assert isinstance(e, ValueError)

    def test_is_bazi_engine_error(self):
        e = LocalTimeError("nonexistent time")
        assert isinstance(e, BaziEngineError)

    def test_http_status_is_422(self):
        e = LocalTimeError("test")
        assert e.http_status == 422

    def test_caught_as_value_error(self):
        """Ensure old try/except ValueError blocks don't break."""
        caught = False
        try:
            raise LocalTimeError("DST gap")
        except ValueError:
            caught = True
        assert caught

    def test_caught_as_input_error(self):
        caught = False
        try:
            raise LocalTimeError("DST gap")
        except InputError:
            caught = True
        assert caught


# ============================================================================
# HTTP status code tests — via TestClient
# ============================================================================

class TestBaziEndpointErrorCodes:
    """POST /calculate/bazi — verify HTTP codes for different error types."""

    def test_invalid_timezone_returns_422_or_400(self):
        """Malformed timezone string should not return 500."""
        r = client.post("/calculate/bazi", json={
            "date": "2024-02-10T14:30:00",
            "tz": "Not/A/Timezone",
            "lon": 13.405,
            "lat": 52.52,
        })
        assert r.status_code in (400, 422), f"Got {r.status_code}: {r.text}"

    def test_dst_nonexistent_time_returns_422(self):
        """2024-03-31T02:30:00 Europe/Berlin is in the DST spring-forward gap → 422."""
        r = client.post("/calculate/bazi", json={
            "date": "2024-03-31T02:30:00",
            "tz": "Europe/Berlin",
            "lon": 13.405,
            "lat": 52.52,
            "nonexistentTime": "error",
        })
        # LocalTimeError → InputError → 422
        assert r.status_code == 422, f"Expected 422, got {r.status_code}: {r.text}"

    def test_missing_required_field_returns_422(self):
        """Pydantic validation error for missing 'date' field."""
        r = client.post("/calculate/bazi", json={
            "tz": "Europe/Berlin",
            "lon": 13.405,
            "lat": 52.52,
        })
        assert r.status_code == 422

    def test_valid_request_not_an_error(self):
        """A valid request with ephemeris auto-mode should not raise 4xx/5xx
        (it may return 503 if ephemeris files are absent — that's OK and expected)."""
        r = client.post("/calculate/bazi", json={
            "date": "2024-02-10T14:30:00",
            "tz": "Europe/Berlin",
            "lon": 13.405,
            "lat": 52.52,
        })
        assert r.status_code in (200, 503), f"Unexpected {r.status_code}: {r.text}"


class TestEphemerisErrorCode:
    """EphemerisUnavailableError must return HTTP 503, not 400."""

    def test_ephemeris_unavailable_gives_503(self):
        from bazi_engine.exc import EphemerisUnavailableError
        from bazi_engine.routers import bazi as bazi_router

        with patch.object(bazi_router, "compute_bazi",
                          side_effect=EphemerisUnavailableError("no ephe files")):
            r = client.post("/calculate/bazi", json={
                "date": "2024-02-10T14:30:00",
                "tz": "Europe/Berlin",
                "lon": 13.405,
                "lat": 52.52,
                "nonexistentTime": "shift_forward",
            })
        assert r.status_code == 503, f"Expected 503, got {r.status_code}: {r.text}"
        data = r.json()
        assert data["error"] == "ephemeris_unavailable"

    def test_ephemeris_503_response_has_error_field(self):
        from bazi_engine.exc import EphemerisUnavailableError
        from bazi_engine.routers import bazi as bazi_router

        with patch.object(bazi_router, "compute_bazi",
                          side_effect=EphemerisUnavailableError("missing", detail={"missing_files": ["sepl.se1"]})):
            r = client.post("/calculate/bazi", json={
                "date": "2024-02-10T14:30:00",
                "tz": "Europe/Berlin",
                "lon": 13.405,
                "lat": 52.52,
                "nonexistentTime": "shift_forward",
            })
        assert r.status_code == 503
        data = r.json()
        assert "error" in data
        assert "message" in data
        assert "detail" in data


class TestCalculationErrorCode:
    """CalculationError must return HTTP 500, not 400."""

    def test_calculation_error_gives_500(self):
        from bazi_engine.exc import CalculationError
        from bazi_engine.routers import bazi as bazi_router

        with patch.object(bazi_router, "compute_bazi",
                          side_effect=CalculationError("bisection failed")):
            r = client.post("/calculate/bazi", json={
                "date": "2024-02-10T14:30:00",
                "tz": "Europe/Berlin",
                "lon": 13.405,
                "lat": 52.52,
                "nonexistentTime": "shift_forward",
            })
        assert r.status_code == 500, f"Expected 500, got {r.status_code}: {r.text}"
        data = r.json()
        assert data["error"] == "calculation_error"


class TestNotSupportedErrorCode:
    """NotSupportedError must return HTTP 501."""

    def test_not_supported_gives_501(self):
        from bazi_engine.exc import NotSupportedError
        from bazi_engine.routers import bazi as bazi_router

        with patch.object(bazi_router, "compute_bazi",
                          side_effect=NotSupportedError("skyfield not impl")):
            r = client.post("/calculate/bazi", json={
                "date": "2024-02-10T14:30:00",
                "tz": "Europe/Berlin",
                "lon": 13.405,
                "lat": 52.52,
                "nonexistentTime": "shift_forward",
            })
        assert r.status_code == 501, f"Expected 501, got {r.status_code}: {r.text}"
        data = r.json()
        assert data["error"] == "not_supported"


class TestErrorResponseShape:
    """All BaziEngineError responses must have a consistent JSON shape."""

    ERROR_PAYLOADS = [
        ("input_error",          422, InputError("bad")),
        ("ephemeris_unavailable", 503, EphemerisUnavailableError("missing")),
        ("calculation_error",     500, CalculationError("fail")),
        ("not_supported",         501, NotSupportedError("stub")),
    ]

    @pytest.mark.parametrize("expected_code,expected_status,exc", ERROR_PAYLOADS)
    def test_error_shape(self, expected_code, expected_status, exc):
        from bazi_engine.routers import bazi as bazi_router

        with patch.object(bazi_router, "compute_bazi", side_effect=exc):
            r = client.post("/calculate/bazi", json={
                "date": "2024-02-10T14:30:00",
                "tz": "Europe/Berlin",
                "lon": 13.405,
                "lat": 52.52,
                "nonexistentTime": "shift_forward",
            })
        assert r.status_code == expected_status
        data = r.json()
        assert data.get("error") == expected_code, f"Got shape: {data}"
        assert "message" in data
        assert "detail" in data
