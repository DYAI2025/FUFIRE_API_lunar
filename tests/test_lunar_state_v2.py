from __future__ import annotations

from datetime import datetime

import pytest

from bazi_engine.lunar_state import (
    CelestialPosition,
    LunarPhenomena,
    classify_eight_phase,
    compute_lunar_state,
)
from bazi_engine.time_utils import resolve_local_instant


@pytest.mark.parametrize(
    ("angle", "phase_id"),
    [
        (0.0, "new_moon"),
        (45.0, "waxing_crescent"),
        (90.0, "first_quarter"),
        (135.0, "waxing_gibbous"),
        (180.0, "full_moon"),
        (225.0, "waning_gibbous"),
        (270.0, "last_quarter"),
        (315.0, "waning_crescent"),
    ],
)
def test_every_named_phase_is_centred_on_its_event(angle: float, phase_id: str) -> None:
    phase = classify_eight_phase(angle)

    assert phase.phase_id == phase_id
    assert phase.center_angle_deg == angle
    assert phase.progress_within_phase == pytest.approx(0.5)


@pytest.mark.parametrize(
    ("angle", "phase_id", "index"),
    [
        (0.0, "new_moon", 0),
        (22.499999, "new_moon", 0),
        (22.5, "waxing_crescent", 1),
        (67.5, "first_quarter", 2),
        (157.5, "full_moon", 4),
        (202.5, "waning_gibbous", 5),
        (337.5, "new_moon", 0),
        (359.999999, "new_moon", 0),
    ],
)
def test_corrected_eight_phase_classification(
    angle: float, phase_id: str, index: int
) -> None:
    phase = classify_eight_phase(angle)

    assert phase.phase_id == phase_id
    assert phase.index == index
    assert 0.0 <= phase.progress_within_phase < 1.0


class LinearLunarProvider:
    """Deterministic synthetic lunation for orchestration tests."""

    mode = "TEST"
    epoch_jd = 2_460_000.0
    synodic_days = 30.0

    def positions(self, jd_ut: float) -> tuple[CelestialPosition, CelestialPosition]:
        sun_lon = ((jd_ut - self.epoch_jd) * 1.0) % 360.0
        moon_lon = ((jd_ut - self.epoch_jd) * 13.0) % 360.0
        sun = CelestialPosition(sun_lon, 0.0, 1.0, 1.0)
        moon = CelestialPosition(moon_lon, 1.0, 0.00257, 13.0)
        return sun, moon

    def moon_phenomena(self, jd_ut: float) -> LunarPhenomena:
        del jd_ut
        return LunarPhenomena(
            phase_angle_deg=90.0,
            illuminated_fraction=0.5,
            elongation_deg=90.0,
            apparent_diameter_deg=0.5,
            apparent_magnitude=-10.0,
            horizontal_parallax_deg=1.0,
        )


def test_jd_is_derived_once_from_the_canonical_utc_instant() -> None:
    resolved = resolve_local_instant("2024-01-01T12:00:00", "Europe/Berlin")
    calls: list[datetime] = []

    def jd_converter(value: datetime) -> float:
        calls.append(value)
        return LinearLunarProvider.epoch_jd + 7.5

    state = compute_lunar_state(
        resolved,
        provider=LinearLunarProvider(),
        jd_converter=jd_converter,
    )

    assert calls == [resolved.utc]
    assert state.jd_ut == LinearLunarProvider.epoch_jd + 7.5
    assert state.phase.phase_id == "first_quarter"
    assert state.lunation.previous_new_moon_jd_ut == pytest.approx(
        LinearLunarProvider.epoch_jd,
        abs=1e-8,
    )
    assert state.lunation.next_new_moon_jd_ut == pytest.approx(
        LinearLunarProvider.epoch_jd + 30.0,
        abs=1e-8,
    )
    assert state.lunation.age_days == pytest.approx(7.5, abs=1e-8)
    assert state.lunation.progress == pytest.approx(0.25, abs=1e-8)


def test_reference_new_moon_event_is_classified_with_ephemeris() -> None:
    pytest.importorskip("swisseph")
    resolved = resolve_local_instant("2024-04-08T18:21:00", "UTC")
    state = compute_lunar_state(resolved)

    assert state.phase.phase_id == "new_moon"
    assert min(state.phase.elongation_deg, 360.0 - state.phase.elongation_deg) < 1.0
    assert state.phase.illuminated_fraction < 0.01
    assert state.lunation.age_days < 0.1


def test_equivalent_physical_instants_have_identical_lunar_state() -> None:
    berlin = resolve_local_instant("2024-01-01T13:00:00", "Europe/Berlin")
    utc = resolve_local_instant("2024-01-01T12:00:00", "UTC")
    provider = LinearLunarProvider()

    a = compute_lunar_state(berlin, provider=provider)
    b = compute_lunar_state(utc, provider=provider)

    assert berlin.utc == utc.utc
    assert a.jd_ut == b.jd_ut
    assert a.phase.elongation_deg == b.phase.elongation_deg
    assert a.lunation == b.lunation
