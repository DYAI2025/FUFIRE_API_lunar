"""Canonical geocentric lunar state derived from one UTC instant / JD_UT.

This V2 module is deliberately separate from ``phases.lunar_phase``.  The
legacy helper retains its historical approximation and start-angle buckets;
this module uses Swiss Ephemeris positions and phase-centred eight-phase
classification for the public astronomy contract.
"""
from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Protocol

import swisseph as swe

from .ephemeris import (
    SwissEphBackend,
    datetime_utc_to_jd_ut,
    jd_ut_to_datetime_utc,
    norm360,
    wrap180,
)
from .exc import CalculationError, InputError
from .resource_loader import (
    PackageResourceIntegrityError,
    load_json_object_resource,
)
from .time_utils import ResolvedInstant

AU_KM = 149_597_870.7
METHOD_ID = "canonical-geocentric-lunar-state-v2"
REFERENCE_FRAME = "geocentric_apparent_ecliptic_of_date"
SUPPORTED_UTC_START = datetime(1900, 1, 1, tzinfo=timezone.utc)
SUPPORTED_UTC_END_EXCLUSIVE = datetime(2100, 1, 1, tzinfo=timezone.utc)
PRIMARY_PHASE_ANGLES = {
    "new_moon": 0.0,
    "first_quarter": 90.0,
    "full_moon": 180.0,
    "last_quarter": 270.0,
}

_EPHEMERIS_LOCK = load_json_object_resource(
    "bazi_engine.resources", "ephemeris.lock.json"
)
EPHEMERIS_LOCK_ID = str(_EPHEMERIS_LOCK.get("lock_id", ""))
if len(EPHEMERIS_LOCK_ID) != 64 or any(
    char not in "0123456789abcdef" for char in EPHEMERIS_LOCK_ID
):
    raise PackageResourceIntegrityError(
        "required package resource has an invalid ephemeris lock id: "
        "bazi_engine.resources:ephemeris.lock.json"
    )


@dataclass(frozen=True)
class CelestialPosition:
    longitude_deg: float
    latitude_deg: float
    distance_au: float
    speed_longitude_deg_per_day: float


@dataclass(frozen=True)
class LunarPhenomena:
    phase_angle_deg: float
    illuminated_fraction: float
    elongation_deg: float
    apparent_diameter_deg: float
    apparent_magnitude: float
    horizontal_parallax_deg: float


@dataclass(frozen=True)
class EightPhaseClassification:
    index: int
    phase_id: str
    name_en: str
    name_de: str
    center_angle_deg: float
    start_angle_deg: float
    end_angle_deg: float
    progress_within_phase: float


@dataclass(frozen=True)
class LunarPhaseMetrics(EightPhaseClassification):
    elongation_deg: float
    phase_angle_deg: float
    illuminated_fraction: float
    apparent_elongation_deg: float
    trend: str


@dataclass(frozen=True)
class LunationMetrics:
    previous_new_moon_jd_ut: float
    previous_new_moon_utc: datetime
    next_new_moon_jd_ut: float
    next_new_moon_utc: datetime
    age_days: float
    length_days: float
    progress: float


@dataclass(frozen=True)
class LunarMethod:
    method_id: str
    ephemeris_mode: str
    reference_frame: str
    precision_grade: str
    provider_version: str
    ephemeris_lock_id: str | None
    supported_utc_start: str
    supported_utc_end_exclusive: str
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class LunarState:
    resolved: ResolvedInstant
    jd_ut: float
    sun: CelestialPosition
    moon: CelestialPosition
    moon_distance_km: float
    phase: LunarPhaseMetrics
    phenomena: LunarPhenomena
    lunation: LunationMetrics
    method: LunarMethod


class LunarEphemerisProvider(Protocol):
    mode: str

    def positions(self, jd_ut: float) -> tuple[CelestialPosition, CelestialPosition]: ...

    def moon_phenomena(self, jd_ut: float) -> LunarPhenomena: ...


