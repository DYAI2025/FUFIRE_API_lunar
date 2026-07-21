"""FUFIRE-005 guard: don't advertise quotas that nothing enforces.

Only per-minute limits are enforced (limiter.py builds minute windows
exclusively). Daily quotas may be re-advertised once a durable daily
counter ships (see ADR-002 / plan Phase 2).
"""
import json
from pathlib import Path

SPEC_PATH = Path(__file__).resolve().parents[1] / "spec/openapi/openapi.json"


def test_no_unenforced_daily_quota_claims() -> None:
    spec = json.loads(SPEC_PATH.read_text())
    desc = spec["info"]["description"].lower()
    for phrase in ("requests/day", "requests per day", "/ day", "per day", "req/day"):
        assert phrase not in desc, (
            f"Spec info.description advertises daily quotas ({phrase!r}) but only "
            "per-minute limits are enforced — keep the contract truthful (FUFIRE-005)."
        )
