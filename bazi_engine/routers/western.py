"""
routers/western.py — POST /calculate/western
"""
from __future__ import annotations

import logging
from datetime import timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from starlette.requests import Request

from ..exc import BaziEngineError
from ..limiter import limiter, tier_limit
from ..provenance import build_provenance, normalize_house_system
from ..time_utils import AmbiguousTimeChoice, NonexistentTimePolicy, resolve_local_iso
from ..western import compute_western_chart
from .shared import PrecisionBlock, ProvenanceResponse, QualityFlags

_log = logging.getLogger(__name__)

router = APIRouter(prefix="/calculate", tags=["Western Astrology"])


class WesternRequest(BaseModel):
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "date": "1990-06-15T14:30:00",
            "tz": "Europe/Berlin",
            "lon": 13.405,
            "lat": 52.52,
            "birth_time_known": True,
        }
    })

    date: str = Field(..., description="Local ISO8601 datetime")
    tz: str = Field("Europe/Berlin", description="IANA timezone name")
    lon: float = Field(13.4050, ge=-180.0, le=180.0, description="Longitude in degrees")
    lat: float = Field(52.52, ge=-90.0, le=90.0, description="Latitude in degrees")
    ambiguousTime: AmbiguousTimeChoice = Field("earlier")
    nonexistentTime: NonexistentTimePolicy = Field("error")
    birth_time_known: bool = Field(True, description="False if birth time is uncertain — flags ascendant/houses/mc as provisional")
    zodiac_mode: Optional[str] = Field(
        "tropical",
        pattern=r"^(tropical|sidereal_lahiri|sidereal_fagan_bradley|sidereal_raman)$",
        description="Zodiac reference frame. Default: tropical.",
    )


class WesternBodyResponse(BaseModel):
    longitude: Optional[float] = None
    latitude: Optional[float] = None
    speed: Optional[float] = None
    distance: Optional[float] = None
    zodiac_sign: Optional[int] = None
    degree_in_sign: Optional[float] = None
    is_retrograde: bool = False


class AspectResponse(BaseModel):
    planet1: str
    planet2: str
    type: str
    angle: float
    orb: float
    exact_angle: float


class HouseQuality(BaseModel):
    flag: str = Field(..., pattern=r"^(exact|fallback|estimated)$")
    system: str
    requested: str = "placidus"
    reason: Optional[str] = None


class WesternResponse(BaseModel):
    jd_ut: float
    house_system: str
    bodies: Dict[str, WesternBodyResponse]
    houses: Optional[Dict[str, float]] = None
    angles: Optional[Dict[str, float]] = None
    aspects: List[AspectResponse] = []
    house_quality: HouseQuality
    quality_flags: QualityFlags
    provenance: ProvenanceResponse
    precision: PrecisionBlock


@router.post("/western", response_model=WesternResponse)
@limiter.limit(tier_limit)
def calculate_western_endpoint(request: Request, req: WesternRequest) -> Dict[str, Any]:
    """Western astrology chart. Returns planetary positions, house cusps, Ascendant/MC angles, and aspects using Swiss Ephemeris. Supports tropical and sidereal zodiac systems (Lahiri, Fagan-Bradley, Raman). Houses use Placidus with automatic fallback for extreme latitudes. When `birth_time_known=false`, ascendant and houses are flagged provisional."""
    try:
        dt_local, _ = resolve_local_iso(
            req.date, req.tz,
            ambiguous=req.ambiguousTime, nonexistent=req.nonexistentTime,
        )
        dt_utc = dt_local.astimezone(timezone.utc)
        zodiac_mode = req.zodiac_mode or "tropical"
        result = compute_western_chart(dt_utc, req.lat, req.lon, zodiac_mode=zodiac_mode)
        result["provenance"] = build_provenance(
            house_system=normalize_house_system(result.get("house_system")),
            zodiac_mode=zodiac_mode,
        )
        result["precision"] = {
            "birth_time_known": req.birth_time_known,
            "provisional_fields": [] if req.birth_time_known else ["ascendant", "houses", "mc"],
        }
        return result
    except BaziEngineError:
        raise
    except Exception:
        _log.exception("Calculation failed")
        raise HTTPException(status_code=500, detail={
            "error": "calculation_error",
            "message": "Internal calculation error",
            "detail": {},
        })
