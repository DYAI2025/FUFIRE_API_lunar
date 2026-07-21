"""
routers/superglue.py — Superglue.ai proxy endpoints.

GET  /api/profile/{user_id}       — Fetch ElevenLabs context for user (Eve)
GET  /api/daily/{user_id}         — Fetch daily transit horoscope for user
POST /api/profile/{user_id}/chart — Trigger/refresh user chart calculation
"""
from __future__ import annotations

import logging
from typing import Any, Dict, NoReturn, Optional

import httpx
from fastapi import APIRouter, Body, HTTPException, Path, Query, Request
from pydantic import BaseModel, ConfigDict

from ..limiter import limiter, tier_limit
from ..services.superglue_client import call_hook

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Superglue"])


class SuperglueChartTriggerRequest(BaseModel):
    force_recalculate: bool = False


class SuperglueProxyResponse(BaseModel):
    """Open-ended response model for Superglue proxy endpoints.

    The actual fields depend on the Superglue hook configuration and may vary.
    Using ``extra="allow"`` ensures all upstream fields pass through without
    filtering while still producing a typed ``$ref`` in the OpenAPI schema.
    """

    model_config = ConfigDict(extra="allow")


def _handle_httpx_error(exc: Exception) -> NoReturn:
    if isinstance(exc, httpx.HTTPStatusError):
        status_code = exc.response.status_code
        raise HTTPException(
            status_code=status_code,
            detail={
                "error": "superglue_upstream_error",
                "message": f"Superglue upstream returned HTTP {status_code}",
            },
        )
    if isinstance(exc, httpx.TimeoutException):
        raise HTTPException(
            status_code=504,
            detail={"error": "superglue_timeout", "message": "Superglue hook timed out"},
        )
    raise exc


@router.get("/profile/{user_id}", response_model=SuperglueProxyResponse)
@limiter.limit(tier_limit)
async def get_profile(
    request: Request,
    user_id: str = Path(..., pattern=r"^[a-zA-Z0-9_\-]{1,128}$"),
) -> Dict[str, Any]:
    """Fetch ElevenLabs context for a user via Superglue bazodiac-elevenlabs-context hook."""
    try:
        return await call_hook("bazodiac-elevenlabs-context", {"user_id": user_id})
    except (httpx.HTTPStatusError, httpx.TimeoutException) as exc:
        return _handle_httpx_error(exc)


@router.get("/profile", response_model=SuperglueProxyResponse)
@limiter.limit(tier_limit)
async def get_profile_query(
    request: Request,
    user_id: str = Query(..., pattern=r"^[a-zA-Z0-9_\-]{1,128}$"),
) -> Dict[str, Any]:
    """Fetch ElevenLabs context via query param — for ElevenLabs tool integration."""
    try:
        return await call_hook("bazodiac-elevenlabs-context", {"user_id": user_id})
    except (httpx.HTTPStatusError, httpx.TimeoutException) as exc:
        return _handle_httpx_error(exc)


@router.get("/daily/{user_id}", response_model=SuperglueProxyResponse)
@limiter.limit(tier_limit)
async def get_daily(
    request: Request,
    user_id: str = Path(..., pattern=r"^[a-zA-Z0-9_\-]{1,128}$"),
) -> Dict[str, Any]:
    """Fetch daily transit horoscope for a user via Superglue bazodiac-daily-transit hook."""
    try:
        return await call_hook("bazodiac-daily-transit", {"user_id": user_id})
    except (httpx.HTTPStatusError, httpx.TimeoutException) as exc:
        return _handle_httpx_error(exc)


@router.get("/daily", response_model=SuperglueProxyResponse)
@limiter.limit(tier_limit)
async def get_daily_query(
    request: Request,
    user_id: str = Query(..., pattern=r"^[a-zA-Z0-9_\-]{1,128}$"),
) -> Dict[str, Any]:
    """Fetch daily horoscope via query param — for ElevenLabs tool integration."""
    try:
        return await call_hook("bazodiac-daily-transit", {"user_id": user_id})
    except (httpx.HTTPStatusError, httpx.TimeoutException) as exc:
        return _handle_httpx_error(exc)


@router.post("/profile/{user_id}/chart", response_model=SuperglueProxyResponse)
@limiter.limit(tier_limit)
async def trigger_user_chart(
    request: Request,
    user_id: str = Path(..., pattern=r"^[a-zA-Z0-9_\-]{1,128}$"),
    body: Optional[SuperglueChartTriggerRequest] = Body(None),
) -> Dict[str, Any]:
    """Trigger or refresh chart calculation for a user via Superglue bazodiac-user-chart hook.

    Request body is optional. Omitting it is equivalent to ``{"force_recalculate": false}``.
    Pass ``force_recalculate=true`` to bypass the Superglue cache.
    """
    force = body.force_recalculate if body is not None else False
    try:
        return await call_hook(
            "bazodiac-user-chart",
            {"user_id": user_id, "force_recalculate": force},
        )
    except (httpx.HTTPStatusError, httpx.TimeoutException) as exc:
        return _handle_httpx_error(exc)
