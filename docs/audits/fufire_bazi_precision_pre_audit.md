# FuFirE BaZi Precision — Pre-Audit (Baseline)

**Status:** BASELINE — captures the state at the start of the
`BAZI-PRECISION-V2` initiative. **No production logic has been changed.**
Findings here are evidence for later phases; they are not fixes.

**Date:** 2026-05-14
**Initiative:** `BAZI-PRECISION-V2` (see `3-code/tasks.md` Phase
`BAZI-PRECISION-V2`)
**Scope:** Effective time model, BaZi core (LiChun / Jieqi / day anchor /
Zi-boundary / hour pillar), Wu-Xing vector, Fusion / L2, classical
interpretation, API contracts, tests, docs.
**Authority:** This document is the *empirical baseline*, not a design
spec. Phase 1+ work must cite finding IDs here when proposing changes.

## Evidence classes

Every finding is tagged with one of:

| Class | Meaning |
|-------|---------|
| `CODE` | Observed in source; cited with `file:line`. |
| `TEST` | Observed in an existing test assertion. |
| `SCHEMA` | Observed in `spec/schemas/`, `spec/rulesets/`, or `spec/openapi/openapi.json`. |
| `DOC` | Observed in committed documentation. |
| `MISSING` | Plan-referenced artifact does not exist in the repo. |
| `DOMAIN_REVIEW_REQUIRED` | Cannot be verified from code/tests alone; needs human domain authority. |

`MISSING` and `DOMAIN_REVIEW_REQUIRED` findings are stop-gate inputs.
They are not bugs by themselves; they are blockers for default
behavior changes.

## 0. Repository state confirmed

- `3-code/tasks.md` exists; Phases 1–4 marked complete, Phase 5 in
  progress. The plan's `BAZI-PRECISION-V2` block will be appended as a
  new phase section, not folded into existing rows. `CODE`
- All plan-referenced source modules exist:
  `bazi_engine/{bazi.py, constants.py, types.py, solar_time.py,
  time_utils.py, fusion.py, provenance.py}`, `bazi_engine/bafe/*`,
  `bazi_engine/routers/*`, `bazi_engine/wuxing/*`. `CODE`
- New modules implied by the plan **do not yet exist** (expected — they
  are Phase 1+ deliverables): `bazi_engine/time_context.py`,
  `bazi_engine/bazi_rules.py`, `bazi_engine/classical/`. `MISSING`
- All plan-referenced existing test files exist:
  `tests/{test_invariants.py, test_golden.py, golden_reference_cases.py,
  test_lichun_transitions.py, test_pillar_trace.py,
  test_openapi_contract.py, test_snapshot_stability.py,
  test_solar_time.py, test_time_utils.py}`. `TEST`
- `tests/conftest.py` auto-selects `EPHEMERIS_MODE=MOSEPH` when Swiss
  Ephemeris SE1 files are absent (`tests/conftest.py:25`). This is
  important: baseline snapshots must record the active ephemeris in
  their metadata — MOSEPH and SWIEPH give bit-identical results for
  most cases but may diverge at boundaries. `CODE`

## 1. Day-cycle anchor (Plan §7 / FBP-02-002)

### Finding A1 — Hardcoded `DAY_OFFSET = 49` in core constants
**Class:** `CODE`
**Evidence:** `bazi_engine/constants.py:22`
```python
DAY_OFFSET: int = 49  # Offset to align JDN so 1949-10-01 is Jia-Zi (0)
```
**Affected callers:**
- `bazi_engine/bazi.py:13` import, `:28` default arg of
  `sexagenary_day_index_from_date`, `:140` `calculated_offset = DAY_OFFSET`,
  `:143` used to derive `day_idx60`.
- `bazi_engine/routers/bazi.py:18` import, `:147` emitted in derivation
  trace as `"day_offset_used"`.
**Note:** Comment on `:22` claims "1949-10-01 is Jia-Zi (0)" but the
constant value itself is asserted as truth without an explicit
verification source.

