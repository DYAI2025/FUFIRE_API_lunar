# FBP-02-001 Review-Fix Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Address all findings from the `/code-review-ai-ai-review` pass on commit `5d7009a` (FBP-02-001 — ruleset-driven day-cycle offset). Four small, independently-commit-able fixes; one explicitly deferred.

**Architecture:** Each task is a contained edit + TDD where applicable. Three tasks touch `bazi_engine/bazi_rules.py`, one is doc-only (`CLAUDE.md`). No production-behavior change for any task — pillars stay bit-identical (verified by `tests/test_regression_v1_compatibility.py`).

**Tech Stack:** Python 3.10+, pytest. Tests run via `uv run python -m pytest …`.

**Findings being addressed:**

| ID | Title | Severity | Type | Commit |
|---|---|---|---|---|
| M-A2 | Defensive: `day_cycle_anchor: None` should raise ValueError, not AttributeError | MEDIUM | code+test | 1 |
| L-A1 | Align `anchor_jdn` typing leniency with `bafe.ruleset_loader.day_cycle_anchor_status` (accept `float.is_integer()`) | LOW | code+test | 2 |
| M-A1 | `bazi_rules.py` module docstring incorrectly claims "Level 3.5"; CLAUDE.md hierarchy section doesn't reflect `bafe.ruleset_loader` carve-out | MEDIUM | docs | 3 |
| L-A3 | `CLAUDE.md` "Day Pillar Calibration" paragraph still treats `DAY_OFFSET = 49` as source of truth after FBP-02-001 | LOW | docs | 3 (combined) |
| L-A2 | `sexagenary_day_index_from_date(offset: int = DAY_OFFSET)` default arg still references the constant | LOW | DEFERRED — see §"Out of scope" |

**Pre-flight (already verified):**
- `bafe/ruleset_loader.py:101-104` accepts `float.is_integer()` for `anchor_jdn`.
- `bazi_engine/bazi_rules.py:54-58` currently has the `day_cycle_anchor: None` AttributeError trap.
- `CLAUDE.md` line ~145 has the stale `DAY_OFFSET = 49` paragraph.
- Working tree clean at start of this plan; HEAD = `5d7009a`.

---

## Task 1 — M-A2: Defensive `day_cycle_anchor: None` check

**Why:** A ruleset with `"day_cycle_anchor": null` passes the `if "day_cycle_anchor" not in ruleset` guard (key exists) but then `anchor.get(...)` raises `AttributeError: 'NoneType' object has no attribute 'get'`. Reader sees a stack trace, not a helpful error.

**Files:**
- Modify: `bazi_engine/bazi_rules.py` (in `day_offset_from_ruleset`)
- Modify: `tests/test_bazi_rules.py` (add one test)

### Step 1 — Write the failing test

Append to `tests/test_bazi_rules.py`:

```python
def test_day_offset_rejects_null_anchor():
    """A ruleset with day_cycle_anchor explicitly null must raise a
    clean ValueError, not an AttributeError from accessing .get on None.
    """
    fake = {"day_cycle_anchor": None}
    with pytest.raises(ValueError, match="day_cycle_anchor"):
        day_offset_from_ruleset(fake)


def test_day_offset_rejects_non_dict_anchor():
    """Anchor must be a dict; lists/strings/ints get a clean error."""
    for bad_value in ([], "JDN", 2419451):
        fake = {"day_cycle_anchor": bad_value}
        with pytest.raises(ValueError, match="day_cycle_anchor"):
            day_offset_from_ruleset(fake)
```

### Step 2 — Run; expect RED

```bash
uv run python -m pytest tests/test_bazi_rules.py::test_day_offset_rejects_null_anchor tests/test_bazi_rules.py::test_day_offset_rejects_non_dict_anchor -q
```

Expected: both fail with `AttributeError: 'NoneType' object has no attribute 'get'` (or similar for the non-dict cases).

### Step 3 — Implement the defensive check

In `bazi_engine/bazi_rules.py`, modify the block at lines 54-58 from:

```python
    if "day_cycle_anchor" not in ruleset:
        raise KeyError(
            "ruleset has no 'day_cycle_anchor' — cannot derive day offset"
        )
    anchor = ruleset["day_cycle_anchor"]
```

to:

```python
    if "day_cycle_anchor" not in ruleset:
        raise KeyError(
            "ruleset has no 'day_cycle_anchor' — cannot derive day offset"
        )
    anchor = ruleset["day_cycle_anchor"]
    if not isinstance(anchor, dict):
        raise ValueError(
            "day_cycle_anchor must be a dict; got "
            f"{type(anchor).__name__}"
        )
```

### Step 4 — Run; expect GREEN

```bash
uv run python -m pytest tests/test_bazi_rules.py -q
```

Expected: 13 passed (was 11; the two new tests now green).

### Step 5 — Commit

```bash
git add bazi_engine/bazi_rules.py tests/test_bazi_rules.py
git commit -m "$(cat <<'EOF'
fix(bazi-rules): defensive ValueError on null/non-dict day_cycle_anchor (M-A2)

A ruleset with `"day_cycle_anchor": null` (or a non-dict value) was
crashing with `AttributeError: 'NoneType' object has no attribute 'get'`
because the key-presence check passed but the value wasn't a dict.
Tighten to an explicit `isinstance(anchor, dict)` guard that surfaces
a clean ValueError naming the field.

Refs: /code-review-ai-ai-review finding M-A2 on commit 5d7009a.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 2 — L-A1: Accept `float.is_integer()` for `anchor_jdn`

**Why:** `bafe/ruleset_loader.py:101-104::day_cycle_anchor_status` accepts a float `anchor_jdn` when `.is_integer()`. The new helper rejects floats outright. Two helpers reading the same field with different leniency rules is a maintenance trap. Align with the existing loader.

**Files:**
- Modify: `bazi_engine/bazi_rules.py` (in `day_offset_from_ruleset`)
- Modify: `tests/test_bazi_rules.py` (add one test)

### Step 1 — Write the failing test

Append to `tests/test_bazi_rules.py`:

```python
def test_day_offset_accepts_integer_valued_float_anchor_jdn():
    """For consistency with bafe.ruleset_loader.day_cycle_anchor_status,
    a float anchor_jdn that is integer-valued (e.g. 2419451.0) is
    accepted. Truly fractional values still raise ValueError.
    """
    ok = {
        "day_cycle_anchor": {
            "anchor_jdn": 2419451.0,
            "anchor_sexagenary_index_0based": 0,
            "anchor_type": "JDN",
            "anchor_verification": "unverified",
        },
    }
    assert day_offset_from_ruleset(ok) == 49

    bad = {
        "day_cycle_anchor": {
            "anchor_jdn": 2419451.5,
            "anchor_sexagenary_index_0based": 0,
            "anchor_type": "JDN",
            "anchor_verification": "unverified",
        },
    }
    with pytest.raises(ValueError, match="integer"):
        day_offset_from_ruleset(bad)
```

### Step 2 — Run; expect RED

```bash
uv run python -m pytest tests/test_bazi_rules.py::test_day_offset_accepts_integer_valued_float_anchor_jdn -q
```

Expected: fails on the first branch (2419451.0 rejected by `isinstance(int)`).

### Step 3 — Implement the leniency

In `bazi_engine/bazi_rules.py`, modify the JDN coercion block. Replace:

```python
    jdn = anchor.get("anchor_jdn")
    sex_idx = anchor.get("anchor_sexagenary_index_0based")
    if not isinstance(jdn, int) or not isinstance(sex_idx, int):
        raise ValueError(
            "day_cycle_anchor must declare integer "
            "'anchor_jdn' and 'anchor_sexagenary_index_0based'"
        )
