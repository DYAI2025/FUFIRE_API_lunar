# PRD — FuFirE Attestation End-to-End (WS-A increment)

| Field | Value |
|---|---|
| Feature slug | `fufire-premium-verification-ci` (increment 1 of N — **WS-A only**) |
| Status | user-confirmed (2026-07-01; AC-02-2/AC-02-3/§5.2 amended + re-confirmed 2026-07-08 — tst `quality_flags` exemption synced to the recorded user decision, contradictions Finding 5) |
| Canvas link | `docs/canvas/fufire-premium-verification-ci.canvas.md` (**user-confirmed**, 2026-07-01) |
| Source backlog | `docs/2026-07-01-fufire-premium-verification-and-ci.md` § "WS-A — Attestierung end-to-end (G3)" (FQ-A1, FQ-A2) |
| Council verdict | `docs/archive/2026-07-01-fufire-premium-verification-ci.md` — SHARPEN, user said "proceed" |
| Traceability matrix | `docs/traceability.md` |
| Vision link | `docs/vision/fufire-premium-verification-ci.vision.md` (**user-confirmed**, 2026-07-01) |
| REQ-IDs (fixed, reused, not invented) | `FQ-ATT-01`, `FQ-ATT-02` |

Status: user-confirmed

---

## 0. Binding scope framing (do not re-litigate — settled by canvas + council)

