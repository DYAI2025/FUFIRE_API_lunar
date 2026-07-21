"""Tests for bazi-hehun chart normalization (REQ-004).

T1 (structural, unit-fake): NormalizedChart shape, warning-code constants
and the Wu-Xing ledger entry shape (source marker + numeric weight).

T2 (contract T-004-01..03, docs/testing/bazi-hehun.acceptance-tests.md):
the binding test names are implemented here at the pure-engine boundary
(``bazi_engine.match.normalize``) — the highest boundary that EXISTS in
Milestone A. The contract's evidence class for these is integration-fake
(assembled app); Milestone B (T9) lifts the same test names onto
``POST /v1/match/bazi-hehun`` once the route exists. T-004-04
(ephemeris-mode attestation parity) is endpoint-only and belongs to T9.
"""
from __future__ import annotations

import dataclasses

import pytest

from tests.fixtures.match_payloads import SENTINEL_A, SENTINEL_B

FORBIDDEN_SCORE_KEYS = {
    "total_score",
    "sub_scores",
    "score_class",
    "awarded_points",
    "score_confidence",
}


def test_normalized_chart_shape() -> None:
    """AC-008a/AC-013a-adjacent structural core: NormalizedChart is a frozen
    canonical structure — day_master is the day stem ONLY (AC-004a premise),
    month/hour masters exist only as provenance labels, Wu-Xing ledger entries
    carry a visible/hidden source marker and a numeric weight (AC-004b
    premise), and warning codes are stable constants (AC-004c premise)."""
    from bazi_engine.constants import STEMS
    from bazi_engine.match import (
        NormalizedChart,
        StemSource,
        WarningCode,
        WarningEntry,
        WuxingLedgerEntry,
    )
    from bazi_engine.types import FourPillars, Pillar

    assert dataclasses.is_dataclass(NormalizedChart)
    assert NormalizedChart.__dataclass_params__.frozen is True  # type: ignore[attr-defined]

    field_names = [f.name for f in dataclasses.fields(NormalizedChart)]
    assert field_names == [
        "pillars",
        "day_master",
        "month_master_label",
        "hour_master_label",
        "wuxing_ledger",
        "wuxing_vector",
        "birth_time_known",
        "warnings",
    ]
    assert not FORBIDDEN_SCORE_KEYS.intersection(field_names)

    # Stable warning codes, not prose (AC-004c: matched by code, not message).
    assert {m.name for m in WarningCode} >= {
        "DAY_ANCHOR_UNVERIFIED",
        "BIRTH_TIME_UNKNOWN",
    }
    assert WarningCode.DAY_ANCHOR_UNVERIFIED.value == "DAY_ANCHOR_UNVERIFIED"
    assert WarningCode.BIRTH_TIME_UNKNOWN.value == "BIRTH_TIME_UNKNOWN"

    # Wu-Xing ledger entry: source marker distinguishes visible vs hidden
    # stems AND carries a numeric weight (AC-004b structural half).
    ledger_fields = [f.name for f in dataclasses.fields(WuxingLedgerEntry)]
    assert ledger_fields == ["pillar", "stem", "element", "source", "weight"]
    assert StemSource.VISIBLE.is_hidden is False
    assert StemSource.HIDDEN_PRINCIPAL.is_hidden is True
    assert StemSource.HIDDEN_CENTRAL.is_hidden is True
    assert StemSource.HIDDEN_RESIDUAL.is_hidden is True

    pillars = FourPillars(
        year=Pillar(stem_index=0, branch_index=0),
        month=Pillar(stem_index=1, branch_index=1),
        day=Pillar(stem_index=2, branch_index=2),
        hour=Pillar(stem_index=3, branch_index=3),
    )
    chart = NormalizedChart(
        pillars=pillars,
        day_master=STEMS[pillars.day.stem_index],
        month_master_label=STEMS[pillars.month.stem_index],
        hour_master_label=STEMS[pillars.hour.stem_index],
        wuxing_ledger=(
            WuxingLedgerEntry(
                pillar="day",
                stem="Bing",
                element="Feuer",
                source=StemSource.VISIBLE,
                weight=1.0,
            ),
        ),
        wuxing_vector=(0.0, 1.0, 0.0, 0.0, 0.0),
        birth_time_known=True,
        warnings=(
            WarningEntry(
                code=WarningCode.DAY_ANCHOR_UNVERIFIED,
                subject="ruleset",
                message="day_cycle_anchor.anchor_verification is 'unverified'.",
            ),
        ),
    )

    # AC-004a structural: day_master equals the day pillar's heavenly stem.
    assert chart.day_master == "Bing"
    assert isinstance(chart.wuxing_ledger[0].weight, float)
    with pytest.raises(dataclasses.FrozenInstanceError):
        chart.day_master = "Jia"  # type: ignore[misc]


