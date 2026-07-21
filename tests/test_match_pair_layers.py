"""Tests for bazi-hehun pair layers (REQ-006).

T4 (contract T-006-01..04, docs/testing/bazi-hehun.acceptance-tests.md):
the binding test names are implemented here at the pure-engine boundary
(``bazi_engine.match.pair``) — the highest boundary that EXISTS in
Milestone A. The contract's evidence class for these is integration-fake
(assembled app); Milestone B (T9) lifts the same test names onto
``POST /v1/match/bazi-hehun`` / ``app.openapi()`` once the route exists.
Engine-level projections used here:

- T-006-01: the pair section is the frozen :class:`PairAnalysis` whose
  field set IS exactly the three MVP layer names (D3/AC-006a) — a fourth
  layer is unrepresentable without changing the type.
- T-006-02: "response schema property names" ⇒ every dataclass field
  name, layer name and fact key in the emitted structure (AC-006b).
- T-006-03: recursive scan over keys AND string values (AC-006c).
- T-006-04: facts carry only factual source statuses; no key is named
  like a point/score; numeric values appear only under pinned
  computed-fact keys (AC-006d).
"""
from __future__ import annotations

import dataclasses
from typing import Any, Iterator

# D1 / REQ-007 — forbidden score keys (contract §0.4)
FORBIDDEN_SCORE_KEYS = {
    "total_score",
    "sub_scores",
    "score_class",
    "awarded_points",
    "score_confidence",
}

# AC-006b — deferred interaction-matrix layer names (case-insensitive
# substring scan; `ten_god` also covers the singular form as hardening).
FORBIDDEN_MATRIX_TOKENS = (
    "branch_matrix",
    "stem_matrix",
    "ten_gods",
    "ten_god",
    "shen_sha",
    "shensha",
)

# Contract §0.4 blocked-language lexicon (EN + QA DE hardening) plus the
# relationship-quality adjective list (T-005-03, reused here for F7 parity).
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

# AC-006d hardening: numeric fact values are permitted ONLY under keys
# with these suffixes (vector components / canonical indices) — anything
# else numeric is presumed to be a smuggled point/score and fails.
NUMERIC_FACT_KEY_SUFFIXES = ("_vector", "_index")


def _analyze_individual(payload: dict, subject: str):
    from bazi_engine.bazi import compute_bazi
    from bazi_engine.match.individual import analyze_individual
    from bazi_engine.match.normalize import normalize_chart
    from bazi_engine.types import BaziInput

    result = compute_bazi(
        BaziInput(
            birth_local=payload["date"],
            timezone=payload["tz"],
            longitude_deg=payload["lon"],
            latitude_deg=payload["lat"],
        )
    )
    chart = normalize_chart(result, subject=subject)
    return analyze_individual(chart, subject=subject)


def _pair():
    """Build the pair analysis for the canonical sentinel pair."""
    from bazi_engine.match.pair import analyze_pair
    from tests.fixtures.match_payloads import SENTINEL_A, SENTINEL_B

    person_a = _analyze_individual(SENTINEL_A, "person_a")
    person_b = _analyze_individual(SENTINEL_B, "person_b")
    return person_a, person_b, analyze_pair(person_a, person_b)


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


def _walk_keys(value: Any) -> Iterator[str]:
    """Yield every 'key-like' name: dataclass field names, layer names
    and fact keys — the engine-level analog of schema property names."""
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        for f in dataclasses.fields(value):
            yield f.name
            field_value = getattr(value, f.name)
            if f.name in ("key", "name") and isinstance(field_value, str):
                yield field_value
            yield from _walk_keys(field_value)
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from _walk_keys(item)
    elif isinstance(value, dict):
        for k, v in value.items():
            if isinstance(k, str):
                yield k
            yield from _walk_keys(v)


