# Da-Yun: Real Solar-Year Dates + Interpretation Layer — Implementation Plan

> **For Claude:** Execute task-by-task. Each task is test-first (write/adjust the
> failing test, then the minimal code, then green, then commit). Tasks are ordered;
> a later task assumes earlier ones landed.

**Goal:** Make `/calculate/bazi/dayun` (a) emit real Gregorian decade dates instead of
360-day ritual-year dates, and (b) fill `semantic_summary` (`supports`/`frictions`/`practice`)
from deterministic Ten-God + branch-clash/combine analysis against the natal chart.

**Architecture:** Two independent workstreams sharing one endpoint. **SF** (Solar-Fix)
touches only date placement + current-cycle selection — the astronomical core (pillars,
jieqi anchor, start age, Ten-Gods, 60-jiazi walk) is already evidence-correct and is NOT
touched. **DL** (Deutungslayer) adds a new pure module `bazi_engine/dayun/interpretation.py`
(import Level 4) and rewires the `_semantic_summary` stub. Response JSON **shape** is
unchanged in both — only field *values* / array *contents* change, so the frozen-endpoint
contract (`schemas/calculate/bazi/dayun.response.schema.json`) holds without a schema edit.

**Tech stack:** Python 3.10+, stdlib `datetime` only (no new deps — `python-dateutil` is
deliberately NOT added; calendar-year addition is done by hand). Existing Swiss-Ephemeris
path is reused unchanged.

---

## Non-goals

- **No new response fields.** `Cycle` and `CurrentCycle` are `additionalProperties: false`
  in the schema. Structured branch-relation output (a `branch_relations` object) would need
  a schema bump + OpenAPI review — out of scope. DL encodes interactions as German strings
  inside the existing `supports`/`frictions` arrays.
- **No per-cycle interpretation.** `semantic_summary` lives only on the `current` block in
  the current schema. DL fills only the current decade. Per-cycle Deutung is future work.
- **No favorability / yong-shen (用神) judgment.** Deciding which element is "useful" for a
  chart is subjective and would violate anti-fabrication discipline. DL uses only
  deterministic classical relations (Ten-God bucket + 六冲/六合). No "this is a lucky decade".
- **No 三合 / 六害 / 刑 (three-harmony / six-harm / punishment) in V1.** Only the two
  highest-signal branch relations (六冲 clash, 六合 combine). Note as future.
- **No change to** pillars, jieqi anchor, `start_age` conversion, `relation.py` Ten-Gods,
  `jiazi` walk, direction resolver. Those are already correct (verified live 2026-07-13).
- **No new ruleset file / no `ruleset_id` bump.** Stays `dayun_v1`. The date-model change is
  a bugfix to a latent unit error, documented in the deviation register (SF-5), not a new
  ruleset version.

## Preconditions & known gaps

- Live endpoint returns 200 + schema-valid today; ephemeris available locally (`.venv`).
- Run tests with the project venv: `.venv/bin/python -m pytest ...` — a bare `uv run` spins a
  depless 3.14 env and `python3` is RTK-rewritten to `uv run`. **Gap:** `.venv` currently has
  runtime deps but **no `pytest`** (`No module named pytest`). First action of TASK SF-0.
- **Current bug (SF):** router builds dates as `birth_local_dt + timedelta(days=age*360)`
  (`routers/dayun.py`, the cycle loop) and `current_cycle.py` divides elapsed time by
  `_DAYS_PER_YEAR = 360.0`. Each decade spans 3600 days (9.86 Gregorian yr) not ~3652; drift
  ~52 days/decade, ~1.1 yr off by decade 8 (measured live). `age_start`/`age_end` are ALREADY
  real years (`start_age.decimal_years = life_days/360` from the 3d=1y rule) — do NOT rescale
  them.
- **Current gap (DL):** `_semantic_summary` in `routers/dayun.py` returns a fixed
  `road_metaphor` string + `supports:[] frictions:[] practice:[]` always empty. No branch
  interaction anywhere in the codebase — `match/` explicitly excludes an interaction matrix
  (`pair.py` AC-006b). Must be built fresh.
- `Pillar` (`types.py`) exposes `stem_index`, `branch_index`. `BRANCHES` (`constants.py`) =
  `["Zi","Chou","Yin","Mao","Chen","Si","Wu","Wei","Shen","You","Xu","Hai"]` (index 0..11).