# ── T2: contract tests T-004-01..03 (pure-engine boundary, see module docstring) ──


def _compute_result(payload: dict):
    """Build a BaziResult for a sentinel person exactly like the engine does."""
    from bazi_engine.bazi import compute_bazi
    from bazi_engine.types import BaziInput

    return compute_bazi(
        BaziInput(
            birth_local=payload["date"],
            timezone=payload["tz"],
            longitude_deg=payload["lon"],
            latitude_deg=payload["lat"],
        )
    )


def test_day_master_is_day_stem_only() -> None:
    """T-004-01 / AC-004a: for each person, day_master equals that person's
    day-pillar heavenly stem; month/hour "master" values appear ONLY as
    provenance labels (dedicated *_label fields), never as day_master."""
    from bazi_engine.constants import STEMS
    from bazi_engine.match import NormalizedChart
    from bazi_engine.match.normalize import normalize_chart

    for subject, payload in (("person_a", SENTINEL_A), ("person_b", SENTINEL_B)):
        res = _compute_result(payload)
        chart = normalize_chart(res, subject=subject)

        assert chart.day_master == STEMS[res.pillars.day.stem_index]
        # Provenance labels carry the month/hour stems — and ONLY there.
        assert chart.month_master_label == STEMS[res.pillars.month.stem_index]
        assert chart.hour_master_label == STEMS[res.pillars.hour.stem_index]

        # No other field named like a master exists on the canonical structure.
        master_fields = [
            f.name for f in dataclasses.fields(NormalizedChart) if "master" in f.name
        ]
        assert master_fields == [
            "day_master",
            "month_master_label",
            "hour_master_label",
        ]

    # Discriminating case: SENTINEL_A's month stem differs from its day stem,
    # so a month-master mixup cannot pass silently.
    res_a = _compute_result(SENTINEL_A)
    assert res_a.pillars.month.stem_index != res_a.pillars.day.stem_index


