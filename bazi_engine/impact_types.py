"""
impact_types.py — Pydantic models for the /impact/active endpoint.

Level 1 module (alongside types.py). Defines request/response schemas for
natal-relative planet impact calculations per PRD P0-3.
"""
from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

# ── Enums as Literals ───────────────────────────────────────────────────────

WuXingElement = Literal["wood", "fire", "earth", "metal", "water"]
ResonanceType = Literal["gleichklang", "naehrung", "kontrolle", "neutral"]
ResonanceIntensity = Literal["gering", "mittel", "stark"]
Strength = Literal["high", "medium", "low"]
DayMode = Literal["calm", "active", "tense", "pulse"]
DriverLevel = Literal["calm", "active", "tense"]


# ── Request ─────────────────────────────────────────────────────────────────

class BirthData(BaseModel):
    """Birth data required for natal chart calculation."""

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    date: str = Field(
        ..., pattern=r"^\d{4}-\d{2}-\d{2}$", description="ISO date, e.g. 1990-05-23"
    )
    time: str = Field(
        default="12:00",
        pattern=r"^\d{2}:\d{2}(:\d{2})?$",
        description="Local time HH:MM or HH:MM:SS. Defaults to 12:00 if unknown.",
    )
    tz: str = Field(..., description="IANA timezone, e.g. Europe/Berlin")
    lat: float = Field(..., ge=-90, le=90, description="Latitude in decimal degrees")
    lon: float = Field(..., ge=-180, le=180, description="Longitude in decimal degrees")

    @field_validator("tz")
    @classmethod
    def _validate_timezone(cls, v: str) -> str:
        from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

        try:
            ZoneInfo(v)
        except (ZoneInfoNotFoundError, KeyError):
            raise ValueError(f"Unknown IANA timezone: {v!r}")
        return v


class ImpactRequest(BaseModel):
    """Request body for POST /impact/active."""

    model_config = ConfigDict(frozen=True)

    birth: BirthData
    soulprint_sectors: Optional[Dict[str, float]] = Field(
        default=None,
        description="Wu-Xing sector weights from soulprint (wood, fire, earth, metal, water).",
    )
    quiz_sectors: Optional[Dict[str, float]] = Field(
        default=None,
        description="Wu-Xing sector weights from onboarding quiz.",
    )
    target_date: Optional[date] = Field(
        default=None,
        description="Date to calculate impacts for. Defaults to today (UTC).",
    )
    locale: str = Field(
        default="de",
        description="Locale for labels. Currently 'de' or 'en'.",
    )

    @field_validator("soulprint_sectors", "quiz_sectors")
    @classmethod
    def _validate_sector_keys(cls, v: Optional[Dict[str, float]]) -> Optional[Dict[str, float]]:
        if v is None:
            return v
        valid = {"wood", "fire", "earth", "metal", "water"}
        invalid = set(v.keys()) - valid
        if invalid:
            raise ValueError(f"Invalid sector keys: {invalid}. Must be: {valid}")
        return v


# ── Response sub-models ─────────────────────────────────────────────────────

class BaziResonance(BaseModel):
    """BaZi resonance between a transiting planet and the natal day master."""

    model_config = ConfigDict(frozen=True)

    element: WuXingElement = Field(..., description="Wu-Xing element")
    type: ResonanceType = Field(
        ..., description="Resonance type relative to day master"
    )
    intensity: ResonanceIntensity = Field(
        ..., description="Resonance intensity derived from orb and weight"
    )


