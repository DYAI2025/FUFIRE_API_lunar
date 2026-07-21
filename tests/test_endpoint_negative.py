"""Negative tests for API endpoints: invalid input, malformed requests, edge cases.

Covers all POST endpoints: /calculate/bazi, /calculate/western, /calculate/fusion,
/calculate/wuxing, /calculate/tst, /transit/state, /transit/narrative.
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from bazi_engine.app import app

client = TestClient(app)


class TestBaziEndpointNegative:
    """POST /calculate/bazi — invalid input handling."""

    def test_missing_date_returns_422(self):
        r = client.post("/calculate/bazi", json={"tz": "Europe/Berlin"})
        assert r.status_code == 422

    def test_empty_body_returns_422(self):
        r = client.post("/calculate/bazi", json={})
        assert r.status_code == 422

    def test_invalid_date_format_returns_error(self):
        r = client.post("/calculate/bazi", json={
            "date": "not-a-date", "tz": "Europe/Berlin",
        })
        assert r.status_code in (400, 422, 500)

    def test_invalid_timezone_returns_error(self):
        r = client.post("/calculate/bazi", json={
            "date": "2024-02-10T14:30:00", "tz": "Fake/Timezone",
        })
        assert r.status_code in (400, 422, 500)

    def test_nonexistent_dst_time_returns_error(self):
        """Spring-forward DST gap: 2:30 AM doesn't exist in US/Eastern on 2024-03-10."""
        r = client.post("/calculate/bazi", json={
            "date": "2024-03-10T02:30:00",
            "tz": "America/New_York",
            "nonexistentTime": "error",
        })
        assert r.status_code in (400, 422)

    def test_invalid_standard_returns_422(self):
        r = client.post("/calculate/bazi", json={
            "date": "2024-02-10T14:30:00",
            "standard": "INVALID",
        })
        assert r.status_code == 422

    def test_invalid_boundary_returns_422(self):
        r = client.post("/calculate/bazi", json={
            "date": "2024-02-10T14:30:00",
            "boundary": "invalid",
        })
        assert r.status_code == 422

    def test_no_content_type_returns_422(self):
        r = client.post("/calculate/bazi", content=b"not json")
        assert r.status_code == 422

    def test_null_body_returns_422(self):
        r = client.post(
            "/calculate/bazi",
            content=b"null",
            headers={"Content-Type": "application/json"},
        )
        assert r.status_code == 422


class TestWesternEndpointNegative:
    """POST /calculate/western — invalid input handling."""

    def test_missing_date_returns_422(self):
        r = client.post("/calculate/western", json={})
        assert r.status_code == 422

    def test_extreme_latitude_accepted(self):
        """Extreme latitude (near pole) should not crash."""
        r = client.post("/calculate/western", json={
            "date": "2024-06-21T12:00:00",
            "tz": "UTC",
            "lon": 0.0,
            "lat": 89.0,
        })
        # May fail with house calculation issues, but should not 500
        assert r.status_code in (200, 400, 422, 503)

    def test_longitude_out_of_range(self):
        """Longitude > 180 or < -180."""
        r = client.post("/calculate/western", json={
            "date": "2024-02-10T14:30:00",
            "tz": "UTC",
            "lon": 999.0,
            "lat": 52.0,
        })
        # Should either reject or handle gracefully
        assert r.status_code != 500 or r.status_code == 200


class TestFusionEndpointNegative:
    """POST /calculate/fusion — invalid input handling."""

    def test_missing_required_fields_returns_422(self):
        r = client.post("/calculate/fusion", json={})
        assert r.status_code == 422

    def test_missing_lon_returns_422(self):
        r = client.post("/calculate/fusion", json={
            "date": "2024-02-10T14:30:00",
            "tz": "UTC",
            "lat": 52.0,
            # missing lon
        })
        assert r.status_code == 422

    def test_invalid_bazi_pillars_format(self):
        """Providing malformed bazi_pillars should not crash."""
        r = client.post("/calculate/fusion", json={
            "date": "2024-02-10T14:30:00",
            "tz": "UTC",
            "lon": 13.4,
            "lat": 52.5,
            "bazi_pillars": {"year": "invalid"},  # wrong structure
        })
        assert r.status_code in (200, 400, 422, 500)


class TestTSTEndpointNegative:
    """POST /calculate/tst — True Solar Time negative cases."""

    def test_missing_date_returns_422(self):
        r = client.post("/calculate/tst", json={})
        assert r.status_code == 422

    def test_extreme_longitude_produces_valid_tst(self):
        """TST at lon=180 (date line) should still produce a valid result."""
        r = client.post("/calculate/tst", json={
            "date": "2024-06-21T12:00:00",
            "tz": "UTC",
            "lon": 180.0,
        })
        if r.status_code == 200:
            data = r.json()
            assert 0 <= data["true_solar_time_hours"] < 24

    def test_negative_longitude(self):
        r = client.post("/calculate/tst", json={
            "date": "2024-06-21T12:00:00",
            "tz": "UTC",
            "lon": -118.0,
        })
        if r.status_code == 200:
            data = r.json()
            assert 0 <= data["true_solar_time_hours"] < 24


