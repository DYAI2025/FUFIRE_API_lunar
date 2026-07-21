"""ZWDS-P1-09 — Five-Elements Bureau from the Ming-palace stem/branch.

Pure-formula tests (design-pack ``zwds_formula_spec.md`` §8). Golden truth:
the Ming palace (stem BING=2, branch YIN=2) resolves to ``FIRE_6``
(``response_example_core.json`` -> chart.five_elements_bureau).
"""

from __future__ import annotations

import pytest

from bazi_engine.zwds.bureau import (
    BUREAU_TABLE,
    Bureau,
    bureau_pair_table,
    five_elements_bureau,
)
from bazi_engine.zwds.domain import BranchId, StemId

_VALID_BUREAU_IDS = {"WOOD_3", "METAL_4", "WATER_2", "FIRE_6", "EARTH_5"}


def _valid_parity(stem0: int, branch0: int) -> bool:
    return (stem0 - branch0) % 2 == 0


def test_all_60_valid_parity_pairs_resolve() -> None:
    """The 60 valid-parity (stem, branch) pairs each resolve to a known bureau."""
    valid = 0
    for stem0 in range(10):
        for branch0 in range(12):
            if not _valid_parity(stem0, branch0):
                continue
            valid += 1
            bureau = five_elements_bureau(stem0, branch0)
            assert isinstance(bureau, Bureau)
            assert bureau.id in _VALID_BUREAU_IDS
            assert bureau.number in (2, 3, 4, 5, 6)
            assert bureau.formula_id == "five-elements-bureau.mnemonic-v1"
            assert bureau.source_status == "SOURCE_REVIEWED"
    assert valid == 60


def test_all_60_invalid_parity_pairs_raise() -> None:
    """The 60 invalid-parity pairs are rejected by the parity guard."""
    invalid = 0
    for stem0 in range(10):
        for branch0 in range(12):
            if _valid_parity(stem0, branch0):
                continue
            invalid += 1
            with pytest.raises(ValueError):
                five_elements_bureau(stem0, branch0)
    assert invalid == 60


def test_example_ming_palace_is_fire_6() -> None:
    """Ming palace (BING, YIN) -> FIRE_6, phase FIRE, number 6 (design-pack)."""
    bureau = five_elements_bureau(int(StemId.BING), int(BranchId.YIN))
    assert bureau.id == "FIRE_6"
    assert bureau.phase_id == "FIRE"
    assert bureau.number == 6
    assert bureau.formula_id == "five-elements-bureau.mnemonic-v1"
    assert bureau.source_status == "SOURCE_REVIEWED"


def test_phase_and_number_consistent_with_id() -> None:
    """Bureau id encodes its phase and number consistently (e.g. FIRE_6)."""
    expected = {
        "WOOD_3": ("WOOD", 3),
        "METAL_4": ("METAL", 4),
        "WATER_2": ("WATER", 2),
        "FIRE_6": ("FIRE", 6),
        "EARTH_5": ("EARTH", 5),
    }
    for stem0 in range(10):
        for branch0 in range(12):
            if not _valid_parity(stem0, branch0):
                continue
            bureau = five_elements_bureau(stem0, branch0)
            phase, number = expected[bureau.id]
            assert bureau.phase_id == phase
            assert bureau.number == number


def test_derived_60_pair_table_matches_formula() -> None:
    """The immutable 60-pair table is exactly reproduced by five_elements_bureau."""
    # Table covers precisely the 60 valid-parity pairs.
    assert len(BUREAU_TABLE) == 60
    expected_pairs = {
        (s, b) for s in range(10) for b in range(12) if _valid_parity(s, b)
    }
    assert set(BUREAU_TABLE) == expected_pairs
    # All five bureaus appear.
    assert set(BUREAU_TABLE.values()) == _VALID_BUREAU_IDS
    # The public function reproduces every table entry.
    for (stem0, branch0), bureau_id in BUREAU_TABLE.items():
        assert five_elements_bureau(stem0, branch0).id == bureau_id
    # The exported builder returns the same immutable snapshot.
    assert bureau_pair_table() == dict(BUREAU_TABLE)
    # Anchor the snapshot with the golden example pair.
    assert BUREAU_TABLE[(int(StemId.BING), int(BranchId.YIN))] == "FIRE_6"


def test_bureau_table_is_immutable() -> None:
    """BUREAU_TABLE must not be mutable in place."""
    with pytest.raises(TypeError):
        BUREAU_TABLE[(0, 0)] = "WOOD_3"  # type: ignore[index]


def test_bureau_is_frozen() -> None:
    """Bureau is an immutable (frozen) dataclass."""
    bureau = five_elements_bureau(int(StemId.BING), int(BranchId.YIN))
    with pytest.raises(Exception) as excinfo:
        bureau.number = 3  # type: ignore[misc]
    assert type(excinfo.value).__name__ == "FrozenInstanceError"
