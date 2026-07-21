from __future__ import annotations

import argparse
import json

from scripts.resume_point import cmd_resume_point, latest_status_by_gate, next_resume_gate


def test_resume_point_uses_canonical_gate_list_for_missing_mandatory_gate() -> None:
    rows = [
        {"gate": "phase0", "status": "CLEARED"},
        {"gate": "gateA_verification", "status": "PENDING"},
    ]

    assert next_resume_gate(rows) == "phase0_5_spec_sanity"


def test_resume_point_returns_first_uncleared_canonical_gate() -> None:
    rows = [
        {"gate": "phase0", "status": "CLEARED"},
        {"gate": "phase0_5_spec_sanity", "status": "CLEARED"},
        {"gate": "gateA_verification", "status": "PENDING"},
    ]

    assert next_resume_gate(rows) == "gateA_verification"


def test_cmd_resume_point_prints_missing_canonical_gate(tmp_path, capsys) -> None:
    ledger = tmp_path / "ledger.json"
    ledger.write_text(
        json.dumps([
            {"gate": "phase0", "status": "CLEARED"},
            {"gate": "gateA_verification", "status": "PENDING"},
        ]),
        encoding="utf-8",
    )

    assert cmd_resume_point(argparse.Namespace(ledger=str(ledger))) == 0
    assert capsys.readouterr().out == "phase0_5_spec_sanity\n"


def test_latest_status_by_gate_keeps_latest_status_and_first_seen_order() -> None:
    rows = [
        {"gate": "phase0", "status": "PENDING"},
        {"gate": "gateA_verification", "status": "PENDING"},
        {"gate": "phase0", "status": "CLEARED"},
    ]

    assert latest_status_by_gate(rows) == {
        "phase0": "CLEARED",
        "gateA_verification": "PENDING",
    }
