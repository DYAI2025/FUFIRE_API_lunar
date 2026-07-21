"""bafe: BaZodiac Fusion Engine (contract-first core)

This package implements the spec-conform core pieces required for /validate:
- JSON Schema (Draft-07) request/response validation
- Error catalog (contract-bound)
- RefData policy checks (no-network guard)
- Mapping conventions (SHIFT_BOUNDARIES / SHIFT_LONGITUDES), HALF_OPEN segmentation
- Ruleset loader (standard_bazi_2026)
- Deterministic config fingerprint (canonical JSON)

Note: This core is designed to be used from the legacy FastAPI app as an adapter.
"""

from .service import validate_request

__all__ = ["validate_request"]
