"""match/evidence.py — REQ-013: the deterministic evidence ledger.

Level 4 (plan §4.1, docs/plans/2026-07-02-bazi-hehun.md). Imports Levels
0-4 only (sibling ``match`` modules); NEVER ``routers/*``, ``app``,
``limiter`` or ``services/*``. Pure functions — no I/O, no HTTP shaping.

Binding contract anchor (docs/testing/bazi-hehun.acceptance-tests.md,
T-013-01 / AC-013a): the response ``evidence_ledger`` carries an entry for
EVERY emitted analysis block and EVERY warning, with no dangling
references and no score contributions (D1). Realized here as a materialized
1:1 map from evidence id → :class:`~bazi_engine.match.types.EvidenceEntry`:

- The emitted text blocks (T5, ``textblocks.build_text_blocks``) reference
  evidence ids drawn from EXACTLY two namespaces — the pair-layer ids
  (``pair.pair_layer_evidence_id``, shared by every block of a layer) and
  the warning ids (``textblocks.warning_evidence_id``, one per unique
  warning). This ledger materializes exactly one entry per distinct id in
  those two namespaces, so every block resolves (T-008-02) and every
  warning is covered, with no orphan entries.
- "exactly one entry per emitted block AND per warning" operates at the
  evidence-id granularity the T4/T5 design already fixed: blocks of one
  pair layer share that layer's single evidence id, so one ledger entry
  covers them; each unique warning has its own id and its own entry.
- No score contribution exists (D1/REQ-007): :class:`EvidenceKind` has no
  score kind, no entry field or value carries a forbidden score key, and
  every emitted string passes the lexical guard (``textblocks.guard_text``).
"""
from __future__ import annotations

from typing import Dict, Final, List, Set, Tuple

from .pair import PairAnalysis
from .textblocks import guard_text, warning_evidence_id
from .types import (
    PAIR_LAYER_NAMES,
    EvidenceEntry,
    EvidenceKind,
    WarningEntry,
)

__all__ = [
    "build_evidence_ledger",
]

# Per-pair-layer evidence metadata (kind, source_ref, description). Keyed by
# the frozen three MVP layer names (D3): the day-master layer is a pure
# Sheng/Ke computation; the spouse-palace and Wu-Xing layers materially
# consult the shipped ruleset (hidden stems / weighting), so they are
# attributed to the ruleset. All are deterministic — none carries a score.
_PAIR_LAYER_EVIDENCE: Final[Dict[str, Tuple[EvidenceKind, str, str]]] = {
    "day_master_comparison": (
        EvidenceKind.COMPUTATION,
        "bazi_engine.match.pair.analyze_pair#day_master_comparison",
        "Day-master stems, elements and the Sheng/Ke relation computed "
        "deterministically from both charts.",
    ),
    "spouse_palace_day_branch": (
        EvidenceKind.RULESET,
        "bazi_engine.match.pair.analyze_pair#spouse_palace_day_branch",
        "Day-branch identities and ruleset hidden stems; the spouse-palace "
        "designation is NEEDS_DOMAIN_REVIEW.",
    ),
    "wuxing_vector_comparison": (
        EvidenceKind.RULESET,
        "bazi_engine.match.pair.analyze_pair#wuxing_vector_comparison",
        "Wu-Xing vectors summed from the normalization ledger — visible "
        "stems plus ruleset/legacy hidden-stem weighting.",
    ),
}

# The layer metadata must cover exactly the frozen MVP layer set — a fourth
# layer (or a rename) fails loudly at import rather than emitting a partial
# ledger (fail-visibly discipline).
assert set(_PAIR_LAYER_EVIDENCE) == set(PAIR_LAYER_NAMES)

# Provenance for warning ledger entries (the warnings are built in T2
# normalization; their ids come from the T5 warning namespace).
_WARNING_SOURCE_REF: Final[str] = "bazi_engine.match.normalize._build_warnings"


def _make_entry(
    *, entry_id: str, kind: EvidenceKind, source_ref: str, description: str
) -> EvidenceEntry:
    """Construct an entry with the lexical guard on EVERY string (D1).

    Mirrors ``textblocks._make_block``: a ledger entry that ever carried
    blocked or score language must fail visibly, never be reworded.
    """
    for value in (entry_id, kind.value, source_ref, description):
        guard_text(value)
    return EvidenceEntry(
        id=entry_id, kind=kind, source_ref=source_ref, description=description
    )


def build_evidence_ledger(
    pair: PairAnalysis,
    warnings: Tuple[WarningEntry, ...] = (),
) -> Tuple[EvidenceEntry, ...]:
    """Materialize the evidence ledger for a pair analysis (AC-013a).

    Args:
        pair:     The T4 :class:`~bazi_engine.match.pair.PairAnalysis`;
                  each layer's ``evidence_ids`` become ledger entries — the
                  same ids the T5 text blocks reference, so every block
                  resolves 1:1.
        warnings: Surfaced :class:`~bazi_engine.match.types.WarningEntry`
                  items (typically both persons' warnings concatenated);
                  duplicates by ``(subject, code)`` collapse to one entry,
                  matching the T5 block de-duplication.

    Returns:
        A tuple of frozen :class:`~bazi_engine.match.types.EvidenceEntry`,
        one per distinct evidence id: first the pair layers (in the frozen
        ``PAIR_LAYER_NAMES`` order), then the unique warnings (in input
        order). Ids are unique; no entry carries a score contribution
        (D1); every emitted string has passed :func:`guard_text`.
    """
    entries: List[EvidenceEntry] = []
    seen: Set[str] = set()

    for name, layer in pair.layers().items():
        kind, source_ref, description = _PAIR_LAYER_EVIDENCE[name]
        for evidence_id in layer.evidence_ids:
            if evidence_id in seen:
                continue
            seen.add(evidence_id)
            entries.append(
                _make_entry(
                    entry_id=evidence_id,
                    kind=kind,
                    source_ref=source_ref,
                    description=description,
                )
            )

    for warning in warnings:
        evidence_id = warning_evidence_id(warning)
        if evidence_id in seen:
            continue
        seen.add(evidence_id)
        entries.append(
            _make_entry(
                entry_id=evidence_id,
                kind=EvidenceKind.WARNING,
                source_ref=_WARNING_SOURCE_REF,
                description=(
                    f"{warning.code.value} warning surfaced for "
                    f"{warning.subject}."
                ),
            )
        )

    return tuple(entries)
