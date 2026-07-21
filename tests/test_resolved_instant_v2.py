from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import timedelta

import pytest

from bazi_engine.time_utils import LocalTimeError, resolve_local_instant


def test_berlin_fold_is_preserved_end_to_end() -> None:
    earlier = resolve_local_instant(
        "2024-10-27T02:51:00",
        "Europe/Berlin",
        ambiguous="earlier",
    )
    later = resolve_local_instant(
        "2024-10-27T02:51:00",
        "Europe/Berlin",
        ambiguous="later",
    )

    assert earlier.fold == 0
    assert later.fold == 1
    assert earlier.status == later.status == "ambiguous"
    assert earlier.utc_offset_seconds == 7200
    assert later.utc_offset_seconds == 3600
    assert later.utc - earlier.utc == timedelta(hours=1)
    assert earlier.civil_local.tzinfo is not None
    assert earlier.utc.utcoffset() == timedelta(0)


def test_gap_policy_records_adjustment_without_reparsing() -> None:
    shifted = resolve_local_instant(
        "2024-03-31T02:30:00",
        "Europe/Berlin",
        nonexistent="shift_forward",
    )

    assert shifted.status == "nonexistent_shifted"
    assert shifted.adjusted_minutes == 30
    assert shifted.warning_code == "nonexistent_local_time_shifted"
    assert shifted.civil_local.isoformat() == "2024-03-31T03:00:00+02:00"
    assert shifted.utc.isoformat() == "2024-03-31T01:00:00+00:00"


def test_gap_error_precedes_downstream_calculation() -> None:
    with pytest.raises(LocalTimeError):
        resolve_local_instant(
            "2024-03-31T02:30:00",
            "Europe/Berlin",
            nonexistent="error",
        )


@pytest.mark.parametrize(
    "value",
    ["2024-01-01T12:00:00+01:00", "2024-01-01T11:00:00Z"],
)
def test_offset_bearing_local_input_is_rejected(value: str) -> None:
    with pytest.raises(LocalTimeError, match="offset"):
        resolve_local_instant(value, "Europe/Berlin")


def test_resolved_instant_is_immutable() -> None:
    instant = resolve_local_instant("2024-01-01T12:00:00", "Europe/Berlin")

    with pytest.raises(FrozenInstanceError):
        instant.fold = 1  # type: ignore[misc]