### Finding A2 — Ruleset already carries an *unverified* day-cycle anchor independent of the core constant
**Class:** `SCHEMA`
**Evidence:** `spec/rulesets/standard_bazi_2026.json:22–27`
```json
"day_cycle_anchor": {
  "anchor_jdn": 2419451,
  "anchor_label": "Assumed JiaZi day (verify!)",
  "anchor_sexagenary_index_0based": 0,
  "anchor_type": "JDN",
  "anchor_verification": "unverified"
}
```
And `:353`: "Day-cycle anchor MUST be verified and pinned."
**Implication:** The ruleset has a parallel anchor record that the
core does **not** consult. Phase 2 (FBP-02-001/002) must reconcile.
Neither anchor is verified.
**Status:** `DOMAIN_REVIEW_REQUIRED` — verification of the 1949-10-01
Jia-Zi claim (or replacement with a stronger source) is required
before any Strict / v2 default change.

### Finding A3 — Test assertions treat `DAY_OFFSET == 49` as ground truth
**Class:** `TEST`
**Evidence:**
- `tests/test_invariants.py:16` — `assert DAY_OFFSET == 49`
- `tests/test_invariants.py:17–18` — asserts two reference dates
  (1912-02-18, 1949-10-01) both have sexagenary index 0.
- `tests/test_constants.py:86,89,92,96,123,128` — five further
  assertions including `assert DAY_OFFSET == 49` and a docstring
  "1949-10-01 should be Jia-Zi (甲子) day with DAY_OFFSET=49".
**Plan action:** Rewrite `test_invariants.py::test_day_offset_reference_examples`
to assert via anchor-ID and verification status, not literal `49`.
`test_constants.py` is **not** explicitly listed in the plan but
contains the same hard-truth pattern — flagged as
`DEV-2026-005` for follow-up.

## 2. Effective time model (Plan §6 / FBP-01-*)

### Finding B1 — `TimeStandard` enum has no TLST
**Class:** `CODE`
**Evidence:** `bazi_engine/types.py:9`
```python
TimeStandard = Literal["CIVIL", "LMT"]
```
And `:41`: `time_standard: TimeStandard = "CIVIL"`.
**Implication:** `TLST` cannot be selected via the API. The plan adds
it as a third value (FBP-01-001).

### Finding B2 — `true_solar_time_used` is set true when LMT is selected — *LMT is not TLST*
**Class:** `CODE` (P0 bug per plan §15)
**Evidence:** `bazi_engine/routers/bazi.py:152`
```python
"true_solar_time_used": inp.time_standard == "LMT",
```
**Why this is wrong:**
- LMT (Local Mean Time) = UTC + longitude/15h — mean solar.
- TLST (True Local Solar Time) = LMT + equation_of_time — apparent
  solar.
The current trace claims "true solar time" was used whenever LMT was
used, which it was not. This is the misleading-field defect.
**Plan action:** FBP-03-002 — rename/correct semantics; `true_solar_time_used`
is true only when TLST is selected; LMT gets its own flag.

### Finding B3 — Equation-of-time math exists but is not connected to the BaZi pillars path
**Class:** `CODE`
**Evidence:** `bazi_engine/solar_time.py:17–60` — `equation_of_time()` is
implemented (NOAA formula; precise variant), and the module docstring
exposes a `true_solar_time()` helper. The module is pure (stdlib-only)
as required by `tests/test_import_hierarchy.py::test_solar_time_has_no_internal_imports`.
**Implication:** The arithmetic is available; the plumbing into
`compute_bazi()` is missing. Phase 1 (FBP-01-002, FBP-02-005) can wire
this in opt-in / `/v2` only.

### Finding B4 — `/calculate/tst` endpoint exists in router layer
**Class:** `CODE`
**Evidence:** `bazi_engine/routers/fusion.py` mounts `/calculate/tst` per
`CLAUDE.md` documentation. Drift vs `solar_time.py` not yet measured —
Phase 1 must check (FBP-01-003).

## 3. Derivation trace / contract (Plan §8 / FBP-03-*)

### Finding C1 — Derivation trace is an untyped nested dict
**Class:** `CODE`
**Evidence:** `bazi_engine/routers/bazi.py:130–154` — the trace is built
as a literal `dict` with four top-level keys (`year`, `month`, `day`,
`hour`) each carrying small nested dicts. No Pydantic model backs it;
no `bazi_engine/schemas/bazi.py` exists.
**Plan action:** FBP-03-001 — typed trace.

