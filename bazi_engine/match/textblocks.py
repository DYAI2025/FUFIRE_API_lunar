"""match/textblocks.py — REQ-008: deterministic raw_analysis_text blocks.

Level 4 (plan §4.1, docs/plans/2026-07-02-bazi-hehun.md). Imports Levels
0-4 only (sibling ``match`` modules, ``exc``); NEVER ``routers/*``,
``app``, ``limiter`` or ``services/*``. Pure functions — no I/O, no HTTP
shaping.

Binding contract anchors (docs/testing/bazi-hehun.acceptance-tests.md):
- AC-008a: every block is a frozen
  :class:`~bazi_engine.match.types.TextBlock` — exactly ``id, layer,
  statement_type, subject, text, source_status, evidence_ids``. Blocks
  are deterministic (pure functions of the pair analysis), layer-scoped
  (``layer`` is one of :data:`TEXT_BLOCK_LAYERS`) and source-linked
  (``evidence_ids`` reference the pair-layer/warning evidence ids the T6
  ledger materializes). The block schema IS the response-text contract;
  no readiness claim for downstream consumption is made anywhere (D4).
- AC-008c: warnings surface as dedicated ``WARNING`` blocks, and the
  blocked-language safeguard is ACTIVE: :func:`guard_text` runs over
  EVERY string a block emits, at construction time.
- AC-007e: the lexical guard rejects the contract §0.4 phrases (EN + DE
  hardening) and score language — see :data:`BLOCKED_PHRASES` and
  :data:`SCORE_LANGUAGE_PATTERNS`.
- AC-006d: block texts are calculated facts, rule applications,
  source-status markers and warnings only — nothing interpretive, no
  relationship-quality vocabulary, no numeric points (D1/REQ-007).
"""
from __future__ import annotations

import re
from typing import Callable, Dict, Final, List, Optional, Pattern, Set, Tuple

from ..exc import CalculationError
from .pair import PairAnalysis
from .types import (
    PAIR_LAYER_NAMES,
    FactValue,
    PairLayer,
    SourceStatus,
    StatementType,
    TextBlock,
    WarningCode,
    WarningEntry,
)

__all__ = [
    "BLOCKED_PHRASES",
    "SCORE_LANGUAGE_PATTERNS",
    "TEXT_BLOCK_LAYERS",
    "WARNINGS_LAYER",
    "BlockedLanguageError",
    "build_text_blocks",
    "find_blocked_language",
    "guard_text",
    "warning_evidence_id",
]

# Contract §0.4 blocked-language lexicon (AC-007e): spec-mandated EN
# phrases + QA-added DE hardening. Case-insensitive SUBSTRING match over
# every emitted string.
BLOCKED_PHRASES: Final[Tuple[str, ...]] = (
    "perfect match",
    "marriage guarantee",
    "breakup prediction",
    "fate certainty",
    "perfekte übereinstimmung",
    "ehegarantie",
    "trennungsvorhersage",
    "schicksals",
)

# Score language (D1/REQ-007, plan §5 T5): word-level score/point tokens
# plus the T-007-03 numeric-compatibility pattern (``87 points``,
# ``75 %``, ``88/100``). Word boundaries keep longer words (``pointer``,
# ``underscore``) out.
SCORE_LANGUAGE_PATTERNS: Final[Tuple[Pattern[str], ...]] = (
    re.compile(r"\bscores?\b", re.IGNORECASE),
    re.compile(r"\bpoints?\b", re.IGNORECASE),
    re.compile(r"\b\d{1,3}\s*(?:%|/\s*100|points?\b)", re.IGNORECASE),
)

# The scope a warning block is filed under — together with the three MVP
# pair layers this is the complete emitted-layer vocabulary (AC-008a).
WARNINGS_LAYER: Final[str] = "warnings"
TEXT_BLOCK_LAYERS: Final[Tuple[str, ...]] = PAIR_LAYER_NAMES + (WARNINGS_LAYER,)

# Deterministic evidence-id namespace for warnings — the T6 ledger
# materializes exactly one entry per id emitted here (AC-013a), mirroring
# ``pair.pair_layer_evidence_id`` for the pair layers.
_WARNING_EVIDENCE_ID_TEMPLATE: Final[str] = "ev:warning:{subject}:{code}"

# All pair-layer statements describe the pair, not one person.
_PAIR_SUBJECT: Final[str] = "pair"


