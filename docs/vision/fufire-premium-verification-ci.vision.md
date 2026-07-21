# Product Vision: fufire-premium-verification-ci (increment 1 — WS-A: attestation end-to-end)

> Canvas: `docs/canvas/fufire-premium-verification-ci.canvas.md` (Status: `user-confirmed`, 2026-07-01)
> PRD: `docs/prd/fufire-premium-verification-ci.prd.md` (REQ-IDs `FQ-ATT-01`, `FQ-ATT-02`)
> Traceability: `docs/traceability.md` § Feature `fufire-premium-verification-ci` — increment 1
> Council: `docs/archive/2026-07-01-fufire-premium-verification-ci.md` (verdict: SHARPEN)
>
> **Scope of this Vision: WS-A only** (FQ-ATT-01 no silent MOSEPH fallback; FQ-ATT-02 no
> `"unknown"` quality/provenance fields). WS-B/C/D/E/F and FQ-030 are out of scope — they
> get their own follow-on canvases/visions per the canvas's own scope decision.

## Target User
Explicit: Broad — any paying FuFirE API customer/integrator that depends on non-degraded,
verifiable calculation accuracy. Not limited to the Bazodiac/`New_Bazi` BFF that originally
surfaced the need. Value claims and acceptance criteria are a general platform guarantee,
not BFF-specific.
Assumption: none — this was an open question at canvas-draft time and was explicitly
resolved by the user.
Missing: none.
Source: canvas §2 ("Decided (user, 2026-07-01): broad"); PRD §0.3.
User decision: CONFIRMED (user, 2026-07-01) — target user is broad, not BFF-specific.

## User Problem
Explicit: A paying API customer cannot currently tell, and FuFirE cannot currently prove,
that a given calculation response was actually computed with the high-precision Swiss
Ephemeris backend rather than a silently-substituted Moshier (MOSEPH) analytical
approximation. The fields that exist specifically to let a customer verify this
(`quality_flags.ephemeris_mode`, `quality_flags.house_system_fallback`,
`provenance.ephemeris_id`, `provenance.tzdb_version_id`) are sometimes the literal string
`"unknown"`, or are entirely absent from three response models (`BaziResponse`,
`WxResponse`, `TSTResponse`) today. Concretely: the flag-checking mechanism
(`assert_no_moseph_fallback`) exists but was, before this increment's discovery pass, of
unconfirmed and in fact incomplete coverage — 4 real call sites across 3 files bypass it
today (`western.py:64,93`, `transit.py:131`, `routers/info.py:90`), and `tzdb_version_id`
demonstrably returns `"unknown"` because `tzdata` is not a declared, pinned dependency
anywhere in the project.
Assumption: none — every fact above is a `belegt` (directly verified) finding in the PRD,
not inferred.
Missing: No quantified business/monetary harm (churn, refund, contractual SLA breach) is
stated by the source doc, canvas, or PRD — the value framing here is deliberately
qualitative (trust/provability), not a dollar figure. Not invented here.
Source: canvas §1 (G3); PRD §3.1–§3.5.
User decision: n/a — this is a factual problem statement, not a decision point.

## Desired Change
Explicit: After this increment, two things become structurally true for every calculation
endpoint, not just the ones already covered:
1. No calculation path (`swe.calc`, `swe.calc_ut`, `swe.fixstar*`, `swe.houses*`) can
   silently substitute MOSEPH for SWIEPH — either it is flag-checked and raises
   `EphemerisUnavailableError` before a response is built, or (for the flag-less
   `houses*` family) it fails closed through a separately-designed guard. Zero direct
   `swe.*` calls of these families exist outside `bazi_engine/ephemeris.py`.
2. Every calculation endpoint's response carries real, non-`"unknown"`, non-absent values
   for `ephemeris_mode`, `ephemeris_id`, `tzdb_version_id`, and (on house-computing
   endpoints only — `western`/`fusion`/`chart`/`experience/*`, per OQ-1) `house_system_fallback`.
   `tzdb_version_id` is sourced from a pinned `tzdata` dependency, not a best-effort probe
   that silently falls back to a placeholder string.
Assumption: none — this is a direct restatement of FQ-ATT-01/FQ-ATT-02 (PRD §4).
Missing: none for this increment; the mechanism choice itself (per-call-site wrapper vs.
import-boundary interception, and the houses-class design) is explicitly left to the
planner/architect via ADR — not a product-value question, so not resolved here.
Source: PRD §4 (FQ-ATT-01, FQ-ATT-02), §6 (architecture options, deliberately undecided).
User decision: n/a — implementation mechanism is a planner/architect decision, not a
product decision.

