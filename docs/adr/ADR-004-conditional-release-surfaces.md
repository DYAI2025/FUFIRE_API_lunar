# ADR-004: Conditional release surfaces

- Status: accepted for safe release defaults; owner approvals pending where noted
- Date: 2026-07-21

## Decision matrix

| Surface | Owner | Safe default | Production behavior | Release status |
|---|---|---|---|---|
| Engine key issuance | Identity/BFF | `FUFIRE_ENABLE_KEY_ISSUANCE=false` | Startup rejects `true`; use the durable Supabase-backed BFF plane | retired/disabled |
| Multi-replica limiter | Platform | one replica may use memory | Redis is mandatory when `FUFIRE_REPLICA_COUNT>1` or `FUFIRE_REQUIRE_REDIS=true` | implemented; Railway values MISSING |
| ZWDS core-seed | ZWDS domain owner | `FUFIRE_ENABLE_ZWDS=false` | `true` also requires `FUFIRE_ZWDS_SIGNOFF_ID` | practitioner sign-off MISSING |
| Moshier ephemeris | Astronomy owner | development/test only | Production accepts `EPHEMERIS_MODE=SWIEPH` only | implemented |
| BaZi-Hehun marketing | Product/Legal | `FUFIRE_ENABLE_HEHUN_MARKETING=false` | Startup rejects `true`; the consent-gated B2B API itself is unchanged | public launch approval MISSING |
| BaZi Precision V2 default | BaZi domain owner | `FUFIRE_BAZI_PRECISION_V2_DEFAULT=false` | Startup rejects a default switch | default migration approval MISSING |

## HTTP and OpenAPI behavior

Disabled key-issuance and ZWDS routes remain registered internally so a
deployment flag can be checked on every request, but they return the standard
`404 feature_disabled` envelope before authentication or business logic. They
are omitted from that process's generated OpenAPI document. Enabling a flag is
therefore explicit and observable; it is not inferred from the presence of an
admin token, key store, API key, or ruleset file.

The engine key route remains deprecated even when explicitly enabled for a
controlled migration test. ZWDS production enablement without the practitioner
sign-off identifier fails startup. V2 Lunar is additive and is not classified
as a deprecated legacy path.

## Rollback

Set both route flags to false, keep Hehun marketing and the Precision V2
default switch false, and keep production in SWIEPH mode. For a multi-replica
deployment, reducing replicas to one is the only safe temporary alternative to
restoring Redis; process-local counters must never be represented as global.
