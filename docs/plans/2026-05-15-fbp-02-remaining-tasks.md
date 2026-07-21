# Phase 2 — Remaining Non-Blocked Tasks Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Land the three remaining non-domain-blocked Phase-2 tasks (FBP-02-006, FBP-02-005, FBP-02-004) of `BAZI-PRECISION-V2`, in that order. After this plan, only the three domain-review-blocked tasks (FBP-02-002, -003, -007) remain in Phase 2.

**Architecture:**
- **FBP-02-006 (vestigial-field deprecation)** is a one-commit doc + warning addition. The `BaziInput.month_boundary_scheme` field is declared but read nowhere; the ruleset's `month_boundary` block is what actually drives month derivation. We mark the field deprecated, warn on non-default values, and add a regression test pinning the no-effect property.
- **FBP-02-005 (hour-branch via effective-time-policy)** is the meaty change. `compute_bazi()` already loads the ruleset; we plumb `EffectiveTimeContext` into it as well, switch `hour_branch_index` to `hour_branch_index_from_tlst(ctx.tlst_hours)` when the request uses TLST, and **remove the Phase-1 router clamp** in `routers/bazi.py` and `routers/chart.py`. The `tests/test_time_standard_acceptance.py::test_tlst_pillars_equal_lmt_pillars_phase1` test (which today pins "TLST pillars == LMT pillars") flips to "TLST pillars MAY DIFFER from LMT at hour-boundary cases".
- **FBP-02-004 (Zi-day-boundary via effective time)** builds on -005's plumbing. `apply_day_boundary` gains a TLST-aware variant that uses `ctx.tlst_hours >= 23` instead of `dt + 1h` to detect Zi-hour rollover, gated by the ruleset's `day_change_policy.time_standard_for_day_rollover` field (`"TLST"` opts in; `"CIVIL"` keeps legacy).

**Tech Stack:** Python 3.10+, pytest, FastAPI/Pydantic. Tests run via `uv run python -m pytest …`.

**Pre-flight (already verified):**
- `bazi_engine/types.py:56` is the SOLE occurrence of `month_boundary_scheme` — `grep -rn` in `bazi_engine/`, `tests/`, `spec/` returns no other references.
- `spec/rulesets/standard_bazi_2026.json` declares `month_boundary.mode = "JIEQI_CROSSING"` and `month_start_solar_longitude_deg = 315.0`, consumed by `compute_bazi()` implicitly via Swiss Ephemeris solar-term lookups.
- `bazi_engine/bafe/mapping.py:79` has `def hour_branch_index_from_tlst(tlst_hours: float) -> int` — the helper FBP-02-005 needs.
- `bazi_engine/bazi.py:51` has the legacy `def hour_branch_index(dt_local: datetime) -> int` returning `((dt_local.hour + 1) // 2) % 12`.
- `bazi_engine/time_context.py::compute_effective_time_context(birth_local_iso, tz_name, longitude_deg) -> EffectiveTimeContext` (FBP-01-002) is already wired and produces `tlst_hours` consistent with `/calculate/tst`.
- Phase-1 router clamp lives in `routers/bazi.py:172-180` (the `engine_standard = "LMT" if requested_standard == "TLST" else requested_standard` block) and `routers/chart.py:208-211` (same idiom).
- Phase-1 invariant `tests/test_time_standard_acceptance.py::test_tlst_pillars_equal_lmt_pillars_phase1` will need to be flipped/renamed by Task 2.
- HEAD = `81e7752` (FBP-02-008 just pushed). Working tree clean.

---

## Task 1 — FBP-02-006: Deprecate `BaziInput.month_boundary_scheme`

**Why this matters:** The field is dead config — declared in the dataclass, never consulted by `compute_bazi()` or any downstream. A user setting `month_boundary_scheme="all_24"` today gets exactly the same pillars as `month_boundary_scheme="jie_only"`, which is misleading. We mark it deprecated and pin the no-effect property as a regression.

**Files:**
- Modify: `bazi_engine/types.py` (annotate the field as deprecated)
- Test: `tests/test_month_boundary_scheme_vestigial.py` (new)

### Step 1 — Write the failing test

Create `tests/test_month_boundary_scheme_vestigial.py`:

```python
"""FBP-02-006 — month_boundary_scheme is vestigial.

The field exists in BaziInput for backward compatibility but is not
consulted by compute_bazi(). The ruleset's month_boundary block is
the actual source. This test pins the no-effect property so a future
implementation that accidentally wires this field surfaces as a
failing test.
"""
from __future__ import annotations

import pytest
import warnings

from bazi_engine.ephemeris import ensure_ephemeris_files
from bazi_engine.exc import EphemerisUnavailableError

try:
    ensure_ephemeris_files(None)
except (FileNotFoundError, EphemerisUnavailableError):
    pytest.skip("Swiss Ephemeris files not available.", allow_module_level=True)

from bazi_engine.bazi import compute_bazi
from bazi_engine.types import BaziInput


BASE = dict(
    birth_local="2024-02-10T14:30:00",
    timezone="Europe/Berlin",
    longitude_deg=13.4050,
    latitude_deg=52.52,
)


def test_month_boundary_scheme_does_not_affect_pillars():
    """jie_only vs all_24 must produce identical pillars (today).

    If this assertion ever fails, either the field has finally been
    wired up (then this test should be replaced with a real
    behavior test) or there is a regression.
    """
    jie = compute_bazi(BaziInput(**BASE, month_boundary_scheme="jie_only"))
    all24 = compute_bazi(BaziInput(**BASE, month_boundary_scheme="all_24"))
    assert str(jie.pillars.year) == str(all24.pillars.year)
    assert str(jie.pillars.month) == str(all24.pillars.month)
    assert str(jie.pillars.day) == str(all24.pillars.day)
    assert str(jie.pillars.hour) == str(all24.pillars.hour)


def test_non_default_month_boundary_scheme_emits_deprecation_warning():
    """Phase 2 marks the field deprecated; non-default values warn."""
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        compute_bazi(BaziInput(**BASE, month_boundary_scheme="all_24"))
    deprecation_warnings = [
        w for w in caught if issubclass(w.category, DeprecationWarning)
        and "month_boundary_scheme" in str(w.message)
    ]
    assert len(deprecation_warnings) >= 1, (
        f"Expected DeprecationWarning mentioning month_boundary_scheme; "
        f"got: {[str(w.message) for w in caught]}"
    )


def test_default_month_boundary_scheme_does_not_warn():
    """Setting the default value (or omitting the field) must not warn."""
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        compute_bazi(BaziInput(**BASE))
        compute_bazi(BaziInput(**BASE, month_boundary_scheme="jie_only"))
    deprecation_warnings = [
        w for w in caught if issubclass(w.category, DeprecationWarning)
        and "month_boundary_scheme" in str(w.message)
    ]
    assert deprecation_warnings == [], (
        f"Default value must not warn; got: "
        f"{[str(w.message) for w in deprecation_warnings]}"
    )
```

### Step 2 — Run; expect RED

```bash
uv run python -m pytest tests/test_month_boundary_scheme_vestigial.py -q
```

Expected: `test_month_boundary_scheme_does_not_affect_pillars` PASSES (the field is already a no-op); the two warning tests FAIL (no warning emitted today).

### Step 3 — Add the deprecation warning at the engine entry

In `bazi_engine/bazi.py`, near the top of `compute_bazi(inp: BaziInput)` (right after the existing SwissEphBackend check at ~line 84, before the year-pillar work), insert:

```python
    # FBP-02-006: month_boundary_scheme is vestigial — the ruleset's
    # month_boundary block is the actual source of truth. Warn callers
    # who set a non-default value so they know it has no effect.
    if inp.month_boundary_scheme != "jie_only":
        import warnings as _warnings
        _warnings.warn(
            f"BaziInput.month_boundary_scheme={inp.month_boundary_scheme!r} "
            "has no effect on the computed pillars. The active "
            "month-boundary policy is read from the ruleset's "
            "`month_boundary` block. This field is deprecated and "
            "will be removed in /v2.",
            DeprecationWarning,
            stacklevel=2,
        )
```

### Step 4 — Run; expect GREEN

```bash
uv run python -m pytest tests/test_month_boundary_scheme_vestigial.py -q
```

Expected: 3 passed.

### Step 5 — Add deprecation note to the field declaration

In `bazi_engine/types.py:55-56`, replace:

```python
    # v0.4 Month Boundary Scheme
    month_boundary_scheme: Literal["jie_only", "all_24"] = "jie_only"
```

with:

```python
    # v0.4 Month Boundary Scheme.
    # FBP-02-006 (Phase 2): vestigial — never read by compute_bazi().
    # Kept for backward-compat with v1 consumers; non-default values
    # emit a DeprecationWarning at the engine entry. Slated for
    # removal in /v2 once consumers stop sending the field.
    month_boundary_scheme: Literal["jie_only", "all_24"] = "jie_only"
```

### Step 6 — Run the full regression slice

```bash
uv run python -m pytest \
    tests/test_month_boundary_scheme_vestigial.py \
    tests/test_regression_v1_compatibility.py \
    tests/test_bazi_rules.py \
    tests/test_pillar_trace.py \
    -q
```

Expected: all green; no regression in the 14-case v1 baseline.

### Step 7 — Commit

