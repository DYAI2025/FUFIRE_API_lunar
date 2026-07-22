"""Validate the immutable release-readiness baseline and execution plan."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

BASELINE_HEAD = "fe8f0198f6a4bda1568d986bf8aac06efe4e123c"
PLAN_PATH = Path("docs/plans/2026-07-21-fufire-api-lunar-release-readiness.md")
BASELINE_PATH = Path("evidence/release-readiness/baseline.json")
MANDATORY_BLOCKERS = tuple(
    [f"RB-{number:03d}" for number in range(1, 12)]
    + ["RB-012", "RB-013", "RB-014", "RB-015", "RB-016", "RB-017"]
)


def validate(root: Path) -> list[str]:
    """Return validation errors without mutating the repository."""
    errors: list[str] = []
    plan_path = root / PLAN_PATH
    baseline_path = root / BASELINE_PATH

    if not plan_path.is_file():
        errors.append(f"missing plan: {PLAN_PATH}")
    if not baseline_path.is_file():
        errors.append(f"missing baseline: {BASELINE_PATH}")
    if errors:
        return errors

    plan = plan_path.read_text(encoding="utf-8")
    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))

    if baseline.get("repository", {}).get("head_sha") != BASELINE_HEAD:
        errors.append("baseline repository head does not match the frozen live head")
    if baseline.get("release_decision") != "BLOCKED":
        errors.append("baseline release decision must remain BLOCKED")
    if "<!-- GOAL_START -->" not in plan or "<!-- GOAL_END -->" not in plan:
        errors.append("plan goal markers are missing")
    else:
        goal = plan.split("<!-- GOAL_START -->", 1)[1].split("<!-- GOAL_END -->", 1)[0]
        if len(goal) >= 4000:
            errors.append("plan goal exceeds the 4000-character gate")

    missing_ids = [blocker for blocker in MANDATORY_BLOCKERS if blocker not in plan]
    if missing_ids:
        errors.append(f"plan is missing blocker IDs: {', '.join(missing_ids)}")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    errors = validate(args.root.resolve())
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print(f"OK: baseline {BASELINE_HEAD} and release-readiness plan are valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