class BlockedLanguageError(CalculationError):
    """A string headed for the response contains blocked language.

    Raised by :func:`guard_text` (AC-007e). This is an INTERNAL defect —
    the engine tried to emit forbidden vocabulary — so it maps to a 500,
    never to caller-visible advice. Fails loudly instead of silently
    rewording (Development Principle: no masking).
    """

    error_code = "blocked_language"


def find_blocked_language(text: str) -> Optional[str]:
    """Return the offending phrase/pattern match in ``text``, or ``None``.

    Checks the §0.4 lexicon (case-insensitive substring) and the
    score-language patterns (AC-007e / D1).
    """
    lowered = text.lower()
    for phrase in BLOCKED_PHRASES:
        if phrase in lowered:
            return phrase
    for pattern in SCORE_LANGUAGE_PATTERNS:
        match = pattern.search(text)
        if match:
            return match.group(0)
    return None


def guard_text(text: str) -> str:
    """Pass ``text`` through the lexical blocked-language guard (AC-007e).

    Returns:
        ``text`` unchanged when clean.

    Raises:
        BlockedLanguageError: If ``text`` contains a §0.4 phrase or score
            language — the emission must fail visibly, never be reworded.
    """
    found = find_blocked_language(text)
    if found is not None:
        raise BlockedLanguageError(
            f"blocked language {found!r} in emitted string",
            detail={"matched": found},
        )
    return text


def warning_evidence_id(entry: WarningEntry) -> str:
    """Return the stable evidence-ledger id for a warning (AC-013a)."""
    return _WARNING_EVIDENCE_ID_TEMPLATE.format(
        subject=entry.subject, code=entry.code.value
    )


def _fact_value(layer: PairLayer, key: str) -> FactValue:
    """Return the single fact ``key`` of ``layer``, failing loudly."""
    for fact in layer.facts:
        if fact.key == key:
            return fact.value
    raise CalculationError(
        f"pair layer {layer.name!r} carries no fact {key!r}"
    )


def _yes_no(value: FactValue) -> str:
    """Render a boolean comparison fact as ``yes``/``no`` prose."""
    if not isinstance(value, bool):
        raise CalculationError(f"expected a boolean fact, got {value!r}")
    return "yes" if value else "no"


def _join_labels(value: FactValue) -> str:
    """Render a tuple-of-labels fact as a comma-joined list."""
    if not isinstance(value, tuple):
        raise CalculationError(f"expected a tuple fact, got {value!r}")
    return ", ".join(str(item) for item in value)


def _join_weights(value: FactValue) -> str:
    """Render a tuple-of-weights fact with fixed 2-decimal formatting."""
    if not isinstance(value, tuple):
        raise CalculationError(f"expected a tuple fact, got {value!r}")
    return ", ".join(f"{float(item):.2f}" for item in value)


# One layer statement: (statement_type, subject, text, source_status).
_Statement = Tuple[StatementType, str, str, SourceStatus]


def _day_master_statements(layer: PairLayer) -> Tuple[_Statement, ...]:
    """Layer 1 — day-master facts + the Sheng/Ke rule application."""
    facts_text = (
        f"Day master of person_a is {_fact_value(layer, 'person_a_day_master')} "
        f"({_fact_value(layer, 'person_a_element')}); day master of person_b is "
        f"{_fact_value(layer, 'person_b_day_master')} "
        f"({_fact_value(layer, 'person_b_element')}). "
        f"Same stem: {_yes_no(_fact_value(layer, 'same_stem'))}. "
        f"Same element: {_yes_no(_fact_value(layer, 'same_element'))}."
    )
    rule_text = (
        "Wu-Xing day-master relation per the canonical Sheng/Ke cycle: "
        f"{_fact_value(layer, 'day_master_wuxing_relation')}."
    )
    return (
        (
            StatementType.CALCULATED_FACT,
            _PAIR_SUBJECT,
            facts_text,
            SourceStatus.CALCULATED,
        ),
        (
            StatementType.RULE_APPLICATION,
            _PAIR_SUBJECT,
            rule_text,
            SourceStatus.CALCULATED,
        ),
    )