```bash
git add bazi_engine/bazi.py bazi_engine/types.py tests/test_month_boundary_scheme_vestigial.py
git commit -m "$(cat <<'EOF'
feat(bazi): deprecate vestigial BaziInput.month_boundary_scheme (FBP-02-006)

`BaziInput.month_boundary_scheme: Literal["jie_only", "all_24"]` is
declared in the dataclass but read nowhere — `compute_bazi()` does
not consult it. The ruleset's `month_boundary.mode` is the actual
source of truth for month-boundary semantics ("JIEQI_CROSSING" by
default, with `month_start_solar_longitude_deg=315.0`).

Phase 2 marks the field deprecated:
- Non-default values now emit a DeprecationWarning at the engine
  entry, naming the field and the replacement source.
- The default value (`jie_only`) remains silent for backward
  compatibility.
- Field comment in types.py explains the deprecation and points to
  /v2 removal.

Regression test pins the no-effect property: `jie_only` and `all_24`
produce identical pillars today. If this ever changes, the test
fails — either the field has finally been wired (then the test
should become a real behavior test) or there is a regression.

Closes FBP-02-006.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 2 — FBP-02-005: Hour-branch through Effective-Time-Policy + remove Phase-1 router clamp

**Why this matters:** Phase 1 added TLST as an opt-in time standard but clamped TLST → LMT at the router layer because `compute_bazi()` couldn't derive pillars from TLST. Phase 2 plumbs `EffectiveTimeContext` into the engine, switches `hour_branch_index` to `hour_branch_index_from_tlst(ctx.tlst_hours)` when TLST is selected, and removes the clamp. **First Phase-2 task that changes pillar output for TLST requests.**

The `test_tlst_pillars_equal_lmt_pillars_phase1` invariant — which today pins "TLST pillars == LMT pillars" via the clamp — must be **flipped**: TLST pillars are no longer required to equal LMT pillars at all times; they may differ at hour-boundary cases (and must match LMT for inputs at the timezone's standard meridian, where TLST == LMT by definition).

**Files:**
- Modify: `bazi_engine/bazi.py` (thread `EffectiveTimeContext`, switch hour-branch)
- Modify: `bazi_engine/routers/bazi.py` (remove clamp; keep `time_standard_used` in trace)
- Modify: `bazi_engine/routers/chart.py` (remove clamp)
- Modify: `tests/test_time_standard_acceptance.py` (flip the invariant; add boundary-case test)
- Possibly modify: `tests/test_regression_v1_compatibility.py` baseline (re-export if any case used TLST — it doesn't; verify)
- Test: `tests/test_bazi_tlst_hour_pillar.py` (new — boundary-case golden assertions)

### Step 1 — Write the failing tests for the new behavior

Create `tests/test_bazi_tlst_hour_pillar.py`:

```python
"""FBP-02-005 — TLST-derived hour pillar.

When a request opts into ``time_standard="TLST"``, the hour pillar
must be derived from True Local Solar Time (LMT + equation_of_time)
rather than from civil clock time. Concretely:

- At the timezone's standard meridian (e.g. 0° for UTC, 15° for CET),
  TLST equals LMT within ≈ 17 min of EoT. The hour-branch can still
  differ at the edge of a 2-hour Zi/Chou/Yin/… bin.
- For longitudes far from the standard meridian (e.g. Madrid at
  ~−3.7° in the CET zone, ~75 min west of meridian), TLST shifts the
  hour-of-day enough that the hour branch differs from LMT for
  birth times near a bin boundary.

This test set picks two cases:
1. A boundary case where TLST and LMT *must* land in different bins.
2. A non-boundary case where both still land in the same bin.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from bazi_engine.app import app

client = TestClient(app)


def _post(payload: dict) -> dict:
    r = client.post("/calculate/bazi", json=payload)
    assert r.status_code == 200, r.text
    return r.json()


# Madrid: longitude ≈ -3.70°, in CET (standard meridian 15°), so
# TLST trails CIVIL by roughly 1h15m on year-round average + EoT.
# A birth at 02:00 civil in late February (EoT ≈ -13 min) puts
# TLST around 00:30 (Zi → branch 0), while LMT at 02:00 civil with
# Madrid's longitude gives roughly 01:15 (Chou → branch 1). So
# hour_pillar.branch differs.
_MADRID_BASE = {
    "date": "2024-02-22T02:00:00",
    "tz": "Europe/Madrid",
    "lon": -3.7038,
    "lat": 40.4168,
    "boundary": "midnight",
}


def test_madrid_boundary_case_tlst_hour_branch_differs_from_lmt():
    """Madrid late-Feb 02:00 civil: TLST hour branch ≠ LMT hour branch."""
    tlst = _post({**_MADRID_BASE, "standard": "TLST"})
    lmt = _post({**_MADRID_BASE, "standard": "LMT"})
    assert tlst["pillars"]["hour"] != lmt["pillars"]["hour"], (
        f"Expected hour-branch divergence at the Madrid boundary case; "
        f"got TLST={tlst['pillars']['hour']!r} LMT={lmt['pillars']['hour']!r}"
    )


def test_civil_request_unchanged_after_phase2(monkeypatch):
    """A CIVIL request must produce the same hour pillar in Phase 2 as
    it did pre-FBP-02-005. Regression guard on the legacy default path."""
    civil = _post({**_MADRID_BASE, "standard": "CIVIL"})
    # 02:00 civil on Feb 22 in Europe/Madrid: hour=2 → branch_index
    # = (2+1)//2 % 12 = 1 (Chou). Stem follows from day stem.
    assert civil["pillars"]["hour"][-4:] == "Chou", (
        f"Civil hour pillar at 02:00 must end with Chou (branch=1); got "
        f"{civil['pillars']['hour']!r}"
    )


def test_tlst_request_no_longer_clamped_in_trace():
    """Post-FBP-02-005 the trace must record time_standard_used == TLST
    for a TLST request, not LMT (which was the Phase-1 clamp signature)."""
    r = client.post("/calculate/bazi", json={**_MADRID_BASE, "standard": "TLST"})
    hour_trace = r.json()["derivation_trace"]["hour"]
    assert hour_trace["time_standard_requested"] == "TLST"
    assert hour_trace["time_standard_used"] == "TLST", (
        "Phase-2 must remove the router clamp; trace should show "
        "time_standard_used=TLST, not LMT."
    )
```

Also, update `tests/test_time_standard_acceptance.py` — rename and rewrite the existing Phase-1 invariant:

Find:

```python
@_skip_no_engine
def test_tlst_pillars_equal_lmt_pillars_phase1():
    """Phase 1 only: TLST pillar values must equal LMT pillar values.

    This is the user-visible consequence of the router clamp. When the
    clamp is removed in FBP-02-005 (Phase 2), this test will need to
    be updated or replaced — that's intentional and tracked in
    docs/release/bazi_precision_release_gate.md.
    """
    r_lmt  = client.post("/calculate/bazi", json={**BASE, "standard": "LMT"})
    r_tlst = client.post("/calculate/bazi", json={**BASE, "standard": "TLST"})
    assert r_lmt.status_code == 200
    assert r_tlst.status_code == 200
    assert r_lmt.json()["pillars"] == r_tlst.json()["pillars"]
```

Replace with:

```python
@_skip_no_engine
def test_tlst_pillars_may_differ_from_lmt_phase2():
    """Phase 2 (FBP-02-005): the router clamp is gone, so TLST and LMT
    can produce different pillars when the longitude offset + EoT
    push the hour-of-day across a 2-hour Zi/Chou/Yin/… bin boundary.

    This particular fixture (Berlin near the CET standard meridian)
    is *not* a boundary case — TLST and LMT happen to land in the
    same bin — so the pillars match. The point of this test is to
    confirm the two surfaces still produce a valid pillar string each;
    the boundary-case divergence is in tests/test_bazi_tlst_hour_pillar.py.
    """
    r_lmt  = client.post("/calculate/bazi", json={**BASE, "standard": "LMT"})
    r_tlst = client.post("/calculate/bazi", json={**BASE, "standard": "TLST"})
    assert r_lmt.status_code == 200
    assert r_tlst.status_code == 200
    # Each response must be a complete BaziResponse; pillar shape must
    # match the Stem+Branch pattern.
    import re
    pat = re.compile(r"^(Jia|Yi|Bing|Ding|Wu|Ji|Geng|Xin|Ren|Gui)"
                     r"(Zi|Chou|Yin|Mao|Chen|Si|Wu|Wei|Shen|You|Xu|Hai)$")
    for label, body in (("LMT", r_lmt.json()), ("TLST", r_tlst.json())):
        for p in body["pillars"].values():
            assert pat.match(p), f"{label}: malformed pillar {p!r}"
```

### Step 2 — Run all four tests; expect RED

```bash
uv run python -m pytest \
    tests/test_bazi_tlst_hour_pillar.py \
    tests/test_time_standard_acceptance.py::test_tlst_pillars_may_differ_from_lmt_phase2 \
    -q
```

Expected:
- `test_madrid_boundary_case_tlst_hour_branch_differs_from_lmt` — FAILS (TLST clamp makes TLST == LMT pillars).
- `test_civil_request_unchanged_after_phase2` — likely PASSES (Civil path unchanged).
- `test_tlst_request_no_longer_clamped_in_trace` — FAILS (trace still shows `time_standard_used="LMT"`).
- `test_tlst_pillars_may_differ_from_lmt_phase2` — PASSES (shape check is permissive; just verifies pillars are well-formed).

**HALT-ON-DEFECT:** if `test_madrid_boundary_case_tlst_hour_branch_differs_from_lmt` passes during RED, STOP and report — the precondition that the clamp produces identical pillars isn't being exercised, and the boundary case must be re-chosen.

### Step 3 — Plumb EffectiveTimeContext into compute_bazi()

In `bazi_engine/bazi.py`:

(a) Add the import near the top:

```python
from .time_context import compute_effective_time_context
from .bafe.mapping import hour_branch_index_from_tlst
```

(b) Inside `compute_bazi()`, after the existing `chart_local_dt = …` line (before the hour-branch step around line 152), compute the context and pick the hour-branch helper:

```python
    # FBP-02-005 — TLST hour pillar.
    # For TLST requests, derive the hour branch from the apparent
    # solar hour-of-day instead of the civil clock. CIVIL and LMT
    # keep the legacy code path (hour_branch_index on chart_local_dt).
    if inp.time_standard == "TLST":
        ctx = compute_effective_time_context(
            birth_local_iso=inp.birth_local,
            tz_name=inp.timezone,
            longitude_deg=inp.longitude_deg,
        )
        hb = hour_branch_index_from_tlst(ctx.tlst_hours)
    else:
        hb = hour_branch_index(chart_local_dt)
```

Replace the existing `hb = hour_branch_index(chart_local_dt)` line with the conditional block above. Confirm `hour_pillar_from_day_stem(day_p.stem_index, hb, ruleset=ruleset)` is what immediately follows; it stays unchanged.

### Step 4 — Remove the Phase-1 router clamp

In `bazi_engine/routers/bazi.py`, find:

```python
        # FBP-01-001 (Phase 1) router clamp: TLST is accepted at the
        # API boundary but the engine still derives pillars from LMT
        # semantics. The original choice is preserved for the trace.
        # FBP-02-005 removes this clamp once compute_bazi() handles
        # TLST natively.
        requested_standard = req.standard
        engine_standard = "LMT" if requested_standard == "TLST" else requested_standard
```

Replace with:

```python
        # FBP-02-005 — Phase-1 router clamp removed. compute_bazi() now
        # handles TLST natively (TLST-derived hour pillar). For CIVIL
        # and LMT the engine keeps the legacy path. requested_standard
        # is kept in the trace alongside the engine's used value (which
        # for Phase 2 onward equals the requested value).
        requested_standard = req.standard
        engine_standard = requested_standard
```

In `bazi_engine/routers/chart.py`, find:

```python
        # FBP-01-001 (Phase 1) router clamp: see routers/bazi.py for
        # the rationale. /api/chart does not expose a derivation trace
        # so the requested-vs-used split is not surfaced here; the
        # same clamp keeps the engine path unambiguous.
        engine_time_standard = (
            "LMT" if req.time_standard == "TLST" else req.time_standard
        )
```

Replace with:

```python
        # FBP-02-005 — Phase-1 router clamp removed. The chart endpoint
        # forwards TLST verbatim to compute_bazi(), which now derives
        # hour pillars from True Local Solar Time directly.
        engine_time_standard = req.time_standard
```

### Step 5 — Run targeted tests; expect GREEN

```bash
uv run python -m pytest \
    tests/test_bazi_tlst_hour_pillar.py \
    tests/test_time_standard_acceptance.py \
    tests/test_regression_v1_compatibility.py \
    tests/test_pillar_trace.py \
    -q
```

Expected: all green. The v1 regression suite uses CIVIL/LMT only, so its 14 cases stay bit-identical. The new TLST boundary test now shows divergence.

### Step 6 — Run the wider Phase-0+1+2 slice

```bash
uv run python -m pytest \
    tests/test_bazi_tlst_hour_pillar.py \
    tests/test_time_standard_acceptance.py \
    tests/test_bazi_time_context.py \
    tests/test_tst_endpoint_consistency.py \
    tests/test_time_utils.py \
    tests/test_solar_time.py \
    tests/test_import_hierarchy.py \
    tests/test_openapi_contract.py \
    tests/test_endpoint_negative.py \
    tests/test_pillar_trace.py \
    tests/test_chart.py \
    tests/test_bazi_rules.py \
    tests/test_bazi_day_anchor_invariants.py \
    tests/test_regression_v1_compatibility.py \
    tests/test_bazi_baseline_dst_fold.py \
    tests/test_bazi_baseline_inventory.py \
    tests/test_constants.py \
    tests/test_month_boundary_scheme_vestigial.py \
    -q
```

Expected: all green; no v1 regression.

### Step 7 — Commit

```bash
git add bazi_engine/bazi.py bazi_engine/routers/bazi.py bazi_engine/routers/chart.py \
        tests/test_bazi_tlst_hour_pillar.py tests/test_time_standard_acceptance.py
git commit -m "$(cat <<'EOF'
feat(bazi): derive hour pillar from TLST when requested; remove Phase-1 clamp (FBP-02-005)

Phase-2 task that finally makes `time_standard="TLST"` produce
TLST-derived pillars. compute_bazi() now uses
hour_branch_index_from_tlst(ctx.tlst_hours) when the request uses
TLST, where ctx is computed via the existing
bazi_engine.time_context.compute_effective_time_context (FBP-01-002).
CIVIL and LMT keep the legacy hour_branch_index(chart_local_dt) path
unchanged.

The Phase-1 router clamp (routers/bazi.py + routers/chart.py — which
remapped TLST → LMT before BaziInput) is removed. The trace's
`time_standard_used` field now equals `time_standard_requested` for
TLST requests; the requested/used split remains the contract for
backward compatibility.

User-visible behavior change:
- /calculate/bazi + standard=TLST now produces different pillars than
  /calculate/bazi + standard=LMT for inputs where the longitude
  offset + equation-of-time push the hour-of-day across a 2-hour
  Zi/Chou/Yin/... bin boundary. For inputs near the timezone's
  standard meridian, TLST and LMT still land in the same bin and
  produce identical pillars.
- /chart + time_standard=TLST: same behavior change. The chart's
  bazi_section.time_standard_used field now reports "TLST" rather
  than "LMT" for TLST requests.

Test changes:
- New tests/test_bazi_tlst_hour_pillar.py: pins the Madrid boundary
  case (TLST hour branch must differ from LMT) + CIVIL regression
  guard + trace-shows-TLST-not-LMT assertion.
- tests/test_time_standard_acceptance.py: the Phase-1 invariant
  `test_tlst_pillars_equal_lmt_pillars_phase1` is replaced with
  `test_tlst_pillars_may_differ_from_lmt_phase2`, which only asserts
  pillar-string shape (no longer asserts equality).

v1 regression intact: tests/test_regression_v1_compatibility.py
(14-case baseline) passes bit-identically — all baseline cases use
CIVIL or LMT, never TLST.

Closes FBP-02-005. FBP-02-004 (Zi-day boundary on effective time)
builds on this plumbing next.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 3 — FBP-02-004: Zi-day boundary on effective time

**Why this matters:** Today `apply_day_boundary(dt, "zi")` does a blunt `dt + 1h` regardless of whether the chart used CIVIL, LMT, or TLST. The ruleset's `day_change_policy.time_standard_for_day_rollover` field declares the intended source ("TLST" in `standard_bazi_2026`). Phase 2 wires this through: when the ruleset says TLST and the request opts in, the Zi-boundary uses `ctx.tlst_hours >= 23` instead of the legacy increment.

**Files:**
- Modify: `bazi_engine/bazi.py` (in the day-pillar block where `apply_day_boundary` is called)
- Modify: `bazi_engine/time_utils.py:187` (no change needed — keep the legacy function; add a parallel TLST-aware helper)
- Test: `tests/test_bazi_zi_day_boundary.py` (new)

### Step 1 — Read the ruleset's day_change_policy

```bash
uv run python -c "
import json
r = json.load(open('spec/rulesets/standard_bazi_2026.json'))
print(json.dumps(r['day_change_policy'], indent=2))
"
```

Capture the values: `interval_convention` (`HALF_OPEN`), `mode` (`zi_hour_start`), `time_standard_for_day_rollover` (`TLST`), `zi_start_hour` (`23.0`). These are the inputs to the new helper.

### Step 2 — Write the failing tests

Create `tests/test_bazi_zi_day_boundary.py`:

```python
"""FBP-02-004 — Zi-day boundary on effective time.

