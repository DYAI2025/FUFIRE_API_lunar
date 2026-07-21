# BaZi–ZWDS Synergy & ZWDS Core-Seed Engine — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` (or `superpowers:subagent-driven-development` for same-session) to implement this plan task-by-task. Each task is independently executable without re-deriving the whole design.

**Goal:** Add a versioned, source-honest Zi-Wei-Dou-Shu (紫微斗數 / ZWDS) natal calculation engine to FuFirE, then a strictly-separated BaZi↔ZWDS semantic **synergy** layer that emits evidence-bound reflection hypotheses (never deterministic fate claims) and a BaZodiac presentation surface.

**Architecture:** Two independent Level-4 calculation engines (`bazi.*` already exists; new `bazi_engine/zwds/`) that **never import each other**. A new Level-4 `bazi_engine/synergy/` package sits *above* both and consumes only their outputs through a neutral semantic ontology. ZWDS gets its own deterministic Swiss-Ephemeris-native Chinese lunisolar calendar provider (the repo has none). All ZWDS/synergy rulesets are immutable, hash-locked data files; every emitted rule carries a `source_status`. The new HTTP surface is `/v1`-only (deliberate B2B, no legacy dual-mount — same idiom as `admin`/`match`).

**Tech Stack:** Python 3.10–3.12, FastAPI, Swiss Ephemeris (`pyswisseph`), JSON Schema Draft 2020-12, `jsonschema`, pytest. Reuses `time_utils.resolve_local_iso`, `time_utils.to_chart_local`/`apply_day_boundary`, `time_context.compute_effective_time_context`, `jieqi.find_crossing`, `dayun.direction.resolve_direction_for_request`, the `require_api_key` dep, the slowapi limiter, `RequestIdMiddleware`, and the `ErrorEnvelope`/provenance conventions.

**Design source of truth:** the audited **ZWDS Design Pack v2** (in scratchpad `zwds_pack/zwds_fufire_design_pack_v2/`). Copy its artifacts into the repo in Phase 0. The pack's verdict — **CONDITIONAL GO** for `zwds.fufire.core-seed.v1`, **BLOCKED** for any "complete / original / universal / infallible" claim — is binding.

---

## Goal and Non-Goals

### Goals
1. Deterministic ZWDS **natal** chart from civil birth data, for one immutable `ruleset_id`.
2. A runtime-local, deterministic Chinese lunisolar calendar provider (Swiss-Ephemeris-native).
3. Two ZWDS endpoints: `POST /v1/calculate/zwds`, `GET /v1/metadata/zwds/rulesets/{ruleset_id}`.
4. A neutral semantic ontology + per-system signal mappers (BaZi, ZWDS).
5. A versioned mapping registry + fusion core (convergence / complement / divergence / no-safe-fusion) with an evidence-linked confidence model.
6. A BaZodiac presentation layer: themes, dual-perspective, evidence view, reflection prompts.
7. Temporal synergy (Da-Yun × ZWDS decadal → theme windows) and dyadic HeHun synergy (reusing `match/`).

### Non-Goals (BLOCKED — never claim or emit)
- "Complete", "original", "universal", "imperial-secret", "108-star", or "infallible" ZWDS. The word *complete* is only ever `complete for ruleset <id>`.
- Any `IDENTICAL` mapping between a BaZi Ten-God and a ZWDS palace/star.
- Deterministic predictions about love, career, money, health, or fate; medical/financial/legal guidance; "both systems prove …"; irreversible personality labels.
- A stateful fusion/chart store (see D-3). A `VERIFIED` label from mere schema-validity or determinism (see D-5).
- Historical-authenticity certification. Star placement is deterministic *within a ruleset*; interpretation stays rule- and school-dependent.

---

## Decisions (record in `docs/precision/deviations.md`)

- **D-1 — Calendar provider (answered).** Build the lunisolar provider from Swiss Ephemeris (true new-moon conjunction search + no-中氣 leap rule). No runtime dependency. A reference library (`sxtwl`/`cnlunar`) is used **offline only** to generate + cross-check the independent boundary corpus — never imported at runtime.
- **D-2 — Naming to avoid collision (binding).** `bazi_engine/fusion.py` and `POST /calculate/fusion` already exist (Wu-Xing/Harmony fusion, frozen). The new semantic layer is `bazi_engine/synergy/` and mounts at `/v1/synergy/*`. Do **not** touch the existing `fusion` module/endpoint. The user design doc's `/v1/calculate/fusion` is renamed `/v1/synergy/bazi-zwds`.
- **D-3 — `fusion_id` is content-addressed, stateless.** `fusion_id = "syn_" + sha256(canonical_json(normalized_inputs + ruleset refs))[:32]`. `GET /v1/synergy/{fusion_id}/…` endpoints accept an **opaque token** (`fusion_ref`) that base64url-encodes the normalized inputs+ruleset ids (size-bounded, integrity-guarded by the embedded sha256); the server recomputes deterministically. No DB, no TTL store required. If the token is malformed/oversized → `synergy_ref_invalid`. (Alternative kept in reserve: a `transit.py`-style TTLCache.)
- **D-4 — ZWDS build label.** `bazi_engine/zwds/__init__.py` carries `__zwds_engine_version__` (e.g. `0.1.0-core-seed`), mirroring the `bazi_engine.__version__` snapshot-regen discipline. Bump deliberately with any golden regeneration.
- **D-5 — Ship honest.** `zwds.fufire.core-seed.v1` ships with `school_label: null`, `source_status: "SOURCE_NEEDED"`, docs say `core-seed`. Never emit `VERIFIED`/`SOURCE_REVIEWED` at the chart level until GATE-1 passes.

---

## Gates (hard preconditions between program phases)

