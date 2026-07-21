# Release Notes - 1.0.0-rc0

## Highlights

- Contract-first /validate endpoint (spec/schemas Draft-07, contract is law).
- Canonical ruleset standard_bazi_2026.
- Deterministic validation (now_utc_override + config_fingerprint).
- Offline-safe refdata policy (no implicit network/download).

## Upgrade Notes

- IMPORTANT: Swiss Ephemeris files are no longer downloaded automatically.
  If you use legacy endpoints that require Swiss Ephemeris, provide the files explicitly:
  - Set SE_EPHE_PATH to a directory that contains the required *.se1 files, OR
  - Pass ephe_path in request payloads that accept it.

- For contract testing, use /validate and provide:
  - now_utc_override (for deterministic behavior)
  - refdata_manifest_inline (for offline modes)

## Known Limitations (rc0)

- /validate focuses on contract compliance and deterministic policy checks.
  Full chart computation remains available via legacy endpoints but requires external refdata provisioning.
