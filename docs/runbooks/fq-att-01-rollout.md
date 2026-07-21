# Runbook: FQ-ATT-01 staged rollout (`FUFIRE_MOSEPH_ATTESTATION_ENFORCE`)

| Field | Value |
|---|---|
| Feature | `fufire-premium-verification-ci` (WS-A increment) |
| REQ | `FQ-ATT-01` |
| PRD | `docs/prd/fufire-premium-verification-ci.prd.md` (NFR-ATT-1) |
| Plan task | T6 |
| ADRs | `docs/architecture/adr-fq-att-01-mechanism.md`, `docs/architecture/adr-fq-att-01-houses-class.md` |

---

## What this hardens

FQ-ATT-01 closes the last gaps where `bazi_engine` could silently compute a
response using the Moshier (MOSEPH) analytical ephemeris fallback while a
customer requested (or expected) full Swiss Ephemeris (SWIEPH) precision, and
closes the structurally-undetectable "houses computed against an unattested
ephemeris state" gap (ADR-2). Concretely, as of this change:

- Every `swe.calc`/`swe.calc_ut`/`swe.fixstar*` call in `bazi_engine/` is
  routed through `SwissEphBackend.calc_ut()` (or the free functions
  `ephemeris.calc_checked()` / `ephemeris.fixstar_checked()`), which raises
  `EphemerisUnavailableError` (HTTP 503) if MOSEPH was silently used when
  SWIEPH was requested.