- **GATE-1 — Natal golden review.** No task in Phase 2+ may start until the Phase 1 natal golden corpus is **practitioner-reviewed** and the release-gate checklist (formula tests, calendar-boundary corpus, ruleset hash-lock, single-source-of-truth graph, `core-seed` language) is green. Rationale (design pack): never multiply an unstable natal contract across signal/fusion/temporal layers. Phases 2–6 are written bite-sized below **but each carries this gate**; their line-level TDD steps are finalized against real Phase-1 golden outputs when the gate opens (specifying exact expected vectors now would be fabrication).

---

## Preconditions and Known Gaps

- **No lunisolar calendar exists.** `phases/lunar_phase.py` is a mean-synodic approximation, unusable for chart `m`/`d`. Phase 1A builds the real provider. This is the single largest correctness risk.
- **Leap-month + month-numbering (時憲曆 no-中氣 rule)** is the hard sub-problem. Correctness is proven by the independent boundary corpus (Phase 1A), not by inspection.
- **Import hierarchy** (`tests/test_import_hierarchy.py`) must learn that `zwds/` and `synergy/` are Level 4; `routers/zwds.py`, `routers/synergy.py`, `services/zwds_service.py` are Level 5. `synergy/` may import `bazi.*` and `zwds.*`; `zwds/` must **not** import `bazi.*` and vice-versa (new enforced rule).
- **OpenAPI is frozen + drift-checked.** Every endpoint/model task ends with `python scripts/export_openapi.py` + a passing `--check`. New `/v1` surfaces are additive and allowed.
- **CI native lib:** any CI job importing `bazi_engine` needs `libswe-dev` (see memory `fufire-dayun-v1-1-0-and-libswe-ci`). No new CI job should import the engine without it.
- **Source materials:** the guide (`S-01`) is a formula seed with a known token error (`庚/午`) and unsupported completeness claims; `iztro` (`S-05/06`) is an implementation comparator, **not** historical proof. Golden vectors need practitioner sign-off (GATE-1).

---

## Governance Invariants (assert in tests, every phase)

1. **Typed IDs.** `StemId`, `BranchId`, `AnimalId` are three distinct enums. No union string; the animal is never a branch value (kills the `庚/午` class error). — `ZWDS-REQ-001`
2. **Safe modulo.** All wrap-around via `mod12`/`mod10` helpers; never rely on Python `%` sign for the public formulas. — `ZWDS-REQ-002`
3. **Single source of truth.** `chart.star_placements[]` is canonical; palaces hold only `placement_ids[]`. No embedded duplicate star objects. — `ZWDS-REQ-012`
4. **Status separation.** `calculation_status` (SUCCESS/DEGRADED) ≠ `source_status` (SOURCE_REVIEWED/SOURCE_NEEDED/BLOCKED) ≠ `crosschecks`. Determinism never upgrades `source_status`. — `ZWDS-REQ-013`, `D-5`
5. **Immutable ruleset.** One `ruleset_id` per request; response returns the full effective fingerprint (component hashes). No per-request policy overrides. — `ZWDS-REQ-011`
6. **Engines separated.** `zwds/` ⊥ `bazi/`; only `synergy/` sees both. — `SYN-REQ-010`
7. **No IDENTICAL cross-system mapping; claim-safety block-list enforced.** — `SYN-REQ-005`, `SYN-REQ-009`
8. **Completeness is manifest-based.** `missing_families = declared − emitted`; the word "complete" only as `complete for ruleset <id>`. — `ZWDS-REQ-018`

---

## Program Phase Map

| Phase | Title | Endpoints | Gate |
|------|-------|-----------|------|
| 0 | Foundations & governance | — | — |
| 1 | ZWDS core-seed natal engine + calendar + rulesets | `POST /v1/calculate/zwds`, `GET /v1/metadata/zwds/rulesets/{id}` | produces GATE-1 |
| 2 | Signal extraction (ontology + BaZi/ZWDS mappers) | — | after GATE-1 |
| 3 | Synergy core (mapping registry + fusion relations + confidence) | `POST /v1/synergy/bazi-zwds` | after GATE-1 |
| 4 | BaZodiac explanation layer | `GET /v1/synergy/{fusion_ref}/themes`, `.../themes/{theme_id}/evidence` | after GATE-1 |
| 5 | Temporal synergy (Da-Yun × ZWDS decadal) | `POST /v1/synergy/bazi-zwds/timeline` | after GATE-1 |
| 6 | HeHun / relationship synergy | `POST /v1/synergy/bazi-zwds/hehun` | after Phase 3 + `match/` |

---

# Phase 0 — Foundations & Governance

### Task ZWDS-P0-01 — Vendor the design-pack artifacts
**REQ:** ZWDS-REQ-019 · **Files:** Create `spec/schemas/zwds/ZwdsRequest.schema.json`, `spec/schemas/zwds/ZwdsRawResponse.schema.json` (copy from scratchpad pack, unchanged); `docs/zwds/design-pack/` (copy `zwds_formula_spec.md`, `zwds_backend_architecture.md`, `analysis_report.md`, `claim_audit.md`, `source_ledger.md`, `response_example_core.json`).
- **Step 1:** Copy the two schema files verbatim into `spec/schemas/zwds/`. Copy the six doc/example files into `docs/zwds/design-pack/`.
- **Step 2:** Add `tests/zwds/test_design_pack_vendored.py`: assert each copied schema file loads as JSON and its `$id` matches the pack (`urn:fufire:zwds:request:v1`, `urn:fufire:zwds:raw-response:v1`).
- **Step 3:** Run `pytest tests/zwds/test_design_pack_vendored.py -q` → PASS. **Commit** `feat(zwds): vendor audited design-pack schemas + docs`.
- **Acceptance:** both schemas load; `response_example_core.json` validates against `ZwdsRawResponse.schema.json` (add that assertion).

