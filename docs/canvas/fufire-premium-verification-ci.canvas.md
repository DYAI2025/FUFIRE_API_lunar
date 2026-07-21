# Product Canvas: fufire-premium-verification-ci (increment 1: WS-A attestation end-to-end)

Status: user-confirmed
Owner: requirements-analyst
Confirmed by user: yes
Canvas file: docs/canvas/fufire-premium-verification-ci.canvas.md

> **Scope decision (user, 2026-07-01):** the source doc's 6 workstreams are sliced into
> sequential increments per the doc's own recommended order. **This canvas/PRD covers
> WS-A only** (FQ-ATT-01/FQ-ATT-02 — attestation end-to-end: no silent MOSEPH fallback,
> no `"unknown"` quality/provenance fields). WS-B (JPL/Jié independent oracle), WS-C
> (historical TZ accuracy), FQ-030 (threshold ratification), WS-D (CI gate expansion incl.
> the Cloud-Run-vs-Railway release gate), WS-E (scheduled Claude audit), and WS-F (prod
> runtime observability) are **explicitly deferred to follow-on canvases** — not built in
> this run. The full source doc `docs/2026-07-01-fufire-premium-verification-and-ci.md`
> remains the authoritative backlog for those follow-on increments.

> The Product Canvas is a **mandatory pre-build value-alignment artifact**. `/agileteam`
> may not finalize the PRD or enter development until this canvas is filled in well
> enough, saved, linked to PRD/Vision/traceability, and **explicitly confirmed by the
> user**. It does not replace the PRD, Product Vision, traceability, Reality Ledger,
> Watcher, or human-acceptance gates — it sits in front of them.
>
> Allowed `Status` values: `draft` | `user-confirmed` | `blocked`. Development entry
> requires `Status: user-confirmed`. No agent may self-confirm the canvas. A
> product-critical field left at `MISSING` / `OPEN QUESTION` / `BLOCKER` blocks Phase 1.

Source: `docs/2026-07-01-fufire-premium-verification-and-ci.md` (2026-07-01, German-language plan; author-context: authored from the Bazodiac/`New_Bazi` BFF that consumes the FuFirE API).

---

## 1. Problem

What real problem should be solved?

Status: CONFIRMED

Answer:
FuFirE cannot currently prove — continuously, independently, and automatically — that its
paid astronomical calculations never silently degrade, and that its accuracy claims hold
up against sources independent of its own self-referential validation. Concretely, per the
source doc's seven named gaps (G1–G7):

- **G1 — Apparent, not real, independence.** The existing reference comparison
  (`scripts/western_reference_validation.py` vs. astro.com/kerykeion) is not
  provider-independent for planetary numerics because kerykeion itself uses Swiss
  Ephemeris — systematic Swiss-Eph errors would stay invisible.
- **G2 — Ascendant error traced to historical TZ/LMT model.** 5 mismatches (97.2% vs.
  premium target) correlate with `utc_offset_minutes_zoneinfo` vs.
  `utc_offset_minutes_kerykeion` discrepancies for pre-1970/LMT-era dates.
- **G3 — Attestation not proven end-to-end.** `assert_no_moseph_fallback` exists in
  `bazi_engine/ephemeris.py` (verified present, reads the `SEFLG_MOSEPH` return-flag
  bit — belegt/confirmed by direct file read) but it is unconfirmed whether it is invoked
  on every `swe.calc_ut`/`swe.houses`/`swe.fixstar` path, and `tzdb_version_id` is
  sometimes exposed as `"unknown"`.
- **G4 — BaZi solar-terms/day-pillar validated only against the engine's own snapshots**,
  no official external (observatory) reference.
- **G5 — No scheduled independent adversarial AI audit exists.**
- **G6 — No production runtime attestation** (live smoke does not check calculation mode).
- **G7 — Pre-1582 calendar-reform / year-lower-bound engine behavior is unspecified.**

