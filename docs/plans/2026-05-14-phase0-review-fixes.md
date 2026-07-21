# Phase 0 Review Fixes — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix B1 (blocking) and I1, I2, I3, I4, I5, M1 from the Phase 0 code review, then run a final review on the result. No production logic changes — work is confined to `scripts/`, `tests/`, and one JSON regeneration.

**Architecture:** Six small, TDD-driven, independently-commit-able fixes to the BAZI-PRECISION-V2 Phase 0 scaffolding already on disk. Each fix is one commit. The exporter (`scripts/export_bazi_baseline.py`) gets two passes (B1 and I1/I2); they're kept separate so reviewers can see the bugfix distinct from the refactor.

**Tech Stack:** Python 3.10+, pytest, jsonschema (already a dep). No new dependencies.

**Pre-flight (already verified):**
- `bazi_engine/time_utils.py:63` — `resolve_local_iso(birth_local_iso, tz_name, *, ambiguous, nonexistent) -> Tuple[datetime, LocalTimeResolution]`
- `bazi_engine/types.py:36-47` — `BaziInput` accepts `fold: Fold = 0`
- `bazi_engine/types.py:59-65` — `BaziResult.birth_utc_dt: datetime`
- `spec/rulesets/standard_bazi_2026.json` — has top-level `"ruleset_id": "standard_bazi_2026"`

**Order:** strict dependency order. Don't re-order; M1 needs B1 and I1/I2 done so regeneration produces a clean baseline.

---

## Task 1 — B1: Fix DST `ambiguousTime` drop in exporter

**Why this matters:** Today `_compute_one()` ignores `ambiguousTime` from case dicts. Both DST fall-back cases (`berlin_dst_fall_back_2024_earlier` / `_later`) are silently constructed with the engine's default fold, defeating the test. BaZi pillars alone are coarse enough that fold typically doesn't change them, so visibility into the *UTC timestamp* must also be added or the regression will remain invisible.

**Files:**
- Modify: `scripts/export_bazi_baseline.py` (`_compute_one`, `BASELINE_CASES`)
- Create: `tests/test_bazi_baseline_dst_fold.py`
- Touch: `tests/fixtures/bazi_baseline_v1.json` (regenerated at Task 5)

### Step 1 — Write failing regression test

Create `tests/test_bazi_baseline_dst_fold.py`:

```python
"""B1 regression: DST fall-back fold must propagate through the exporter.

Two cases that differ only in ``ambiguousTime`` must record different
``birth_utc_iso`` values in the baseline output. If they don't, the
exporter is silently dropping fold disambiguation.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
BASELINE_PATH = REPO_ROOT / "tests" / "fixtures" / "bazi_baseline_v1.json"


def _load_or_skip() -> dict:
    if not BASELINE_PATH.exists():
        pytest.skip("baseline missing; run scripts/export_bazi_baseline.py")
    return json.loads(BASELINE_PATH.read_text())


def test_dst_fall_back_pair_records_different_utc():
    doc = _load_or_skip()
    by_id = {c["id"]: c for c in doc["cases"]}
    earlier = by_id.get("berlin_dst_fall_back_2024_earlier")
    later = by_id.get("berlin_dst_fall_back_2024_later")
    assert earlier is not None, "exporter must keep the DST 'earlier' case"
    assert later is not None, "exporter must keep the DST 'later' case"

    earlier_utc = earlier["output"].get("birth_utc_iso")
    later_utc = later["output"].get("birth_utc_iso")
    assert earlier_utc is not None, (
        "B1 fix must record birth_utc_iso so fold differences are visible."
    )
    assert later_utc is not None
    assert earlier_utc != later_utc, (
        f"DST fold drop: both cases recorded the same UTC ({earlier_utc!r}). "
        "Exporter is not honoring ambiguousTime."
    )


def test_dst_fall_back_pair_records_fold_in_input():
    doc = _load_or_skip()
    by_id = {c["id"]: c for c in doc["cases"]}
    earlier = by_id["berlin_dst_fall_back_2024_earlier"]
    later = by_id["berlin_dst_fall_back_2024_later"]
    assert earlier["input"].get("ambiguousTime") == "earlier"
    assert later["input"].get("ambiguousTime") == "later"
```

### Step 2 — Run; expect failure

```bash
.venv/bin/python -m pytest tests/test_bazi_baseline_dst_fold.py -q
```

Expected: 2 failures — `birth_utc_iso` is missing from current output structure, and even if it were present the two UTCs would be equal.

