"""routers/geocode.py — POST /geocode  (+ /v1/geocode).

Exposes the Open-Meteo geocoding service (free, no upstream key) as a protected
HTTP endpoint and adds the OQ-001 ambiguity gate the bare service lacks.

The service resolves a place name into up to 5 ranked candidates
(``geocode_candidates``). This router derives a deterministic v1 confidence
score from that candidate list and fails loud on ambiguity instead of silently
returning ``results[0]``:

Confidence v1 heuristic (docs/plans/2026-06-18-req-001-geocode-endpoint.md):
  - 0 candidates                       → 404 ``place_not_found``.
  - exactly 1 candidate                → confidence 1.0.
  - >= 2 candidates                    → ``pop_top / (pop_top + pop_second)``
    using the two top candidates' populations; a missing population on either
    of the top two yields 0.5 (treated as ambiguous — do not silently pick).
  - confidence < 0.6                   → 422 ``ambiguous_place`` with the
    candidate list so the consumer can disambiguate.
  - otherwise                          → 200 with the resolved location.

The place string flows into the external Open-Meteo URL only through the
service's existing ``urlencode`` seam (no raw URL construction here).
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from starlette.requests import Request

from ..limiter import limiter, tier_limit
from ..services.geocoding import (
    AMBIGUITY_THRESHOLD,
    compute_confidence,
    geocode_candidates,
    project_candidate,
)

_log = logging.getLogger(__name__)

router = APIRouter(tags=["Geocode"])


# ── Request / response models ────────────────────────────────────────────────

class GeocodeRequest(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={"example": {"place": "Berlin, DE", "language": "de"}},
    )
    place: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Place name, optionally with a ', XX' 2-letter country suffix.",
    )
    language: str = Field("de", description="Language code for result names.")


class GeocodeResponse(BaseModel):
    lat: float = Field(..., description="Latitude in degrees")
    lon: float = Field(..., description="Longitude in degrees")
    resolved_name: str = Field(..., description="Resolved place name from Open-Meteo")
    confidence: float = Field(..., description="v1 confidence score in [0, 1]")
    timezone: str = Field(..., description="IANA timezone name")
    country_code: str = Field(..., description="ISO 3166-1 alpha-2 country code")


# ── Route ────────────────────────────────────────────────────────────────────

@router.post("/geocode", response_model=GeocodeResponse)
@limiter.limit(tier_limit)
async def geocode_endpoint(request: Request, req: GeocodeRequest) -> Dict[str, Any]:
    """Resolve a place name to coordinates, failing loud on ambiguity.

    Returns the dominant candidate on an unambiguous match (confidence >= 0.6).
    When several comparable candidates exist (confidence < 0.6) it returns
    422 ``ambiguous_place`` with the candidate list instead of guessing, and
    404 ``place_not_found`` when nothing matched.
    """
    try:
        candidates = await geocode_candidates(req.place, req.language)
    except (httpx.HTTPError, json.JSONDecodeError, ValueError) as exc:
        # Upstream failure (timeout, 5xx via raise_for_status, connection error,
        # or a non-JSON/undecodable body). Surface as 503 instead of letting it
        # fall through to the app's generic Exception handler → misleading 500.
        # NOTE: an empty result set is a normal ``[]`` return, not an exception,
        # so the 404 place_not_found path below is unaffected.
        _log.warning("geocode.upstream_unavailable place=%r err=%s", req.place, exc)
        raise HTTPException(
            status_code=503, detail={"error": "geocoding_unavailable"}
        ) from exc

    if not candidates:
        raise HTTPException(status_code=404, detail={"error": "place_not_found"})

    confidence = compute_confidence(candidates)

    if confidence < AMBIGUITY_THRESHOLD:
        typed_candidates = [project_candidate(c) for c in candidates]
        raise HTTPException(
            status_code=422,
            detail={
                "error": "ambiguous_place",
                "candidates": typed_candidates,
                "confidence": confidence,
            },
        )

    top = candidates[0]
    return {
        "lat": float(top["latitude"]),
        "lon": float(top["longitude"]),
        "resolved_name": str(top.get("name") or req.place),
        "confidence": confidence,
        "timezone": str(top.get("timezone") or ""),
        "country_code": str(top.get("country_code") or ""),
    }
