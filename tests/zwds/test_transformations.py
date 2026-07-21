"""ZWDS-P1-13 — versioned Four-Transformations (四化) table.

Pure-data tests over the versioned ruleset table
(``bazi_engine/data/zwds/rulesets/zwds.fufire.core-seed.v1/transformations.json``)
and its loader. The golden truth for the JIA row is
``docs/zwds/design-pack/response_example_core.json`` -> ``chart.transformations``.

The table is a SOURCE_NEEDED seed with two documented contested cells
(GENG.HUA_KE, REN.HUA_KE); every response must disclose the table id and its
sha256 (design-pack ``zwds_formula_spec.md`` §12).
"""

from __future__ import annotations

import hashlib

from bazi_engine.zwds.domain import StemId
from bazi_engine.zwds.transformations import (
    TABLE_ID,
    TABLE_PATH,
    TABLE_SHA256,
    Transformation,
    four_transformations,
    transformation_types_by_star,
)

# The 18 core-seed stars: 14 majors ∪ 4 guide auxiliaries.
_MAJOR_14 = {
    "ZI_WEI",
    "TIAN_JI",
    "TAI_YANG",
    "WU_QU",
    "TIAN_TONG",
    "LIAN_ZHEN",
    "TIAN_FU",
    "TAI_YIN",
    "TAN_LANG",
    "JU_MEN",
    "TIAN_XIANG",
    "TIAN_LIANG",
    "QI_SHA",
    "PO_JUN",
}
_GUIDE_AUX_4 = {"ZUO_FU", "YOU_BI", "WEN_QU", "WEN_CHANG"}
_CORE_SEED_18 = _MAJOR_14 | _GUIDE_AUX_4

_TRANSFORMATION_ORDER = ("HUA_LU", "HUA_QUAN", "HUA_KE", "HUA_JI")


def test_example_jia_matches_response_example_core() -> None:
    """JIA (year stem 0) yields exactly the design-pack example's transformations."""
    got = four_transformations(int(StemId.JIA))
    assert [(t.type, t.star_id) for t in got] == [
        ("HUA_LU", "LIAN_ZHEN"),
        ("HUA_QUAN", "PO_JUN"),
        ("HUA_KE", "WU_QU"),
        ("HUA_JI", "TAI_YANG"),
    ]
    for t in got:
        assert isinstance(t, Transformation)
        assert t.source_stem_id == "JIA"
        assert t.table_id == TABLE_ID == "guide-four-transformations.v1"
        assert t.scope == "natal"


def test_all_ten_stems_yield_four_transformations_in_order() -> None:
    """Every stem yields exactly 4 transformations, in the fixed HUA order."""
    for y_s in range(10):
        got = four_transformations(y_s)
        assert len(got) == 4, y_s
        assert tuple(t.type for t in got) == _TRANSFORMATION_ORDER, y_s
        assert all(t.source_stem_id == StemId(y_s).name for t in got), y_s


def test_all_targets_in_core_seed_18_star_set() -> None:
    """Every transformation target star is one of the 18 core-seed stars."""
    for y_s in range(10):
        for t in four_transformations(y_s):
            assert t.star_id in _CORE_SEED_18, (StemId(y_s).name, t.type, t.star_id)


def test_transformation_types_by_star_shape() -> None:
    """The by-star helper maps each target star to its transformation type list."""
    by_star = transformation_types_by_star(int(StemId.JIA))
    assert by_star == {
        "LIAN_ZHEN": ["HUA_LU"],
        "PO_JUN": ["HUA_QUAN"],
        "WU_QU": ["HUA_KE"],
        "TAI_YANG": ["HUA_JI"],
    }
    # Consistency with four_transformations for every stem.
    for y_s in range(10):
        rebuilt: dict[str, list[str]] = {}
        for t in four_transformations(y_s):
            rebuilt.setdefault(t.star_id, []).append(t.type)
        assert transformation_types_by_star(y_s) == rebuilt, y_s


def test_transformation_is_frozen() -> None:
    """Transformation is an immutable (frozen) dataclass."""
    t = four_transformations(0)[0]
    try:
        t.star_id = "X"  # type: ignore[misc]
    except Exception as exc:  # dataclasses.FrozenInstanceError
        assert type(exc).__name__ == "FrozenInstanceError"
    else:  # pragma: no cover - must not reach
        raise AssertionError("Transformation must be frozen")


def test_exposed_sha256_matches_raw_file_bytes() -> None:
    """The exposed sha256 is the digest of the raw table bytes."""
    raw = TABLE_PATH.read_bytes()
    assert TABLE_SHA256 == hashlib.sha256(raw).hexdigest()
    assert len(TABLE_SHA256) == 64


def test_mutating_bytes_changes_sha256() -> None:
    """Any change to the table bytes changes the exposed sha256 (integrity)."""
    raw = TABLE_PATH.read_bytes()
    mutated = raw + b" "  # append one byte
    assert hashlib.sha256(mutated).hexdigest() != TABLE_SHA256
    # a flipped byte anywhere inside also diverges
    flipped = bytearray(raw)
    flipped[0] ^= 0x01
    assert hashlib.sha256(bytes(flipped)).hexdigest() != TABLE_SHA256
