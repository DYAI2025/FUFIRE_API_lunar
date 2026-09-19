"""FUF-158 AC #2: `uv lock --check` must be a fail-fast CI preflight.

`uv sync --frozen` / `uv export --frozen` install the committed lock
deterministically but never compare it against pyproject.toml, so a stale lock
stays green (that is exactly how FUF-158 went unnoticed for eight weeks). Only
`uv lock --check` proves freshness, and proving it *after* the lock has already
been installed proves nothing useful. This module pins the ordering contract:
the check is a top-level ci.yml job, and every job that consumes uv.lock — or
builds a Python/Docker artifact out of it — is blocked behind it.

Deliberately narrow to FUF-158. Two known, unrelated findings stay untouched
and stay red: the toolchain validator rejecting the local reusable-workflow
path (J.1), and MANDATORY_JOBS in tests/test_release_workflow_contract.py not
listing the aggregate jobs (J.2).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
CI_PATH = ROOT / ".github" / "workflows" / "ci.yml"
AUDIT_PATH = ROOT / ".github" / "workflows" / "audit-hardening.yml"

PREFLIGHT = "lock-freshness"

# Jobs that read uv.lock (uv sync/export) or build an artifact out of it. The
# Docker build runs `uv export --frozen --require-hashes` inside the image, so
# it consumes the lock even though ci.yml itself shows no uv invocation.
LOCK_CONSUMING_JOBS = (
    "test",
    "typecheck",
    "lint",
    "complexity",
    "security",
    "docker-build",
    "distribution",
    "audit-hardening",
)


def _jobs(path: Path) -> dict[str, Any]:
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(loaded, dict)
    jobs = loaded["jobs"]
    assert isinstance(jobs, dict)
    return jobs


def _needs(job: Any) -> list[str]:
    declared = job.get("needs") if isinstance(job, dict) else None
    if declared is None:
        return []
    return [declared] if isinstance(declared, str) else list(declared)


def _depends_on(jobs: dict[str, Any], start: str, target: str, seen: frozenset[str] = frozenset()) -> bool:
    """True when `start` cannot begin before `target` has succeeded."""
    if start in seen:
        return False
    for parent in _needs(jobs.get(start, {})):
        if parent == target or _depends_on(jobs, parent, target, seen | {start}):
            return True
    return False


def _job_text(job: Any) -> str:
    return yaml.safe_dump(job)


def test_lock_freshness_is_a_top_level_ci_job_running_uv_lock_check() -> None:
    job = _jobs(CI_PATH)[PREFLIGHT]
    text = _job_text(job)

    assert "uv lock --check" in text
    assert "uv==0.11.29" in text


def test_preflight_is_non_mutating_and_unblocked() -> None:
    job = _jobs(CI_PATH)[PREFLIGHT]
    text = _job_text(job)

    # A preflight that waits on another job is no longer fail-fast.
    assert _needs(job) == []
    # `uv lock --check` is read-only; any install/re-lock here would rewrite the
    # very file under test and turn the gate into a no-op.
    assert "uv sync" not in text
    assert "uv lock\n" not in text
    assert "--frozen" not in text


def test_every_lock_consuming_job_is_blocked_behind_the_preflight() -> None:
    jobs = _jobs(CI_PATH)

    ungated = [name for name in LOCK_CONSUMING_JOBS if not _depends_on(jobs, name, PREFLIGHT)]

    assert ungated == []


def test_contract_artifact_inherits_the_gate_transitively_through_test() -> None:
    jobs = _jobs(CI_PATH)

    assert "test" in _needs(jobs["contract-artifact"])
    assert _depends_on(jobs, "contract-artifact", PREFLIGHT)


def test_codegen_is_not_gated_because_it_never_reads_the_python_lock() -> None:
    jobs = _jobs(CI_PATH)
    text = _job_text(jobs["codegen"])

    # Guard the premise, not just the conclusion: if codegen ever starts
    # consuming uv.lock, this fails and forces the gate to be added.
    assert "uv " not in text
    assert "uv.lock" not in text
    assert not _depends_on(jobs, "codegen", PREFLIGHT)


def test_release_gate_fails_closed_on_the_preflight() -> None:
    gate = _jobs(CI_PATH)["release-gate"]

    assert PREFLIGHT in _needs(gate)
    step = gate["steps"][0]
    assert step["env"]["LOCK_FRESHNESS_RESULT"] == "${{ needs['lock-freshness'].result }}"
    # The aggregation collects every *_RESULT env var and fails on non-success.
    assert '_RESULT' in step["run"]
    assert 'result != "success"' in step["run"]


def test_reusable_audit_hardening_keeps_no_second_lock_freshness_gate() -> None:
    jobs = _jobs(AUDIT_PATH)

    assert PREFLIGHT not in jobs
    # Assert over the executable job graph, not the raw file: the file carries a
    # prose comment naming `uv lock --check` to stop the job being re-added here.
    assert "uv lock --check" not in yaml.safe_dump(jobs)
    assert PREFLIGHT not in _needs(jobs["audit-hardening-gate"])
    assert "needs.lock-freshness" not in _job_text(jobs["audit-hardening-gate"])
