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


def _fixture_repo(tmp_path: Path, workflow_body: str) -> Path:
    """Minimal repo copy whose ONLY intended defect is `workflow_body`."""
    for filename in ("pyproject.toml", "uv.lock", "requirements.lock", "package.json", "package-lock.json"):
        shutil.copy2(ROOT / filename, tmp_path / filename)
    shutil.copy2(ROOT / "Dockerfile", tmp_path / "Dockerfile")
    shutil.copy2(ROOT / "Dockerfile.ephe-base", tmp_path / "Dockerfile.ephe-base")
    workflows = tmp_path / ".github" / "workflows"
    workflows.mkdir(parents=True)
    (workflows / "ci.yml").write_text(workflow_body, encoding="utf-8")
    return tmp_path


def test_validator_accepts_local_reusable_workflow_reference(tmp_path: Path) -> None:
    """`uses: ./.github/workflows/x.yml` is pinned by the commit under review.

    It resolves out of the same tree the validator is checking and cannot carry
    an `@ref`, so reading it as a mutable third-party action was a false
    positive that blocked lint, test and audit-hardening/moseph-no-se1 alike.
    """
    root = _fixture_repo(
        tmp_path,
        "jobs:\n  gates:\n    uses: ./.github/workflows/audit-hardening.yml\n",
    )

    errors = [error for error in validator.validate(root) if "mutable action" in error]
    assert errors == [], errors


def test_validator_still_rejects_non_local_and_traversing_uses_references(tmp_path: Path) -> None:
    """Canary for the carve-out above: it must not become a blanket bypass."""
    root = _fixture_repo(
        tmp_path,
        "jobs:\n"
        "  a:\n    uses: ./../evil/.github/workflows/x.yml\n"
        "  b:\n    uses: ./.github/workflows/x.yml@main\n"
        "  c:\n    uses: ./scripts/not-a-workflow.sh\n"
        "  d:\n    uses: other/repo/.github/workflows/x.yml@main\n",
    )

    flagged = {
        error.rsplit("mutable action ", 1)[1]
        for error in validator.validate(root)
        if "mutable action" in error
    }
    assert flagged == {
        "./../evil/.github/workflows/x.yml",
        "./.github/workflows/x.yml@main",
        "./scripts/not-a-workflow.sh",
        "other/repo/.github/workflows/x.yml@main",
    }, flagged


def test_validator_rejects_unapproved_python_runtime_even_when_digest_pinned(
    tmp_path: Path,
) -> None:
    for filename in ("pyproject.toml", "uv.lock", "requirements.lock", "package.json", "package-lock.json"):
        shutil.copy2(ROOT / filename, tmp_path / filename)
    dockerfile = (
        (ROOT / "Dockerfile")
        .read_text(encoding="utf-8")
        .replace(
            "python:3.12-slim@sha256:",
            "python:3.14-slim@sha256:",
        )
    )
    (tmp_path / "Dockerfile").write_text(dockerfile, encoding="utf-8")
    shutil.copy2(ROOT / "Dockerfile.ephe-base", tmp_path / "Dockerfile.ephe-base")
    workflows = tmp_path / ".github" / "workflows"
    shutil.copytree(ROOT / ".github" / "workflows", workflows)

    errors = validator.validate(tmp_path)
    assert any("unapproved Python base" in error for error in errors)


def test_validator_rejects_docker_build_backend_drift(tmp_path: Path) -> None:
    for filename in ("pyproject.toml", "uv.lock", "requirements.lock", "package.json", "package-lock.json"):
        shutil.copy2(ROOT / filename, tmp_path / filename)
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8").replace("wheel==0.47.0", "wheel==0.45.1")
    (tmp_path / "Dockerfile").write_text(dockerfile, encoding="utf-8")
    shutil.copy2(ROOT / "Dockerfile.ephe-base", tmp_path / "Dockerfile.ephe-base")
    workflows = tmp_path / ".github" / "workflows"
    shutil.copytree(ROOT / ".github" / "workflows", workflows)

    errors = validator.validate(tmp_path)
    assert any("Dockerfile build frontend drifts" in error for error in errors)


def test_validator_rejects_ci_build_backend_drift(tmp_path: Path) -> None:
    for filename in ("pyproject.toml", "uv.lock", "requirements.lock", "package.json", "package-lock.json"):
        shutil.copy2(ROOT / filename, tmp_path / filename)
    shutil.copy2(ROOT / "Dockerfile", tmp_path / "Dockerfile")
    shutil.copy2(ROOT / "Dockerfile.ephe-base", tmp_path / "Dockerfile.ephe-base")
    workflows = tmp_path / ".github" / "workflows"
    shutil.copytree(ROOT / ".github" / "workflows", workflows)
    ci_path = workflows / "ci.yml"
    ci_path.write_text(
        ci_path.read_text(encoding="utf-8").replace("wheel==0.47.0", "wheel==0.45.1", 1),
        encoding="utf-8",
    )

    errors = validator.validate(tmp_path)
    assert any("build bootstrap drifts from pyproject" in error and "wheel==0.47.0" in error for error in errors)


def test_node_lock_root_matches_package_manifest() -> None:
    package = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
    lock = json.loads((ROOT / "package-lock.json").read_text(encoding="utf-8"))
    assert lock["packages"][""]["devDependencies"] == package["devDependencies"]
