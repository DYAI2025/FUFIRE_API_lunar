"""ZWDS-P1-02 — Swiss-Ephemeris new-moon (sun–moon conjunction) search.

The lunisolar ZWDS calendar numbers months from true new moons. These tests
pin ``previous_new_moon`` / ``next_new_moon`` against independently known
astronomical new moons (UTC):

    2024-01-11 11:57
    2024-02-09 22:59
    2024-03-10 09:00

All value-level checks are gated behind ``@pytest.mark.swieph`` (they need the
real ``.se1`` files; conftest auto-skips them when the SE1 data is absent and
the suite falls back to MOSEPH). The synodic-spacing test also runs, gated the
same way, since Moshier vs Swiss precision would not change a ±15 min claim but
the marker keeps the CI contract honest.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from bazi_engine.zwds.astro_moon import (
    MEAN_SYNODIC_MONTH,
    next_new_moon,
    previous_new_moon,
)

# Reference new moons (UTC), independently sourced.
NM_2024_01 = datetime(2024, 1, 11, 11, 57, tzinfo=timezone.utc)
NM_2024_02 = datetime(2024, 2, 9, 22, 59, tzinfo=timezone.utc)
NM_2024_03 = datetime(2024, 3, 10, 9, 0, tzinfo=timezone.utc)

TOL_15_MIN = timedelta(minutes=15)
TOL_1_MIN = timedelta(minutes=1)


def _abs_delta(a: datetime, b: datetime) -> timedelta:
    return abs(a - b)


def test_mean_synodic_month_constant() -> None:
    # Sizing constant only — never used as the answer. Sanity-pin the value.
    assert MEAN_SYNODIC_MONTH == pytest.approx(29.530588, abs=1e-6)


@pytest.mark.swieph
def test_next_new_moon_february_2024() -> None:
    seed = datetime(2024, 2, 1, 0, 0, tzinfo=timezone.utc)
    got = next_new_moon(seed)
    assert got.tzinfo is not None and got.utcoffset() == timedelta(0)
    assert _abs_delta(got, NM_2024_02) <= TOL_15_MIN


@pytest.mark.swieph
def test_previous_new_moon_february_2024() -> None:
    seed = datetime(2024, 2, 15, 0, 0, tzinfo=timezone.utc)
    got = previous_new_moon(seed)
    assert got.tzinfo is not None and got.utcoffset() == timedelta(0)
    assert _abs_delta(got, NM_2024_02) <= TOL_15_MIN


@pytest.mark.swieph
def test_next_new_moon_january_2024() -> None:
    seed = datetime(2024, 1, 5, 0, 0, tzinfo=timezone.utc)
    got = next_new_moon(seed)
    assert _abs_delta(got, NM_2024_01) <= TOL_15_MIN


@pytest.mark.swieph
@pytest.mark.parametrize(
    "seed",
    [
        datetime(2024, 1, 5, 0, 0, tzinfo=timezone.utc),
        datetime(2024, 2, 1, 0, 0, tzinfo=timezone.utc),
    ],
)
def test_consecutive_new_moon_spacing_is_synodic(seed: datetime) -> None:
    first = next_new_moon(seed)
    # Step a full day past the first conjunction so the forward scan lands on
    # the *next* one rather than re-finding the same root.
    second = next_new_moon(first + timedelta(days=1))
    spacing_days = (second - first).total_seconds() / 86400.0
    # Physical synodic month varies ~29.18–29.84 d around the 29.53 d mean.
    assert 29.18 <= spacing_days <= 29.84


@pytest.mark.swieph
@pytest.mark.parametrize("seed", [NM_2024_01, NM_2024_02, NM_2024_03])
def test_previous_agrees_with_next_at_same_conjunction(seed: datetime) -> None:
    # Seed just before a new moon; next_new_moon resolves the exact conjunction,
    # and previous_new_moon of that instant must return the SAME conjunction
    # (both bracket the same root), not the previous month's.
    just_before = seed - timedelta(hours=2)
    nm = next_new_moon(just_before)
    back = previous_new_moon(nm)
    assert _abs_delta(back, nm) <= TOL_1_MIN
