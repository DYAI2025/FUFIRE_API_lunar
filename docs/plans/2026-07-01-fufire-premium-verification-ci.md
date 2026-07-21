# Plan: fufire-premium-verification-ci (WS-A: attestation end-to-end)

| Field | Value |
|---|---|
| PRD | `docs/prd/fufire-premium-verification-ci.prd.md` (REQ-IDs `FQ-ATT-01`, `FQ-ATT-02`) |
| Canvas | `docs/canvas/fufire-premium-verification-ci.canvas.md` |
| Vision | `docs/vision/fufire-premium-verification-ci.vision.md` |
| Traceability | `docs/traceability.md` § `fufire-premium-verification-ci` — increment 1 |
| ADRs | `docs/architecture/adr-fq-att-01-mechanism.md` (§6.1 → **Option A**), `docs/architecture/adr-fq-att-01-houses-class.md` (§6.2 → **construction-time + precondition-gate**) |
| Phase | Phase 1 (planner) output — task/test design only, **no code changes made by this plan** |
| Task IDs | T1–T12, exactly as numbered in PRD §11 / `docs/traceability.md` — not renumbered |

---

## Goal

Land FQ-ATT-01 (zero silent MOSEPH fallback on any calc path) and FQ-ATT-02 (attestation
fields guaranteed non-`"unknown"`, `tzdb_version_id` pinned) per the PRD's acceptance
criteria (§7, AC-01-1…6, AC-02-1…6) and the Vision's QA value checks (VCHK-01a/01b,
02–07), using the two architecture decisions now fixed by ADR (see table above).

## Non-goals (inherited from PRD §0/canvas §7 — not re-litigated here)

WS-B (JPL/Jié oracle), WS-C (historical TZ accuracy), FQ-030 (threshold ratification),
WS-D (CI gate/release-gate expansion), WS-E (scheduled Claude audit), WS-F (prod runtime
observability). No new customer-facing endpoints. No endpoint path/response-*structure*
change — additive fields only. No Cloud Run work. `POST /validate` (BAFE) is **not**
touched by FQ-ATT-02's "never unknown" bar in this plan (OQ-2 default adopted: its
`ephemeris_id`/`null` is a deliberately different, config-dry-run contract) — if T1's
fresh grep in Phase 2 shows `bafe/service.py` needs a wiring change unrelated to that
bar (e.g. sourcing from the same pinned `tzdata` detection as T7/T8 for consistency),
that is a small addendum to T9's scope, not a reopening of OQ-2.

## Preconditions and known gaps (verified during this planning pass, not re-derived from the PRD's summary alone)

- Re-ran `grep -rn "swe\.\(calc\|houses\|fixstar\)" bazi_engine/` (full repo, this
  session) — **confirms the PRD §3.1 baseline exactly, zero new call sites**:
  `western.py:64` (calc_ut), `western.py:93` (houses), `ephemeris.py:98,118` (the
  existing wrapper itself), `transit.py:131` (calc_ut), `routers/info.py:90` (calc_ut,
  no flags arg, no backend). `bazi_engine/bazi.py`'s only `swe.*` call remains
  `swe.julday` (not in either guarded class). T1 in Phase 2 must still re-run this grep
  itself (do not skip it because this plan already did it once) — if it diverges from
  this list, stop and re-triage before continuing T4/T9.
- Re-ran `grep -rln "QualityFlags\|ProvenanceResponse" bazi_engine/routers/*.py` —
  confirms PRD §3.5's coverage table: `bazi.py`, `fusion.py`, `experience.py`,
  `western.py`, `shared.py` (defines both models). `BaziResponse` (`bazi.py`),
  `WxResponse`/`TSTResponse` (`fusion.py`) do not import either model today — matches
  PRD, this is the gap T9 closes.
- Confirmed `tzdata` absent from `pyproject.toml`, `requirements.lock`, and `uv.lock`
  (fresh grep, zero matches) — T7's starting state.
