"""routers/zwds.py — ZWDS-P1-20/21 HTTP layer for the Zi Wei Dou Shu engine.

Two ``/v1``-ONLY endpoints (a deliberate deviation from the dual-mount idiom,
exactly like ``routers/match.py`` and ``routers/admin.py`` — there is no legacy
unversioned twin):

* ``POST /v1/calculate/zwds`` — a full natal ``ZwdsRawResponse`` for a civil
  birth request.
* ``GET  /v1/metadata/zwds/rulesets/{ruleset_id}`` — the immutable, hash-locked
  ruleset envelope plus core-seed release markers.

**Two-stage request validation.** The Pydantic models below document the
request in OpenAPI and enforce field presence / types / enums / patterns (so a
malformed shape is a plain ``validation_error`` 422). Inside the handler the
assembled dict is THEN re-validated against the vendored
``spec/schemas/zwds/ZwdsRequest.schema.json`` with a ``Draft202012Validator``
to enforce the cross-field conditional invariants a flat Pydantic model cannot
express (``direction_method`` ↔ ``flow_direction``/``sex_at_birth``,
``include_decadal_limits`` ↔ direction).

**PII discipline (WS-A retro).** The birth datetime/timezone are NEVER echoed
in any error body. jsonschema failures name the failing JSON *path* only (never
``err.message``/``err.instance``, which can carry the raw value). The engine's
own DST / birth-time errors are already PII-scrubbed by ``resolve_local_iso`` /
``resolve_chronometry`` and propagate unchanged to the global
``error_handlers`` → ``ErrorEnvelope``.

Layer: this is the HTTP composition seam (Level 5). It reaches the engine only
through ``services/zwds_service.py`` and the ZWDS error contract from
``bazi_engine.zwds.errors``; it never re-implements engine logic.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter, HTTPException, Request
from jsonschema import Draft202012Validator
from pydantic import BaseModel, ConfigDict, Field

from ..limiter import limiter, tier_limit
from ..resource_loader import load_json_object_resource
from ..services import zwds_service
from ..zwds.errors import (
    ZwdsDirectionBasisMissingError,
    ZwdsRequestedScopeUnavailableError,
    ZwdsRulesetNotFoundError,
)

router = APIRouter(tags=["ZWDS"])

# --- vendored request schema (cross-field conditional invariants) ------------

@lru_cache(maxsize=1)
def _request_validator() -> Draft202012Validator:
    """Load and cache the Draft-2020-12 validator for the request schema."""
    schema = load_json_object_resource(
        "bazi_engine.resources", "schemas", "zwds", "ZwdsRequest.schema.json"
    )
    return Draft202012Validator(schema)


def _assert_request_conditionals(request: Dict[str, Any]) -> None:
    """Validate the assembled request against the vendored JSON Schema.

    Pydantic has already enforced field presence / types / enums / patterns, so
    the only NEW violations a Draft-2020-12 pass surfaces here are the
    cross-field conditional invariants — all direction / decadal-direction
    related once the ``include_catalog`` toggle has been gated separately. On
    failure we raise a PII-safe 422 that names the failing JSON *path(s)* only;
    we deliberately never surface ``err.message`` / ``err.instance``, which can
    echo the raw birth value.
    """
    errors = sorted(
        _request_validator().iter_errors(request), key=lambda e: list(e.path)
    )
    if not errors:
        return
    failing_paths = sorted({err.json_path for err in errors})
    raise ZwdsDirectionBasisMissingError(
        "ZWDS request violates a conditional requirement; check the "
        "direction_method / flow_direction / sex_at_birth / "
        "include_decadal_limits combination.",
        detail={"failing_paths": failing_paths},
    )


# --- Request models (documented in OpenAPI; mirror ZwdsRequest.schema.json) ---


class ZwdsLocation(BaseModel):
    """Birth-place coordinates (WGS-84 degrees)."""

    model_config = ConfigDict(extra="forbid")

    lat: float = Field(..., ge=-90, le=90)
    lon: float = Field(..., ge=-180, le=180)


class ZwdsBirth(BaseModel):
    """Civil birth input. Calendar validity is checked at runtime by the engine."""

    model_config = ConfigDict(extra="forbid")

    datetime_local: str = Field(
        ...,
        pattern=r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2}(?:\.\d{1,6})?)?$",
        description="Naive local civil datetime (calendar validity checked at runtime).",
    )
    timezone: str = Field(
        ..., min_length=1, max_length=128, description="IANA timezone name."
    )
    location: ZwdsLocation
    sex_at_birth: Optional[Literal["male", "female"]] = Field(
        None,
        description=(
            "Used only by the traditional direction rule. Prefer explicit "
            "direction to avoid supplying this."
        ),
    )
    ambiguousTime: Literal["earlier", "later"] = Field(
        ..., description="DST fall-back disambiguation (matches resolve_local_iso)."
    )
    nonexistentTime: Literal["error", "shift_forward"] = Field(
        ..., description="DST spring-forward gap handling (matches resolve_local_iso)."
    )


class ZwdsCalculation(BaseModel):
    """Ruleset selection + decadal-limit direction method."""

    model_config = ConfigDict(extra="forbid")

    ruleset_id: str = Field(..., pattern=r"^[a-z0-9][a-z0-9._-]{2,127}$")
    direction_method: Literal["year_stem_yinyang_and_sex", "explicit", "omit"]
    flow_direction: Optional[Literal["forward", "backward"]] = Field(
        None,
        description="Required when direction_method='explicit'; forbidden otherwise.",
    )


class ZwdsOutput(BaseModel):
    """Output shaping toggles (mirror OutputOptions in the request schema)."""

    model_config = ConfigDict(extra="forbid")

    locale: str = Field(..., pattern=r"^[A-Za-z]{2,3}(?:-[A-Za-z0-9]{2,8})*$")
    script_variant: Literal["ids_only", "zh-Hans", "zh-Hant", "both"]
    include_trace: bool
    include_decadal_limits: bool
    include_layout: bool
    include_catalog: bool
    star_scope: Literal["core", "full_ruleset"]


class ZwdsCalculateRequest(BaseModel):
    """POST /v1/calculate/zwds request body."""

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {
                "birth": {
                    "datetime_local": "1984-02-01T23:30:00",
                    "timezone": "Asia/Shanghai",
                    "location": {"lat": 31.2304, "lon": 121.4737},
                    "sex_at_birth": "male",
                    "ambiguousTime": "earlier",
                    "nonexistentTime": "error",
                },
                "calculation": {
                    "ruleset_id": "zwds.fufire.core-seed.v1",
                    "direction_method": "year_stem_yinyang_and_sex",
                },
                "output": {
                    "locale": "de-DE",
                    "script_variant": "ids_only",
                    "include_trace": True,
                    "include_decadal_limits": True,
                    "include_layout": False,
                    "include_catalog": False,
                    "star_scope": "core",
                },
            }
        },
    )

    birth: ZwdsBirth
    calculation: ZwdsCalculation
    output: ZwdsOutput


# --- Response models ----------------------------------------------------------


class ZwdsRawResponseModel(BaseModel):
    """Typed top-level envelope for the ZWDS raw response.

    The AUTHORITATIVE response contract is the vendored JSON Schema
    ``spec/schemas/zwds/ZwdsRawResponse.schema.json``; this model exists only to
    give the OpenAPI operation a typed 200 (the nested blocks are pass-through
    objects). The engine returns exactly these top-level keys, so nothing is
    dropped; ``extra="allow"`` keeps the response pass-through-safe.
    """

    model_config = ConfigDict(extra="allow")

    request_id: str
    schema_version: str
    engine_version: str
    generated_at: str
    chart_fingerprint: str
    ruleset: Dict[str, Any]
    normalized_input: Dict[str, Any]
    resolution: Dict[str, Any]
    chart: Dict[str, Any]
    catalog: Optional[Dict[str, Any]] = None
    quality: Dict[str, Any]
    provenance: List[Dict[str, Any]]
    derivation_trace: Optional[List[Dict[str, Any]]] = None


class ZwdsRulesetMetadataResponse(BaseModel):
    """Immutable ruleset envelope + core-seed release markers."""

    model_config = ConfigDict(extra="forbid")

    ruleset_id: str
    ruleset_version: str
    ruleset_sha256: str
    school_label: Optional[str] = None
    calendar_policy_id: str
    time_policy_id: str
    leap_month_policy_id: str
    year_cycle_policy_id: str
    star_catalog_id: str
    transformation_table_id: str
    age_reckoning_id: str
    source_status: str
    star_catalog_sha256: str
    transformation_table_sha256: str
    calendar_policy_sha256: str
    time_policy_sha256: str
    release_status: str
    human_review_required: bool


# --- Endpoints (mounted at /v1 only via routers/registry.py) ------------------


@router.post(
    "/calculate/zwds",
    response_model=ZwdsRawResponseModel,
    summary="Compute a full ZWDS (Zi Wei Dou Shu) natal chart",
)
@limiter.limit(tier_limit)
async def calculate_zwds(
    request: Request, req: ZwdsCalculateRequest
) -> Dict[str, Any]:
    """Return the full deterministic ``ZwdsRawResponse`` for a civil birth input.

    Unset optional fields are dropped from the assembled dict so the vendored
    schema's ``additionalProperties: false`` / enum constraints hold. The
    ``include_catalog`` toggle is gated first (the core-seed engine materializes
    no catalog), then the cross-field conditionals are enforced, then the engine
    runs. Engine / seed errors (birth-time-required, ruleset-not-found,
    direction-basis-missing, DST ``LocalTimeError``, calendar / graph failures)
    subclass the ``bazi_engine.exc`` bases and propagate to the global handlers,
    which render a PII-free ``ErrorEnvelope``.
    """
    request_dict = req.model_dump(exclude_none=True)

    # Gate the unsupported catalog toggle BEFORE the schema pass, so a catalog
    # request is always a clean scope-unavailable 422 regardless of the
    # script_variant the schema's catalog conditional would otherwise flag.
    if req.output.include_catalog:
        raise ZwdsRequestedScopeUnavailableError(
            "output.include_catalog is not available in the core-seed engine "
            "(no catalog is materialized).",
            detail={"field": "output.include_catalog", "requested_scope": "catalog"},
        )

    _assert_request_conditionals(request_dict)

    return zwds_service.calculate(request_dict)


@router.get(
    "/metadata/zwds/rulesets/{ruleset_id}",
    response_model=ZwdsRulesetMetadataResponse,
    summary="ZWDS ruleset metadata (immutable, hash-locked)",
)
@limiter.limit(tier_limit)
async def zwds_ruleset_metadata(
    request: Request, ruleset_id: str
) -> Dict[str, Any]:
    """Return the immutable ruleset envelope plus core-seed release markers.

    An unknown ``ruleset_id`` is a missing GET resource, so it maps to **404**
    (rather than the ``InputError`` default 422) while keeping the ZWDS
    ``zwds_ruleset_not_found`` code in the ``ErrorEnvelope``. The ``ruleset_id``
    is the caller-supplied resource identifier (a path segment), not birth PII,
    so echoing it in the message is safe.
    """
    try:
        return zwds_service.ruleset_metadata(ruleset_id)
    except ZwdsRulesetNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail={
                "error": exc.error_code,
                "message": str(exc),
                "detail": exc.detail,
            },
        ) from exc