### Finding C2 — Trace lacks CIVIL/LMT/TLST decomposition
**Class:** `CODE`
**Evidence:** `bazi_engine/routers/bazi.py:130–154`. The trace only
records `local_hour`, `branch_index`, and the misleading
`true_solar_time_used`. There is no `civil_local`, `utc`, `lmt`,
`tlst_hours`, `eot`, `tz_offset`, or `effective_standard` field.
**Plan action:** FBP-03-003.

## 4. Provenance (Plan §8 / FBP-03-004)

### Finding D1 — Provenance is shallow; missing model IDs
**Class:** `CODE`
**Evidence:** `bazi_engine/provenance.py:114–136` — `Provenance` carries
`engine_version`, `parameter_set_id`, `ruleset_id`, `ephemeris_id`,
`tzdb_version_id`, `house_system`, `zodiac_mode`, `computation_timestamp`.
**Missing (plan-required):** `ruleset_version`, `time_policy_id`,
`day_anchor_id`, `vector_model_id`, `normalization_model_id`,
`fusion_model_id`, `harmony_model_id`, `calibration_model_id`.

### Finding D2 — Provenance `ruleset_id` default does not match the actual ruleset file name
**Class:** `CODE` (severity: trace-misleading)
**Evidence:**
- `bazi_engine/provenance.py:142` — default `ruleset_id =
  "traditional_bazi_2026"`.
- `spec/rulesets/` — file is named `standard_bazi_2026.json`. There is
  no `traditional_bazi_2026.json`.
**Plan action:** Track as `DEV-2026-002`. Decide whether to rename the
file, the default, or both (under v2; v1 default must keep emitting
its current value or we break consumers).

## 5. OpenAPI / API surface (Plan §11)

### Finding E1 — OpenAPI 3.1.0; spec is large (9,290 lines)
**Class:** `SCHEMA`
**Evidence:** `spec/openapi/openapi.json:2` — `"openapi": "3.1.0"`. The
plan references OpenAPI 3.2.0 (Sept 2025) as the current standard but
does not mandate upgrade. **Decision deferred** to Phase 3.