### Step 3 — Fix `_compute_one` to honor `ambiguousTime`/`nonexistentTime` and record UTC

Edit `scripts/export_bazi_baseline.py`. Replace the `_compute_one` function entirely:

```python
def _compute_one(case: dict[str, Any]) -> dict[str, Any]:
    """Run the engine on a single case and return a plain-data record.

    Handles ``ambiguousTime`` and ``nonexistentTime`` the same way the
    API router does (``bazi_engine/routers/bazi.py:162``): resolve the
    local time first, then construct ``BaziInput`` with the chosen
    ``fold``. The chart UTC is recorded in the output so DST-fold
    regressions are visible in the baseline.
    """
    from bazi_engine.bazi import compute_bazi
    from bazi_engine.types import BaziInput
    from bazi_engine.time_utils import resolve_local_iso

    ambiguous = case.get("ambiguousTime", "earlier")
    nonexistent = case.get("nonexistentTime", "error")
    dt_local, _resolution = resolve_local_iso(
        case["birth_local"],
        case["timezone"],
        ambiguous=ambiguous,
        nonexistent=nonexistent,
    )
    resolved_naive = dt_local.replace(tzinfo=None).isoformat()
    chosen_fold = 0 if ambiguous == "earlier" else 1

    kwargs: dict[str, Any] = {
        "birth_local": resolved_naive,
        "timezone": case["timezone"],
        "longitude_deg": case["longitude_deg"],
        "latitude_deg": case["latitude_deg"],
        "fold": chosen_fold,
    }
    for opt in ("time_standard", "day_boundary"):
        if opt in case:
            kwargs[opt] = case[opt]

    res = compute_bazi(BaziInput(**kwargs))
    pillars = (
        str(res.pillars.year),
        str(res.pillars.month),
        str(res.pillars.day),
        str(res.pillars.hour),
    )
    return {
        "id": case["id"],
        "category": case["category"],
        "input": {k: v for k, v in case.items() if k not in {"id", "category"}},
        "output": {
            "pillars": {
                "year":  pillars[0],
                "month": pillars[1],
                "day":   pillars[2],
                "hour":  pillars[3],
            },
            "is_before_lichun": bool(res.is_before_lichun),
            "birth_utc_iso": res.birth_utc_dt.isoformat(),
        },
    }
```

### Step 4 — Regenerate baseline and rerun the test

```bash
.venv/bin/python scripts/export_bazi_baseline.py
.venv/bin/python -m pytest tests/test_bazi_baseline_dst_fold.py tests/test_bazi_baseline_inventory.py tests/test_regression_v1_compatibility.py -q
```

Expected: all pass. The two DST cases now have different `birth_utc_iso` values (one hour apart).

### Step 5 — Commit

```bash
git add scripts/export_bazi_baseline.py tests/test_bazi_baseline_dst_fold.py tests/fixtures/bazi_baseline_v1.json
git commit -m "fix(exporter): honor ambiguousTime; record birth_utc_iso (B1)

Previously _compute_one() built BaziInput directly without calling
resolve_local_iso, so 'ambiguousTime' values in BASELINE_CASES were
silently dropped. Both fall-back cases produced identical output.
Also surface chart UTC so fold differences are visible in the baseline.

Refs: docs/audits/fufire_bazi_precision_pre_audit.md review finding B1."
```

---

## Task 2 — I3 + I4: Move ruleset-only invariant test out of SE1-skipped module

**Why this matters:** `tests/test_invariants.py` skips at module level when Swiss Ephemeris files are absent. The new `test_day_offset_reference_examples` only reads a JSON ruleset and a constant — it doesn't need ephemeris. In MOSEPH-only CI it never runs, which defeats the point of the rewrite (FBP-00-005 anchor-policy test).

I4 (replace bare `AssertionError` with `pytest.fail`) is folded in because we're touching the same code.

**Files:**
- Create: `tests/test_bazi_day_anchor_invariants.py`
- Modify: `tests/test_invariants.py` (remove the rewritten function and its imports)

### Step 1 — Create the SE1-independent test file

Create `tests/test_bazi_day_anchor_invariants.py`:

```python
"""FBP-00-005 — ruleset-driven day-anchor invariants.

This module deliberately has **no** ephemeris dependency so the
anchor-policy test runs in every CI configuration (including
MOSEPH-only). The day-pillar sanity checks that *do* require ephemeris
remain in ``tests/test_invariants.py``.

History: prior to BAZI-PRECISION-V2, this test asserted
``DAY_OFFSET == 49`` directly. That treated an unverified engine
constant as ground truth (DEV-2026-004). It now reads the ruleset's
own declared anchor and verification status.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from bazi_engine.constants import DAY_OFFSET

RULESET_PATH = (
    Path(__file__).resolve().parents[1]
    / "spec" / "rulesets" / "standard_bazi_2026.json"
)


def test_day_offset_is_a_valid_sexagenary_offset():
    """Range/type invariant — survives any ruleset anchor change."""
    assert isinstance(DAY_OFFSET, int)
    assert 0 <= DAY_OFFSET < 60


def test_ruleset_declares_day_cycle_anchor():
    """The ruleset must carry an anchor record (FBP-02-001 precondition)."""
    ruleset = json.loads(RULESET_PATH.read_text())
    anchor = ruleset["day_cycle_anchor"]
    assert anchor["anchor_type"] in {"JDN", "DATE"}, anchor
    assert anchor["anchor_sexagenary_index_0based"] == 0
    assert anchor["anchor_verification"] in {"unverified", "verified"}


def test_day_anchor_phase0_baseline_behavior():
    """Phase-0 stop-gate behavior — engine baseline preserved until anchor is verified.

    While the anchor is ``unverified`` (Phase 0 / start of Phase 2),
    the engine's historic outputs for the two reference dates are
    preserved as a *regression guard*, NOT as truth. When the anchor
    is upgraded to ``verified`` (FBP-02-003), this test must be
    rewritten to assert against an EXTERNAL_ORACLE golden in
    ``tests/golden_reference_cases.py``.
    """
    # Local import keeps the module load cheap and avoids pulling in
    # ephemeris-touching code for the other two tests above.
    from bazi_engine.bazi import sexagenary_day_index_from_date

    ruleset = json.loads(RULESET_PATH.read_text())
    status = ruleset["day_cycle_anchor"]["anchor_verification"]

    if status == "verified":
        pytest.fail(
            "Anchor verification was upgraded to 'verified'. "
            "Rewrite this test per FBP-02-002 to assert against the "
            "EXTERNAL_ORACLE entries in tests/golden_reference_cases.py."
        )

    # Engine baseline (regression guard, not truth):
    assert sexagenary_day_index_from_date(1912, 2, 18) == 0
    assert sexagenary_day_index_from_date(1949, 10, 1) == 0
```

### Step 2 — Run new file in isolation; verify it executes without SE1

```bash
.venv/bin/python -m pytest tests/test_bazi_day_anchor_invariants.py -q
```

Expected: 3 passed (no skip).

### Step 3 — Remove the rewritten function from `tests/test_invariants.py`

Edit `tests/test_invariants.py`. Remove the entire `test_day_offset_reference_examples` function (the version I rewrote in Phase 0) and the now-unused `DAY_OFFSET` import.

After the edit, `test_invariants.py` should contain only:

```python
from __future__ import annotations

import pytest
from bazi_engine.ephemeris import ensure_ephemeris_files
from bazi_engine.exc import EphemerisUnavailableError

try:
    ensure_ephemeris_files(None)
except (FileNotFoundError, EphemerisUnavailableError):
    pytest.skip("Legacy tests require Swiss Ephemeris files (no implicit downloads). Set SE_EPHE_PATH to run.", allow_module_level=True)

from bazi_engine.types import BaziInput
from bazi_engine.bazi import compute_bazi


def test_month_boundaries_strict_increasing():
    inp = BaziInput(
        birth_local="2024-02-10T14:30:00",
        timezone="Europe/Berlin",
        longitude_deg=13.4050,
        latitude_deg=52.52,
    )
    res = compute_bazi(inp)
    bounds = res.month_boundaries_local_dt
    assert len(bounds) == 13
    for a, b in zip(bounds, bounds[1:]):
        assert a < b
```

### Step 4 — Run the relevant tests

```bash
.venv/bin/python -m pytest tests/test_bazi_day_anchor_invariants.py tests/test_invariants.py -q
```

Expected: 3 passed in `test_bazi_day_anchor_invariants.py`; `test_invariants.py` skipped (no SE1 present), or 1 passed if SE1 is configured.

### Step 5 — Commit