Today apply_day_boundary("zi") naively returns dt + 1h regardless of
the request's time standard. Phase 2 routes the boundary check through
the ruleset's day_change_policy: when time_standard_for_day_rollover
is "TLST" and the request itself uses TLST, the boundary fires at
tlst_hours >= 23 (using HALF_OPEN convention) rather than at civil
hour 23.

The four cases that must be tested (per the original plan §7
FBP-02-004): 22:59 / 23:00 / 00:59 / 01:00 — once for CIVIL, once
for LMT, once for TLST.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from bazi_engine.app import app

client = TestClient(app)


BERLIN_BASE = {
    "tz": "Europe/Berlin",
    "lon": 13.4050, "lat": 52.52,
    "boundary": "zi",
}


def _hours_to_iso(h: int, m: int, day: str = "2024-06-15") -> str:
    return f"{day}T{h:02d}:{m:02d}:00"


@pytest.mark.parametrize("std", ["CIVIL", "LMT", "TLST"])
@pytest.mark.parametrize("hour,minute,expected_rollover", [
    (22, 59, False),
    (23, 0, True),   # Zi-hour start — rolls to next day
    (0, 59, True),   # Still in Zi-hour of next-day boundary semantics
    (1, 0, False),   # Past Zi-hour
])
def test_zi_boundary_per_standard(std, hour, minute, expected_rollover):
    """For each time standard, the Zi-day boundary fires at >= 23:00
    in that standard's hour-of-day, not in civil time.

    'expected_rollover=True' means the day pillar should advance
    by one sexagenary day compared to the same wall-clock just
    before 23:00.
    """
    iso = _hours_to_iso(hour, minute)
    payload = {**BERLIN_BASE, "date": iso, "standard": std}

    r = client.post("/calculate/bazi", json=payload)
    if r.status_code != 200:
        pytest.skip(f"engine unavailable: {r.text[:200]}")

    body = r.json()
    rolled = body["derivation_trace"]["day"]["sexagenary_index"]

    # Reference (just before Zi-hour same calendar day)
    ref_iso = _hours_to_iso(22, 0)
    ref = client.post(
        "/calculate/bazi", json={**BERLIN_BASE, "date": ref_iso, "standard": std}
    ).json()["derivation_trace"]["day"]["sexagenary_index"]

    if expected_rollover:
        assert rolled == (ref + 1) % 60, (
            f"{std} @ {hour:02d}:{minute:02d}: expected day-pillar "
            f"to be ref+1 (={(ref+1)%60}); got {rolled}"
        )
    else:
        assert rolled == ref, (
            f"{std} @ {hour:02d}:{minute:02d}: expected day-pillar "
            f"= ref (={ref}); got {rolled}"
        )
