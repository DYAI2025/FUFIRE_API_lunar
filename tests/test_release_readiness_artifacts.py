from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "validate_release_readiness_artifacts.py"
SPEC = importlib.util.spec_from_file_location("validate_release_readiness_artifacts", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
validator = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(validator)


def test_committed_release_readiness_artifacts_validate() -> None:
    assert validator.validate(ROOT) == []


def test_validator_rejects_mutated_baseline_head(tmp_path: Path) -> None:
    plan = tmp_path / validator.PLAN_PATH
    plan.parent.mkdir(parents=True)
    plan.write_text((ROOT / validator.PLAN_PATH).read_text(encoding="utf-8"), encoding="utf-8")

    baseline = json.loads((ROOT / validator.BASELINE_PATH).read_text(encoding="utf-8"))
    baseline["repository"]["head_sha"] = "0" * 40
    baseline_path = tmp_path / validator.BASELINE_PATH
    baseline_path.parent.mkdir(parents=True)
    baseline_path.write_text(json.dumps(baseline), encoding="utf-8")

    assert "frozen live head" in " ".join(validator.validate(tmp_path))
