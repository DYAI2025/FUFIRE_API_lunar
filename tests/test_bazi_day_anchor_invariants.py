"""FBP-00-005 — ruleset-driven day-anchor invariants.

This module deliberately has **no** ephemeris dependency so the
anchor-policy test runs in every CI configuration (including
MOSEPH-only). The day-pillar sanity checks that *do* require ephemeris
remain in ``tests/test_invariants.py``.

History: prior to BAZI-PRECISION-V2, this test asserted
``DAY_OFFSET == 49`` directly. That treated an unverified engine
constant as ground truth (DEV-2026-004). It now reads the ruleset's
own declared anchor and verification status.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from bazi_engine.constants import DAY_OFFSET

RULESET_PATH = (
    Path(__file__).resolve().parents[1]
    / "spec" / "rulesets" / "standard_bazi_2026.json"
)


def test_day_offset_is_a_valid_sexagenary_offset():
    """Range/type invariant — survives any ruleset anchor change."""
    assert isinstance(DAY_OFFSET, int)
    assert 0 <= DAY_OFFSET < 60


def test_ruleset_declares_day_cycle_anchor():
    """The ruleset must carry an anchor record (FBP-02-001 precondition)."""
    ruleset = json.loads(RULESET_PATH.read_text())
    anchor = ruleset["day_cycle_anchor"]
    assert anchor["anchor_type"] in {"JDN", "DATE"}, anchor
    assert anchor["anchor_sexagenary_index_0based"] == 0
    assert anchor["anchor_verification"] in {"unverified", "verified"}


def test_day_anchor_phase0_baseline_behavior():
    """Phase-0 stop-gate behavior — engine baseline preserved until anchor is verified.

    While the anchor is ``unverified`` (Phase 0 / start of Phase 2),
    the engine's historic outputs for the two reference dates are
    preserved as a *regression guard*, NOT as truth. When the anchor
    is upgraded to ``verified`` (FBP-02-003), this test must be
    rewritten to assert against an EXTERNAL_ORACLE golden in
    ``tests/golden_reference_cases.py``.
    """
    # Local import keeps the module load cheap and avoids pulling in
    # ephemeris-touching code for the other two tests above.
    from bazi_engine.bazi import sexagenary_day_index_from_date

    ruleset = json.loads(RULESET_PATH.read_text())
    status = ruleset["day_cycle_anchor"]["anchor_verification"]

    if status == "verified":
        pytest.fail(
            "Anchor verification was upgraded to 'verified'. "
            "Rewrite this test per FBP-02-002 to assert against the "
            "EXTERNAL_ORACLE entries in tests/golden_reference_cases.py."
        )

    # Engine baseline (regression guard, not truth):
    assert sexagenary_day_index_from_date(1912, 2, 18) == 0
    assert sexagenary_day_index_from_date(1949, 10, 1) == 0