```

### Step 3 — Run; expect RED for TLST cases

```bash
uv run python -m pytest tests/test_bazi_zi_day_boundary.py -q
```

Expected: CIVIL and LMT cases mostly pass (the legacy `dt + 1h` handles them); TLST cases fail at the 22:59 / 23:00 boundary because the engine still uses civil hour-of-day for the rollover check.

**HALT-ON-DEFECT:** if all TLST cases pass during RED, STOP and report — the boundary differentiation isn't being exercised.

### Step 4 — Add the TLST-aware day-boundary helper

In `bazi_engine/bazi.py`, locate the existing block:

```python
    dt_for_day = apply_day_boundary(chart_local_dt, inp.day_boundary)
```

Replace with:

```python
    # FBP-02-004 — Zi-day boundary on effective time.
    # When the request uses TLST and the ruleset's day_change_policy
    # says TLST is the rollover reference, derive the boundary from
    # ctx.tlst_hours instead of the legacy chart_local_dt clock. For
    # CIVIL/LMT the legacy `apply_day_boundary` is unchanged.
    day_change_policy = ruleset.get("day_change_policy", {}) or {}
    zi_uses_tlst = (
        inp.day_boundary == "zi"
        and inp.time_standard == "TLST"
        and day_change_policy.get("time_standard_for_day_rollover") == "TLST"
    )
    if zi_uses_tlst:
        zi_start = float(day_change_policy.get("zi_start_hour", 23.0))
        # If the apparent solar hour is at or past the Zi start, advance
        # the day; otherwise stay on the civil calendar day.
        # ctx was computed earlier (FBP-02-005) for the hour-branch
        # decision — reuse the same instance.
        if 'ctx' not in dir() or ctx is None:  # safety: re-derive if not yet
            ctx = compute_effective_time_context(
                birth_local_iso=inp.birth_local,
                tz_name=inp.timezone,
                longitude_deg=inp.longitude_deg,
            )
        if ctx.tlst_hours >= zi_start:
            dt_for_day = chart_local_dt.replace(hour=0, minute=0, second=0) \
                          .replace() + _timedelta(days=1)
        else:
            dt_for_day = chart_local_dt
    else:
        dt_for_day = apply_day_boundary(chart_local_dt, inp.day_boundary)
