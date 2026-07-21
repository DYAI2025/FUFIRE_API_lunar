"""ZWDS-P1-19 — natal engine orchestrator end-to-end.

Drives :func:`bazi_engine.zwds.engine.compute_zwds_raw` from the design-pack
example's own ``normalized_input`` (``response_example_core.json``) and asserts
the assembled response:

1. validates against ``ZwdsRawResponse.schema.json`` (0 errors), with the input
   first validated against ``ZwdsRequest.schema.json``;
2. reproduces the example chart's formula-derived fields (Ming/Shen, bureau,
   the 18 star placements, spot-checked star seats, the JIA transformation row,
   the first decadal limit, and a complete family set);
3. keeps the star/palace graph invariant (an explicit re-validation);
4. honors the schema's include_* if/then invariants (trace / decadal / catalog);
5. exposes the expected engine-version, source_status, and 64-hex fingerprint.

Marked ``swieph`` because the calendar half converts the civil chart date onto
the Chinese lunisolar calendar via the Swiss-Ephemeris astronomy (conftest
auto-skips when the SE1 data is absent; the formula-derived fields depend only
on the resolved ``(m, d, y_s, y_b, h-1)`` seed, which this vector fixes).
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict

import pytest
from jsonschema import Draft202012Validator

from bazi_engine.zwds import __zwds_engine_version__
from bazi_engine.zwds.engine import compute_zwds_raw
from bazi_engine.zwds.validation import validate_chart_graph

pytestmark = pytest.mark.swieph


def _repo_root() -> Path:
    """Walk up until the repo root (the dir carrying ``pyproject.toml``)."""
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

_GENERATED_AT = "1984-02-01T00:00:00Z"


def _load(path: Path) -> Dict[str, Any]:
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def _example_request() -> Dict[str, Any]:
    """Build a ``ZwdsRequest`` from the example's ``normalized_input`` echo."""
    normalized = _load(RESPONSE_EXAMPLE)["normalized_input"]
    return {
        "birth": normalized["birth"],
        "calculation": normalized["calculation"],
        "output": normalized["output"],
    }


def _schema_errors(schema: Dict[str, Any], instance: Dict[str, Any]) -> list:
    validator = Draft202012Validator(schema)
    return sorted(validator.iter_errors(instance), key=lambda err: list(err.path))


def _request_variant(**output_overrides: Any) -> Dict[str, Any]:
    """A schema-valid request with ``output`` field overrides applied."""
    request = _example_request()
    request["output"] = {**request["output"], **output_overrides}
    return request


def test_input_validates_against_request_schema() -> None:
    request = _example_request()
    errors = _schema_errors(_load(REQUEST_SCHEMA), request)
    assert errors == [], "request failed ZwdsRequest schema: " + "; ".join(
        f"{list(e.path)}: {e.message}" for e in errors
    )


def test_output_validates_against_raw_response_schema() -> None:
    schema = _load(RAW_RESPONSE_SCHEMA)
    Draft202012Validator.check_schema(schema)
    out = compute_zwds_raw(_example_request(), generated_at=_GENERATED_AT)
    errors = _schema_errors(schema, out)
    assert errors == [], "response failed ZwdsRawResponse schema: " + "; ".join(
        f"{list(e.path)}: {e.message}" for e in errors
    )


def test_reproduces_example_chart_formula_fields() -> None:
    chart = compute_zwds_raw(_example_request(), generated_at=_GENERATED_AT)[
        "chart"
    ]

    # Ming/Shen anchors + Five-Elements Bureau.
    assert chart["ming_palace_branch_id"] == "YIN"
    assert chart["shen_palace_branch_id"] == "YIN"
    assert chart["five_elements_bureau"]["id"] == "FIRE_6"

    # The 18 core-seed stars (14 major + 4 guide-auxiliary).
    placements = chart["star_placements"]
    assert len(placements) == 18
    seat = {p["star_id"]: p["branch_id"] for p in placements}
    assert seat["ZI_WEI"] == "YOU"
    assert seat["TIAN_FU"] == "WEI"
    assert seat["TAI_YANG"] == "WU"

    # JIA year-stem transformation row (design-pack example).
    tx = {t["type"]: t["star_id"] for t in chart["transformations"]}
    assert tx == {
        "HUA_LU": "LIAN_ZHEN",
        "HUA_QUAN": "PO_JUN",
        "HUA_KE": "WU_QU",
        "HUA_JI": "TAI_YANG",
    }
    # And the transformed star carries the type on its placement.
    assert seat and next(
        p["transformation_types"]
        for p in placements
        if p["star_id"] == "TAI_YANG"
    ) == ["HUA_JI"]

    # First decadal limit: Ming palace on YIN, ages 6-15, forward.
    first = chart["decadal_limits"][0]
    assert first["palace_role_id"] == "MING"
    assert first["branch_id"] == "YIN"
    assert first["start_age_inclusive"] == 6
    assert first["end_age_inclusive"] == 15
    assert first["direction"] == "forward"

    # Every declared star family was emitted.
    assert chart["completeness"]["missing_families"] == []
    assert chart["completeness"]["emitted_families"] == ["MAJOR_14", "GUIDE_AUX_4"]


def test_graph_invariant_holds_on_returned_chart() -> None:
    chart = compute_zwds_raw(_example_request(), generated_at=_GENERATED_AT)[
        "chart"
    ]
    # Re-validating the returned chart must not raise.
    validate_chart_graph(chart)


def test_include_trace_false_nulls_derivation_trace() -> None:
    out = compute_zwds_raw(
        _request_variant(include_trace=False), generated_at=_GENERATED_AT
    )
    assert out["derivation_trace"] is None
    # Still schema-valid under the trace-selection if/then invariant.
    assert _schema_errors(_load(RAW_RESPONSE_SCHEMA), out) == []


def test_include_decadal_limits_false_nulls_decadal_limits() -> None:
    out = compute_zwds_raw(
        _request_variant(include_decadal_limits=False),
        generated_at=_GENERATED_AT,
    )
    assert out["chart"]["decadal_limits"] is None
    assert _schema_errors(_load(RAW_RESPONSE_SCHEMA), out) == []


def test_include_catalog_false_nulls_catalog() -> None:
    out = compute_zwds_raw(_example_request(), generated_at=_GENERATED_AT)
    # The example request has include_catalog=false.
    assert out["catalog"] is None


def test_response_envelope_markers() -> None:
    out = compute_zwds_raw(_example_request(), generated_at=_GENERATED_AT)
    assert out["quality"]["source_status"] == "SOURCE_NEEDED"
    assert out["quality"]["calculation_status"] == "SUCCESS"
    assert out["engine_version"] == __zwds_engine_version__
    assert re.fullmatch(r"[a-f0-9]{64}", out["chart_fingerprint"])
    assert out["schema_version"] == "zwds.raw.v1"