- `test_dayun_current_cycle.py` bakes the 360-day model into two boundary tests
  (`days = 12.86 * 360`) — these MUST be updated by SF (they encode the old unit, not a
  contract). The article-example test (`sequence == 4` for 1987→2026) stays green under both
  models (age ≈ 38.9 real ≈ 39.4 ritual, both inside `[32.86, 42.86)`).

---

## Workstream SF — Real Solar-Year Dates

### SF-0: Restore a runnable test environment
- **Files:** none (env only).
- **Action:** `.venv/bin/python -m pip install -e ".[dev]"` (or `pip install pytest jsonschema`
  into `.venv`). Confirm `.venv/bin/python -m pytest tests/ -k dayun -q` collects.
- **Acceptance:** dayun test subset runs (pass/fail both acceptable — collection must succeed,
  no `ModuleNotFoundError`).

### SF-1: `add_real_years` calendar helper (test-first)
- **REQ:** DY-SF-1.
- **Files:** Create `bazi_engine/dayun/dates.py`. Test: create `tests/test_dayun_dates.py`.
- **Design:**
  ```python
  from datetime import date, datetime, timedelta

  _MEAN_YEAR_DAYS = 365.2425  # Gregorian mean year; used only for the sub-year remainder

  def add_real_years(base: datetime, years: float) -> date:
      """Return the real Gregorian date `years` real years after `base`.

      Whole years are added on the calendar (leap-aware); the fractional remainder
      is added as `frac * 365.2425` days. Feb-29 anchors clamp to Feb-28 in a
      non-leap target year. Decade spans are therefore ~3652-3653 days, not 3600.
      """
      whole = int(years)
      frac = years - whole
      y = base.year + whole
      try:
          anchored = base.replace(year=y)
      except ValueError:      # base is Feb 29, target year not leap
          anchored = base.replace(year=y, day=28)
      return (anchored + timedelta(days=frac * _MEAN_YEAR_DAYS)).date()
  ```
- **Tests to add:** whole-year add (`add_real_years(datetime(1987,7,4,21,30), 10.0)` → `1997-07-04`);
  fractional (`... , 0.5` → `~1988-01-02`, assert within ±1 day of `1987-07-04 + 182 days`);
  decade span is real (`add_real_years(b, 10) - add_real_years(b, 0)` in `[3652, 3653]` days);
  Feb-29 clamp (`datetime(2000,2,29)`, `+1.0` → `2001-02-28`).
- **Acceptance:** `tests/test_dayun_dates.py` green.

### SF-2: Router uses real dates for `date_start`/`date_end` (test-first)
- **REQ:** DY-SF-2.
- **Files:** `bazi_engine/routers/dayun.py` (the `for i in range(req.cycles)` loop). Test:
  extend `tests/test_dayun_endpoint.py`.
- **Change:** replace
  ```python
  date_start = (birth_local_dt + timedelta(days=age_start * 360)).date().isoformat()
  date_end   = (birth_local_dt + timedelta(days=age_end   * 360)).date().isoformat()
  ```
  with
  ```python
  from ..dayun.dates import add_real_years
  date_start = add_real_years(birth_local_dt, age_start).isoformat()
  date_end   = add_real_years(birth_local_dt, age_end).isoformat()
  ```
  Delete the now-stale "360-day ritual year … 3600 calendar days" comment block; replace with
  a one-liner noting decades are real Gregorian years (leap-aware).
- **Tests to add:** for the canonical request (1987-07-04, explicit/forward, 8 cycles), assert
  every cycle's `date_end − date_start` ∈ `[3652, 3653]` days (parse ISO), and assert
  consecutive `date_start[i+1] == date_end[i]` (contiguous decades). Assert `cycles[0].date_start`
  is within ±2 days of `add_real_years(birth, cycles[0].age_start)`.
- **Acceptance:** new asserts green; existing `test_dayun_endpoint.py` structural asserts still
  green; response still schema-valid (`test_response_validates_against_response_schema`).

### SF-3: `current_cycle.select_current` uses the real mean year (test-first)
- **REQ:** DY-SF-3.
- **Files:** `bazi_engine/dayun/current_cycle.py`. Tests: `tests/test_dayun_current_cycle.py`.
- **Change:** `_DAYS_PER_YEAR = 360.0` → `_DAYS_PER_YEAR = 365.2425`. Update the module docstring
  ("360-day-year units" → "real Gregorian mean-year units, consistent with the real decade
  dates emitted by the endpoint"). No signature change (still age-based; `age_start`/`age_end`
  are real years).