def test_wuxing_ledger_includes_visible_and_hidden_stems_with_source_and_weight() -> None:
    """T-004-02 / AC-004b: every ledger entry carries a source marker
    distinguishing visible vs hidden stems AND a numeric weight; hidden
    weighting binds to the legacy /calculate/wuxing source (DECISION-003);
    the ruleset role weights currently coincide (1.0/0.5/0.3 per role), so
    the keyed cross-check below stays valid."""
    from bazi_engine.bazi_rules import load_default_ruleset
    from bazi_engine.constants import STEMS
    from bazi_engine.match import StemSource
    from bazi_engine.match.normalize import normalize_chart
    from bazi_engine.wuxing.analysis import calculate_wuxing_from_bazi
    from bazi_engine.wuxing.constants import WUXING_ORDER

    ruleset = load_default_ruleset()
    role_weights = ruleset["hidden_stems_weighting"]["role_weights"]

    for subject, payload in (("person_a", SENTINEL_A), ("person_b", SENTINEL_B)):
        res = _compute_result(payload)
        chart = normalize_chart(res, subject=subject)

        assert len(chart.wuxing_ledger) > 0
        for entry in chart.wuxing_ledger:
            assert isinstance(entry.source, StemSource)  # source marker
            assert isinstance(entry.weight, float)  # numeric weight
            assert entry.stem in STEMS
            assert entry.element in WUXING_ORDER
            assert entry.pillar in ("year", "month", "day", "hour")

        visible = [e for e in chart.wuxing_ledger if e.source is StemSource.VISIBLE]
        hidden = [e for e in chart.wuxing_ledger if e.source.is_hidden]
        # Both kinds present (every branch has >= 1 hidden stem in the ruleset).
        assert visible, "expected visible-stem ledger entries"
        assert hidden, "expected hidden-stem ledger entries"

        # One visible stem per pillar at weight 1.0 (analysis.py ledger pattern).
        assert len(visible) == 4
        assert all(e.weight == 1.0 for e in visible)

        # Hidden weights are EXACTLY the ruleset role weights, keyed by role.
        role_by_source = {
            StemSource.HIDDEN_PRINCIPAL: "principal",
            StemSource.HIDDEN_CENTRAL: "central",
            StemSource.HIDDEN_RESIDUAL: "residual",
        }
        for e in hidden:
            assert e.weight == role_weights[role_by_source[e.source]]

        # The vector is exactly the ledger's per-element weight sum
        # (WUXING_ORDER) — internal consistency of the normalization.
        expected = [0.0] * 5
        for e in chart.wuxing_ledger:
            expected[WUXING_ORDER.index(e.element)] += e.weight
        assert chart.wuxing_vector == tuple(expected)

    # Weight-pattern parity with the existing wuxing/analysis.py ledger
    # (visible 1.0 + Qi role weights): asserted on SENTINEL_A. Since
    # DECISION-003 binds the match ledger to that legacy source, parity now
    # holds for ALL branches incl. Wei — see the dedicated test below for
    # the explicit Wei binding.
    res_a = _compute_result(SENTINEL_A)
    chart_a = normalize_chart(res_a, subject="person_a")
    pillars_dict = {
        name: {
            "stem": STEMS[getattr(res_a.pillars, name).stem_index],
            "branch": str(getattr(res_a.pillars, name))[
                len(STEMS[getattr(res_a.pillars, name).stem_index]) :
            ],
        }
        for name in ("year", "month", "day", "hour")
    }
    legacy = calculate_wuxing_from_bazi(pillars_dict)
    assert chart_a.wuxing_vector == pytest.approx(tuple(legacy.to_list()))