### Task ZWDS-P0-02 — Typed ID enums + safe modulo
**REQ:** ZWDS-REQ-001, ZWDS-REQ-002 · **Files:** Create `bazi_engine/zwds/__init__.py` (`__zwds_engine_version__ = "0.1.0-core-seed"`), `bazi_engine/zwds/domain.py`; Test `tests/zwds/test_domain.py`.
- **Step 1 (test first):** assert `StemId`, `BranchId`, `AnimalId` are distinct `Enum`s; `BranchId.ZI.value == 0 … HAI == 11`; `StemId.JIA == 0 … GUI == 9`; `mod12(-1) == 11`, `mod10(-1) == 9`, `mod12(14) == 2`. Assert `AnimalId` has no member equal to any `BranchId` (type-distinctness guard).
- **Step 2:** implement frozen enums + `def mod12(x): return ((x % 12) + 12) % 12` and `mod10`.
- **Step 3:** `pytest tests/zwds/test_domain.py -q` → PASS. **Commit** `feat(zwds): typed Stem/Branch/Animal IDs + safe modulo`.

### Task ZWDS-P0-03 — Import-hierarchy rules for zwds/ + synergy/
**REQ:** SYN-REQ-010 · **Files:** Modify `tests/test_import_hierarchy.py`; create empty `bazi_engine/synergy/__init__.py`.
- **Step 1 (test first):** add cases — `bazi_engine.zwds.*` must not import `bazi_engine.bazi`/`western`/`fusion`/`impact`; `bazi_engine.bazi` must not import `bazi_engine.zwds`; `bazi_engine.synergy.*` **may** import both `bazi.*` and `zwds.*` but not `routers`/`app`.
- **Step 2:** run → expect PASS on the empty packages (no violating imports yet). **Commit** `test(zwds): enforce engine separation in import hierarchy`.
- **Acceptance:** `pytest tests/test_import_hierarchy.py -q` PASS; the rule is now a standing guard for later tasks.

### Task ZWDS-P0-04 — Errors + failure-code contract
**REQ:** ZWDS-REQ-015 · **Files:** Create `bazi_engine/zwds/errors.py`; Test `tests/zwds/test_errors.py`.
- **Step 1 (test first):** assert error classes exist with these `error_code`s: `zwds_birth_time_required`, `zwds_ruleset_not_found`, `zwds_ruleset_not_release_ready`, `zwds_calendar_conversion_failed`, `zwds_direction_basis_missing`, `zwds_requested_scope_unavailable`, `zwds_ruleset_integrity_failed`, `zwds_graph_invariant_failed`. All subclass the existing `bazi_engine.exc` base so `error_handlers.py` renders them into `ErrorEnvelope`.
- **Step 2:** implement. **Step 3:** PASS. **Commit** `feat(zwds): typed failure-code contract`.

---

# Phase 1 — ZWDS Core-Seed Natal Engine

## 1A — Chinese Lunisolar Calendar Provider (highest risk)

### Task ZWDS-P1-01 — Calendar protocol + resolved-lunar-date type
**REQ:** ZWDS-REQ-003 · **Files:** Create `bazi_engine/zwds/calendar_provider.py`; Test `tests/zwds/test_calendar_protocol.py`.
- **Step 1 (test first):** assert a `ChineseLunisolarCalendar` `Protocol` with `resolve(chart_local_date: date) -> ResolvedLunarDate`; `ResolvedLunarDate` is a frozen dataclass with `year_label:int, month:int(1..12), day:int(1..30), is_leap_month:bool, month_length:29|30, calendar_engine_id:str`.
- **Step 2:** implement protocol + dataclass. **Step 3:** PASS. **Commit** `feat(zwds): lunisolar calendar protocol`.

### Task ZWDS-P1-02 — Swiss-Ephemeris new-moon search
**REQ:** ZWDS-REQ-003 · **Files:** Create `bazi_engine/zwds/astro_moon.py` (reuses `ephemeris`/`jieqi.find_crossing` bisection style); Test `tests/zwds/test_new_moon.py` (marked `swieph`).
- **Step 1 (test first):** `previous_new_moon(dt_utc)` and `next_new_moon(dt_utc)` return UTC instants where geocentric apparent `(moon_lon − sun_lon) mod 360 == 0` within 1e-4°; assert consecutive new moons are 29–30 days apart; assert a known 2024 new moon (e.g. 2024-02-09 22:59 UTC ± tolerance) matches.
- **Step 2:** implement conjunction bisection over elongation, analog to `find_crossing`.
- **Step 3:** PASS (skips w/o ephemeris). **Commit** `feat(zwds): swisseph new-moon conjunction search`.

### Task ZWDS-P1-03 — Principal-term (中氣) month numbering + leap rule
**REQ:** ZWDS-REQ-003 · **Files:** Modify `calendar_provider.py`; new `bazi_engine/zwds/calendar_swisseph.py`; Test `tests/zwds/test_calendar_leap_rule.py`.
- **Step 1 (test first):** a lunation containing **no** 中氣 (sun longitude crossing a multiple of 30° measured from 春分=0°/雨水 convention per the ruleset policy) is `is_leap_month=True` and shares the previous month's number; month 1 is the lunation containing 雨水 (330°). Use fixed known leap years (e.g. leap month in 2023 = leap 2nd month; 2020 leap 4th month) as assertions.
- **Step 2:** implement the no-中氣 leap-month suanfa over `astro_moon` + `jieqi` term crossings; expose `calendar_engine_id = "fufire-swisseph-shixian.v1"`.
- **Step 3:** PASS. **Commit** `feat(zwds): 中氣 month numbering + no-中氣 leap rule`.

### Task ZWDS-P1-04 — Independent boundary corpus (offline lib, D-1)
**REQ:** ZWDS-REQ-003 · **Files:** Create `tests/zwds/fixtures/lunisolar_boundary_corpus.json`, `scripts/zwds/gen_lunisolar_corpus.py` (offline generator using `sxtwl`/`cnlunar` — NOT imported at runtime, guarded `if __name__`); Test `tests/zwds/test_calendar_corpus.py`.
- **Step 1:** write the generator; produce ≥200 civil→lunar rows covering: 29- vs 30-day month ends, lunar-year transitions, every leap month 2000–2040, days around 23:00/00:00.
- **Step 2 (test):** for every corpus row, `calendar_swisseph.resolve(...)` equals the corpus `{year_label,month,day,is_leap_month}`.
- **Step 3:** run; fix provider until green. **Commit** `test(zwds): independent lunisolar boundary corpus`.
- **Acceptance:** corpus committed as data; generator documented as offline-only; provider matches 100% of rows. **This is the calendar correctness proof.**

