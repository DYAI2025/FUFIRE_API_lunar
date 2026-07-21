"""
routers/validate.py — POST /validate (contract-first BAFE validator)
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict
from starlette.requests import Request

from ..bafe import validate_request as bafe_validate_request
from ..limiter import limiter, tier_limit
from .shared import ErrorEnvelope

_log = logging.getLogger(__name__)

router = APIRouter(tags=["Validation"])


class ValidateRequest(BaseModel):
    """Loose request wrapper for contract-first /validate payloads.

    The effective public schema is patched to spec/schemas/ValidateRequest.schema.json
    in app._custom_openapi(). This model exists to keep the endpoint typed in OpenAPI.
    """

    model_config = ConfigDict(extra="allow")


class ValidateResponse(BaseModel):
    """Loose response wrapper for /validate results.

    The effective public schema is patched to spec/schemas/ValidateResponse.schema.json
    in app._custom_openapi().
    """

    model_config = ConfigDict(extra="allow")


@router.post(
    "/validate",
    response_model=ValidateResponse,
    responses={
        422: {"model": ErrorEnvelope},
        500: {"model": ErrorEnvelope},
    },
)
@limiter.limit(tier_limit)
async def validate(request: Request, payload: ValidateRequest) -> ValidateResponse:
    """Contract-first validator (JSON Schema Draft-07)."""
    try:
        result = bafe_validate_request(payload.model_dump(exclude_none=False))
        return ValidateResponse.model_validate(result)
    except ValueError as e:
        raise HTTPException(status_code=422, detail={
            "error": "validation_error",
            "message": str(e),
            "detail": {},
        })
    except Exception:
        _log.exception("Validation failed")
        raise HTTPException(status_code=500, detail={
            "error": "validation_error",
            "message": "Internal validation error",
            "detail": {},
        })
