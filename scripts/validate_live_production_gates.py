"""Validate the Lunar V2 live-production dependency and release-gate state.

The validator is intentionally evidence-neutral: a coherent BLOCKED state passes
normal validation, while ``--require-release`` fails until every mandatory P0
gate is closed with evidence. It never contacts external systems and never
accepts secret material as evidence.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

GATES_PATH = Path("evidence/release-readiness/live-production-gates.json")
PLAN_PATH = Path("docs/plans/2026-07-22-lunar-v2-live-production-readiness.md")
SCHEMA_VERSION = "fufire.live-production-gates.v1"
ALLOWED_STATUSES = {"CLOSED", "PARTIAL", "MISSING", "BLOCKED"}
ALLOWED_EVIDENCE_CLASSES = {
    "fake-only",
    "unit-only",
    "integration",
    "real-boundary-smoke",
    "browser-live",
    "production-observed",
    "user-confirmed",
}
MANDATORY_GATE_IDS = tuple(
    [f"LR-{number:03d}" for number in range(1, 21)] + ["LR-022"]
)
TASK_IDS = tuple(f"TASK-{number:03d}" for number in range(1, 22))
SECRET_KEY_PATTERN = re.compile(
    r"(?:^|_)(?:secret|token|password|api[_-]?key|private[_-]?key|credential)(?:$|_)",
    re.IGNORECASE,
)
SHA40_PATTERN = re.compile(r"^[0-9a-f]{40}$")


def _load_json(path: Path, errors: list[str]) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"cannot load {path}: {exc}")
        return {}
    if not isinstance(value, dict):
        errors.append(f"{path} must contain a JSON object")
        return {}
    return value


def _find_secret_keys(value: Any, prefix: str = "$") -> list[str]:
    findings: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            key_text = str(key)
            child_prefix = f"{prefix}.{key_text}"
            if SECRET_KEY_PATTERN.search(key_text):
                findings.append(child_prefix)
            findings.extend(_find_secret_keys(child, child_prefix))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            findings.extend(_find_secret_keys(child, f"{prefix}[{index}]"))
    return findings


def _gate_index(document: dict[str, Any], errors: list[str]) -> dict[str, dict[str, Any]]:
    raw_gates = document.get("gates")
    if not isinstance(raw_gates, list):
        errors.append("gates must be a list")
        return {}

    indexed: dict[str, dict[str, Any]] = {}
    for index, raw_gate in enumerate(raw_gates):
        if not isinstance(raw_gate, dict):
            errors.append(f"gates[{index}] must be an object")
            continue
        gate_id = raw_gate.get("id")
        if not isinstance(gate_id, str) or not gate_id:
            errors.append(f"gates[{index}] has no valid id")
            continue
        if gate_id in indexed:
            errors.append(f"duplicate gate id: {gate_id}")
            continue
        indexed[gate_id] = raw_gate
    return indexed


def _validate_gate(gate_id: str, gate: dict[str, Any], errors: list[str]) -> None:
    status = gate.get("status")
    evidence_class = gate.get("evidence_class")
    evidence = gate.get("evidence")
    missing = gate.get("missing")
    owner = gate.get("owner")

    if status not in ALLOWED_STATUSES:
        errors.append(f"{gate_id}: invalid status {status!r}")
    if evidence_class not in ALLOWED_EVIDENCE_CLASSES:
        errors.append(f"{gate_id}: invalid evidence_class {evidence_class!r}")
    if not isinstance(owner, str) or not owner.strip():
        errors.append(f"{gate_id}: owner is required")
    if not isinstance(evidence, list) or not all(isinstance(item, str) and item for item in evidence):
        errors.append(f"{gate_id}: evidence must be a list of non-empty strings")
    if not isinstance(missing, list) or not all(isinstance(item, str) and item for item in missing):
        errors.append(f"{gate_id}: missing must be a list of non-empty strings")

    if status == "CLOSED":
        if not evidence:
            errors.append(f"{gate_id}: CLOSED gate requires evidence")
        if missing:
            errors.append(f"{gate_id}: CLOSED gate cannot retain missing items")
    elif status in {"PARTIAL", "MISSING", "BLOCKED"} and isinstance(missing, list) and not missing:
        errors.append(f"{gate_id}: {status} gate must name at least one missing item")


def _validate_branch_identity(document: dict[str, Any], errors: list[str]) -> None:
    repositories = document.get("repositories")
    if not isinstance(repositories, dict):
        errors.append("repositories must be an object")
        return
    engine = repositories.get("engine")
    if not isinstance(engine, dict):
        errors.append("repositories.engine must be an object")
        return

    main_sha = engine.get("main_sha")
    master_sha = engine.get("master_sha")
    if not isinstance(main_sha, str) or not SHA40_PATTERN.fullmatch(main_sha):
        errors.append("repositories.engine.main_sha must be a lowercase 40-character SHA")
    if not isinstance(master_sha, str) or not SHA40_PATTERN.fullmatch(master_sha):
        errors.append("repositories.engine.master_sha must be a lowercase 40-character SHA")

    if engine.get("content_converged") is True and main_sha != master_sha:
        errors.append("content_converged=true requires identical main_sha and master_sha")
    if engine.get("github_default_branch") not in {"main", "master"}:
        errors.append("repositories.engine.github_default_branch must be main or master")
    if engine.get("intended_canonical_branch") != "main":
        errors.append("repositories.engine.intended_canonical_branch must remain main")


def validate(root: Path) -> list[str]:
    """Return structural and fail-closed consistency errors."""
    errors: list[str] = []
    gates_path = root / GATES_PATH
    plan_path = root / PLAN_PATH

    if not gates_path.is_file():
        errors.append(f"missing gate state: {GATES_PATH}")
    if not plan_path.is_file():
        errors.append(f"missing execution plan: {PLAN_PATH}")
    if errors:
        return errors

    document = _load_json(gates_path, errors)
    if not document:
        return errors

    if document.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"schema_version must be {SCHEMA_VERSION}")
    if document.get("release_decision") not in {"BLOCKED", "RELEASE"}:
        errors.append("release_decision must be BLOCKED or RELEASE")

    secret_keys = _find_secret_keys(document)
    if secret_keys:
        errors.append("secret-like fields are forbidden: " + ", ".join(secret_keys))

    _validate_branch_identity(document, errors)
    gates = _gate_index(document, errors)
    for gate_id, gate in gates.items():
        _validate_gate(gate_id, gate, errors)

    missing_gate_ids = [gate_id for gate_id in MANDATORY_GATE_IDS if gate_id not in gates]
    if missing_gate_ids:
        errors.append("missing mandatory gate IDs: " + ", ".join(missing_gate_ids))

    non_closed = [
        gate_id
        for gate_id in MANDATORY_GATE_IDS
        if gate_id in gates and gates[gate_id].get("status") != "CLOSED"
    ]
    decision = document.get("release_decision")
    if decision == "RELEASE" and non_closed:
        errors.append("RELEASE is invalid while mandatory gates are not CLOSED: " + ", ".join(non_closed))
    if decision == "BLOCKED" and not non_closed:
        errors.append("BLOCKED is inconsistent because every mandatory gate is CLOSED")

    try:
        plan = plan_path.read_text(encoding="utf-8")
    except OSError as exc:
        errors.append(f"cannot load {PLAN_PATH}: {exc}")
        return errors

    if "<!-- GOAL_START -->" not in plan or "<!-- GOAL_END -->" not in plan:
        errors.append("execution plan goal markers are missing")
    else:
        goal = plan.split("<!-- GOAL_START -->", 1)[1].split("<!-- GOAL_END -->", 1)[0]
        if len(goal) >= 4000:
            errors.append("execution plan goal exceeds the 4000-character gate")

    absent_tasks = [task_id for task_id in TASK_IDS if task_id not in plan]
    if absent_tasks:
        errors.append("execution plan is missing task IDs: " + ", ".join(absent_tasks))
    absent_plan_gates = [gate_id for gate_id in MANDATORY_GATE_IDS if gate_id not in plan]
    if absent_plan_gates:
        errors.append("execution plan is missing mandatory gate IDs: " + ", ".join(absent_plan_gates))

    return errors


def release_blockers(root: Path) -> list[str]:
    """Return mandatory gate IDs that still block a production release."""
    errors: list[str] = []
    document = _load_json(root / GATES_PATH, errors)
    if errors:
        return ["GATE_STATE_INVALID"]
    gates = _gate_index(document, errors)
    if errors:
        return ["GATE_STATE_INVALID"]
    return [
        gate_id
        for gate_id in MANDATORY_GATE_IDS
        if gate_id not in gates or gates[gate_id].get("status") != "CLOSED"
    ]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--require-release",
        action="store_true",
        help="Fail unless the gate state is valid, marked RELEASE, and every mandatory gate is CLOSED.",
    )
    args = parser.parse_args()
    root = args.root.resolve()

    errors = validate(root)
    for error in errors:
        print(f"ERROR: {error}")
    if errors:
        return 1

    blockers = release_blockers(root)
    document = json.loads((root / GATES_PATH).read_text(encoding="utf-8"))
    if args.require_release and (document.get("release_decision") != "RELEASE" or blockers):
        print("BLOCKED: mandatory live-production gates are not closed: " + ", ".join(blockers))
        return 1

    if blockers:
        print("OK: fail-closed gate state is coherent; release remains BLOCKED by " + ", ".join(blockers))
    else:
        print("OK: every mandatory live-production gate is CLOSED and the gate state is coherent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
