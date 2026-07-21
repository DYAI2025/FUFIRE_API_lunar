from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


def _repo_root_from_here() -> Path:
    # bazi_engine/bafe/ruleset_loader.py -> bazi_engine -> repo root
    here = Path(__file__).resolve()
    return here.parents[2]

def _spec_rulesets_dir() -> Path:
    return _repo_root_from_here() / "spec" / "rulesets"

def load_ruleset(ruleset_id: str) -> Dict[str, Any]:
    # Canonical mapping: id -> filename
    filename = f"{ruleset_id}.json"
    path = _spec_rulesets_dir() / filename
    if not path.exists():
        raise FileNotFoundError(f"Ruleset not found: {ruleset_id} ({path})")
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("ruleset_id") != ruleset_id:
        raise ValueError("Ruleset id mismatch in file")
    return data

def ruleset_version(ruleset: Dict[str, Any]) -> str:
    return str(ruleset.get("ruleset_version", "MISSING"))

def branch_order(ruleset: Dict[str, Any]) -> List[str]:
    bo = ruleset.get("branch_order")
    if not isinstance(bo, list) or len(bo) != 12:
        raise ValueError("ruleset.branch_order must be a 12-item list")
    return [str(x) for x in bo]

def hidden_stems_for_branch(ruleset: Dict[str, Any], branch: str) -> List[str]:
    hs = ruleset.get("hidden_stems", {})
    mapping = hs.get("branch_to_hidden", {})
    if branch not in mapping:
        raise KeyError(f"hidden stems missing for branch: {branch}")
    lst = mapping[branch]
    if not isinstance(lst, list):
        raise TypeError("hidden stems entry must be a list")
    return [str(x) for x in lst]

def _find_group(groups: List[Dict[str, Any]], key_field: str, stem_index: int) -> Dict[str, Any]:
    """Find the table group whose key_field list contains stem_index."""
    for group in groups:
        if stem_index in group[key_field]:
            return group
    raise KeyError(f"No group found for {key_field}={stem_index}")


def month_stem_for_year_stem(
    ruleset: Dict[str, Any], year_stem_index: int, month_index: int
) -> int:
    """Look up month stem index from the ruleset table.

    Parameters
    ----------
    ruleset : loaded ruleset dict
    year_stem_index : 0-9 (Jia..Gui)
    month_index : 0-11 (Yin=0 .. Chou=11)

    Returns
    -------
    int : stem index 0-9
    """
    rule = ruleset["month_stem_rule"]
    group = _find_group(rule["groups"], "year_stems", year_stem_index)
    return int(group["month_stems_by_month_index"][month_index])


def hour_stem_for_day_stem(
    ruleset: Dict[str, Any], day_stem_index: int, hour_branch_index: int
) -> int:
    """Look up hour stem index from the ruleset table.

    Parameters
    ----------
    ruleset : loaded ruleset dict
    day_stem_index : 0-9 (Jia..Gui)
    hour_branch_index : 0-11 (Zi=0 .. Hai=11)

    Returns
    -------
    int : stem index 0-9
    """
    rule = ruleset["hour_stem_rule"]
    group = _find_group(rule["groups"], "day_stems", day_stem_index)
    return int(group["hour_stems_by_hour_branch"][hour_branch_index])


def ten_god_for_relation(ruleset: Dict[str, Any], relation: str, same_polarity: bool) -> str:
    """Look up the Ten-God label for a relation (see ``match.ten_gods``).

    Parameters
    ----------
    relation : one of "same", "resource", "output", "wealth", "officer"
    same_polarity : True if day-master and target stem share Yin/Yang polarity
    """
    table = ruleset["ten_gods"]["relation_to_god"]
    key = f"{relation}_element"
    if key not in table:
        raise KeyError(f"ten_gods.relation_to_god missing relation: {relation}")
    polarity_key = "same_polarity" if same_polarity else "diff_polarity"
    return str(table[key][polarity_key])


def spouse_star_convention(ruleset: Dict[str, Any]) -> Dict[str, Any]:
    """Return the ``spouse_star_convention`` block verbatim (raises if absent)."""
    convention = ruleset.get("spouse_star_convention")
    if not isinstance(convention, dict):
        raise KeyError("ruleset carries no spouse_star_convention block")
    return convention


def day_cycle_anchor_status(ruleset: Dict[str, Any]) -> Tuple[Optional[int], str]:
    """
    Returns (anchor_jdn, anchor_verification).
    anchor_jdn may be None if missing.
    """
    anchor = ruleset.get("day_cycle_anchor", {})
    jdn = anchor.get("anchor_jdn", None)
    verification = str(anchor.get("anchor_verification", "MISSING"))
    if isinstance(jdn, int):
        return jdn, verification
    if isinstance(jdn, float) and jdn.is_integer():
        return int(jdn), verification
    return None, verification