def test_pair_section_contains_exactly_three_mvp_layers() -> None:
    """T-006-01 / AC-006a: the pair section's layer key set is EXACTLY
    {day_master_comparison, spouse_palace_day_branch,
    wuxing_vector_comparison} — no more, no fewer — and each layer is
    non-empty and fully populated from the source-verified computation."""
    from bazi_engine.match import PAIR_LAYER_NAMES, SourceStatus
    from bazi_engine.match.pair import PairAnalysis
    from bazi_engine.match.types import Fact, PairLayer

    person_a, person_b, pair = _pair()

    expected = {
        "day_master_comparison",
        "spouse_palace_day_branch",
        "wuxing_vector_comparison",
    }
    assert set(PAIR_LAYER_NAMES) == expected

    # The frozen type itself carries EXACTLY the three layers — a fourth
    # layer is structurally unrepresentable (D3).
    assert [f.name for f in dataclasses.fields(PairAnalysis)] == list(
        PAIR_LAYER_NAMES
    )
    layers = pair.layers()
    assert set(layers) == expected

    for name, layer in layers.items():
        assert isinstance(layer, PairLayer)
        assert layer.name == name
        # Non-empty / fully populated.
        assert len(layer.facts) > 0
        assert len(layer.evidence_ids) > 0
        assert isinstance(layer.source_status, SourceStatus)
        for fact in layer.facts:
            assert isinstance(fact, Fact)
            assert isinstance(fact.key, str) and fact.key
            assert fact.value is not None
            assert isinstance(fact.source_status, SourceStatus)

    def fact_value(layer: PairLayer, key: str) -> Any:
        matches = [f.value for f in layer.facts if f.key == key]
        assert len(matches) == 1, f"expected exactly one fact {key!r} in {layer.name}"
        return matches[0]

    # Layer 1 — day_master_comparison: populated from the individual
    # analyses' computed day masters, verbatim.
    dm = layers["day_master_comparison"]
    assert fact_value(dm, "person_a_day_master") == person_a.day_master
    assert fact_value(dm, "person_b_day_master") == person_b.day_master
    assert fact_value(dm, "person_a_element") == person_a.day_master_element
    assert fact_value(dm, "person_b_element") == person_b.day_master_element
    assert fact_value(dm, "same_stem") == (person_a.day_master == person_b.day_master)
    assert fact_value(dm, "same_element") == (
        person_a.day_master_element == person_b.day_master_element
    )

    # Layer 2 — spouse_palace_day_branch: identification facts, verbatim
    # from the per-person spouse-palace computation.
    sp = layers["spouse_palace_day_branch"]
    assert fact_value(sp, "palace_pillar") == "day"
    assert fact_value(sp, "person_a_day_branch") == person_a.spouse_palace.day_branch
    assert fact_value(sp, "person_b_day_branch") == person_b.spouse_palace.day_branch
    assert fact_value(sp, "person_a_hidden_stems") == person_a.spouse_palace.hidden_stems
    assert fact_value(sp, "person_b_hidden_stems") == person_b.spouse_palace.hidden_stems
    assert fact_value(sp, "same_day_branch") == (
        person_a.spouse_palace.day_branch == person_b.spouse_palace.day_branch
    )
    # The day-branch⇒spouse-palace DESIGNATION has no ruleset table
    # (planning note a / F7) — the layer must not look source-verified.
    assert sp.source_status is SourceStatus.NEEDS_DOMAIN_REVIEW

    # Layer 3 — wuxing_vector_comparison: both vectors verbatim, ordered
    # by the canonical element order.
    from bazi_engine.wuxing.constants import WUXING_ORDER

    wx = layers["wuxing_vector_comparison"]
    assert fact_value(wx, "element_order") == tuple(WUXING_ORDER)
    assert fact_value(wx, "person_a_vector") == person_a.wuxing_vector
    assert fact_value(wx, "person_b_vector") == person_b.wuxing_vector


def test_no_matrix_layers_in_schema() -> None:
    """T-006-02 / AC-006b: no branch-matrix, stem-matrix, Ten-Gods or
    Shen-Sha layer appears anywhere — engine-level analog: no field name,
    layer name or fact key matches any deferred-matrix token
    (case-insensitive substring)."""
    from bazi_engine.match import PAIR_LAYER_NAMES

    _, _, pair = _pair()

    for key in _walk_keys(pair):
        lowered = key.lower()
        for token in FORBIDDEN_MATRIX_TOKENS:
            assert token not in lowered, (
                f"deferred matrix token {token!r} found in key {key!r}"
            )

    # The layer-name vocabulary itself is matrix-free.
    for name in PAIR_LAYER_NAMES:
        for token in FORBIDDEN_MATRIX_TOKENS:
            assert token not in name


