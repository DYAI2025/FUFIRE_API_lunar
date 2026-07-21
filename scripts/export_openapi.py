#!/usr/bin/env python3
"""Export the current OpenAPI spec from the FastAPI app to spec/openapi/.

Usage:
    python scripts/export_openapi.py          # write JSON
    python scripts/export_openapi.py --check  # CI mode: fail if spec drifted
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC_PATH = ROOT / "spec" / "openapi" / "openapi.json"


def _load_json_reject_duplicates(raw: str) -> None:
    """Parse JSON and raise on duplicate object keys.

    Python's default ``json.loads`` silently accepts duplicate keys and keeps
    only the last value, which can mask OpenAPI path collisions.
    """

    def _no_dupes(pairs: list[tuple[str, object]]) -> dict[str, object]:
        out: dict[str, object] = {}
        for key, value in pairs:
            if key in out:
                raise ValueError(f"Duplicate JSON key: {key}")
            out[key] = value
        return out

    json.loads(raw, object_pairs_hook=_no_dupes)


def _current_spec_json() -> str:
    # Inline import so the script works without activated venv in PATH
    sys.path.insert(0, str(ROOT))
    from bazi_engine.app import app
    return json.dumps(app.openapi(), indent=2, ensure_ascii=False) + "\n"


def main() -> None:
    check_mode = "--check" in sys.argv
    fresh = _current_spec_json()
    _load_json_reject_duplicates(fresh)

    if check_mode:
        if not SPEC_PATH.exists():
            print(f"FAIL: {SPEC_PATH} does not exist. Run: python scripts/export_openapi.py")
            sys.exit(1)
        existing = SPEC_PATH.read_text(encoding="utf-8")
        try:
            _load_json_reject_duplicates(existing)
        except ValueError as exc:
            print(f"FAIL: OpenAPI spec contains duplicate keys. {exc}")
            sys.exit(1)
        if existing != fresh:
            print("FAIL: OpenAPI spec drifted. Run: python scripts/export_openapi.py")
            sys.exit(1)
        print("OK: OpenAPI spec is up-to-date.")
    else:
        SPEC_PATH.parent.mkdir(parents=True, exist_ok=True)
        SPEC_PATH.write_text(fresh, encoding="utf-8")
        print(f"Written: {SPEC_PATH}")


if __name__ == "__main__":
    main()
