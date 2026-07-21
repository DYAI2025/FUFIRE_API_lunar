"""ZWDS-P1-01 — lunisolar calendar protocol + ResolvedLunarDate.

Interface-only task: no astronomy. Proves the frozen result type validates its
fields and that a structural stub satisfies the ``ChineseLunisolarCalendar``
protocol by duck typing (see design pack §"Calendar provider").
"""

from __future__ import annotations

import dataclasses
from datetime import date
from typing import Protocol, get_type_hints

import pytest

from bazi_engine.zwds.calendar_provider import (
    ChineseLunisolarCalendar,
    ResolvedLunarDate,
)


def test_constructs_and_fields_read_back() -> None:
    rd = ResolvedLunarDate(1984, 1, 1, False, 30, "x")
    assert rd.year_label == 1984
    assert rd.month == 1
    assert rd.day == 1
    assert rd.is_leap_month is False
    assert rd.month_length == 30
    assert rd.calendar_engine_id == "x"


@pytest.mark.parametrize(
    ("month", "day", "month_length"),
    [
        (0, 1, 30),   # month too low
        (13, 1, 30),  # month too high
        (1, 0, 30),   # day too low
        (1, 31, 30),  # day too high
        (1, 1, 28),   # month_length not 29/30
    ],
)
def test_out_of_range_fields_raise_value_error(
    month: int, day: int, month_length: int
) -> None:
    with pytest.raises(ValueError):
        ResolvedLunarDate(1984, month, day, False, month_length, "x")


def test_valid_boundary_values_construct() -> None:
    # Exercise every accepted extreme so validation is not over-strict.
    assert ResolvedLunarDate(2000, 12, 30, True, 29, "id").month_length == 29
    assert ResolvedLunarDate(2000, 12, 1, False, 30, "id").day == 1


def test_protocol_is_a_typing_protocol() -> None:
    assert issubclass(ChineseLunisolarCalendar, Protocol)  # type: ignore[arg-type]
    # ``resolve`` is the sole method of the structural contract.
    hints = get_type_hints(ChineseLunisolarCalendar.resolve)
    assert hints["return"] is ResolvedLunarDate


def test_structural_stub_satisfies_protocol() -> None:
    class _Stub:
        def resolve(self, chart_local_date: date) -> ResolvedLunarDate:
            return ResolvedLunarDate(
                year_label=chart_local_date.year,
                month=1,
                day=1,
                is_leap_month=False,
                month_length=30,
                calendar_engine_id="stub.v0",
            )

    def use(cal: ChineseLunisolarCalendar) -> ResolvedLunarDate:
        return cal.resolve(date(1984, 2, 2))

    resolved = use(_Stub())
    assert resolved.year_label == 1984
    assert resolved.calendar_engine_id == "stub.v0"


def test_frozen_instance_cannot_be_mutated() -> None:
    rd = ResolvedLunarDate(1984, 1, 1, False, 30, "x")
    with pytest.raises(dataclasses.FrozenInstanceError):
        rd.month = 5  # type: ignore[misc]
