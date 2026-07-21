"""FBP-03-005 — ErrorEnvelope extracted to spec/schemas/ErrorEnvelope.schema.json.

Verifies:
- The schema file exists and is valid JSON Schema Draft-07
- The Pydantic ErrorEnvelope lives in routers/shared (not validate.py)
- The OpenAPI spec's ErrorEnvelope is loaded from the file (not inline)
- Required fields are consistent between file, Pydantic model, and OpenAPI spec
- Existing error-envelope behaviour tests still pass (no regression)
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from bazi_engine.app import app
from bazi_engine.routers.shared import ErrorEnvelope

client = TestClient(app)

SPEC_DIR = Path(__file__).parent.parent / "spec" / "schemas"
SCHEMA_FILE = SPEC_DIR / "ErrorEnvelope.schema.json"


def _ephemeris_available() -> bool:
    r = client.post("/calculate/bazi", json={
        "date": "2024-02-10T14:30:00", "tz": "Europe/Berlin",
        "lon": 13.405, "lat": 52.52,
    })
    return r.status_code == 200


_HAS_EPHEMERIS = _ephemeris_available()
_skip_no_ephe = pytest.mark.skipif(not _HAS_EPHEMERIS,
                                   reason="Swiss Ephemeris files not available")


class TestSchemaFile:
    def test_schema_file_exists(self):
        assert SCHEMA_FILE.exists(), f"Missing: {SCHEMA_FILE}"

    def test_schema_file_valid_json(self):
        data = json.loads(SCHEMA_FILE.read_text())
        assert isinstance(data, dict)

    def test_schema_draft07(self):
        data = json.loads(SCHEMA_FILE.read_text())
        assert "draft-07" in data.get("$schema", "")

    def test_schema_required_fields(self):
        data = json.loads(SCHEMA_FILE.read_text())
        assert set(data["required"]) == {"error", "message", "request_id"}

    def test_schema_properties_cover_all_fields(self):
        data = json.loads(SCHEMA_FILE.read_text())
        props = set(data["properties"].keys())
        expected = {"error", "message", "detail", "status", "path", "timestamp", "request_id"}
        assert expected == props

    def test_schema_has_title(self):
        data = json.loads(SCHEMA_FILE.read_text())
        assert data.get("title") == "ErrorEnvelope"


class TestPydanticModel:
    def test_error_envelope_importable_from_shared(self):
        """FBP-03-005: canonical home is routers/shared, not routers/validate."""
        from bazi_engine.routers.shared import ErrorEnvelope as EE
        assert EE is ErrorEnvelope

    def test_error_envelope_not_defined_in_validate(self):
        """No independent ErrorEnvelope class left in validate.py."""
        import importlib
        validate_mod = importlib.import_module("bazi_engine.routers.validate")
        # The name may be re-exported, but it must point to shared.ErrorEnvelope
        if hasattr(validate_mod, "ErrorEnvelope"):
            assert validate_mod.ErrorEnvelope is ErrorEnvelope

    def test_pydantic_required_fields_match_schema(self):
        schema_required = set(json.loads(SCHEMA_FILE.read_text())["required"])
        # All schema required fields must be non-optional in the Pydantic model
        model_fields = ErrorEnvelope.model_fields
        for field in schema_required:
            assert field in model_fields, f"Pydantic model missing {field!r}"
            info = model_fields[field]
            assert info.is_required(), f"Pydantic field {field!r} should be required"

    def test_error_envelope_rejects_extra_fields(self):
        """ErrorEnvelope Pydantic model must enforce additionalProperties: false."""
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            ErrorEnvelope(
                error="x", message="y", request_id="z",
                status=422, path="/", timestamp="2026-01-01T00:00:00Z",
                extra_field="should_fail",
            )


class TestOpenApiSpec:
    def test_openapi_error_envelope_exists(self):
        spec = client.get("/openapi.json").json()
        assert "ErrorEnvelope" in spec["components"]["schemas"]

    def test_openapi_error_envelope_required_fields(self):
        spec = client.get("/openapi.json").json()
        ee = spec["components"]["schemas"]["ErrorEnvelope"]
        assert "required" in ee
        assert set(ee["required"]) == {"error", "message", "request_id"}

    def test_openapi_error_envelope_has_additionalproperties_false(self):
        """Loaded from file — should inherit additionalProperties: false."""
        spec = client.get("/openapi.json").json()
        ee = spec["components"]["schemas"]["ErrorEnvelope"]
        assert ee.get("additionalProperties") is False

    def test_openapi_validate_422_refs_error_envelope(self):
        spec = client.get("/openapi.json").json()
        paths = spec.get("paths", {})
        validate_path = paths.get("/validate") or paths.get("/v1/validate") or {}
        post = validate_path.get("post", {})
        err_schema = (
            post.get("responses", {})
               .get("422", {})
               .get("content", {})
               .get("application/json", {})
               .get("schema", {})
        )
        assert err_schema == {"$ref": "#/components/schemas/ErrorEnvelope"}


    def test_openapi_error_envelope_has_example(self):
        """ErrorEnvelope in OpenAPI spec must have an example for Swagger UI (FBP-03-005 fix)."""
        spec = client.get("/openapi.json").json()
        ee = spec["components"]["schemas"]["ErrorEnvelope"]
        assert "example" in ee, "ErrorEnvelope schema missing example field"
        assert ee["example"]["error"] == "validation_error"
        assert "request_id" in ee["example"]

@_skip_no_ephe
class TestErrorEnvelopeRuntime:
    def test_dst_error_returns_envelope(self):
        """Trigger 422 via DST gap — response must match ErrorEnvelope shape."""
        r = client.post("/calculate/bazi", json={
            "date": "2026-03-29T02:30:00",
            "tz": "Europe/Berlin",
            "lon": 13.405, "lat": 52.52,
            "nonexistentTime": "error",
        })
        assert r.status_code == 422
        body = r.json()
        for field in ("error", "message", "status", "path", "timestamp", "request_id"):
            assert field in body, f"envelope missing {field!r}"

    def test_envelope_error_field_is_string(self):
        r = client.post("/calculate/bazi", json={
            "date": "2026-03-29T02:30:00", "tz": "Europe/Berlin",
            "lon": 13.405, "lat": 52.52, "nonexistentTime": "error",
        })
        assert isinstance(r.json()["error"], str)