## Core Value Promise
Explicit: A paying customer's calculation request either (a) returns a result they can
trust was computed at full Swiss-Ephemeris precision, provably so via attestation fields
that are always real values, or (b) fails honestly and explicitly (503
`EphemerisUnavailableError`) instead of silently degrading and returning a 200 with
lower, unstated precision. **This is a baseline correctness/reliability guarantee owed to
every paying customer — explicitly not a premium-tier differentiator.** The council's
SHARPEN verdict required this framing correction before PRD drafting, and it is carried
forward here as binding: "premium" language is reserved for the later, separate
accuracy-threshold work (WS-C/FQ-030), which is a genuinely different kind of claim (a
numeric accuracy tier) from this increment's claim (no silent degradation, ever).
Assumption: none — directly required by concilium SHARPEN #1 and PRD §0.1.
Missing: none.
Source: concilium report (Recommendation: SHARPEN, point 1); PRD §0.1; canvas §4.
User decision: CONFIRMED (user said "proceed" on the council recommendation, 2026-07-01,
per concilium report's closing line) — accepted this framing into the PRD without
amendment.

## Why Now
Explicit: The gap (G3 in the source doc) was found during discovery to be small in file
count but real and multi-file — not theoretical. Hardening it now is the structural
prerequisite the source doc's own recommended execution order depends on: independent JPL
oracle work (WS-B), historical TZ accuracy (WS-C), CI gate expansion (WS-D), scheduled
audit (WS-E), and prod observability (WS-F) all build on top of attestation being
trustworthy first. Doing WS-B/C/D/E/F before WS-A would mean building verification
machinery on top of a foundation that can still silently lie about which ephemeris backend
actually ran.
Assumption: none — this is the source doc's own stated ordering, adopted by the canvas.
Missing: none.
Source: canvas §4 ("structural foundation the later increments build on, per the source
doc's own recommended ordering").
User decision: n/a — sequencing rationale, not a decision point requiring confirmation.

## Non-Goals
Explicit: No change to astrological interpretation/narrative content. No new
customer-facing endpoints. No move away from Swiss Ephemeris as the runtime engine (JPL
Horizons stays oracle-only, is WS-B, deferred). No deploy-target change — Railway remains
the target, correcting the source doc's Cloud-Run framing. WS-B (JPL/Jié independent
oracle), WS-C (historical TZ accuracy), FQ-030 (threshold ratification), WS-D (CI gate
expansion incl. the release gate), WS-E (scheduled Claude audit), and WS-F (prod runtime
observability) are all explicitly out of scope for this increment — each gets its own
follow-on canvas/PRD/vision.
Assumption: none.
Missing: none.
Source: canvas §7.
User decision: CONFIRMED (user, 2026-07-01) — scope sliced to WS-A only; deploy target
confirmed Railway.

## Success Signal
Explicit: `pytest tests/test_ephemeris_attestation.py -q` green, parametrized over every
calculation endpoint, under a forced-MOSEPH test environment (`SE_EPHE_PATH` pointed at an
empty directory) — every endpoint raises `EphemerisUnavailableError`. An AST/grep guard
shows zero direct `swe.calc*`/`swe.houses*`/`swe.fixstar*` calls outside
`bazi_engine/ephemeris.py`. A per-endpoint attestation contract test
(`pytest -k attestation_contract`) shows `ephemeris_mode`, `house_system_fallback` (scoped
per OQ-1), `ephemeris_id`, `tzdb_version_id` present and never `"unknown"` on every
calculation response. `python scripts/export_openapi.py --check` stays green after the
schema fields move from optional-in-practice to reliably-real-valued.
Assumption: none — this is the canvas's own confirmed success signal, unmodified.
Missing: none for this increment. (Full-initiative DoD — JPL/Jié diffs, premium
thresholds, nightly live diff, weekly Claude audit, release-gate prod-smoke — belongs to
deferred follow-on increments, not this one.)
Source: canvas §5.
User decision: CONFIRMED (canvas §5, Status: CONFIRMED).

## Risks if Misbuilt
Explicit — what would make this *useless despite green tests* (product-owner synthesis
for the Gate D judgment this Vision feeds into later):
- **Partial-coverage-disguised-as-complete.** The AST/grep static guard could have a blind
  spot (e.g. dynamic import, `getattr(swe, "calc_ut")`, a new file added after the guard's
  regex was written) — tests stay green while a real unguarded call site exists. The guard
  itself must be tested against an intentionally-reintroduced violation, not just run
  against the current clean tree (see VCHK-04).
- **Fake-attested values.** An attestation field could be hardcoded or stubbed to satisfy
  the contract test (e.g., a constant `"SWIEPH"` or a fixed tzdata string) without the
  value being causally derived from the actual ephemeris backend / actually-installed
  `tzdata` package used at request time. A green contract test proves the field exists and
  has the right shape, not that it reflects reality — VCHK-02 exists specifically to close
  this gap.
- **Houses-class guard that fails on paper only.** `swe.houses*` returns no flag at all
  (verified, PRD §3.3) — whichever design the planner chooses (precondition-gate,
  construction-time guarantee, or a documented combination) could be asserted as "closing
  the gap" in an ADR while the actual behavior under a forced-MOSEPH/missing-`.se1`
  condition still silently returns geometrically-computed-but-unattested house cusps. This
  must be demonstrated end-to-end against a real house-computing endpoint request, not
  just documented as a residual-risk paragraph (VCHK-03).
- **`/health` still the blind spot.** `routers/info.py:90`'s `_check_ephemeris()` was the
  one genuinely-unguarded site found (not merely duplicated-but-correct like `western.py`
  and `transit.py`) — it is exactly the signal an operator or automated monitor would
  trust to detect this class of degradation. If it is migrated on paper (code changed) but
  not actually exercised under a forced-MOSEPH condition in a real test, the single
  clearest safety signal in the whole system stays silently broken (VCHK-05).
- **Rollout breaks production instead of protecting customers.** If MOSEPH is silently
  active on some live path today that nobody has found yet, hardening to hard-fail could
  convert a degraded-but-200 response into a fleet of customer-facing 503s without the
  staged, env-toggled rollout (NFR-ATT-1) actually being used — the fix would be
  technically correct and still harm the exact customers it's meant to protect.
- **Contract customers never see.** If the OpenAPI spec is regenerated but not actually
  consulted/consumed by any real downstream integrator, "the contract is correct" and "a
  customer can act on it" are different claims — this increment does not assert (and must
  not silently start asserting) that any consumer currently reads `quality_flags` (OQ-3);
  the value promise is the structural guarantee itself, not a claimed behavior change in
  downstream systems.
