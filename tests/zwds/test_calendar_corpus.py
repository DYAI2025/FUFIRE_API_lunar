"""ZWDS-P1-04 — independent lunisolar boundary corpus (calendar correctness gate).

Checks :class:`SwissephLunisolarCalendar` (the Swiss-Ephemeris-native, D-1 runtime
provider) against an independently generated boundary corpus. The corpus lives in
``fixtures/lunisolar_boundary_corpus.json`` and was produced offline by
``scripts/zwds/gen_lunisolar_corpus.py`` from the ``sxtwl`` reference library — an
*independent* astronomy-based implementation of the same modern 時憲曆 calendar.

This test reads only the committed JSON: it never imports ``sxtwl`` and never
imports the generator, so it proves the provider needs no third-party lunar
library at runtime (design rule D-1). The corpus adversarially stresses the
leap-month logic across 40 years — every leap month 2000–2040 (a date INTO the
leap month AND in the preceding non-leap month of the same number), 29- vs
30-day month ends, lunar-year transitions, 冬至=month-11 windows, and a broad
monthly baseline scan.

Value-level checks need the real ``.se1`` files, so every corpus assertion is
gated behind ``@pytest.mark.swieph`` (conftest auto-skips when SE1 data is
absent). The corpus is expressed in CST/+8, matching a provider built with
``day_boundary_offset_hours=8``.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Dict, List

import pytest

from bazi_engine.zwds.calendar_provider import build_core_seed_calendar

CST_OFFSET_HOURS = 8

_CORPUS_PATH = Path(__file__).resolve().parent / "fixtures" / "lunisolar_boundary_corpus.json"
_CORPUS: List[Dict[str, object]] = json.loads(_CORPUS_PATH.read_text(encoding="utf-8"))


def _corpus_ids() -> List[str]:
    return [str(row["gregorian"]) for row in _CORPUS]


def test_corpus_is_substantial_and_leap_heavy() -> None:
    """Guard the corpus itself: enough rows, leap coverage, 40-year span."""
    assert len(_CORPUS) >= 200, f"corpus too small: {len(_CORPUS)} rows"
    leap_rows = [r for r in _CORPUS if r["is_leap_month"]]
    assert len(leap_rows) >= 20, f"too few leap rows: {len(leap_rows)}"
    # Every leap month 2000–2040 must appear (repeated number, is_leap True).
    leap_numbers = {(int(r["year_label"]), int(r["month"])) for r in leap_rows}
    assert len(leap_numbers) >= 15, f"leap-month coverage thin: {sorted(leap_numbers)}"
    years = {int(str(r["gregorian"])[:4]) for r in _CORPUS}
    assert min(years) <= 1984 and max(years) >= 2040, f"span too narrow: {min(years)}–{max(years)}"


@pytest.mark.swieph
@pytest.mark.parametrize("row", _CORPUS, ids=_corpus_ids())
def test_provider_matches_corpus(row: Dict[str, object]) -> None:
    """The provider must reproduce every independently generated corpus row."""
    cal = build_core_seed_calendar(day_boundary_offset_hours=CST_OFFSET_HOURS)
    rd = cal.resolve(date.fromisoformat(str(row["gregorian"])))
    assert rd.year_label == row["year_label"], (
        f"{row['gregorian']}: year_label {rd.year_label} != {row['year_label']}"
    )
    assert rd.month == row["month"], (
        f"{row['gregorian']}: month {rd.month} != {row['month']}"
    )
    assert rd.day == row["day"], (
        f"{row['gregorian']}: day {rd.day} != {row['day']}"
    )
    assert rd.is_leap_month == row["is_leap_month"], (
        f"{row['gregorian']}: is_leap_month {rd.is_leap_month} != {row['is_leap_month']}"
    )
