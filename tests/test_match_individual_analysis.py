"""Tests for bazi-hehun individual chart analysis (REQ-005).

T3 (contract T-005-01..03, docs/testing/bazi-hehun.acceptance-tests.md):
the binding test names are implemented here at the pure-engine boundary
(``bazi_engine.match.individual``) — the highest boundary that EXISTS in
Milestone A. The contract's evidence class for these is integration-fake
(assembled app); Milestone B (T9) lifts the same test names onto
``POST /v1/match/bazi-hehun`` once the route exists. The text-block leg of
T-005-03 (spouse-palace ``statement_type`` is factual) belongs to T5
(``match/textblocks.py``) and is asserted there/at T9 — the engine-level
half asserted here is the F7 core: spouse-palace content is computed
identification facts + ``source_status`` only, with zero interpretive
vocabulary anywhere in the emitted strings.
"""
from __future__ import annotations

import dataclasses
from typing import Any, Iterator

import pytest

from tests.fixtures.match_payloads import SENTINEL_A, SENTINEL_B

# D1 / REQ-007 — forbidden score keys (contract §0.4)
FORBIDDEN_SCORE_KEYS = {
    "total_score",
    "sub_scores",
    "score_class",
    "awarded_points",
    "score_confidence",
}

# Contract §0.4 blocked-language lexicon (EN + QA DE hardening) plus the
# T-005-03 relationship-quality adjective list (EN + DE equivalents).
BLOCKED_PHRASES = (
    "perfect match",
    "marriage guarantee",
    "breakup prediction",
    "fate certainty",
    "perfekte übereinstimmung",
    "ehegarantie",
    "trennungsvorhersage",
    "schicksals",
    "harmonious",
    "unstable",
    "loyal",
    "unfaithful",
    "harmonisch",
    "instabil",
    "treu",  # also substring of "untreu"
)


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


def _analyze(payload: dict, subject: str, gender=None):
    from bazi_engine.match.individual import analyze_individual
    from bazi_engine.match.normalize import normalize_chart

    chart = normalize_chart(_compute_result(payload), subject=subject)
    return analyze_individual(chart, subject=subject, gender=gender)


def _walk_strings(value: Any) -> Iterator[str]:
    """Yield every string value at every depth of a dataclass tree."""
    if isinstance(value, str):
        yield value
    elif dataclasses.is_dataclass(value) and not isinstance(value, type):
        for f in dataclasses.fields(value):
            yield from _walk_strings(getattr(value, f.name))
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from _walk_strings(item)
    elif isinstance(value, dict):
        for k, v in value.items():
            yield from _walk_strings(k)
            yield from _walk_strings(v)


def _walk_field_names(value: Any) -> Iterator[str]:
    """Yield every dataclass field name at every depth."""
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        for f in dataclasses.fields(value):
            yield f.name
            yield from _walk_field_names(getattr(value, f.name))
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from _walk_field_names(item)


def test_response_contains_individual_person_a_and_b() -> None:
    """T-005-01 / AC-005a: the individual section carries person_a AND
    person_b, each with Day Master, spouse-palace/day-branch facts, month
    command, Wu-Xing vector, source status and warnings."""
    from bazi_engine.constants import BRANCHES, STEMS
    from bazi_engine.match import SourceStatus
    from bazi_engine.match.individual import IndividualAnalysis

    individual = {
        "person_a": _analyze(SENTINEL_A, "person_a"),
        "person_b": _analyze(SENTINEL_B, "person_b"),
    }
    assert set(individual) == {"person_a", "person_b"}

    for subject, payload in (("person_a", SENTINEL_A), ("person_b", SENTINEL_B)):
        analysis = individual[subject]
        assert isinstance(analysis, IndividualAnalysis)
        assert analysis.subject == subject

        res = _compute_result(payload)
        # Day Master — day pillar's heavenly stem ONLY (AC-004a carried in).
        assert analysis.day_master == STEMS[res.pillars.day.stem_index]

        # Spouse-palace/day-branch facts present.
        assert analysis.spouse_palace.day_branch == BRANCHES[res.pillars.day.branch_index]

        # Month command present and anchored to the month branch.
        assert analysis.month_command.branch == BRANCHES[res.pillars.month.branch_index]

        # Wu-Xing vector present (5 components, some weight in the chart).
        assert len(analysis.wuxing_vector) == 5
        assert sum(analysis.wuxing_vector) > 0

        # Source status + warnings surfaces exist.
        assert isinstance(analysis.source_status, SourceStatus)
        assert isinstance(analysis.warnings, tuple)

        # D1/REQ-007: no score-named field anywhere in the structure.
        assert not FORBIDDEN_SCORE_KEYS.intersection(set(_walk_field_names(analysis)))

    # The two analyses are genuinely per-person (no cross-person bleed).
    assert (
        individual["person_a"].day_master != individual["person_b"].day_master
        or individual["person_a"].spouse_palace.day_branch
        != individual["person_b"].spouse_palace.day_branch
    )


