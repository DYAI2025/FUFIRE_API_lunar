from __future__ import annotations

import json
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from bazi_engine.ephemeris import wrap180
from bazi_engine.lunar_state import (
    EPHEMERIS_LOCK_ID,
    PRIMARY_PHASE_ANGLES,
    compute_lunar_state,
    find_lunar_phase_event_utc,
)
from bazi_engine.time_utils import resolve_local_instant

pytestmark = pytest.mark.swieph

REFERENCE_PATH = (
    Path(__file__).resolve().parent / "fixtures" / "lunar_phase_usno_reference.json"
)


def _utc(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def test_primary_phase_times_match_usno_reference_corpus() -> None:
    corpus = json.loads(REFERENCE_PATH.read_text(encoding="utf-8"))
    tolerance = corpus["provisional_tolerance_seconds"]

    for event in corpus["events"]:
        expected = _utc(event["utc"])
        actual = find_lunar_phase_event_utc(expected, event["phase_id"])
        delta_seconds = abs((actual - expected).total_seconds())
        assert delta_seconds <= tolerance, (
            f"{event['phase_id']} {event['utc']} differs by {delta_seconds:.3f}s"
        )


@pytest.mark.parametrize(
    ("phase_id", "approximate"),
    [
        ("new_moon", "2024-01-11T11:57:00Z"),
        ("first_quarter", "2024-01-18T03:52:00Z"),
        ("full_moon", "2024-01-25T17:54:00Z"),
        ("last_quarter", "2024-01-04T03:30:00Z"),
    ],
)
def test_primary_phase_solver_crosses_target_monotonically(
    phase_id: str, approximate: str
) -> None:
    event = find_lunar_phase_event_utc(_utc(approximate), phase_id)
    before = compute_lunar_state(
        resolve_local_instant(
            (event - timedelta(minutes=2)).replace(tzinfo=None).isoformat(), "UTC"
        )
    )
    after = compute_lunar_state(
        resolve_local_instant(
            (event + timedelta(minutes=2)).replace(tzinfo=None).isoformat(), "UTC"
        )
    )
    target = PRIMARY_PHASE_ANGLES[phase_id]

    assert wrap180(before.phase.elongation_deg - target) < 0.0
    assert wrap180(after.phase.elongation_deg - target) > 0.0


def test_seeded_lunation_invariants_across_supported_range() -> None:
    rng = random.Random(20260721)
    start = datetime(1900, 2, 1, tzinfo=timezone.utc)
    span_days = (datetime(2099, 12, 1, tzinfo=timezone.utc) - start).days

    for _ in range(48):
        instant = start + timedelta(
            days=rng.randrange(span_days),
            seconds=rng.randrange(86_400),
        )
        resolved = resolve_local_instant(
            instant.replace(tzinfo=None).isoformat(), "UTC"
        )
        state = compute_lunar_state(resolved)

        assert state.method.ephemeris_mode == "SWIEPH"
        assert state.method.precision_grade == "high_precision"
        assert state.method.ephemeris_lock_id == EPHEMERIS_LOCK_ID
        assert state.lunation.previous_new_moon_jd_ut <= state.jd_ut
        assert state.jd_ut < state.lunation.next_new_moon_jd_ut
        assert 20.0 < state.lunation.length_days < 40.0
        assert 0.0 <= state.lunation.age_days <= state.lunation.length_days
        assert 0.0 <= state.lunation.progress < 1.0
        assert 0.0 <= state.phase.elongation_deg < 360.0
        assert 0.0 <= state.phase.illuminated_fraction <= 1.0
