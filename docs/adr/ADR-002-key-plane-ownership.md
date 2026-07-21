# ADR-002 — Key-Plane Ownership: Retire Engine Email-Issuance, Consolidate on the Supabase-Backed BFF Plane

- **Status:** Accepted (2026-07-12, Decision D3 — Option A, decided by Benjamin)
- **Deciders:** Benjamin (product owner)
- **Cross-references:** FUFIRE-007 / FUFIRE-012 audit findings;
  `docs/plans/2026-07-11-fufire-api-cleanup-refactoring.md` (Decision D3, Task 2.19)
- **Numbering note:** legacy ADR-1..ADR-7 live in `spec/FuFirE_Addendum_v1.md`
  (e.g. ADR-1: transit `TTLCache`). This file starts the standalone `docs/adr/`
  series at the number reserved by the 2026-07-11 cleanup plan.

## Context

Two API-key planes exist today, built independently, with very different
durability guarantees.

### Plane 1 — `ff_live_*` dashboard keys (LIVE BFF, Supabase-backed)

Owned entirely by the LIVE repo (`DYAI2025/FuFire_API_LIVE`):

- Minted in the BFF: `src/server/keys-router.ts` +
  `src/server/api-key.ts` (`ff_live_<base62>`, CSPRNG, reveal-once).
- Stored in Supabase as a **SHA-256 hash** of the full plaintext
  (`hashApiKey()` in `src/server/api-key.ts`; `key_hash` column is UNIQUE),
  under RLS. Plaintext is never persisted or logged.
- Full lifecycle: rotation (`POST /rotate`, 24 h grace window), revocation
  (`POST /revoke`, immediate), usage counting.
- **Never forwarded upstream.** The BFF proxy authenticates dashboard users
  against Supabase and injects a static env `FUFIRE_API_KEY` toward the
  engine (`src/server/app.ts`); `src/server/dev-key-auth.ts` explicitly
  blocks an `ff_live_` value from being smuggled into the upstream
  `X-API-Key` header.

Survives every deploy of every service. Durable by construction.

### Plane 2 — `ff_free_*` email-funnel keys (engine-minted, memory-only)

Split across both repos:

- LIVE's email confirm flow (`GET /api/keys/confirm` in
  `src/server/app.ts`) calls the engine's `POST /v1/admin/keys`
  (`bazi_engine/routers/admin.py`), authenticated via `X-Admin-Token`.
- The engine mints `ff_free_*` keys (issuance allow-list
  `_ALLOWED_ISSUANCE_TIERS = {"free"}` in `routers/admin.py`) and persists
  them **only in process memory**: `bazi_engine/key_store.py` supports
  backends `none` (default) and `memory`; a `postgres` backend is
  documented-as-planned but not implemented; `firestore` is hard-rejected
  with a `ValueError`.
- The plaintext key is emailed to the user (Brevo client in LIVE); the
  engine never logs key material (only `jti` + `tier`).
- Issuance is idempotent on `jti` — but the `jti → key` map lives in the
  same in-memory store, so idempotency also resets on restart.

**Consequence as-built: every engine deploy (Railway auto-deploys on each
push to `main`) silently invalidates all previously emailed free-tier keys.**
Affected users get 401s with no signal that their key ceased to exist
(FUFIRE-007: non-durable KeyStore).

## Decision (Option A)

1. **Retire engine email-issuance.** Free-tier keys move onto the
   Supabase-backed BFF plane and get the same treatment as `ff_live_*`
   keys: minted in LIVE, SHA-256-hashed at rest, RLS-scoped,
   rotate/revoke/usage-count lifecycle.
2. **Deprecate, don't remove.** The engine's `POST /v1/admin/keys` will be
   marked `deprecated` in the OpenAPI contract. Deprecation is
   contract-legal under the frozen-endpoint rule; actual removal happens
   only after a lifecycle gate backed by usage telemetry shows the route
   is dead.
3. **Ownership boundary.** The engine stays a stateless calculation
   service. Identity and key lifecycle live in the product layer (LIVE +
   Supabase), where a durable store, RLS, and an admin surface already
   exist.

## Consequences

- **Interim risk (until the implementation slice ships):** every Railway
  deploy of the engine continues to invalidate all emailed free keys —
  silent 401s for those users. This ADR documents the risk; it does not
  yet remove it.
- **Implementation slice** happens in the LIVE repo (Supabase mint for the
  free tier, reusing the `keys-router.ts` machinery) plus the engine-side
  deprecation marking of `/v1/admin/keys`. It is a follow-up slice, not on
  the cleanup plan's critical path.
- **`ff_live_*` users are unaffected throughout** — their plane does not
  change.
- **Option B rejected** (implement the planned Postgres KeyStore backend
  inside the engine): it would create a second key database, duplicate the
  rotation/revocation/usage lifecycle that Supabase already provides, and
  make the engine stateful — the opposite of the ownership boundary above.