- **Tests to update (these encode the OLD unit):**
  - `test_inclusive_lower_bound`: change `timedelta(days=1029.6)` (= `2.86*360`) to
    `timedelta(days=2.86 * 365.2425)`; keep `assert out["sequence"] == 1`.
  - `test_exclusive_upper_bound`: change `days=12.86 * 360` to `days=12.86 * 365.2425`; keep
    the cycle-2 expectation.
  - Leave `test_article_example_returns_cycle_4`, `test_before_first_cycle_returns_none`,
    `test_after_last_cycle_returns_none` unchanged (still green under real year — verify).
  - Update the `# … (360-day)` inline comments to reflect real-year reasoning.
- **Acceptance:** full `tests/test_dayun_current_cycle.py` green; `test_dayun_endpoint.py`
  `test_happy_path_current_set_when_as_of_in_range` still selects exactly one current cycle.

### SF-4: Cross-consistency guard (test-first)
- **REQ:** DY-SF-4.
- **Files:** `tests/test_dayun_endpoint.py` (new test).
- **Change:** none in prod. Add a regression test: for the canonical request with
  `as_of_date` set to the midpoint date of `cycles[3]` (`date_start`..`date_end`), assert
  `current.sequence == 4` and the flagged `is_current` cycle's `[date_start, date_end)`
  brackets `as_of_date`. Locks date-model ↔ current-selection agreement (the core bug class).
- **Acceptance:** test green.

### SF-5: Governance / decision note
- **REQ:** DY-SF-5.
- **Files:** `docs/precision/deviations.md` (append). Optionally a one-line note in
  `CLAUDE.md` Da-Yun mention if present.
- **Change:** append a dated entry (e.g. **DECISION-DAYUN-002 — 2026-07-13**): the Da-Yun
  decade dates previously used a 360-day ritual year (documented as "intentional" in
  `routers/dayun.py`); this is superseded — decade `date_start`/`date_end` now track real
  Gregorian years (leap-aware) because the fields are declared `format: date` and were being
  consumed as real dates, drifting ~1.1 yr by decade 8. `start_age` (3d=1y) and `age_*`
  (real-year decimals) are unchanged. Append-only; do not rewrite history.
- **Acceptance:** entry present; `git log` shows the doc commit.

---

## Workstream DL — Interpretation Layer

### DL-1: Branch-relation core — 六冲 / 六合 (test-first)
- **REQ:** DY-DL-1.
- **Files:** Create `bazi_engine/dayun/interpretation.py`. Test: `tests/test_dayun_interpretation.py`.
- **Design (constants + pure fn):**
  ```python
  from ..constants import BRANCHES  # index 0..11: Zi..Hai

  # 六冲 (Six Clashes): each branch clashes with the one 6 positions away.
  # Zi-Wu, Chou-Wei, Yin-Shen, Mao-You, Chen-Xu, Si-Hai.
  def _clashes(a: int, b: int) -> bool:
      return (a - b) % 12 == 6

  # 六合 (Six Combinations): fixed classical pairs.
  # Zi-Chou, Yin-Hai, Mao-Xu, Chen-You, Si-Shen, Wu-Wei.
  SIX_COMBINE: frozenset[frozenset[int]] = frozenset(
      frozenset(p) for p in [(0, 1), (2, 11), (3, 10), (4, 9), (5, 8), (6, 7)]
  )
  def _combines(a: int, b: int) -> bool:
      return frozenset((a, b)) in SIX_COMBINE

  def branch_interactions(decade_branch_index: int,
                          natal_branches: dict[str, int]) -> dict:
      """Return {'clashes': [pos...], 'combines': [pos...]} where pos ∈
      {'year','month','day','hour'} — the natal positions the decade branch
      clashes with / combines with. Deterministic, self-vs-self excluded is N/A
      (decade branch is not itself natal)."""
  ```
  `natal_branches` = `{"year": p.year.branch_index, "month": ..., "day": ..., "hour": ...}`.
- **Tests to add:** Zi(0) clashes Wu(6) not Chou(1); combine Zi-Chou true, Zi-Wu false; a
  crafted `natal_branches` yields the exact expected `clashes`/`combines` position lists;
  clash relation is symmetric; every branch clashes exactly one other and combines exactly one
  other (partition sanity over 0..11).