def test_known_ruleset_vs_legacy_wei_hidden_stem_divergence_is_visible() -> None:
    """NOT a contract test — loud pin for a data divergence found during T2,
    resolved by user DECISION-003 (2026-07-02) pending MISSING-006 domain
    review (docs/governance/bazi-hehun.missing-assumption-blocker-ledger.md,
    docs/context/bazi-hehun.response-schema-decision.md):

    (a) DETECTION: ruleset ``standard_bazi_2026`` lists branch Wei's hidden
        stems as ``["Ji", "Yi", "Ding"]`` (positional roles → Yi central
        0.5, Ding residual 0.3), while the legacy ``wuxing/analysis.py``
        ``_BRANCH_HIDDEN`` table weights Wei as Feuer/Ding 0.5, Holz/Yi 0.3
        (mainstream 藏干 tradition Ji-Ding-Yi). This divergence must remain
        exactly ``["Wei"]`` — if either source changes, fail loudly and
        force a conscious re-decision instead of silent drift.
    (b) BINDING: per DECISION-003 the match engine binds its ledger
        weighting to the SAME source ``/calculate/wuxing`` uses (the legacy
        table) — the product must never disagree with itself. For a
        Wei-bearing chart the ledger must weight Ding 0.5 (central) and
        Yi 0.3 (residual), NOT the ruleset's outlier ordering."""
    from bazi_engine.bazi_rules import load_default_ruleset
    from bazi_engine.match import StemSource
    from bazi_engine.match.normalize import (
        build_wuxing_ledger,
        wuxing_vector_from_ledger,
    )
    from bazi_engine.types import FourPillars, Pillar
    from bazi_engine.wuxing.analysis import (  # type: ignore[attr-defined]
        _BRANCH_HIDDEN,
        _STEM_TO_ELEMENT,
        calculate_wuxing_from_bazi,
    )

    ruleset = load_default_ruleset()
    branch_to_hidden = ruleset["hidden_stems"]["branch_to_hidden"]
    positional_weights = (1.0, 0.5, 0.3)

    # (a) The ruleset-vs-legacy divergence IS detected — and is exactly Wei.
    diverging = []
    for branch, hidden_stems in branch_to_hidden.items():
        ruleset_view = [
            (_STEM_TO_ELEMENT[s], w)
            for s, w in zip(hidden_stems, positional_weights)
        ]
        if ruleset_view != _BRANCH_HIDDEN[branch]:
            diverging.append(branch)

    assert diverging == ["Wei"], (
        "Hidden-stem divergence set between ruleset and wuxing/analysis.py "
        f"changed (was exactly ['Wei'], now {diverging!r}) — a source was "
        "edited; MISSING-006/DECISION-003 must be re-decided and this pin "
        "updated."
    )

    # (b) Legacy binds (DECISION-003): a Ji-Wei day pillar's hidden entries
    # follow the legacy weighting Ji/Erde 1.0, Ding/Feuer 0.5, Yi/Holz 0.3.
    pillars = FourPillars(
        year=Pillar(stem_index=0, branch_index=0),  # Jia Zi
        month=Pillar(stem_index=2, branch_index=5),  # Bing Si
        day=Pillar(stem_index=5, branch_index=7),  # Ji Wei
        hour=Pillar(stem_index=4, branch_index=4),  # Wu Chen
    )
    ledger = build_wuxing_ledger(pillars, ruleset)
    wei_hidden = [
        (e.stem, e.element, e.source, e.weight)
        for e in ledger
        if e.pillar == "day" and e.source.is_hidden
    ]
    assert wei_hidden == [
        ("Ji", "Erde", StemSource.HIDDEN_PRINCIPAL, 1.0),
        ("Ding", "Feuer", StemSource.HIDDEN_CENTRAL, 0.5),
        ("Yi", "Holz", StemSource.HIDDEN_RESIDUAL, 0.3),
    ], (
        "Wei hidden-stem weighting must bind to the legacy /calculate/wuxing "
        "source (DECISION-003, pending MISSING-006 domain review), not to "
        f"the ruleset's outlier ordering — got {wei_hidden!r}."
    )

    # Full-chart vector parity with /calculate/wuxing's computation for a
    # Wei-bearing chart — the product does not disagree with itself.
    from bazi_engine.constants import BRANCHES, STEMS

    pillars_dict = {
        name: {
            "stem": STEMS[getattr(pillars, name).stem_index],
            "branch": BRANCHES[getattr(pillars, name).branch_index],
        }
        for name in ("year", "month", "day", "hour")
    }
    legacy_vector = calculate_wuxing_from_bazi(pillars_dict)
    assert wuxing_vector_from_ledger(ledger) == pytest.approx(
        tuple(legacy_vector.to_list())
    )


def test_unverified_anchor_and_unknown_birth_time_produce_warnings() -> None:
    """T-004-03 / AC-004c: with the shipped ruleset
    (day_cycle_anchor.anchor_verification == "unverified") and
    birth_time_known=False, the warnings carry BOTH stable codes —
    matched by code, never by prose."""
    from bazi_engine.bazi_rules import load_default_ruleset
    from bazi_engine.match import WarningCode
    from bazi_engine.match.normalize import normalize_chart

    # Premise from the shipped ruleset (contract T-004-03 Given).
    ruleset = load_default_ruleset()
    assert ruleset["day_cycle_anchor"]["anchor_verification"] == "unverified"

    res = _compute_result(SENTINEL_A)
    chart = normalize_chart(res, subject="person_a", birth_time_known=False)

    codes = {w.code for w in chart.warnings}
    assert WarningCode.DAY_ANCHOR_UNVERIFIED in codes
    assert WarningCode.BIRTH_TIME_UNKNOWN in codes
    assert chart.birth_time_known is False

    # birth_time_known=True (default) drops ONLY the birth-time warning;
    # the anchor warning stays as long as the ruleset anchor is unverified.
    chart_known = normalize_chart(res, subject="person_a")
    codes_known = {w.code for w in chart_known.warnings}
    assert WarningCode.DAY_ANCHOR_UNVERIFIED in codes_known
    assert WarningCode.BIRTH_TIME_UNKNOWN not in codes_known