```bash
git add tests/test_bazi_day_anchor_invariants.py tests/test_invariants.py
git commit -m "test: extract ruleset-only day-anchor invariants to dedicated module (I3, I4)

The rewritten test_day_offset_reference_examples does not need
ephemeris, but the module-level skip in tests/test_invariants.py
prevented it from running in MOSEPH-only CI. Move the ruleset-policy
checks to tests/test_bazi_day_anchor_invariants.py so they run
unconditionally; leave the ephemeris-dependent month_boundaries test
behind. Also replace the bare AssertionError with pytest.fail() for
clearer reporting when the anchor is upgraded (FBP-02-003).

Refs: review findings I3, I4."
```

---

## Task 3 — I1 + I2: Exporter ephemeris-mode refactor

**Why this matters:** `_resolve_ephemeris_mode()` claims to *resolve* but in fact mutates `os.environ["EPHEMERIS_MODE"]` permanently. Two problems: (a) silent global side effect in a function named "resolve", and (b) the env mutation persists for any subsequent code in the same process.

**Fix shape:** split into a pure `_detect_ephemeris_mode()` and an explicit `_apply_ephemeris_mode_to_env()`. `build_baseline()` snapshots and restores the env around the work.

**Files:**
- Modify: `scripts/export_bazi_baseline.py`

### Step 1 — Write a small unit test for the pure detector

Append to `tests/test_bazi_baseline_inventory.py`:

```python
def test_detect_ephemeris_mode_is_pure(monkeypatch):
    """I2: detection must not mutate the environment."""
    import importlib
    import scripts.export_bazi_baseline as exp
    importlib.reload(exp)

    monkeypatch.delenv("EPHEMERIS_MODE", raising=False)
    before = dict(os.environ)
    mode = exp._detect_ephemeris_mode()
    after = dict(os.environ)
    assert mode in {"SWIEPH", "MOSEPH"}
    assert before == after, (
        f"_detect_ephemeris_mode mutated env. "
        f"Added: {set(after) - set(before)}; "
        f"Changed: {[k for k in before if before[k] != after.get(k)]}"
    )
```

Also add `import os` at the top of `test_bazi_baseline_inventory.py` if not present.

### Step 2 — Run; expect failure

```bash
.venv/bin/python -m pytest tests/test_bazi_baseline_inventory.py::test_detect_ephemeris_mode_is_pure -q
```

Expected: `AttributeError: module 'scripts.export_bazi_baseline' has no attribute '_detect_ephemeris_mode'`.

### Step 3 — Refactor the exporter

In `scripts/export_bazi_baseline.py`, replace `_resolve_ephemeris_mode()` and adjust `build_baseline()`:

```python
def _detect_ephemeris_mode() -> str:
    """Pure inspection. Returns the ephemeris mode the engine would use
    *given the current environment and SE1 file availability*.

    Does NOT modify the environment. Use ``_apply_ephemeris_mode_to_env``
    if you need to force MOSEPH for the duration of a call.
    """
    explicit = os.environ.get("EPHEMERIS_MODE")
    if explicit:
        return explicit.upper()
    try:
        from bazi_engine.ephemeris import (
            EPHEMERIS_FILES_REQUIRED,
            _resolve_ephe_path,
        )
        path = _resolve_ephe_path(None)
        if all((path / name).exists() for name in EPHEMERIS_FILES_REQUIRED):
            return "SWIEPH"
    except Exception:
        pass
    return "MOSEPH"


def _apply_ephemeris_mode_to_env(mode: str) -> str | None:
    """Set ``EPHEMERIS_MODE`` and return the prior value (or None).

    Caller is responsible for restoring the prior value when done.
    """
    prior = os.environ.get("EPHEMERIS_MODE")
    os.environ["EPHEMERIS_MODE"] = mode
    return prior


def _restore_ephemeris_mode(prior: str | None) -> None:
    if prior is None:
        os.environ.pop("EPHEMERIS_MODE", None)
    else:
        os.environ["EPHEMERIS_MODE"] = prior


def build_baseline(cases: Iterable[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Assemble the full baseline document (deterministic)."""
    ephemeris_mode = _detect_ephemeris_mode()
    prior = _apply_ephemeris_mode_to_env(ephemeris_mode)
    try:
        from bazi_engine import __version__ as engine_version
        from bazi_engine.provenance import WUXING_PARAMETER_SET

        records = [_compute_one(c) for c in (cases or BASELINE_CASES)]
    finally:
        _restore_ephemeris_mode(prior)

    return {
        "schema_version": "1.0",
        "purpose": (
            "Engine-derived v1 baseline for regression detection only. "
            "NOT an external oracle. See "
            "spec/golden/bazi_case.schema.json source_type taxonomy."
        ),
        "metadata": {
            "engine_version": engine_version,
            "parameter_set_version": WUXING_PARAMETER_SET["version"],
            "ruleset_id": "standard_bazi_2026",   # placeholder; Task 5 (M1) replaces.
            "ephemeris_mode": ephemeris_mode,
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "exporter": "scripts/export_bazi_baseline.py",
        },
        "cases": records,
    }
```