## 1B — Seed Resolution Pipeline

### Task ZWDS-P1-05 — `ResolvedZwdsSeed` + time→hour-branch→late-Zi
**REQ:** ZWDS-REQ-004 · **Files:** Create `bazi_engine/zwds/seed.py`; Test `tests/zwds/test_seed_pipeline.py`.
- **Step 1 (test first):** given civil input, `resolve_seed` (a) calls `resolve_local_iso` with `earlier|later`/`error|shift_forward`; (b) applies ruleset time standard via `to_chart_local`/`compute_effective_time_context` (CIVIL/LMT/TLST); (c) derives `hour_branch_id` (Zi=0 double-hour); (d) detects late-Zi (23:00–24:00) and applies the late-Zi **chart-date** policy by advancing the chart date **through the calendar engine** (never a bare `d += 1`). Assert the `1984-02-01T23:30 Asia/Shanghai` late-Zi vector rolls the chart date across the lunar boundary.
- **Step 2:** implement; emit `ChronometryResolution` fields matching the schema.
- **Step 3:** PASS. **Commit** `feat(zwds): seed time/hour-branch/late-Zi pipeline`.

### Task ZWDS-P1-06 — Lunisolar + leap-month + year-cycle → `(m, d, y_s, y_b)`
**REQ:** ZWDS-REQ-004 · **Files:** Modify `seed.py`; Test extend `test_seed_pipeline.py`.
- **Step 1 (test first):** seed resolves `m∈1..12` (after leap-month interpretation policy), `d∈1..30`, and independent `y_s∈0..9`, `y_b∈0..11` via the year-cycle policy. Assert `y_s`/`y_b` are separate typed values (never a union). Emit `CalendarResolution` (`pre_late_zi_lunar_date`, `chart_lunar_date`, `effective_month_for_chart`, `year_cycle`).
- **Step 2:** implement. **Step 3:** PASS. **Commit** `feat(zwds): lunisolar+leap+year-cycle seed resolution`.

## 1C — Palaces, Stems, Bureau

### Task ZWDS-P1-07 — Ming/Shen + 12 palaces
**REQ:** ZWDS-REQ-005 · **Files:** Create `bazi_engine/zwds/palace.py`; Test `tests/zwds/test_palace.py`.
- **Formulas (YIN=2):** `ming_b = mod12(2 + (m-1) - (h-1))`; `shen_b = mod12(2 + (m-1) + (h-1))`; roles in order `[MING, XIONG_DI, FU_QI, ZI_NU, CAI_BO, JI_E, QIAN_YI, JIAO_YOU, GUAN_LU, TIAN_ZHAI, FU_DE, FU_MU]`; palace `i` has `branch = mod12(ming_b - i)`.
- **Step 1 (test first):** all **144** `(m,h)` combos (`12×12`); `m=1,h=1` → both Ming and Shen = `YIN`; role/branch mapping matches the `response_example_core.json` chart (Ming=YIN, Shen=YIN, FU_QI=ZI, …).
- **Step 2:** implement. **Step 3:** PASS. **Commit** `feat(zwds): Ming/Shen + 12-palace layout`.

### Task ZWDS-P1-08 — Palace stems (Five Tigers)
**REQ:** ZWDS-REQ-005 · **Files:** Modify `palace.py`; Test `tests/zwds/test_palace_stems.py`.
- **Formulas:** `yin_stem = mod10(2*y_s + 2)`; `palace_stem(branch_b) = mod10(yin_stem + mod12(branch_b - 2))`.
- **Step 1 (test first):** the five year-stem start pairs; `response_example` stems (YIN→BING, CHOU→DING, ZI→BING, …) for `y_s=JIA`.
- **Step 2:** implement. **Step 3:** PASS. **Commit** `feat(zwds): Five-Tigers palace stems`.

### Task ZWDS-P1-09 — Five-Elements Bureau + parity guard
**REQ:** ZWDS-REQ-006 · **Files:** Create `bazi_engine/zwds/bureau.py`; Test `tests/zwds/test_bureau.py`.
- **Formulas:** reject `(stem0 - branch0) mod 2 != 0`; `stem_group=floor(stem0/2)+1`; `branch_group=floor((branch0 mod 6)/2)+1`; `v=((stem_group+branch_group-1) mod 5)+1`; map `1→WOOD_3,2→METAL_4,3→WATER_2,4→FIRE_6,5→EARTH_5`.
- **Step 1 (test first):** all **60 valid** stem/branch parity pairs resolve to a bureau; invalid parity raises; Ming(BING,YIN)→`FIRE_6` (matches example). Ship the derived 60-pair table as data and assert it matches the formula.
- **Step 2:** implement + emit immutable `bureau_table.json` (hashed in ruleset). **Step 3:** PASS. **Commit** `feat(zwds): Five-Elements Bureau + parity guard`.

## 1D — Stars, Transformations, Relations, Decadals

### Task ZWDS-P1-10 — Zi Wei / Tian Fu
**REQ:** ZWDS-REQ-007 · **Files:** Create `bazi_engine/zwds/stars/major.py`; Test `tests/zwds/test_ziwei_tianfu.py`.
- **Formulas (B=bureau number):** `k=ceil(d/B)`; `delta=k*B-d`; `step=k+delta if delta even else k-delta`; `ziwei_b=mod12(2+step-1)`; `tianfu_b=mod12(4-ziwei_b)`.
- **Step 1 (test first):** all **150** `(d∈1..30, B∈{2,3,4,5,6})` cases produce `0..11`; `(d=1,FIRE_6)` per example → `ZI_WEI=YOU`, `TIAN_FU=WEI`.
- **Step 2:** implement. **Step 3:** PASS. **Commit** `feat(zwds): Zi Wei / Tian Fu placement`.

