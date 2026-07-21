"""
routers/admin.py — Administrative API-key issuance.

POST /v1/admin/keys mints a real, immediately-valid API key and persists it
to the configured KeyStore. Intended for automated key issuance (e.g. the
landing page) behind an admin token.

Auth model
----------
* Caller authenticates with the ``X-Admin-Token`` header, compared
  constant-time (``hmac.compare_digest``) against ``FUFIRE_ADMIN_TOKEN``.
* Issuance is impossible — and the endpoint returns an honest ``503`` — unless
  BOTH a KeyStore is configured (``KEY_STORE_BACKEND`` != none) AND
  ``FUFIRE_ADMIN_TOKEN`` is set. You cannot persist a key without a store, and
  you must not mint without an admin gate.

Safety
------
* Tier allow-list: only ``free`` may be issued via this endpoint.
* Idempotent on ``jti``: re-issuing the same ``jti`` returns the same key and
  never mints a second.
* The minted key is NEVER logged. Logs record only ``jti`` + ``tier``.
"""
from __future__ import annotations

import hmac
import logging
import os

from fastapi import APIRouter, HTTPException, Request, Security
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, ConfigDict, Field

from ..key_store import get_key_store
from ..limiter import limiter, tier_limit
from .shared import ErrorEnvelope

_log = logging.getLogger(__name__)

router = APIRouter(tags=["Admin"])

# auto_error=False so we control the 401 envelope rather than FastAPI's default.
_ADMIN_TOKEN_HEADER = APIKeyHeader(name="X-Admin-Token", auto_error=False)

# Only this tier may be minted through the public issuance endpoint.
_ALLOWED_ISSUANCE_TIERS = frozenset({"free"})

# Minimum recommended admin-token length. The admin token is the SOLE control
# on a public mint endpoint and rate-limiting may collapse to a shared
# proxy-IP bucket, so a low-entropy token is a real risk. We WARN (never
# hard-fail) so a configured deploy is never broken by this check.
_MIN_ADMIN_TOKEN_LEN = 32

# One-time guard so the weak-token warning is logged at most once per process
# (first issuance attempt), not on every request.
_WEAK_TOKEN_WARNED = False


class IssueKeyRequest(BaseModel):
    """Body for POST /v1/admin/keys."""

    model_config = ConfigDict(extra="forbid")

    tier: str = Field(..., description="Tier to issue. Allow-list: only 'free'.")
    label: str = Field("", description="Human-readable label for audit/traceability.")
    jti: str = Field(..., min_length=1, description="Idempotency key (JWT ID). Re-issuing the same jti returns the same key.")


class IssueKeyResponse(BaseModel):
    """Response for POST /v1/admin/keys. Returns the (only) plaintext copy of the key."""

    model_config = ConfigDict(extra="forbid")

    key: str
    tier: str


def _admin_token() -> str | None:
    raw = os.environ.get("FUFIRE_ADMIN_TOKEN", "").strip()
    return raw or None


def _warn_if_weak_admin_token(configured_token: str | None) -> None:
    """Emit a one-time WARNING if the configured admin token is weak (<32 chars).

    Defense-in-depth only: the admin token is the sole control on a public mint
    endpoint, so a short/low-entropy token is risky. We never log the token
    value and never hard-fail — a configured deploy must keep working.
    """
    global _WEAK_TOKEN_WARNED
    if _WEAK_TOKEN_WARNED or configured_token is None:
        return
    if len(configured_token) < _MIN_ADMIN_TOKEN_LEN:
        _WEAK_TOKEN_WARNED = True  # set first so a logging error can't loop us
        _log.warning(
            "FUFIRE_ADMIN_TOKEN is short (<%d chars); use a high-entropy token, "
            "e.g. secrets.token_urlsafe(32)",
            _MIN_ADMIN_TOKEN_LEN,
        )


def _verify_admin(token: str | None) -> None:
    """Raise 503 if issuance isn't configured, 401 if the token is missing/wrong.

    Order matters: a missing admin token / missing store is a *server*
    misconfiguration (503), independent of what the caller sent. A configured
    server with a bad caller token is 401.
    """
    configured_token = _admin_token()
    # Defense-in-depth: warn once if a configured token is weak. Done here (the
    # single funnel for every issuance attempt) rather than at startup because
    # the token may be injected/rotated after import.
    _warn_if_weak_admin_token(configured_token)
    store = get_key_store()
    if configured_token is None or store is None:
        raise HTTPException(
            status_code=503,
            detail={
                "error": "issuance_not_configured",
                "message": "key issuance not configured",
                "detail": {},
            },
        )
    if not token or not hmac.compare_digest(token, configured_token):
        raise HTTPException(
            status_code=401,
            detail={
                "error": "unauthorized",
                "message": "Missing or invalid X-Admin-Token header",
                "detail": {},
            },
            headers={"WWW-Authenticate": "AdminToken"},
        )


@router.post(
    "/admin/keys",
    response_model=IssueKeyResponse,
    # 200 (not 201): issuance is idempotent on jti — a repeat call returns the
    # same existing key rather than creating a new resource. Also keeps the
    # OpenAPI contract's typed-200-response invariant satisfied.
    status_code=200,
    responses={
        400: {"model": ErrorEnvelope},
        401: {"model": ErrorEnvelope},
        503: {"model": ErrorEnvelope},
    },
    summary="Issue a new API key (admin)",
    deprecated=True,
)
@limiter.limit(tier_limit)
async def issue_key(
    request: Request,
    payload: IssueKeyRequest,
    x_admin_token: str | None = Security(_ADMIN_TOKEN_HEADER),
) -> IssueKeyResponse:
    """Mint a real, immediately-valid ``ff_<tier>_<hex>`` API key.

    Requires ``X-Admin-Token``. Only the ``free`` tier may be issued.
    Idempotent on ``jti``. The key is returned exactly once and never logged.
    """
    _verify_admin(x_admin_token)

    tier = payload.tier.strip().lower()
    if tier not in _ALLOWED_ISSUANCE_TIERS:
        # Reject non-allow-listed tiers. Never echo the requested tier into logs
        # beyond what's needed for an audit trail.
        _log.warning("admin.issue.rejected_tier jti=%s tier=%s", payload.jti, tier)
        raise HTTPException(
            status_code=400,
            detail={
                "error": "tier_not_allowed",
                "message": f"Tier '{tier}' may not be issued. Allowed: {sorted(_ALLOWED_ISSUANCE_TIERS)}",
                "detail": {},
            },
        )

    store = get_key_store()
    assert store is not None  # guaranteed by _verify_admin

    key = store.issue(tier=tier, label=payload.label, jti=payload.jti)
    # NEVER log the key — only jti + tier.
    _log.info("admin.issue.ok jti=%s tier=%s", payload.jti, tier)
    return IssueKeyResponse(key=key, tier=tier)