```

with:

```python
    jdn = anchor.get("anchor_jdn")
    sex_idx = anchor.get("anchor_sexagenary_index_0based")

    # Match bafe.ruleset_loader.day_cycle_anchor_status leniency: a
    # float JDN with no fractional part is accepted and narrowed to
    # int. Truly fractional values raise.
    if isinstance(jdn, float) and jdn.is_integer():
        jdn = int(jdn)
    if isinstance(sex_idx, float) and sex_idx.is_integer():
        sex_idx = int(sex_idx)

    if not isinstance(jdn, int) or isinstance(jdn, bool) \
       or not isinstance(sex_idx, int) or isinstance(sex_idx, bool):
        raise ValueError(
            "day_cycle_anchor must declare integer "
            "'anchor_jdn' and 'anchor_sexagenary_index_0based' "
            "(integer-valued float accepted; fractional rejected)"
        )
```

Note the `isinstance(x, bool)` clauses — Python's `True`/`False` are `int` subclasses, and we don't want a `bool` anchor_jdn to slip past.

### Step 4 — Run; expect GREEN

```bash
uv run python -m pytest tests/test_bazi_rules.py -q
```

Expected: 14 passed (was 13 after Task 1; the new test now green).

### Step 5 — Commit

```bash
git add bazi_engine/bazi_rules.py tests/test_bazi_rules.py
git commit -m "$(cat <<'EOF'
fix(bazi-rules): align anchor_jdn typing leniency with ruleset_loader (L-A1)

bafe.ruleset_loader.day_cycle_anchor_status() accepts a float
anchor_jdn that is integer-valued (line 101-104). The new helper
in bazi_rules.py rejected floats outright. Aligning the two
prevents a maintenance trap where the same field gets two
different validation rules at different read sites.

Adds an isinstance(_, bool) guard while at it — bool is an int
subclass in Python and `True` would otherwise sneak past the
narrowed int check.

Refs: /code-review-ai-ai-review finding L-A1 on commit 5d7009a.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 3 — M-A1 + L-A3: Doc accuracy (combined)

**Why:** Two stale documentation issues in adjacent areas. Fold into one commit since both are doc-only.

- **M-A1:** `bazi_engine/bazi_rules.py:14-23` module docstring claims "Level 3.5"; CLAUDE.md's module hierarchy puts `bafe/` at Level 5, so the upward `bazi.py → bafe.ruleset_loader` import (pre-existing) and my new `bazi_rules.py → bafe.ruleset_loader` import are both technically violations of the documented top-down rule.
- **L-A3:** CLAUDE.md "Day Pillar Calibration" section still says `DAY_OFFSET = 49` is the source of truth. After FBP-02-001 the ruleset is authoritative; CLAUDE.md should mention `bazi_rules.day_offset_from_ruleset`.

**Files:**
- Modify: `bazi_engine/bazi_rules.py` (module docstring at top)
- Modify: `/Users/benjaminpoersch/Projects/codebase/FuFirE/CLAUDE.md` (Module Hierarchy + Day Pillar Calibration sections)

No tests; doc-only changes.

### Step 1 — Update `bazi_rules.py` module docstring

In `bazi_engine/bazi_rules.py`, replace the lines:

```
Module hierarchy: depends on ``bazi_engine.bafe.ruleset_loader`` for
``load_ruleset`` and is imported by ``bazi_engine.bazi``. The existing
``bazi.py → bafe.ruleset_loader`` import already crosses level lines;
this module follows the same precedent. If the hierarchy gets
re-tightened later, both this module and ruleset_loader would move
together.
```

with:

```
Module hierarchy note: this module imports
``bazi_engine.bafe.ruleset_loader``, which is technically an upward
import per the strict Level-3-only rule in CLAUDE.md. The convention
followed here (and pre-existing in ``bazi.py``) treats
``bafe.ruleset_loader`` as a pure data-loader living *logically* at
the same level as ``bazi.py`` itself — it has no side-effecting
business logic and no router/service dependencies. CLAUDE.md's
"Module Hierarchy" section has a carve-out noting the same. If
``bafe`` ever gains levels-mixed contents, the loader should move
to its own top-level module.
```

### Step 2 — Update CLAUDE.md

In `/Users/benjaminpoersch/Projects/codebase/FuFirE/CLAUDE.md`, in the "Module Hierarchy" section, append a one-line carve-out note after the existing Level 5 description:

```
> **Carve-out:** ``bafe.ruleset_loader`` is a pure data-loader (JSON
> read + typed accessors, no side effects). ``bazi.py`` and
> ``bazi_rules.py`` import from it despite the nominal Level-5
> placement; logically it sits at Level 3. ``tests/test_import_hierarchy.py``
> does not enforce a violation for this import.
```

And in the "Day Pillar Calibration" section, replace:

```python
DAY_OFFSET = 49  # in constants.py — DO NOT MODIFY unless recalibrating
```

with:

```python
# Pre-FBP-02-001 source of truth (kept as a Phase-1 baseline reference):
DAY_OFFSET = 49  # in constants.py

# FBP-02-001 (Phase 2) — the canonical engine path now derives the
# offset from the ruleset's day_cycle_anchor:
from bazi_engine.bazi_rules import day_offset_from_ruleset, load_default_ruleset
calculated_offset = day_offset_from_ruleset(load_default_ruleset())
# yields 49 for the shipped standard_bazi_2026 ruleset; will change
# automatically when FBP-02-002 verifies/corrects the anchor.
```

### Step 3 — Verify no test breakage

(There shouldn't be any — these are doc files.)

```bash
uv run python -m pytest tests/test_bazi_rules.py tests/test_regression_v1_compatibility.py -q
```

Expected: same pass count as before this task.

### Step 4 — Commit

```bash
git add bazi_engine/bazi_rules.py CLAUDE.md
git commit -m "$(cat <<'EOF'
docs(bazi-rules): correct module-hierarchy note + DAY_OFFSET stale paragraph (M-A1, L-A3)

Two related documentation fixes from the FBP-02-001 review:

M-A1: bazi_rules.py module docstring claimed "Level 3.5" — not a
thing in CLAUDE.md's hierarchy. Rewrite to honestly acknowledge the
pre-existing upward import from bafe.ruleset_loader as a documented
carve-out (the loader is a pure data-reader; logically Level 3).

L-A3: CLAUDE.md "Day Pillar Calibration" still described
`DAY_OFFSET = 49` as the canonical source. Post-FBP-02-001 the
canonical path is `day_offset_from_ruleset(load_default_ruleset())`;
the constant remains as a Phase-1 baseline reference.

No code changes — purely descriptive.

Refs: /code-review-ai-ai-review findings M-A1, L-A3 on commit 5d7009a.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 4 — Push the trio

### Step 1 — Final regression sweep

```bash
uv run python -m pytest \
    tests/test_bazi_rules.py \
    tests/test_bazi_day_anchor_invariants.py \
    tests/test_regression_v1_compatibility.py \
    tests/test_bazi_baseline_dst_fold.py \
    tests/test_bazi_baseline_inventory.py \
    tests/test_constants.py \
    tests/test_invariants.py \
    tests/test_openapi_contract.py \
    -q
```

Expected: all green; no count regression vs the pre-plan baseline (144 pass / 1 skip).

### Step 2 — Pre-push divergence check

```bash
git fetch origin main
git log --oneline origin/main..HEAD
git merge-base --is-ancestor origin/main HEAD && echo "OK: fast-forward"
```

Expected: 3 local commits ahead of origin, fast-forward shape.

### Step 3 — Push

```bash
git push
```

Expected: `5d7009a..<new HEAD>  main -> main`.

---

## Out of scope (deferred)

- **L-A2** — `sexagenary_day_index_from_date(offset: int = DAY_OFFSET)` default arg. Direct callers (tests, CLI) still get the historic constant. A future cleanup could change the signature to `offset: Optional[int] = None` and derive from the default ruleset when None, but that's a non-trivial signature change for a low-impact issue. Deferred to a Phase-3 cleanup pass.
- **L-A4** — Provenance `ruleset_id` default mismatch (DEV-2026-002). Explicitly tracked for FBP-03-004; out of scope here.

---

## Estimated wall-clock

~25–35 minutes including final sweep + push.
