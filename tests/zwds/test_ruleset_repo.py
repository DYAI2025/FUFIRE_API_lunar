"""ZWDS-P1-16 — immutable, hash-locked ruleset repository.

Ephemeris-free, pure-data tests over
``bazi_engine/data/zwds/rulesets/zwds.fufire.core-seed.v1/`` and its loader
:mod:`bazi_engine.zwds.ruleset_repository`.

Covered:

1. ``load_ruleset`` returns a fully populated :class:`RulesetRef`.
2. The star catalog declares MAJOR_14 + GUIDE_AUX_4 with the correct per-family
   ``source_status`` split (authoritative file).
3. An unknown ruleset id raises the ZWDS ruleset-not-found error.
4. Tampering one component byte (in a tmp copy — never the committed files)
   raises the ZWDS ruleset-integrity-failed error (the hash lock).
5. Two loads return an identical ``ruleset_sha256`` (determinism).
"""

from __future__ import annotations

import json
import re
import shutil

import pytest

from bazi_engine.zwds import ruleset_repository as repo
from bazi_engine.zwds.errors import (
    ZwdsRulesetIntegrityFailedError,
    ZwdsRulesetNotFoundError,
)
from bazi_engine.zwds.ruleset_repository import RulesetRef, load_ruleset

RULESET_ID = "zwds.fufire.core-seed.v1"
_HEX64 = re.compile(r"^[a-f0-9]{64}$")

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


def _load_catalog() -> dict:
    """Read the star catalog exactly as the loader would resolve it."""
    path = repo.RULESETS_DIR / RULESET_ID / "star_catalog.json"
    return json.loads(path.read_bytes())


def test_load_ruleset_returns_full_rulesetref() -> None:
    """A known id loads into a complete RulesetRef with correct scalar fields."""
    ref = load_ruleset(RULESET_ID)

    assert isinstance(ref, RulesetRef)
    assert ref.ruleset_id == RULESET_ID
    assert ref.ruleset_version == "0.1.0"
    assert ref.source_status == "SOURCE_NEEDED"
    assert ref.school_label is None

    # All the disclosed policy / catalog / table ids.
    assert ref.calendar_policy_id == "local-civil-day.v1"
    assert ref.time_policy_id == "civil-latezi-nextday.v1"
    assert ref.leap_month_policy_id == "split-after-day-15.guide-v1"
    assert ref.year_cycle_policy_id == "lunar-year.guide-v1"
    assert ref.star_catalog_id == "core-seed.18.v1"
    assert ref.transformation_table_id == "guide-four-transformations.v1"
    assert ref.age_reckoning_id == "east_asian_nominal.guide-v1"

    # All five sha256 fields are lowercase 64-hex digests.
    for value in (
        ref.ruleset_sha256,
        ref.star_catalog_sha256,
        ref.transformation_table_sha256,
        ref.calendar_policy_sha256,
        ref.time_policy_sha256,
    ):
        assert _HEX64.match(value), value


def test_rulesetref_is_frozen() -> None:
    """RulesetRef is immutable."""
    ref = load_ruleset(RULESET_ID)
    with pytest.raises(Exception) as excinfo:
        ref.ruleset_id = "mutated"  # type: ignore[misc]
    assert type(excinfo.value).__name__ == "FrozenInstanceError"


def test_star_catalog_declares_two_families_with_source_status_split() -> None:
    """MAJOR_14 stars are SOURCE_REVIEWED; GUIDE_AUX_4 stars are SOURCE_NEEDED."""
    catalog = _load_catalog()
    assert catalog["star_catalog_id"] == "core-seed.18.v1"
    assert catalog["declared_families"] == ["MAJOR_14", "GUIDE_AUX_4"]

    stars = catalog["stars"]
    assert len(stars) == 18

    majors = {s["star_id"] for s in stars if s["family_id"] == "MAJOR_14"}
    auxes = {s["star_id"] for s in stars if s["family_id"] == "GUIDE_AUX_4"}
    assert majors == _MAJOR_14
    assert auxes == _GUIDE_AUX_4

    for s in stars:
        if s["family_id"] == "MAJOR_14":
            assert s["source_status"] == "SOURCE_REVIEWED", s
        else:
            assert s["family_id"] == "GUIDE_AUX_4"
            assert s["source_status"] == "SOURCE_NEEDED", s


def test_unknown_ruleset_id_raises_not_found() -> None:
    """An id with no ruleset directory raises the ruleset-not-found error."""
    with pytest.raises(ZwdsRulesetNotFoundError):
        load_ruleset("zwds.does-not-exist.v9")


def test_tampered_component_raises_integrity_failed(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """One flipped byte in any component file trips the hash lock.

    The committed ruleset files are never touched: the loader is pointed at a
    tmp copy whose ``star_catalog.json`` has one appended byte.
    """
    src = repo.RULESETS_DIR / RULESET_ID
    original_catalog_bytes = (src / "star_catalog.json").read_bytes()

    dst_root = tmp_path / "rulesets"
    shutil.copytree(src, dst_root / RULESET_ID)

    tampered = dst_root / RULESET_ID / "star_catalog.json"
    tampered.write_bytes(tampered.read_bytes() + b" ")

    monkeypatch.setattr(repo, "RULESETS_DIR", dst_root)
    with pytest.raises(ZwdsRulesetIntegrityFailedError):
        load_ruleset(RULESET_ID)

    # The committed source file is byte-for-byte unchanged.
    assert (src / "star_catalog.json").read_bytes() == original_catalog_bytes


def test_committed_ruleset_still_loads_after_tamper_test() -> None:
    """The real, committed ruleset passes integrity and loads cleanly."""
    ref = load_ruleset(RULESET_ID)
    assert ref.ruleset_id == RULESET_ID


def test_ruleset_sha256_is_deterministic() -> None:
    """Two independent loads yield an identical overall ruleset_sha256."""
    first = load_ruleset(RULESET_ID)
    second = load_ruleset(RULESET_ID)
    assert first.ruleset_sha256 == second.ruleset_sha256
    assert first == second