### Finding E2 — Version drift between `__init__` and `pyproject.toml`
**Class:** `CODE`
**Evidence:**
- `bazi_engine/__init__.py:18` — `__version__ = "1.0.0-rc1-20260220"`
- `pyproject.toml:version` — `"1.0.0rc0"`
This is flagged in `CLAUDE.md` ("Versioning has two sources … When
bumping, update **both**"). **Status:** Known; tracked as `DEV-2026-003`.

### Finding E3 — No standalone `ErrorEnvelope.schema.json`; envelope is inlined in `app.py`
**Class:** `SCHEMA` + `MISSING`
**Evidence:**
- `spec/schemas/` contains only `refdata_manifest.schema.json`,
  `ValidateRequest.schema.json`, `ValidateResponse.schema.json`.
- `bazi_engine/app.py:515,530` — `ErrorEnvelope` is defined inline
  inside the OpenAPI customization function.
**Plan action:** FBP-03-005 / FBP-03-006 — extract to
`spec/schemas/ErrorEnvelope.schema.json` and plan RFC 9457 v2
compatibility.

## 6. Golden cases (Plan §5 / FBP-00-003, FBP-00-005)

### Finding F1 — Engine-derived goldens are presented as if external
**Class:** `TEST`
**Evidence:** `tests/golden_reference_cases.py:10–18`
```
All expected values were computed by the BaZi Engine v1.0.0-rc0 using
Swiss Ephemeris and verified for structural correctness.

Sources:
- "engine"    = computed by BaZi Engine, verified structurally
- "lichun"    = LiChun boundary test (year pillar must flip)
...
```
The `source` strings act as informal categories, but every value
ultimately originates from the engine — there is no external oracle.
A regression in the engine will silently rewrite "truth".
**Plan action:** FBP-00-003 / FBP-00-005 — formalize `source_type`
(`ENGINE_BASELINE | EXTERNAL_ORACLE | DOMAIN_REVIEW_REQUIRED`) and
ensure `test_golden.py` honors it.

## 7. Wu-Xing vector and fusion (Plan §9)

### Finding G1 — `WUXING_PARAMETER_SET["version"] = "1.1.0"` is currently the only versioning hook
**Class:** `CODE`
**Evidence:** `bazi_engine/provenance.py:18`. There is no
`vector_model_id`, `normalization_model_id`, or `harmony_model_id` —
the single `parameter_set` `version` field carries all of these
concerns implicitly. This makes v1/v2 parallel operation (FBP-04-005)
impossible without first separating the dimensions.

### Finding G2 — Raw vs L2-normalized Wu-Xing vector separation status: **not audited at Phase 0**
**Class:** `DOMAIN_REVIEW_REQUIRED` for Phase 4 scope; explicitly
out-of-scope for Phase 0 docs-only work. Note for FBP-04-001.

## 8. Classical interpretation layer (Plan §10)

`bazi_engine/classical/` does not exist. Hidden-stem tables and any
Ten-Gods / DMS logic, if present, live elsewhere — not audited in
Phase 0 beyond noting the structural absence. `MISSING`

## 9. Phase 0 stop-gate status

| Stop-gate (Plan §5) | Status |
|---|---|
| Verified Day-Cycle-Anchor? | ❌ Unverified (ruleset says so explicitly, core constant is independent and unsourced). Phase 1 is **opt-in / diagnostic only** until resolved. |
| External boundary golden cases? | ❌ None. All goldens are engine-derived. No default change allowed. |
| v1 snapshot? | 🟡 Pending — FBP-00-004 export script and `tests/fixtures/bazi_baseline_v1.json` are deliverables of *this* phase, not prerequisites. |

**Conclusion:** Phase 1 may proceed in opt-in / diagnostic mode only.
Default behavior of `/calculate/bazi` and `/calculate/fusion` is
**frozen** until anchors are verified and migration deltas are
documented.

## 10. Initial deviation register entries

The following deviations are seeded from Phase 0 findings and entered
into `docs/precision/deviations.md`:

- `DEV-2026-001` — `true_solar_time_used` semantic mislabel
  (Finding B2). Severity: P0.
- `DEV-2026-002` — Provenance `ruleset_id` default mismatch with
  ruleset filename (Finding D2). Severity: P1.
- `DEV-2026-003` — Engine version split between `__init__.py` and
  `pyproject.toml` (Finding E2). Severity: P1.
- `DEV-2026-004` — Day-cycle anchor unverified (Findings A1+A2).
  Severity: P0 (blocker for v2 default).
- `DEV-2026-005` — Hardcoded `DAY_OFFSET == 49` asserted as truth in
  `tests/test_constants.py` in addition to `tests/test_invariants.py`
  (Finding A3). Severity: P1 (follow-up to FBP-02-002).
- `DEV-2026-006` — `ErrorEnvelope` inlined in `app.py` instead of
  versioned schema (Finding E3). Severity: P2.
- `DEV-2026-007` — Wu-Xing model versioning collapsed into a single
  `parameter_set.version` field (Finding G1). Severity: P1
  (precondition for FBP-04-005).

## 11. What this audit does *not* answer

- Whether the equation-of-time formula in `solar_time.py` agrees with
  `/calculate/tst` for the timezones we actually serve (FBP-01-004).
- Whether `compute_bazi()` and `/validate` use compatible rulesets in
  practice (FBP-02-001).
- Whether the L2 normalization in fusion silently divides on near-zero
  vectors (FBP-04-001).
- Whether downstream Bazodiac / ElevenLabs consumers rely on any
  field this plan would deprecate.

These are deferred to their respective phases. Marking them here so
the next reviewer knows what is and is not covered.

## 12. References

- Implementation plan: pasted into session `/loop` invocation
  `2026-05-14`; canonical copy lives in this audit's history. (No
  separate plan file is checked in yet — the plan itself instructs
  this audit to be the durable artifact.)
- Repo conventions: `CLAUDE.md` (project root) and `3-code/CLAUDE.code.md`.
