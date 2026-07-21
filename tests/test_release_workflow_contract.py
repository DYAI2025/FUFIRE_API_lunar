from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
CI_PATH = ROOT / ".github" / "workflows" / "ci.yml"
MANDATORY_JOBS = {
    "test",
    "typecheck",
    "lint",
    "complexity",
    "security",
    "docker-build",
    "distribution",
    "codegen",
    "contract-artifact",
}


def _workflow() -> dict[str, object]:
    loaded = yaml.safe_load(CI_PATH.read_text(encoding="utf-8"))
    assert isinstance(loaded, dict)
    return loaded


def test_atomic_release_gate_transitively_requires_every_mandatory_job() -> None:
    gate = _workflow()["jobs"]["release-gate"]

    assert gate["name"] == "release-gate"
    assert gate["if"] == "always()"
    assert set(gate["needs"]) == MANDATORY_JOBS
    assert "result != \"success\"" in gate["steps"][0]["run"]


def test_ci_targets_only_the_canonical_main_branch() -> None:
    raw = CI_PATH.read_text(encoding="utf-8")

    assert "branches: [main]" in raw
    assert "branches: [master]" not in raw
