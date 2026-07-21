"""
services/auth.py — HMAC signature verification for ElevenLabs webhooks.

Extracted from app.py. Supports three authentication methods:
  1. HMAC-SHA256 signature via ElevenLabs-Signature header
  2. Simple API key via X-Api-Key header
  3. Bearer token via Authorization header
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import time
from typing import Optional

_log = logging.getLogger(__name__)


def verify_elevenlabs_signature(
    payload: bytes,
    signature_header: Optional[str],
    secret: str,
    tolerance_ms: int = 300_000,  # 5 minutes
) -> bool:
    """Verify HMAC-SHA256 signature from ElevenLabs-Signature header.

    Header format: "t=<timestamp_ms>,v1=<hex_signature>"

    Args:
        payload:          Raw request body bytes.
        signature_header: Value of the ElevenLabs-Signature header.
        secret:           Shared secret (ELEVENLABS_TOOL_SECRET env var).
        tolerance_ms:     Maximum age of the signature in milliseconds.

    Returns:
        True if signature is valid and within tolerance, False otherwise.
    """
    if not signature_header:
        return False

    parts = signature_header.split(",")
    timestamp_part = next((p for p in parts if p.startswith("t=")), None)
    signature_part = next((p for p in parts if p.startswith("v1=")), None)

    if not timestamp_part or not signature_part:
        return False

    try:
        timestamp = int(timestamp_part.split("=")[1])
    except (ValueError, IndexError):
        return False

    provided_signature = signature_part.split("=")[1]

    now = int(time.time() * 1000)
    if abs(now - timestamp) > tolerance_ms:
        return False

    signed_payload = f"{timestamp}.".encode() + payload
    expected_signature = hmac.new(
        secret.encode(),
        signed_payload,
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(provided_signature, expected_signature)


def verify_request_auth(
    raw_body: bytes,
    *,
    elevenlabs_signature: Optional[str],
    x_api_key: Optional[str],
    authorization: Optional[str],
    secret: str,
    hmac_only: bool = False,
) -> bool:
    """Try auth methods in order. hmac_only=True disables Method 2/3 fallbacks."""
    # Method 1: HMAC signature (preferred, replay-protected)
    if elevenlabs_signature and verify_elevenlabs_signature(raw_body, elevenlabs_signature, secret):
        return True
    if hmac_only:
        _log.warning("webhook.auth_failed hmac_only=True — fallback methods disabled")
        return False
    # Method 2: Simple API key header
    if x_api_key and hmac.compare_digest(x_api_key, secret):
        return True
    # Method 3: Bearer token
    if authorization and authorization.startswith("Bearer "):
        token = authorization[7:]
        if hmac.compare_digest(token, secret):
            return True
    _log.warning(
        "webhook.auth_failed sig=%s key_present=%s bearer_present=%s",
        bool(elevenlabs_signature), bool(x_api_key), bool(authorization),
    )
    return False
