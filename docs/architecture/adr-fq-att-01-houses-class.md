# ADR: FQ-ATT-01 design for the flag-less `houses*` class

| Field | Value |
|---|---|
| Status | Accepted |
| Date | 2026-07-01 |
| Feature | `fufire-premium-verification-ci` (WS-A increment) |
| REQ | `FQ-ATT-01` |
| Resolves | PRD §6.2 / §9 OQ-5 (planner architecture decision, deferred by council sharpen #2) |
| Decider | planner (Phase 1, `/agileteam`) |

## Context

`swe.houses`, `swe.houses_ex`, `swe.houses_ex2`, `swe.houses_armc`,
`swe.houses_armc_ex2` accept no output-checkable retflag in any variant (PRD §3.3,
verified via `help()` on the installed `pyswisseph==2.10.3.2`: `houses()`/`houses_armc*`
take no flags at all; `houses_ex(2)` accept a flags *input* but still return no retflag).
There is structurally no return-value signal to check, unlike `calc_ut`/`fixstar*`.

The one live call site today is `bazi_engine/western.py:93`:
`c, a = swe.houses(jd_ut, lat, lon, sys_char)`, called inside `compute_western_chart()`,
**after** line 54's `backend = SwissEphBackend(ephe_path=ephe_path)` has already run
`__post_init__` → `ensure_ephemeris_files()` (raises `EphemerisUnavailableError` if any of
the 4 required `.se1` files are missing, *before* any planet or house call in the same
function executes).

## Investigation performed (before deciding)

1. Confirmed via `help(swe.houses)` that Swiss Ephemeris's house-cusp computation is a
   pure spherical-trigonometry calculation from ARMC (right ascension of the midheaven,
   itself a function of Julian day + sidereal time + geographic longitude) and geographic
   latitude — it does **not** consult the `.se1` ephemeris data files at all. This is *why*
   no variant returns a MOSEPH/SWIEPH retflag: there is no ephemeris-mode concept inside
   `houses()` to report. A "houses used MOSEPH" event is not a real failure mode of
   `houses()` itself.
2. Given (1), the actual risk `houses()` poses is not "houses silently degraded to
   MOSEPH" (structurally impossible — it never used any ephemeris mode) but: **the
   endpoint's `house_system_fallback`/`ephemeris_mode` attestation fields describe the
   co-located planet computation in the same response, and a future refactor could call
   `swe.houses()` without ever constructing/attesting a `SwissEphBackend` in the same code
   path** — producing house cusps in a response whose attestation fields either don't
   exist or reflect a stale/unrelated backend state. This is the real, narrow gap.
3. Re-confirmed `western.py`'s current ordering: backend construction (with its
   construction-time `ensure_ephemeris_files()` guard) happens at line 54, strictly before
   the planet loop (lines 62-76) and the houses loop (lines 91-102) in the same function —
   so today's one call site is already, incidentally, protected by construction-time
   ordering. The gap is that this protection is **positional/implicit**, not enforced by
   the houses call itself — nothing stops a future call site from calling
   `swe.houses()` (or the migrated `backend.houses()`) without that ordering guarantee.
4. Docker/deploy model check (`Dockerfile`, `railway.toml`): `.se1` files are baked into
   the image at build time with SHA256 verification (CLAUDE.md); no runtime download or
   mutation path exists in this deployment. This materially narrows (but does not
   eliminate) the "mid-request file deletion/corruption" residual risk named in PRD §6.2
   option 2 — the deployed artifact does not write to that directory at runtime.

## Decision

**Documented combination of construction-time guarantee (existing) + an added
precondition-gate (new), implemented as a `SwissEphBackend.houses()` method in
`ephemeris.py`** that:

1. Refuses to proceed unless `self._attested` is `True` (see point 2 below). As
   implemented, this is gated on `self._attested` alone, **not** a literal
   `self.mode == "SWIEPH"` check — see "Implementation deviation from this ADR's
   original text" below, added 2026-07-01 after the plumbline-watcher's
   per-increment True-Line check flagged the divergence between this document's
   wording and the shipped code.
