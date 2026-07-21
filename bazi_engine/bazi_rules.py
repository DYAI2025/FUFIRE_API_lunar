"""FBP-02-001 — Ruleset-driven derivation helpers for the BaZi core.

The BaZi engine reads several values that the ruleset already
declares (``day_cycle_anchor``, ``year_boundary``, ``month_boundary``,
etc.) but historically used hardcoded constants for. This module
exposes typed accessors that derive engine inputs from a loaded
ruleset dict, so ``compute_bazi()`` and ``/validate`` consume a single
source of truth (see DEV-2026-002, DEV-2026-004, DEV-2026-005).

Phase-2 scope (this module): the day-cycle offset derivation. Other
ruleset-driven knobs (year/month boundaries, zi rollover policy) are
follow-up tasks (FBP-02-004, FBP-02-006).

Module hierarchy note: this module imports
``bazi_engine.bafe.ruleset_loader``, which is technically an upward
import per the strict Level-3-only rule in CLAUDE.md. The convention
followed here (and pre-existing in ``bazi.py``) treats
``bafe.ruleset_loader`` as a pure data-loader living *logically* at
the same level as ``bazi.py`` itself — it has no side-effecting
business logic and no router/service dependencies. CLAUDE.md's
"Module Hierarchy" section has a carve-out noting the same. If
``bafe`` ever gains levels-mixed contents, the loader should move
to its own top-level module.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Any, Dict

from .bafe.ruleset_loader import load_ruleset

DEFAULT_RULESET_ID = "standard_bazi_2026"


@lru_cache(maxsize=1)
def load_default_ruleset() -> Dict[str, Any]:
    """Load and cache the default ruleset.

    The cache ensures hot paths in ``compute_bazi()`` don't pay the
    JSON-read cost per request. Cache scope is process-wide; the
    ruleset file is read-only at runtime.

    Tests that need a fresh load can call
    ``load_default_ruleset.cache_clear()``.
    """
    return load_ruleset(DEFAULT_RULESET_ID)


def day_offset_from_ruleset(ruleset: Dict[str, Any]) -> int:
    """Compute the JDN-to-sexagenary-day-index offset from the ruleset.

    The relationship is:

        (jdn + offset) mod 60 == sexagenary_index_at_that_jdn

    so given the anchor (anchor_jdn, anchor_sex_idx):

        offset = (anchor_sex_idx - anchor_jdn) mod 60

    The canonical ruleset (``standard_bazi_2026``) currently yields
    49, matching the historic ``bazi_engine.constants.DAY_OFFSET``.

    Raises
    ------
    KeyError
        if ``day_cycle_anchor`` is absent from the ruleset.
    ValueError
        if ``anchor_type`` is not ``"JDN"`` (DATE-based anchors are
        not supported by this helper — file an FBP-02-002 follow-up
        when needed), or if the anchor fields are not integers.
    """
    if "day_cycle_anchor" not in ruleset:
        raise KeyError(
            "ruleset has no 'day_cycle_anchor' — cannot derive day offset"
        )
    anchor = ruleset["day_cycle_anchor"]

    if not isinstance(anchor, dict):
        raise ValueError(
            "day_cycle_anchor must be a dict; got "
            f"{type(anchor).__name__}"
        )

    anchor_type = anchor.get("anchor_type", "JDN")
    if anchor_type != "JDN":
        raise ValueError(
            f"day_cycle_anchor.anchor_type = {anchor_type!r} is not supported "
            "by day_offset_from_ruleset; only 'JDN' is implemented "
            "(see FBP-02-002 for DATE / other future variants)"
        )

    jdn = anchor.get("anchor_jdn")
    sex_idx = anchor.get("anchor_sexagenary_index_0based")

    # Match bafe.ruleset_loader.day_cycle_anchor_status leniency: a
    # float JDN with no fractional part is accepted and narrowed to
    # int. Truly fractional values raise.
    if isinstance(jdn, float) and jdn.is_integer():
        jdn = int(jdn)
    if isinstance(sex_idx, float) and sex_idx.is_integer():
        sex_idx = int(sex_idx)

    if not isinstance(jdn, int) or isinstance(jdn, bool) \
       or not isinstance(sex_idx, int) or isinstance(sex_idx, bool):
        raise ValueError(
            "day_cycle_anchor must declare integer "
            "'anchor_jdn' and 'anchor_sexagenary_index_0based' "
            "(integer-valued float accepted; fractional rejected)"
        )

    return (sex_idx - jdn) % 60
