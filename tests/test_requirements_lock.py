from __future__ import annotations

import re
import sys
from pathlib import Path

if sys.version_info >= (3, 11):
    import tomllib
else:
    try:
        import tomllib
    except ImportError:
        import tomli as tomllib  # type: ignore[no-redef]


def _normalize_name(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def _dependency_name(spec: str) -> str:
    match = re.match(r"\s*([A-Za-z0-9_.-]+)", spec)
    if not match:
        raise AssertionError(f"Could not parse dependency name from: {spec!r}")
    return _normalize_name(match.group(1))


def _locked_name(spec: str) -> str:
    match = re.match(r"\s*([A-Za-z0-9_.-]+)(?:\[[A-Za-z0-9_.,-]+\])?==", spec)
    if not match:
        raise AssertionError(f"Could not parse locked package name from: {spec!r}")
    return _normalize_name(match.group(1))


def test_requirements_lock_covers_all_runtime_dependencies() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    pyproject = tomllib.loads((repo_root / "pyproject.toml").read_text())

    direct_dependencies = {
        _dependency_name(spec)
        for spec in pyproject["project"]["dependencies"]
    }

    locked_dependencies = {
        _locked_name(line)
        for line in (repo_root / "requirements.lock").read_text().splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }

    missing = sorted(direct_dependencies - locked_dependencies)
    assert not missing, (
        "requirements.lock is missing runtime dependencies declared in "
        f"pyproject.toml: {missing}"
    )
