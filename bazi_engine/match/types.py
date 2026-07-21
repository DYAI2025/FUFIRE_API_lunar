"""match/types.py — frozen domain types for the BaZi-Hehun pair engine.

Level 4 (see plan §4.1, docs/plans/2026-07-02-bazi-hehun.md). Imports only
Level 0-1 modules (``constants`` transitively via ``types``); NEVER imports
``routers/*``, ``app``, ``limiter`` or ``services/*``.

Binding contract anchors:
- AC-008a: :class:`TextBlock` carries EXACTLY ``id, layer, statement_type,
  subject, text, source_status, evidence_ids`` — this block schema IS the
  response-text contract (D4: no LLM/Fusion interpretation-readiness).
- AC-013a: :class:`EvidenceEntry` — one ledger entry per emitted block and
  per warning; no score contributions exist (D1).
- AC-004c: warning codes are stable constants (:class:`WarningCode`),
  matched by code, never by prose.
- D1/REQ-007: no score field of any kind exists in any type here.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Final, Literal, Tuple, Union

from ..types import FourPillars

# Engine-level schema version of the Hehun MVP contract (plan §4.3).
MATCH_SCHEMA_VERSION: Final[str] = "hehun-mvp-1"

# The EXACT MVP pair-layer set (D3 / AC-006a) — no more, no fewer.
PairLayerName = Literal[
    "day_master_comparison",
    "spouse_palace_day_branch",
    "wuxing_vector_comparison",
]
PAIR_LAYER_NAMES: Final[Tuple[str, ...]] = (
    "day_master_comparison",
    "spouse_palace_day_branch",
    "wuxing_vector_comparison",
)


class SourceStatus(str, Enum):
    """Honesty marker for every emitted value (AC-005b/c, audit F7).

    There is deliberately NO tradition-verified-looking status: a value is
    either a deterministic computation (``CALCULATED``) or explicitly
    unsourced. The two unsourced markers say *why* the value is unsourced:

    - ``PENDING_TABLES`` — the derived field (day_master_strength/yong_shen/
      spouse_star) is NOT "missing" or broken; the domain mapping tables it
      needs are pending delivery (MISSING-001..003). The engine is ready,
      the reviewed lookup tables are not — so ``PENDING_TABLES`` is the
      honest, transparent status. (This member was renamed from ``MISSING``
      as a deliberate post-launch vocabulary refinement.)
    - ``NEEDS_DOMAIN_REVIEW`` — a derivation exists but has not been
      domain-reviewed (e.g. the spouse-palace designation/interpretation).
    """

    CALCULATED = "CALCULATED"  # deterministic astronomical/ruleset computation
    PENDING_TABLES = "PENDING_TABLES"  # domain mapping tables pending delivery (MISSING-001..003)
    NEEDS_DOMAIN_REVIEW = "NEEDS_DOMAIN_REVIEW"  # derivable but unreviewed


class StatementType(str, Enum):
    """The complete factual statement set (AC-006d) — nothing interpretive."""

    CALCULATED_FACT = "CALCULATED_FACT"
    RULE_APPLICATION = "RULE_APPLICATION"
    SOURCE_STATUS = "SOURCE_STATUS"
    WARNING = "WARNING"


class WarningCode(str, Enum):
    """Stable warning codes (AC-004c) — tests match codes, not prose."""

    DAY_ANCHOR_UNVERIFIED = "DAY_ANCHOR_UNVERIFIED"  # ruleset anchor_verification
    BIRTH_TIME_UNKNOWN = "BIRTH_TIME_UNKNOWN"  # birth_time_known=false


class EvidenceKind(str, Enum):
    """What a ledger entry is backed by. No score-contribution kind (D1)."""

    COMPUTATION = "COMPUTATION"  # deterministic engine computation
    RULESET = "RULESET"  # lookup in the shipped ruleset
    WARNING = "WARNING"  # emitted warning condition


class StemSource(str, Enum):
    """Wu-Xing ledger source marker: visible stem vs hidden-stem Qi role.

    Hidden-role names follow the ruleset ``hidden_stems_weighting.role_weights``
    vocabulary (``principal``/``central``/``residual`` in
    ``spec/rulesets/standard_bazi_2026.json``).
    """

    VISIBLE = "visible"
    HIDDEN_PRINCIPAL = "hidden_principal"
    HIDDEN_CENTRAL = "hidden_central"
    HIDDEN_RESIDUAL = "hidden_residual"

    @property
    def is_hidden(self) -> bool:
        return self is not StemSource.VISIBLE


@dataclass(frozen=True)
class WuxingLedgerEntry:
    """One Wu-Xing contribution with source marker and weight (AC-004b).

    ``element`` uses the Wu-Xing package vocabulary
    (``wuxing.constants.WUXING_ORDER``: Holz/Feuer/Erde/Metall/Wasser).
    """

    pillar: str  # "year" | "month" | "day" | "hour"
    stem: str  # heavenly stem label (constants.STEMS)
    element: str
    source: StemSource
    weight: float


@dataclass(frozen=True)
class WarningEntry:
    """A surfaced warning: stable code + subject, prose is informative only."""

    code: WarningCode
    subject: str  # e.g. "person_a" | "person_b" | "ruleset"
    message: str
    evidence_ids: Tuple[str, ...] = field(default=())


@dataclass(frozen=True)
class NormalizedChart:
    """Canonical per-person chart structure (REQ-004).

    ``day_master`` is the DAY pillar's heavenly stem ONLY (AC-004a);
    month/hour stems are carried strictly as provenance labels.
    ``wuxing_vector`` follows ``wuxing.constants.WUXING_ORDER``.
    """

    pillars: FourPillars
    day_master: str
    month_master_label: str
    hour_master_label: str
    wuxing_ledger: Tuple[WuxingLedgerEntry, ...]
    wuxing_vector: Tuple[float, ...]
    birth_time_known: bool
    warnings: Tuple[WarningEntry, ...]


@dataclass(frozen=True)
class TextBlock:
    """AC-008a — exactly these seven fields; this schema IS the contract."""

    id: str
    layer: str
    statement_type: StatementType
    subject: str
    text: str
    source_status: SourceStatus
    evidence_ids: Tuple[str, ...]


@dataclass(frozen=True)
class EvidenceEntry:
    """AC-013a — one ledger entry per emitted block and per warning."""

    id: str
    kind: EvidenceKind
    source_ref: str  # e.g. "bazi_engine.bazi.compute_bazi" or "ruleset:standard_bazi_2026#hidden_stems"
    description: str


FactValue = Union[str, int, float, bool, Tuple[str, ...], Tuple[float, ...]]


@dataclass(frozen=True)
class Fact:
    """A single keyed, source-labelled fact inside a pair layer (AC-006d).

    Numeric values are permitted ONLY as computed facts (e.g. vector
    components); nothing here may be named or presented as a point/score.
    """

    key: str
    value: FactValue
    source_status: SourceStatus = SourceStatus.CALCULATED


@dataclass(frozen=True)
class PairLayer:
    """One of the EXACTLY three MVP pair layers (D3 / AC-006a-d).

    Facts, rule applications and source statuses only — no numeric points,
    no matrix content, no ``MISSING_INTERACTION_TABLE`` stubs (AC-006c).
    """

    name: PairLayerName
    facts: Tuple[Fact, ...]
    source_status: SourceStatus
    evidence_ids: Tuple[str, ...]