- `SwissEphBackend.houses()` now refuses to compute house cusps unless an
  attested `calc_ut()` call has already succeeded on the same backend
  instance (ADR-2's precondition-gate).
- `routers/info.py`'s `/health` dependency check (`_check_ephemeris()`) now
  goes through the same `SwissEphBackend` construction-time guard and
  `calc_ut()` attestation as every other calculation endpoint (previously the
  one genuinely-unguarded call site, PRD §3.1 site 4 / AC-01-6).

This is a **hardening** change: call sites that were previously silently
tolerant of an unrequested MOSEPH fallback now hard-fail (503) instead. That
is the entire point of FQ-ATT-01 — but per NFR-ATT-1, hardening a previously
tolerant path always carries the risk of surfacing a **pre-existing, until-now
invisible** MOSEPH dependency as a fleet of 503s the moment it goes live.

## The rollback lever: `FUFIRE_MOSEPH_ATTESTATION_ENFORCE`

| Value | Behavior |
|---|---|
| unset (default), or any value other than the literal string `"false"` (case-insensitive) | **Hard-fail** (default, production-recommended). A detected silent MOSEPH fallback, or an unattested `houses()` call, raises `EphemerisUnavailableError` (HTTP 503) exactly as FQ-ATT-01 requires. |
| `"false"` (case-insensitive, e.g. `false`, `FALSE`, `False`) | **Degrade-with-log.** The same conditions are logged as a `WARNING` (via the `bazi_engine.ephemeris` logger) instead of raising. The response proceeds using whatever the underlying `pyswisseph` call actually returned. |

This is implemented in `bazi_engine/ephemeris.py`:
- `moseph_attestation_enforced()` reads the env var once per check (no
  caching — always reflects the current environment value).
- `assert_no_moseph_fallback()` (the flag-checkable class: `calc_ut`,
  `calc_checked`, `fixstar_checked`, and — transitively — `sun_lon_deg_ut`)
  consults the toggle before raising.
- `SwissEphBackend.houses()` (the flag-less class, ADR-2's precondition-gate)
  consults the same toggle before raising, for a single, consistent rollback
  lever across both halves of FQ-ATT-01's hardening.

**The degrade-with-log state is a staging-only escape hatch.** It exists
solely so a staged rollout can detect an unexpected volume of newly-surfaced
`EphemerisUnavailableError` conditions without taking production traffic down
immediately. It is never the recommended steady state for any environment,
staging included — the goal is always to reach zero degraded events and flip
back to (or leave at) the default hard-fail behavior.

## Staged rollout procedure

1. **Staging first.** Deploy this change to staging with the toggle at its
   default (unset = hard-fail). Do not pre-emptively set
   `FUFIRE_MOSEPH_ATTESTATION_ENFORCE=false` "just in case" — the point of
   this step is to observe real hard-fail behavior against real staging
   traffic patterns.
2. **Monitor for unexpected `EphemerisUnavailableError` volume.** Watch
   staging's error rate / logs for HTTP 503 `ephemeris_unavailable` responses
   on `/calculate/*`, `/transit/*`, and `/health`. A pre-existing, previously
   silent MOSEPH dependency (e.g. a misconfigured `SE_EPHE_PATH` in some
   environment, or a request path this PRD's discovery (T1) did not
   anticipate) would show up here as a new, unexpected spike.
3. **If an unexpected spike appears:** flip the toggle
   (`FUFIRE_MOSEPH_ATTESTATION_ENFORCE=false`) in the affected environment
   ONLY — this restores the previous (pre-hardening) degrade-silently
   behavior, logged instead of raised, while you investigate root cause. Do
   **not** revert the code change; the centralized wrapper code
   (`SwissEphBackend.calc_ut()`/`.houses()`, `ephemeris.calc_checked()`,
   `fixstar_checked()`) stays in place regardless of the toggle's value —
   only the raise-vs-log behavior changes (PRD §12).
4. **Root-cause and fix** whatever produced the unexpected MOSEPH usage
   (missing `.se1` files in that environment, a misconfigured
   `SE_EPHE_PATH`, etc.) — the toggle is a rollback lever, not a permanent
   fix.
5. **Once staging shows zero unexpected degraded/hard-fail events** over a
   representative traffic window, promote to production with the toggle
   still at its default (hard-fail). Production should never need the
   `false` setting if staging validation was done properly — if it does,
   treat that as a signal to re-open investigation, not to leave the escape
   hatch on indefinitely.

## Rollback = toggle flip, not a code revert

Per PRD §12: if FQ-ATT-01's hardening needs to be rolled back in any single
environment, set `FUFIRE_MOSEPH_ATTESTATION_ENFORCE=false` in that
environment's configuration (Railway variables, or the equivalent for
staging) and redeploy/restart to pick up the new env value. This is
deliberately faster and lower-risk than reverting the code change, and keeps
the centralized attestation wrapper code in place (so the AST/grep static
guard, AC-01-5, continues to hold zero direct `swe.calc*`/`houses*`/
`fixstar*` calls outside `bazi_engine/ephemeris.py` regardless of the
toggle's runtime value).

## What this does NOT cover

- This runbook is scoped to FQ-ATT-01 only. `FQ-ATT-02` (attestation field
  coverage on response bodies, `tzdata` pinning) is a separate, independently
  rollout-able track (T7–T11) with no shared toggle.
- WS-D (CI gate / release-gate expansion, e.g. making these tests a required
  branch-protection check, or wiring `EphemerisUnavailableError` volume into
  an alerting dashboard) is explicitly out of scope for this increment — see
  `docs/canvas/fufire-premium-verification-ci.canvas.md` § Non-goals.

## CONTRA-1 resolution note (added 2026-07-01)

The plumbline-watcher's per-increment True-Line check flagged that the
`/health` claim above (`_check_ephemeris()` closing AC-01-6/VCHK-05) was
asserted as done while its own acceptance test,
`tests/test_ephemeris_attestation.py::TestConstructionGuardClassEmptyDirectory::test_health_reports_unavailable_under_missing_se1_files`,
was still failing. Independent investigation confirmed the test's own
simulation methodology was stale (it forced the failure via a direct
`swe.set_ephe_path()` call, written against the *pre-migration*
`_check_ephemeris()` that never constructed a backend at all) — it did not
match how the already-migrated `_check_ephemeris()` actually behaves. Fixed by:
correcting the test to use the same `SE_EPHE_PATH` + cache-clear methodology as
its `bazi` sibling test, and removing the `@lru_cache` on
`ensure_ephemeris_files()` (it was masking a live filesystem/env change for the
remainder of a process's lifetime — most consequential for `bazi.py`'s
`solcross_ut()`-only-protected path, which has no return-flag check as a
second line of defense). The claim in this runbook is now backed by a passing,
order-independent test — verified via
`SE_EPHE_PATH=~/.cache/bazi_engine/swisseph pytest tests/test_ephemeris_attestation.py -q`
and in isolation (single-test invocation, no reliance on prior test ordering).
