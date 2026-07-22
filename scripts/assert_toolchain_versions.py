"""Fail closed when release-critical build inputs are mutable or unpinned."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python 3.10 compatibility
    import tomli as tomllib


ACTION_SHA = re.compile(r"^[^@\s]+@[0-9a-f]{40}$")
DOCKER_ACTION_DIGEST = re.compile(r"^docker://[^@\s]+@sha256:[0-9a-f]{64}$")
IMAGE_DIGEST = re.compile(r"^[^\s]+@sha256:[0-9a-f]{64}$")
EXACT_REQUIREMENT = re.compile(r"^[A-Za-z0-9_.-]+(?:\[[^]]+\])?==[^;\s]+(?:;.+)?$")

EXPECTED_TOOLCHAIN = {
    "python": "3.12",
    "pip": "26.1.2",
    "uv": "0.11.29",
    "node": "22.21.1",
    "@redocly/cli": "2.40.0",
    "typescript": "7.0.2",
}


def _workflow_errors(root: Path) -> list[str]:
    errors: list[str] = []
    workflows = sorted((root / ".github" / "workflows").glob("*.y*ml"))
    if not workflows:
        return ["no GitHub workflows found"]

    combined = ""
    for workflow in workflows:
        raw = workflow.read_text(encoding="utf-8")
        combined += raw
        for line_number, line in enumerate(raw.splitlines(), 1):
            match = re.search(r"\buses:\s*([^\s#]+)", line)
            if not match:
                continue
            reference = match.group(1)
            valid = (
                DOCKER_ACTION_DIGEST.fullmatch(reference)
                if reference.startswith("docker://")
                else ACTION_SHA.fullmatch(reference)
            )
            if not valid:
                errors.append(f"{workflow.relative_to(root)}:{line_number}: mutable action {reference}")

    forbidden = {
        "pip install --upgrade": "pip self-upgrade",
        "npx -y": "network-resolving npx invocation",
        "npm install ": "non-locking npm install",
    }
    for needle, label in forbidden.items():
        if needle in combined:
            errors.append(f"workflows contain {label}: {needle!r}")

    for tool, version in (("pip", EXPECTED_TOOLCHAIN["pip"]), ("uv", EXPECTED_TOOLCHAIN["uv"])):
        if f"{tool}=={version}" not in combined:
            errors.append(f"workflows do not install approved {tool}=={version}")
    if f'node-version: "{EXPECTED_TOOLCHAIN["node"]}"' not in combined:
        errors.append("codegen does not select the approved exact Node version")
    if "npm ci --ignore-scripts" not in combined:
        errors.append("codegen does not use the npm lockfile with scripts disabled")
    if "uv sync --frozen" not in combined:
        errors.append("Python CI does not enforce uv.lock with --frozen")
    if "uv export --frozen" not in combined or "--require-hashes" not in combined:
        errors.append("distribution CI does not install a hash-locked uv export")
    return errors


def _docker_errors(root: Path) -> list[str]:
    errors: list[str] = []
    for dockerfile in (root / "Dockerfile", root / "Dockerfile.ephe-base"):
        if not dockerfile.is_file():
            errors.append(f"missing container definition: {dockerfile.name}")
            continue
        for line_number, line in enumerate(dockerfile.read_text(encoding="utf-8").splitlines(), 1):
            if not line.startswith("FROM "):
                continue
            image = line.split()[1]
            if not IMAGE_DIGEST.fullmatch(image):
                errors.append(f"{dockerfile.name}:{line_number}: mutable base image {image}")
            if dockerfile.name == "Dockerfile" and image.startswith("python:"):
                approved_prefix = f"python:{EXPECTED_TOOLCHAIN['python']}-slim@sha256:"
                if not image.startswith(approved_prefix):
                    errors.append(
                        f"Dockerfile:{line_number}: unapproved Python base {image}; "
                        f"expected Python {EXPECTED_TOOLCHAIN['python']}-slim with digest"
                    )
        if dockerfile.name == "Dockerfile":
            raw = dockerfile.read_text(encoding="utf-8")
            if "uv export" not in raw or "--frozen" not in raw or "--require-hashes" not in raw:
                errors.append("Dockerfile must install the frozen uv export with hash enforcement")
            if "--ignore-installed" not in raw:
                errors.append("Dockerfile must isolate the runtime prefix from builder packages")
            for build_input in (
                "build==1.3.0",
                "packaging==26.0",
                "pyproject-hooks==1.2.0",
            ):
                if build_input not in raw:
                    errors.append(f"Dockerfile does not pin {build_input}")
            if "pip install --no-cache-dir --no-deps" not in raw:
                errors.append("Dockerfile builder bootstrap may resolve mutable dependencies")
    return errors


def _python_lock_errors(root: Path) -> list[str]:
    errors: list[str] = []
    pyproject_path = root / "pyproject.toml"
    uv_lock_path = root / "uv.lock"
    requirements_path = root / "requirements.lock"
    if not pyproject_path.is_file() or not uv_lock_path.is_file() or not requirements_path.is_file():
        return ["pyproject.toml, uv.lock, and requirements.lock are all mandatory"]

    pyproject = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
    dev_requirements = pyproject["project"]["optional-dependencies"]["dev"]
    for requirement in dev_requirements:
        compact = requirement.replace(" ", "")
        if not EXACT_REQUIREMENT.fullmatch(compact):
            errors.append(f"dev tool is not exact-pinned: {requirement}")

    for line_number, line in enumerate(requirements_path.read_text(encoding="utf-8").splitlines(), 1):
        stripped = line.strip().replace(" ", "")
        if stripped and not stripped.startswith("#") and not EXACT_REQUIREMENT.fullmatch(stripped):
            errors.append(f"requirements.lock:{line_number}: non-exact requirement {line.strip()}")

    lock_text = uv_lock_path.read_text(encoding="utf-8")
    if "revision = 3" not in lock_text:
        errors.append("uv.lock is not the expected revision-3 lock format")
    return errors


def _node_lock_errors(root: Path) -> list[str]:
    errors: list[str] = []
    package_path = root / "package.json"
    lock_path = root / "package-lock.json"
    if not package_path.is_file() or not lock_path.is_file():
        return ["package.json and package-lock.json are mandatory"]

    package = json.loads(package_path.read_text(encoding="utf-8"))
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    if package.get("engines", {}).get("node") != EXPECTED_TOOLCHAIN["node"]:
        errors.append("package.json has an unapproved Node version")
    for name in ("@redocly/cli", "typescript"):
        actual = package.get("devDependencies", {}).get(name)
        if actual != EXPECTED_TOOLCHAIN[name]:
            errors.append(f"package.json must pin {name}=={EXPECTED_TOOLCHAIN[name]}, found {actual!r}")

    root_lock = lock.get("packages", {}).get("", {})
    if root_lock.get("devDependencies") != package.get("devDependencies"):
        errors.append("package-lock.json root dependencies drift from package.json")
    if root_lock.get("engines") != package.get("engines"):
        errors.append("package-lock.json Node engine drifts from package.json")
    return errors


def validate(root: Path) -> list[str]:
    """Return every pinning violation without mutating the repository."""
    return [
        *_workflow_errors(root),
        *_docker_errors(root),
        *_python_lock_errors(root),
        *_node_lock_errors(root),
    ]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    errors = validate(args.root.resolve())
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print("OK: release toolchain, actions, locks, and container bases are immutable")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
