#!/usr/bin/env python3
"""Clean-install smoke for wheel/sdist execution outside the checkout."""

from __future__ import annotations

import json
from pathlib import Path


def main() -> int:
    from bazi_engine import __version__
    from bazi_engine.app import app
    from bazi_engine.bafe.ruleset_loader import load_ruleset as load_bazi_ruleset
    from bazi_engine.resource_loader import load_json_object_resource
    from bazi_engine.services.quiz_affinity import resolve_quiz_sectors
    from bazi_engine.zwds.ruleset_repository import load_ruleset as load_zwds_ruleset

    if (Path.cwd() / "bazi_engine").exists():
        raise SystemExit("distribution smoke must run outside a source checkout")

    request_schema = load_json_object_resource(
        "bazi_engine.resources", "schemas", "ValidateRequest.schema.json"
    )
    zwds_schema = load_json_object_resource(
        "bazi_engine.resources",
        "schemas",
        "zwds",
        "ZwdsRequest.schema.json",
    )
    bazi_ruleset = load_bazi_ruleset("standard_bazi_2026")
    zwds_ruleset = load_zwds_ruleset("zwds.fufire.core-seed.v1")
    affinity = resolve_quiz_sectors("expression")
    app.openapi_schema = None
    openapi = app.openapi()

    checks = {
        "version": __version__,
        "validate_schema": request_schema.get("title"),
        "zwds_schema": zwds_schema.get("title"),
        "bazi_ruleset": bazi_ruleset.get("ruleset_id"),
        "zwds_ruleset": zwds_ruleset.ruleset_id,
        "affinity_sectors": len(affinity),
        "openapi_paths": len(openapi.get("paths", {})),
    }
    if checks["affinity_sectors"] != 12 or not checks["openapi_paths"]:
        raise SystemExit(f"distribution smoke failed: {checks}")
    print(json.dumps(checks, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