Paid customers currently have no hard, structural, continuously-enforced guarantee that a
response was computed with the high-precision Swiss Ephemeris backend rather than the
Moshier/MOSEPH analytical fallback, and no accuracy check independent of a source that
shares the same underlying implementation.

---

## 2. Target user / customer

Who has this problem?

Status: CONFIRMED

Answer:
**Decided (user, 2026-07-01): broad.** Any paying FuFirE API customer/integrator that
depends on non-degraded, verifiable calculation accuracy — not only the Bazodiac/`New_Bazi`
BFF that originally surfaced the need. Value claims and acceptance criteria are framed as a
general platform guarantee (no silent MOSEPH fallback; no `"unknown"` attestation fields on
any calculation response), not BFF-specific.

---

## 3. Current workaround

How is the problem handled today?

Status: CONFIRMED

Answer:
Per the source doc's "Bereits vorhanden" inventory (verified in-repo: `ephemeris.py`,
`chronometry.py`, `scripts/western_reference_validation.py`,
`reports/western_validation_summary.json` all exist as claimed):

- `bazi_engine/ephemeris.py::assert_no_moseph_fallback(requested_flags, returned_flags)`
  detects a silent Moshier fallback via the returned flag bit and raises
  `EphemerisUnavailableError` — but coverage across all calculation paths is unconfirmed.
- `.github/workflows/ci.yml` runs a 3.10–3.12 matrix, installs `libswe-dev`, loads/caches
  `.se1` ephemeris files, generates SWIEPH snapshots, and enforces
  `pytest --cov-fail-under=75` plus `scripts/export_openapi.py --check`.
- `.github/workflows/build-ephe-base.yml` + `Dockerfile.ephe-base` bake ephemeris files
  into a base image at build time.
- `scripts/western_reference_validation.py` compares 176 charts against the astro.com
  Astrodatabank via kerykeion: Sun/Moon 100%, Ascendant 97.15% (5 mismatches) — this is
  the self-referential check named in G1.
- Golden/snapshot regression tests (`tests/golden_reference_cases.py`,
  `tests/fixtures/western_reference_charts.json`,
  `tests/fixtures/bazi_baseline_v1.json`, `tests/snapshots/{moseph,swieph}/...` including
  high-latitude and Li-Chun solar-term-boundary cases).
- `bazi_engine/routers/validate.py` + BAFE JSON-Schema contract validation.
- Responses already carry `quality_flags.ephemeris_mode`, `quality_flags.house_system_fallback`,
  `provenance.ephemeris_id`, `provenance.tzdb_version_id` — but the doc states these are
  "currently partly `unknown`."

This is a partial, self-referential safety net (per G1–G4 above) — not a continuous,
independent, or production-enforced guarantee.

---

## 4. Value proposition

What concrete human/customer value will this create?

Status: CONFIRMED

Answer:
**Scoped to this increment (WS-A only):** a paid calculation response can structurally
never originate from an unrequested MOSEPH (Moshier) fallback — hard-enforced on every
calculation path, not just the paths already wired — and every calculation response
exposes real (never `"unknown"`) `quality_flags.ephemeris_mode`,
`quality_flags.house_system_fallback`, `provenance.ephemeris_id`, and
`provenance.tzdb_version_id`. This is the structural foundation the later increments
(JPL/Jié independent oracle, premium accuracy threshold, CI gate expansion, scheduled
audit, prod observability) build on, per the source doc's own recommended ordering.

The doc does not state a quantified business/monetary value (e.g., churn impact, price
premium justified, contractual SLA) beyond the qualitative "premium API quality" framing —
none is invented here.

---

## 5. Success signal

How will we know this is valuable?

Status: CONFIRMED