```

(Note: `_timedelta` is `from datetime import timedelta as _timedelta` near the imports; check that it's imported. If not, add it.)

### Step 5 — Run targeted tests; expect GREEN

```bash
uv run python -m pytest \
    tests/test_bazi_zi_day_boundary.py \
    tests/test_bazi_tlst_hour_pillar.py \
    tests/test_regression_v1_compatibility.py \
    tests/test_pillar_trace.py \
    tests/test_time_utils.py \
    -q
```

Expected: all green. v1 baseline still passes (CIVIL/LMT path unchanged).

### Step 6 — Full Phase-2 slice

```bash
uv run python -m pytest \
    tests/test_month_boundary_scheme_vestigial.py \
    tests/test_bazi_tlst_hour_pillar.py \
    tests/test_bazi_zi_day_boundary.py \
    tests/test_bazi_rules.py \
    tests/test_bazi_day_anchor_invariants.py \
    tests/test_regression_v1_compatibility.py \
    tests/test_time_standard_acceptance.py \
    tests/test_bazi_time_context.py \
    tests/test_tst_endpoint_consistency.py \
    tests/test_time_utils.py \
    tests/test_solar_time.py \
    tests/test_import_hierarchy.py \
    tests/test_openapi_contract.py \
    tests/test_endpoint_negative.py \
    tests/test_pillar_trace.py \
    tests/test_chart.py \
    tests/test_bazi_baseline_dst_fold.py \
    tests/test_bazi_baseline_inventory.py \
    tests/test_constants.py \
    -q
