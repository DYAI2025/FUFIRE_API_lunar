"""ZWDS-P1-06 — calendar half of the seed pipeline.

Pins the second half of ZWDS seed resolution: chronometry → lunisolar date →
leap-interpretation month ``m`` → sexagenary year cycle, packaged as the
``resolution.calendar`` contract (:class:`CalendarResolution`) plus the
downstream ``(m, d, y_s, y_b, h-1)`` formula inputs (:class:`ResolvedZwdsSeed`).

The two pure policy functions (leap-split, year-cycle) are ephemeris-free and
run unconditionally. The end-to-end vectors need the lunisolar calendar (hence
Swiss Ephemeris) and are gated behind ``@pytest.mark.swieph`` — conftest
auto-skips them when the ``.se1`` files are absent.

Every lunar date asserted below was computed with the shipped
``SwissephLunisolarCalendar`` (CST / ``day_boundary_offset_hours=8``) and, for
the 1984 vector, cross-checked byte-for-byte against the design-pack
``response_example_core.json`` calendar block.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from bazi_engine.zwds.domain import AnimalId, BranchId, StemId
from bazi_engine.zwds.seed import (
    YEAR_CYCLE_BASIS_POLICY_ID,
    CalendarResolution,
    LunarDate,
    ResolvedZwdsSeed,
    YearCycle,
    effective_month_for_leap_split,
    resolve_calendar_seed,
    resolve_chronometry,
    resolve_seed,
    year_cycle_for_label,
)

_REPO_ROOT = Path(__file__).resolve().parents[2]
_DESIGN_PACK = (
    _REPO_ROOT / "docs" / "zwds" / "design-pack" / "response_example_core.json"
)

# The canonical design-pack vector: 1984-02-01T23:30 Asia/Shanghai, CIVIL,
# late-Zi (advances the chart day 1984-02-01 → 1984-02-02, crossing 甲子 新年).
_SHANGHAI = dict(
    datetime_local="1984-02-01T23:30:00",
    timezone="Asia/Shanghai",
    lat=31.2304,
    lon=121.4737,
    ambiguous_time="earlier",
    nonexistent_time="error",
    time_standard="CIVIL",
)


def _design_pack_calendar() -> dict:
    return json.loads(_DESIGN_PACK.read_text(encoding="utf-8"))["resolution"][
        "calendar"
    ]


def _lunar_date_from_json(block: dict) -> LunarDate:
    return LunarDate(
        year_label=block["year_label"],
        month=block["month"],
        day=block["day"],
        is_leap_month=block["is_leap_month"],
        month_length=block["month_length"],
    )


# ── pure leap-split policy (no ephemeris) ────────────────────────────────────
@pytest.mark.parametrize(
    ("month", "day", "is_leap", "expected"),
    [
        (4, 10, True, 4),  # leap, day ≤ 15 → repeated (same) number
        (4, 20, True, 5),  # leap, day ≥ 16 → next number
        (12, 20, True, 1),  # leap, day ≥ 16 → wrap 12 → 1
        (7, 20, False, 7),  # non-leap → the month itself, regardless of day
        (2, 15, True, 2),  # boundary: day == 15 still repeats
        (2, 16, True, 3),  # boundary: day == 16 rolls forward
    ],
)
def test_effective_month_for_leap_split(
    month: int, day: int, is_leap: bool, expected: int
) -> None:
    assert (
        effective_month_for_leap_split(month=month, day=day, is_leap_month=is_leap)
        == expected
    )


# ── pure year-cycle table (no ephemeris) ─────────────────────────────────────
@pytest.mark.parametrize(
    ("year_label", "stem", "branch", "animal"),
    [
        (1984, StemId.JIA, BranchId.ZI, AnimalId.RAT),  # (1980)%10=0, %12=0
        (2024, StemId.JIA, BranchId.CHEN, AnimalId.DRAGON),  # (2020)%10=0, %12=4
        (2017, StemId.DING, BranchId.YOU, AnimalId.ROOSTER),  # (2013)%10=3, %12=9
    ],
)
def test_year_cycle_for_label(
    year_label: int, stem: StemId, branch: BranchId, animal: AnimalId
) -> None:
    got_stem, got_branch, got_animal = year_cycle_for_label(year_label)
    assert got_stem is stem
    assert got_branch is branch
    assert got_animal is animal


# ── 1984 vector: exact design-pack calendar block ────────────────────────────
@pytest.mark.swieph
def test_1984_vector_lunar_dates_match_design_pack() -> None:
    _, calendar, _ = resolve_seed(**_SHANGHAI)
    expected = _design_pack_calendar()

    assert calendar.chart_lunar_date == LunarDate(1984, 1, 1, False, 30)
    assert calendar.pre_late_zi_lunar_date == LunarDate(1983, 12, 30, False, 30)
    # Byte-for-byte against the vendored contract example.
    assert calendar.chart_lunar_date == _lunar_date_from_json(
        expected["chart_lunar_date"]
    )
    assert calendar.pre_late_zi_lunar_date == _lunar_date_from_json(
        expected["pre_late_zi_lunar_date"]
    )
    # Real engine tag (the design pack's is the synthetic "EXAMPLE_ONLY").
    assert calendar.calendar_engine_id == "fufire-swisseph-shixian.v1"
    assert isinstance(calendar, CalendarResolution)


@pytest.mark.swieph
def test_1984_vector_year_cycle_matches_design_pack() -> None:
    _, calendar, seed = resolve_seed(**_SHANGHAI)
    expected_yc = _design_pack_calendar()["year_cycle"]

    assert calendar.year_cycle == YearCycle(
        stem_id="JIA",
        branch_id="ZI",
        basis_policy_id="lunar-year.guide-v1",
    )
    assert calendar.year_cycle.stem_id == expected_yc["stem_id"]
    assert calendar.year_cycle.branch_id == expected_yc["branch_id"]
    assert calendar.year_cycle.basis_policy_id == expected_yc["basis_policy_id"]
    assert calendar.year_cycle.basis_policy_id == YEAR_CYCLE_BASIS_POLICY_ID
    # year_animal_id lives on the downstream seed, not the calendar block.
    assert seed.year_animal_id is AnimalId.RAT


@pytest.mark.swieph
def test_1984_vector_resolved_seed() -> None:
    chronometry, calendar, seed = resolve_seed(**_SHANGHAI)

    assert calendar.effective_month_for_chart == 1
    assert calendar.leap_month_policy_id == "split-after-day-15.guide-v1"

    assert seed == ResolvedZwdsSeed(
        month=1,
        day=1,
        year_stem_index=0,
        year_branch_index=0,
        hour_branch_index=0,  # ZI, equals spec's (h - 1)
        year_animal_id=AnimalId.RAT,
    )
    # hour_branch_index is the 0-based branch index of the chronometry hour branch.
    assert seed.hour_branch_index == int(BranchId[chronometry.hour_branch_id])


@pytest.mark.swieph
def test_resolve_seed_chains_chronometry_unchanged() -> None:
    chronometry, _, _ = resolve_seed(**_SHANGHAI)
    direct = resolve_chronometry(**_SHANGHAI)
    assert chronometry == direct
    # resolve_calendar_seed alone reproduces the chained calendar/seed halves.
    cal_a, seed_a = resolve_calendar_seed(direct)
    _, cal_b, seed_b = resolve_seed(**_SHANGHAI)
    assert cal_a == cal_b
    assert seed_a == seed_b


# ── 2023 leap-month vector: leap 闰二月, day ≥ 16 → effective month 3 ──────────
@pytest.mark.swieph
def test_2023_leap_second_month_rolls_forward() -> None:
    # 2023-04-10 (CST, non-late-Zi hour) lands in 闰二月 (leap 2nd), day 20.
    _, calendar, seed = resolve_seed(
        datetime_local="2023-04-10T14:30:00",
        timezone="Asia/Shanghai",
        lat=31.2304,
        lon=121.4737,
        ambiguous_time="earlier",
        nonexistent_time="error",
        time_standard="CIVIL",
    )

    assert calendar.chart_lunar_date.is_leap_month is True
    assert calendar.chart_lunar_date.month == 2
    assert calendar.chart_lunar_date.day >= 16
    # leap + day ≥ 16 → next month number.
    assert calendar.effective_month_for_chart == 3
    assert seed.month == 3
    assert seed.day == calendar.chart_lunar_date.day
