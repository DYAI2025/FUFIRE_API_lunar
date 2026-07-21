"""Tests for bazi-hehun raw_analysis_text blocks (REQ-008).

T1 (structural, unit-fake): TextBlock carries EXACTLY the seven AC-008a
contract fields and EvidenceEntry (AC-013a) has a stable, score-free shape.

T5 (contract T-008-01..04, docs/testing/bazi-hehun.acceptance-tests.md):
the binding test names are implemented here at the pure-engine boundary
(``bazi_engine.match.textblocks``) — the highest boundary that EXISTS in
Milestone A (same idiom as ``test_match_pair_layers.py``). The contract's
evidence class for these is integration-fake (assembled app); Milestone B
(T9) lifts the same test names onto ``POST /v1/match/bazi-hehun`` /
``app.openapi()`` once the route exists. Engine-level projections:

- T-008-01: "every raw-analysis text block" ⇒ every block emitted by
  ``build_text_blocks`` for the canonical sentinel pair.
- T-008-02: "resolve to ledger entries" ⇒ the T6 evidence ledger does not
  exist yet, so resolution targets the id NAMESPACE the ledger will
  materialize: the pair-layer evidence ids (``pair_layer_evidence_id``)
  and the warning evidence ids (``warning_evidence_id``). Full
  referential integrity against the materialized ledger is T6
  (``test_match_observability.py::test_evidence_ledger_complete``).
- T-008-03: "schema docs and examples" ⇒ every emitted string plus the
  docstrings of the ``match.textblocks`` module and its public surface.
- T-008-04: "warnings array + guard metadata" ⇒ the warnings tuple fed
  to / surfaced by the engine, plus proof the lexical guard mechanism
  actively rejects blocked language (AC-008c).
"""
from __future__ import annotations

import dataclasses
import inspect
from typing import Any, Iterator, Tuple

import pytest

# D1 / REQ-007 — forbidden score keys (contract §0.4)
FORBIDDEN_SCORE_KEYS = {
    "total_score",
    "sub_scores",
    "score_class",
    "awarded_points",
    "score_confidence",
}

# AC-008a — the block schema IS the contract (order pinned)
AC_008A_FIELDS = [
    "id",
    "layer",
    "statement_type",
    "subject",
    "text",
    "source_status",
    "evidence_ids",
]


def test_textblock_fields() -> None:
    """AC-008a (structural): TextBlock has exactly the seven contract fields."""
    from bazi_engine.match import SourceStatus, StatementType, TextBlock

    assert dataclasses.is_dataclass(TextBlock)
    assert TextBlock.__dataclass_params__.frozen is True  # type: ignore[attr-defined]

    field_names = [f.name for f in dataclasses.fields(TextBlock)]
    assert field_names == AC_008A_FIELDS
    assert not FORBIDDEN_SCORE_KEYS.intersection(field_names)

    # statement_type vocabulary is EXACTLY the factual set (AC-006d premise):
    # calculated fact / rule application / source-status / warning.
    assert {m.name for m in StatementType} == {
        "CALCULATED_FACT",
        "RULE_APPLICATION",
        "SOURCE_STATUS",
        "WARNING",
    }

    # source_status vocabulary is honest: no tradition-verified-looking
    # status exists — a value is CALCULATED, its domain mapping tables are
    # PENDING_TABLES (MISSING-001..003), or the derivation still needs
    # domain review (AC-005c premise).
    assert {m.name for m in SourceStatus} == {
        "CALCULATED",
        "PENDING_TABLES",
        "NEEDS_DOMAIN_REVIEW",
    }

    block = TextBlock(
        id="blk-001",
        layer="day_master_comparison",
        statement_type=StatementType.CALCULATED_FACT,
        subject="pair",
        text="Day Master of person_a is Jia; Day Master of person_b is Bing.",
        source_status=SourceStatus.CALCULATED,
        evidence_ids=("ev-001",),
    )
    assert isinstance(block.evidence_ids, tuple)
    with pytest.raises(dataclasses.FrozenInstanceError):
        block.text = "mutated"  # type: ignore[misc]


