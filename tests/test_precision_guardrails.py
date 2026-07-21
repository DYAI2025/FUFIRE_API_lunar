"""
tests/test_precision_guardrails.py — Precision guardrail tests.

When birth time is absent or marked uncertain, computed results
that depend on exact time (Ascendant, hour pillar, signature)
must carry a 'provisional' flag.
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from bazi_engine.app import app

client = TestClient(app)


class TestPrecisionFlags:
    """When birth_time_known=false, time-sensitive outputs are provisional."""

    BAZI_PAYLOAD = {
        "date": "1990-06-15T12:00:00",
        "tz": "Europe/Berlin",
        "lon": 13.405,
        "lat": 52.52,
    }

    def test_bazi_default_has_no_provisional_flag(self):
        """Normal request: precision.birth_time_known defaults to True."""
        response = client.post("/calculate/bazi", json=self.BAZI_PAYLOAD)
        assert response.status_code == 200
        body = response.json()
        assert body.get("precision", {}).get("birth_time_known") is True

    def test_bazi_unknown_time_flags_hour_provisional(self):
        """Unknown birth time: hour pillar flagged provisional."""
        payload = {**self.BAZI_PAYLOAD, "birth_time_known": False}
        response = client.post("/calculate/bazi", json=payload)
        assert response.status_code == 200
        body = response.json()
        prec = body.get("precision", {})
        assert prec.get("birth_time_known") is False
        assert "hour" in prec.get("provisional_fields", [])

    def test_bazi_known_time_has_empty_provisional_fields(self):
        """Known birth time: provisional_fields must be empty."""
        payload = {**self.BAZI_PAYLOAD, "birth_time_known": True}
        response = client.post("/calculate/bazi", json=payload)
        assert response.status_code == 200
        body = response.json()
        prec = body.get("precision", {})
        assert prec.get("provisional_fields", []) == []

    def test_western_unknown_time_flags_ascendant_provisional(self):
        """Unknown birth time: ascendant and houses flagged provisional."""
        payload = {
            "date": "1990-06-15T12:00:00",
            "tz": "Europe/Berlin",
            "lon": 13.405,
            "lat": 52.52,
            "birth_time_known": False,
        }
        response = client.post("/calculate/western", json=payload)
        assert response.status_code == 200
        body = response.json()
        prec = body.get("precision", {})
        assert prec.get("birth_time_known") is False
        assert "ascendant" in prec.get("provisional_fields", [])
        assert "houses" in prec.get("provisional_fields", [])

    def test_western_default_has_precision_block(self):
        """Western response always includes a precision block."""
        payload = {
            "date": "1990-06-15T12:00:00",
            "tz": "Europe/Berlin",
            "lon": 13.405,
            "lat": 52.52,
        }
        response = client.post("/calculate/western", json=payload)
        assert response.status_code == 200
        body = response.json()
        assert "precision" in body
        assert body["precision"]["birth_time_known"] is True

    def test_fusion_unknown_time_flags_signature_provisional(self):
        """Unknown birth time: signature flagged provisional."""
        payload = {
            "date": "1990-06-15T12:00:00",
            "tz": "Europe/Berlin",
            "lon": 13.405,
            "lat": 52.52,
            "birth_time_known": False,
        }
        response = client.post("/calculate/fusion", json=payload)
        assert response.status_code == 200
        body = response.json()
        prec = body.get("precision", {})
        assert prec.get("birth_time_known") is False
        assert "signature" in prec.get("provisional_fields", [])

    def test_fusion_default_has_precision_block(self):
        """Fusion response always includes a precision block."""
        payload = {
            "date": "1990-06-15T12:00:00",
            "tz": "Europe/Berlin",
            "lon": 13.405,
            "lat": 52.52,
        }
        response = client.post("/calculate/fusion", json=payload)
        assert response.status_code == 200
        body = response.json()
        assert "precision" in body
        assert body["precision"]["birth_time_known"] is True
