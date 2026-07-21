"""
tests/test_openapi_error_contract.py

Failing contract tests for ErrorEnvelope coverage on protected operations.
Task 5 is responsible for making the xfail tests pass.
"""
import pytest

from bazi_engine.app import app


@pytest.fixture(scope="module")
def schema():
    return app.openapi()


def _get_protected_operations(schema: dict) -> list[tuple[str, str, dict]]:
    """Return (path, method, operation) for operations with X-API-Key parameter."""
    ops = []
    for path, methods in schema.get("paths", {}).items():
        for method, op in methods.items():
            if method not in ("get", "post", "put", "patch", "delete"):
                continue
            has_api_key = any(
                p.get("name") == "X-API-Key"
                for p in op.get("parameters", [])
            )
            has_security = bool(op.get("security"))
            if has_api_key or has_security:
                ops.append((path, method, op))
    return ops


def test_at_least_one_protected_operation(schema):
    """Sanity check — the auth detection must find some operations."""
    ops = _get_protected_operations(schema)
    assert len(ops) >= 5, f"Expected protected operations, found {len(ops)}: {[(p, m) for p, m, _ in ops]}"


def test_protected_ops_have_401(schema):
    ops = _get_protected_operations(schema)
    assert ops, "No protected operations detected — fix _get_protected_operations"
    missing = [
        f"{method.upper()} {path}"
        for path, method, op in ops
        if "401" not in op.get("responses", {})
    ]
    assert not missing, f"Missing 401 on: {missing[:5]}... ({len(missing)} total)"


def test_protected_ops_have_429(schema):
    ops = _get_protected_operations(schema)
    assert ops, "No protected operations detected — fix _get_protected_operations"
    missing = [
        f"{method.upper()} {path}"
        for path, method, op in ops
        if "429" not in op.get("responses", {})
    ]
    assert not missing, f"Missing 429 on: {missing[:5]}... ({len(missing)} total)"


def test_error_responses_reference_error_envelope(schema):
    error_codes = ("400", "401", "422", "429", "500", "503")
    components = schema.get("components", {}).get("schemas", {})
    assert "ErrorEnvelope" in components, "ErrorEnvelope schema missing from components"
    errors = []
    inspected = 0
    for path, methods in schema.get("paths", {}).items():
        for method, op in methods.items():
            if method not in ("get", "post", "put", "patch", "delete"):
                continue
            for code in error_codes:
                resp = op.get("responses", {}).get(code)
                if resp is None:
                    continue
                inspected += 1
                content = resp.get("content", {})
                json_content = content.get("application/json", {})
                ref = json_content.get("schema", {}).get("$ref", "")
                if "ErrorEnvelope" not in ref:
                    errors.append(f"{method.upper()} {path} [{code}] ref={ref!r}")
    # This xfail test is only meaningful if there are actual error responses to check.
    # If inspected==0, the test would vacuously pass — that would be a detection bug.
    assert inspected > 0, (
        "No error responses found in schema — either detection is broken "
        "or Task 5 hasn't added any responses yet (expected xfail, not vacuous pass)"
    )
    assert not errors, f"Non-ErrorEnvelope error responses: {errors[:5]}... ({len(errors)} total)"