- Confirmed installed `pyswisseph==2.10.3.2` (matches `pyproject.toml`'s
  `pyswisseph>=2.10.3` pin) and confirmed the two ADR's mechanical claims against it
  directly (module-attribute monkeypatch succeeds; `swe.calc_ut` default flags are
  `FLG_SWIEPH|FLG_SPEED` when the flags arg is omitted, exactly `routers/info.py:90`'s
  case; `swe.houses`/`houses_armc*` accept no flags and return no retflag in any
  variant; `swe.fixstar_ut` returns a 3-tuple `(xx, stnam, retflags)`, not 2-tuple like
  `calc_ut`).
- `QualityFlags` (`routers/shared.py:80-98`) currently makes `house_system_fallback`,
  `house_system_requested`, `house_system_used` **required** (non-`Optional`) fields.
  Per OQ-1 (CONFIRMED), non-house endpoints (`bazi`/`wuxing`/`tst`) must **not carry**
  `house_system_fallback` at all (absent, not merely `null`) — reusing `QualityFlags`
  as-is for those three endpoints is not correct. **T9 design note (not a formal ADR —
  a data-modeling detail within FQ-ATT-02's own scope):** introduce a second, slimmer
  model (e.g. `MinimalQualityFlags` with only `ephemeris_mode`, optionally
  `chart_type_quality`) for `BaziResponse`/`WxResponse`/`TSTResponse`, and keep the
  existing `QualityFlags` (house fields intact, required) for
  `western`/`fusion`/`chart`/`experience/*`. Do not make `house_system_fallback`
  `Optional` on the existing model — that would blur the "absent vs. null" distinction
  OQ-1's decision depends on.
- OQ-8 (narrow `ephemeris_mode` to `Literal["SWIEPH"]`?): **this plan does not adopt the
  narrowing in this increment.** It is cosmetic type precision per the PRD's own framing,
  and narrowing now is a needless coupling to T4's completion timing; revisit once WS-D's
  release-gate work independently observes zero MOSEPH-on-2xx in production. Not a
  blocker, not silently decided either — recorded here for `context-keeper`.

## Task list

Two independently-progressable tracks emerge from the file sets below — **T1/T4/T5/T6
(FQ-ATT-01) and T7/T8/T9/T10/T11 (FQ-ATT-02) touch fully disjoint files** and can be
developed as two parallel PRs/workstreams; they converge only at **T12** (final review
gate, sequential, depends on everything).

```
T1 ──► T2 (ADR, done) ──► T4 ──► T5 ──► T6 ──┐
       T3 (ADR, done) ──►┘                   │
                                              ├──► T12
T7 ──► T8 ──┐                                 │
      T9 ───┼──► T10 ──► T11 ──────────────────┘
(T9 also depends on T1's endpoint matrix)
```

---

### T1 — Discovery: authoritative call-site + endpoint-coverage inventory

- **REQ:** FQ-ATT-01, FQ-ATT-02
- **Depends on:** nothing (first task)
- **Files touched:** none (read-only discovery)
- **Action:** Re-run, for real, in Phase 2 (do not treat this plan's pre-check as a
  substitute): `grep -rn "swe\." bazi_engine/` and `grep -rn "response_model=" bazi_engine/routers/*.py`
  cross-referenced against `QualityFlags`/`ProvenanceResponse` imports. Diff against
  this plan's "Preconditions" section baseline above (which itself mirrors PRD §3.1/§3.5).
- **Tests to add/run:** none (discovery only); capture output in the T4/T9 PR
  description as the audit trail this task exists to produce.
- **Acceptance evidence:** AC-01-1. If the grep diverges from this plan's baseline,
  halt T4/T9 and re-triage (new call site → re-run ADR applicability check; new
  endpoint → add to T9's field-addition scope) before continuing.
- **Parallelizable with:** nothing meaningfully depends on waiting for T1 to *start*,
  but T4 and T9 must not treat their own file lists as final until T1's Phase-2 re-run
  confirms no drift from this plan.

### T2 — ADR: mechanism for flag-checkable class (§6.1)

- **REQ:** FQ-ATT-01
- **Status:** **Resolved in this planning phase.** See
  `docs/architecture/adr-fq-att-01-mechanism.md` — **Option A** (per-call-site
  `calc_checked()`/backend-method wrapper + AST/grep static guard), not Option B
  (import-boundary monkeypatch), even though the monkeypatch was verified mechanically
  safe on the installed `pyswisseph==2.10.3.2` — Option A wins on audit-surface
  parity + call-site locality + return-shape heterogeneity, not on the monkeypatch
  being unsafe.
- **Phase 2 action:** read the ADR; carry its function-naming/signature decisions into
  T4. No further decision-making needed here.

### T3 — ADR: design for flag-less `houses*` class (§6.2)

- **REQ:** FQ-ATT-01
- **Status:** **Resolved in this planning phase.** See
  `docs/architecture/adr-fq-att-01-houses-class.md` — construction-time guarantee
  (existing `ensure_ephemeris_files()`) **combined with** a new precondition-gate
  (`SwissEphBackend.houses()` refuses to run unless an attested `calc_ut()` call has
  already succeeded on the same backend instance). Residual gap (sub-request-duration
  file-mutation race, immaterial to `houses()`'s own correctness since it never reads
  `.se1` data) is named and accepted, not silent.
- **Phase 2 action:** read the ADR; carry its method signature into T4.

### T4 — Migrate call sites per T2/T3 decisions

- **REQ:** FQ-ATT-01
- **Depends on:** T1 (confirm no new sites), T2 + T3 (ADRs, already resolved)
- **Files touched:**
  - `bazi_engine/ephemeris.py` — add `calc_checked()` free function (or extend
    `SwissEphBackend.calc_ut()`, already correct at lines 109-120, to be the single
    call point) for the bare `routers/info.py:90` case; add `fixstar_checked()` /
    `fixstar_ut_checked()` preventively (no live call site today, per PRD §3.1, but
    ADR-1 requires it be ready for the first future fixstar call site); add
    `SwissEphBackend._attested` instance flag + `SwissEphBackend.houses()` method per
    ADR-2.
  - `bazi_engine/western.py:64` — replace the manual `flags = backend.flags |
    swe.FLG_SPEED; swe.calc_ut(...); assert_no_moseph_fallback(...)` with
    `backend.calc_ut(jd_ut, pid, extra_flags=swe.FLG_SPEED)`.
  - `bazi_engine/western.py:93` — replace `swe.houses(jd_ut, lat, lon, sys_char)` with
    `backend.houses(jd_ut, lat, lon, sys_char)`.
  - `bazi_engine/transit.py:131` — same pattern as `western.py:64`:
    `backend.calc_ut(jd_ut, pid, extra_flags=swe.FLG_SPEED)`.
  - `bazi_engine/routers/info.py:_check_ephemeris()` (line ~85-93) — construct a
    `SwissEphBackend()` (respecting `SE_EPHE_PATH`/`EPHEMERIS_MODE` like every other
    endpoint, so `/health` is no longer the one site that bypasses the
    construction-time guard) and call `backend.calc_ut(jd, swe.SUN)` instead of the
    bare `swisseph.calc_ut(jd, swe.SUN)`. This is the fix for AC-01-6 / site 4 (§3.1) /
    VCHK-05.
- **Tests to add/run:** `pytest -q` (full suite green — no regressions); update the two
  existing precedent tests whose `patch(...)` target changes shape as a direct
  consequence of this migration:
  `tests/test_ephemeris_fallback.py::TestWesternFallbackDetection::test_western_catches_moseph_fallback`
  and `::TestTransitFallbackDetection::test_transit_catches_moseph_fallback` — their
  `patch("bazi_engine.western.swe.calc_ut", ...)` / `patch("bazi_engine.transit.swe.calc_ut", ...)`
  targets must move to wherever the wrapper's `swe.calc_ut` call now physically resolves
  (`bazi_engine.ephemeris.swe.calc_ut`, if `calc_ut()` stays on `SwissEphBackend` in
  `ephemeris.py`) — do this in the **same PR as T4**, not deferred to T5, since it is a
  mechanical consequence of the call-site move, not new test design.
- **Acceptance evidence:** `grep -rn "swe\.\(calc\|houses\|fixstar\)" bazi_engine/ --include="*.py" | grep -v "ephemeris.py"` returns zero matches; `pytest -q` green; AC-01-2, AC-01-6.

### T5 — `tests/test_ephemeris_attestation.py` (AC-01-4a/4b split) + AST/grep static guard + houses precondition-gate unit test + concurrency test

- **REQ:** FQ-ATT-01
- **Depends on:** the ADR-fixed function signatures (T2/T3, already resolved) for
  test-first authoring; should land in the **same PR as T4** (may be written
  test-first/TDD before T4's implementation, but must not be merged separately/orphaned
  per the PRD's own T5 wording).
- **Files touched:** `tests/test_ephemeris_attestation.py` (new).
- **Sub-tasks:**
  1. **AC-01-4a** (flag-checkable class, mocked-return-flag): construct
     `SwissEphBackend` with `.se1` files present (so construction-time guard passes),
     mock/force `swe.calc_ut`/`swe.fixstar*`'s return flags to include `SEFLG_MOSEPH`,
     assert the migrated wrapper raises `EphemerisUnavailableError` before any response
     is built. Covers `western.py:64`, `transit.py:131`, and (new, post-T4)
     `routers/info.py`'s `_check_ephemeris()`.
  2. **AC-01-4b** (flag-less/construction-time-guard class, empty-directory): run with
     `SE_EPHE_PATH` pointed at an empty directory; assert every endpoint that reaches
     `SwissEphBackend.__post_init__` raises `EphemerisUnavailableError` (or, for
     `/health`, reports `unavailable`). Explicitly includes `routers/info.py:90`
     post-T4 migration (VCHK-05) and the `western.py:93` houses call transitively (via
     backend construction failing first).
  3. **Houses precondition-gate unit test (ADR-2, new mechanism, not re-proving the
     construction-time guard):** construct a `SwissEphBackend` with files present (so
     construction succeeds), call `backend.houses(...)` **without** first calling
     `backend.calc_ut(...)` on the same instance, assert it raises. This is the test
     that actually exercises ADR-2's new precondition-gate logic (VCHK-03).
  4. **AST/grep static guard:** scans `bazi_engine/` excluding `ephemeris.py`, fails on
     any direct `swe.calc*`/`swe.houses*`/`swe.fixstar*` call. During code-review gate
     (T12), demonstrate it actually catches a violation by temporarily reintroducing
     one direct call and confirming the guard fails, then removing it (VCHK-04) — do
     not leave this reintroduced violation committed.
  5. **Concurrency test (NFR-ATT-4 / VCHK-07):** spin up N concurrent threads
     (`concurrent.futures.ThreadPoolExecutor`, mirroring FastAPI's threadpool execution
     model per PRD §3.7) calling `backend.calc_ut()`/`backend.houses()` against the
     same process-global `pyswisseph` state — some forced-MOSEPH, some legitimate SWIEPH
     — assert no false-negative pass-through and no false-positive 503 storm.
- **Acceptance evidence:** `pytest tests/test_ephemeris_attestation.py -q` green;
  AC-01-2 through AC-01-6; VCHK-01a, VCHK-01b, VCHK-03, VCHK-04 (demonstrated once at
  review, see T12), VCHK-05, VCHK-07.

### T6 — Env-toggle for enforcement (default hard-on) + staged-rollout runbook

- **REQ:** FQ-ATT-01
- **Depends on:** T4 (needs the wrapper functions to gate)
- **Files touched:** `bazi_engine/ephemeris.py` (toggle logic — e.g. an env var such as
  `FUFIRE_MOSEPH_ATTESTATION_ENFORCE`, default unset/`true` = hard-fail, explicit
  `false` = degrade-with-log rather than raise, for staging rollback use only);
  `docs/runbooks/fq-att-01-rollout.md` (new — staged rollout: staging environment
  toggled on first, monitor for unexpected `EphemerisUnavailableError` volume, then
  default hard-on in production; rollback = flip the toggle per-environment, not a code
  revert, per PRD §12).
- **Tests to add/run:** unit test — toggle unset/default → hard fail on forced MOSEPH;
  toggle explicitly disabled → degraded-but-logged, no raise (document this is a
  staging-only escape hatch, not a production-recommended state).
- **Acceptance evidence:** NFR-ATT-1.

### T7 — Pin `tzdata` dependency

- **REQ:** FQ-ATT-02
- **Depends on:** nothing (independent track start; can run in parallel with T1–T6)
- **Files touched:** `pyproject.toml` (add `tzdata` to `dependencies`),
  `requirements.lock`, `uv.lock` (regenerate/relock).
- **OQ-6 decision (exact version):** pin to the latest stable `tzdata` release available
  at implementation time; record the chosen version + upgrade policy (e.g. "bump on new
  IANA release, re-lock, no code change needed") directly in this task's PR description
  — a full separate ADR file is not warranted for a single version-pin choice, per the
  PRD's own framing of OQ-6 as "reversible, does not need a user round-trip."
- **Tests to add/run:** `uv sync` / install succeeds cleanly;
  `importlib.metadata.version("tzdata")` resolves to the pinned version in a fresh env.
- **Acceptance evidence:** AC-02-1 (partial — pin exists; T8 makes the detector use it).

### T8 — Fix `_detect_tzdb_version()`; resolve OQ-7

- **REQ:** FQ-ATT-02
- **Depends on:** T7 (tzdata must be pinned first)
- **Files touched:** `bazi_engine/provenance.py` (`_detect_tzdb_version()`,
  currently lines ~83-102).
- **OQ-7 decision:** **raise** (`EphemerisUnavailableError` or a dedicated
  provenance-detection error) instead of silently returning `"unknown"` if detection
  still fails after `tzdata` is pinned — consistent with this repo's "fail visibly, no
  masking" principle (`CLAUDE.md`). Flag explicitly at the T12 code-review gate per the
  PRD's own OQ-7 recommendation (this is a failure-mode semantics change: previously
  degraded-200, now 5xx on an edge case that should not occur once `tzdata` is
  correctly pinned and locked).
- **Tests to add/run:** unit test — with `tzdata` pinned and present, always returns a
  real IANA version string, never `"unknown"`; a forced-failure test (mock
  `importlib.metadata.version` to raise) confirms the new raise behavior instead of a
  silent fallback string.
- **Acceptance evidence:** AC-02-1 (complete).

### T9 — Add missing attestation fields; resolve OQ-1 scope; fix dead-code branch

- **REQ:** FQ-ATT-02
- **Depends on:** T1 (endpoint matrix — already spot-checked in this plan's
  Preconditions, but Phase 2 confirms no drift). Independent of T7/T8 at the code
  level (different files) but should land in the same PR/review pass as T10 since T10
  asserts on these fields. Must complete before T11 (OpenAPI regen depends on these
  field additions being final).
- **Files touched:**
  - `bazi_engine/routers/shared.py` — add a new, slimmer model (e.g.
    `MinimalQualityFlags`: `ephemeris_mode: Literal["SWIEPH","MOSEPH"]`, optionally
    `chart_type_quality`) for non-house endpoints, per this plan's Preconditions design
    note. Do **not** make `QualityFlags.house_system_fallback` `Optional` — that would
    blur the absent-vs-null distinction OQ-1 depends on.
  - `bazi_engine/routers/bazi.py` — add `MinimalQualityFlags`-equivalent field(s) +
    `provenance` completeness to `BaziResponse`.
  - `bazi_engine/routers/fusion.py` — same for `WxResponse`, `TSTResponse`.
  - `bazi_engine/routers/experience.py` — fix `_quality_flags_for_daily()`'s
    (line ~681-695) dead-code `None`-branch (§3.6): either make it unreachable by
    construction (remove the branch, since `DailyRequest` has no fields that could ever
    make `profile_data is None` reachable via the public endpoint) or, if kept for
    defensive purposes, make it raise a clear internal error rather than constructing
    `QualityFlags(**{...None...})` against non-`Optional` fields (which would currently
    raise an opaque Pydantic `ValidationError`).
  - `bazi_engine/routers/chart.py` — **confirmed gap, orchestrator spot-check
    post-planning (2026-07-01):** `ChartResponse` has zero `quality_flags`/`provenance`
    fields, same gap class as `BaziResponse`/`WxResponse`/`TSTResponse`. `chart` was in
    the PRD's §3.5 "not yet audited" bucket, not a contradiction of the PRD — this is
    T1's promised follow-up discovery confirming a real gap in that bucket. In scope for
    T9 (canvas's `bazi_engine/routers/**` pattern already covers this file).
  - `bazi_engine/routers/transit.py` — **same confirmed gap:** `TransitNowResponse`,
    `TransitStateResponse`, `TimelineDayResponse`, `TimelineResponse`, `NarrativeResponse`
    all have zero `quality_flags`/`provenance` fields, despite `transit.py:131` being one
    of FQ-ATT-01's own confirmed guarded call sites (i.e. this endpoint computes real
    ephemeris data with zero attestation exposed today). Decide during T9 implementation
    which of the 5 response models need the fields (at minimum `TransitNowResponse`,
    since it's the one backed by the live `calc_ut` call; the others may be
    derived/cached and need their own check) — do not assume all 5 need identical
    treatment without checking each one's data flow.
  - `bazi_engine/bafe/service.py` — **only** if T1's Phase-2 re-run of the endpoint
    matrix surfaces a concrete wiring need (per OQ-2's default: out of scope for the
    "never unknown" bar itself, but the canvas allows edits here if T1 finds a reason).
- **Tests to add/run:** contract-shape tests (new fields present with correct types) —
  can be folded into T10's contract test rather than a separate test file; a direct
  regression test asserting `_quality_flags_for_daily()`'s dead-code branch either
  cannot be reached with `None`s anymore or raises cleanly (not a Pydantic
  `ValidationError` surfacing as an unhandled 500).
- **Acceptance evidence:** AC-02-3, AC-02-4.

### T10 — Per-endpoint attestation contract test

- **REQ:** FQ-ATT-02
- **Depends on:** T8 (real tzdb value), T9 (fields must exist)
- **Files touched:** `tests/test_attestation_contract.py` (new).
- **Action:** `pytest -k attestation_contract`, parametrized over the full T1 endpoint
  inventory (confirmed: `western`, `fusion`, `wuxing`, `tst`, `bazi`, `daily`, `chart`,
  `transit/now` — the last two per the orchestrator's post-planning spot-check above —
  plus whatever else T1's Phase-2 re-run surfaces) asserting: `provenance.ephemeris_id` and
  `provenance.tzdb_version_id` present and not `"unknown"`/empty; `ephemeris_mode ==
  "SWIEPH"` under test config; `house_system_fallback` present+boolean on
  house-computing endpoints, **absent** on `bazi`/`wuxing`/`tst` (OQ-1).
- **Tests to add/run:** this task is the test.
- **Acceptance evidence:** AC-02-2, AC-02-5; VCHK-02, VCHK-06 (partial — VCHK-06 also
  needs T11's regenerated spec file itself inspected, not just this test passing).

### T11 — OpenAPI regen + drift check

- **REQ:** FQ-ATT-02
- **Depends on:** **T9's field additions being final** — do not run this before T9
  lands, or the regenerated spec will need a second pass.
- **Files touched:** `spec/openapi/openapi.json` (regenerated via
  `python scripts/export_openapi.py`, never hand-edited).
- **Note on OQ-8:** this plan does **not** narrow `ephemeris_mode`'s
  `Literal["SWIEPH","MOSEPH"]` type in this increment (see Preconditions) — no schema
  type change beyond the new fields T9 adds.
- **Tests to add/run:** `python scripts/export_openapi.py --check`.
- **Acceptance evidence:** AC-02-6; VCHK-06 (inspect the committed diff directly —
  attestation fields present on `BaziResponse`/`WxResponse`/`TSTResponse`,
  `house_system_fallback` present only on house-computing endpoints).

### T12 — Full review/validation gates

- **REQ:** FQ-ATT-01, FQ-ATT-02
- **Depends on:** T1–T11, all complete (true convergence point — sequential, last task)
- **Roster (per council sharpen #5 — full roster, no downgrade):** code-reviewer,
  security-reviewer, spec-auditor + plumbline-watcher (against this PRD + canvas),
  product-owner (Gate D).
- **Specific checks this gate must perform (not delegate to earlier tasks):**
  - VCHK-04's self-test (deliberately reintroduce a direct `swe.*` call, confirm the
    AST/grep guard fails the build, then remove it) — demonstrated live at this gate,
    not left as a permanently-committed broken state.
  - Security-reviewer: resolve §10's info-disclosure note —
    `EphemerisUnavailableError`'s `resolved_path` (a server-local filesystem path)
    currently serializes verbatim into the client-facing 503 body via
    `ensure_ephemeris_files()` (`ephemeris.py:179-183`) and `app.py`'s exception
    handler. Centralizing MOSEPH detection (T4) makes this reachable from more call
    sites (including now `/health` and `houses()`'s new precondition-gate failure).
    Decide explicitly: redact `resolved_path` from the client response (log-only) or
    accept as-is — do not leave unreviewed.
  - Product-owner Gate D: walk all of VCHK-01a/01b, 02–07 against the *real*, wired
    implementation (not unit-level assertions in isolation) — per the Vision's own
    "Risks if Misbuilt" framing.
- **Acceptance evidence:** all of AC-01-1…6, AC-02-1…6 confirmed end-to-end; all VCHKs
  confirmed; `docs/traceability.md` updated (`wired-in-prod?` flips from `no` once
  merged and deployed; `true-line-status` moves from `draft`).

---

## Risks and rollback notes

- **Rollout risk (NFR-ATT-1):** hardening a previously-tolerant path to hard-fail could
  convert an undiscovered live MOSEPH dependency into a fleet of 503s. Mitigation: T6's
  env-toggle + staged rollout (staging first). Rollback = flip the toggle
  per-environment, **not** a code revert (PRD §12) — the centralized wrapper code stays
  in place regardless of toggle state.
- **Monkeypatch-safety concern (PRD §6.1) — resolved, not a residual risk:** verified
  directly against the installed `pyswisseph==2.10.3.2` that module-attribute
  reassignment is safe; this concern does not apply to the chosen Option A design
  anyway (Option A does not monkeypatch anything).
- **Houses-class residual gap (ADR-2):** narrow, accepted, documented — a
  sub-request-duration file-mutation race between an attested `calc_ut()` call and a
  subsequent `houses()` call, immaterial to `houses()`'s own correctness since it never
  reads `.se1` data. Not treated as a blocker; re-evaluate only if the deployment model
  changes (e.g., if `.se1` files ever become runtime-mutable, unlike today's
  build-time-baked, SHA256-verified Docker image).
- **Info-disclosure (§10):** pre-existing, not introduced by this plan, but reachable
  from more call sites after T4 — explicitly assigned to T12's security-reviewer pass,
  not silently fixed or silently left as-is.
- **Two-track parallelism risk:** if T1's Phase-2 re-run surfaces a new call site or
  endpoint not in this plan's baseline, both tracks must pause for re-triage before
  continuing — do not let T4/T9 proceed on stale file lists.
- **Rollback (general):** FQ-ATT-01 and FQ-ATT-02 are isolated, individually revertible
  PRs per track (PRD §12) — a problem discovered in one track's PR does not require
  reverting the other.

## Blocker check

None. All items OQ-1 through OQ-8 are either CONFIRMED (OQ-1) or explicitly
planner/implementation decisions this plan (and its two ADRs) now resolves (OQ-4,
OQ-5) or defers with a stated, reversible default (OQ-6 — version choice recorded in
T7's PR; OQ-7 — raise, per T8; OQ-8 — no narrowing, per Preconditions). OQ-2 and OQ-3
remain genuinely open per the PRD but are explicitly non-blocking (evidence-needed
items, not gaps in this increment's own acceptance bar).
