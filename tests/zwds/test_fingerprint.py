"""ZWDS-P1-17 — deterministic chart fingerprint.

Exercises ``bazi_engine.zwds.trace`` against the vendored design-pack ``chart``
example. The fingerprint must be a 64-hex digest, deterministic across calls,
and order-independent at the dict-KEY level while remaining content-sensitive
to list order and every value.
"""

from __future__ import annotations

import copy
import json
import re
from pathlib import Path
from typing import Any

import pytest

from bazi_engine.zwds.trace import canonical_sha256, chart_fingerprint

HEX64 = re.compile(r"^[a-f0-9]{64}$")


def _repo_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "pyproject.toml").is_file():
            return parent
    raise RuntimeError("could not locate repo root (no pyproject.toml found)")


def _load_example_chart() -> dict:
    path = (
        _repo_root() / "docs" / "zwds" / "design-pack" / "response_example_core.json"
    )
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)["chart"]


def _reorder_keys(obj: Any) -> Any:
    """Rebuild every dict with its keys in reversed insertion order.

    LIST order is preserved (list order is content); only dict-KEY order flips,
    which must NOT change the canonical fingerprint.
    """
    if isinstance(obj, dict):
        return {key: _reorder_keys(obj[key]) for key in reversed(list(obj))}
    if isinstance(obj, list):
        return [_reorder_keys(item) for item in obj]
    return obj


@pytest.fixture
def example_chart() -> dict:
    # Deep copy so no test can mutate the shared on-disk fixture in memory.
    return copy.deepcopy(_load_example_chart())


def test_fingerprint_is_64_lowercase_hex(example_chart: dict) -> None:
    assert HEX64.match(chart_fingerprint(example_chart))


def test_fingerprint_is_deterministic(example_chart: dict) -> None:
    assert chart_fingerprint(example_chart) == chart_fingerprint(example_chart)


def test_key_order_does_not_change_fingerprint(example_chart: dict) -> None:
    reordered = _reorder_keys(example_chart)
    # Sanity: we genuinely changed the top-level key order.
    assert list(reordered) != list(example_chart)
    assert chart_fingerprint(reordered) == chart_fingerprint(example_chart)


def test_mutating_a_star_branch_changes_fingerprint(example_chart: dict) -> None:
    base = chart_fingerprint(example_chart)
    mutated = copy.deepcopy(example_chart)
    star = mutated["star_placements"][0]
    star["branch_id"] = "HAI" if star["branch_id"] != "HAI" else "ZI"
    assert chart_fingerprint(mutated) != base


def test_star_placement_list_order_is_content(example_chart: dict) -> None:
    base = chart_fingerprint(example_chart)
    mutated = copy.deepcopy(example_chart)
    mutated["star_placements"] = list(reversed(mutated["star_placements"]))
    assert chart_fingerprint(mutated) != base


def test_palace_list_order_is_content(example_chart: dict) -> None:
    base = chart_fingerprint(example_chart)
    mutated = copy.deepcopy(example_chart)
    mutated["palaces"] = list(reversed(mutated["palaces"]))
    assert chart_fingerprint(mutated) != base


def test_canonical_sha256_ignores_key_order_not_list_order() -> None:
    a = {"x": 1, "y": [1, 2, 3], "z": {"p": True, "q": None}}
    b = {"z": {"q": None, "p": True}, "y": [1, 2, 3], "x": 1}
    assert canonical_sha256(a) == canonical_sha256(b)
    # List order remains content — reordering the list changes the digest.
    c = {"x": 1, "y": [3, 2, 1], "z": {"p": True, "q": None}}
    assert canonical_sha256(c) != canonical_sha256(a)
