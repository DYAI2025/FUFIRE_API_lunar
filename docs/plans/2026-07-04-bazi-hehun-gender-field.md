# Implementation Plan — gender field for `spouse_star` (male / female / divers)

Status: plan (no code written by this document)
Feature Slug: `bazi-hehun-gender-field`
Date: 2026-07-04
Branch: continues `feature/bazi-hehun-domain-tables` (backend worktree
`/Users/benjaminpoersch/fufireAPI/FuFirE-bazi-hehun`), or a fresh branch off it — see §7.
Resolves: MISSING-007 (docs/governance/bazi-hehun.missing-assumption-blocker-ledger.md)
Depends on: `bazi_engine/match/ten_gods.py` + `ten_gods`/`spouse_star_convention` ruleset
blocks (commit `1f6d29a`, already merged into this branch).

---

## 1. Goal

Let a caller optionally declare each person's gender (`male` | `female` | `divers`) on
`POST /v1/match/bazi-hehun` so `spouse_star` can legitimately flip from `PENDING_TABLES`
to a computed fact — per person, per the sourced narrow convention
(`systematisches_handbuch_der_bazi_hehun_kompatibili.md`, Tabelle 10: male → Direct
Wealth, female → Direct Officer) — without ever fabricating a value for the case the
source doesn't cover (`divers`).

`divers` is the German civil-status third-gender category (law since 2018) — included
because the product serves a German user base, not invented ad hoc. The source table
only defines a convention for `male`/`female`; there is no sourced convention for
`divers`. That gap is a **first-class, honestly-reported outcome**, not an implementation
detail to paper over.

## 2. Non-goals

- Does **not** touch `bazi_engine/routers/bazi.py`'s `BaziRequest` — that model is shared
  with `/calculate/bazi` and `/personalize` (`routers/personalize.py:49`). Adding
  `gender` there would leak an unrelated field into two unrelated, already-live
  endpoints. A match-local wrapper type carries the new field instead (§4, GF-1).
- Does **not** invent a `divers` spouse-star convention. If `gender="divers"` is
  supplied, the response says so explicitly (new open item, §4 GF-3/GF-7) — it never
  silently falls back to `male` or `female`'s rule, and never averages/blends the two.
- Does **not** flip the production feature flag (`VITE_FEATURE_HEHUN` stays whatever it
  is today — CAN-015 governs that separately). This plan is additive-schema work only.
- Does **not** touch `day_master_strength` or `yong_shen` — still blocked by MISSING-003
  (no source at all, per CONTRA-DOMAIN-TABLES-002), untouched by this plan.
- Does **not** decide the privacy/consent question for collecting gender (§3, gate).
  That is a precondition to implementing past GF-1, not something an agent decides
  unilaterally — same discipline as OQ-001 gating the original launch.

## 3. Preconditions and known gaps

**Hard precondition — new gate, must resolve before GF-3 onward:**

- **OQ-004 (new, open):** collecting gender — especially `divers`, which can reveal
  transgender/intersex status — is a new, more sensitive data-collection point than the
  birth data already gated by consent (D5/MISSING-004/OQ-001). Before shipping the field
  as *live* (flag-ON, real callers), the user must decide: (a) does the existing
  `second_person_consent_confirmed` copy cover this, or does the consent text need an
  explicit gender-purpose line; (b) should `gender` apply to consent-requiring
  `person_b` only, both persons, or is it symmetric; (c) is gender persisted/logged
  anywhere the existing hash-only logging discipline (AC-013d) doesn't already cover.
  **GF-1 (schema-only, flag stays OFF, no real traffic) may proceed without this** — it's
  the same "build complete, flag OFF" posture already used for the whole feature
  (CONTRA-LAUNCH-001 Option A). GF-3 onward (wiring real computation + eventually
  flipping the flag) must not proceed past a flag-OFF build until OQ-004 is resolved.

**Verified at code level, this planning pass:**

