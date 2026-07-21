"""Characterization: the composed app's route table must not change during
the Phase-3 extraction. Regenerate the golden ONLY for an intentional
endpoint change: python tests/golden/regen_route_table.py
"""
import json
from pathlib import Path

from fastapi.routing import APIRoute

from bazi_engine.app import app

GOLDEN = Path(__file__).parent / "golden" / "route_table.json"


# NOTE: keep build_route_table in sync with tests/golden/regen_route_table.py
# (the golden's regeneration script carries an identical copy). tests/ is not a
# package, so a shared import would be fragile; the columns pinned here and
# written there must match.
def build_route_table() -> list[list]:
    rows = []
    for r in app.routes:
        if isinstance(r, APIRoute):
            deps = {
                getattr(d.call, "__name__", type(d.call).__name__)
                for d in r.dependant.dependencies
                if d.call is not None
            }
            rows.append([r.path, sorted(r.methods), "require_api_key" in deps, r.include_in_schema])
    return sorted(rows)


def test_route_table_unchanged() -> None:
    assert json.loads(GOLDEN.read_text()) == build_route_table()
