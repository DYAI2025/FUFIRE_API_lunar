from __future__ import annotations

from fastapi.testclient import TestClient

from bazi_engine.app import app
from bazi_engine.lunar_state import EPHEMERIS_LOCK_ID

client = TestClient(app)


def _payload() -> dict[str, object]:
    return {
        "instant": {
            "datetime_local": "2024-04-08T18:21:00",
            "timezone": "UTC",
            "ambiguousTime": "earlier",
            "nonexistentTime": "error",
        }
    }


def test_v2_lunar_state_endpoint_returns_canonical_shape() -> None:
    response = client.post("/v2/astronomy/lunar-state", json=_payload())

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["schema_version"] == "lunar-state.v2"
    assert body["instant"]["utc"] == "2024-04-08T18:21:00.000000Z"
    assert body["lunar_state"]["phase"]["id"] == "new_moon"
    assert body["lunar_state"]["phase"]["illumination_fraction"] < 0.01
    assert body["lunar_state"]["method"]["id"] == "canonical-geocentric-lunar-state-v2"
    assert body["lunar_state"]["method"]["reference_frame"] == "geocentric_apparent_ecliptic_of_date"
    method = body["lunar_state"]["method"]
    assert method["precision_grade"] in {"high_precision", "degraded"}
    assert method["precision_grade"] != "exact"
    if method["ephemeris_mode"] == "SWIEPH":
        assert method["ephemeris_lock_id"] == EPHEMERIS_LOCK_ID
    else:
        assert method["ephemeris_lock_id"] is None
    assert method["supported_utc_start"] == "1900-01-01T00:00:00+00:00"
    assert method["supported_utc_end_exclusive"] == "2100-01-01T00:00:00+00:00"


def test_v2_lunar_state_endpoint_preserves_fold_choice() -> None:
    payload = _payload()
    payload["instant"] = {
        "datetime_local": "2024-10-27T02:51:00",
        "timezone": "Europe/Berlin",
        "ambiguousTime": "later",
        "nonexistentTime": "error",
    }

    response = client.post("/v2/astronomy/lunar-state", json=payload)

    assert response.status_code == 200, response.text
    instant = response.json()["instant"]
    assert instant["fold"] == 1
    assert instant["utc"] == "2024-10-27T01:51:00.000000Z"
    assert instant["utc_offset_seconds"] == 3600


def test_v2_lunar_state_rejects_nonexistent_time_before_astronomy() -> None:
    payload = _payload()
    payload["instant"] = {
        "datetime_local": "2024-03-31T02:30:00",
        "timezone": "Europe/Berlin",
        "ambiguousTime": "earlier",
        "nonexistentTime": "error",
    }

    response = client.post("/v2/astronomy/lunar-state", json=payload)

    assert response.status_code == 422
    assert response.json()["error"] == "dst_time_error"


def test_lunar_state_is_v2_only() -> None:
    assert client.post("/astronomy/lunar-state", json=_payload()).status_code == 404
    assert client.post("/v1/astronomy/lunar-state", json=_payload()).status_code == 404


def test_lunar_state_rejects_instant_outside_supported_range() -> None:
    payload = _payload()
    payload["instant"] = {
        "datetime_local": "2100-01-01T00:00:00",
        "timezone": "UTC",
        "ambiguousTime": "earlier",
        "nonexistentTime": "error",
    }

    response = client.post("/v2/astronomy/lunar-state", json=payload)

    assert response.status_code == 422
    assert response.json()["error"] == "input_error"
    assert "supported_utc_end_exclusive" in response.json()["detail"]


def test_openapi_contains_typed_v2_lunar_state_contract() -> None:
    spec = app.openapi()
    operation = spec["paths"]["/v2/astronomy/lunar-state"]["post"]

    assert operation["requestBody"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/LunarStateRequest"
    }
    assert operation["responses"]["200"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/LunarStateResponse"
    }