- **Acceptance:** `tests/test_dayun_interpretation.py` branch-relation tests green.

### DL-2: `build_semantic_summary` from Ten-God + branch interactions (test-first)
- **REQ:** DY-DL-2.
- **Files:** `bazi_engine/dayun/interpretation.py` (add fn). Test: same test module.
- **Design:** deterministic German string builder — NO favorability verdicts.
  ```python
  # Ten-God → (bucket, German phrase). Buckets: 'support' | 'friction' | 'neutral'.
  _TEN_GOD_BUCKET = {
      "Zheng Yin": ("support", "Direkte Quelle stützt deinen Kern (Lernen, Rückhalt)."),
      "Pian Yin":  ("support", "Indirekte Quelle nährt unkonventionell (Intuition, Nischenwissen)."),
      "Shi Shen":  ("support", "Schöpferische Ausgabe fließt leicht (Ausdruck, Genuss)."),
      "Zheng Cai": ("support", "Direktes Vermögen — stetiger, greifbarer Ertrag."),
      "Bi Jian":   ("neutral", "Gefährte — Gleichrangige, Selbstbehauptung, Teamdynamik."),
      "Zheng Guan":("neutral", "Verantwortung — Struktur, Pflicht, Anerkennung von außen."),
      "Pian Cai":  ("neutral", "Indirektes Vermögen — Chancen, unregelmäßiger Fluss."),
      "Shang Guan":("friction", "Disruptive Ausgabe — Reibung mit Regeln/Autorität, aber Innovationsdruck."),
      "Qi Sha":    ("friction", "Druck/Struktur — Belastung, die zu Disziplin zwingt."),
      "Jie Cai":   ("friction", "Rivale — Konkurrenz um Ressourcen, Wachsamkeit nötig."),
  }
  # practice hint keyed off bucket of the decade's Ten-God (1 line, deterministic).
  _PRACTICE = {
      "support":  "Diese Dekade trägt — nutze den Rückenwind für Aufbau statt Absicherung.",
      "friction": "Diese Dekade fordert — kleine, disziplinierte Schritte schlagen große Sprünge.",
      "neutral":  "Diese Dekade ist gestaltbar — setze bewusst Richtung, sie kippt in keine Extreme.",
  }

  def build_semantic_summary(day_master_stem_index, decade_pillar,
                             natal_branches, relation) -> dict:
      # road_metaphor: keep the existing Jia-Kern-style sentence.
      # supports:  ten_god support-bucket phrase (if any) + one line per branch COMBINE
      #            ("六合 mit der {Palast}-Säule — Bündelung/Unterstützung dort").
      # frictions: ten_god friction-bucket phrase (if any) + one line per branch CLASH
      #            ("六冲 mit der {Palast}-Säule — Aufbruch/Spannung dort").
      # practice:  [ _PRACTICE[bucket_of(relation.ten_god)] ].
  ```
  Palace German names: `year→Jahr (Herkunft)`, `month→Monat (Umfeld/Karriere)`,
  `day→Tag (Selbst/Partnerschaft)`, `hour→Stunde (Nachkommen/Spätphase)`.
- **Tests to add:** a decade Ten-God = `Qi Sha` + a clashing natal branch → `frictions`
  non-empty containing both the Ten-God friction phrase and the `六冲` palace line; a `Shi Shen`
  + combining branch → `supports` has both lines; `practice` always length 1; output keys ==
  `{road_metaphor, supports, frictions, practice}` and all list items are `str`; determinism
  (same input → identical output twice).
- **Acceptance:** builder tests green; output validates against `$defs.SemanticSummary`
  (assert via `jsonschema` on the returned dict in-test).

### DL-3: Wire builder into the router (test-first)
- **REQ:** DY-DL-3.
- **Files:** `bazi_engine/routers/dayun.py`. Test: `tests/test_dayun_endpoint.py`.
- **Change:** delete the `_semantic_summary(day_master_stem_index)` stub; import
  `from ..dayun.interpretation import build_semantic_summary`. In the `current_cycle is not None`
  branch, build `natal_branches` from `bazi_result.pillars` (year/month/day/hour `.branch_index`)
  and call
  ```python
  "semantic_summary": build_semantic_summary(
      day_master_stem_index=day_master_stem_index,
      decade_pillar=current_cycle["pillar"],
      natal_branches={
          "year":  bazi_result.pillars.year.branch_index,
          "month": bazi_result.pillars.month.branch_index,
          "day":   bazi_result.pillars.day.branch_index,
          "hour":  bazi_result.pillars.hour.branch_index,
      },
      relation=current_cycle["relation_to_day_master"],
  ),
  ```