### Step 4 — Rerun the new test plus the existing exporter check

```bash
.venv/bin/python -m pytest tests/test_bazi_baseline_inventory.py -q
.venv/bin/python scripts/export_bazi_baseline.py --check
```

Expected: all pass; `--check` reports "Baseline unchanged" because the metadata field that differs (`exported_at`) is stripped by `_strip_volatile`.

### Step 5 — Commit

```bash
git add scripts/export_bazi_baseline.py tests/test_bazi_baseline_inventory.py
git commit -m "refactor(exporter): split detect from apply; restore env (I1, I2)

_resolve_ephemeris_mode was misnamed: it both detected the mode AND
permanently mutated os.environ. Split into _detect_ephemeris_mode
(pure) and _apply_ephemeris_mode_to_env (explicit setter with prior
returned); build_baseline now restores the env after work. Adds a
unit test asserting that detection does not mutate the environment.

Refs: review findings I1, I2."
```

---

## Task 4 — I5: Drop unused `baseline` fixture parameter

**Why this matters:** `test_v1_pillars_unchanged(baseline, case)` accepts `baseline` but never references it. The fixture is meant to skip when the file is absent, but that skip is already guaranteed by `_build_baseline_or_skip()` returning `{"cases": []}` (no parametrize entries → no test runs). The unused parameter trips linters and confuses readers.

**Files:**
- Modify: `tests/test_regression_v1_compatibility.py`

### Step 1 — Drop the fixture parameter

In `tests/test_regression_v1_compatibility.py`, change:

```python
def test_v1_pillars_unchanged(baseline, case):
```

to:

```python
def test_v1_pillars_unchanged(case):
```

(Keep the `baseline` fixture definition — it is still used by `test_baseline_ephemeris_recorded`.)

### Step 2 — Run

```bash
.venv/bin/python -m pytest tests/test_regression_v1_compatibility.py -q
```

Expected: same number of tests pass (14 parametrized + 1 metadata = 15).

### Step 3 — Commit

```bash
git add tests/test_regression_v1_compatibility.py
git commit -m "test: drop unused 'baseline' fixture param from regression test (I5)

The 'baseline' fixture in test_v1_pillars_unchanged was never
referenced in the body; the skip-on-missing-file behavior is already
covered by _build_baseline_or_skip() producing an empty parametrize
list. test_baseline_ephemeris_recorded still uses the fixture.

Refs: review finding I5."
```

---

## Task 5 — M1: Source `ruleset_id` from the ruleset JSON itself

**Why this matters:** The baseline metadata hardcoded `"ruleset_id": "standard_bazi_2026"`. That happens to match the file name, but the live provenance default emits `traditional_bazi_2026` (DEV-2026-002). The right fix is to source the ID from the ruleset file's own `ruleset_id` field — verified to exist at the top level of `spec/rulesets/standard_bazi_2026.json`. This way the baseline tracks whatever the ruleset declares, and DEV-2026-002 is contained to provenance.py.

**Files:**
- Modify: `scripts/export_bazi_baseline.py`
- Regenerate: `tests/fixtures/bazi_baseline_v1.json`

### Step 1 — Replace the hardcoded value with a ruleset lookup

In `scripts/export_bazi_baseline.py`, add a helper near `_detect_ephemeris_mode`:

```python
def _load_ruleset_id(ruleset_path: Path | None = None) -> str:
    """Read ``ruleset_id`` from the canonical ruleset file.

    Falls back to the file stem if the ruleset omits the field; logs a
    warning in that case so the gap is visible.
    """
    path = ruleset_path or (REPO_ROOT / "spec" / "rulesets" / "standard_bazi_2026.json")
    try:
        data = json.loads(path.read_text())
    except Exception:
        return path.stem
    declared = data.get("ruleset_id")
    if declared:
        return str(declared)
    print(
        f"[warn] {path} has no top-level 'ruleset_id'; falling back to filename.",
        file=sys.stderr,
    )
    return path.stem
```

Then in `build_baseline()` replace the line:

```python
"ruleset_id": "standard_bazi_2026",   # placeholder; Task 5 (M1) replaces.
```

with:

```python
"ruleset_id": _load_ruleset_id(),
```

### Step 2 — Regenerate the baseline

```bash
.venv/bin/python scripts/export_bazi_baseline.py
```

Expected output: `[OK] Wrote baseline → ... (14 cases).`

Verify:

```bash
.venv/bin/python -c "import json; d=json.load(open('tests/fixtures/bazi_baseline_v1.json')); print(d['metadata']['ruleset_id'])"
```

Expected: `standard_bazi_2026` (sourced from the ruleset file, not from a hardcoded string).

### Step 3 — Run regression + inventory tests

```bash
.venv/bin/python -m pytest tests/test_bazi_baseline_inventory.py tests/test_regression_v1_compatibility.py tests/test_bazi_baseline_dst_fold.py -q
```

Expected: all pass.

### Step 4 — Commit

```bash
git add scripts/export_bazi_baseline.py tests/fixtures/bazi_baseline_v1.json
git commit -m "fix(exporter): source ruleset_id from the ruleset JSON itself (M1)

Hardcoding 'standard_bazi_2026' in baseline metadata produced an
inconsistency with the live provenance default ('traditional_bazi_2026',
DEV-2026-002). Read the ruleset's own declared ruleset_id field so the
baseline tracks the ruleset's identity rather than a brittle string.

Refs: review finding M1."
```

---

## Task 6 — Final review pass

**Files:**
- Read every file touched by tasks 1–5 and run the full Phase 0 test slice.

### Step 1 — Run the full Phase 0 test slice

```bash
.venv/bin/python -m pytest \
    tests/test_bazi_day_anchor_invariants.py \
    tests/test_bazi_golden_case_schema.py \
    tests/test_bazi_baseline_inventory.py \
    tests/test_regression_v1_compatibility.py \
    tests/test_bazi_baseline_dst_fold.py \
    tests/test_constants.py \
    -q
```

Expected: all green; no skips other than module-skipped suites that depend on SE1.

### Step 2 — Run the exporter `--check` mode (idempotency)

```bash
.venv/bin/python scripts/export_bazi_baseline.py --check
```

Expected: `[OK] Baseline unchanged (14 cases).`

### Step 3 — Diff sanity: confirm DST fall-back pair really differs

```bash
.venv/bin/python -c "
import json
d = json.load(open('tests/fixtures/bazi_baseline_v1.json'))
pair = [c for c in d['cases'] if c['id'].startswith('berlin_dst_fall_back_2024_')]
for c in pair:
    print(c['id'], c['output']['birth_utc_iso'])
"
```

Expected: two different ISO timestamps, one hour apart (e.g. `2024-10-27T00:30:00+00:00` and `2024-10-27T01:30:00+00:00`).

### Step 4 — Read each changed file end-to-end; produce review notes

Files to read in full:
- `scripts/export_bazi_baseline.py`
- `tests/test_bazi_baseline_dst_fold.py`
- `tests/test_bazi_day_anchor_invariants.py`
- `tests/test_invariants.py` (only to confirm it's smaller and clean)
- `tests/test_regression_v1_compatibility.py`
- `tests/test_bazi_baseline_inventory.py`
- `tests/fixtures/bazi_baseline_v1.json` (metadata block only)

Write a short review summary covering correctness, security (none expected — no untrusted input), performance (one-time export script, irrelevant), maintainability, and any deferred items (e.g., DEV entry updates).

### Step 5 — If review is clean: nothing to commit; if it surfaces issues, fix and commit per the same TDD pattern

Then mark the work done.

---

## Notes & deferred work

- **DEV register update.** After Task 5, DEV-2026-002 is *contained* (baseline no longer participates) but not resolved (provenance default still mismatches). No new DEV entry is needed.
- **`test_constants.py` literal-49 assertions** remain (DEV-2026-005). Out of scope; tracked for FBP-02-002 follow-up.
- **MOSEPH baseline note** still applies; recorded in `metadata.ephemeris_mode`. When SE1 files become available in CI, regenerate and verify the diff.
- **`test_invariants.py` is now slimmer** — it only contains the SE1-dependent month-boundaries test. If a future change makes the module fully empty under SE1-skip, replace the bare skip with `pytestmark = pytest.mark.skip(...)` for clarity.

---

## Estimated wall-clock

~25–35 minutes if executed sequentially, including verification steps and small commits.