### Task ZWDS-P1-11 — 14 major stars
**REQ:** ZWDS-REQ-007 · **Files:** Modify `stars/major.py`; Test `tests/zwds/test_major_stars.py`.
- **Offsets from ziwei_b:** `ZI_WEI 0, TIAN_JI -1, TAI_YANG -3, WU_QU -4, TIAN_TONG -5, LIAN_ZHEN -8`. **From tianfu_b:** `TIAN_FU 0, TAI_YIN +1, TAN_LANG +2, JU_MEN +3, TIAN_XIANG +4, TIAN_LIANG +5, QI_SHA +6, PO_JUN +10`. `pos = mod12(base+offset)`.
- **Step 1 (test first):** for all **12** ziwei base positions the 14 placements match; the full example chart's 14 star branches match exactly.
- **Step 2:** implement, `formula_id="major-star-offsets.v1"`, `family_id="MAJOR_14"`. **Step 3:** PASS. **Commit** `feat(zwds): 14 major-star offsets`.

### Task ZWDS-P1-12 — 4 guide auxiliaries
**REQ:** ZWDS-REQ-007 · **Files:** Create `bazi_engine/zwds/stars/auxiliary.py`; Test `tests/zwds/test_aux_stars.py`.
- **Formulas (CHEN=4, XU=10):** `ZUO_FU=mod12(4+(m-1))`, `YOU_BI=mod12(10-(m-1))`, `WEN_QU=mod12(4+(h-1))`, `WEN_CHANG=mod12(10-(h-1))`.
- **Step 1 (test first):** all **144** `(m,h)` combos in `0..11`; example values (ZUO_FU=CHEN, YOU_BI=XU, WEN_QU=CHEN, WEN_CHANG=XU for m=1,h=1).
- **Step 2:** implement, `family_id="GUIDE_AUX_4"`, `source_status="SOURCE_NEEDED"` (seed subset). **Step 3:** PASS. **Commit** `feat(zwds): four guide auxiliary stars`.

### Task ZWDS-P1-13 — Four Transformations (versioned table)
**REQ:** ZWDS-REQ-008 · **Files:** Create `bazi_engine/zwds/transformations.py`, `bazi_engine/data/zwds/rulesets/zwds.fufire.core-seed.v1/transformations.json`; Test `tests/zwds/test_transformations.py`.
- **Step 1 (test first):** the four `HUA_*` are looked up from the versioned table by `y_s`; response includes `table_id` + the table's sha256; `y_s=JIA` → `HUA_LU=LIAN_ZHEN, HUA_QUAN=PO_JUN, HUA_KE=WU_QU, HUA_JI=TAI_YANG` (matches example); tampering the table changes the hash (integrity test). Also: `transformation_types` on the matching `star_placements[]` entries reflect the 4 transformations.
- **Step 2:** implement as data-driven lookup; **never** hard-code as universal (design pack `C-14`). **Step 3:** PASS. **Commit** `feat(zwds): versioned Four-Transformations table`.

### Task ZWDS-P1-14 — San Fang Si Zheng relations
**REQ:** ZWDS-REQ-009 · **Files:** Create `bazi_engine/zwds/relations.py`; Test `tests/zwds/test_relations.py`.
- **Formulas:** `harmony_1=mod12(p+4)`, `harmony_2=mod12(p+8)`, `opposition=mod12(p+6)`. Geometry only, no benefic/malefic interpretation.
- **Step 1 (test first):** all **12** focus palaces produce the example's relation records (MING@YIN → harmony {WU,XU}, opposition SHEN).
- **Step 2:** implement. **Step 3:** PASS. **Commit** `feat(zwds): San Fang Si Zheng relations (geometry only)`.

### Task ZWDS-P1-15 — Decadal limits
**REQ:** ZWDS-REQ-010 · **Files:** Create `bazi_engine/zwds/decadal.py` (reuse `dayun.direction.resolve_direction_for_request` semantics); Test `tests/zwds/test_decadal.py`.
- **Rule:** first start age = bureau number; each next +10; first range = Ming palace; direction from `explicit` or year-stem-yin/yang+sex; ranges inclusive; `age_reckoning_id="east_asian_nominal.guide-v1"`. Forward = increasing branch index (= decreasing palace `sequence_index`), per the example (MING@YIN age6-15 → FU_MU@MAO age16-25 → …).
- **Step 1 (test first):** the example's 12 forward ranges (FIRE_6, start 6) match exactly; `direction_method="omit"` ⇒ `decadal_limits=null` and request rejects `include_decadal_limits=true`.
- **Step 2:** implement. **Step 3:** PASS. **Commit** `feat(zwds): decadal limits (ruleset candidate)`.

## 1E — Assembly, Fingerprint, Validation, Engine

### Task ZWDS-P1-16 — Ruleset repository + integrity
**REQ:** ZWDS-REQ-011 · **Files:** Create `bazi_engine/zwds/ruleset_repository.py`, and the ruleset dir `bazi_engine/data/zwds/rulesets/zwds.fufire.core-seed.v1/{manifest.json,palace_roles.json,star_catalog.json,bureau_table.json,transformations.json,placement_rules.json,sources.json}`; Test `tests/zwds/test_ruleset_repo.py`.
- **Step 1 (test first):** loader returns a `RulesetRef` with all component ids + **sha256** for star_catalog/transformation_table/calendar_policy/time_policy and the overall `ruleset_sha256`; unknown id → `zwds_ruleset_not_found`; a tampered component file → `zwds_ruleset_integrity_failed`; `source_status="SOURCE_NEEDED"`, `school_label=null`. Mirror `bafe.canonical_json` for deterministic hashing.
- **Step 2:** implement + author the data files (core-seed: MAJOR_14 + GUIDE_AUX_4). **Step 3:** PASS. **Commit** `feat(zwds): immutable hash-locked ruleset repository`.