2. **Precondition-gate**: requires that at least one flag-checked `calc_ut()` call on
   *this same backend instance* has already completed and passed
   `assert_no_moseph_fallback` before `houses()` may be called — tracked via a private
   instance flag (e.g. `self._attested: bool`, set `True` inside
   `SwissEphBackend.calc_ut()` immediately after `assert_no_moseph_fallback` passes). If
   `houses()` is invoked on a backend that has never yet had an attested `calc_ut()` call,
   it raises `EphemerisUnavailableError` (fail closed) rather than silently computing
   cusps — this converts today's *incidental* ordering safety into a *causally enforced*
   one, closing the "future refactor calls houses without ever attesting the backend"
   gap.
3. `western.py:93`'s direct `swe.houses(jd_ut, lat, lon, sys_char)` migrates to
   `backend.houses(jd_ut, lat, lon, sys_char)`, and since `compute_western_chart()`
   already calls `backend`-attested `calc_ut()` for every planet in the loop preceding the
   houses loop, the precondition is naturally satisfied by existing call order — no
   behavior change for the one live call site, only a structural guarantee added.

## Alternatives considered

- **Construction-time guarantee only (PRD option 2)** — rejected as the sole mechanism:
  it protects "no `.se1` files at all" but not "future call site calls `houses()` without
  ever constructing/attesting a backend in the same path," which is exactly the kind of
  silent regression this PRD exists to prevent. Accepting this alone would satisfy AC-01-3
  today but leave a documented-but-real latent gap for future call sites, closer to the
  "silent" outcome §6.2 explicitly disallows.
- **Precondition-gate only, no construction-time check** — rejected: would require
  redundantly re-deriving what `__post_init__` already guarantees, and would weaken the
  existing, already-verified construction-time protection for no benefit.
- **A per-request global "SWIEPH attested" flag (module-level, not per-backend-instance)**
  — considered and rejected: `SwissEphBackend` instances are constructed per-call
  (`western.py:54`, `transit.py:124`), and a module-level flag would leak attestation
  state across concurrent requests/threads (violates the PRD §3.7 concurrency constraint:
  a request that legitimately runs MOSEPH mode, or a request whose backend construction
  fails, must not be able to "borrow" another concurrent request's attestation). Per-
  instance state avoids this entirely since each request constructs its own backend.

## Residual gap (explicitly accepted, not silent, not no-op)

**Accepted residual risk**: a request where (a) `SwissEphBackend.__post_init__` succeeds
(files present at construction time), (b) at least one `calc_ut()` call succeeds and is
attested, and then (c) the underlying `.se1` files are deleted, corrupted, or made
unreadable **within the same synchronous request**, strictly between the attested
`calc_ut()` call and the subsequent `houses()` call. In this narrow window, `houses()`
would proceed (the precondition-gate is satisfied by (b), and `houses()` itself never
reads those files anyway per the investigation above, so file removal at that exact
instant would not even change `houses()`'s output correctness — the attestation gap is
purely about *whether the guard fires*, not about `houses()` producing wrong geometry).

This residual is accepted because:
- It requires a sub-request-duration race on a file system that, in this repo's actual
  deployment model (Docker image with SHA256-verified `.se1` files baked in at build
  time, no runtime write path — `Dockerfile`/`railway.toml`), does not mutate at runtime
  at all.
- `houses()` does not consult the `.se1` files for its own computation (confirmed via
  `help()`), so even in the accepted-residual scenario, house-cusp *correctness* is
  unaffected — only the *attestation guarantee's* theoretical completeness has a
  vanishingly narrow gap, not the calculation itself.
- Closing this fully would require either wrapping the entire request in a single
  cross-call file-system lock (disproportionate engineering cost for a residual this
  narrow, and in tension with the PRD's own thread-safety/performance constraints, §3.7,
  NFR-ATT-5) or re-verifying file presence on every single `houses()` call (redundant with
  the already-attested `calc_ut()` check milliseconds earlier in the same request).

This is documented here per PRD §6.2's explicit requirement that "no-op" and "silent" are
disallowed outcomes — the residual is named, bounded, and justified, not left implicit.

## Implementation deviation from this ADR's original text (added 2026-07-01)

**Finding (plumbline-watcher, per-increment True-Line check):** the shipped
`SwissEphBackend.houses()` (`bazi_engine/ephemeris.py`) gates solely on
`self._attested`. It does **not** additionally check `self.mode == "SWIEPH"`, even
though the Decision section above (point 1, before this amendment) literally said
"Refuses to proceed unless `self.mode == "SWIEPH"`". Confirmed by direct code read;
this is a genuine doc/code divergence, not a misreading.

**Why the shipped behavior (gate on `_attested` alone) is correct, and the ADR's
original text was wrong:** `SwissEphBackend` also supports an explicit
`EPHEMERIS_MODE=MOSEPH` deployment mode (a deliberately-supported, already-tested
configuration — see `docs/runbooks/fq-att-01-rollout.md` and
`test_all_files_present_ok`-adjacent MOSEPH-mode tests in
`tests/test_ephemeris_fallback.py`). In that mode, `__post_init__` sets
`self.mode = "MOSEPH"` and `self.flags = swe.FLG_MOSEPH`; a subsequent `calc_ut()`
call legitimately *requests* MOSEPH, so `assert_no_moseph_fallback` does not raise,
and `self._attested` is correctly set to `True` — the backend genuinely completed
an attested calculation, just not a SWIEPH one. A literal `self.mode == "SWIEPH"`
check in `houses()`, as this ADR's original text specified, would have made
`houses()` unconditionally 503 on every single explicit-MOSEPH-mode request — even
though that mode is legitimate, already supported, and already exercised by tests
elsewhere in the suite. Gating on `_attested` alone is the behavior that actually
satisfies this ADR's own underlying intent (never compute house cusps against an
*unattested* backend instance) without breaking a legitimate, pre-existing
configuration the literal text failed to account for.

