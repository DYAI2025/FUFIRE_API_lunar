"""match/normalize.py — REQ-004: BaziResult → NormalizedChart.

Level 4 (plan §4.1, docs/plans/2026-07-02-bazi-hehun.md). Imports Levels
0-4 only (``constants``, ``types``, ``bazi_rules``/``bafe.ruleset_loader``
carve-out, ``wuxing``); NEVER ``routers/*``, ``app``, ``limiter`` or
``services/*``. Pure functions — no I/O beyond the cached ruleset read,
no HTTP shaping.

Binding contract anchors (docs/testing/bazi-hehun.acceptance-tests.md):
- AC-004a: ``day_master`` is the DAY pillar's heavenly stem ONLY;
  month/hour stems are carried strictly as provenance labels
  (``month_master_label`` / ``hour_master_label``), never as day_master.
- AC-004b: the Wu-Xing ledger lists visible AND hidden stems, each with a
  source marker (:class:`~bazi_engine.match.types.StemSource`) and a
  numeric weight. Per user DECISION-003 (2026-07-02, pending MISSING-006
  domain review — docs/governance/bazi-hehun.missing-assumption-blocker-
  ledger.md): the hidden-stem WEIGHTING binds to the SAME source the
  existing ``/calculate/wuxing`` endpoint uses (the legacy
  ``wuxing/analysis.py`` ``_BRANCH_HIDDEN`` table, mainstream Ji-Ding-Yi
  for branch Wei) — the product must never disagree with itself. The
  ruleset ``hidden_stems`` (via ``bafe.ruleset_loader``) still provides
  the stem IDENTITIES (the legacy table stores pre-collapsed elements),
  matched to the legacy rows by element, so the ledger stays auditable
  per stem.
- AC-004c: stable warning codes — ``DAY_ANCHOR_UNVERIFIED`` whenever the
  ruleset ``day_cycle_anchor.anchor_verification`` is not ``"verified"``,
  ``BIRTH_TIME_UNKNOWN`` whenever the caller flags the birth time as
  not known. Matched by code, never by prose.
- D1/REQ-007: nothing here computes or names a score.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from ..bafe.ruleset_loader import day_cycle_anchor_status, hidden_stems_for_branch
from ..bazi_rules import load_default_ruleset
from ..constants import BRANCHES, STEMS
from ..types import BaziResult, FourPillars, Pillar

# DECISION-003 (2026-07-02): the hidden-stem weighting source is the SAME
# legacy table /calculate/wuxing computes from — reused, not copied, so the
# two surfaces cannot drift apart. Deliberate private-table import; the loud
# divergence test in tests/test_match_normalization.py pins both sources.
from ..wuxing.analysis import _BRANCH_HIDDEN as _LEGACY_BRANCH_HIDDEN
from ..wuxing.constants import WUXING_INDEX, WUXING_ORDER
from .types import (
    NormalizedChart,
    StemSource,
    WarningCode,
    WarningEntry,
    WuxingLedgerEntry,
)

# Visible heavenly stems contribute with full weight — same convention as
# ``wuxing.analysis.calculate_wuxing_from_bazi_with_ledger`` (stem → 1.0).
_VISIBLE_STEM_WEIGHT: float = 1.0

# Positional hidden-stem Qi roles of the legacy ``_BRANCH_HIDDEN`` rows
# (main/middle/residual Qi — 1.0/0.5/0.3), expressed in the ruleset's
# role vocabulary (``principal``/``central``/``residual``).
_HIDDEN_ROLE_ORDER: Tuple[str, ...] = ("principal", "central", "residual")
_ROLE_TO_SOURCE: Dict[str, StemSource] = {
    "principal": StemSource.HIDDEN_PRINCIPAL,
    "central": StemSource.HIDDEN_CENTRAL,
    "residual": StemSource.HIDDEN_RESIDUAL,
}

_PILLAR_NAMES: Tuple[str, ...] = ("year", "month", "day", "hour")

_STEM_INDEX: Dict[str, int] = {name: i for i, name in enumerate(STEMS)}


def stem_element(stem: str) -> str:
    """Return the Wu-Xing element of a heavenly stem (``WUXING_ORDER`` label).

    Uses the canonical stem/element pairing — consecutive stem pairs map to
    consecutive elements (Jia/Yi→Holz, Bing/Ding→Feuer, Wu/Ji→Erde,
    Geng/Xin→Metall, Ren/Gui→Wasser) — identical to the private mapping in
    ``wuxing/analysis.py``, derived here from the shared constants instead
    of duplicating the table.

    Raises:
        KeyError: If ``stem`` is not one of ``constants.STEMS``.
    """
    return WUXING_ORDER[_STEM_INDEX[stem] // 2]


def build_wuxing_ledger(
    pillars: FourPillars, ruleset: Dict[str, Any]
) -> Tuple[WuxingLedgerEntry, ...]:
    """Build the per-stem Wu-Xing contribution ledger (AC-004b).

    Per pillar: the visible heavenly stem (weight 1.0, source ``visible``)
    plus every hidden stem of the earthly branch. Per user DECISION-003
    (2026-07-02, pending MISSING-006 domain review) the hidden ORDER and
    WEIGHTS bind to the legacy ``wuxing/analysis.py`` ``_BRANCH_HIDDEN``
    table — the same source ``/calculate/wuxing`` computes from — while
    the ruleset ``hidden_stems`` supplies the stem identities (the legacy
    table stores pre-collapsed elements). Stems are matched to the legacy
    ``(element, weight)`` rows by element, a per-branch bijection; row
    position maps to ``hidden_principal``/``hidden_central``/
    ``hidden_residual``.

    Raises:
        ValueError: If the two sources disagree beyond ordering — i.e. a
            branch's ruleset stem elements are not exactly the legacy
            row elements (duplicate, missing or extra) — the ledger must
            fail visibly rather than guess (MISSING-006 discipline).
    """
    entries: List[WuxingLedgerEntry] = []
    for pillar_name in _PILLAR_NAMES:
        pillar: Pillar = getattr(pillars, pillar_name)
        visible_stem = STEMS[pillar.stem_index]
        entries.append(
            WuxingLedgerEntry(
                pillar=pillar_name,
                stem=visible_stem,
                element=stem_element(visible_stem),
                source=StemSource.VISIBLE,
                weight=_VISIBLE_STEM_WEIGHT,
            )
        )

        branch = BRANCHES[pillar.branch_index]
        stem_by_element: Dict[str, str] = {}
        for hidden_stem in hidden_stems_for_branch(ruleset, branch):
            element = stem_element(hidden_stem)
            if element in stem_by_element:
                raise ValueError(
                    f"Ruleset hidden stems for branch {branch!r} carry the "
                    f"element {element!r} twice — cannot match them to the "
                    "legacy weighting rows (DECISION-003/MISSING-006)"
                )
            stem_by_element[element] = hidden_stem

        legacy_rows = _LEGACY_BRANCH_HIDDEN.get(branch)
        if legacy_rows is None:
            raise ValueError(
                f"Legacy wuxing/analysis.py table misses branch {branch!r} "
                "(DECISION-003 weighting source)"
            )
        if {elem for elem, _ in legacy_rows} != set(stem_by_element):
            raise ValueError(
                f"Hidden-stem element sets diverge for branch {branch!r}: "
                f"ruleset {sorted(stem_by_element)!r} vs legacy "
                f"{sorted(elem for elem, _ in legacy_rows)!r} — re-decide "
                "the binding source (DECISION-003/MISSING-006)"
            )
        if len(legacy_rows) > len(_HIDDEN_ROLE_ORDER):
            raise ValueError(
                f"Branch {branch!r} lists more hidden rows than the "
                f"ordering {_HIDDEN_ROLE_ORDER} defines roles for"
            )
        for position, (element, weight) in enumerate(legacy_rows):
            role = _HIDDEN_ROLE_ORDER[position]
            entries.append(
                WuxingLedgerEntry(
                    pillar=pillar_name,
                    stem=stem_by_element[element],
                    element=element,
                    source=_ROLE_TO_SOURCE[role],
                    weight=float(weight),
                )
            )
    return tuple(entries)


def wuxing_vector_from_ledger(
    ledger: Tuple[WuxingLedgerEntry, ...],
) -> Tuple[float, ...]:
    """Sum ledger weights per element, ordered by ``WUXING_ORDER``."""
    values = [0.0] * len(WUXING_ORDER)
    for entry in ledger:
        values[WUXING_INDEX[entry.element]] += entry.weight
    return tuple(values)


def _build_warnings(
    ruleset: Dict[str, Any], *, birth_time_known: bool, subject: str
) -> Tuple[WarningEntry, ...]:
    """AC-004c — stable warning codes for anchor and birth-time status."""
    warnings: List[WarningEntry] = []

    _, verification = day_cycle_anchor_status(ruleset)
    if verification != "verified":
        warnings.append(
            WarningEntry(
                code=WarningCode.DAY_ANCHOR_UNVERIFIED,
                subject="ruleset",
                message=(
                    "Day-cycle anchor is not verified "
                    f"(day_cycle_anchor.anchor_verification={verification!r})."
                ),
            )
        )

    if not birth_time_known:
        warnings.append(
            WarningEntry(
                code=WarningCode.BIRTH_TIME_UNKNOWN,
                subject=subject,
                message=(
                    "Birth time was flagged as not known; the hour pillar "
                    "and hour-derived values are provisional."
                ),
            )
        )
    return tuple(warnings)


def normalize_chart(
    result: BaziResult,
    *,
    birth_time_known: bool = True,
    subject: str = "person",
    ruleset: Optional[Dict[str, Any]] = None,
) -> NormalizedChart:
    """Normalize a computed chart into the canonical structure (REQ-004).

    Args:
        result:           The pure ``compute_bazi()`` output. It embeds the
                          originating :class:`~bazi_engine.types.BaziInput`
                          (``result.input``), so both halves of the
                          "BaziResult + BaziInput" contract arrive here.
        birth_time_known: Caller-provided flag (the engine input carries no
                          such field); ``False`` emits the stable
                          ``BIRTH_TIME_UNKNOWN`` warning (AC-004c).
        subject:          Provenance label for person-scoped warnings,
                          e.g. ``"person_a"`` / ``"person_b"``.
        ruleset:          Loaded ruleset dict; defaults to the shipped
                          ``standard_bazi_2026`` via the cached
                          ``bazi_rules.load_default_ruleset()``.

    Returns:
        A frozen :class:`~bazi_engine.match.types.NormalizedChart` whose
        ``day_master`` is the day pillar's heavenly stem ONLY (AC-004a),
        whose month/hour stems appear strictly as provenance labels, and
        whose Wu-Xing ledger carries visible+hidden stems with source
        markers and weights (AC-004b).
    """
    active_ruleset: Dict[str, Any] = (
        ruleset if ruleset is not None else load_default_ruleset()
    )
    pillars = result.pillars
    ledger = build_wuxing_ledger(pillars, active_ruleset)

    return NormalizedChart(
        pillars=pillars,
        day_master=STEMS[pillars.day.stem_index],
        month_master_label=STEMS[pillars.month.stem_index],
        hour_master_label=STEMS[pillars.hour.stem_index],
        wuxing_ledger=ledger,
        wuxing_vector=wuxing_vector_from_ledger(ledger),
        birth_time_known=birth_time_known,
        warnings=_build_warnings(
            active_ruleset, birth_time_known=birth_time_known, subject=subject
        ),
    )