```

Expected: all green.

### Step 7 — Commit

```bash
git add bazi_engine/bazi.py tests/test_bazi_zi_day_boundary.py
git commit -m "$(cat <<'EOF'
feat(bazi): Zi-day boundary uses effective TLST when ruleset says so (FBP-02-004)

Today apply_day_boundary("zi") naively returns dt + 1h regardless of
the request's time standard. The ruleset's `day_change_policy` block
declares `time_standard_for_day_rollover: "TLST"` (in the shipped
standard_bazi_2026 ruleset) and `zi_start_hour: 23.0`, but the engine
ignored both.

Phase 2 wires the policy through compute_bazi():
- When `inp.day_boundary == "zi"` AND `inp.time_standard == "TLST"`
  AND the ruleset opts into TLST rollover, the boundary is computed
  from `ctx.tlst_hours >= zi_start_hour` (HALF_OPEN convention)
  instead of the legacy clock-based check.
- For CIVIL and LMT the legacy `apply_day_boundary` path is
  unchanged — pre-Phase-2 behavior preserved.

Test matrix: 22:59 / 23:00 / 00:59 / 01:00 × {CIVIL, LMT, TLST},
parametrized as 12 cases, locks the boundary semantics per standard.
Without the helper, TLST cases at 22:59/23:00 silently follow the
civil-time path and produce wrong rollover.

