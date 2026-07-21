"""Regenerate tests/golden/route_table.json.

Run ONLY for an intentional endpoint change:

    python tests/golden/regen_route_table.py
"""
import json
from pathlib import Path

from fastapi.routing import APIRoute

from bazi_engine.app import app

GOLDEN = Path(__file__).parent / "route_table.json"


# NOTE: keep build_route_table in sync with tests/test_app_composition.py
# (the characterization test carries an identical copy). See the note there.
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


if __name__ == "__main__":
    GOLDEN.write_text(json.dumps(build_route_table(), indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {GOLDEN} ({len(build_route_table())} routes)")
