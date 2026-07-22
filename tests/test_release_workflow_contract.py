from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
CI_PATH = ROOT / ".github" / "workflows" / "ci.yml"
DEPENDABOT_PATH = ROOT / ".github" / "dependabot.yml"
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


def test_ci_covers_canonical_main_and_deployed_master_branches() -> None:
    raw = CI_PATH.read_text(encoding="utf-8")

    assert raw.count("branches: [main, master]") == 2


def test_docker_gate_executes_non_root_ephemeris_runtime_smoke() -> None:
    docker_job = _workflow()["jobs"]["docker-build"]
    steps = docker_job["steps"]
    build_step = next(step for step in steps if step.get("uses", "").startswith("docker/build-push-action@"))
    runtime_step = next(step for step in steps if step.get("name", "").startswith("Verify non-root runtime"))

    assert build_step["with"]["load"] is True
    assert "os.getuid() == 10001" in runtime_step["run"]
    assert "path.read_bytes()" in runtime_step["run"]
    assert "hashlib.sha256(data).hexdigest()" in runtime_step["run"]


def test_dependabot_titles_follow_semantic_pr_policy() -> None:
    config = yaml.safe_load(DEPENDABOT_PATH.read_text(encoding="utf-8"))

    assert config["updates"]
    for update in config["updates"]:
        assert update["commit-message"] == {"prefix": "chore", "include": "scope"}