def test_no_missing_interaction_table_stub_anywhere() -> None:
    """T-006-03 / AC-006c: the token MISSING_INTERACTION_TABLE appears
    nowhere — not as a key, not as a string value: deferred layers are
    ABSENT from the contract, never stubbed."""
    _, _, pair = _pair()

    for key in _walk_keys(pair):
        assert "MISSING_INTERACTION_TABLE" not in key.upper()
    for text in _walk_strings(pair):
        assert "MISSING_INTERACTION_TABLE" not in text.upper()


def test_pair_text_is_factual_and_pointless() -> None:
    """T-006-04 / AC-006d: pair content is limited to calculated facts,
    rule applications, source-status markers and warnings; NO numeric
    value anywhere in the pair section is named like a point/score
    (recursive key scan: ``*_points``, ``*_score*``)."""
    from bazi_engine.match import SourceStatus

    _, _, pair = _pair()

    # Key discipline: nothing named like a point/score, none of the five
    # forbidden score keys (D1/REQ-007).
    for key in _walk_keys(pair):
        lowered = key.lower()
        assert not lowered.endswith("_points"), f"point-named key: {key!r}"
        assert "_score" not in lowered, f"score-named key: {key!r}"
        assert lowered not in FORBIDDEN_SCORE_KEYS, f"forbidden score key: {key!r}"

    # Every fact carries a factual source-status marker; numeric values
    # occur ONLY under pinned computed-fact keys (vectors/indices) —
    # bools are comparisons, not numbers.
    for layer in pair.layers().values():
        assert isinstance(layer.source_status, SourceStatus)
        for fact in layer.facts:
            assert isinstance(fact.source_status, SourceStatus)
            values = (
                fact.value if isinstance(fact.value, tuple) else (fact.value,)
            )
            for item in values:
                if isinstance(item, bool):
                    continue
                if isinstance(item, (int, float)):
                    assert fact.key.endswith(NUMERIC_FACT_KEY_SUFFIXES), (
                        f"numeric value under non-allowlisted key {fact.key!r}"
                    )

    # The day-master Wu-Xing relation is a RULE APPLICATION of the
    # canonical production/control cycle — closed factual vocabulary,
    # cross-checked against the repo's existing canonical implementation.
    from bazi_engine.constants import STEMS
    from bazi_engine.dayun.relation import (
        _classify_element_relation,
        _element_index,
    )
    from bazi_engine.match.pair import analyze_pair
    from tests.fixtures.match_payloads import SENTINEL_A, SENTINEL_B

    allowed_relations = {
        "same_element",
        "a_generates_b",
        "b_generates_a",
        "a_controls_b",
        "b_controls_a",
    }
    canonical_to_pair = {
        "same_element": "same_element",
        "produced_by_day_master": "a_generates_b",
        "controlled_by_day_master": "a_controls_b",
        "produces_day_master": "b_generates_a",
        "controls_day_master": "b_controls_a",
    }
    for payload_a, payload_b in (
        (SENTINEL_A, SENTINEL_B),
        (SENTINEL_B, SENTINEL_A),
    ):
        a = _analyze_individual(payload_a, "person_a")
        b = _analyze_individual(payload_b, "person_b")
        layer = analyze_pair(a, b).layers()["day_master_comparison"]
        relation = [
            f.value for f in layer.facts if f.key == "day_master_wuxing_relation"
        ]
        assert len(relation) == 1
        assert relation[0] in allowed_relations
        expected = canonical_to_pair[
            _classify_element_relation(
                _element_index(STEMS.index(a.day_master)),
                _element_index(STEMS.index(b.day_master)),
            )
        ]
        assert relation[0] == expected

    # Lexical guard over EVERY emitted string: no blocked language, no
    # relationship-quality vocabulary (AC-007e parity at the pair layer).
    for text in _walk_strings(pair):
        lowered = text.lower()
        for phrase in BLOCKED_PHRASES:
            assert phrase not in lowered, (
                f"blocked phrase {phrase!r} found in emitted string {text!r}"
            )
