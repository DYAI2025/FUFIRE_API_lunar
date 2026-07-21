"""B1 regression: DST fall-back fold must propagate through the exporter.

Any pair of cases that share location + birth_local but differ only in
``ambiguousTime`` must record different ``birth_utc_iso`` values in the
baseline output. Parametrized over all such pairs discovered in the
baseline JSON so adding a new pair (or renaming the existing one) does
not silently lose the regression guard.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
BASELINE_PATH = REPO_ROOT / "tests" / "fixtures" / "bazi_baseline_v1.json"


def _load_or_skip() -> dict:
    if not BASELINE_PATH.exists():
        pytest.skip("baseline missing; run scripts/export_bazi_baseline.py")
    return json.loads(BASELINE_PATH.read_text())


def _ambiguous_pairs(cases: list[dict]) -> Iterable[tuple[dict, dict]]:
    """Yield (earlier, later) pairs that share location + birth_local
    and differ only in ``ambiguousTime``.

    ``earlier`` is always the case whose input says ``ambiguousTime ==
    "earlier"`` (or, if missing, the first-seen) so failures read
    consistently.
    """
    by_key: dict[tuple, list[dict]] = {}
    for c in cases:
        i = c.get("input", {})
        if "ambiguousTime" not in i:
            continue
        key = (
            i.get("birth_local"),
            i.get("timezone"),
            i.get("longitude_deg"),
            i.get("latitude_deg"),
        )
        by_key.setdefault(key, []).append(c)

    for group in by_key.values():
        if len(group) < 2:
            continue
        # Order so 'earlier' is first; fall back to id sort for stability.
        group.sort(key=lambda c: (c["input"].get("ambiguousTime") != "earlier", c["id"]))
        first = group[0]
        for other in group[1:]:
            yield first, other


def _pair_params():
    if not BASELINE_PATH.exists():
        return []
    cases = json.loads(BASELINE_PATH.read_text()).get("cases", [])
    return [
        pytest.param(a, b, id=f"{a['id']}__vs__{b['id']}")
        for a, b in _ambiguous_pairs(cases)
    ]


def test_baseline_includes_at_least_one_ambiguous_pair():
    """If this fails, the exporter case list lost its DST fold coverage."""
    doc = _load_or_skip()
    pairs = list(_ambiguous_pairs(doc["cases"]))
    assert pairs, (
        "Baseline must contain at least one ambiguous pair "
        "(two cases sharing location + birth_local, differing in "
        "ambiguousTime). Without one, DST fold regressions are "
        "invisible."
    )


@pytest.mark.parametrize("earlier,later", _pair_params())
def test_ambiguous_pair_records_different_utc(earlier, later):
    """Each ambiguous pair must record distinct ``birth_utc_iso`` values.

    Identical UTCs across a pair mean the exporter dropped the fold —
    the B1 regression.
    """
    earlier_utc = earlier["output"].get("birth_utc_iso")
    later_utc = later["output"].get("birth_utc_iso")
    assert earlier_utc is not None, (
        f"{earlier['id']} is missing birth_utc_iso "
        "(B1 fix requires this field for fold visibility)."
    )
    assert later_utc is not None, f"{later['id']} is missing birth_utc_iso."
    assert earlier_utc != later_utc, (
        f"DST fold drop between {earlier['id']!r} and {later['id']!r}: "
        f"both recorded UTC {earlier_utc!r}. "
        "Exporter is not honoring ambiguousTime."
    )