Answer:
**Scoped to this increment (WS-A only):** `pytest tests/test_ephemeris_attestation.py -q`
green (every calculation endpoint raises `EphemerisUnavailableError` under a forced-MOSEPH
test environment); an AST/grep guard shows zero direct `swe.calc*`/`swe.houses*`/
`swe.fixstar*` calls outside `bazi_engine/ephemeris.py`; a per-endpoint attestation
contract test shows `ephemeris_mode`, `house_system_fallback`, `ephemeris_id`,
`tzdb_version_id` present and never `"unknown"` on every calculation response; OpenAPI
drift check (`scripts/export_openapi.py --check`) stays green after the schema fields move
from optional to required.

The full-initiative Definition of Done (PR gate with JPL/Jié diffs, premium thresholds,
nightly live diff, weekly Claude audit, release-gate prod-smoke) applies to the deferred
follow-on increments, not this one.

---

## 6. Core use case

What is the smallest meaningful use case?

Status: CONFIRMED

Answer:
**Decided (user, 2026-07-01): WS-A alone** (FQ-A1 + FQ-A2), per the source doc's own
recommended execution order ("FQ-000 → WS-A → WS-B/WS-C parallel → FQ-030 → WS-D →
WS-E/F"): a paid calculation response can never silently originate from MOSEPH, and every
calculation response exposes non-`"unknown"`
`ephemeris_mode`/`ephemeris_id`/`tzdb_version_id`/`house_system_fallback` fields.

---

## 7. Non-goals

What should explicitly not be built?

Status: CONFIRMED

Answer:
Copied from the source doc's "Nicht-Ziele", corrected against verified repo reality and
narrowed to this increment:

- No change to astrological interpretation/narrative content (calculation logic and
  provability only).
- No new business-facing endpoints (only verification tooling; no new customer-facing
  features).
- No move away from Swiss Ephemeris as the runtime calculation engine (JPL Horizons is
  oracle-only, never a runtime backend — not relevant to this increment anyway, JPL work
  is WS-B, deferred).
- **No change to the deploy target — corrected to Railway** (the source doc said "Cloud
  Run bleibt", but this repo's `CLAUDE.md` states Railway is the verified active
  auto-deploy target and Fly.io was already decommissioned; `.github/workflows/
  deploy-cloudrun.yml` also exists as a manual-dispatch-only job, but is not this
  increment's concern). **Decided (user, 2026-07-01): redesign any future release-gate
  work (FQ-D3, WS-D, deferred) for Railway** rather than the Cloud-Run-shaped design in
  the source doc — recorded here for the follow-on WS-D canvas, not built now.
- **This increment builds WS-A only.** WS-B, WS-C, FQ-030, WS-D, WS-E, WS-F are explicit
  non-goals of *this* PRD (they are the whole-initiative's goals, deferred to later
  canvases per the scope decision above).

---

## 8. Risks / contradictions

What could make this wrong, useless, unsafe, misleading, too broad, or misaligned?

Status: CONFIRMED

Answer:
**Decisions recorded (user, 2026-07-01) — resolves the four open questions raised during
canvas drafting:**
1. Deploy target: Railway is the verified target; any future release-gate work (FQ-D3) is
   redesigned for Railway, not Cloud Run — deferred to the WS-D canvas, not this one.
2. Target user: broad (all paying API customers), not BFF-specific.
3. Premium threshold: stays provisional-until-ratified per the doc's own FQ-030 design —
   not this increment's concern (WS-C/FQ-030 deferred).
4. Scope: sliced — this canvas/PRD builds **WS-A only**.

**Risks in scope for this increment (WS-A):**
- **Hardening attestation enforcement could break production** if some calculation path
  currently tolerates a MOSEPH fallback that would now hard-fail with
  `EphemerisUnavailableError`. Mitigation per source doc: feature-gated rollout, staging
  first, env-togglable enforcement, hard default.
- **House/fixstar calls have no comparable flag mechanism** to body calls (`swe.calc_ut`/
  `swe.calc`) — a naive uniform wrapper could raise incorrectly or silently no-op on paths
  where no flag exists. FQ-A1 explicitly requires treating these as two separate classes;
  getting this wrong either breaks legitimate house calculations or leaves a real gap
  unguarded.
- **Response-field tightening (`Optional` → `required`) is a breaking OpenAPI contract
  change** for any consumer currently tolerating `"unknown"`/absent attestation fields —
  must be checked against `python scripts/export_openapi.py --check` and the "endpoints
  are frozen" rule in this repo's `CLAUDE.md` (field additions/tightening within an
  existing response shape, not a path/structure change, should be compatible — confirm
  during PRD drafting).
- **`tzdb_version_id` pinning** requires a `tzdata` dependency version decision
  (`pyproject.toml`/`requirements.lock`) — a wrong or unpinned choice reintroduces the
  `"unknown"` problem this increment exists to close.

**Risks belonging to deferred workstreams (not this increment, kept here for continuity
into the follow-on canvases):** JPL ecliptic-frame misalignment (WS-B), network-oracle
flakiness (WS-B/D), TZ-model snapshot shifts (WS-C), Claude-audit noise (WS-E), reference
data quality / Rodden filtering (WS-C), premium-threshold ratification (FQ-030), new
oracle/network test code affecting the coverage gate (WS-B/D).

---

## 9. Evidence needed

What must be verified before implementation can be considered real?

Status: CONFIRMED

Answer:
**Evidence required for this increment (WS-A):**
- Coverage proof that `assert_no_moseph_fallback` (or an equivalent flag-checked wrapper,
  `calc_checked()`) is reached on every `swe.calc_ut`/`swe.calc` call site, via
  `grep -rn "swe\." bazi_engine/` run for real (not assumed) — plus an explicit, separate
  treatment for `swe.houses*`/`swe.fixstar*` paths, which carry no comparable flag.
- `pytest tests/test_ephemeris_attestation.py -q` green, parametrized over every
  calculation endpoint (western/bazi/wuxing/fusion/daily), under a `SE_EPHE_PATH` pointed
  at an empty directory (forces MOSEPH) — must raise `EphemerisUnavailableError`.
- An AST/grep guard proving zero direct `swe.calc*`/`swe.houses*`/`swe.fixstar*` calls
  outside `bazi_engine/ephemeris.py`.
- A per-endpoint attestation contract test proving `ephemeris_mode`,
  `house_system_fallback`, `ephemeris_id`, `tzdb_version_id` are present and never
  `"unknown"`, with a real (pinned) `tzdata` version driving `tzdb_version_id`.
- `python scripts/export_openapi.py --check` green after the schema fields move from
  optional to required.

**Evidence belonging to deferred workstreams (kept here for continuity, not required for
this increment):** JPL Horizons frame-alignment proof (WS-B/FQ-B1), official Hong Kong
Observatory solar-term reference + day-pillar boundary-convention decision (WS-B/FQ-B2), a
frozen Rodden-AA/A-filtered chart set for the Ascendant accuracy metric (WS-C), ratified
`spec/quality_thresholds.json` values (FQ-030), CI negative-probe demonstrations for
FQ-D1/D2/D3 (WS-D), production smoke-test logs before traffic migration (WS-D/FQ-D3).

---

## Allowed change scope

List the only repo-relative files, directories, or glob patterns that implementation agents may edit for this feature. Keep this narrow and user-confirmed with the canvas. Examples: `src/<feature>/**`, `docs/<feature>.md`, `tests/<feature>/**`.

Status: CONFIRMED

Narrowed to WS-A only (attestation end-to-end — FQ-ATT-01/FQ-ATT-02). Machine-parsed by
`plumbline_scope.py` (Stop-hook scope guard): one bare glob pattern per bullet, `#`
introduces an inline comment (stripped before matching), no bold sub-headers or
multi-line continuations inside this list (both would corrupt the parsed pattern set —
learned the hard way once already on this feature; see decision-log if present).

Allowed change scope:

- bazi_engine/ephemeris.py
- bazi_engine/western.py
- bazi_engine/*.py  # any other swe.calc*/houses*/fixstar* call site the required grep -rn "swe\." bazi_engine/ discovery pass finds; exact set TBD by that grep
- bazi_engine/app.py
- bazi_engine/routers/**  # response-field guarantees only
- bazi_engine/bafe/service.py
- pyproject.toml
- requirements.lock
- uv.lock
- spec/schemas/*.schema.json  # attestation fields optional -> required
- spec/openapi/openapi.json  # regenerated via scripts/export_openapi.py, not hand-edited
- tests/test_ephemeris_attestation.py
- tests/test_ephemeris_fallback.py  # existing precedent pattern to extend/preserve, not orphan
- tests/test_attestation_contract.py
- tests/**  # any other new test file this increment's T5/T10 tasks add
- docs/runbooks/fq-att-01-rollout.md  # T6 staged-rollout runbook
- docs/contradictions/fufire-premium-verification-ci.contradictions.md  # plumbline-watcher CONTRA ledger
- docs/reality/fufire-premium-verification-ci.evidence.jsonl  # Reality Ledger (plumbline-reality-check)
- docs/canvas/fufire-premium-verification-ci.canvas.md
- docs/prd/fufire-premium-verification-ci.prd.md
- docs/vision/fufire-premium-verification-ci.vision.md
- docs/traceability.md
- docs/architecture/**  # planner ADRs (T2/T3 mechanism + houses-class decisions)
- docs/plans/**  # planner's atomic task-sequence doc
- docs/context/**  # run-ledger + .active-feature marker (orchestrator bookkeeping)
- concilium/reports/**  # pre-PRD challenge-council report
- config/claude/bin/**  # local PRIL CLI wiring (this repo lacked it; created to unblock Stop-hook enforcement)
- docs/2026-07-01-fufire-premium-verification-and-ci.md  # the source plan doc that seeded this feature
- AGENTS.md  # documents the attestation-first guarantee (quality_flags + provenance); user-added to scope 2026-07-03
- .gitignore  # exclude claude-flow daemon runtime junk (recurring PRIL scope-gate false-positive); user-added to scope 2026-07-08

Out of scope for this increment (belongs to deferred WS-B/C/D/E/F canvases, no glob
needed here since these are prose, not parsed): tests/oracle/**, scripts/build_jpl_reference.py,
scripts/attest_image_ephemeris.py, scripts/prod_attestation_smoke.py, spec/quality_thresholds.json,
spec/tests/tv_matrix.json, .github/workflows/** (verify/nightly/claude-audit/deploy-cloudrun),
docs/verification_vectors.md, docs/audits/, .claude/commands/fufire-independent-audit.md,
bazi_engine/chronometry.py (WS-C).

---

## 10. Traceability links

PRD: docs/prd/fufire-premium-verification-ci.prd.md (to be created, Phase 0.2)
Product Vision: docs/vision/fufire-premium-verification-ci.vision.md (to be created, Phase 0.4)
Traceability Matrix: docs/traceability.md (to be created, Phase 0.2)
Related REQ IDs (this increment): FQ-ATT-01, FQ-ATT-02
Related REQ IDs (deferred to follow-on canvases): FQ-IND-01, FQ-IND-02, FQ-ACC-01, FQ-CI-01, FQ-CI-02, FQ-CI-03, FQ-AUD-01, FQ-OBS-01
True-Line status: draft

---

## User confirmation

Confirmed by user: yes
Confirmation date: 2026-07-01
Confirmation note: User answered all 4 open questions raised at canvas draft time via
AskUserQuestion (deploy target → Railway; target user → broad; scope → slice WS-A first;
premium threshold → keep provisional-until-ratified). Canvas amended by orchestrator to
reflect these decisions and confirmed.
