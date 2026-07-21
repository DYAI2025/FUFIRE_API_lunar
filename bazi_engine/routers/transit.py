"""
routers/transit.py — Transit API endpoints.

GET  /transit/now        — Current planetary positions.
GET  /transit/timeline   — Multi-day transit forecast.
POST /transit/state      — Personalized transit state.
POST /transit/narrative  — Text generation from transit state.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator

from ..limiter import limiter, tier_limit
from ..narrative import generate_narrative
from ..provenance import build_provenance
from ..transit import compute_transit_now, compute_transit_state, compute_transit_timeline
from .shared import MinimalQualityFlags, ProvenanceResponse, current_ephemeris_mode

router = APIRouter(prefix="/transit", tags=["Transit"])


# ── Response models ──────────────────────────────────────────────────────────
#
# FQ-ATT-02 (T9): confirmed gap -- all 5 response models below previously
# carried zero quality_flags/provenance fields despite /transit/now computing
# real ephemeris data via a live, guarded backend.calc_ut() call
# (bazi_engine/transit.py:130, FQ-ATT-01, out of this file's scope). Per-model
# decision, based on each one's actual data flow (not applied identically to
# all 5):
#
#   - TransitNowResponse: DOES get quality_flags/provenance. It is the one
#     model directly, causally backed by that live calc_ut call for THIS
#     response (subject to the 1h TTLCache, same attestation guarantee
#     either way since the cache key is itself ephemeris-mode-scoped).
#     Non-house endpoint (transit computes no house cusps) -> OQ-1's
#     non-house treatment -> MinimalQualityFlags, not the full QualityFlags.
#   - TransitStateResponse: NOT extended. It's a personalized aggregate
#     (ring/transit_contribution/events) derived from TransitNowResponse's
#     already-cached sector_intensity plus user-supplied vectors -- it
#     carries no raw ephemeris body/position data of its own; attaching a
#     second, independent attestation block here would be a re-derivation
#     of the same fact TransitNowResponse already states, not a new one.
#   - TimelineDayResponse / TimelineResponse: NOT extended. Multi-day batch
#     of the same TransitNowResponse-shaped data, cached up to 24h -- adding
#     per-day (or once-per-response) attestation fields here would either
#     misleadingly imply N independently-attested computations or be a bare
#     duplicate of the single environment-wide mode value; the PRD's own T9
#     scope note explicitly limited required contract-test coverage to
#     "transit/now", not timeline/state.
#   - NarrativeResponse: NOT extended. `generate_narrative()`
#     (bazi_engine/narrative.py) is template-based text generation over an
#     already-computed `TransitStateInput` supplied in the request body --
#     it performs NO ephemeris computation of its own at all, so it is not
#     a "calculation performed by bazi_engine" in FQ-ATT-02's sense.


class PlanetPosition(BaseModel):
    longitude: float
    sector: int
    sign: str
    speed: float


class TransitNowResponse(BaseModel):
    computed_at: str
    planets: Dict[str, PlanetPosition]
    sector_intensity: List[float]
    quality_flags: MinimalQualityFlags
    provenance: ProvenanceResponse


class RingSectors(BaseModel):
    sectors: List[float]


class TransitContribution(BaseModel):
    sectors: List[float]
    transit_intensity: float


class TransitStateResponse(BaseModel):
    schema_: str = Field(..., alias="schema")
    generated_at: str
    ring: RingSectors
    transit_contribution: TransitContribution
    events: List[Dict[str, Any]]

    model_config = {"populate_by_name": True}


class TimelineDayResponse(BaseModel):
    date: str
    planets: Dict[str, PlanetPosition]
    sector_intensity: List[float]


class TimelineResponse(BaseModel):
    days: List[TimelineDayResponse]


class NarrativeResponse(BaseModel):
    headline: str
    body: str
    advice: str
    pushworthy: bool
    push_text: Optional[str] = None


# ── Request models ───────────────────────────────────────────────────────────

class TransitStateRequest(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)

    soulprint_sectors: List[float] = Field(..., min_length=12, max_length=12)
    quiz_sectors: List[float] = Field(..., min_length=12, max_length=12)

    @field_validator("soulprint_sectors", "quiz_sectors")
    @classmethod
    def validate_sector_values(cls, v: List[float]) -> List[float]:
        for i, val in enumerate(v):
            if val < 0 or val > 1:
                raise ValueError(f"Element {i} = {val} not in range [0, 1]")
        return v


class TransitEvent(BaseModel):
    """A single transit event as produced by compute_transit_state()."""
    model_config = ConfigDict(allow_inf_nan=False)

    type: str = Field(
        ...,
        pattern=r"^(resonance_jump|moon_event)$",
        description="Event type identifier.",
    )
    priority: int = Field(..., ge=1, le=99, description="Priority (1 = highest).")
    sector: int = Field(..., ge=0, le=11, description="Zodiac sector index (0-11).")
    trigger_planet: str = Field(
        ...,
        max_length=20,
        description="Planet that triggered the event (empty string for dominance_shift).",
    )
    description_de: str = Field(
        ..., max_length=500, description="German description of the event."
    )
    personal_context: str = Field(
        ..., max_length=500, description="Personal context message."
    )


class TransitStateInput(BaseModel):
    """Typed transit state matching the TRANSIT_STATE_v2 schema."""
    model_config = ConfigDict(allow_inf_nan=False, populate_by_name=True)

    schema_: str = Field(
        "TRANSIT_STATE_v2",
        alias="schema",
        pattern=r"^TRANSIT_STATE_v\d+$",
        description="Schema version identifier.",
    )
    generated_at: str = Field(
        ..., description="ISO 8601 UTC timestamp of generation."
    )
    ring: RingSectors
    transit_contribution: TransitContribution
    events: List[TransitEvent] = Field(
        default_factory=list,
        max_length=50,
        description="Detected transit events.",
    )

    @field_validator("ring")
    @classmethod
    def validate_ring_length(cls, v: RingSectors) -> RingSectors:
        if len(v.sectors) != 12:
            raise ValueError("ring.sectors must have exactly 12 elements")
        for i, val in enumerate(v.sectors):
            if val < 0:
                raise ValueError(f"ring.sectors[{i}] = {val} must be >= 0")
        return v

    @field_validator("transit_contribution")
    @classmethod
    def validate_contribution(cls, v: TransitContribution) -> TransitContribution:
        if len(v.sectors) != 12:
            raise ValueError(
                "transit_contribution.sectors must have exactly 12 elements"
            )
        return v


class NarrativeRequest(BaseModel):
    transit_state: TransitStateInput


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.get("/now", response_model=TransitNowResponse)
@limiter.limit(tier_limit)
def transit_now(
    request: Request,
    datetime_param: Optional[str] = Query(
        None,
        alias="datetime",
        description="Optional UTC datetime in ISO format. Default: now.",
    ),
) -> Dict[str, Any]:
    """Current planetary positions from Swiss Ephemeris."""
    dt_utc = None
    if datetime_param:
        try:
            dt_utc = datetime.fromisoformat(
                datetime_param.replace("Z", "+00:00")
            ).astimezone(timezone.utc)
        except (ValueError, TypeError):
            from ..exc import InputError
            raise InputError(
                f"Invalid datetime format: {datetime_param!r}",
                detail={"parameter": "datetime", "value": datetime_param},
            )
    result = dict(compute_transit_now(dt_utc=dt_utc))
    # FQ-ATT-02 (T9): compute_transit_now() (bazi_engine/transit.py, out of
    # this file's scope) constructs its own SwissEphBackend internally
    # without exposing it here, and its dict result is TTL-cached without
    # attestation fields -- read the attested environment mode via a
    # throwaway backend construction (current_ephemeris_mode), same pattern
    # as /calculate/bazi and /calculate/tst, rather than a hardcoded/stubbed
    # literal (VCHK-02).
    result["quality_flags"] = {"ephemeris_mode": current_ephemeris_mode()}
    result["provenance"] = build_provenance()
    return result


@router.post("/state", response_model=TransitStateResponse)
@limiter.limit(tier_limit)
def transit_state(request: Request, body: TransitStateRequest) -> Dict[str, Any]:
    """Personalized transit state combining current transits with user profile."""
    return compute_transit_state(
        soulprint_sectors=body.soulprint_sectors,
        quiz_sectors=body.quiz_sectors,
    )


@router.get("/timeline", response_model=TimelineResponse)
@limiter.limit(tier_limit)
def transit_timeline(
    request: Request,
    days: int = Query(7, ge=1, le=30, description="Number of days to forecast (1-30)."),
) -> Dict[str, Any]:
    """Multi-day transit forecast. Cached 24h (ADR-1)."""
    return compute_transit_timeline(days=days)


@router.post("/narrative", response_model=NarrativeResponse)
@limiter.limit(tier_limit)
def transit_narrative(request: Request, body: NarrativeRequest) -> Dict[str, Any]:
    """Generate narrative text from transit state. Template-based, <50ms (ADR-3)."""
    return generate_narrative(body.transit_state.model_dump(by_alias=True))
