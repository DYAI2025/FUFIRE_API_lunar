"""Minimal fail-closed validation for the generated CycloneDX dependency SBOM."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

MINIMUM_COMPONENTS = {"fastapi", "pyswisseph", "redis", "uvicorn"}


def validate(path: Path) -> list[str]:
    if not path.is_file():
        return [f"missing SBOM: {path}"]
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"unreadable SBOM: {exc}"]

    errors: list[str] = []
    if document.get("bomFormat") != "CycloneDX":
        errors.append("SBOM bomFormat must be CycloneDX")
    if not str(document.get("specVersion", "")).startswith("1."):
        errors.append("SBOM specVersion must be a supported CycloneDX 1.x version")
    components = document.get("components")
    if not isinstance(components, list) or not components:
        errors.append("SBOM must contain dependency components")
        return errors

    names = {str(component.get("name", "")).lower() for component in components if isinstance(component, dict)}
    missing = sorted(MINIMUM_COMPONENTS - names)
    if missing:
        errors.append(f"SBOM is missing critical runtime components: {', '.join(missing)}")
    if any(not component.get("version") for component in components if isinstance(component, dict)):
        errors.append("every SBOM component must have a version")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path)
    args = parser.parse_args()
    errors = validate(args.path)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print(f"OK: valid CycloneDX SBOM at {args.path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
