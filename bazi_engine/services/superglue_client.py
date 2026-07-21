"""
services/superglue_client.py — HTTP client for Superglue.ai hooks.

Calls POST https://api.superglue.ai/v1/hooks/<hook>?token=<SUPERGLUE_API_KEY>
with a JSON payload and returns the parsed response.

Environment:
    SUPERGLUE_API_KEY — API token for superglue.ai (required in production)

Note:
    The token is passed as a URL query parameter (?token=...) because that
    is the format required by the Superglue.ai hooks API. This is intentional.
"""
from __future__ import annotations

import os
from typing import Any, Dict

import httpx

_SUPERGLUE_BASE = "https://api.superglue.ai/v1/hooks"
_TIMEOUT = 30.0  # generous: Superglue may run enrichment logic server-side


class SuperglueConfigurationError(RuntimeError):
    """Raised when the Superglue service token is not configured."""


async def call_hook(hook_name: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """POST to a Superglue hook and return the parsed JSON response.

    Args:
        hook_name: Hook identifier, e.g. ``bazodiac-elevenlabs-context``
        payload:   JSON body sent to the hook.

    Returns:
        Parsed JSON response dict from Superglue.

    Raises:
        SuperglueConfigurationError: If the Superglue service token is not set.
        httpx.HTTPStatusError: If Superglue returns a non-2xx status.
        httpx.TimeoutException: If the request exceeds 30 s.
    """
    token = os.environ.get("SUPERGLUE_API_KEY", "")
    if not token:
        raise SuperglueConfigurationError(
            "Superglue service is not configured — token missing"
        )

    url = f"{_SUPERGLUE_BASE}/{hook_name}?token={token}"

    async with httpx.AsyncClient(timeout=_TIMEOUT, headers={"User-Agent": "bafe-bazi-engine/1.0"}) as client:
        resp = await client.post(url, json=payload)
        resp.raise_for_status()
        return resp.json()
