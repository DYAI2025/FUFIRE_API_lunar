from __future__ import annotations

import importlib.util
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "config" / "claude" / "lib" / "gate_contracts.py"
_spec = importlib.util.spec_from_file_location("gate_contracts", MODULE_PATH)
assert _spec is not None and _spec.loader is not None
gate_contracts = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gate_contracts)


def test_simple_roster_parser_preserves_hash_inside_quotes(tmp_path: Path) -> None:
    manifest = tmp_path / "roster.yml"
    manifest.write_text('agents:\n  - "agent #1" # trailing comment\n', encoding="utf-8")

    assert gate_contracts._load_simple_roster_manifest(manifest) == {"agents": ["agent #1"]}


def test_simple_roster_parser_removes_only_one_matching_quote_pair(tmp_path: Path) -> None:
    manifest = tmp_path / "roster.yml"
    manifest.write_text('agents:\n  - "\'quoted\'"\n', encoding="utf-8")

    assert gate_contracts._load_simple_roster_manifest(manifest) == {"agents": ["'quoted'"]}


def test_simple_roster_parser_error_mentions_pyyaml_for_richer_yaml(tmp_path: Path) -> None:
    manifest = tmp_path / "roster.yml"
    manifest.write_text("agents:\n  nested:\n    - role\n", encoding="utf-8")

    try:
        gate_contracts._load_simple_roster_manifest(manifest)
    except ValueError as exc:
        message = str(exc)
    else:  # pragma: no cover - defensive test clarity
        raise AssertionError("expected unsupported YAML to fail")

    assert "limited subset of roster YAML" in message
    assert "install PyYAML" in message