def test_dms_yongshen_fields_carry_source_status_and_confidence() -> None:
    """T-005-02 / AC-005b + AC-005c: every DMS/Yong-Shen field has BOTH a
    source_status and a confidence marker; while the domain mapping tables
    (MISSING-003) are pending, the status MUST be PENDING_TABLES or
    NEEDS_DOMAIN_REVIEW — never a verified-looking status — and the stub
    carries NO value field at all, so a fabricated value is impossible by
    construction. spouse_star (GF-3, MISSING-002 resolved) moved to its own
    SpouseStarResult type — see test_spouse_star_* below, not here."""
    from bazi_engine.match import SourceStatus
    from bazi_engine.match.individual import DerivedFieldStatus

    analysis = _analyze(SENTINEL_A, "person_a")

    derived = {stub.field: stub for stub in analysis.derived_fields}
    # The remaining DerivedFieldStatus set: DMS, Yong-Shen only.
    assert set(derived) == {"day_master_strength", "yong_shen"}

    allowed = {SourceStatus.PENDING_TABLES, SourceStatus.NEEDS_DOMAIN_REVIEW}
    for stub in analysis.derived_fields:
        # BOTH markers present (AC-005b).
        assert isinstance(stub.source_status, SourceStatus)
        assert isinstance(stub.confidence, float)
        # Never verified-looking while MISSING-003 is open (AC-005c).
        assert stub.source_status in allowed
        # No approved source ⇒ no confidence is claimable.
        assert stub.confidence == 0.0
        # Ledger attribution names the open MISSING item.
        assert stub.blocked_by == "MISSING-003"

    # Structural honesty: the stub type has NO value-carrying field.
    stub_fields = [f.name for f in dataclasses.fields(DerivedFieldStatus)]
    assert stub_fields == ["field", "source_status", "confidence", "blocked_by"]

    # The guard is enforced by the type itself: a "helpfully filled"
    # CALCULATED derived field must be unrepresentable.
    with pytest.raises(ValueError):
        DerivedFieldStatus(
            field="day_master_strength",
            source_status=SourceStatus.CALCULATED,
            confidence=1.0,
            blocked_by="MISSING-003",
        )


def test_spouse_palace_layer_is_computed_facts_only() -> None:
    """T-005-03 / AC-005c (audit F7): spouse-palace content is limited to
    computed identification facts (which branch/pillar, ruleset hidden
    stems) + source_status; the palace DESIGNATION is not masqueraded as
    verified; no emitted string contains blocked language or
    relationship-quality adjectives."""
    from bazi_engine.bazi_rules import load_default_ruleset
    from bazi_engine.constants import BRANCHES
    from bazi_engine.match import SourceStatus
    from bazi_engine.match.individual import SpousePalaceFacts

    ruleset = load_default_ruleset()

    for subject, payload in (("person_a", SENTINEL_A), ("person_b", SENTINEL_B)):
        analysis = _analyze(payload, subject)
        palace = analysis.spouse_palace

        # EXACTLY the identification-fact field set — nothing interpretive.
        field_names = [f.name for f in dataclasses.fields(SpousePalaceFacts)]
        assert field_names == [
            "palace_pillar",
            "day_branch",
            "day_branch_index",
            "hidden_stems",
            "position_source_status",
            "position_source_note",
            "source_status",
        ]

        # Facts are the deterministic computations, verbatim.
        res = _compute_result(payload)
        assert palace.palace_pillar == "day"
        assert palace.day_branch_index == res.pillars.day.branch_index
        assert palace.day_branch == BRANCHES[palace.day_branch_index]
        assert palace.hidden_stems == tuple(
            ruleset["hidden_stems"]["branch_to_hidden"][palace.day_branch]
        )

        # CHANGE (b): the POSITION identification (day branch = spouse
        # palace, 日支=夫妻宫) is a standard, deterministic BaZi fact ⇒
        # CALCULATED, with a source note recording the identification.
        assert palace.position_source_status is SourceStatus.CALCULATED
        assert "spouse palace" in palace.position_source_note.lower()
        # The spouse-palace INTERPRETATION/designation (compatibility
        # meaning, spouse-star derivation) has no ruleset table (planning
        # note a) — it must NOT look source-verified; it stays deferred and
        # is never collapsed into the CALCULATED position status.
        assert palace.source_status is SourceStatus.NEEDS_DOMAIN_REVIEW

        # Lexical guard over EVERY string in the whole analysis: no blocked
        # language, no relationship-quality adjectives (F7).
        for text in _walk_strings(analysis):
            lowered = text.lower()
            for phrase in BLOCKED_PHRASES:
                assert phrase not in lowered, (
                    f"blocked phrase {phrase!r} found in emitted string {text!r}"
                )


