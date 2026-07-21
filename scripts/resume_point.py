#!/usr/bin/env python3
"""Resolve the next mandatory gate from a status ledger.

The resume-point command intentionally walks the canonical gate contract,
not just the gates already present in the ledger.  This prevents reruns from
skipping a mandatory phase that has not emitted a ledger row yet.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

CLEARED_STATUS = "CLEARED"

# Canonical release-gate order.  Resume-point must consult this list before
# falling back to ad-hoc ledger rows so missing mandatory phases are detected.
CANONICAL_GATES: tuple[str, ...] = (
    "phase0",
    "phase0_5_spec_sanity",
    "gateA_verification",
)

Row = Mapping[str, Any]


def _row_gate(row: Row) -> str:
    gate = row.get("gate") or row.get("gate_id") or row.get("name")
    if not isinstance(gate, str) or not gate:
        raise ValueError(f"ledger row has no gate: {row!r}")
    return gate


def _row_status(row: Row) -> str:
    status = row.get("status")
    if not isinstance(status, str) or not status:
        raise ValueError(f"ledger row has no status: {row!r}")
    return status


def latest_status_by_gate(rows: Iterable[Row]) -> dict[str, str]:
    """Return each gate's latest status, preserving first-seen gate order."""
    latest: dict[str, str] = {}
    for row in rows:
        latest[_row_gate(row)] = _row_status(row)
    return latest


def next_resume_gate(
    rows: Iterable[Row],
    *,
    canonical_gates: Sequence[str] = CANONICAL_GATES,
    cleared_status: str = CLEARED_STATUS,
) -> str | None:
    """Return the first gate that must still run.

    Mandatory gates are evaluated in canonical order.  A missing canonical row
    is treated as not cleared, which is the key distinction from iterating only
    over ``latest_status_by_gate(rows)``.  Non-canonical ledger rows are still
    considered afterwards for backwards-compatible extension gates.
    """
    latest = latest_status_by_gate(rows)
    for gate in canonical_gates:
        if latest.get(gate) != cleared_status:
            return gate

    canonical = set(canonical_gates)
    for gate, status in latest.items():
        if gate not in canonical and status != cleared_status:
            return gate
    return None


def _read_json_or_jsonl(path: Path) -> list[Row]:
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return []
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return [json.loads(line) for line in text.splitlines() if line.strip()]

    if isinstance(data, list):
        return data
    if isinstance(data, dict) and isinstance(data.get("rows"), list):
        return data["rows"]
    raise ValueError("JSON ledger must be a list, JSONL, or an object with a rows list")


def read_ledger(path: str | Path) -> list[Row]:
    """Read a JSON, JSONL, or CSV ledger file."""
    ledger_path = Path(path)
    if ledger_path.suffix.lower() == ".csv":
        with ledger_path.open(newline="", encoding="utf-8") as handle:
            return list(csv.DictReader(handle))
    return _read_json_or_jsonl(ledger_path)


def cmd_resume_point(args: argparse.Namespace) -> int:
    """Print the next resume gate for CLI callers."""
    rows = read_ledger(args.ledger)
    gate = next_resume_gate(rows)
    if gate is None:
        print("CLEARED")
        return 0
    print(gate)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Print the next mandatory resume gate")
    parser.add_argument("ledger", help="Path to a JSON, JSONL, or CSV gate ledger")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    return cmd_resume_point(parser.parse_args(argv))


if __name__ == "__main__":
    sys.exit(main())