| Fact | Evidence |
|---|---|
| `BaziRequest` is a shared OpenAPI component (bazi.py + match.py + personalize.py) | `bazi_engine/routers/bazi.py:38`, `match.py:86`, `personalize.py:49` — comment at `bazi.py:68` explicitly says "keep a single BaziRequest OpenAPI component for the B2B/contract tests" |
| `MatchRequest.person_a`/`person_b` currently typed `BaziRequest` directly | `bazi_engine/routers/match.py:184-189` |
| `DerivedFieldStatus` (individual.py) carries **no value field at all** by design — the anti-fabrication guard | `bazi_engine/match/individual.py:75-105`; `__post_init__` rejects any status other than `PENDING_TABLES`/`NEEDS_DOMAIN_REVIEW` |
| `_DERIVED_FIELD_SPECS` currently produces exactly 3 stubs: `day_master_strength`, `yong_shen`, `spouse_star` | `bazi_engine/match/individual.py:51-66` (post commit `1f6d29a`) |
| `spouse_star`'s blocker is now MISSING-007 (gender field absent), not a table gap | same file, same commit |
| Ten-Gods computation + narrow spouse-star convention are shipped and tested | `bazi_engine/match/ten_gods.py`, `spec/rulesets/standard_bazi_2026.json` (`ten_gods`, `spouse_star_convention`), `tests/test_match_ten_gods.py` |
| Wu-Xing ledger already carries every visible+hidden stem with pillar + source label | `bazi_engine/match/types.py:105-118` `WuxingLedgerEntry`; built by `bazi_engine/match/normalize.py:build_wuxing_ledger` — this is what a per-chart spouse-star-occurrence scan iterates over, no new astronomy needed |
| D3's `FORBIDDEN_MATRIX_SUBSTRINGS` guard bars any property/field named with a `ten_gods` substring anywhere in the response schema | `tests/test_match_schema.py:54` — **binding naming constraint on every new field this plan adds** (§4, cross-cutting) |
| `ruleset_version` is pinned `"1.0.0"` in unrelated product-wide tests | `tests/test_bazi_derivation_trace_typed.py`, `tests/test_match_schema.py`, `tests/test_personalize_endpoint.py` — do not bump it for this plan either |
| No test asserts `BaziRequest` itself lacks a `gender` field today | none found — GF-1 should add one (regression lock, §4) |

**Known gaps carried into this plan (not closed by it):**

