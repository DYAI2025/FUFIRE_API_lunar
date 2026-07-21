"""FUFIRE-013 guard, updated for release-please (2026-07): pyproject.toml's
`version` is now release-please-owned (bumped automatically from Conventional
Commits on every release) and is an independent axis from
`bazi_engine.__version__` — the manually-curated engine-build label embedded
in API responses, the OpenAPI spec, and the golden snapshot fixtures. This
test no longer cross-checks the two (see DEV-2026-003 in
docs/precision/deviations.md for why that coupling was retired); it only
guards the pairing that's still a real invariant: the OpenAPI spec's
info.version must track __version__ (scripts/export_openapi.py derives it
from there, not from pyproject.toml).
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_openapi_spec_version_matches_engine_version() -> None:
    from bazi_engine import __version__

    spec = json.loads((ROOT / "spec/openapi/openapi.json").read_text())
    assert spec["info"]["version"] == __version__, (
        "spec/openapi/openapi.json info.version drifted from __version__ — "
        "run: python scripts/export_openapi.py"
    )
