"""
test_openapi_contract.py — Verify OpenAPI spec completeness and /validate typing.

These tests ensure:
  - All routes have a typed response schema (no generic "object any")
  - /validate references ValidateRequest and ValidateResponse
  - ErrorEnvelope schema exists
  - info.version matches engine __version__
"""
from __future__ import annotations

import pytest

from bazi_engine import __version__
from bazi_engine.app import app


@pytest.fixture(scope="module")
def openapi_spec():
    # Force fresh generation
    app.openapi_schema = None
    return app.openapi()


class TestOpenAPICompleteness:
    def test_version_matches_engine(self, openapi_spec):
        assert openapi_spec["info"]["version"] == __version__

    def test_all_endpoints_have_typed_responses(self, openapi_spec):
        untyped = []
        for path, methods in openapi_spec["paths"].items():
            for method, detail in methods.items():
                resp200 = (
                    detail.get("responses", {})
                    .get("200", {})
                    .get("content", {})
                    .get("application/json", {})
                    .get("schema", {})
                )
                has_ref = "$ref" in str(resp200)
                has_props = "properties" in resp200
                if not has_ref and not has_props:
                    untyped.append(f"{method.upper()} {path}")
        assert untyped == [], f"Untyped endpoints: {untyped}"


class TestValidateEndpointContract:
    def test_validate_request_schema_referenced(self, openapi_spec):
        validate = openapi_spec["paths"]["/validate"]["post"]
        req_schema = validate["requestBody"]["content"]["application/json"]["schema"]
        assert req_schema == {"$ref": "#/components/schemas/ValidateRequest"}

    def test_validate_response_schema_referenced(self, openapi_spec):
        validate = openapi_spec["paths"]["/validate"]["post"]
        resp_schema = validate["responses"]["200"]["content"]["application/json"]["schema"]
        assert resp_schema == {"$ref": "#/components/schemas/ValidateResponse"}

    def test_validate_request_definitions_hoisted(self, openapi_spec):
        """Draft-07 definitions are hoisted to components/schemas for codegen compatibility."""
        all_schemas = set(openapi_spec["components"]["schemas"].keys())
        expected = {"BirthEvent", "EngineConfig", "RefDataConfig", "Pillar"}
        assert expected.issubset(all_schemas), f"Missing: {expected - all_schemas}"

    def test_validate_response_definitions_hoisted(self, openapi_spec):
        all_schemas = set(openapi_spec["components"]["schemas"].keys())
        expected = {"Issue", "ErrorCode", "ComponentStatus", "TimeEvidence"}
        assert expected.issubset(all_schemas), f"Missing: {expected - all_schemas}"

    def test_error_envelope_exists(self, openapi_spec):
        assert "ErrorEnvelope" in openapi_spec["components"]["schemas"]

    def test_validate_422_uses_error_envelope(self, openapi_spec):
        validate = openapi_spec["paths"]["/validate"]["post"]
        err_schema = validate["responses"]["422"]["content"]["application/json"]["schema"]
        assert err_schema == {"$ref": "#/components/schemas/ErrorEnvelope"}