1. **This is a baseline correctness/reliability guarantee for ALL paying customers, not a premium-tier differentiator.** "Premium" language is reserved for the deferred WS-C/FQ-030 accuracy-threshold work. (Council sharpen #1.)
2. **Scope = WS-A only**: `FQ-ATT-01` (no silent MOSEPH fallback, all calc paths) and `FQ-ATT-02` (attestation fields guaranteed non-`"unknown"`, `tzdb_version_id` pinned). WS-B (JPL/Jié oracle), WS-C (historical TZ accuracy), FQ-030 (threshold ratification), WS-D (CI gate expansion), WS-E (scheduled Claude audit), WS-F (prod observability) are **out of scope** — deferred to follow-on canvases per `docs/canvas/fufire-premium-verification-ci.canvas.md` § Non-goals.
3. **Target user is broad**: any paying FuFirE API customer/integrator, not only the Bazodiac/`New_Bazi` BFF that originally surfaced the need (canvas §2).
4. **Deploy target is Railway**, not Cloud Run (this repo's `CLAUDE.md`; corrects the source doc). Not this increment's concern — no release-gate work here (that is WS-D, deferred).
5. **The architecture section below presents two mechanism options for the planner to choose between — it does not pre-decide.** (Council sharpen #2.)
6. **Do not assert that any downstream consumer (Bazodiac/ElevenLabs or otherwise) currently reads `quality_flags`.** Kept as an explicit evidence-needed / open item throughout this PRD, never a stated premise. (Council sharpen #4.)

---

## 1. Problem & value (pointer, not restated)

Full problem statement, value proposition, success signal, and non-goals live in the
confirmed canvas — see `docs/canvas/fufire-premium-verification-ci.canvas.md` §§ 1, 4, 5, 7.
One-line restatement: paying API customers have no hard, structural, continuously-enforced
guarantee that a calculation response was computed with Swiss Ephemeris (not the Moshier/
MOSEPH analytical fallback), and the attestation fields meant to prove this
(`ephemeris_mode`, `ephemeris_id`, `tzdb_version_id`, `house_system_fallback`) are
sometimes `"unknown"` or absent.

---

## 2. Actors

| Actor | Role in this increment |
|---|---|
| Paying API customer/integrator | Consumer of `/v1/*` calculation endpoints; the party this guarantee protects. Broad — not BFF-specific. |
| FuFirE engine (`bazi_engine/`) | System under change. |
| CI pipeline (`.github/workflows/ci.yml`) | Must stay green; new attestation tests run inside the existing matrix — no new workflow file required for WS-A (PR-gate wiring for these tests as a *required* branch-protection check is WS-D, deferred; this increment only needs the tests to exist and pass locally/in CI's existing job). |
| Downstream BFF(s) (Bazodiac/`New_Bazi`, and unknown others) | **Evidence-needed, not asserted**: unconfirmed whether any consumer reads `quality_flags` today. Do not build or justify this increment on an assumed consumer behavior. |

---

## 3. Verified evidence (discovery findings — grounded, not speculative)

Per the gap rule, every claim below was checked against the real artifact (source file,
line number, or the installed `pyswisseph` package's own docstrings via `help()`) before
being used as a PRD premise. Classification: **belegt** (directly verified) / **ableitbar**
(inferable from verified facts) / **ungeprüft** (unverified — flagged, not used as premise).

### 3.1 The four call sites (re-confirms the canvas/council grep, exact line numbers)

| # | Site | Call | Guard today | Class |
|---|---|---|---|---|
| 1 | `bazi_engine/western.py:64` | `swe.calc_ut(jd_ut, pid, flags)` | **Guarded inline** — `assert_no_moseph_fallback(flags, ret)` called directly at line 65 | belegt |
| 2 | `bazi_engine/western.py:93` | `swe.houses(jd_ut, lat, lon, sys_char)` | **Unguarded — cannot be guarded via return flags** (see 3.3) | belegt |
| 3 | `bazi_engine/transit.py:131` | `swe.calc_ut(jd_ut, pid, flags)` | **Guarded inline** — `assert_no_moseph_fallback(flags, ret)` at line 132 | belegt |
| 4 | `bazi_engine/routers/info.py:90` | `swe.calc_ut(jd, swe.SUN)` | **Genuinely unguarded** — no flags argument, no backend, no assertion. This is the `/health` dependency check (`_check_ephemeris()`). | belegt |

**Correction to the source doc's risk framing:** sites 1 and 3 are not silently unguarded
today — they duplicate the flag-assertion inline rather than going through the centralized
`ephemeris.py` wrapper. The real risk from duplication is DRY/drift (a future call site
copy-pasted from this pattern could omit the assert and reopen the gap silently, and no
mechanical AST-lint guard can today prove "zero direct calls outside `ephemeris.py`" because
these direct calls exist even though currently correct). **Site 4 (`routers/info.py:90`,
the `/health` check) is the one site with no guard of any kind** — notable because this is
exactly the endpoint meant to be the safety signal (G6 territory), even though full
runtime-attestation observability (WS-F) is out of scope here.

`bazi_engine/bazi.py` imports `swisseph` but its only direct `swe.*` call is
`swe.julday(year, 1, 1, 0.0)` (line 156) — a pure calendar/date conversion, not a
calc/houses/fixstar call, so it carries no MOSEPH risk. Confirmed by direct read — **belegt**,
not assumed. Re-verify at implementation time regardless (see Task T1); this file's status
can change as the engine evolves.

No `swe.fixstar*` call sites exist anywhere in `bazi_engine/` today (repo-wide grep,
zero matches) — the fixstar guard discussed below is preventive, not a fix for a live gap.

### 3.2 `assert_no_moseph_fallback` and `SwissEphBackend` (existing foundation — belegt)

- `bazi_engine/ephemeris.py:27-51` — `assert_no_moseph_fallback(requested_flags, returned_flags)` raises `EphemerisUnavailableError` if `SEFLG_MOSEPH` is set on the return but not the request.
- `bazi_engine/ephemeris.py:63-101` (`SwissEphBackend.__post_init__`) — in `SWIEPH` mode, calls `ensure_ephemeris_files()` (line 166-184) which **already raises `EphemerisUnavailableError` at backend-construction time** if any of the 4 required `.se1` files are missing — before any `calc_ut`/`houses` call happens. This is a real, pre-existing safety net that narrows (but does not close) the gap: it protects any code path that constructs a `SwissEphBackend`, but **not** `routers/info.py:90`, which calls the bare global `swisseph` module directly without constructing a backend at all.
- `bazi_engine/ephemeris.py:109-120` (`SwissEphBackend.calc_ut()`) is the existing centralizable wrapper FQ-A1 must extend/reuse — confirmed present, confirmed it already does the flag-assertion correctly for the one call site that uses it (`sun_lon_deg_ut`, line 98).

### 3.3 Corrected two-class split for `swe.houses*` vs. `swe.fixstar*` (verified against the installed `pyswisseph` package — foreign-API claim, checked before use)

The source doc groups `swe.houses*` and `swe.fixstar*` together as "no comparable
flags." **This is only half true.** Verified via `help()` on the actually-installed
`swisseph` module (not assumed from documentation or training data):

| Function family | Accepts `flags` input? | Returns `retflags`? | MOSEPH-detectable via return value? |
|---|---|---|---|
| `swe.calc`, `swe.calc_ut` | yes | yes | **yes** (existing pattern) |
| `swe.fixstar`, `swe.fixstar_ut`, `swe.fixstar2`, `swe.fixstar2_ut` | **yes** (`flags=FLG_SWIEPH` default) | **yes** (`retflags` as 3rd return value) | **yes — same shape as `calc_ut`, contrary to the source doc's grouping** |
| `swe.houses`, `swe.houses_ex`, `swe.houses_ex2`, `swe.houses_armc`, `swe.houses_armc_ex2` | `houses` no; `houses_ex(2)` yes (input only); `houses_armc*` no | **no — none of the 5 variants return any flag** | **no — genuinely undetectable via return value in any variant** |

**Correction adopted into this PRD (disproven claim, not carried forward as a premise):**
`swe.fixstar*` calls belong in the **same flag-checkable class as `swe.calc`/`swe.calc_ut`**,
not the houses no-op class. If/when a fixstar call site is ever added, it must use the
identical `assert_no_moseph_fallback`-style wrapper as body calls — this changes the AST-lint
guard design (see §6) from "two exempt classes" to "one flag-checkable class (calc + fixstar)
and one genuinely-flagless class (houses only)."

### 3.4 `tzdb_version_id` "unknown" root cause (belegt)

- `tzdata` is **not declared as a dependency anywhere**: absent from `pyproject.toml`
  `dependencies`, absent from `requirements.lock`, absent from `uv.lock` (grepped all three,
  zero matches).
- `bazi_engine/provenance.py:83-102` (`_detect_tzdb_version()`) tries
  `importlib.metadata.version("tzdata")`, then falls back to reading the `tzdata` package's
  `zoneinfo/tzdata.zi` file, then **returns the literal string `"unknown"`** if both fail.
  This is the exact, concrete mechanism behind G3's "`tzdb_version_id` sometimes exposed as
  `unknown`" — confirmed, not inferred.

### 3.5 Endpoint × attestation-field coverage gap (belegt — corrects a premise in both the source doc and the canvas's risk section)

Direct read of every response model that imports `QualityFlags`/`ProvenanceResponse`
(`bazi_engine/routers/shared.py`):

| Endpoint | Response model | `provenance` | `quality_flags` |
|---|---|---|---|
| `POST /calculate/western` | `WesternResponse` | yes | **yes** |
| `POST /calculate/fusion` | `FusionResponse` | yes | **yes** |
| `POST /experience/daily` | `DailyResponse` | (via profile) | **yes** (`QualityFlags`, built by `_quality_flags_for_daily()`) |
| `POST /calculate/bazi` | `BaziResponse` | yes | **no field at all** |
| `POST /calculate/wuxing` | `WxResponse` | yes | **no field at all** |
| `POST /calculate/tst` | `TSTResponse` | yes | **no field at all** |
| `POST /transit/*`, `POST /impact/active`, `POST /api/chart`, `POST /bazi/dayun`, `POST /experience/bootstrap`, `POST /experience/signature-delta`, `POST /chronometry/resolve` | — | **not yet audited** | **not yet audited** |

**This corrects the source doc's "`Optional`→`required`" framing** (FQ-A2's description
assumes the field already exists everywhere, just loosely typed). For `BaziResponse`,
`WxResponse`, `TSTResponse` this is not a type-tightening — it is a **new field addition**
to a response body on an endpoint whose path/structure is otherwise frozen per this repo's
`CLAUDE.md` ("Endpoints are frozen — do not change paths or response structures"). Additive,
backward-compatible field additions are the correct, permitted way to close this without
violating that rule, but the scope is materially larger than "flip Optional to required" —
it also includes wiring a currently-absent field into three response models plus whatever
the remaining unaudited endpoints turn up. **The full endpoint × field matrix is not
exhaustively enumerated here — completing it is FQ-ATT-02's own first discovery task (T1),
not assumed complete by this PRD.**

Separately verified: the **OpenAPI schema for the fields that DO exist already marks them
`required`**, not `Optional` (`spec/openapi/openapi.json` → `QualityFlags.required` = all
four non-`chart_type_quality` fields; `ProvenanceResponse.required` = all eight fields).
The source doc's "Optional→required" schema-tightening premise is **already satisfied**
for `QualityFlags`/`ProvenanceResponse` as declared types — the remaining gap is
value-level (a required `str` field can still literally equal `"unknown"`) and
coverage-level (see table above), not type-level.

**`/validate` (BAFE contract-validation router) is a different, deliberately-nullable
contract, not an instance of the same gap.** `bafe/service.py:167,173` builds
`"ephemeris_id": engine_config["refdata"].get("ephemeris_id", None)` as a raw dict value —
not validated by `ProvenanceResponse`/`QualityFlags` at all. Confirmed by direct read of
`spec/schemas/ValidateResponse.schema.json`: its `ephemeris_id` field is explicitly typed
`["string", "null"]` — `null` is a **contractually valid** value there (legitimate when the
request runs in `positions_override_only=true` mode and never invokes a live ephemeris),
unlike `ProvenanceResponse.ephemeris_id: str`, which is non-nullable. `/validate` validates
a hypothetical request/config; it does not perform a live astronomical computation. The
canvas's "Allowed change scope" section does list `bazi_engine/bafe/service.py` as an
editable file for this increment, so it is not excluded from the file set — but whether
`/validate` must satisfy FQ-ATT-02's "never `unknown`, present on every calculation
response" acceptance bar is still an open scope question (§9, OQ-2), since it is
architecturally a schema/config validator, not a computation endpoint.

### 3.6 Dead-code landmine (belegt — found during discovery, not previously documented anywhere)

`bazi_engine/routers/experience.py:681-695` (`_quality_flags_for_daily()`) constructs
`QualityFlags(**{"house_system_fallback": None, "house_system_requested": None,
"house_system_used": None, "ephemeris_mode": None})` when `profile_data is None`.
Traced the call chain: `profile_data` can only be `None` if `_daily_profile_missing()`
(line 633) returns `False`, which requires `body.day_master`/`sun_sign_idx`/etc. to be
non-`None` — but `DailyRequest` (line 232) **has no such fields declared**, so
`getattr(body, "day_master", None)` is always `None` and this branch is **currently
unreachable via the public `/experience/daily` HTTP endpoint**. Not a live bug today, but
a landmine: `QualityFlags`'s fields are typed non-`Optional`, so if this branch ever became
reachable (e.g. a future internal caller wiring precomputed signals) it would raise a
Pydantic `ValidationError` (crash) rather than silently emit `"unknown"`. Recommend
removing or hard-fixing this branch as part of FQ-ATT-02 hardening (Task T9).

### 3.7 Concurrency constraint (belegt)

`railway.toml` / `Dockerfile` start a single `uvicorn` process (`python start.py`), no
`--workers` override visible in either file. All calculation path-operation functions in
scope here are `def`, not `async def`, so FastAPI runs them in a shared thread pool —
**concurrent HTTP requests can and do call `swe.set_ephe_path()` / `swe.calc_ut()` /
`swe.houses()` concurrently against the same process-global `pyswisseph` C-library state.**
`western.py`'s `_SWE_LOCK` (line 12) only guards the sidereal `set_sid_mode()` /
`get_ayanamsa_ut()` / reset sequence (lines 147-150) — it does **not** wrap the
`calc_ut`/`houses` calls. This is a genuine architecture constraint for whichever FQ-ATT-01
mechanism is chosen (§6): the guard must be safe under concurrent threads in a single
process, and an import-boundary monkeypatch must be installed once (module import time),
not per-request.

### 3.8 Pre-existing info-disclosure note (belegt, not introduced by this PRD but newly reachable more often)

`ensure_ephemeris_files()` raises `EphemerisUnavailableError` with
`detail={"missing_files": [...], "resolved_path": str(path)}` (`ephemeris.py:179-183`).
`bazi_engine/app.py`'s `EphemerisUnavailableError` handler serializes `exc.to_dict()["detail"]`
verbatim into the client-facing JSON 503 body — meaning a server-local filesystem path is
returned to the API caller on this specific failure mode. Pre-existing, not created by
this PRD, but centralizing/hardening MOSEPH detection across more call sites makes
`EphemerisUnavailableError` reachable from more triggers — carried into the security
matrix (§8) as a note, not a blocker.

---

## 4. Requirements

### FQ-ATT-01 — Paid response can structurally never originate from unrequested MOSEPH (hard, all calc paths)

**Statement:** No calculation performed by `bazi_engine` may silently use the Moshier
(MOSEPH) analytical ephemeris fallback when SWIEPH (Swiss Ephemeris `.se1` data) was
requested. Every `swe.calc`/`swe.calc_ut`/`swe.fixstar*` call must be flag-checked (either
via a per-call-site wrapper or a single import-boundary interception — see §6, planner
chooses). Every `swe.houses*` call must go through a separately designed guard, since no
variant of `swe.houses*` exposes a return flag to check (§3.3). Zero direct calls to any of
these functions may exist outside `bazi_engine/ephemeris.py` once implemented.

### FQ-ATT-02 — Attestation fields guaranteed non-`"unknown"` in every calculation response, `tzdb_version_id` pinned

**Statement:** Every calculation endpoint response (full inventory: Task T1) exposes
`quality_flags.ephemeris_mode`, `provenance.ephemeris_id`, `provenance.tzdb_version_id`,
and — where the endpoint computes house cusps — `quality_flags.house_system_fallback`.
None of these may ever be the literal string `"unknown"`, `null`/`None`, or absent when the
endpoint's computation depends on them. `tzdb_version_id` must derive from a pinned,
declared `tzdata` dependency, not a best-effort runtime probe with a silent fallback string.

---

## 5. Data model

### 5.1 Current state (verified, §3.5)

```jsonc
// QualityFlags (bazi_engine/routers/shared.py:80-98) — already required-typed
{
  "house_system_fallback": true,           // bool, required
  "house_system_requested": "placidus",    // str, required
  "house_system_used": "whole_sign",       // str, required
  "ephemeris_mode": "SWIEPH",              // Literal["SWIEPH","MOSEPH"], required
  "chart_type_quality": "exact"            // Optional — untouched by this REQ
}

// ProvenanceResponse (shared.py:63-72) — already required-typed
{
  "engine_version": "...", "parameter_set_id": "...", "ruleset_id": "...",
  "ephemeris_id": "swieph_sepl18",         // str, required — but VALUE can be stale/wrong today
  "tzdb_version_id": "unknown",            // str, required — VALUE is the actual gap (§3.4)
  "house_system": "...", "zodiac_mode": "...", "computation_timestamp": "..."
}
```

### 5.2 Target state (this PRD's Definition of Done for the data model)

- `tzdb_version_id` is always a real IANA tzdata version string (e.g. a `YYYY[letter]`
  release tag) sourced from a pinned dependency — never `"unknown"`.
- `ephemeris_mode` is always `"SWIEPH"` on a successful (2xx) response — a `"MOSEPH"` value
  can never appear on a successful response once FQ-ATT-01 lands, because the request
  would instead raise `EphemerisUnavailableError` (503) before a response body is built.
  **(OPEN QUESTION — see §9: should the `Literal["SWIEPH","MOSEPH"]` type on `ephemeris_mode`
  be narrowed to `Literal["SWIEPH"]` once MOSEPH can no longer reach a 2xx response? Left
  for planner/architect ADR — reversible, does not change the guarantee either way.)**
- `quality_flags` and `provenance.ephemeris_id` are present (additively, not replacing
  frozen response structure) on every endpoint in the T1 inventory that performs an
  ephemeris-dependent calculation — including `BaziResponse` and `WxResponse` (previously
  missing them entirely). **Amended 2026-07-08 (user decision 2026-07-01, recorded as
  contradictions Finding 5):** `/calculate/tst` (`TSTResponse`) is exempt from
  `quality_flags` — its compute path (`time_context.py` → `equation_of_time`) performs
  zero Swiss-Ephemeris work, so attesting an `ephemeris_mode` there would itself be a
  fake-attested value. `TSTResponse` carries `provenance` only; the no-swe-calc invariant
  is regression-guarded by `tests/test_attestation_contract.py`
  (`TestAttestationContractTstNoSwissEph`).
- `house_system_fallback` semantics: **CONFIRMED by user (2026-07-01, OQ-1).** The field
  is scoped to house-computing endpoints only (`western`, `fusion`, `chart`,
  `experience/*`). Endpoints that do not compute houses at all (`/calculate/bazi`,
  `/calculate/wuxing`, `/calculate/tst`) do not carry `house_system_fallback` — they only
  need `ephemeris_mode`/`ephemeris_id`/`tzdb_version_id`.

---

## 6. Architecture constraints (planner chooses — not pre-decided)

### 6.1 Mechanism for the flag-checkable class (`calc`, `calc_ut`, `fixstar*`)

Present **two options**, per council sharpen #2. Both satisfy FQ-ATT-01's "zero direct
calls outside `ephemeris.py`" acceptance bar; they differ in enforcement mechanism and
blast radius.

| | **Option A — per-call-site wrapper + static lint** (source doc's original design) | **Option B — import-boundary interception** (council-raised alternative) |
|---|---|---|
| Mechanism | Add `ephemeris.calc_checked()` (wraps `assert_no_moseph_fallback`); migrate every direct `swe.calc*`/`swe.fixstar*` call site to call it instead; add an AST/grep lint test asserting zero remaining direct calls outside `ephemeris.py`. | Inside `ephemeris.py`'s module init, replace `swisseph.calc_ut`/`calc`/`fixstar*` with wrapped versions (monkeypatch at the `pyswisseph` import boundary) so the checked function is the only one that exists in the process — no call-site discipline needed. |
| Enforcement point | N call sites + 1 static check (fragile if lint regexes drift; must keep pace with new files) | 1 control point (the module init) |
| Blast radius if wrong | Isolated to the call site that wasn't migrated | Global — a bug in the monkeypatch affects every caller in the process, including third-party code that imports `swisseph` directly for any reason |
| Thread-safety requirement (§3.7) | Each call site must itself be safe under concurrent threads (already true today — the assertion is a stateless function call) | The monkeypatch install must happen exactly once at import time (module-level code executes once under Python's import lock) — verify no re-entrant re-patching if `ephemeris.py` is reloaded (e.g. in tests using `importlib.reload`) |
| Detectability of new violations | Requires the AST/grep test to run in CI and to correctly parse every new file | Structural — a new caller literally cannot reach the unwrapped function, no lint drift risk |
| Downside | Someone could still call `swisseph.calc_ut` directly if lint regex has a blind spot (e.g. dynamic import, `getattr(swe, "calc_ut")`) | Monkeypatching a compiled-extension module's attribute may not be safe/permanent for all `pyswisseph` build variants — must be verified against the actually-installed `pyswisseph>=2.10.3` before adoption, not assumed to work in general |

**Decision:** deferred to the planner/architect (Phase 1), recorded via ADR. This PRD's
acceptance criteria (§7) are written to be satisfied by either option.

### 6.2 Design for the genuinely flag-less class (`houses`, `houses_ex`, `houses_ex2`, `houses_armc`, `houses_armc_ex2`)

No variant returns a flag (§3.3) — this is a hard, verified constraint, not a design
choice. Candidate approaches for the planner/architect to evaluate (not pre-decided):

1. **Precondition-gate**: only call `swe.houses*` after at least one flag-checked
   body call has already succeeded in the same request using the same `SwissEphBackend`
   instance/global ephemeris-path state — transitively proves SWIEPH is active for the
   process at that point in time.
2. **Construction-time guarantee**: rely on `SwissEphBackend.__post_init__`'s existing
   `ensure_ephemeris_files()` check (§3.2) as the sole protection for `houses*` calls —
   requires explicitly documenting what this does **not** catch (e.g. mid-request file
   removal/corruption, or a JD outside the range covered by present `.se1` files) as an
   accepted residual risk.
3. A documented, reviewed combination of (1) and (2), with the residual-risk boundary
   written into `docs/verification_vectors.md`-equivalent documentation for this increment.

**Decision:** deferred to the planner/architect, recorded via ADR. Whichever approach is
chosen must explicitly state what residual gap (if any) remains and why it's accepted —
"no-op" and "silent" are both explicitly disallowed outcomes per the source doc.

### 6.3 Non-negotiable constraints (apply regardless of §6.1/6.2 choice)

- Zero direct `swe.calc*`/`swe.houses*`/`swe.fixstar*` calls outside `bazi_engine/ephemeris.py` (mechanically verified by an AST/grep test in CI).
- Enforcement is env-toggleable but **hard-on by default** (canvas Risk #1 mitigation) — no code path may make hard-fail the non-default behavior.
- Thread-safe under FastAPI's threadpool execution model (§3.7).
- No new customer-facing endpoints, no change to existing endpoint paths/response *structure* (only additive fields), consistent with this repo's "endpoints are frozen" rule.
- `python scripts/export_openapi.py --check` must stay green (regenerate via `python scripts/export_openapi.py` when models change).

---

## 7. Acceptance criteria (Given/When/Then)

### FQ-ATT-01

- **AC-01-1** (discovery). *Given* the implementer starts FQ-ATT-01, *when* they run
  `grep -rn "swe\." bazi_engine/`, *then* the resulting call-site list is diffed against
  §3.1's 4-site baseline (+ `bazi.py`'s `swe.julday` non-match) and any new/changed sites
  are triaged before code changes begin.
- **AC-01-2** (body/star calls). *Given* the chosen mechanism (§6.1, Option A or B),
  *when* any code path calls `swe.calc`, `swe.calc_ut`, `swe.fixstar`, `swe.fixstar_ut`,
  `swe.fixstar2`, or `swe.fixstar2_ut` with MOSEPH actually used but not requested,
  *then* `EphemerisUnavailableError` is raised before any response is constructed.
- **AC-01-3** (houses class). *Given* the chosen design (§6.2), *when* `SE_EPHE_PATH`
  points at a directory missing required `.se1` files, *then* any endpoint that calls
  `swe.houses*` fails closed (raises `EphemerisUnavailableError` or an equivalent hard
  failure) rather than silently returning geometrically-computed-but-unattested house
  cusps.
- **AC-01-4a** (flag-checkable class — mocked-return-flag test). *Given* the call sites in
  the flag-checkable class (`swe.calc`/`swe.calc_ut`/`swe.fixstar*`, confirmed today at
  `western.py:64` and `transit.py:131`, plus any additional sites T1/T4 discover), *when* a
  test constructs the backend with ephemeris files **present** (so the construction-time
  `ensure_ephemeris_files()` guard in `SwissEphBackend.__post_init__`, §3.2, passes) but
  mocks/forces the return flags from `swe.calc_ut`/`swe.fixstar*` to include
  `SEFLG_MOSEPH` — extending, not replacing, the existing precedent in
  `tests/test_ephemeris_fallback.py::TestWesternFallbackDetection::test_western_catches_moseph_fallback`
  and its parallel `TestTransitFallbackDetection` test — *then* the migrated (T2/T4)
  wrapper raises `EphemerisUnavailableError` before any response is constructed. **This is
  the only test design that actually reaches and exercises the return-flag detection
  logic for this class.** An empty-`SE_EPHE_PATH`-directory test alone is insufficient
  here: `SwissEphBackend.__post_init__`'s construction-time `ensure_ephemeris_files()`
  check raises first, so the test would never reach the `swe.calc_ut`/
  `assert_no_moseph_fallback` code path at all, and would pass identically even if the
  migrated flag-checking wrapper were silently broken or missing (spec-auditor finding,
  2026-07-01).
- **AC-01-4b** (flag-less / construction-time-guard class — empty-directory test). *Given*
  `tests/test_ephemeris_attestation.py` parametrized over the flag-less class (confirmed
  today: `routers/info.py:90`'s `/health` `_check_ephemeris()` — the one call site with no
  `SwissEphBackend` construction and no return-flag check at all — plus any other endpoint
  whose *only* protection is the missing-`.se1`-files construction-time guard, per T1's
  inventory), *when* run with `SE_EPHE_PATH` set to an empty directory, *then* every such
  endpoint raises `EphemerisUnavailableError` (or, for `/health`, reports `unavailable`)
  and `pytest tests/test_ephemeris_attestation.py -q` is green. This empty-directory
  methodology is the correct test design for this class specifically, since the
  construction-time guard is exactly what it exercises — it must **not** be reused as the
  sole proof for the flag-checkable class above (AC-01-4a).
- **AC-01-5** (static guard). *Given* the AST/grep lint test, *when* it scans
  `bazi_engine/` excluding `ephemeris.py`, *then* it finds zero direct calls to
  `swe.calc*`, `swe.houses*`, or `swe.fixstar*` and fails the build if any exist.
- **AC-01-6** (health check closes the one bare gap). *Given* `routers/info.py`'s
  `_check_ephemeris()`, *when* it is migrated to the chosen mechanism, *then* `/health`
  fails (or reports `unavailable`) under a forced-MOSEPH environment, exactly like every
  other calculation endpoint.

### FQ-ATT-02

- **AC-02-1** (tzdata pin). *Given* `tzdata` is added as a pinned dependency in
  `pyproject.toml` and locked in `requirements.lock`/`uv.lock`, *when*
  `_detect_tzdb_version()` runs in any deployed environment, *then* it returns a real
  IANA tzdata version string, never `"unknown"`.
- **AC-02-2** (per-endpoint contract). *Given* the T1 endpoint inventory, *when* a
  successful (2xx) calculation response is returned from any endpoint that performs an
  ephemeris-dependent calculation, *then* `provenance.ephemeris_id` and
  `provenance.tzdb_version_id` are present and not `"unknown"`/empty, and
  `quality_flags.ephemeris_mode == "SWIEPH"` under test ephemeris configuration;
  `quality_flags.house_system_fallback` is present and boolean for every house-computing
  endpoint (`western`/`fusion`/`chart`/`experience/*`) and absent on non-house endpoints
  (`bazi`/`wuxing`) — confirmed scope, OQ-1, §9. **Amended 2026-07-08 (user decision
  2026-07-01, contradictions Finding 5):** `/calculate/tst` is exempt from
  `quality_flags` entirely (no ephemeris work on its path — see §5.2); it carries
  `provenance` only, and its `tzdb_version_id` bar still applies.
- **AC-02-3** (missing-field endpoints closed). *Given* `BaziResponse`, `WxResponse`,
  `TSTResponse` previously had no `quality_flags` field at all (§3.5), *when* FQ-ATT-02 is
  implemented, *then* `BaziResponse` and `WxResponse` carry the attestation fields
  applicable to them (at minimum `ephemeris_mode`, `ephemeris_id`, `tzdb_version_id`) as
  an additive, backward-compatible change. **Amended 2026-07-08:** `TSTResponse` is
  deliberately exempt from `quality_flags` (user decision 2026-07-01, contradictions
  Finding 5) and carries `provenance` only.
- **AC-02-4** (dead-code hardening). *Given* the `_quality_flags_for_daily()` None-branch
  (§3.6), *when* FQ-ATT-02 is implemented, *then* this branch either can no longer be
  constructed with `None` values or is removed — it may not remain a latent
  `ValidationError` trap.
- **AC-02-5** (contract test). *Given* `pytest -k attestation_contract`, *when* run
  against every T1-inventoried endpoint, *then* it is green.
- **AC-02-6** (OpenAPI drift). *Given* any response-model field additions from AC-02-3,
  *when* `python scripts/export_openapi.py --check` runs, *then* it is green (spec was
  regenerated and committed, not just hand-edited).

---

## 8. Non-functional requirements

| ID | NFR | Statement |
|---|---|---|
| NFR-ATT-1 | Rollout safety | Hardening enforcement is env-toggleable; default is hard-fail; staged rollout (staging environment first) before default enforcement reaches production traffic. (Canvas Risk #1.) |
| NFR-ATT-2 | Compatibility | All schema changes are additive; no endpoint path or existing-field removal; `scripts/export_openapi.py --check` green. |
| NFR-ATT-3 | Coverage | New test files count toward `pytest --cov-fail-under=75`; unlike WS-B/D, this increment adds no network-oracle code, so no `.coveragerc` carve-out is expected — flag it during implementation if one turns out to be needed (MISSING: confirm no exclusion needed once the mechanism is chosen). |
| NFR-ATT-4 | Thread-safety | Whichever FQ-ATT-01 mechanism is chosen (§6.1) must be safe under FastAPI's shared-threadpool execution model for synchronous path-operation functions (§3.7) — verified by a concurrent-request test, not assumed from single-threaded test runs. |
| NFR-ATT-5 | Performance | No explicit latency budget exists in the source doc or canvas for this increment. **MISSING** — attestation checks are expected to add negligible (bitwise-comparison-level) per-call overhead, but this PRD does not assert a number; if the planner needs a hard budget, that is a new OPEN QUESTION, not silently assumed as "negligible = fine." |
| NFR-ATT-6 | Non-scope-creep into WS-F | This increment must not require or block the future runtime-attestation-metric/alerting work (WS-F, `FQ-OBS-01`) — e.g., raising `EphemerisUnavailableError` more broadly should not preclude adding structured-log fields later, but building that logging/alerting is explicitly out of scope now. |

---

## 9. Open items — labeled per the gap rule (none silently closed)

| ID | Label | Item | Recommended default (not adopted without confirmation) |
|---|---|---|---|
| OQ-1 | **CONFIRMED (user, 2026-07-01)** | Does `quality_flags.house_system_fallback` apply to calculation endpoints that do not compute houses at all (`/calculate/bazi`, `/calculate/wuxing`, `/calculate/tst`)? This directly shapes AC-02-2/AC-02-3's per-endpoint scope. | **Decided: scoped to house-computing endpoints only** (`western`, `fusion`, `chart`, `experience/*`); non-house endpoints (`bazi`/`wuxing`/`tst`) only carry `ephemeris_mode`/`ephemeris_id`/`tzdb_version_id`. Locked for Phase 1. |
| OQ-2 | OPEN QUESTION | Is `POST /validate` (BAFE contract-validation router, `bafe/service.py:167,173`) in scope for FQ-ATT-02's "never `unknown`" acceptance bar? Its `ephemeris_id` is contract-config-derived and explicitly nullable by schema (`spec/schemas/ValidateResponse.schema.json` types it `["string","null"]`, §3.5) — a different, deliberately-nullable contract, not the same gap as a live calculation's `ProvenanceResponse.ephemeris_id: str`. The canvas's allowed-change-scope does list `bafe/service.py` as editable, so it is not file-excluded from this increment. | Recommend the FQ-ATT-02 "never unknown, present on every response" acceptance bar applies only to live calculation endpoints, not `/validate`'s config dry-run — but `bafe/service.py` may still need edits (e.g. sourcing `ephemeris_id` from the same pinned detection as T7/T8) if the discovery task (T1) finds it should. Confirm at Phase 1. |
| OQ-3 | OPEN QUESTION (evidence-needed, per council sharpen #4) | Do any downstream consumers (Bazodiac/`New_Bazi`, ElevenLabs integration, or others) currently read `quality_flags` at all? | No recommendation — genuinely unverified; do not build value-justification on an assumed "yes." Track as a follow-up evidence-gathering item, not a blocker to shipping the guarantee itself. |
| OQ-4 | Architecture decision (planner, not user) | Mechanism choice §6.1 (Option A vs. B). | Explicitly deferred by design — not a gap requiring a user answer. |
| OQ-5 | Architecture decision (planner, not user) | Houses-class design §6.2. | Explicitly deferred by design — not a gap requiring a user answer. |
| OQ-6 | Implementation detail (ADR-eligible, reversible) | Exact `tzdata` package version to pin. | Recommend latest stable at implementation time, documented in an ADR with an upgrade policy. Reversible; does not need a user round-trip. |
| OQ-7 | Implementation detail (ADR-eligible, reversible) | Should `_detect_tzdb_version()` hard-fail (raise) instead of silently returning `"unknown"` if detection somehow still fails after `tzdata` is pinned? Changes failure-mode semantics (previously: degraded 200 with a bad string; proposed: 5xx). | Recommend raise, consistent with this repo's "fail visibly, no masking" development principle — but this changes observable behavior on an edge case, so flag for explicit review at code-review gate, not silently shipped. |
| OQ-8 | Implementation detail (ADR-eligible, reversible) | Should `ephemeris_mode`'s `Literal["SWIEPH","MOSEPH"]` type narrow to `Literal["SWIEPH"]` once MOSEPH can no longer reach a 2xx response? | No recommendation either way — cosmetic type precision, does not change the guarantee. Planner's call. |

**None of OQ-1 through OQ-8 are BLOCKERs.** No genuine product-critical gap was found
that halts this PRD — the canvas and council report already resolved the load-bearing
product questions (scope, target user, framing, deploy target, mechanism-choice deferral,
non-assertion of consumer behavior). OQ-1 is the one item with a real, if narrow,
acceptance-criterion impact and is flagged prominently for your explicit confirmation
before Phase 1 task-lock; it does not need a full `brainstorming` round given its bounded,
reversible nature and the clear default offered — but it is not treated as silently
adopted either.

---

## 10. Security matrix

| Axis | Assessment |
|---|---|
| Spoofing | No new auth surface introduced. |
| Tampering | No new user-controlled input for this REQ pair. |
| Repudiation | **Improves** repudiation posture — attestation fields becoming reliably non-`"unknown"` strengthens the audit trail this increment exists to build. |
| Information disclosure | Pre-existing, not introduced here: `EphemerisUnavailableError` raised via `ensure_ephemeris_files()` includes `resolved_path` (a server-local filesystem path) in the client-facing 503 body (§3.8). Centralizing MOSEPH detection makes this exception reachable from more call sites. Recommend the security-reviewer gate (Phase 2) confirm whether `resolved_path` should be redacted from the client response (log-only) as part of this hardening work — not silently left as-is nor silently fixed without review. |
| Denial of service | Converting a previously-tolerant path to hard-fail (503) is the intended behavior change, but if MOSEPH is currently silently active on any live production path today, hardening could turn a degraded-but-200 response into a fleet of 503s. Mitigated by NFR-ATT-1 (env-toggle, staged rollout, staging-first). |
| Elevation of privilege | N/A. |

---

## 11. Atomic tasks (each traces to a REQ; see `docs/traceability.md` for the full matrix)

| Task | REQ | Summary |
|---|---|---|
| T1 | FQ-ATT-01, FQ-ATT-02 | Re-run `grep -rn "swe\." bazi_engine/` (full repo, not just previously-checked files) **and** grep `response_model=` across `bazi_engine/routers/*.py` cross-referenced against `QualityFlags`/`ProvenanceResponse` imports, to build (a) the authoritative call-site list and (b) the authoritative endpoint × attestation-field coverage matrix. First step, before any code change. |
| T2 | FQ-ATT-01 | Planner/architect ADR: choose §6.1 mechanism (Option A or B) for the flag-checkable class. |
| T3 | FQ-ATT-01 | Planner/architect ADR: choose §6.2 design for the flag-less `houses*` class. |
| T4 | FQ-ATT-01 | Migrate the 4 confirmed sites (§3.1) plus any new ones T1 finds, per T2/T3 decisions; re-run T1's grep afterward to confirm 0 remaining direct calls outside `ephemeris.py`. |
| T5 | FQ-ATT-01 | Write `tests/test_ephemeris_attestation.py` split per AC-01-4a/AC-01-4b: (a) for the flag-checkable class (`calc`/`calc_ut`/`fixstar*`), a test that constructs the backend with ephemeris files present and mocks/forces the return flags to `SEFLG_MOSEPH`, extending — never silently dropping — the existing precedent in `tests/test_ephemeris_fallback.py` (`TestWesternFallbackDetection`/`TestTransitFallbackDetection`); if T4's migration changes the call-site shape, these tests must be explicitly ported/updated in the same PR, not orphaned; (b) for the flag-less/construction-time-guard class (`routers/info.py:90` and any endpoint whose only protection is the missing-files guard), the empty-`SE_EPHE_PATH`-directory methodology. Add the AST/grep static-guard test. |
| T6 | FQ-ATT-01 | Add env-toggle for enforcement (default hard-on); document staged rollout in a runbook/ADR (NFR-ATT-1). |
| T7 | FQ-ATT-02 | Add and pin `tzdata` in `pyproject.toml`; regenerate `requirements.lock`/`uv.lock`; ADR for exact version (OQ-6). |
| T8 | FQ-ATT-02 | Fix `_detect_tzdb_version()`; resolve OQ-7 (raise vs. fallback) at code-review gate. |
| T9 | FQ-ATT-02 | Using T1's matrix, add missing attestation fields to `BaziResponse`/`WxResponse`/`TSTResponse` (+ any other endpoints T1 finds); resolve OQ-1 scope for `house_system_fallback`; remove/fix the `_quality_flags_for_daily()` dead-code None-branch (§3.6). |
| T10 | FQ-ATT-02 | Per-endpoint attestation contract test (`pytest -k attestation_contract`) across the full T1 inventory. |
| T11 | FQ-ATT-02 | `python scripts/export_openapi.py --check` green; regenerate + commit if new fields were added. |
| T12 | FQ-ATT-01, FQ-ATT-02 | Standard `/agileteam` review/validation gates: code-reviewer, security-reviewer (§10 info-disclosure note), spec-auditor + plumbline-watcher against this PRD + canvas, product-owner Gate D. Team stays the full roster per council sharpen #5 — no downgrade to a lean fix. |

---

## 12. Rollout & rollback

Per canvas Risk #1 and the source doc's own risk table: enforcement sits behind an
env-toggle, hard-on by default, staging-first rollout. Rollback = disable the toggle
per-environment (not a code revert) if hardening surfaces an unexpected live MOSEPH
dependency; the underlying code change (centralized wrapper) remains in place either way.
Engine changes (FQ-ATT-01/02) are isolated, individually revertible PRs, consistent with
the source doc's "Globaler Rollback" principle (§4 of the source doc).

---

## 13. Handoff

- **To `spec-auditor` (Phase 0.5) and `planner`/`tester`**: this PRD, `docs/traceability.md`,
  REQ-IDs `FQ-ATT-01`/`FQ-ATT-02`, all `MISSING`/`OPEN QUESTION`/`ASSUMPTION` items in §9,
  and the two explicitly-deferred architecture decisions (§6.1, §6.2) that must be resolved
  via ADR before/during Phase 1.
- **To `product-owner`**: this PRD path, REQ-IDs, acceptance criteria (§7), non-goals
  (canvas §7), unresolved items (§9 — particularly OQ-1 and OQ-3), customer/user statements
  (canvas §§1-2), and the corrected value framing (this is a baseline guarantee for all
  paying customers, not a premium-tier feature — §0.1). Product Owner creates
  `docs/vision/fufire-premium-verification-ci.vision.md`. **Phase 0 is not complete until
  both this PRD and the Product Vision are confirmed by the user.**
- **To `context-keeper`**: keep `state.md`, `decision-log.md`, and ADRs consistent with
  `docs/traceability.md` as T2/T3/OQ-6/OQ-7/OQ-8 decisions are made.
