# Error Codes (Contract-bound)

Source of truth:
- spec/schemas/ValidateResponse.schema.json -> definitions/ErrorCode

This document is a convenience index. Do not edit without changing the schema + version bump.

## Codes

- REFDATA_NETWORK_FORBIDDEN
- REFDATA_MANIFEST_MISSING
- EPHEMERIS_HASH_MISMATCH
- EPHEMERIS_MISSING
- TZDB_SIGNATURE_INVALID
- LEAP_SECONDS_FILE_EXPIRED
- MISSING_TT
- EOP_MISSING
- EOP_STALE
- EOP_PREDICTED_REGION_USED
- DST_AMBIGUOUS_LOCAL_TIME
- DST_NONEXISTENT_LOCAL_TIME
- INCONSISTENT_BRANCH_ORIGIN_FOR_SHIFTED_LONGITUDES
- MISSING_DAY_CYCLE_ANCHOR
- MISSING_AYANAMSA_ID
- INTERP_DERIVATION_EMPTY
- INTERP_LINT_FAIL

Notes:
- Severity is per Issue.severity (ERROR/WARNING).
- /validate returns structured issues in errors[] and warnings[].
