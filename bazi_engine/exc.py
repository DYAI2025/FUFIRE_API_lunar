"""
exc.py — Level 0: BaZi Engine exception hierarchy.

No internal imports. Defines structured exceptions that carry HTTP status
and machine-readable error codes. All other modules raise these instead of
bare RuntimeError/ValueError so that app.py can map them correctly.

HTTP status conventions:
  422 InputError             — caller sent bad data (DST gap, invalid coords, …)
  501 NotSupportedError      — feature is not yet implemented
  503 EphemerisUnavailableError — ephemeris files missing / service dependency down
  500 CalculationError       — internal numerical failure (should never reach users)
"""
from __future__ import annotations

from typing import Any, Dict, Optional


class BaziEngineError(Exception):
    """Base class for all domain exceptions.

    Attributes:
        http_status: Suggested HTTP status code for API responses.
        error_code:  Machine-readable snake_case identifier.
        detail:      Optional structured context dict for debugging.
    """
    http_status: int = 500
    error_code: str = "internal_error"

    def __init__(
        self,
        message: str,
        *,
        detail: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(message)
        self.detail = detail or {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "error": self.error_code,
            "message": str(self),
            "detail": self.detail,
        }


class InputError(BaziEngineError):
    """Caller provided invalid or unresolvable input.

    Examples: nonexistent DST times, out-of-range coordinates,
    malformed ISO date strings.
    """
    http_status = 422
    error_code = "input_error"


class EphemerisUnavailableError(BaziEngineError):
    """Swiss Ephemeris data files are missing or inaccessible.

    The service cannot compute astronomical positions without them.
    Returned as HTTP 503 so load-balancers can retry another instance.
    """
    http_status = 503
    error_code = "ephemeris_unavailable"


class CalculationError(BaziEngineError):
    """An internal numerical computation failed unexpectedly.

    Examples: bisection solver did not converge, LiChun crossing not found.
    Always indicates a bug or unsupported edge case — should never be
    triggered by normal user input.
    """
    http_status = 500
    error_code = "calculation_error"


class NotSupportedError(BaziEngineError):
    """Requested feature or backend is not yet implemented."""
    http_status = 501
    error_code = "not_supported"
