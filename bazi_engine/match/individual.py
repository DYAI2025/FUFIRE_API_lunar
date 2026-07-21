"""match/individual.py — REQ-005: per-person individual chart analysis.

Level 4 (plan §4.1, docs/plans/2026-07-02-bazi-hehun.md). Imports Levels
0-4 only (``constants``, ``bazi_rules``/``bafe.ruleset_loader`` carve-out,
sibling ``match`` modules); NEVER ``routers/*``, ``app``, ``limiter`` or
``services/*``. Pure functions — no I/O beyond the cached ruleset read,
no HTTP shaping.

Binding contract anchors (docs/testing/bazi-hehun.acceptance-tests.md):
- AC-005a: each person gets an :class:`IndividualAnalysis` with Day
  Master, spouse-palace/day-branch facts, month command, Wu-Xing vector,
  source status and warnings — the router (T9) mounts these under
  ``individual.person_a`` / ``individual.person_b``.
- AC-005b: DMS/Yong-Shen (and spouse-star, REQ-005) fields carry BOTH a
  ``source_status`` and a ``confidence`` marker.
- AC-005c (audit F7): missing reviewed thresholds never masquerade as
  tradition-verified facts. Enforced structurally:
  * :class:`DerivedFieldStatus` has NO value field — a fabricated
    DMS/Yong-Shen value is unrepresentable, and its ``__post_init__``
    rejects any verified-looking status while MISSING-003 is open.
  * :class:`SpouseStarResult` (GF-3, docs/plans/2026-07-04-bazi-hehun-
    gender-field.md) is a DEDICATED type, split out of
    ``DerivedFieldStatus`` — it is sometimes computable (gender male/female
    + the sourced Ten-Gods table, ``match.ten_gods``), which the shared,
    permanently value-less ``DerivedFieldStatus`` cannot represent without
    weakening the guard for the still-fully-unsourced DMS/Yong-Shen
    fields. Its own ``__post_init__`` enforces the same discipline:
    ``CALCULATED`` is only reachable with a known ``male``/``female``
    gender; ``divers`` (no sourced convention, MISSING-008) and an absent
    gender (``GENDER_NOT_PROVIDED``) can never produce a value.
  * :class:`SpousePalaceFacts` splits honesty (CHANGE b): the POSITION
    identification (day branch = spouse palace, 日支=夫妻宫) is a standard,
    deterministic BaZi fact ⇒ ``position_source_status = CALCULATED`` with
    a ``position_source_note``; only the INTERPRETATION/designation of that
    palace has no ruleset table (planning note a), so ``source_status``
    stays ``NEEDS_DOMAIN_REVIEW`` — the two are never collapsed into one
    verified status.
- D1/REQ-007: nothing here computes or names a score — spouse-star
  occurrences are a located fact list (pillar + source + stem), never a
  count/rating.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Final, Literal, Optional, Tuple

from ..bafe.ruleset_loader import hidden_stems_for_branch, spouse_star_convention
from ..bazi_rules import load_default_ruleset
from ..constants import BRANCHES
from .normalize import stem_element
from .ten_gods import ten_god_for_stems
from .types import NormalizedChart, SourceStatus, StemSource, WarningEntry, WuxingLedgerEntry

# The REQ-005 derived-field set that stays status-only while the named
# ledger items (docs/governance/bazi-hehun.missing-assumption-blocker-ledger.md)
# are open. Statuses are honest, not decorative:
# - day_master_strength: derivable from month command + ledger, but the
#   thresholds are not domain-approved (MISSING-003) ⇒ NEEDS_DOMAIN_REVIEW.
#   Neither reference doc supplied a seasonal-weight/band table (checked
#   2026-07-04) — still genuinely unsourced, not merely unwired.
# - yong_shen: selection rules need the pending mapping table
#   (MISSING-003) ⇒ PENDING_TABLES. Same 2026-07-04 finding: no
#   selection table in either reference doc.
# spouse_star (GF-3, docs/plans/2026-07-04-bazi-hehun-gender-field.md) moved
# OUT of this stub set into its own SpouseStarResult type below: it is now
# SOMETIMES computable (gender male/female + the sourced Ten-Gods table +
# spouse_star_convention), which the value-less DerivedFieldStatus cannot
# represent by design. Widening DerivedFieldStatus itself would risk
# weakening the guard for day_master_strength/yong_shen, which still have
# ZERO source (MISSING-003) and must stay permanently value-less.
_DERIVED_FIELD_SPECS: Final[Tuple[Tuple[str, SourceStatus, str], ...]] = (
    ("day_master_strength", SourceStatus.NEEDS_DOMAIN_REVIEW, "MISSING-003"),
    ("yong_shen", SourceStatus.PENDING_TABLES, "MISSING-003"),
)

# GF-3/GF-4 spouse_star constants.
_GENDER_NOT_PROVIDED: Final[str] = "GENDER_NOT_PROVIDED"
_MISSING_008: Final[str] = "MISSING-008"  # no sourced divers/non-binary convention
_CALCULATED_CONFIDENCE: Final[float] = 1.0  # both source tables are cited, not estimated
Gender = Literal["male", "female", "divers"]

# No approved source exists for any derived field ⇒ no confidence is
# claimable (AC-005c: never a fabricated value).
_UNRESOLVED_CONFIDENCE: Final[float] = 0.0

# Identification fact (traditional convention, planning note a): the
# spouse palace is hosted by the DAY pillar.
_SPOUSE_PALACE_PILLAR: Final[str] = "day"

# CHANGE (b): the day branch IS the spouse-palace POSITION (日支=夫妻宫) — a
# standard, deterministic BaZi position identification. That POSITION fact is
# CALCULATED; only its INTERPRETATION (compatibility meaning, spouse-star
# derivation) stays deferred (no approved table — MISSING-002/003).
_SPOUSE_PALACE_POSITION_NOTE: Final[str] = (
    "day branch = spouse palace (日支=夫妻宫), "
    "standard BaZi position identification"
)


@dataclass(frozen=True)
class DerivedFieldStatus:
    """AC-005b/c honesty stub for DMS/Yong-Shen/spouse-star fields.

    Carries a ``source_status`` and a ``confidence`` marker and — by
    construction — NO value: while the domain mapping tables are pending
    (MISSING-001..003) there is nothing honest to emit, so a fabricated
    value is unrepresentable.

    Raises:
        ValueError: If constructed with a verified-looking status
            (anything other than ``PENDING_TABLES``/``NEEDS_DOMAIN_REVIEW``)
            — the type itself fails the moment someone "helpfully" fills it.
    """

    field: str
    source_status: SourceStatus
    confidence: float
    blocked_by: str  # open ledger item, e.g. "MISSING-003"

    def __post_init__(self) -> None:
        if self.source_status not in (
            SourceStatus.PENDING_TABLES,
            SourceStatus.NEEDS_DOMAIN_REVIEW,
        ):
            raise ValueError(
                f"Derived field {self.field!r} cannot carry status "
                f"{self.source_status.value!r}: no domain-approved source "
                f"exists ({self.blocked_by}); AC-005c forbids "
                "verified-looking derived fields."
            )


@dataclass(frozen=True)
class SpouseStarOccurrence:
    """One stem in the chart that IS the person's convention god, or its
    disruption-signal counterpart (Tabelle 10) — a LOCATED fact, never a
    count or score (D1)."""

    pillar: str  # "year" | "month" | "day" | "hour"
    source: StemSource
    stem: str
    role: Literal["primary_convention_god", "disruption_signal_god"]


@dataclass(frozen=True)
class SpouseStarResult:
    """Per-person spouse-star result (GF-3, MISSING-007/008-aware).

    Exactly one of three states holds, enforced by ``__post_init__``:

    - ``gender_used is None`` (caller omitted the optional field) ⇒
      ``PENDING_TABLES`` / ``blocked_by="GENDER_NOT_PROVIDED"`` / no
      occurrences — a per-request input gap, not a product-level blocker.
    - ``gender_used == "divers"`` ⇒ ``PENDING_TABLES`` /
      ``blocked_by="MISSING-008"`` / no occurrences — no sourced
      convention exists for this value in either reference doc; NEVER
      falls back to the male/female rule.
    - ``gender_used in ("male", "female")`` ⇒ ``CALCULATED`` / no blocker /
      the real, possibly-empty occurrence list. An empty tuple here is a
      valid computed fact (the convention god simply doesn't appear in
      this chart) — not a fabricated placeholder.
    """

    gender_used: Optional[Gender]
    source_status: SourceStatus
    confidence: float
    blocked_by: str
    occurrences: Tuple[SpouseStarOccurrence, ...]

    def __post_init__(self) -> None:
        if self.gender_used is None:
            valid = (
                self.source_status is SourceStatus.PENDING_TABLES
                and self.blocked_by == _GENDER_NOT_PROVIDED
                and not self.occurrences
            )
        elif self.gender_used == "divers":
            valid = (
                self.source_status is SourceStatus.PENDING_TABLES
                and self.blocked_by == _MISSING_008
                and not self.occurrences
            )
        elif self.gender_used in ("male", "female"):
            valid = self.source_status is SourceStatus.CALCULATED and self.blocked_by == ""
        else:
            raise ValueError(f"Unknown gender_used: {self.gender_used!r}")
        if not valid:
            raise ValueError(
                f"Inconsistent SpouseStarResult: gender_used={self.gender_used!r} "
                f"source_status={self.source_status!r} blocked_by={self.blocked_by!r} "
                f"occurrences={self.occurrences!r} — AC-005c forbids a fabricated or "
                "mismatched combination."
            )


@dataclass(frozen=True)
class MonthCommand:
    """Month command (Yue Ling) — deterministic ruleset facts only.

    ``branch`` is the month pillar's earthly branch; ``principal_qi_stem``
    is the branch's principal hidden stem per the ruleset ordering
    (``principal_central_residual``); ``element`` is that stem's Wu-Xing
    element. All values are pure lookups (ruleset + shared constants) —
    no seasonal-strength assessment (Wang/Xiang/...) is emitted, as that
    would need domain-reviewed tables (MISSING-003).
    """

    branch: str
    branch_index: int
    principal_qi_stem: str
    element: str
    source_status: SourceStatus


@dataclass(frozen=True)
class SpousePalaceFacts:
    """Spouse-palace layer: computed identification facts ONLY (AC-005c/F7).

    Which pillar hosts the palace, which branch that is, and the branch's
    ruleset hidden stems — nothing interpretive, no relationship-quality
    vocabulary.

    CHANGE (b) splits the honesty marker in two so neither is overclaimed:

    - ``position_source_status`` is ``CALCULATED`` and ``position_source_note``
      records that the day branch IS the spouse-palace POSITION (日支=夫妻宫)
      — a standard, deterministic BaZi position identification.
    - ``source_status`` stays ``NEEDS_DOMAIN_REVIEW``: the INTERPRETATION of
      the palace (compatibility meaning, spouse-star derivation) has no
      approved table in the shipped ruleset (planning note a). The deferred
      interpretation marker is never collapsed into the CALCULATED position.
    """

    palace_pillar: str
    day_branch: str
    day_branch_index: int
    hidden_stems: Tuple[str, ...]
    position_source_status: SourceStatus
    position_source_note: str
    source_status: SourceStatus


@dataclass(frozen=True)
class IndividualAnalysis:
    """Per-person individual analysis (REQ-005 / AC-005a).

    ``source_status`` is the status of the COMPUTED layers (day master,
    month command, Wu-Xing vector): ``CALCULATED``. The unsourced layers
    carry their own explicit statuses (``spouse_palace.source_status``,
    ``derived_fields[*].source_status``) and never inherit this one.
    """

    subject: str
    day_master: str
    day_master_element: str
    month_command: MonthCommand
    spouse_palace: SpousePalaceFacts
    wuxing_vector: Tuple[float, ...]
    derived_fields: Tuple[DerivedFieldStatus, ...]
    spouse_star: SpouseStarResult
    source_status: SourceStatus
    warnings: Tuple[WarningEntry, ...]


def _build_month_command(
    chart: NormalizedChart, ruleset: Dict[str, Any]
) -> MonthCommand:
    """Month command from the month branch + ruleset hidden stems."""
    branch_index = chart.pillars.month.branch_index
    branch = BRANCHES[branch_index]
    principal_qi_stem = hidden_stems_for_branch(ruleset, branch)[0]
    return MonthCommand(
        branch=branch,
        branch_index=branch_index,
        principal_qi_stem=principal_qi_stem,
        element=stem_element(principal_qi_stem),
        source_status=SourceStatus.CALCULATED,
    )


def _build_spouse_palace(
    chart: NormalizedChart, ruleset: Dict[str, Any]
) -> SpousePalaceFacts:
    """Spouse-palace identification facts from the day branch + ruleset."""
    branch_index = chart.pillars.day.branch_index
    branch = BRANCHES[branch_index]
    return SpousePalaceFacts(
        palace_pillar=_SPOUSE_PALACE_PILLAR,
        day_branch=branch,
        day_branch_index=branch_index,
        hidden_stems=tuple(hidden_stems_for_branch(ruleset, branch)),
        position_source_status=SourceStatus.CALCULATED,
        position_source_note=_SPOUSE_PALACE_POSITION_NOTE,
        source_status=SourceStatus.NEEDS_DOMAIN_REVIEW,
    )


def _spouse_star_occurrences(
    ledger: Tuple[WuxingLedgerEntry, ...],
    ruleset: Dict[str, Any],
    day_master: str,
    gender: Literal["male", "female"],
) -> Tuple[SpouseStarOccurrence, ...]:
    """Scan every visible+hidden stem in the chart (GF-4) for the person's
    convention god or its disruption-signal counterpart (Tabelle 10)."""
    convention = spouse_star_convention(ruleset)
    primary_gods = set(convention[gender])
    disruption_god = convention["disruption_signal"][gender]["god"]
    occurrences = []
    for entry in ledger:
        god = ten_god_for_stems(ruleset, day_master, entry.stem)
        role: Optional[Literal["primary_convention_god", "disruption_signal_god"]]
        if god in primary_gods:
            role = "primary_convention_god"
        elif god == disruption_god:
            role = "disruption_signal_god"
        else:
            role = None
        if role is not None:
            occurrences.append(
                SpouseStarOccurrence(
                    pillar=entry.pillar, source=entry.source, stem=entry.stem, role=role
                )
            )
    return tuple(occurrences)


def _build_spouse_star(
    chart: NormalizedChart, ruleset: Dict[str, Any], gender: Optional[Gender]
) -> SpouseStarResult:
    """Per-person spouse-star result (GF-3/GF-4) — see SpouseStarResult."""
    if gender is None:
        return SpouseStarResult(
            gender_used=None,
            source_status=SourceStatus.PENDING_TABLES,
            confidence=_UNRESOLVED_CONFIDENCE,
            blocked_by=_GENDER_NOT_PROVIDED,
            occurrences=(),
        )
    if gender == "divers":
        return SpouseStarResult(
            gender_used="divers",
            source_status=SourceStatus.PENDING_TABLES,
            confidence=_UNRESOLVED_CONFIDENCE,
            blocked_by=_MISSING_008,
            occurrences=(),
        )
    occurrences = _spouse_star_occurrences(
        chart.wuxing_ledger, ruleset, chart.day_master, gender
    )
    return SpouseStarResult(
        gender_used=gender,
        source_status=SourceStatus.CALCULATED,
        confidence=_CALCULATED_CONFIDENCE,
        blocked_by="",
        occurrences=occurrences,
    )


def build_derived_field_stubs() -> Tuple[DerivedFieldStatus, ...]:
    """The DMS/Yong-Shen/spouse-star status stubs (AC-005b/c).

    Chart-independent while MISSING-002/003 are open: there is no approved
    rule source, so every person gets the same honest status set.
    """
    return tuple(
        DerivedFieldStatus(
            field=name,
            source_status=status,
            confidence=_UNRESOLVED_CONFIDENCE,
            blocked_by=blocked_by,
        )
        for name, status, blocked_by in _DERIVED_FIELD_SPECS
    )


def analyze_individual(
    chart: NormalizedChart,
    *,
    subject: str,
    ruleset: Optional[Dict[str, Any]] = None,
    gender: Optional[Gender] = None,
) -> IndividualAnalysis:
    """Compute the per-person individual analysis (REQ-005).

    Args:
        chart:   The person's :class:`~bazi_engine.match.types.NormalizedChart`
                 (T2 output) — day master, pillars, Wu-Xing vector and
                 warnings are taken from it verbatim, never recomputed.
        subject: Provenance label, e.g. ``"person_a"`` / ``"person_b"``.
        ruleset: Loaded ruleset dict; defaults to the shipped
                 ``standard_bazi_2026`` via the cached
                 ``bazi_rules.load_default_ruleset()``.
        gender:  Optional self-declared gender (GF-1/GF-3); ``None`` when
                 the caller omitted it. Used ONLY to select the sourced
                 spouse-star convention — see :func:`_build_spouse_star`.

    Returns:
        A frozen :class:`IndividualAnalysis` whose computed layers are
        ``CALCULATED`` and whose unsourced layers (spouse-palace
        interpretation, DMS/Yong-Shen) carry explicit
        ``PENDING_TABLES``/``NEEDS_DOMAIN_REVIEW`` statuses with confidence
        0.0 — never fabricated values (AC-005c). ``spouse_star`` is
        sometimes computable (see :class:`SpouseStarResult`).
    """
    active_ruleset: Dict[str, Any] = (
        ruleset if ruleset is not None else load_default_ruleset()
    )
    return IndividualAnalysis(
        subject=subject,
        day_master=chart.day_master,
        day_master_element=stem_element(chart.day_master),
        month_command=_build_month_command(chart, active_ruleset),
        spouse_palace=_build_spouse_palace(chart, active_ruleset),
        wuxing_vector=chart.wuxing_vector,
        derived_fields=build_derived_field_stubs(),
        spouse_star=_build_spouse_star(chart, active_ruleset, gender),
        source_status=SourceStatus.CALCULATED,
        warnings=chart.warnings,
    )