def test_evidence_entry_fields() -> None:
    """AC-013a (structural): EvidenceEntry shape is stable and score-free."""
    from bazi_engine.match import EvidenceEntry, EvidenceKind

    assert dataclasses.is_dataclass(EvidenceEntry)
    assert EvidenceEntry.__dataclass_params__.frozen is True  # type: ignore[attr-defined]

    field_names = [f.name for f in dataclasses.fields(EvidenceEntry)]
    assert field_names == ["id", "kind", "source_ref", "description"]
    assert not FORBIDDEN_SCORE_KEYS.intersection(field_names)

    # Ledger entries back blocks (computation / ruleset lookup) and warnings —
    # nothing else; no score-contribution kind exists (D1).
    assert {m.name for m in EvidenceKind} == {"COMPUTATION", "RULESET", "WARNING"}

    entry = EvidenceEntry(
        id="ev-001",
        kind=EvidenceKind.COMPUTATION,
        source_ref="bazi_engine.bazi.compute_bazi",
        description="Four Pillars computed deterministically from birth input.",
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        entry.id = "ev-002"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# T5 — contract T-008-01..04 at the pure-engine boundary
# ---------------------------------------------------------------------------

# D4 readiness-claim tokens (AC-008b): none may appear in any emitted string
# nor in the textblocks module's public docstrings (case-insensitive).
LLM_READINESS_TOKENS = (
    "llm",
    "interpretation-ready",
    "interpretation ready",
    "fusion interpretation",
)


def _individual(payload: dict, subject: str, *, birth_time_known: bool = True):
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
    chart = normalize_chart(
        result, subject=subject, birth_time_known=birth_time_known
    )
    return analyze_individual(chart, subject=subject)


def _build(birth_time_known: bool = True) -> Tuple[Any, Tuple[Any, ...], Tuple[Any, ...]]:
    """Return (pair, warnings, blocks) for the canonical sentinel pair."""
    from bazi_engine.match.pair import analyze_pair
    from bazi_engine.match.textblocks import build_text_blocks
    from tests.fixtures.match_payloads import SENTINEL_A, SENTINEL_B

    person_a = _individual(
        SENTINEL_A, "person_a", birth_time_known=birth_time_known
    )
    person_b = _individual(
        SENTINEL_B, "person_b", birth_time_known=birth_time_known
    )
    pair = analyze_pair(person_a, person_b)
    warnings = person_a.warnings + person_b.warnings
    return pair, warnings, build_text_blocks(pair, warnings=warnings)


def _block_strings(block: Any) -> Iterator[str]:
    """Yield EVERY string a block emits (incl. enum values + evidence ids)."""
    yield block.id
    yield block.layer
    yield block.statement_type.value
    yield block.subject
    yield block.text
    yield block.source_status.value
    yield from block.evidence_ids


def test_every_text_block_has_the_seven_contract_fields() -> None:
    """T-008-01 / AC-008a: EVERY emitted block has exactly-typed id, layer,
    statement_type, subject, text, source_status, evidence_ids (list-like);
    id values unique; layer ∈ the emitted layer set."""
    from bazi_engine.match import SourceStatus, StatementType, TextBlock
    from bazi_engine.match.textblocks import TEXT_BLOCK_LAYERS

    pair, _, blocks = _build()

    assert isinstance(blocks, tuple) and len(blocks) > 0
    for block in blocks:
        assert isinstance(block, TextBlock)
        assert [f.name for f in dataclasses.fields(block)] == AC_008A_FIELDS
        assert isinstance(block.id, str) and block.id
        assert isinstance(block.layer, str) and block.layer
        assert isinstance(block.statement_type, StatementType)
        assert isinstance(block.subject, str) and block.subject
        assert isinstance(block.text, str) and block.text
        assert isinstance(block.source_status, SourceStatus)
        assert isinstance(block.evidence_ids, tuple)
        for evidence_id in block.evidence_ids:
            assert isinstance(evidence_id, str) and evidence_id

    ids = [block.id for block in blocks]
    assert len(ids) == len(set(ids)), f"duplicate block ids: {ids!r}"

    # layer ∈ the emitted layer set — the pinned vocabulary is the three
    # MVP pair layers plus the warnings scope, and every pair layer is
    # actually covered by at least one block (layer-scoped, D3).
    from bazi_engine.match import PAIR_LAYER_NAMES

    emitted_layers = {block.layer for block in blocks}
    assert set(TEXT_BLOCK_LAYERS) == set(PAIR_LAYER_NAMES) | {"warnings"}
    assert emitted_layers <= set(TEXT_BLOCK_LAYERS)
    assert set(PAIR_LAYER_NAMES) <= emitted_layers


def test_evidence_ids_resolve_to_ledger_entries() -> None:
    """T-008-02 / AC-008a+AC-013a (engine projection): every evidence id in
    every block resolves into the id namespace the T6 ledger materializes
    (pair-layer ids + warning ids) — no dangling refs; no block has empty
    evidence_ids unless its statement_type is a warning/status type."""
    from bazi_engine.match import StatementType
    from bazi_engine.match.pair import pair_layer_evidence_id
    from bazi_engine.match.textblocks import warning_evidence_id

    pair, warnings, blocks = _build(birth_time_known=False)

    namespace = {
        evidence_id
        for layer in pair.layers().values()
        for evidence_id in layer.evidence_ids
    }
    namespace |= {warning_evidence_id(entry) for entry in warnings}

    for block in blocks:
        for evidence_id in block.evidence_ids:
            assert evidence_id in namespace, (
                f"dangling evidence id {evidence_id!r} in block {block.id!r}"
            )
        if not block.evidence_ids:
            assert block.statement_type in (
                StatementType.WARNING,
                StatementType.SOURCE_STATUS,
            ), f"non-status block {block.id!r} has empty evidence_ids"

    # Source-linkage: every block scoped to a pair layer carries that
    # layer's evidence ids — the T6 ledger resolves them 1:1.
    for block in blocks:
        if block.layer in pair.layers():
            assert pair_layer_evidence_id(block.layer) in block.evidence_ids


def test_no_llm_readiness_claim_in_schema_docs_or_examples() -> None:
    """T-008-03 / AC-008b (engine projection): no emitted string and no
    public docstring of match.textblocks claims LLM/Fusion
    interpretation-readiness (D4). The OpenAPI descriptions/examples scan
    is lifted at Milestone B/C once app.openapi() carries the route."""
    from bazi_engine.match import textblocks

    _, _, blocks = _build()

    for block in blocks:
        for text in _block_strings(block):
            lowered = text.lower()
            for token in LLM_READINESS_TOKENS:
                assert token not in lowered, (
                    f"readiness token {token!r} in emitted string {text!r}"
                )

    docs = [inspect.getdoc(textblocks) or ""]
    for name in getattr(textblocks, "__all__", dir(textblocks)):
        if name.startswith("_"):
            continue
        docs.append(inspect.getdoc(getattr(textblocks, name)) or "")
    for doc in docs:
        lowered = doc.lower()
        for token in LLM_READINESS_TOKENS:
            assert token not in lowered, (
                f"readiness token {token!r} in textblocks docstring"
            )


def test_response_contains_warnings_array_and_guard_metadata() -> None:
    """T-008-04 / AC-008c (engine projection): the engine surfaces a
    warnings collection (non-empty for a birth-time-unknown input), every
    warning appears as a WARNING block, and the blocked-language safeguard
    holds over every emitted string AND actively rejects blocked input."""
    from bazi_engine.match import StatementType
    from bazi_engine.match.textblocks import (
        BlockedLanguageError,
        find_blocked_language,
        guard_text,
    )

    _, warnings, blocks = _build(birth_time_known=False)

    # Warnings surface: DAY_ANCHOR_UNVERIFIED (ruleset anchor unverified)
    # and BIRTH_TIME_UNKNOWN (flagged input) are both present (AC-004c).
    codes = {entry.code.value for entry in warnings}
    assert "DAY_ANCHOR_UNVERIFIED" in codes
    assert "BIRTH_TIME_UNKNOWN" in codes

    warning_blocks = [
        block
        for block in blocks
        if block.statement_type is StatementType.WARNING
    ]
    assert warning_blocks, "no WARNING blocks emitted for a warned input"
    assert {block.layer for block in warning_blocks} == {"warnings"}
    for entry in warnings:
        assert any(
            entry.code.value in block.text and block.subject == entry.subject
            for block in warning_blocks
        ), f"warning {entry.code.value!r}/{entry.subject!r} has no block"

    # Blocked-language safeguard over EVERY emitted string (delegates the
    # same scan T-007-03 runs at the HTTP boundary).
    for block in blocks:
        for text in _block_strings(block):
            assert find_blocked_language(text) is None, (
                f"blocked language in emitted string {text!r}"
            )

    # The guard is an active mechanism, not a convention: blocked input
    # raises, clean input passes through verbatim.
    with pytest.raises(BlockedLanguageError):
        guard_text("They are a perfect match.")
    clean = "Day master of person_a is Jia (Holz)."
    assert guard_text(clean) == clean
