"""Public V2 astronomy endpoints."""
from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field
from starlette.requests import Request

from ..limiter import limiter, tier_limit
from ..lunar_state import compute_lunar_state
from ..time_utils import resolve_local_instant

router = APIRouter(prefix="/astronomy", tags=["Astronomy v2"])


class LunarInstantInput(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {
                "datetime_local": "2024-04-08T18:21:00",
                "timezone": "UTC",
                "ambiguousTime": "earlier",
                "nonexistentTime": "error",
            }
        },
    )

    datetime_local: str = Field(
        ...,
        description="Local ISO 8601 datetime without a numeric UTC offset.",
    )
    timezone: str = Field(..., min_length=1, max_length=128, description="IANA timezone name.")
    ambiguousTime: Literal["earlier", "later"] = "earlier"
    nonexistentTime: Literal["error", "shift_forward"] = "error"


class LunarStateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    instant: LunarInstantInput


class ResolvedInstantResponse(BaseModel):
    input_local: str
    resolved_local: str
    utc: str
    timezone: str
    fold: int
    status: Literal["ok", "ambiguous", "nonexistent_shifted"]
    utc_offset_seconds: int
    dst_offset_seconds: int
    timezone_abbreviation: str | None
    adjusted_minutes: int
    warning_code: str | None
    warning: str | None


class CelestialPositionResponse(BaseModel):
    longitude_deg: float
    latitude_deg: float
    distance_au: float
    speed_longitude_deg_per_day: float


class MoonPositionResponse(CelestialPositionResponse):
    distance_km: float


class LunarPhaseResponse(BaseModel):
    id: str
    index: int
    name_en: str
    name_de: str
    center_angle_deg: float
    start_angle_deg: float
    end_angle_deg: float
    progress_within_phase: float
    elongation_deg: float
    phase_angle_deg: float
    illumination_fraction: float
    apparent_elongation_deg: float
    apparent_diameter_deg: float
    apparent_magnitude: float
    horizontal_parallax_deg: float
    trend: Literal["waxing", "waning", "turning"]


class LunationResponse(BaseModel):
    previous_new_moon_jd_ut: float
    previous_new_moon_utc: str
    next_new_moon_jd_ut: float
    next_new_moon_utc: str
    age_days: float
    length_days: float
    progress: float


class LunarMethodResponse(BaseModel):
    id: str
    ephemeris_mode: str
    reference_frame: str
    precision_grade: Literal["high_precision", "degraded"]
    provider_version: str
    ephemeris_lock_id: str | None
    supported_utc_start: str
    supported_utc_end_exclusive: str
    warnings: list[str]


class LunarStateDataResponse(BaseModel):
    jd_ut: float
    sun: CelestialPositionResponse
    moon: MoonPositionResponse
    phase: LunarPhaseResponse
    lunation: LunationResponse
    method: LunarMethodResponse


class LunarStateResponse(BaseModel):
    request_id: str
    schema_version: Literal["lunar-state.v2"]
    instant: ResolvedInstantResponse
    lunar_state: LunarStateDataResponse


def _utc_iso(value: Any) -> str:
    return value.isoformat(timespec="microseconds").replace("+00:00", "Z")


@router.post("/lunar-state", response_model=LunarStateResponse)
@limiter.limit(tier_limit)
def lunar_state_endpoint(request: Request, body: LunarStateRequest) -> dict[str, Any]:
    """Return canonical geocentric Sun/Moon state and eight-phase metrics."""

    item = body.instant
    resolved = resolve_local_instant(
        item.datetime_local,
        item.timezone,
        ambiguous=item.ambiguousTime,
        nonexistent=item.nonexistentTime,
    )
    state = compute_lunar_state(resolved)
    return {
        "request_id": getattr(request.state, "request_id", "unknown"),
        "schema_version": "lunar-state.v2",
        "instant": {
            "input_local": resolved.input_local_iso,
            "resolved_local": resolved.civil_local.isoformat(timespec="microseconds"),
            "utc": _utc_iso(resolved.utc),
            "timezone": resolved.timezone,
            "fold": resolved.fold,
            "status": resolved.status,
            "utc_offset_seconds": resolved.utc_offset_seconds,
            "dst_offset_seconds": resolved.dst_offset_seconds,
            "timezone_abbreviation": resolved.tz_abbrev,
            "adjusted_minutes": resolved.adjusted_minutes,
            "warning_code": resolved.warning_code,
            "warning": resolved.warning,
        },
        "lunar_state": {
            "jd_ut": state.jd_ut,
            "sun": state.sun.__dict__,
            "moon": {**state.moon.__dict__, "distance_km": state.moon_distance_km},
            "phase": {
                "id": state.phase.phase_id,
                "index": state.phase.index,
                "name_en": state.phase.name_en,
                "name_de": state.phase.name_de,
                "center_angle_deg": state.phase.center_angle_deg,
                "start_angle_deg": state.phase.start_angle_deg,
                "end_angle_deg": state.phase.end_angle_deg,
                "progress_within_phase": state.phase.progress_within_phase,
                "elongation_deg": state.phase.elongation_deg,
                "phase_angle_deg": state.phase.phase_angle_deg,
                "illumination_fraction": state.phase.illuminated_fraction,
                "apparent_elongation_deg": state.phase.apparent_elongation_deg,
                "apparent_diameter_deg": state.phenomena.apparent_diameter_deg,
                "apparent_magnitude": state.phenomena.apparent_magnitude,
                "horizontal_parallax_deg": state.phenomena.horizontal_parallax_deg,
                "trend": state.phase.trend,
            },
            "lunation": {
                "previous_new_moon_jd_ut": state.lunation.previous_new_moon_jd_ut,
                "previous_new_moon_utc": _utc_iso(state.lunation.previous_new_moon_utc),
                "next_new_moon_jd_ut": state.lunation.next_new_moon_jd_ut,
                "next_new_moon_utc": _utc_iso(state.lunation.next_new_moon_utc),
                "age_days": state.lunation.age_days,
                "length_days": state.lunation.length_days,
                "progress": state.lunation.progress,
            },
            "method": {
                "id": state.method.method_id,
                "ephemeris_mode": state.method.ephemeris_mode,
                "reference_frame": state.method.reference_frame,
                "precision_grade": state.method.precision_grade,
                "provider_version": state.method.provider_version,
                "ephemeris_lock_id": state.method.ephemeris_lock_id,
                "supported_utc_start": state.method.supported_utc_start,
                "supported_utc_end_exclusive": state.method.supported_utc_end_exclusive,
                "warnings": list(state.method.warnings),
            },
        },
    }
