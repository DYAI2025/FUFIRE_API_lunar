from __future__ import annotations

import importlib.util
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "assert_toolchain_versions.py"
SPEC = importlib.util.spec_from_file_location("assert_toolchain_versions", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
validator = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(validator)


def test_repository_toolchain_is_immutable() -> None:
    assert validator.validate(ROOT) == []


def test_validator_rejects_mutable_action_reference(tmp_path: Path) -> None:
    for filename in ("pyproject.toml", "uv.lock", "requirements.lock", "package.json", "package-lock.json"):
        shutil.copy2(ROOT / filename, tmp_path / filename)
    shutil.copy2(ROOT / "Dockerfile", tmp_path / "Dockerfile")
    shutil.copy2(ROOT / "Dockerfile.ephe-base", tmp_path / "Dockerfile.ephe-base")
    workflows = tmp_path / ".github" / "workflows"
    workflows.mkdir(parents=True)
    (workflows / "ci.yml").write_text(
        "jobs:\n  test:\n    steps:\n      - uses: actions/checkout@v7\n",
        encoding="utf-8",
    )

    errors = validator.validate(tmp_path)
    assert any("mutable action" in error for error in errors)


def test_node_lock_root_matches_package_manifest() -> None:
    package = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
    lock = json.loads((ROOT / "package-lock.json").read_text(encoding="utf-8"))
    assert lock["packages"][""]["devDependencies"] == package["devDependencies"]