- **Tests to add:** for a birth whose current decade branch is known to clash a natal branch,
  assert `current.semantic_summary.frictions` non-empty; assert the 4 keys + string-typed items
  for the canonical request; assert whole response still schema-valid.
- **Acceptance:** endpoint tests green; `current.semantic_summary` no longer all-empty for the
  crafted case; `test_response_validates_against_response_schema` green.

### DL-4: Import-hierarchy + constants-sync compliance
- **REQ:** DY-DL-4.
- **Files:** `tests/test_import_hierarchy.py` (run; add level entry only if the checker requires
  an explicit map for `dayun.interpretation`), `tests/test_dayun_constants_sync.py` (run —
  `interpretation.py` must not fork a second `BRANCHES`/`STEMS`; it imports from `constants`).
- **Change:** ensure `interpretation.py` imports `BRANCHES` from `..constants` and any stem data
  from existing modules — no duplicated tables. Add module to the hierarchy level map at Level 4
  if the test demands an explicit entry.
- **Acceptance:** `tests/test_import_hierarchy.py` and `tests/test_dayun_constants_sync.py` green.

---

## Final verification (run after all tasks)

```bash
.venv/bin/python -m pytest tests/ -k dayun -q          # full dayun suite green
.venv/bin/python -m pytest tests/test_import_hierarchy.py tests/test_openapi_contract.py -q
.venv/bin/python scripts/export_openapi.py --check      # no OpenAPI drift (dayun body is Dict[str,Any])
```
Plus a live smoke (TestClient, explicit + traditional modes): assert decade span ∈ [3652,3653] days,
contiguous dates, exactly one current cycle, and non-empty `semantic_summary` for a clash/combine birth.

---

## Risks & rollback

| Risk | Mitigation | Rollback |
|------|-----------|----------|
| Downstream consumer depended on the OLD 360-day `date_start`/`date_end` values | Values were provably wrong (drift ~1.1 yr); documented in SF-5 deviation note; shape unchanged so no deserialization break | Revert SF-2 (one loop block) + SF-3 constant; dates return to 360-day |
| `select_current` real-year switch shifts a near-boundary "current decade" by ≤1 day vs the leap-aware date fields | Sub-day; SF-4 test locks date↔current agreement at a mid-decade `as_of`; acceptable and documented | Revert SF-3 constant only |
| DL German copy reads as fabricated fortune-telling | Non-goals bar favorability/yong-shen; only deterministic 六冲/六合 + Ten-God labels; strings are structural, not predictive | Revert DL-3 wiring → `semantic_summary` returns to empty arrays (schema still valid) |
| New `interpretation.py` violates import hierarchy | DL-4 runs `test_import_hierarchy.py`; module imports only Levels 0–1 (`constants`, `types`) | Delete module + revert DL-3 |
| `.venv` missing `pytest` blocks all TDD | SF-0 reinstalls dev extras first | n/a |
| 六合/六冲 index tables transcribed wrong | DL-1 partition-sanity test (each branch clashes/combines exactly one) catches off-by-one | Fix table; tests gate |

## Task summary (stable IDs)

- **SF-0** env: reinstall dev deps into `.venv`
- **SF-1** `dayun/dates.py::add_real_years` (+ test) — DY-SF-1
- **SF-2** router real `date_start`/`date_end` (+ test) — DY-SF-2
- **SF-3** `current_cycle` real mean year (+ update 2 boundary tests) — DY-SF-3
- **SF-4** date↔current consistency regression test — DY-SF-4
- **SF-5** deviation-register decision note — DY-SF-5
- **DL-1** `dayun/interpretation.py` 六冲/六合 core (+ test) — DY-DL-1
- **DL-2** `build_semantic_summary` (+ test) — DY-DL-2
- **DL-3** wire builder into router (+ test) — DY-DL-3
- **DL-4** import-hierarchy + constants-sync compliance — DY-DL-4
