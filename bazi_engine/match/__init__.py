"""bazi_engine.match — deterministic BaZi-Hehun pair-analysis engine.

Level 4 subpackage (plan §4.1, docs/plans/2026-07-02-bazi-hehun.md):
imports Levels 0-4 only; NEVER ``routers/*``, ``app``, ``limiter`` or
``services/*``. Pure functions, frozen types, no HTTP shaping — response
formatting is composed at ``routers/match.py`` (plan §4.2).

MVP scope (frozen spec, D1-D7): three pair layers, zero score fields.
"""
from .evidence import build_evidence_ledger
from .individual import (
    DerivedFieldStatus,
    IndividualAnalysis,
    MonthCommand,
    SpousePalaceFacts,
    SpouseStarOccurrence,
    SpouseStarResult,
    analyze_individual,
    build_derived_field_stubs,
)
from .normalize import (
    build_wuxing_ledger,
    normalize_chart,
    stem_element,
    wuxing_vector_from_ledger,
)
from .pair import (
    DAY_MASTER_RELATIONS,
    PairAnalysis,
    analyze_pair,
    classify_day_master_relation,
    pair_layer_evidence_id,
)
from .textblocks import (
    BLOCKED_PHRASES,
    SCORE_LANGUAGE_PATTERNS,
    TEXT_BLOCK_LAYERS,
    WARNINGS_LAYER,
    BlockedLanguageError,
    build_text_blocks,
    find_blocked_language,
    guard_text,
    warning_evidence_id,
)
from .types import (
    MATCH_SCHEMA_VERSION,
    PAIR_LAYER_NAMES,
    EvidenceEntry,
    EvidenceKind,
    Fact,
    FactValue,
    NormalizedChart,
    PairLayer,
    PairLayerName,
    SourceStatus,
    StatementType,
    StemSource,
    TextBlock,
    WarningCode,
    WarningEntry,
    WuxingLedgerEntry,
)

__all__ = [
    "BLOCKED_PHRASES",
    "DAY_MASTER_RELATIONS",
    "MATCH_SCHEMA_VERSION",
    "PAIR_LAYER_NAMES",
    "SCORE_LANGUAGE_PATTERNS",
    "TEXT_BLOCK_LAYERS",
    "WARNINGS_LAYER",
    "BlockedLanguageError",
    "DerivedFieldStatus",
    "EvidenceEntry",
    "EvidenceKind",
    "Fact",
    "FactValue",
    "IndividualAnalysis",
    "MonthCommand",
    "NormalizedChart",
    "PairAnalysis",
    "PairLayer",
    "PairLayerName",
    "SourceStatus",
    "SpousePalaceFacts",
    "SpouseStarOccurrence",
    "SpouseStarResult",
    "StatementType",
    "StemSource",
    "TextBlock",
    "WarningCode",
    "WarningEntry",
    "WuxingLedgerEntry",
    "analyze_individual",
    "analyze_pair",
    "build_derived_field_stubs",
    "build_evidence_ledger",
    "build_text_blocks",
    "build_wuxing_ledger",
    "classify_day_master_relation",
    "find_blocked_language",
    "guard_text",
    "normalize_chart",
    "pair_layer_evidence_id",
    "stem_element",
    "warning_evidence_id",
    "wuxing_vector_from_ledger",
]
