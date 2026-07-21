"""ZWDS calendar — 中氣 month numbering + no-中氣 leap rule.

Pins the swisseph-native modern Chinese calendar (時憲曆 / Shíxiàn, post-1645)
implemented by :class:`SwissephLunisolarCalendar`:

  * month numbers anchored so the 冬至 (Sun = 270°) month is month 11,
  * the leap month is the first lunation in a 冬至→冬至 span containing no 中氣
    (it repeats the preceding month's number, ``is_leap_month=True``),
  * civil-day boundaries in a fixed local frame (core-seed ``local-civil-day.v1``;
    here CST / ``day_boundary_offset_hours=8`` to match the design-pack Shanghai
    example and the iztro comparator).

All value-level checks are gated behind ``@pytest.mark.swieph``: they need the
real ``.se1`` files (conftest auto-skips when SE1 data is absent). The
construction/protocol check runs unconditionally — it touches no astronomy.

Every asserted lunar date below was computed with this engine and cross-checked
against independently established facts (CST civil calendar):
    - 1984-02-02 → 甲子 year 正月 day 1 (design-pack ``chart_lunar_date``);
    - 2023 has 闰二月 (leap 2nd), 2020 has 闰四月 (leap 4th), 2017 has 闰六月
      (leap 6th) — all confirmed as ``is_leap_month=True`` at the repeated number;
    - 2023-12-25 (after 冬至 2023-12-22) is month 11.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from bazi_engine.zwds.calendar_provider import (
    ChineseLunisolarCalendar,
    ResolvedLunarDate,
    SwissephLunisolarCalendar,
    build_core_seed_calendar,
)

# CST (Asia/Shanghai) civil frame — matches the design-pack example and iztro.
CST_OFFSET_HOURS = 8

_REPO_ROOT = Path(__file__).resolve().parents[2]
_DESIGN_PACK = _REPO_ROOT / "docs" / "zwds" / "design-pack" / "response_example_core.json"


def _cal() -> SwissephLunisolarCalendar:
    return SwissephLunisolarCalendar(day_boundary_offset_hours=CST_OFFSET_HOURS)


# ── construction / protocol (no ephemeris) ───────────────────────────────────
def test_class_satisfies_protocol_and_builder() -> None:
    cal = _cal()
    assert isinstance(cal, ChineseLunisolarCalendar)
    assert cal.calendar_engine_id == "fufire-swisseph-shixian.v1"
    built = build_core_seed_calendar(CST_OFFSET_HOURS)
    assert isinstance(built, SwissephLunisolarCalendar)
    assert built.day_boundary_offset_hours == CST_OFFSET_HOURS


# ── month-1 anchor: matches the design-pack chart_lunar_date ──────────────────
@pytest.mark.swieph
def test_month_1_anchor_matches_design_pack() -> None:
    # Design pack: 1984-02-01T23:30 +08 with late-zi → chart day 1984-02-02,
    # whose chart_lunar_date is the authoritative expected conversion.
    expected = json.loads(_DESIGN_PACK.read_text(encoding="utf-8"))[
        "resolution"
    ]["calendar"]["chart_lunar_date"]

    got = _cal().resolve(date(1984, 2, 2))

    assert got.year_label == expected["year_label"] == 1984
    assert got.month == expected["month"] == 1
    assert got.day == expected["day"] == 1
    assert got.is_leap_month == expected["is_leap_month"] is False
    assert got.month_length == expected["month_length"] == 30


# ── known leap months (verified against this engine, no adjustments) ──────────
@pytest.mark.swieph
@pytest.mark.parametrize(
    ("chart_date", "expected_month", "expected_year_label"),
    [
        (date(2023, 3, 25), 2, 2023),  # 闰二月 (leap 2nd), Mar–Apr 2023
        (date(2020, 5, 25), 4, 2020),  # 闰四月 (leap 4th), May–Jun 2020
        (date(2017, 7, 30), 6, 2017),  # 闰六月 (leap 6th), Jul–Aug 2017
    ],
)
def test_known_leap_months(
    chart_date: date, expected_month: int, expected_year_label: int
) -> None:
    got = _cal().resolve(chart_date)
    assert got.is_leap_month is True
    assert got.month == expected_month  # leap month repeats the preceding number
    assert got.year_label == expected_year_label
    assert 1 <= got.day <= 30
    assert got.month_length in (29, 30)


# ── non-leap sanity: a clearly normal month ───────────────────────────────────
@pytest.mark.swieph
def test_non_leap_normal_month() -> None:
    got = _cal().resolve(date(2024, 6, 10))
    assert got.is_leap_month is False
    assert got.month in (4, 5)  # engine yields 5
    assert got.month == 5
    assert got.year_label == 2024
    assert 1 <= got.day <= 30
    assert got.month_length in (29, 30)


# ── winter-solstice month is month 11 ─────────────────────────────────────────
@pytest.mark.swieph
def test_winter_solstice_month_is_11() -> None:
    # 冬至 2023 fell on 2023-12-22 (CST); a date just after it is in month 11.
    got = _cal().resolve(date(2023, 12, 25))
    assert got.month == 11
    assert got.is_leap_month is False
    assert got.year_label == 2023


# ── day / month_length always valid across a 24-month scan ────────────────────
@pytest.mark.swieph
def test_scan_all_dates_schema_valid() -> None:
    cal = _cal()
    d = date(2023, 1, 15)
    end = date(2024, 12, 15)
    count = 0
    while d <= end:
        got = cal.resolve(d)
        # ResolvedLunarDate would already reject out-of-range fields, but assert
        # explicitly so a regression is a clear failure rather than a raise.
        assert isinstance(got, ResolvedLunarDate)
        assert 1 <= got.month <= 12
        assert 1 <= got.day <= 30
        assert got.month_length in (29, 30)
        assert isinstance(got.is_leap_month, bool)
        count += 1
        # advance ~one Gregorian month
        if d.month == 12:
            d = date(d.year + 1, 1, 15)
        else:
            d = date(d.year, d.month + 1, 15)
    assert count == 24


# ── leap month attaches to the preceding number, not a fresh one ──────────────
@pytest.mark.swieph
def test_leap_month_is_a_repeat_not_a_gap() -> None:
    cal = _cal()
    # In 2023 the sequence around the leap is: 2月 → 闰2月 → 3月.
    normal_2 = cal.resolve(date(2023, 3, 15))
    leap_2 = cal.resolve(date(2023, 4, 15))
    normal_3 = cal.resolve(date(2023, 5, 15))
    assert (normal_2.month, normal_2.is_leap_month) == (2, False)
    assert (leap_2.month, leap_2.is_leap_month) == (2, True)
    assert (normal_3.month, normal_3.is_leap_month) == (3, False)