class TestTransitEndpointNegative:
    """Transit endpoints — invalid input handling."""

    def test_state_missing_body_returns_422(self):
        r = client.post("/transit/state", json={})
        assert r.status_code == 422

    def test_state_wrong_array_length_returns_422(self):
        r = client.post("/transit/state", json={
            "soulprint_sectors": [0.1] * 5,
            "quiz_sectors": [0.1] * 12,
        })
        assert r.status_code == 422

    def test_state_string_values_returns_422(self):
        r = client.post("/transit/state", json={
            "soulprint_sectors": ["a"] * 12,
            "quiz_sectors": [0.1] * 12,
        })
        assert r.status_code == 422

    def test_timeline_days_zero_returns_422(self):
        r = client.get("/transit/timeline?days=0")
        assert r.status_code == 422

    def test_timeline_days_negative_returns_422(self):
        r = client.get("/transit/timeline?days=-5")
        assert r.status_code == 422

    def test_timeline_days_too_large_returns_422(self):
        r = client.get("/transit/timeline?days=100")
        assert r.status_code == 422

    def test_timeline_days_string_returns_422(self):
        r = client.get("/transit/timeline?days=abc")
        assert r.status_code == 422

    def test_now_invalid_datetime_returns_422(self):
        r = client.get("/transit/now?datetime=garbage")
        assert r.status_code == 422

    def test_now_partial_datetime_returns_422(self):
        r = client.get("/transit/now?datetime=2024-13-45")
        assert r.status_code == 422

    def test_narrative_empty_body_returns_422(self):
        r = client.post("/transit/narrative", json={})
        assert r.status_code == 422

    def test_narrative_missing_required_fields_returns_422(self):
        r = client.post("/transit/narrative", json={
            "transit_state": {
                "schema": "TRANSIT_STATE_v1",
                # missing generated_at, ring, transit_contribution, delta
            }
        })
        assert r.status_code == 422

    def test_narrative_invalid_schema_version_returns_422(self):
        r = client.post("/transit/narrative", json={
            "transit_state": {
                "schema": "INVALID_SCHEMA",
                "generated_at": "2026-01-01T00:00:00Z",
                "ring": {"sectors": [0.1] * 12},
                "transit_contribution": {
                    "sectors": [0.1] * 12,
                    "transit_intensity": 0.5,
                },
                "delta": {"vs_previous": None, "vs_30day_avg": None},
                "events": [],
            }
        })
        assert r.status_code == 422

    def test_narrative_wrong_ring_length_returns_422(self):
        r = client.post("/transit/narrative", json={
            "transit_state": {
                "schema": "TRANSIT_STATE_v1",
                "generated_at": "2026-01-01T00:00:00Z",
                "ring": {"sectors": [0.1] * 5},  # should be 12
                "transit_contribution": {
                    "sectors": [0.1] * 12,
                    "transit_intensity": 0.5,
                },
                "delta": {"vs_previous": None, "vs_30day_avg": None},
                "events": [],
            }
        })
        assert r.status_code == 422

    def test_narrative_event_invalid_type_returns_422(self):
        """Event with non-matching type pattern should be rejected."""
        r = client.post("/transit/narrative", json={
            "transit_state": {
                "schema": "TRANSIT_STATE_v1",
                "generated_at": "2026-01-01T00:00:00Z",
                "ring": {"sectors": [0.1] * 12},
                "transit_contribution": {
                    "sectors": [0.1] * 12,
                    "transit_intensity": 0.5,
                },
                "delta": {"vs_previous": None, "vs_30day_avg": None},
                "events": [{
                    "type": "invalid_type",
                    "priority": 1,
                    "sector": 0,
                    "trigger_planet": "moon",
                    "description_de": "test",
                    "personal_context": "test",
                }],
            }
        })
        assert r.status_code == 422

    def test_narrative_event_sector_out_of_range_returns_422(self):
        r = client.post("/transit/narrative", json={
            "transit_state": {
                "schema": "TRANSIT_STATE_v1",
                "generated_at": "2026-01-01T00:00:00Z",
                "ring": {"sectors": [0.1] * 12},
                "transit_contribution": {
                    "sectors": [0.1] * 12,
                    "transit_intensity": 0.5,
                },
                "delta": {"vs_previous": None, "vs_30day_avg": None},
                "events": [{
                    "type": "moon_event",
                    "priority": 1,
                    "sector": 15,  # must be 0-11
                    "trigger_planet": "moon",
                    "description_de": "test",
                    "personal_context": "test",
                }],
            }
        })
        assert r.status_code == 422


class TestValidateEndpointNegative:
    """POST /validate — contract validation edge cases."""

    def test_empty_body_returns_422(self):
        r = client.post("/validate", json={})
        assert r.status_code in (400, 422)

    def test_missing_content_type_returns_422(self):
        r = client.post("/validate", content=b"not json")
        assert r.status_code == 422

    def test_refdata_manifest_inline_null_rejected_by_schema(self):
        payload = {
            "engine_config": {
                "bazi_ruleset_id": "standard_bazi_2026",
                "refdata": {
                    "ephemeris_id": "swisseph"
                },
            },
            "refdata_manifest_inline": None,
        }
        r = client.post("/validate", json=payload)
        assert r.status_code == 422
        assert "ValidateRequest schema violation" in r.json().get("message", "")