- MISSING-003 (DMS/Yong-Shen source tables) — still open, untouched.
- day_cycle_anchor citation — still open, untouched (CONTRA-DOMAIN-TABLES-002).
- OQ-004 (this plan's own new gate, above) — must be resolved before GF-3+.
- No sourced `divers` spouse-star convention exists anywhere — will not exist after
  this plan either, unless the user supplies one (mirrors the MISSING-003 pattern:
  the gap is reported, not invented).

---

## 4. Task list

### GF-1 — Schema: match-local person model with optional `gender`

- **Related:** REQ-005 (individual analysis), MISSING-007.
- **Files:** `bazi_engine/routers/match.py` (new `MatchPersonInput(BaziRequest)` model;
  change `MatchRequest.person_a`/`person_b` type from `BaziRequest` to
  `MatchPersonInput`); no changes to `bazi_engine/routers/bazi.py`.
- **Design:**
  ```python
  class MatchPersonInput(BaziRequest):
      """BaziRequest + an OPTIONAL, match-local gender declaration.

      Deliberately NOT added to BaziRequest itself (shared with /calculate/bazi
      and /personalize) -- see plan docs/plans/2026-07-04-bazi-hehun-gender-field.md.
      Optional and defaulted to None: omitting it is fully backward-compatible
      with every existing caller.
      """
      gender: Optional[Literal["male", "female", "divers"]] = Field(
          None,
          description=(
              "Optional self-declared gender, used ONLY to select which Ten-God "
              "the sourced spouse-star convention designates for this person "
              "(Tabelle 10: male -> Direct Wealth, female -> Direct Officer). "
              "'divers' is accepted (German civil-status third-gender category) "
              "but has NO sourced convention -- supplying it does not compute a "
              "spouse star; the response says so explicitly, honestly, not "
              "silently falling back to male/female's rule."
          ),
      )
  ```
- **Tests to add:** `tests/test_match_schema.py` — (a) `gender` accepts `"male"`,
  `"female"`, `"divers"`; (b) an invalid value (e.g. `"other"`) is a 422; (c) omitting
  `gender` still constructs a valid request (backward compatibility); (d) **regression
  lock** — a new test asserting `"gender" not in` `BaziRequest`'s own JSON schema
  properties (fails loudly if someone "helpfully" merges the field upstream later).
- **Acceptance evidence:** all four tests green; `python scripts/export_openapi.py
  --check` clean after a real regen (not `--check` alone — the schema DOES change here,
  first genuine drift since the ruleset-only commit).

### GF-2 — Privacy/consent gate (USER DECISION, not agent-decided)

- **Related:** OQ-004 (§3).
- **No files changed.** Present the three OQ-004 sub-questions to the user; record the
  answer in `docs/governance/bazi-hehun.missing-assumption-blocker-ledger.md` as a new
  `DECISION-00x` entry, same format as `DECISION-001`..`003`.
- **Gate:** GF-3 onward does not start implementation until this decision is recorded.
  GF-1 (schema-only, additive, flag stays OFF) may ship independently before this gate
  clears — same posture as the rest of this feature pre-launch.

### GF-3 — Response type: split `spouse_star` out of the value-less `DerivedFieldStatus`

- **Related:** REQ-005, AC-005c (fabrication guard), MISSING-007/008.
- **Design decision (recommended, needs confirmation before coding — flag this
  explicitly to the user, do not silently pick):** do **not** add a `value` field to
  the shared `DerivedFieldStatus` type. `day_master_strength` and `yong_shen` still have
  zero source (MISSING-003) and must stay permanently value-less — widening the shared
  type's contract for one field's sake risks weakening the guard for the other two.
  Instead, introduce a **new, dedicated type** for `spouse_star` only (mirrors how
  `SpousePalaceFacts` already splits `position_source_status` from `source_status`
  rather than overloading one field):

  ```python
  @dataclass(frozen=True)
  class SpouseStarOccurrence:
      """One stem in the chart that IS the person's convention god (or its
      disruption-signal counterpart) -- a located fact, never a count/score."""
      pillar: str            # "year" | "month" | "day" | "hour"
      source: StemSource     # visible / hidden_principal / hidden_central / hidden_residual
      stem: str
      role: Literal["primary_convention_god", "disruption_signal_god"]

  @dataclass(frozen=True)
  class SpouseStarResult:
      """Per-person spouse-star result (MISSING-007/008-aware, AC-005c-safe).

      Exactly one of these holds, enforced by __post_init__:
      - gender is None                       -> status PENDING_TABLES,  blocked_by="GENDER_NOT_PROVIDED", occurrences=()
      - gender == "divers"                   -> status PENDING_TABLES,  blocked_by="MISSING-008",          occurrences=()
      - gender in ("male", "female")          -> status CALCULATED,     blocked_by="",                     occurrences=(...)
      A CALCULATED status with an empty occurrences tuple IS valid (the
      convention god simply doesn't appear in this chart) -- that is a real
      computed fact, not a fabricated placeholder.
      """
      gender_used: Optional[Literal["male", "female", "divers"]]
      source_status: SourceStatus
      confidence: float
      blocked_by: str
      occurrences: Tuple[SpouseStarOccurrence, ...]
  ```
  `IndividualAnalysis.derived_fields` shrinks to exactly `day_master_strength` +
  `yong_shen`; `IndividualAnalysis` gains a new top-level `spouse_star: SpouseStarResult`
  field.
  **Naming constraint (binding, from §3):** nothing here — type, field, or dataclass
  name — may contain the substring `ten_gods` (case-insensitive) anywhere it reaches
  the response schema; `FORBIDDEN_MATRIX_SUBSTRINGS` in `tests/test_match_schema.py`
  will fail loudly and correctly if violated. `SpouseStarOccurrence`/`SpouseStarResult`
  as named above are clear of it.
- **Files:** `bazi_engine/match/individual.py` (new types + `_build_spouse_star`
  replacing the `spouse_star` entry in `_DERIVED_FIELD_SPECS`), `bazi_engine/match/
  ten_gods.py` (no change — already reusable), `bazi_engine/routers/match.py` (new
  `SpouseStarOccurrenceModel`/`SpouseStarModel`; `IndividualAnalysisModel` gains
  `spouse_star`, `derived_fields` shrinks to 2 expected entries).
- **Tests to add/update:**
  - `tests/test_match_individual_analysis.py::test_dms_yongshen_fields_carry_source_status_and_confidence`
    — narrow the derived-field set assertion to `{"day_master_strength", "yong_shen"}`;
    keep the "no verified-looking status" + "no value field" guard for exactly those two.
  - New `tests/test_match_individual_analysis.py::test_spouse_star_gender_states` (or a
    new file) covering all three states: no gender, `divers`, `male`/`female` with a
    real computed occurrence list, cross-checked against `tests/test_match_ten_gods.py`'s
    already-validated Ten-God table (reuse Person A/B fixtures with a **synthetic,
    explicitly-test-only** gender annotation — the source docs never state either
    real person's gender, so the test must not imply they do).
  - Regression: `DerivedFieldStatus.__post_init__` still rejects `CALCULATED` for
    `day_master_strength`/`yong_shen` (existing test already covers this — rerun, don't
    weaken it).
- **Acceptance evidence:** full match test suite green in both SWIEPH and MOSEPH modes;
  `ruff`/`mypy` clean; `export_openapi.py --check` clean after regen.

### GF-4 — Engine computation: locate convention-god occurrences across the whole chart

- **Related:** REQ-005, ten_gods table (already shipped).
- **Design:** iterate the person's already-built `WuxingLedgerEntry` tuple (visible +
  hidden stems, all 4 pillars — `normalize.build_wuxing_ledger`), compute each entry's
  Ten-God label via `ten_gods.ten_god_for_stems(ruleset, day_master, entry.stem)`, and
  classify: label == convention's primary god (from `spouse_star_convention.male`/
  `.female`) → `primary_convention_god`; label == the same convention's
  `disruption_signal.god` → `disruption_signal_god`; otherwise skip. Report every
  match as a `SpouseStarOccurrence` (pillar + source + stem + role) — a located,
  non-numeric fact, never a count/score (D1 stays intact: no "3 wealth stars = high
  score" framing anywhere, not even informally in a description string).
- **Files:** `bazi_engine/match/individual.py` (new pure helper, no I/O beyond the
  ruleset already loaded).
- **Tests:** unit tests directly on the helper (deterministic, small fixture charts)
  plus the GF-3 integration test above.
- **Acceptance evidence:** occurrence lists match hand-computed expectations for at
  least 2 synthetic charts (one with zero occurrences — must not error or omit the
  field, just report an empty tuple under CALCULATED).

### GF-5 — Contract-test sweep (existing guards must still pass, unmodified in intent)

- **Related:** D1 (no score), D3 (no matrix), D4 (no LLM-readiness), AC-009d (no PII
  echo in errors).
- **Files (read/verify, edit only if a NEW field trips an existing guard):**
  `tests/test_match_score_absence.py`, `tests/test_match_raw_blocks.py`,
  `tests/test_match_errors.py`, `tests/test_match_privacy.py`.
- **Specific checks:** the recursive score-key walk still finds nothing forbidden; the
  blocked-language lexical scan still finds nothing in any new description string
  (careful with the `SpouseStarResult` docstrings/Field descriptions above — no
  "guaranteed"/"perfect match"/relationship-quality adjectives); a malformed or
  `divers`-only request still error-contracts correctly; no raw gender value appears in
  any 4xx/5xx error body if a request fails for an unrelated reason (gender isn't birth
  data, but treat it with the same "never echo request internals in errors" discipline).
- **Acceptance evidence:** all four files pass unmodified, OR modified with a documented
  reason (new field name added to a lexicon list, etc.) — no silent weakening of any
  assertion.

### GF-6 — Full verification + snapshot rebaseline

- **Files:** `tests/snapshots/swieph/*.json`, `tests/snapshots/moseph/*.json` (all 4
  match snapshot files WILL drift — `IndividualAnalysis`'s shape genuinely changes,
  unlike the GF-schema-only ruleset commit).
- **Commands:**
  ```
  pytest -q                                                    # SWIEPH default
  EPHEMERIS_MODE=MOSEPH pytest tests/test_match_determinism.py -q
  UPDATE_SNAPSHOTS=1 pytest tests/test_match_determinism.py::test_fixture_snapshot_stability_per_ephemeris_mode -q   # both modes, review diff before commit
  ruff check bazi_engine/ tests/
  mypy bazi_engine --ignore-missing-imports
  python scripts/export_openapi.py            # REGENERATE (real schema change, not just --check)
  python scripts/export_openapi.py --check     # confirm clean after regen
  ```
- **Acceptance evidence:** every command clean; snapshot diffs reviewed and contain
  ONLY the expected new/changed fields (same discipline as commit `1f6d29a`'s 4-line
  diffs — if a snapshot diff is larger than expected, stop and investigate before
  committing, don't rubber-stamp `UPDATE_SNAPSHOTS=1`).

### GF-7 — Governance close-out

- **Files:** `docs/governance/bazi-hehun.missing-assumption-blocker-ledger.md`,
  `docs/reality/bazi-hehun.evidence.jsonl`.
- Mark MISSING-007 RESOLVED (schema field shipped + wired).
- Add MISSING-008: "No sourced spouse-star convention for `divers`/non-binary gender
  in either reference doc — supplying `gender=\"divers\"` reports this explicitly
  (`blocked_by=\"MISSING-008\"`), never falls back to male/female's rule." Impact:
  blocks `spouse_star` CALCULATED status for `divers` specifically; does not block
  anything else.
  Record the GF-2/OQ-004 decision as `DECISION-00x` (whatever number is next).
- Add an `integration-fake` evidence-ledger entry per the usual pattern (this plan's
  evidence class starts there, same as the rest of REQ-005, until a T22-style
  real-boundary smoke is run against a deployed build).

---

## 5. Risks and rollback

| Risk | Mitigation |
|---|---|
| `gender` accidentally leaks into `/calculate/bazi` or `/personalize` later (someone merges `MatchPersonInput`'s field back into shared `BaziRequest` "for consistency") | GF-1's regression-lock test (`"gender" not in BaziRequest schema`) fails loudly if this happens |
| Splitting `spouse_star` out of `DerivedFieldStatus` weakens the fabrication guard for `day_master_strength`/`yong_shen` | GF-3 explicitly keeps `DerivedFieldStatus` untouched and value-less; existing `__post_init__` rejection test reruns unmodified |
| `divers` silently computed via the `male` or `female` rule by an implementer in a hurry | GF-3's `SpouseStarResult.__post_init__` invariant makes `CALCULATED` + `gender_used="divers"` structurally impossible, same pattern as the existing guard |
| New field trips `FORBIDDEN_MATRIX_SUBSTRINGS` (`ten_gods` substring ban, D3) | Naming constraint called out explicitly in GF-3; `SpouseStarOccurrence`/`SpouseStarResult` chosen to avoid it; test suite would catch a violation immediately regardless |
| Privacy/consent question (OQ-004) skipped under time pressure | GF-2 is a hard, separately-called-out gate before GF-3; GF-1 alone is safe to ship (schema-only, flag OFF, no real computation) |
| Snapshot rebaseline done carelessly (`UPDATE_SNAPSHOTS=1` blindly accepted) | GF-6 requires reviewing the diff size/content before commit, same as commit `1f6d29a` |
| `ruleset_version` bumped unnecessarily, breaking unrelated product-wide tests | Not needed for this plan (no new ruleset keys) — if a future task DOES add ruleset keys, repeat the "additive only, no version bump" discipline from `1f6d29a` |

**Rollback:** every task here is additive (new optional field, new type, new ruleset-
adjacent code) and confined to the `bazi-hehun` match feature; the flag stays OFF in
production throughout. A single `git revert` of the implementing commit(s) is clean —
no other endpoint or shared model is touched. If OQ-004 resolves unfavorably (e.g. "do
not collect gender at all"), GF-1 can be revered on its own before GF-3+ ever starts.

## 6. Traceability

| Task | REQ/AC | Ledger item touched |
|---|---|---|
| GF-1 | REQ-005 | MISSING-007 (partial: schema shipped) |
| GF-2 | — (process gate) | OQ-004 (new) |
| GF-3 | REQ-005, AC-005b/c | MISSING-007 (resolved), MISSING-008 (new) |
| GF-4 | REQ-005 | — |
| GF-5 | D1, D3, D4, AC-009d | — (regression only) |
| GF-6 | AC-014b (snapshot stability) | — |
| GF-7 | — (governance) | MISSING-007 closed, MISSING-008 opened, DECISION-00x added |

## 7. Branch/worktree note

This plan's tasks can land as further commits on `feature/bazi-hehun-domain-tables`
(current HEAD `1f6d29a`) since nothing here conflicts with that commit's content — or
on a fresh branch off it if the user prefers to keep the Ten-Gods-table commit
separately mergeable from the gender-field work. No preference encoded here; ask before
GF-1 lands if it matters for the merge/PR strategy.