### Task ZWDS-P1-17 — Chart fingerprint (canonical JSON)
**REQ:** ZWDS-REQ-014 · **Files:** Create `bazi_engine/zwds/trace.py` (or reuse `bafe.canonical_json`); Test `tests/zwds/test_fingerprint.py`.
- **Step 1 (test first):** `chart_fingerprint` is 64-hex, stable across key-order permutations, and changes iff a canonical chart field changes.
- **Step 2:** implement over the canonical chart projection. **Step 3:** PASS. **Commit** `feat(zwds): deterministic chart fingerprint`.

### Task ZWDS-P1-18 — Graph-consistency validation
**REQ:** ZWDS-REQ-015, ZWDS-REQ-012 · **Files:** Create `bazi_engine/zwds/validation.py`; Test `tests/zwds/test_graph_invariants.py`.
- **Step 1 (test first):** every `placement_id` in any palace exists exactly once in `star_placements[]`; each star placed exactly once; palace `branch_id` matches its `sequence_index`; `completeness.missing_families == declared − emitted`; violation raises `zwds_graph_invariant_failed`.
- **Step 2:** implement. **Step 3:** PASS. **Commit** `feat(zwds): star-graph consistency validation`.

### Task ZWDS-P1-19 — Engine orchestrator + schema round-trip
**REQ:** ZWDS-REQ-004…015 · **Files:** Create `bazi_engine/zwds/engine.py` (`compute_zwds_raw(request, ruleset) -> dict`); Test `tests/zwds/test_engine_end_to_end.py`.
- **Step 1 (test first):** the processing order (validation → local-time → effective time → hour+late-Zi → chart-date → lunisolar+rollover → leap → year-cycle → palace/stem/bureau → stars/transformations/relations/decadals → graph validation → fingerprint) runs; output **validates against** `ZwdsRawResponse.schema.json`; `include_trace/include_catalog/include_decadal_limits` toggles honor the schema's `if/then` invariants (null when off); `quality.source_status="SOURCE_NEEDED"`.
- **Step 2:** implement assembly. **Step 3:** PASS. **Commit** `feat(zwds): natal engine orchestrator`.

## 1F/1G — Endpoints

### Task ZWDS-P1-20 — Metadata endpoint
**REQ:** ZWDS-REQ-017 · **Files:** Create `bazi_engine/routers/zwds.py` (metadata route first), `bazi_engine/services/zwds_service.py`; add `Mount(zwds.router, legacy_prefix=None)` to `routers/registry.py` import list + `MOUNTS`; Test `tests/zwds/test_metadata_endpoint.py`.
- **Step 1 (test first, HTTP boundary via `TestClient`):** `GET /v1/metadata/zwds/rulesets/zwds.fufire.core-seed.v1` → 200 with version, all hashes, policy ids, declared families, `source_status`, release status; unknown id → 404 `zwds_ruleset_not_found` in `ErrorEnvelope`. `/v1`-only (no legacy path). Assert on `resp.json()` (per WS-A HTTP-boundary convention).
- **Step 2:** implement router+service+mount. **Step 3:** PASS. **Commit** `feat(zwds): GET /v1/metadata/zwds/rulesets/{id}`.

### Task ZWDS-P1-21 — Calculate endpoint
**REQ:** ZWDS-REQ-016 · **Files:** Modify `routers/zwds.py`, `services/zwds_service.py`; Test `tests/zwds/test_calculate_endpoint.py`.
- **Step 1 (test first, HTTP boundary):** `POST /v1/calculate/zwds` with `request_example_civil.json` → 200, body validates against `ZwdsRawResponse.schema.json`, `Ming=YIN`; missing birth time → `zwds_birth_time_required`; DST gap with `nonexistentTime:error` → 422 with **no birth-instant PII** echoed (assert `resp.text` scrubbed, per WS-A retro); requires API key when `FUFIRE_API_KEYS` set; rate-limited by key. Civil input only (no direct-lunar).
- **Step 2:** implement handler reusing `resolve_local_iso` exactly like `routers/bazi.py`. **Step 3:** PASS. **Commit** `feat(zwds): POST /v1/calculate/zwds`.

### Task ZWDS-P1-22 — OpenAPI + codegen
**REQ:** ZWDS-REQ-019 · **Files:** run `scripts/export_openapi.py`; Test rely on `test_openapi_contract.py`.
- **Step 1:** `python scripts/export_openapi.py` (regenerate `spec/openapi/openapi.json`); **Step 2:** `python scripts/export_openapi.py --check` → drift-free; **Step 3:** `pytest tests/test_openapi_contract.py -q` PASS; ensure the codegen job's `redocly lint` passes. **Commit** `chore(zwds): regenerate OpenAPI for ZWDS endpoints`.

## 1H — GATE-1

### Task ZWDS-P1-23 — Natal golden corpus + practitioner-review gate
**REQ:** ZWDS-REQ-018 · **Files:** Create `tests/zwds/goldens/*.json`, `tests/zwds/test_zwds_golden.py`, `docs/zwds/golden-review.md` (sign-off checklist); update `docs/precision/deviations.md` (DECISION-ZWDS-001 core-seed release).
- **Step 1:** generate goldens covering every policy boundary, every bureau, representative star collisions, every year-stem transformation row; record the `iztro` comparator result as a `crosscheck` (MATCH ≠ historical proof).
- **Step 2 (test):** each golden reproduces byte-stable (fingerprint) under the frozen ruleset.
- **Step 3:** fill `golden-review.md`; **request human practitioner review**. **Commit** `test(zwds): natal golden corpus + release gate`.
- **Acceptance / GATE-1:** practitioner sign-off recorded + release-gate checklist green. **Only then may Phase 2+ start.**

---