- **Concurrency-blind guard.** Every test above, including a naive reading of VCHK-01,
  could be single-threaded and still pass while the chosen flag-checking mechanism (§6.1)
  is defeated — or produces false-positive 503 storms — under real concurrent production
  load. FastAPI runs the synchronous calculation path-operation functions in a shared
  thread pool against process-global `pyswisseph` C-library state (PRD §3.7); `western.py`'s
  `_SWE_LOCK` only guards the sidereal mode reset, not `calc_ut`/`houses` calls. NFR-ATT-4
  (PRD §8) requires a concurrent-request test, but the original VCHK list had no
  corresponding entry for it — a guard proven correct under `pytest -q`'s default
  single-threaded execution is not the same claim as one proven safe under real concurrent
  traffic (VCHK-07; spec-auditor finding, 2026-07-01).
Assumption: the risk framing above is product-owner synthesis grounded in PRD §3 findings
and PRD §6 architecture options — it goes beyond literal restatement of the PRD and should
be read as this Vision's interpretive contribution, to be checked (not re-litigated) at
the Gate D reality-ledger review after implementation.
Missing: none.
Source: PRD §3.1–§3.8, §6.1–§6.2, §8 (security matrix), §12 (rollout/rollback); canvas §8.
User decision: n/a — risk synthesis for later Gate D use, not a decision requiring
confirmation now.

## QA Value Checks
Explicit — VCHK-IDs QA must verify as *customer value*, not merely function, before this
increment is considered real (each one exists specifically to defeat one of the "Risks if
Misbuilt" above; each demands a real/wired proof, not a stub or unit-level assertion in
isolation):
- **VCHK-01a** (flag-checkable class: `calc`/`calc_ut`/`fixstar*`, today `western.py:64`,
  `transit.py:131`) — On a real HTTP request through the app, with ephemeris files
  **present** (construction-time guard passes) but the return flags from
  `swe.calc_ut`/`swe.fixstar*` mocked/forced to `SEFLG_MOSEPH`, the request fails hard
  (`EphemerisUnavailableError`/503) — proving the migrated (T2/T4) return-flag detection
  is actually reached and correct for the newly chosen mechanism. **An empty-directory
  test does not prove this for this class**: `SwissEphBackend.__post_init__`'s
  construction-time `ensure_ephemeris_files()` check raises before any
  `swe.calc_ut`/`assert_no_moseph_fallback` code executes, so a silently broken or missing
  flag-checking wrapper would go undetected by that methodology alone (spec-auditor
  finding, 2026-07-01).