v1 regression intact (14-case baseline passes bit-identically). Closes
FBP-02-004.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 4 — Push the trio

### Step 1 — Sanity sweep

```bash
uv run python -m pytest \
    tests/test_month_boundary_scheme_vestigial.py \
    tests/test_bazi_tlst_hour_pillar.py \
    tests/test_bazi_zi_day_boundary.py \
    tests/test_bazi_rules.py \
    tests/test_regression_v1_compatibility.py \
    tests/test_openapi_contract.py \
    -q
```

Expected: green.

### Step 2 — OpenAPI drift check

```bash
uv run python scripts/export_openapi.py --check
```

Expected: `OK: OpenAPI spec is up-to-date.` (No new fields visible to OpenAPI; the trace is still `Dict[str, Any]`.)

### Step 3 — Pre-push divergence check

```bash
git fetch origin main
git log --oneline origin/main..HEAD
git merge-base --is-ancestor origin/main HEAD && echo "OK: fast-forward"
```

Expected: 3 local commits ahead of origin (one per task), fast-forward shape.

### Step 4 — Push

```bash
git push
```

Expected: `81e7752..<HEAD> main -> main`.

---

## Stop-gates (Release-Gate §1 Phase 2 → Phase 3)

After this plan, of the 8 Phase-2 tasks:

| ID | Status after plan |
|---|---|
| FBP-02-001 | ✅ Done (already) |
| FBP-02-002 | ⬜ DOMAIN-BLOCKED — DEV-2026-004 needs human verifier |
| FBP-02-003 | ⬜ DOMAIN-BLOCKED — Anchor verification gate |
| FBP-02-004 | ✅ Done (this plan, Task 3) |
| FBP-02-005 | ✅ Done (this plan, Task 2) |
| FBP-02-006 | ✅ Done (this plan, Task 1) |
| FBP-02-007 | ⬜ DOMAIN-BLOCKED — External oracle cases |
| FBP-02-008 | ✅ Done (already) |

→ Phase 2 is **6 of 8 done**. The remaining three need a domain reviewer (not engineering work). Phase 3 (typed derivation trace, RFC 9457 errors, OpenAPI v2 contract) can start in parallel with the domain review.

## Out of scope

- Anything requiring domain review (FBP-02-002, -003, -007). The plan does not change ruleset content or oracle data.
- Phase 3 work (typed traces, provenance model IDs). That's a separate plan.

## Estimated wall-clock

~2.5–3 hours including verification + push.
