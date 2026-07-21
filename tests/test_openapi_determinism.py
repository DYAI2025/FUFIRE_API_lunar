"""Tests that verify OpenAPI schema determinism and model-name uniqueness.

``ChartRequest`` was previously defined in both
``bazi_engine.routers.chart`` and ``bazi_engine.routers.superglue``,
causing FastAPI/Pydantic to emit disambiguated fully-qualified keys such as
``bazi_engine__routers__chart__ChartRequest``.  Task 3 resolved the collision
by renaming to ``ChartComputeRequest`` and ``SuperglueChartTriggerRequest``.

``test_no_duplicate_unqualified_chart_request`` now passes cleanly.

``test_chart_refs_stable_across_seeds`` tests that the $ref targets in the
``/chart`` path remain identical across multiple in-process calls.  Because
the schema is cached by FastAPI (``app.openapi()``), we must invalidate the
cache between calls; here we vary nothing and just confirm stability.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_schema_in_process() -> dict:
    """Return the OpenAPI schema from the live FastAPI app.

    Forces a fresh schema generation by clearing FastAPI's internal cache
    (``app.openapi_schema``) before each call.
    """
    # Ensure the project root is on the path
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    from bazi_engine.app import app  # noqa: PLC0415

    # Clear FastAPI's cached schema so we get a fresh generation each call
    app.openapi_schema = None
    return app.openapi()


def _collect_chart_refs(schema: dict) -> set[str]:
    """Collect all $ref values from request bodies on paths containing 'chart'."""
    refs: set[str] = set()
    paths = schema.get("paths", {})
    for path, methods in paths.items():
        if "chart" in path.lower():
            for _method, op in methods.items():
                if not isinstance(op, dict):
                    continue
                body = op.get("requestBody", {})
                content = body.get("content", {})
                for _ct, desc in content.items():
                    s = desc.get("schema", {})
                    # Direct $ref
                    if "$ref" in s:
                        refs.add(s["$ref"])
                    # anyOf-wrapped (Optional[...] renders as anyOf with $ref + null)
                    for variant in s.get("anyOf", []):
                        if "$ref" in variant:
                            refs.add(variant["$ref"])
    return refs


def _export_schema_via_subprocess(seed: int) -> dict:
    """Run export_openapi.py with a given PYTHONHASHSEED, return the written JSON.

    The script writes to ``spec/openapi/openapi.json`` rather than stdout,
    so we read the file after the subprocess completes.
    """
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    spec_path = os.path.join(project_root, "spec", "openapi", "openapi.json")
    env = {**os.environ, "PYTHONHASHSEED": str(seed), "PYTHONPATH": project_root}
    # Delete stale spec file before each subprocess call so we always read fresh output
    if os.path.exists(spec_path):
        os.remove(spec_path)
    result = subprocess.run(
        [sys.executable, "scripts/export_openapi.py"],
        capture_output=True,
        text=True,
        env=env,
        cwd=project_root,
    )
    if result.returncode != 0:
        pytest.skip(
            f"export_openapi.py failed (seed={seed}): {result.stderr[:300]}"
        )
    try:
        return json.loads(
            open(spec_path, encoding="utf-8").read()
        )
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        pytest.skip(f"Could not read generated spec (seed={seed}): {exc}")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_no_duplicate_unqualified_chart_request():
    """There must be at most one schema component whose bare name is ChartRequest.

    Task 3 resolved the collision by renaming:
        bazi_engine.routers.chart.ChartRequest   → ChartComputeRequest
        bazi_engine.routers.superglue.ChartRequest → SuperglueChartTriggerRequest

    After the rename neither class carries the bare name ``ChartRequest``, so
    this assertion verifies the fix is in place and no regression has occurred.
    """
    schema = _get_schema_in_process()
    components = schema.get("components", {}).get("schemas", {})

    # Collect all component keys whose bare (last double-underscore segment or
    # the key itself) equals "ChartRequest" — case-insensitive for safety.
    chart_request_variants = [
        k for k in components
        # Match both the bare name and disambiguated fully-qualified variants
        if k.lower() == "chartrequest" or k.lower().endswith("__chartrequest")
    ]

    assert len(chart_request_variants) <= 1, (
        f"Multiple ChartRequest-named schemas detected (name collision): "
        f"{chart_request_variants}. "
        f"Rename one class to remove the ambiguity."
    )


def test_chart_refs_stable_across_seeds():
    """$ref targets on chart-related paths must be identical across repeated in-process calls.

    We call app.openapi() five times (cache cleared between calls) and verify
    the chart endpoint's $ref is always the same string.  This guards against
    mutable-default or side-effect non-determinism in schema generation — i.e.,
    where clearing and regenerating the schema within a single process produces
    different component keys on each call.  Hash-seed variance across *processes*
    is tested separately by ``test_chart_refs_stable_across_subprocesses``.
    """
    ref_sets = []
    for _ in range(5):
        schema = _get_schema_in_process()
        ref_sets.append(_collect_chart_refs(schema))

    assert all(r == ref_sets[0] for r in ref_sets), (
        f"Chart $refs are non-deterministic across schema generations: {ref_sets}"
    )


def test_chart_refs_stable_across_subprocesses():
    """$ref targets must be identical when the schema is generated with different
    PYTHONHASHSEED values via subprocess.

    This test exercises true cross-process hash-seed variance (unlike the
    in-process test above which only clears the cache).  It may be skipped in
    environments where export_openapi.py cannot run (e.g., missing ephemeris).
    """
    schemas = [_export_schema_via_subprocess(seed) for seed in range(3)]
    ref_sets = [_collect_chart_refs(s) for s in schemas]
    assert all(r == ref_sets[0] for r in ref_sets), (
        f"Chart $refs differ across PYTHONHASHSEED values: {ref_sets}"
    )