# Phase 2 — Signal Extraction  *(GATE-1 required)*

### Task SYN-P2-01 — Neutral semantic ontology (data)
**REQ:** SYN-REQ-001 · **Files:** `bazi_engine/data/synergy/ontology/fufire.semantic-ontology.v1.json` (the 17 domains: agency, resources, expression, structure, pressure, relationships, visibility, material_flow, vocation, mobility, stability, adaptation, conflict, support, recovery, learning, transformation), `bazi_engine/synergy/ontology.py`; Test `tests/synergy/test_ontology.py`.
- **Acceptance:** loader exposes the 17 domain ids + German glosses, hash-locked; ids are FuFirE product terms (documented as non-canonical). TDD: unknown domain → error; hash stable.

### Task SYN-P2-02 — Signal schema + type
**REQ:** SYN-REQ-004 · **Files:** `spec/schemas/synergy/SemanticSignal.schema.json`, `bazi_engine/synergy/signal.py`; Test `tests/synergy/test_signal_schema.py`.
- **Acceptance:** `SemanticSignal` frozen type with `signal_id, system∈{bazi,zwds}, semantic_domain, direction, intensity∈[0,1], temporal_scope, source{...}, confidence∈[0,1], source_status`; validates against schema.

### Task SYN-P2-03 — BaZi signal mapper
**REQ:** SYN-REQ-002 · **Files:** `bazi_engine/synergy/bazi_mapper.py`; Test `tests/synergy/test_bazi_mapper.py`.
- **Acceptance:** consumes an existing `BaziResult` (+ dayun) → `SemanticSignal[]`; deterministic; `source_status="API_VERIFIED"`; **imports `bazi.*` only**, never `zwds.*`. TDD from a fixed BaZi fixture.

### Task SYN-P2-04 — ZWDS signal mapper
**REQ:** SYN-REQ-003 · **Files:** `bazi_engine/synergy/zwds_mapper.py`; Test `tests/synergy/test_zwds_mapper.py`.
- **Acceptance:** consumes a ZWDS raw chart → `SemanticSignal[]`; transformation/palace/network → domains; `source_status` inherited from placements (`SOURCE_NEEDED` for core-seed); **imports `zwds.*` only**. TDD from a Phase-1 golden.

---

# Phase 3 — Synergy Core  *(GATE-1 required)*

### Task SYN-P3-01 — Mapping registry (governed)
**REQ:** SYN-REQ-005 · **Files:** `bazi_engine/data/synergy/mappings/*.json`, `bazi_engine/synergy/mapping_registry.py`; Test `tests/synergy/test_mapping_registry.py`.
- **Acceptance:** each mapping is versioned `{mapping_id, source_system_a/b, patterns, target_domain, relationship∈{ANALOGOUS,COMPLEMENTARY,CONVERGENT,DIVERGENT,UNRELATED,CONTRADICTORY}, confidence, status∈{DRAFT,INTERNAL_REVIEWED,EXPERT_REVIEWED,USER_VALIDATED,DEPRECATED,BLOCKED}, rationale, counterexamples, limitations}`. **`IDENTICAL` between systems is rejected** (test asserts a schema/loader guard). Only `EXPERT_REVIEWED`+ mappings are active in prod.

### Task SYN-P3-02 — Fusion relation detector
**REQ:** SYN-REQ-006 · **Files:** `bazi_engine/synergy/fusion_core.py`; Test `tests/synergy/test_fusion_relations.py`.
- **Acceptance:** given two signal sets + registry → `convergence/complement/divergence` records, or `NO_SAFE_FUSION` when no reviewed mapping links them (no forced sentence). TDD covering each of the four outcomes.

### Task SYN-P3-03 — Confidence model
**REQ:** SYN-REQ-007 · **Files:** modify `fusion_core.py`; Test `tests/synergy/test_confidence.py`.
- **Formula:** `fusion_confidence = min(bazi_conf, zwds_conf, mapping_conf) × independence_factor × temporal_alignment_factor − contradiction_penalty − missing_data_penalty`. Assert: two weak signals never yield a strong fusion; shared-input signals drop `independence_factor`; missing birth time strongly downweights (ZWDS-heavy) fusions; result clamped `[0,1]`.

### Task SYN-P3-04 — `POST /v1/synergy/bazi-zwds` (D-2, D-3)
**REQ:** SYN-REQ-011, SYN-REQ-012, SYN-REQ-008/009 · **Files:** `bazi_engine/routers/synergy.py`, `bazi_engine/services/synergy_service.py`, `spec/schemas/synergy/SynergyResponse.schema.json`, registry mount (`legacy_prefix=None`); Test `tests/synergy/test_synergy_endpoint.py`.
- **Acceptance (HTTP boundary):** orchestrates BaZi + ZWDS (each computed independently, never cross-importing) → signals → fusion; response carries `fusion_id` (content-addressed, D-3), the three ruleset refs+hashes, `semantic_signals`, `themes`, `limitations`, `quality{calculation_status,fusion_status,source_status,human_review_required}`, provenance. **Claim-safety:** every user-facing string carries `claim_type="reflective_hypothesis"` + `limitations`; a block-list test asserts no "beweist/garantiert/dein Schicksal/medical/financial" phrasing escapes. `/v1`-only. Regenerate OpenAPI + drift check.

---

# Phase 4 — BaZodiac Explanation Layer  *(GATE-1 required)*

### Task SYN-P4-01 — Themes projection + dual-perspective composer
**REQ:** SYN-REQ-013, SYN-REQ-016 · **Files:** `bazi_engine/synergy/themes.py`, `bazi_engine/synergy/explanation.py`; Test `tests/synergy/test_themes.py`.
- **Acceptance:** ranks cross-system themes with `{theme_id,title,relation,confidence,bazi_summary,zwds_summary,fusion_summary,reflection_questions[]}`; each theme names which system carries which claim; deterministic ordering. Divergence themes are kept (not discarded).

