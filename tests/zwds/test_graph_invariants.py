"""ZWDS-P1-18 — star-graph consistency validation.

Drives ``bazi_engine.zwds.validation.validate_chart_graph`` against the
vendored design-pack ``chart`` example (which must pass) and a deep-copied,
individually-mutated variant per invariant (each of which must raise). The
shared on-disk fixture is never mutated — every mutation works on a
``copy.deepcopy``.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from bazi_engine.zwds.errors import ZwdsGraphInvariantFailedError
from bazi_engine.zwds.validation import validate_chart_graph


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


@pytest.fixture
def example_chart() -> dict:
    return copy.deepcopy(_load_example_chart())


def _palace(chart: dict, role: str) -> dict:
    return next(p for p in chart["palaces"] if p["palace_role_id"] == role)


def test_example_chart_passes(example_chart: dict) -> None:
    assert validate_chart_graph(example_chart) is None


def test_invariant_1_dangling_placement_reference(example_chart: dict) -> None:
    mutated = copy.deepcopy(example_chart)
    # Delete a star from star_placements but keep the palace's reference to it.
    mutated["star_placements"] = [
        p for p in mutated["star_placements"] if p["placement_id"] != "natal:ZI_WEI"
    ]
    with pytest.raises(ZwdsGraphInvariantFailedError) as excinfo:
        validate_chart_graph(mutated)
    assert "palace_placement_reference" in str(excinfo.value)


def test_invariant_1_placement_referenced_by_two_palaces(example_chart: dict) -> None:
    mutated = copy.deepcopy(example_chart)
    # MING has no placements; make it also claim a star owned by JI_E.
    _palace(mutated, "MING")["placement_ids"] = ["natal:ZI_WEI"]
    with pytest.raises(ZwdsGraphInvariantFailedError) as excinfo:
        validate_chart_graph(mutated)
    assert "palace_placement_reference" in str(excinfo.value)


def test_invariant_2_duplicate_placement_id(example_chart: dict) -> None:
    mutated = copy.deepcopy(example_chart)
    mutated["star_placements"].append(copy.deepcopy(mutated["star_placements"][0]))
    with pytest.raises(ZwdsGraphInvariantFailedError) as excinfo:
        validate_chart_graph(mutated)
    assert "duplicate_placement" in str(excinfo.value)


def test_invariant_3_branch_disagreement(example_chart: dict) -> None:
    mutated = copy.deepcopy(example_chart)
    # natal:ZI_WEI is on YOU (palace JI_E); flip its branch so they disagree.
    star = next(
        p for p in mutated["star_placements"] if p["placement_id"] == "natal:ZI_WEI"
    )
    star["branch_id"] = "ZI"
    with pytest.raises(ZwdsGraphInvariantFailedError) as excinfo:
        validate_chart_graph(mutated)
    assert "placement_palace_disagreement" in str(excinfo.value)


def test_invariant_3_palace_role_disagreement(example_chart: dict) -> None:
    mutated = copy.deepcopy(example_chart)
    star = next(
        p for p in mutated["star_placements"] if p["placement_id"] == "natal:ZI_WEI"
    )
    star["palace_role_id"] = "MING"  # still referenced by JI_E
    with pytest.raises(ZwdsGraphInvariantFailedError) as excinfo:
        validate_chart_graph(mutated)
    assert "placement_palace_disagreement" in str(excinfo.value)


def test_invariant_4_sequence_index_not_permutation(example_chart: dict) -> None:
    mutated = copy.deepcopy(example_chart)
    # Duplicate index 0 -> the twelve values are no longer 0..11.
    _palace(mutated, "XIONG_DI")["sequence_index_0"] = 0
    with pytest.raises(ZwdsGraphInvariantFailedError) as excinfo:
        validate_chart_graph(mutated)
    assert "palace_set" in str(excinfo.value)


def test_invariant_4_branches_not_distinct(example_chart: dict) -> None:
    mutated = copy.deepcopy(example_chart)
    # MING and FU_MU both have zero placements; colliding their branches keeps
    # invariant 3 (placement/palace agreement) satisfied so invariant 4 fires.
    _palace(mutated, "FU_MU")["branch_id"] = _palace(mutated, "MING")["branch_id"]
    with pytest.raises(ZwdsGraphInvariantFailedError) as excinfo:
        validate_chart_graph(mutated)
    assert "palace_set" in str(excinfo.value)


def test_invariant_5_missing_families_corrupted(example_chart: dict) -> None:
    mutated = copy.deepcopy(example_chart)
    # declared − emitted is empty, so any non-empty missing set is inconsistent.
    mutated["completeness"]["missing_families"] = ["MAJOR_14"]
    with pytest.raises(ZwdsGraphInvariantFailedError) as excinfo:
        validate_chart_graph(mutated)
    assert "completeness_families" in str(excinfo.value)


def test_invariant_5_emitted_families_mismatch(example_chart: dict) -> None:
    mutated = copy.deepcopy(example_chart)
    # GUIDE_AUX_4 is genuinely present; dropping it from emitted is inconsistent.
    mutated["completeness"]["emitted_families"] = ["MAJOR_14"]
    with pytest.raises(ZwdsGraphInvariantFailedError) as excinfo:
        validate_chart_graph(mutated)
    assert "completeness_families" in str(excinfo.value)
