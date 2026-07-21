# ADR: FQ-ATT-01 mechanism for the flag-checkable class (`calc`/`calc_ut`/`fixstar*`)

| Field | Value |
|---|---|
| Status | Accepted |
| Date | 2026-07-01 |
| Feature | `fufire-premium-verification-ci` (WS-A increment) |
| REQ | `FQ-ATT-01` |
| Resolves | PRD §6.1 / §9 OQ-4 (planner architecture decision, deferred by council sharpen #2) |
| Decider | planner (Phase 1, `/agileteam`) |

## Context

PRD §6.1 presents two options for closing the "zero direct `swe.calc*`/`fixstar*` calls
outside `bazi_engine/ephemeris.py`" requirement (FQ-ATT-01, AC-01-2, AC-01-5, §6.3):

- **Option A** — add `ephemeris.calc_checked()` (extends the existing
  `SwissEphBackend.calc_ut()` wrapper pattern already in place at
  `bazi_engine/ephemeris.py:109-120`), migrate the 4 confirmed direct call sites
  (`western.py:64`, `western.py:93` is houses, not this class; `transit.py:131`;
  `routers/info.py:90`) to call it, and add an AST/grep static-guard test.
- **Option B** — monkeypatch `swisseph.calc_ut`/`calc`/`fixstar*` at `ephemeris.py`'s
  module-init time so the wrapped function is the only one reachable process-wide.

The PRD explicitly flags a risk for Option B: "monkeypatching a compiled-extension
module's attribute may not be safe/permanent for all `pyswisseph` build variants — must be
verified against the actually-installed `pyswisseph>=2.10.3` before adoption."

## Investigation performed (before deciding)

1. Read `bazi_engine/ephemeris.py`, `western.py`, `transit.py`, `routers/info.py` directly
   (not from the PRD's summary table). Re-ran `grep -rn "swe\.\(calc\|houses\|fixstar\)"
   bazi_engine/` — confirms the PRD's §3.1 4-site baseline exactly, zero new sites.
2. Verified the actually-installed package in this repo's `.venv`:
   `importlib.metadata.version("pyswisseph") == "2.10.3.2"` (matches
   `pyproject.toml`'s `pyswisseph>=2.10.3` pin and `requirements.lock`'s
   `pyswisseph==2.10.3.2`), backed by
   `.venv/lib/python3.12/site-packages/swisseph.cpython-312-darwin.so`.
3. Directly tested the PRD's named risk on the real installed module:
   ```python
   import swisseph as swe
   orig = swe.calc_ut
   swe.calc_ut = lambda *a, **k: orig(*a, **k)   # succeeds
   ```
   **Result: the monkeypatch assignment succeeds.** `swisseph` is a Python module object
   (even though backed by a compiled `.so` extension); module `__dict__`s are ordinary
   mutable Python dicts, so rebinding an attribute on the module is safe and permanent for
   the remaining lifetime of the process on this build. The PRD's named risk (**"may not be
   safe/permanent"**) is **not realized** on `pyswisseph==2.10.3.2` — this concern alone
   does not rule Option B out.
4. However, three *other* facts surfaced by reading the real call sites make Option B
   materially worse than Option A here, independent of the monkeypatch-safety question:
   - `routers/info.py:90` calls `swe.calc_ut(jd, swe.SUN)` with **no flags argument at
     all** — relying on pyswisseph's own default (`FLG_SWIEPH|FLG_SPEED`, confirmed via
     `help(swe.calc_ut)`). A generic process-wide patch would have to reconstruct/mirror
     that default internally to know what was "requested" — re-implementing pyswisseph's
     own default-flag semantics is fragile across pyswisseph versions. Option A instead
     forces this call site to pass explicit flags through `calc_checked()`, which is
     strictly more correct.
   - `swe.calc_ut`/`swe.calc` return `(xx, retflags)` (2 values) while `swe.fixstar_ut`/
     `swe.fixstar2_ut` return `(xx, stnam, retflags)` (3 values, confirmed via
     `help(swe.fixstar_ut)`) — the two families are not drop-in-swappable at a single
     generic patch point; each needs family-aware unwrapping logic. This is exactly the
     per-call-site-aware logic Option A already centralizes in named wrapper functions,
     just made implicit and harder to trace inside a generic patch under Option B.
   - **AC-01-5's static AST/grep guard is required under both options** (§6.3 is
     mechanism-agnostic on this point). Option B's claimed advantage ("no lint-drift
     risk") does not eliminate the need for this guard: a call site could still bind
     `from swisseph import calc_ut as _c` (a name binding taken at import time, before or
     regardless of the module-attribute patch) and bypass the patch entirely — so the
     codebase still needs the same static guard to catch that binding pattern under
     Option B. Option B therefore adds a global-interception layer **without** removing
     the audit-surface Option A already needs anyway.
5. Existing test precedent (`tests/test_ephemeris_fallback.py::TestWesternFallbackDetection`
   /`TestTransitFallbackDetection`) already patches `bazi_engine.western.swe.calc_ut` /
   `bazi_engine.transit.swe.calc_ut` per-test via `unittest.mock.patch`, which relies on
   exactly the same "module attribute is mutable" fact confirmed in step 3 — this pattern
   ports cleanly to Option A (patch target simply moves to
   `bazi_engine.ephemeris.swe.calc_ut` once call sites migrate) with no new test
   machinery. Under Option B, the *production* patch and the *test* patch would be two
   monkeypatch layers stacked on the same attribute, needing careful save/restore
   ordering (interacts with the PRD's own noted `importlib.reload` re-entrancy concern,
   §6.1 table).

## Decision

**Option A — per-call-site `ephemeris.calc_checked()` wrapper + AST/grep static-guard
test.** Extend the existing, already-correct `SwissEphBackend.calc_ut()` pattern
(`ephemeris.py:109-120`) with a free-function or backend-method wrapper covering
`swe.calc`/`swe.fixstar*` (currently unused, but per PRD §3.3, `fixstar*` belongs in this
same flag-checkable class if a call site is ever added). Migrate the 3 direct
flag-checkable call sites in the PRD §3.1 baseline (`western.py:64`, `transit.py:131`,
`routers/info.py:90`) to call it. Add the AST/grep lint test asserting zero remaining
direct `swe.calc*`/`swe.fixstar*` calls outside `bazi_engine/ephemeris.py`.

Option B is **not** ruled out on the PRD's named "unsafe/non-permanent" concern (that
concern is empirically false on the installed `pyswisseph==2.10.3.2` — monkeypatching
works). It is ruled out because, once the default-flag-reconstruction problem, the
`calc_ut`/`fixstar*` return-shape heterogeneity, and the still-mandatory AC-01-5 static
guard are accounted for, Option B adds a global interception layer that provides no
audit-surface reduction over Option A while introducing a materially larger blast radius
(a bug in the patch affects every caller in the process, including any future third-party
code that imports `swisseph` directly) and worse stack-trace locality for debugging.

## Alternatives considered

- **Option B (import-boundary monkeypatch)** — rejected. Mechanically safe on the
  installed build (verified), but does not reduce required audit surface (AC-01-5 still
  needed), must special-case 2 divergent return shapes and reconstruct pyswisseph's own
  default-flag behavior for the flag-omitted call site, and has full-process blast radius
  for any implementation bug.
- **Hybrid (Option B for calc/calc_ut, Option A wrapper for fixstar\* since no live call
  site exists yet)** — considered and rejected as needless mechanism-splitting for a
  single, already-small (3-site) call-site set; adds two enforcement mechanisms to reason
  about instead of one.

## Consequences

- `bazi_engine/ephemeris.py` gains one or two new wrapper functions/methods
  (`calc_checked()` for the bare `swe.calc`/`swe.calc_ut` case used by `routers/info.py`,
  and reuse/extension of `SwissEphBackend.calc_ut()` for the two backend-instance call
  sites in `western.py`/`transit.py`); `fixstar_checked()` added preventively even though
  no live call site exists today (§3.1), so a future fixstar call site has an obvious,
  already-guarded entry point to use instead of calling `swe.fixstar*` directly.
- `western.py:64`, `transit.py:131`, `routers/info.py:90` each change from a direct
  `swe.calc_ut(...)` + inline `assert_no_moseph_fallback(...)` call to a single call into
  `ephemeris.py`'s wrapper. `routers/info.py:90` additionally needs to construct (or reuse)
  a `SwissEphBackend` instance rather than calling the bare global `swisseph.calc_ut`, to
  route through the same construction-time guard as every other endpoint (this closes the
  one genuinely-unguarded site named in PRD §3.1 site 4 / AC-01-6).
- The AST/grep static-guard test (`tests/test_ephemeris_attestation.py` or a dedicated
  lint test module, T5) must scan `bazi_engine/` excluding `ephemeris.py` and fail on any
  direct `swe.calc*`/`swe.houses*`/`swe.fixstar*` call — this test is required regardless
  of this ADR's choice (§6.3) and is unaffected by it.
- Existing test precedent in `tests/test_ephemeris_fallback.py` needs its `patch(...)`
  targets updated to point at `bazi_engine.ephemeris.swe.calc_ut` (or the new wrapper) once
  T4 migrates the call sites — this is explicitly called out as in-scope for T4/T5 in the
  PRD's own task list, not a new discovery.
- No change to `bazi_engine/bazi.py` (its only `swe.*` call, `swe.julday`, is a pure
  calendar conversion, confirmed not in this class, §3.1).

## Why this satisfies PRD §6.3's non-negotiable constraints

- **Zero direct calls outside `ephemeris.py`, mechanically verified**: satisfied via the
  AST/grep test (T5), which Option A needs and gets no worse at than Option B would.
- **Hard-on by default, env-toggleable**: unaffected by this choice — the toggle sits in
  `SwissEphBackend`/`calc_checked()`'s use of `EPHEMERIS_MODE`, identical under either
  option (T6).
- **Thread-safe under FastAPI's shared threadpool (§3.7)**: each wrapper call remains a
  stateless function call (request→flags→assert, no shared mutable state beyond the
  already-existing process-global `pyswisseph` C state) — safe under concurrent threads,
  identical to today's inline `assert_no_moseph_fallback` pattern already proven correct
  in production. No new locking is introduced or required by this ADR.
- **No endpoint path/response-structure change**: this is an internal implementation
  change only; response bodies are unaffected by this ADR (FQ-ATT-02/T9 handles response
  fields separately).
- **OpenAPI drift stays green**: this ADR touches no Pydantic response models, so
  `scripts/export_openapi.py --check` is unaffected by T2/T4's changes on their own.
