from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "validate_sbom.py"
SPEC = importlib.util.spec_from_file_location("validate_sbom", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
validator = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(validator)


def test_valid_cyclonedx_dependency_sbom(tmp_path: Path) -> None:
    path = tmp_path / "sbom.cdx.json"
    path.write_text(
        json.dumps(
            {
                "bomFormat": "CycloneDX",
                "specVersion": "1.6",
                "components": [
                    {"name": name, "version": "1.0.0"}
                    for name in sorted(validator.MINIMUM_COMPONENTS)
                ],
            }
        ),
        encoding="utf-8",
    )
    assert validator.validate(path) == []


def test_missing_sbom_fails_closed(tmp_path: Path) -> None:
    assert "missing SBOM" in validator.validate(tmp_path / "missing.json")[0]