_PHASES: tuple[tuple[str, str, str], ...] = (
    ("new_moon", "New Moon", "Neumond"),
    ("waxing_crescent", "Waxing Crescent", "Zunehmende Sichel"),
    ("first_quarter", "First Quarter", "Erstes Viertel"),
    ("waxing_gibbous", "Waxing Gibbous", "Zunehmender Dreiviertelmond"),
    ("full_moon", "Full Moon", "Vollmond"),
    ("waning_gibbous", "Waning Gibbous", "Abnehmender Dreiviertelmond"),
    ("last_quarter", "Last Quarter", "Letztes Viertel"),
    ("waning_crescent", "Waning Crescent", "Abnehmende Sichel"),
)


def classify_eight_phase(elongation_deg: float) -> EightPhaseClassification:
    """Classify by the nearest 45° phase centre using half-open boundaries.

    Named astronomical events are phase centres: new moon is centred at 0°,
    first quarter at 90°, full moon at 180°, and last quarter at 270°.  Thus
    the new-moon bucket spans [337.5°, 360°) ∪ [0°, 22.5°), correcting the
    legacy start-angle classification.
    """

    if not math.isfinite(elongation_deg):
        raise CalculationError("Lunar elongation is not finite.")
    angle = norm360(elongation_deg)
    index = int(((angle + 22.5) % 360.0) // 45.0)
    phase_id, name_en, name_de = _PHASES[index]
    center = float(index * 45)
    start = (center - 22.5) % 360.0
    end = (center + 22.5) % 360.0
    progress = ((angle - start) % 360.0) / 45.0
    return EightPhaseClassification(
        index=index,
        phase_id=phase_id,
        name_en=name_en,
        name_de=name_de,
        center_angle_deg=center,
        start_angle_deg=start,
        end_angle_deg=end,
        progress_within_phase=progress,
    )


class SwissEphLunarProvider:
    """Checked Swiss Ephemeris adapter for geocentric lunar calculations."""

    def __init__(self, backend: SwissEphBackend | None = None) -> None:
        self._backend = backend or SwissEphBackend()
        self.mode = self._backend.mode
        self.version = str(swe.version)

    def positions(self, jd_ut: float) -> tuple[CelestialPosition, CelestialPosition]:
        try:
            sun_raw, _ = self._backend.calc_ut(jd_ut, swe.SUN, extra_flags=swe.FLG_SPEED)
            moon_raw, _ = self._backend.calc_ut(jd_ut, swe.MOON, extra_flags=swe.FLG_SPEED)
        except swe.Error as exc:
            raise CalculationError("Swiss Ephemeris could not calculate Sun/Moon state.") from exc

        sun = CelestialPosition(sun_raw[0], sun_raw[1], sun_raw[2], sun_raw[3])
        moon = CelestialPosition(moon_raw[0], moon_raw[1], moon_raw[2], moon_raw[3])
        _validate_position(sun, "Sun")
        _validate_position(moon, "Moon")
        return sun, moon

    def moon_phenomena(self, jd_ut: float) -> LunarPhenomena:
        try:
            # Attest this exact instant before entering the flag-less pheno_ut
            # class. In SWIEPH mode construction has already verified the SE1
            # files and calc_ut verifies that no MOSEPH fallback occurred.
            self._backend.calc_ut(jd_ut, swe.MOON)
            values = swe.pheno_ut(jd_ut, swe.MOON, self._backend.flags)
        except swe.Error as exc:
            raise CalculationError("Swiss Ephemeris could not calculate lunar phenomena.") from exc
        result = LunarPhenomena(
            phase_angle_deg=values[0],
            illuminated_fraction=values[1],
            elongation_deg=values[2],
            apparent_diameter_deg=values[3],
            apparent_magnitude=values[4],
            horizontal_parallax_deg=values[5],
        )
        _validate_phenomena(result)
        return result


def _validate_position(position: CelestialPosition, body: str) -> None:
    if not all(math.isfinite(value) for value in position.__dict__.values()):
        raise CalculationError(f"Swiss Ephemeris returned non-finite {body} state.")
    if position.distance_au <= 0.0:
        raise CalculationError(f"Swiss Ephemeris returned an invalid {body} distance.")


def _validate_phenomena(phenomena: LunarPhenomena) -> None:
    if not all(math.isfinite(value) for value in phenomena.__dict__.values()):
        raise CalculationError("Swiss Ephemeris returned non-finite lunar phenomena.")
    if not 0.0 <= phenomena.illuminated_fraction <= 1.0:
        raise CalculationError("Swiss Ephemeris returned an invalid illuminated fraction.")


def _elongation_and_speed(
    provider: LunarEphemerisProvider,
    jd_ut: float,
) -> tuple[float, float]:
    sun, moon = provider.positions(jd_ut)
    elongation = norm360(moon.longitude_deg - sun.longitude_deg)
    relative_speed = moon.speed_longitude_deg_per_day - sun.speed_longitude_deg_per_day
    if not math.isfinite(relative_speed) or relative_speed <= 0.0:
        raise CalculationError("Invalid relative Sun/Moon angular speed.")
    return elongation, relative_speed


def _refine_phase_event(
    provider: LunarEphemerisProvider,
    initial_jd_ut: float,
    target_angle_deg: float,
) -> float:
    jd_ut = initial_jd_ut
    for _ in range(15):
        elongation, relative_speed = _elongation_and_speed(provider, jd_ut)
        correction_days = wrap180(elongation - target_angle_deg) / relative_speed
        jd_ut -= correction_days
        # A Julian day around 2.4 million has a float resolution of roughly
        # 4.7e-10 days. Stop above that floor; demanding a smaller correction
        # can repeat the same representable JD forever despite a sub-millisecond
        # and sub-microdegree residual.
        if abs(correction_days) < 1e-8:
            break
    else:
        raise CalculationError("Lunar phase-event search did not converge.")

    residual, _ = _elongation_and_speed(provider, jd_ut)
    if (
        abs(wrap180(residual - target_angle_deg)) > 1e-6
        or not math.isfinite(jd_ut)
    ):
        raise CalculationError("Lunar phase-event search failed its residual check.")
    return jd_ut


def _refine_new_moon(
    provider: LunarEphemerisProvider,
    initial_jd_ut: float,
) -> float:
    return _refine_phase_event(provider, initial_jd_ut, 0.0)


def _validate_supported_utc(value: datetime) -> None:
    if value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise ValueError("Expected aware UTC datetime")
    if not SUPPORTED_UTC_START <= value < SUPPORTED_UTC_END_EXCLUSIVE:
        raise InputError(
            "Lunar State V2 supports UTC instants from 1900-01-01 "
            "through 2099-12-31.",
            detail={
                "supported_utc_start": SUPPORTED_UTC_START.isoformat(),
                "supported_utc_end_exclusive": (
                    SUPPORTED_UTC_END_EXCLUSIVE.isoformat()
                ),
            },
        )


def find_lunar_phase_event_utc(
    approximate_utc: datetime,
    phase_id: str,
    *,
    provider: LunarEphemerisProvider | None = None,
) -> datetime:
    """Refine a nearby primary phase event for reference-corpus validation."""

    _validate_supported_utc(approximate_utc)
    try:
        target = PRIMARY_PHASE_ANGLES[phase_id]
    except KeyError as exc:
        raise ValueError(f"unsupported primary lunar phase: {phase_id!r}") from exc
    active_provider = provider or SwissEphLunarProvider()
    event_jd = _refine_phase_event(
        active_provider,
        datetime_utc_to_jd_ut(approximate_utc),
        target,
    )
    event_utc = jd_ut_to_datetime_utc(event_jd)
    _validate_supported_utc(event_utc)
    return event_utc


def _lunation_metrics(
    provider: LunarEphemerisProvider,
    jd_ut: float,
    elongation_deg: float,
    relative_speed: float,
) -> LunationMetrics:
    previous_guess = jd_ut - elongation_deg / relative_speed
    next_arc = 360.0 - elongation_deg if elongation_deg > 1e-9 else 360.0
    next_guess = jd_ut + next_arc / relative_speed
    previous = _refine_new_moon(provider, previous_guess)
    next_event = _refine_new_moon(provider, next_guess)

    tolerance_days = 1.0 / 86_400.0
    if previous > jd_ut + tolerance_days:
        previous = _refine_new_moon(provider, previous - 29.530588)
    if next_event <= jd_ut + tolerance_days:
        next_event = _refine_new_moon(provider, next_event + 29.530588)

    length = next_event - previous
    age = max(0.0, jd_ut - previous)
    if not 20.0 < length < 40.0 or not 0.0 <= age <= length + tolerance_days:
        raise CalculationError("Calculated lunation interval is outside physical bounds.")
    progress = min(1.0, max(0.0, age / length))
    return LunationMetrics(
        previous_new_moon_jd_ut=previous,
        previous_new_moon_utc=jd_ut_to_datetime_utc(previous),
        next_new_moon_jd_ut=next_event,
        next_new_moon_utc=jd_ut_to_datetime_utc(next_event),
        age_days=age,
        length_days=length,
        progress=progress,
    )


def compute_lunar_state(
    resolved: ResolvedInstant,
    *,
    provider: LunarEphemerisProvider | None = None,
    jd_converter: Callable[[datetime], float] = datetime_utc_to_jd_ut,
) -> LunarState:
    """Compute canonical LunarState from one already-resolved UTC instant."""

    _validate_supported_utc(resolved.utc)
    jd_ut = jd_converter(resolved.utc)
    if not math.isfinite(jd_ut):
        raise CalculationError("Calculated JD_UT is not finite.")

    active_provider = provider or SwissEphLunarProvider()
    sun, moon = active_provider.positions(jd_ut)
    phenomena = active_provider.moon_phenomena(jd_ut)
    _validate_position(sun, "Sun")
    _validate_position(moon, "Moon")
    _validate_phenomena(phenomena)
    elongation = norm360(moon.longitude_deg - sun.longitude_deg)
    relative_speed = moon.speed_longitude_deg_per_day - sun.speed_longitude_deg_per_day
    if not math.isfinite(relative_speed) or relative_speed <= 0.0:
        raise CalculationError("Invalid relative Sun/Moon angular speed.")
    classification = classify_eight_phase(elongation)
    trend = "waxing" if 0.0 < elongation < 180.0 else "waning" if elongation > 180.0 else "turning"
    phase = LunarPhaseMetrics(
        **classification.__dict__,
        elongation_deg=elongation,
        phase_angle_deg=phenomena.phase_angle_deg,
        illuminated_fraction=phenomena.illuminated_fraction,
        apparent_elongation_deg=phenomena.elongation_deg,
        trend=trend,
    )
    lunation = _lunation_metrics(active_provider, jd_ut, elongation, relative_speed)

    warnings: tuple[str, ...] = ()
    precision_grade = "high_precision"
    if active_provider.mode != "SWIEPH":
        precision_grade = "degraded"
        warnings = ("Swiss Ephemeris high-precision SE1 mode was not active.",)
    method = LunarMethod(
        method_id=METHOD_ID,
        ephemeris_mode=active_provider.mode,
        reference_frame=REFERENCE_FRAME,
        precision_grade=precision_grade,
        provider_version=str(getattr(active_provider, "version", "custom")),
        ephemeris_lock_id=(
            EPHEMERIS_LOCK_ID if active_provider.mode == "SWIEPH" else None
        ),
        supported_utc_start=SUPPORTED_UTC_START.isoformat(),
        supported_utc_end_exclusive=SUPPORTED_UTC_END_EXCLUSIVE.isoformat(),
        warnings=warnings,
    )
    return LunarState(
        resolved=resolved,
        jd_ut=jd_ut,
        sun=sun,
        moon=moon,
        moon_distance_km=moon.distance_au * AU_KM,
        phase=phase,
        phenomena=phenomena,
        lunation=lunation,
        method=method,
    )