**Disposition:** this document's text is corrected here to describe the
implemented, correct behavior; the code is not changed to match the original
(incorrect) text. No behavior change results from this amendment — it is a
documentation correction only.

## Consequences

- `bazi_engine/ephemeris.py`: add `_attested: bool` instance state (or equivalent) to
  `SwissEphBackend` and a new `houses()` method implementing the precondition-gate +
  construction-time check described above.
- `bazi_engine/western.py:93`: migrate `swe.houses(...)` → `backend.houses(...)`.
- **AC-01-3** (missing `.se1` files → `houses*` fails closed) is satisfied by the existing
  construction-time guarantee, unchanged by this ADR.
- **VCHK-03** (vision doc — houses-class guard demonstrated end-to-end, not just
  documented) requires a real HTTP request test against `/calculate/western` (or
  `/calculate/fusion`) under `SE_EPHE_PATH` pointed at an empty directory, confirming
  `EphemerisUnavailableError`/503 — this is satisfied transitively via the construction-
  time guard (backend construction fails before `houses()` is ever reached), and must be
  covered by T5's AC-01-4b empty-directory test class alongside `routers/info.py:90`.
- A new, narrower unit test should also directly exercise the precondition-gate itself:
  construct a `SwissEphBackend` with files present (so construction succeeds), then call
  `backend.houses(...)` **without** first calling `backend.calc_ut(...)`, and assert it
  raises — this is the test that actually proves the new mechanism (as opposed to only
  re-proving the pre-existing construction-time guard). Add this to T5.

## Why this satisfies PRD §6.3's non-negotiable constraints

- **Zero direct calls outside `ephemeris.py`**: `western.py:93`'s only `houses*` call
  moves into `backend.houses()`, so the AST/grep guard (T5) covers it identically to the
  flag-checkable class.
- **Hard-on by default, env-toggleable**: the precondition-gate is unconditional logic (no
  separate toggle needed) layered on top of the existing `EPHEMERIS_MODE`-driven
  construction path — inherits the same default-hard-fail behavior as `__post_init__`.
- **Thread-safe (§3.7)**: `_attested` is instance state on a per-request-constructed
  `SwissEphBackend` (never shared across requests/threads, since each call site
  constructs its own instance) — no new shared mutable state, no new lock needed.
- **No endpoint path/response-structure change**: internal-only change; `western.py`'s
  public return shape is unaffected.
- **OpenAPI drift unaffected**: no Pydantic model touched by this ADR.