### Task SYN-P4-02 — `GET /v1/synergy/{fusion_ref}/themes` + evidence view
**REQ:** SYN-REQ-013 · **Files:** modify `routers/synergy.py`; Test `tests/synergy/test_theme_endpoints.py`.
- **Acceptance (HTTP boundary):** `fusion_ref` opaque token (D-3) recomputes deterministically; `.../themes` returns prioritized themes; `.../themes/{theme_id}/evidence` returns `{bazi_evidence[], zwds_evidence[], mapping_rules[], confidence_calculation{}, limitations[]}` making every claim auditable; malformed token → `synergy_ref_invalid`. OpenAPI regen + drift check.

### Task SYN-P4-03 — Reflection prompts + claim-safety pass
**REQ:** SYN-REQ-009 · **Files:** `bazi_engine/synergy/reflection.py`; Test `tests/synergy/test_claim_safety.py`.
- **Acceptance:** reflection questions are open (not verdicts); a fuzz test over generated outputs asserts the block-list never appears; every emitted claim object has `evidence_ids` + `confidence` + `limitations`.

---

# Phase 5 — Temporal Synergy  *(GATE-1 required)*

### Task SYN-P5-01 — Da-Yun × ZWDS decadal aligner
**REQ:** SYN-REQ-014 · **Files:** `bazi_engine/synergy/temporal.py`; Test `tests/synergy/test_temporal.py`.
- **Acceptance:** computes BaZi Da-Yun intervals (existing `dayun`) and ZWDS decadal ranges **separately**, then marks overlapping active domains as *theme windows* (never a synchronized single timeline, never event prediction). TDD: intervals stay independent; overlaps labelled `CONVERGENT/DIVERGENT` with confidence.

### Task SYN-P5-02 — `POST /v1/synergy/bazi-zwds/timeline`
**REQ:** SYN-REQ-014 · **Files:** modify `routers/synergy.py`; Test `tests/synergy/test_timeline_endpoint.py`.
- **Acceptance (HTTP boundary):** returns `periods[]` with `{start,end,active_domains[],bazi_signals[],zwds_signals[],fusion_relation,confidence}`; language is "theme window", not forecast. OpenAPI regen + drift check.

---

# Phase 6 — HeHun / Relationship Synergy  *(Phase 3 + `match/` required)*

### Task SYN-P6-01 — Dyadic synergy over two charts
**REQ:** SYN-REQ-015 · **Files:** `bazi_engine/synergy/hehun.py` (reuse `bazi_engine.match` for BaZi side), `routers/synergy.py`; Test `tests/synergy/test_hehun_synergy.py`.
- **Acceptance:** two persons → BaZi HeHun (existing engine) + ZWDS relationship geometry → shared vs divergent relationship themes; **no score field anywhere** (parity with `match/` D1); requires both-person consent flag (parity with `match/`); reflection-hypothesis claim type only. `POST /v1/synergy/bazi-zwds/hehun`, `/v1`-only. OpenAPI regen + drift check.

---

## Cross-cutting acceptance evidence (run per phase)
```bash
.venv/bin/python -m pytest tests/zwds tests/synergy -q          # phase suites
.venv/bin/python -m pytest -q                                   # full suite, 0 failed
uvx ruff check bazi_engine/ tests/                              # lint clean (E4/E7/E9/F/I/B)
.venv/bin/python -m mypy bazi_engine --ignore-missing-imports   # typecheck
.venv/bin/python scripts/export_openapi.py --check              # OpenAPI drift-free
.venv/bin/python -m pytest tests/test_import_hierarchy.py -q    # engine separation held
```

## Risks and Rollback

| Risk | Mitigation | Rollback |
|------|-----------|----------|
| **Lunisolar leap-month bug** (highest) | Independent boundary corpus (ZWDS-P1-04) is the correctness gate; provider is swisseph-native + deterministic | Feature-flag the calculate endpoint off; ruleset stays `SOURCE_NEEDED`; corpus failures block release |
| Fabricated interpretive certainty | Governance invariants + claim-safety fuzz tests + `source_status` separation; GATE-1 before any fusion | Registry mappings default `DRAFT`/inactive; only `EXPERT_REVIEWED` ship |
| Endpoint/module collision with existing `fusion` | D-2 rename to `synergy` / `/v1/synergy/*`; never touch frozen `/calculate/fusion` | New surfaces are additive `/v1`-only mounts — remove the `Mount(...)` rows to revert |
| Stateful-store creep | D-3 content-addressed `fusion_id`, recompute, no DB | n/a (no persistence introduced) |
| OpenAPI drift / downstream break | Every endpoint task ends with export + `--check`; frozen legacy paths untouched | Revert the endpoint commit; spec regenerates clean |
| CI import failure (native libswe) | Any new engine-importing CI job mirrors the `libswe-dev` apt step | Add the apt step; see memory `fufire-dayun-v1-1-0-and-libswe-ci` |
| ZWDS↔BaZi coupling regression | `test_import_hierarchy.py` enforces separation (ZWDS-P0-03) | Revert the offending import; test fails loudly |

## Traceability (REQ → primary task)
ZWDS-REQ-001→P0-02 · 002→P0-02 · 003→P1-01..04 · 004→P1-05/06 · 005→P1-07/08 · 006→P1-09 · 007→P1-10..12 · 008→P1-13 · 009→P1-14 · 010→P1-15 · 011→P1-16 · 012→P1-18 · 013→P1-19 · 014→P1-17 · 015→P1-18 · 016→P1-21 · 017→P1-20 · 018→P1-23 · 019→P1-22
SYN-REQ-001→P2-01 · 002→P2-03 · 003→P2-04 · 004→P2-02 · 005→P3-01 · 006→P3-02 · 007→P3-03 · 008/009→P3-04/P4-03 · 010→P0-03 · 011→P3-04 · 012→P3-04 · 013→P4-02 · 014→P5-01/02 · 015→P6-01 · 016→P4-01