- **VCHK-01b** (flag-less/construction-time-guard class: `routers/info.py:90`'s `/health`
  check, and any endpoint whose only protection is the missing-files guard) — Under a
  forced-MOSEPH environment (`SE_EPHE_PATH` → empty dir), a real HTTP request through the
  app returns a hard failure (`EphemerisUnavailableError`/503, or `/health` reports
  `unavailable`) — this empty-directory methodology is correct and sufficient for this
  class specifically, since the construction-time guard is exactly what it exercises.
- **VCHK-02** — On a real, successful (2xx) request to every calculation endpoint (not a
  mocked/monkeypatched environment), `provenance.tzdb_version_id` is a real IANA tzdata
  version string traceable to the actually-installed, pinned `tzdata` package version —
  not a hardcoded literal that merely satisfies a contract-shape test.
- **VCHK-03** — The `swe.houses*` (flag-less) guard is demonstrated end-to-end: a real
  request to a house-computing endpoint (`western`/`fusion`/`chart`/`experience/*`) under
  a forced-MOSEPH / missing-`.se1` condition fails closed, exactly like the flag-checkable
  class — not merely documented as an accepted residual risk in an ADR.
- **VCHK-04** — The AST/grep static guard is proven to actually catch violations: run it
  against a deliberately, temporarily reintroduced direct `swe.calc_ut`/`houses`/`fixstar`
  call outside `ephemeris.py` and confirm it fails the build — not just confirmed green
  against the current already-clean tree.
- **VCHK-05** — `/health`'s `_check_ephemeris()` (`routers/info.py:90`, the one previously
  genuinely-unguarded site) is confirmed, via a real forced-MOSEPH probe against the live
  `/health` route, to report unavailable — since this is the one signal most likely to be
  relied on operationally to detect exactly this class of degradation.
- **VCHK-06** — The regenerated OpenAPI contract (`spec/openapi/openapi.json`) actually
  reflects the field changes a downstream integrator would need to see: attestation fields
  present on `BaziResponse`/`WxResponse`/`TSTResponse` (previously absent), and
  `house_system_fallback` present only on house-computing endpoints and absent elsewhere,
  per OQ-1's confirmed scope — checked against the committed, regenerated spec file, not
  just the `--check` exit code.
- **VCHK-07** — Concurrency: a real concurrent-request test against the chosen T2/T4
  flag-checking mechanism (not a single-threaded assertion) confirms the guard holds under
  FastAPI's shared-threadpool execution model — proving NFR-ATT-4 (PRD §8) is not merely
  single-threaded-clean but actually safe (no false-negative pass-through, no
  false-positive 503 storm) when multiple threads call `swe.calc_ut`/`swe.houses*`
  concurrently against the same process-global `pyswisseph` C-library state (PRD §3.7).
Assumption: VCHK-01a/VCHK-01b through VCHK-07 are product-owner synthesis (mapped to the
seven risks above, with VCHK-01 split into VCHK-01a/VCHK-01b per spec-auditor finding
2026-07-01); they are additive to, not a replacement for, the PRD's own AC-01-1…AC-01-6
(including the AC-01-4a/AC-01-4b split) and AC-02-1…AC-02-6 (functional acceptance
criteria) and NFR-ATT-1…NFR-ATT-6. QA/Gates A–C own functional correctness; these VCHK
items are what Gate D (product-owner) will specifically check for real, wired, non-fake
customer value at final review.
Missing: none.
Source: PRD §7 (acceptance criteria), §8 (security matrix), §12 (rollout); this Vision's
own Risks-if-Misbuilt section above.
User decision: n/a — QA/product-owner-owned verification design, not a user decision
point.

## User Confirmation
Explicit: Obtained. The user was shown the full PRD and this Vision in full text and
confirmed both via the orchestrator's explicit confirmation prompt, which stated that
confirming serves as the required Vision GO-gate confirmation ("I confirm this Product
Vision as the basis for AgileTeam planning.").
Assumption: none.
Missing: none.
Source: user response to orchestrator confirmation prompt, 2026-07-01.
User decision: CONFIRMED (user, 2026-07-01).

Status: user-confirmed
Confirmed by: user
Confirmed at: 2026-07-01
Open contradictions: none identified at drafting time. All four open questions raised
during canvas drafting were resolved by the user (deploy target → Railway; target user →
broad; scope → WS-A first; premium threshold → provisional-until-ratified). OQ-1 (scope of
`house_system_fallback`) was resolved by the user during PRD drafting (CONFIRMED,
2026-07-01). OQ-2 (`/validate` in scope?), OQ-3 (do downstream consumers read
`quality_flags`?), and OQ-4–OQ-8 (architecture/implementation details) remain open per the
PRD but are explicitly not BLOCKERs — none contradicts this Vision's value claims.
