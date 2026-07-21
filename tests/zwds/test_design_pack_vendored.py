"""Guard test for the vendored ZWDS design-pack artifacts (ZWDS-P0-01).

Asserts the audited design-pack schemas and the canonical response example
were vendored intact: both schemas parse as JSON, carry their expected
stable ``$id`` URNs, and the shipped ``response_example_core.json`` validates
against the raw-response schema under JSON Schema Draft 2020-12.
"""

import json
from pathlib import Path

from jsonschema import Draft202012Validator


def _repo_root() -> Path:
    """Walk up from this file until we find the repo root (has pyproject.toml)."""
    for parent in Path(__file__).resolve().parents:
        if (parent / "pyproject.toml").is_file():
            return parent
    raise RuntimeError("could not locate repo root (no pyproject.toml found)")


ROOT = _repo_root()
SCHEMA_DIR = ROOT / "spec" / "schemas" / "zwds"
DESIGN_PACK_DIR = ROOT / "docs" / "zwds" / "design-pack"
REQUEST_SCHEMA = SCHEMA_DIR / "ZwdsRequest.schema.json"
RAW_RESPONSE_SCHEMA = SCHEMA_DIR / "ZwdsRawResponse.schema.json"
RESPONSE_EXAMPLE = DESIGN_PACK_DIR / "response_example_core.json"


def _load(path: Path) -> dict:
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def test_request_schema_loads_and_has_expected_id() -> None:
    schema = _load(REQUEST_SCHEMA)
    assert schema["$id"] == "urn:fufire:zwds:request:v1"


def test_raw_response_schema_loads_and_has_expected_id() -> None:
    schema = _load(RAW_RESPONSE_SCHEMA)
    assert schema["$id"] == "urn:fufire:zwds:raw-response:v1"


def test_response_example_validates_against_raw_response_schema() -> None:
    schema = _load(RAW_RESPONSE_SCHEMA)
    example = _load(RESPONSE_EXAMPLE)
    Draft202012Validator.check_schema(schema)
    errors = sorted(
        Draft202012Validator(schema).iter_errors(example),
        key=lambda err: list(err.path),
    )
    assert errors == [], "response_example_core.json failed schema validation: " + "; ".join(
        f"{list(err.path)}: {err.message}" for err in errors
    )
