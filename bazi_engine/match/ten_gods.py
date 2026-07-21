"""match/ten_gods.py — Ten-Gods (十神) relation, resolved MISSING-002.

Level 4 (plan §4.1, docs/plans/2026-07-02-bazi-hehun.md). Imports Levels
0-4 only (``constants``, ``wuxing.ke_cycle``, ``bafe.ruleset_loader``
carve-out, sibling ``match`` modules); NEVER ``routers/*``, ``app``,
``limiter`` or ``services/*``. Pure functions — no I/O beyond the ruleset
dict already loaded by the caller.

A Ten God labels a target heavenly stem relative to a day master: the
element relation (same / the element that produces the day master /
the element the day master produces / the element the day master
controls / the element that controls the day master) crossed with
whether the two stems share Yin-Yang polarity. This is a closed,
deterministic function of the Wu-Xing generation and control cycles
(the control cycle is the SAME ``wuxing.ke_cycle.KE_CYCLE`` the engine
already uses elsewhere) plus stem polarity (parity of the stem's index
in ``constants.STEMS``) — nothing here is domain judgment.

Source: ``systematisches_handbuch_der_bazi_hehun_kompatibili.md``,
Tabelle 8 (the explicit 10x10 Shi Shen matrix). The closed rule encoded
in the ruleset's ``ten_gods.relation_to_god`` block was hand-verified
against every cell of the DM=Jia/甲 row (covering all 5 relation types)
and independently reproduced against
``systemische_hehun_kompatibilitaetsanalyse.md``'s two worked charts
(Person A, Person B — both DM=Wu/戊) via the live engine — see
``tests/test_match_ten_gods.py``.
"""
from __future__ import annotations

from typing import Any, Dict, Final

from ..bafe.ruleset_loader import ten_god_for_relation
from ..constants import STEMS
from ..wuxing.ke_cycle import KE_CYCLE, KE_INVERSE
from .normalize import stem_element

_STEM_INDEX: Final[Dict[str, int]] = {name: i for i, name in enumerate(STEMS)}

# Generation cycle (相生): element -> the element it generates. Mirrors the
# cycle already documented in wuxing/constants.py ("Element order follows
# the Wu Xing generative cycle") and used privately in impact_resonance.py.
_SHENG_CYCLE: Final[Dict[str, str]] = {
    "Holz": "Feuer",
    "Feuer": "Erde",
    "Erde": "Metall",
    "Metall": "Wasser",
    "Wasser": "Holz",
}
_SHENG_INVERSE: Final[Dict[str, str]] = {v: k for k, v in _SHENG_CYCLE.items()}


def stem_polarity(stem: str) -> str:
    """"yang" for Jia/Bing/Wu/Geng/Ren (even STEMS index), "yin" otherwise."""
    return "yang" if _STEM_INDEX[stem] % 2 == 0 else "yin"


def element_relation(day_master_element: str, target_element: str) -> str:
    """Classify ``target_element`` relative to ``day_master_element``.

    Returns one of "same", "resource" (target generates the day master),
    "output" (the day master generates target), "wealth" (the day master
    controls target) or "officer" (target controls the day master).
    """
    if target_element == day_master_element:
        return "same"
    if _SHENG_INVERSE.get(day_master_element) == target_element:
        return "resource"
    if _SHENG_CYCLE.get(day_master_element) == target_element:
        return "output"
    if KE_CYCLE.get(day_master_element) == target_element:
        return "wealth"
    if KE_INVERSE.get(day_master_element) == target_element:
        return "officer"
    raise ValueError(
        f"Unclassifiable Wu-Xing relation: {day_master_element!r} -> {target_element!r}"
    )


def ten_god_for_stems(ruleset: Dict[str, Any], day_master_stem: str, target_stem: str) -> str:
    """Ten-God label for ``target_stem`` relative to ``day_master_stem``.

    Both are heavenly stem names from ``constants.STEMS``. Sourced from the
    ruleset's ``ten_gods.relation_to_god`` block (module docstring).
    """
    relation = element_relation(
        stem_element(day_master_stem), stem_element(target_stem)
    )
    same_polarity = stem_polarity(day_master_stem) == stem_polarity(target_stem)
    return ten_god_for_relation(ruleset, relation, same_polarity)
