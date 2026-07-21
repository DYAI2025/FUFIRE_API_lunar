from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

# Contract-bound error codes (must match spec/schemas/ValidateResponse.schema.json)
ERROR_CODES: List[str] = [
  "REFDATA_NETWORK_FORBIDDEN",
  "REFDATA_MANIFEST_MISSING",
  "EPHEMERIS_HASH_MISMATCH",
  "EPHEMERIS_MISSING",
  "TZDB_SIGNATURE_INVALID",
  "LEAP_SECONDS_FILE_EXPIRED",
  "MISSING_TT",
  "EOP_MISSING",
  "EOP_STALE",
  "EOP_PREDICTED_REGION_USED",
  "DST_AMBIGUOUS_LOCAL_TIME",
  "DST_NONEXISTENT_LOCAL_TIME",
  "INCONSISTENT_BRANCH_ORIGIN_FOR_SHIFTED_LONGITUDES",
  "MISSING_DAY_CYCLE_ANCHOR",
  "MISSING_AYANAMSA_ID",
  "INTERP_DERIVATION_EMPTY",
  "INTERP_LINT_FAIL",
]

Severity = Literal["ERROR", "WARNING"]

def make_issue(
    code: str,
    message: str,
    *,
    severity: Severity = "ERROR",
    path: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    if code not in ERROR_CODES:
        # Fail fast: do not emit unknown codes (would violate schema).
        raise ValueError(f"Unknown error code: {code}")
    issue: Dict[str, Any] = {
        "code": code,
        "message": message,
        "severity": severity,
        "path": path,
        "details": details,
    }
    # Drop nulls to keep output compact (schema allows null)
    if issue["path"] is None:
        issue["path"] = None
    if issue["details"] is None:
        issue["details"] = None
    return issue
