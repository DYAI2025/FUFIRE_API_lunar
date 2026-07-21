"""Tests for transit input validation."""
from __future__ import annotations

import json

from fastapi.testclient import TestClient

from bazi_engine.app import app

client = TestClient(app)

VALID_SECTORS = [0.1] * 12

# JSON strings with non-finite values (Python json module rejects NaN/Inf,
# so we construct the raw payload manually).
_VALID_JSON = json.dumps(VALID_SECTORS)


class TestTransitSectorValidation:
    """Verify sector arrays are validated before processing."""

    def test_nan_in_soulprint_rejected(self):
        # NaN is not valid JSON per RFC 7159, but many parsers accept it.
        # Send raw content to bypass Python json encoder.
        payload = (
            '{"soulprint_sectors": [0.1,0.1,0.1,0.1,0.1,0.1,0.1,0.1,0.1,0.1,0.1,NaN],'
            f' "quiz_sectors": {_VALID_JSON}}}'
        )
        r = client.post(
            "/transit/state",
            content=payload,
            headers={"Content-Type": "application/json"},
        )
        assert r.status_code == 422

    def test_inf_in_quiz_rejected(self):
        payload = (
            f'{{"soulprint_sectors": {_VALID_JSON},'
            ' "quiz_sectors": [Infinity,0.1,0.1,0.1,0.1,0.1,0.1,0.1,0.1,0.1,0.1,0.1]}'
        )
        r = client.post(
            "/transit/state",
            content=payload,
            headers={"Content-Type": "application/json"},
        )
        assert r.status_code == 422

    def test_negative_value_rejected(self):
        bad = [-0.5] + [0.1] * 11
        r = client.post("/transit/state", json={
            "soulprint_sectors": bad,
            "quiz_sectors": VALID_SECTORS,
        })
        assert r.status_code == 422

    def test_value_above_one_rejected(self):
        bad = [1.5] + [0.1] * 11
        r = client.post("/transit/state", json={
            "soulprint_sectors": bad,
            "quiz_sectors": VALID_SECTORS,
        })
        assert r.status_code == 422

    def test_wrong_length_rejected(self):
        r = client.post("/transit/state", json={
            "soulprint_sectors": [0.1] * 10,
            "quiz_sectors": VALID_SECTORS,
        })
        assert r.status_code == 422

    def test_valid_sectors_accepted(self):
        """Valid sectors should not be rejected by validation (may get 503 from ephemeris)."""
        r = client.post("/transit/state", json={
            "soulprint_sectors": VALID_SECTORS,
            "quiz_sectors": VALID_SECTORS,
        })
        assert r.status_code != 422


class TestTransitDatetimeValidation:
    """Verify datetime parameter validation returns 422 not 500."""

    def test_invalid_datetime_returns_422(self):
        r = client.get("/transit/now", params={"datetime": "not-a-date"})
        assert r.status_code == 422, f"Expected 422 but got {r.status_code}: {r.json()}"

    def test_valid_datetime_accepted(self):
        r = client.get("/transit/now", params={"datetime": "2024-06-15T12:00:00Z"})
        assert r.status_code in (200, 503)

    def test_no_datetime_defaults_to_now(self):
        r = client.get("/transit/now")
        assert r.status_code in (200, 503)