# ── GF-3/GF-4 (docs/plans/2026-07-04-bazi-hehun-gender-field.md) ────────────
def test_spouse_star_no_gender_provided() -> None:
    from bazi_engine.match import SourceStatus

    analysis = _analyze(SENTINEL_A, "person_a", gender=None)
    star = analysis.spouse_star
    assert star.gender_used is None
    assert star.source_status is SourceStatus.PENDING_TABLES
    assert star.confidence == 0.0
    assert star.blocked_by == "GENDER_NOT_PROVIDED"
    assert star.occurrences == ()


def test_spouse_star_divers_gender_has_no_sourced_convention() -> None:
    """'divers' must NEVER fall back to the male/female rule -- MISSING-008."""
    from bazi_engine.match import SourceStatus

    analysis = _analyze(SENTINEL_A, "person_a", gender="divers")
    star = analysis.spouse_star
    assert star.gender_used == "divers"
    assert star.source_status is SourceStatus.PENDING_TABLES
    assert star.confidence == 0.0
    assert star.blocked_by == "MISSING-008"
    assert star.occurrences == ()


@pytest.mark.parametrize("gender", ["male", "female"])
def test_spouse_star_male_female_calculated_matches_independent_recomputation(
    gender: str,
) -> None:
    """CALCULATED once gender is known; occurrences independently
    re-derived here (separate loop, not the module's private helper) from
    the already-validated Ten-Gods table + convention (tests/
    test_match_ten_gods.py) -- catches wiring bugs the lower-level unit
    tests can't see."""
    from bazi_engine.bafe.ruleset_loader import spouse_star_convention
    from bazi_engine.bazi_rules import load_default_ruleset
    from bazi_engine.match import SourceStatus
    from bazi_engine.match.ten_gods import ten_god_for_stems

    analysis = _analyze(SENTINEL_A, "person_a", gender=gender)
    star = analysis.spouse_star
    assert star.gender_used == gender
    assert star.source_status is SourceStatus.CALCULATED
    assert star.confidence == 1.0
    assert star.blocked_by == ""

    ruleset = load_default_ruleset()
    convention = spouse_star_convention(ruleset)
    primary_gods = set(convention[gender])
    disruption_god = convention["disruption_signal"][gender]["god"]

    chart = normalize_chart_for_test(SENTINEL_A, "person_a")
    expected = []
    for entry in chart.wuxing_ledger:
        god = ten_god_for_stems(ruleset, chart.day_master, entry.stem)
        if god in primary_gods:
            expected.append((entry.pillar, entry.source, entry.stem, "primary_convention_god"))
        elif god == disruption_god:
            expected.append((entry.pillar, entry.source, entry.stem, "disruption_signal_god"))

    actual = [
        (occ.pillar, occ.source, occ.stem, occ.role) for occ in star.occurrences
    ]
    assert actual == expected


def normalize_chart_for_test(payload: dict, subject: str):
    from bazi_engine.match.normalize import normalize_chart

    return normalize_chart(_compute_result(payload), subject=subject)


def test_spouse_star_result_rejects_inconsistent_construction() -> None:
    """The guard is enforced by the type itself (mirrors DerivedFieldStatus):
    a "helpfully filled" value under a blocked status, or a CALCULATED
    status with no gender, must be unrepresentable."""
    from bazi_engine.match import SourceStatus
    from bazi_engine.match.individual import SpouseStarResult

    with pytest.raises(ValueError):
        SpouseStarResult(
            gender_used=None,
            source_status=SourceStatus.CALCULATED,  # no gender -> can't be CALCULATED
            confidence=1.0,
            blocked_by="",
            occurrences=(),
        )
    with pytest.raises(ValueError):
        SpouseStarResult(
            gender_used="divers",
            source_status=SourceStatus.CALCULATED,  # no sourced convention -> can't be CALCULATED
            confidence=1.0,
            blocked_by="",
            occurrences=(),
        )
    with pytest.raises(ValueError):
        SpouseStarResult(
            gender_used="male",
            source_status=SourceStatus.PENDING_TABLES,
            confidence=0.0,
            blocked_by="GENDER_NOT_PROVIDED",  # gender IS known -> wrong blocker
            occurrences=(),
        )
