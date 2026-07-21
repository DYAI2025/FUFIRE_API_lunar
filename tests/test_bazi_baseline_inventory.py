"""FBP-00-004 — Baseline inventory test.

Confirms that ``tests/fixtures/bazi_baseline_v1.json`` exists and
covers the boundary categories required by the Phase-0 stop-gate
(routine, lichun_boundary, zi_day_boundary, dst, jieqi_boundary,
tlst_neighborhood, historical).

The test does **not** assert exact pillar values — that is the job of
``test_regression_v1_compatibility.py``. This test only enforces
*coverage*.

If the baseline file is missing, the test fails with a pointer to the
exporter script (``scripts/export_bazi_baseline.py``) rather than
silently passing.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
BASELINE_PATH = REPO_ROOT / "tests" / "fixtures" / "bazi_baseline_v1.json"

REQUIRED_CATEGORIES = {
    "routine",
    "lichun_boundary",
    "zi_day_boundary",
    "dst",
    "jieqi_boundary",
    "tlst_neighborhood",
    "historical",
}


def test_baseline_file_exists():
    """Phase-0 deliverable: an engine-derived v1 baseline must exist."""
    if not BASELINE_PATH.exists():
        pytest.fail(
            f"Baseline {BASELINE_PATH} is missing. "
            "Run `python scripts/export_bazi_baseline.py` to create it. "
            "See FBP-00-004 in 3-code/tasks.md."
        )


def _load_baseline() -> dict:
    if not BASELINE_PATH.exists():
        pytest.skip("baseline file absent; see test_baseline_file_exists")
    return json.loads(BASELINE_PATH.read_text())


def test_baseline_metadata_complete():
    doc = _load_baseline()
    md = doc.get("metadata", {})
    for key in (
        "engine_version",
        "parameter_set_version",
        "ruleset_id",
        "ephemeris_mode",
        "exporter",
    ):
        assert key in md, f"Baseline metadata missing '{key}': {md}"
    assert md["exporter"].endswith("export_bazi_baseline.py")


def test_baseline_covers_required_categories():
    doc = _load_baseline()
    cases = doc.get("cases", [])
    categories = {c["category"] for c in cases}
    missing = REQUIRED_CATEGORIES - categories
    assert not missing, (
        f"Baseline is missing required boundary categories: {missing}. "
        "Extend BASELINE_CASES in scripts/export_bazi_baseline.py."
    )


def test_baseline_ids_are_unique():
    doc = _load_baseline()
    ids = [c["id"] for c in doc["cases"]]
    duplicates = {i for i in ids if ids.count(i) > 1}
    assert not duplicates, f"Duplicate baseline case ids: {duplicates}"


def test_detect_ephemeris_mode_is_pure(monkeypatch):
    """I2: detection must not mutate the environment."""
    import importlib

    import scripts.export_bazi_baseline as exp
    importlib.reload(exp)

    monkeypatch.delenv("EPHEMERIS_MODE", raising=False)
    before = dict(os.environ)
    mode = exp._detect_ephemeris_mode()
    after = dict(os.environ)
    assert mode in {"SWIEPH", "MOSEPH"}
    assert before == after, (
        f"_detect_ephemeris_mode mutated env. "
        f"Added: {set(after) - set(before)}; "
        f"Changed: {[k for k in before if before[k] != after.get(k)]}"
    )


def test_baseline_pillars_well_formed():
    """Every recorded pillar must match the canonical Stem+Branch shape."""
    import re
    pat = re.compile(
        r"^(Jia|Yi|Bing|Ding|Wu|Ji|Geng|Xin|Ren|Gui)"
        r"(Zi|Chou|Yin|Mao|Chen|Si|Wu|Wei|Shen|You|Xu|Hai)$"
    )
    doc = _load_baseline()
    for case in doc["cases"]:
        pillars = case["output"]["pillars"]
        for slot in ("year", "month", "day", "hour"):
            value = pillars[slot]
            assert pat.match(value), (
                f"Case {case['id']}: malformed pillar {slot}={value!r}"
            )