class ActivePlanet(BaseModel):
    """A planet with a significant transit aspect to a natal position."""

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    planet: str = Field(..., min_length=1, description="Planet name, e.g. 'mars', 'jupiter'")
    aspect: str = Field(
        ..., min_length=1, description="Aspect name, e.g. 'conjunction', 'opposition', 'trine'"
    )
    orb: float = Field(..., ge=0, description="Orb in degrees (distance from exact aspect)")
    strength: Strength = Field(
        ..., description="high (<3 deg), medium (3-5 deg), low (5-8 deg)"
    )
    is_retrograde: bool = Field(..., description="Whether the transiting planet is retrograde")
    natal_position: float = Field(
        ..., ge=0, lt=360, description="Natal planet ecliptic longitude in degrees"
    )
    transit_position: float = Field(
        ..., ge=0, lt=360, description="Current transit ecliptic longitude in degrees"
    )
    sector: WuXingElement = Field(
        ..., description="Wu-Xing sector this planet's transit falls into"
    )
    weight: float = Field(
        ..., ge=0, le=1, description="Composite weight (0-1) combining orb, planet rank, aspect type"
    )
    dignity: Optional[str] = Field(
        default=None,
        description="Planetary dignity: domicile, exaltation, detriment, fall, or null (peregrine)",
    )
    bazi_resonance: BaziResonance


class SpaceWeather(BaseModel):
    """NOAA space weather summary."""

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    kp_index: float = Field(..., ge=0, le=9, description="Kp geomagnetic index (0-9)")
    solar_pressure: float = Field(..., ge=0, description="Solar wind dynamic pressure (nPa)")
    storm_active: bool = Field(default=False, description="Whether a geomagnetic storm is active")
    source: str = Field(default="noaa", description="Data source identifier")
    fetched_at: Optional[str] = Field(
        default=None, description="ISO timestamp of last fetch"
    )


class Driver(BaseModel):
    """A single coherence driver for the Driver Strip."""

    model_config = ConfigDict(frozen=True)

    name: str = Field(..., description="Driver name: geomagnetic, solar, transit, day_field")
    level: DriverLevel


class ResonanceBadge(BaseModel):
    """A resonance badge for premium users."""

    model_config = ConfigDict(frozen=True)

    label: str = Field(..., description="Badge label, e.g. 'Feuer-Gleichklang'")
    element: WuXingElement
    type: ResonanceType
    intensity: ResonanceIntensity
    source_planet: str = Field(..., min_length=1, description="Planet that triggered this badge")


class Evidence(BaseModel):
    """Calculation evidence for traceability (Nachvollziehbarkeit)."""

    model_config = ConfigDict(frozen=True)

    resonance_formula: str = Field(
        ...,
        description="Human-readable formula string describing the resonance calculation",
    )
    parameters: Dict[str, Any] = Field(
        default_factory=dict,
        description="All calculation parameters used to derive the impact",
    )


# ── Top-level response ──────────────────────────────────────────────────────

class ImpactResponse(BaseModel):
    """Response body for POST /impact/active."""

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    harmony_index: float = Field(
        ..., ge=0, le=1, description="Wu-Xing cosine coherence index (0-1)"
    )
    day_mode: DayMode = Field(
        ..., description="Overall day energy mode"
    )
    intensity: float = Field(
        ..., ge=0, le=1, description="Intensity scalar (0-1)"
    )
    active_planets: List[ActivePlanet] = Field(
        ..., description="Planets with orb <= 8 deg to a natal aspect"
    )
    space_weather: SpaceWeather
    space_weather_score: float = Field(
        ..., ge=0, le=1, description="Normalized space weather impact (0-1)"
    )
    drivers: List[Driver] = Field(
        ..., min_length=4, max_length=4,
        description="4 coherence drivers: geomagnetic, solar, transit, day_field",
    )
    resonance_badges: List[ResonanceBadge] = Field(
        default_factory=list, description="Active resonance badges (Premium)"
    )
    top_sector: WuXingElement = Field(
        ..., description="Dominant Wu-Xing sector for the day"
    )
    day_master: WuXingElement = Field(
        ..., description="BaZi day master element"
    )
    evidence: Evidence
    partial: bool = Field(
        default=False,
        description="True if space weather data was unavailable (503 fallback)",
    )
