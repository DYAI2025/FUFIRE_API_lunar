"""
test_services_auth.py — Unit tests for bazi_engine/services/auth.py

Tests HMAC signature verification and multi-method auth without any
HTTP dependency. All time-sensitive tests use mocked timestamps.
"""
from __future__ import annotations

import hashlib
import hmac as hmac_mod
import time

from bazi_engine.services.auth import verify_elevenlabs_signature, verify_request_auth

SECRET = "test-secret-key-12345"
PAYLOAD = b'{"birthDate":"2024-02-10"}'


def _make_signature(payload: bytes, secret: str, timestamp: int) -> str:
    """Helper: produce a valid ElevenLabs-style signature header."""
    signed = f"{timestamp}.".encode() + payload
    sig = hmac_mod.new(secret.encode(), signed, hashlib.sha256).hexdigest()
    return f"t={timestamp},v1={sig}"


class TestVerifyElevenLabsSignature:
    def test_valid_signature_returns_true(self):
        ts = int(time.time() * 1000)
        header = _make_signature(PAYLOAD, SECRET, ts)
        assert verify_elevenlabs_signature(PAYLOAD, header, SECRET) is True

    def test_wrong_secret_returns_false(self):
        ts = int(time.time() * 1000)
        header = _make_signature(PAYLOAD, SECRET, ts)
        assert verify_elevenlabs_signature(PAYLOAD, header, "wrong-secret") is False

    def test_tampered_payload_returns_false(self):
        ts = int(time.time() * 1000)
        header = _make_signature(PAYLOAD, SECRET, ts)
        tampered = PAYLOAD + b"TAMPER"
        assert verify_elevenlabs_signature(tampered, header, SECRET) is False

    def test_expired_timestamp_returns_false(self):
        old_ts = int(time.time() * 1000) - 400_000  # 400 seconds ago > 5 min
        header = _make_signature(PAYLOAD, SECRET, old_ts)
        assert verify_elevenlabs_signature(PAYLOAD, header, SECRET) is False

    def test_none_header_returns_false(self):
        assert verify_elevenlabs_signature(PAYLOAD, None, SECRET) is False

    def test_empty_header_returns_false(self):
        assert verify_elevenlabs_signature(PAYLOAD, "", SECRET) is False

    def test_malformed_header_no_timestamp_returns_false(self):
        # Missing 't=' part
        assert verify_elevenlabs_signature(PAYLOAD, "v1=abc123", SECRET) is False

    def test_malformed_header_no_signature_returns_false(self):
        ts = int(time.time() * 1000)
        assert verify_elevenlabs_signature(PAYLOAD, f"t={ts}", SECRET) is False

    def test_custom_tolerance_accepted(self):
        ts = int(time.time() * 1000) - 100_000  # 100s ago
        header = _make_signature(PAYLOAD, SECRET, ts)
        # Default tolerance=300_000ms → should pass
        assert verify_elevenlabs_signature(PAYLOAD, header, SECRET, tolerance_ms=300_000) is True

    def test_custom_tolerance_rejected(self):
        ts = int(time.time() * 1000) - 100_000  # 100s ago
        header = _make_signature(PAYLOAD, SECRET, ts)
        # Tight tolerance=50_000ms → should fail
        assert verify_elevenlabs_signature(PAYLOAD, header, SECRET, tolerance_ms=50_000) is False

    def test_returns_bool_not_truthy(self):
        ts = int(time.time() * 1000)
        header = _make_signature(PAYLOAD, SECRET, ts)
        result = verify_elevenlabs_signature(PAYLOAD, header, SECRET)
        assert result is True  # exactly True, not just truthy


class TestVerifyRequestAuth:
    def _hmac_header(self) -> str:
        ts = int(time.time() * 1000)
        return _make_signature(PAYLOAD, SECRET, ts)

    def test_hmac_auth_succeeds(self):
        header = self._hmac_header()
        assert verify_request_auth(
            PAYLOAD,
            elevenlabs_signature=header,
            x_api_key=None,
            authorization=None,
            secret=SECRET,
        ) is True

    def test_api_key_auth_succeeds(self):
        assert verify_request_auth(
            PAYLOAD,
            elevenlabs_signature=None,
            x_api_key=SECRET,
            authorization=None,
            secret=SECRET,
        ) is True

    def test_bearer_auth_succeeds(self):
        assert verify_request_auth(
            PAYLOAD,
            elevenlabs_signature=None,
            x_api_key=None,
            authorization=f"Bearer {SECRET}",
            secret=SECRET,
        ) is True

    def test_all_none_returns_false(self):
        assert verify_request_auth(
            PAYLOAD,
            elevenlabs_signature=None,
            x_api_key=None,
            authorization=None,
            secret=SECRET,
        ) is False

    def test_wrong_api_key_returns_false(self):
        assert verify_request_auth(
            PAYLOAD,
            elevenlabs_signature=None,
            x_api_key="wrong-key",
            authorization=None,
            secret=SECRET,
        ) is False

    def test_malformed_bearer_returns_false(self):
        # Missing "Bearer " prefix
        assert verify_request_auth(
            PAYLOAD,
            elevenlabs_signature=None,
            x_api_key=None,
            authorization=SECRET,  # no "Bearer " prefix
            secret=SECRET,
        ) is False

    def test_hmac_takes_priority_over_api_key(self):
        """If HMAC is present and valid, other methods are not needed."""
        header = self._hmac_header()
        result = verify_request_auth(
            PAYLOAD,
            elevenlabs_signature=header,
            x_api_key="wrong-key",
            authorization=None,
            secret=SECRET,
        )
        assert result is True


class TestHmacOnlyMode:
    """When hmac_only=True, method 2/3 must be rejected even with correct secret."""

    def test_api_key_rejected_in_hmac_only_mode(self):
        result = verify_request_auth(
            PAYLOAD,
            elevenlabs_signature=None,
            x_api_key=SECRET,
            authorization=None,
            secret=SECRET,
            hmac_only=True,
        )
        assert result is False

    def test_bearer_rejected_in_hmac_only_mode(self):
        result = verify_request_auth(
            PAYLOAD,
            elevenlabs_signature=None,
            x_api_key=None,
            authorization=f"Bearer {SECRET}",
            secret=SECRET,
            hmac_only=True,
        )
        assert result is False

    def test_valid_hmac_accepted_in_hmac_only_mode(self):
        ts = int(time.time() * 1000)
        header = _make_signature(PAYLOAD, SECRET, ts)
        result = verify_request_auth(
            PAYLOAD,
            elevenlabs_signature=header,
            x_api_key=None,
            authorization=None,
            secret=SECRET,
            hmac_only=True,
        )
        assert result is True
