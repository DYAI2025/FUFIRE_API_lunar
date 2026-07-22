from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "validate_live_production_gates.py"
SPEC = importlib.util.spec_from_file_location("validate_live_production_gates", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
validator = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(validator)


def _copy_gate_fixture(tmp_path: Path) -> dict:
    plan_path = tmp_path / validator.PLAN_PATH
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    plan_path.write_text((ROOT / validator.PLAN_PATH).read_text(encoding="utf-8"), encoding="utf-8")

    document = json.loads((ROOT / validator.GATES_PATH).read_text(encoding="utf-8"))
    gate_path = tmp_path / validator.GATES_PATH
    gate_path.parent.mkdir(parents=True, exist_ok=True)
    gate_path.write_text(json.dumps(document, indent=2), encoding="utf-8")
    return document


def _write_gate_fixture(tmp_path: Path, document: dict) -> None:
    (tmp_path / validator.GATES_PATH).write_text(json.dumps(document, indent=2), encoding="utf-8")


def test_committed_live_production_gate_state_is_coherent_and_blocked() -> None:
    assert validator.validate(ROOT) == []
    blockers = validator.release_blockers(ROOT)
    assert "LR-001" in blockers
    assert "LR-022" in blockers
    assert "LR-021" not in blockers


def test_validator_rejects_release_while_mandatory_gates_are_open(tmp_path: Path) -> None:
    document = _copy_gate_fixture(tmp_path)
    document["release_decision"] = "RELEASE"
    _write_gate_fixture(tmp_path, document)

    errors = validator.validate(tmp_path)

    assert any("RELEASE is invalid" in error for error in errors)


def test_validator_rejects_closed_gate_with_missing_items(tmp_path: Path) -> None:
    document = _copy_gate_fixture(tmp_path)
    gate = next(item for item in document["gates"] if item["id"] == "LR-001")
    gate["status"] = "CLOSED"
    _write_gate_fixture(tmp_path, document)

    errors = validator.validate(tmp_path)

    assert any("LR-001: CLOSED gate cannot retain missing items" in error for error in errors)


def test_validator_rejects_duplicate_gate_ids(tmp_path: Path) -> None:
    document = _copy_gate_fixture(tmp_path)
    document["gates"].append(dict(document["gates"][0]))
    _write_gate_fixture(tmp_path, document)

    errors = validator.validate(tmp_path)

    assert any("duplicate gate id: LR-001" in error for error in errors)


def test_validator_rejects_secret_like_fields(tmp_path: Path) -> None:
    document = _copy_gate_fixture(tmp_path)
    document["release_token"] = "must-never-be-committed"
    _write_gate_fixture(tmp_path, document)

    errors = validator.validate(tmp_path)

    assert any("secret-like fields are forbidden" in error for error in errors)


def test_release_mode_stays_fail_closed_for_committed_state() -> None:
    assert validator.release_blockers(ROOT)
