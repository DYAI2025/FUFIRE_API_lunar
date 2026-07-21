"""FBP-00-003 — Golden Case schema validation.

Two things are verified:

1. ``spec/golden/bazi_case.schema.json`` is itself a valid JSON Schema
   (Draft-07).
2. Every case currently registered in
   ``tests/golden_reference_cases.py::EXTENDED_GOLDEN_CASES`` can be
   converted to a dict that validates against the schema.

The conversion makes implicit assumptions explicit:

- ``calculation_profile.time_standard`` defaults to ``CIVIL``
  (because the tuple form does not carry it).
- ``calculation_profile.day_boundary_scheme`` defaults to ``midnight``
  (same reason).
- ``calculation_profile.ruleset_id`` defaults to
  ``standard_bazi_2026`` (the ruleset shipped in
  ``spec/rulesets/``).
- ``calculation_profile.ephemeris_id`` defaults to
  ``swieph_sepl18`` because the original docstring of
  ``golden_reference_cases.py`` states the values were produced under
  Swiss Ephemeris.

If Phase 1+ work changes any of these defaults, this test must be
updated alongside ``golden_reference_cases.py``.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

jsonschema = pytest.importorskip("jsonschema")
from jsonschema import Draft7Validator
from jsonschema.exceptions import SchemaError

from tests.golden_reference_cases import EXTENDED_GOLDEN_CASES

SPEC_DIR = Path(__file__).resolve().parents[1] / "spec" / "golden"
SCHEMA_PATH = SPEC_DIR / "bazi_case.schema.json"


@pytest.fixture(scope="module")
def schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text())


def test_schema_file_exists():
    """FBP-00-003: schema artifact must exist."""
    assert SCHEMA_PATH.exists(), (
        f"Expected {SCHEMA_PATH} (FBP-00-003 deliverable)."
    )


def test_schema_is_valid_draft7(schema):
    """The schema document itself must be valid Draft-07."""
    try:
        Draft7Validator.check_schema(schema)
    except SchemaError as exc:  # pragma: no cover - failure path
        pytest.fail(f"Schema is not valid Draft-07: {exc.message}")


def test_schema_declares_source_type_enum(schema):
    """source_type must be the three documented values, no fewer."""
    enum = schema["properties"]["source_type"]["enum"]
    assert set(enum) == {
        "ENGINE_BASELINE",
        "EXTERNAL_ORACLE",
        "DOMAIN_REVIEW_REQUIRED",
    }


def _tuple_to_case_dict(case) -> dict:
    case_id, birth_local, tz, lon, lat, expected, source_note, source_type = case
    year, month, day, hour = expected
    return {
        "id": case_id,
        "birth_local": birth_local,
        "timezone": tz,
        "longitude_deg": float(lon),
        "latitude_deg": float(lat),
        "expected_pillars": {
            "year": year, "month": month, "day": day, "hour": hour,
        },
        "source_type": source_type,
        "source": source_note,
        "calculation_profile": {
            "time_standard": "CIVIL",
            "day_boundary_scheme": "midnight",
            "ruleset_id": "standard_bazi_2026",
            "ephemeris_id": "swieph_sepl18",
        },
    }


@pytest.mark.parametrize(
    "case",
    EXTENDED_GOLDEN_CASES,
    ids=[c[0] for c in EXTENDED_GOLDEN_CASES],
)
def test_each_extended_case_validates(schema, case):
    """Every registered golden case must validate against the schema."""
    validator = Draft7Validator(schema)
    case_dict = _tuple_to_case_dict(case)
    errors = sorted(validator.iter_errors(case_dict), key=lambda e: list(e.path))
    assert not errors, "\n".join(
        f"{list(e.path)}: {e.message}" for e in errors
    )


def test_pillar_pattern_rejects_garbage(schema):
    """Pattern must reject invalid Stem/Branch combinations."""
    validator = Draft7Validator(schema)
    bad = {
        "id": "bad",
        "birth_local": "2024-01-01T00:00:00",
        "timezone": "UTC",
        "longitude_deg": 0.0,
        "latitude_deg": 0.0,
        "expected_pillars": {
            "year": "NotAPillar", "month": "JiaChen",
            "day": "JiaChen", "hour": "JiaChen",
        },
        "source_type": "ENGINE_BASELINE",
        "calculation_profile": {
            "time_standard": "CIVIL",
            "day_boundary_scheme": "midnight",
            "ruleset_id": "standard_bazi_2026",
        },
    }
    errors = list(validator.iter_errors(bad))
    assert errors, "Schema must reject invalid pillar string 'NotAPillar'."