def _spouse_palace_statements(layer: PairLayer) -> Tuple[_Statement, ...]:
    """Layer 2 — identification facts + the honest designation status."""
    facts_text = (
        f"Spouse-palace host pillar: {_fact_value(layer, 'palace_pillar')}. "
        f"Day branch of person_a: {_fact_value(layer, 'person_a_day_branch')} "
        f"(hidden stems: {_join_labels(_fact_value(layer, 'person_a_hidden_stems'))}); "
        f"day branch of person_b: {_fact_value(layer, 'person_b_day_branch')} "
        f"(hidden stems: {_join_labels(_fact_value(layer, 'person_b_hidden_stems'))}). "
        f"Same day branch: {_yes_no(_fact_value(layer, 'same_day_branch'))}."
    )
    status_text = (
        "The day-branch to spouse-palace designation has no domain-approved "
        "ruleset table; this layer is marked "
        f"{SourceStatus.NEEDS_DOMAIN_REVIEW.value}."
    )
    return (
        (
            StatementType.CALCULATED_FACT,
            _PAIR_SUBJECT,
            facts_text,
            SourceStatus.CALCULATED,
        ),
        (
            StatementType.SOURCE_STATUS,
            _PAIR_SUBJECT,
            status_text,
            SourceStatus.NEEDS_DOMAIN_REVIEW,
        ),
    )


def _wuxing_vector_statements(layer: PairLayer) -> Tuple[_Statement, ...]:
    """Layer 3 — both Wu-Xing vectors verbatim, in canonical element order."""
    facts_text = (
        "Wu-Xing vectors in element order "
        f"{_join_labels(_fact_value(layer, 'element_order'))} — person_a: "
        f"{_join_weights(_fact_value(layer, 'person_a_vector'))}; person_b: "
        f"{_join_weights(_fact_value(layer, 'person_b_vector'))}."
    )
    return (
        (
            StatementType.CALCULATED_FACT,
            _PAIR_SUBJECT,
            facts_text,
            SourceStatus.CALCULATED,
        ),
    )


_STATEMENT_BUILDERS: Final[
    Dict[str, Callable[[PairLayer], Tuple[_Statement, ...]]]
] = {
    "day_master_comparison": _day_master_statements,
    "spouse_palace_day_branch": _spouse_palace_statements,
    "wuxing_vector_comparison": _wuxing_vector_statements,
}


def _make_block(
    *,
    block_id: str,
    layer: str,
    statement_type: StatementType,
    subject: str,
    text: str,
    source_status: SourceStatus,
    evidence_ids: Tuple[str, ...],
) -> TextBlock:
    """Construct a block with the guard applied to EVERY string (AC-008c)."""
    for value in (
        block_id,
        layer,
        statement_type.value,
        subject,
        text,
        source_status.value,
        *evidence_ids,
    ):
        guard_text(value)
    return TextBlock(
        id=block_id,
        layer=layer,
        statement_type=statement_type,
        subject=subject,
        text=text,
        source_status=source_status,
        evidence_ids=evidence_ids,
    )


def build_text_blocks(
    pair: PairAnalysis,
    *,
    warnings: Tuple[WarningEntry, ...] = (),
) -> Tuple[TextBlock, ...]:
    """Build the deterministic raw_analysis_text blocks (REQ-008).

    Args:
        pair:     The T4 :class:`~bazi_engine.match.pair.PairAnalysis`;
                  every block text is derived from its layer facts
                  verbatim (source-linked, never recomputed).
        warnings: Surfaced :class:`~bazi_engine.match.types.WarningEntry`
                  items (typically both persons' warnings concatenated);
                  duplicates by ``(code, subject)`` collapse into one
                  block each.

    Returns:
        A tuple of frozen AC-008a blocks: per pair layer its factual
        statements (evidence-linked to that layer's evidence ids), then
        one ``WARNING`` block per unique warning (evidence-linked via
        :func:`warning_evidence_id`). Ids are deterministic and unique;
        every emitted string has passed :func:`guard_text` (AC-007e).
    """
    blocks: List[TextBlock] = []
    for name, layer in pair.layers().items():
        statements = _STATEMENT_BUILDERS[name](layer)
        for ordinal, (statement_type, subject, text, status) in enumerate(
            statements, start=1
        ):
            blocks.append(
                _make_block(
                    block_id=f"blk:{name}:{ordinal:02d}",
                    layer=name,
                    statement_type=statement_type,
                    subject=subject,
                    text=text,
                    source_status=status,
                    evidence_ids=layer.evidence_ids,
                )
            )

    seen: Set[Tuple[WarningCode, str]] = set()
    for entry in warnings:
        dedupe_key = (entry.code, entry.subject)
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        blocks.append(
            _make_block(
                block_id=f"blk:{WARNINGS_LAYER}:{entry.subject}:{entry.code.value}",
                layer=WARNINGS_LAYER,
                statement_type=StatementType.WARNING,
                subject=entry.subject,
                text=f"{entry.code.value}: {entry.message}",
                source_status=SourceStatus.CALCULATED,
                evidence_ids=(warning_evidence_id(entry),),
            )
        )
    return tuple(blocks)
