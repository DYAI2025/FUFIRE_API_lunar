# FuFirE Hardening & B2B-Readiness Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Eliminate the four audit-confirmed P0 failure paths (Ascendant naming-mismatch, Mercury day/night cascade, silent fallbacks, OpenAPI / request-binding integrity), wire `H_calibrated` and a per-planet Contribution Ledger as the documented audit surface, then prune redundant tests and seed B2B-tier extensibility (Tenant Layer + Artifact Referencing) — without changing any frozen `/v1/*` response paths.

**Architecture:**
1. **Single source of truth for chart data:** `compute_western_chart()` returns `{"angles": ..., "houses": ...}`. Every consumer reads `western["angles"]["Ascendant"]`. Legacy `ascmc` lookups are deleted, not aliased.
2. **Explicit quality contract:** A `quality_flags` block — sibling to `provenance` — is added to every `/calculate/*` and `/v1/experience/*` response. Silent cascades become `{house_system_fallback: true, requested: "placidus", used: "porphyry", reason: "high_latitude"}` etc. The frozen surface is preserved (existing fields stay), only additive.
3. **Contribution Ledger as a sub-block of provenance**, not a new endpoint — keeps the contract additive.
4. **Test hygiene:** consolidate the 79 test files using a coverage-by-feature matrix (Phase G) rather than guessing which are redundant.

**Tech Stack:** FastAPI, Pydantic, Swiss Ephemeris (`pyswisseph`), `slowapi`, `pytest`, JSON Schema Draft-07.

**References:**
- `~/Downloads/FlashDocs/md/technischer_audit_bericht_korrektur_fehlerhafter_.md` — bug catalogue
- `~/Downloads/FlashDocs/md/technischer_audit_bericht_analyse_struktureller_s.md` — strategic context
- `~/Downloads/FlashDocs/md/strategiebericht_nachhaltige_schlie_ung_der_opena.md` — OpenAPI roadmap
- `CLAUDE.md` — Module hierarchy, frozen-endpoint rule, gotchas

---

## Phase Overview

| Phase | Theme | P | Tasks |
|-------|-------|---|-------|
| A | Datenintegrität (Ascendant + Mercury) | P0 | 1–6 |
| B | Anti-Silent-Fallback (Quality Flags) | P0 | 7–11 |
| C | Sprach- & Enum-Konsistenz | P0 | 12–14 |
| D | OpenAPI / Request-Binding Hardening | P0 | 15–18 |
| E | Provenance & Contribution Ledger | P1 | 19–22 |
| F | H_calibrated als Primary Signal | P1 | 23–25 |
| G | Test-Hygiene & Redundanz-Audit | P1 | 26–29 |
| H | B2B Tenant Layer & Artifact Referencing (Design only) | P2 | 30–32 |

**Discipline for every task:**
- TDD: write the failing test first; run it; confirm the *expected failure mode*; then implement minimum code to flip it green.
- Commit per task. Use Conventional Commits (`fix:`, `feat:`, `test:`, `refactor:`, `docs:`, `chore:`).
- After every behaviour-changing task, run `python scripts/export_openapi.py --check`. If it drifts, regenerate and include in the same commit.
- After each phase: full `pytest -q` and `ruff check bazi_engine/ --output-format=github` and `mypy bazi_engine --ignore-missing-imports`. CI must stay green.

---

# Phase A — Datenintegrität (P0)

The Ascendant naming-mismatch (`ascmc` queried, `angles` returned) silently strips birth-time precision from every `/v1/experience/*` response and cascades into the Mercury day/night logic. The chart_type_quality flag exists at the `wuxing` layer (see `bazi_engine/wuxing/analysis.py:86`) but never reaches the experience layer because the input is wrong. Fix the data flow first, then the visibility.

### Task 1: Reproduce the Ascendant bug with a failing test

**Files:**
- Create: `tests/test_experience_ascendant_wiring.py`

**Step 1: Write the failing test**

```python
# tests/test_experience_ascendant_wiring.py
"""Regression: routers/experience.py must read western['angles']['Ascendant'],
not the legacy western.get('ascmc'). Audit ref: technischer_audit_bericht_korrektur_fehlerhafter_.md"""

import pytest
from fastapi.testclient import TestClient
from bazi_engine.app import create_app


@pytest.fixture
def client():
    return TestClient(create_app())


def _daily_payload():
    # Berlin midday, ephemeris-friendly
    return {
        "natal": {
            "date": "1990-06-15T14:30:00",
            "tz": "Europe/Berlin",
            "lon": 13.405,
            "lat": 52.52,
            "birth_time_known": True,
        },
        "today": "2026-05-09",
    }


def test_daily_response_marks_chart_as_exact_when_birth_time_known(client):
    """If a precise birth time is supplied, the experience endpoint must NOT
    fall back to assumed_day. This proves the angles->ascendant wiring."""
    res = client.post("/v1/experience/daily", json=_daily_payload())
    assert res.status_code == 200, res.text
    body = res.json()
    quality = body.get("quality_flags") or body.get("quality") or {}
    chart_type_quality = quality.get("chart_type_quality") or body.get("chart_type_quality")
    assert chart_type_quality == "exact", (
        f"Expected 'exact' (Ascendant must be wired through), got {chart_type_quality!r}. "
        f"Symptom of the ascmc/angles naming mismatch."
    )
```

> Note: the assertion accepts either a top-level `chart_type_quality` (current shape) or a nested `quality_flags.chart_type_quality` (Phase B target). The check is forgiving so the test stays green after Task 7 introduces the nested form.

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_experience_ascendant_wiring.py -v`
Expected: FAIL with `assumed_day != exact` (because `ascmc` lookup returns `None` → `ascendant=None` → `chart_type_quality="assumed_day"`).

**Step 3: Fix the consumer in `routers/experience.py`**

Edit `bazi_engine/routers/experience.py:330`:

```python
# OLD
ascendant = western.get("ascmc", [0])[0] if western.get("ascmc") else None

# NEW
angles = western.get("angles") or {}
ascendant = angles.get("Ascendant")
```

Then grep the file for any other `ascmc` usages and replace each:

```bash
grep -n "ascmc" bazi_engine/routers/experience.py
```

If any survive, replace with `angles.get("<KeyName>")` using the keys produced by `bazi_engine/western.py:138-141` (`Ascendant`, `MC`, `Vertex`).

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_experience_ascendant_wiring.py -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add tests/test_experience_ascendant_wiring.py bazi_engine/routers/experience.py
git commit -m "fix(experience): read Ascendant from western['angles'], not ascmc

The audit-reported P0 bug: routers/experience.py looked for
western.get('ascmc') while compute_western_chart() returns 'angles'.
Result: ascendant=None for every request, triggering an assumed_day
fallback that silently discards birth-time precision."
```

### Task 2: Audit and exterminate every other `ascmc` consumer

**Files:**
- Modify: any file matched below
- Test: `tests/test_no_legacy_ascmc_references.py` (new)

**Step 1: Inventory remaining `ascmc` usages**

Run:

```bash
grep -rnE "\.get\(['\"]ascmc['\"]|\bascmc\b" bazi_engine/ tests/ \
  | grep -v __pycache__ \
  | grep -v "western.py:" \
  | grep -v "ascmc = " \
  | grep -v "ascmc\[" \
  | grep -v "if ascmc"
```

Expected: nothing in `bazi_engine/` outside `western.py` (which legitimately uses `ascmc` as the local variable returned by Swiss Ephemeris). If anything else appears, treat each line as a follow-up edit.

**Step 2: Write the lint-style guard test**

```python
# tests/test_no_legacy_ascmc_references.py
"""Guard: no consumer outside compute_western_chart() may read 'ascmc' from a
chart dict. The legacy field never existed; every prior usage was a bug."""

import pathlib
import re

FORBIDDEN = re.compile(r"""\.get\(['"]ascmc['"]""")


def test_no_consumer_reads_ascmc():
    root = pathlib.Path(__file__).resolve().parents[1] / "bazi_engine"
    offenders = []
    for path in root.rglob("*.py"):
        if path.name == "western.py":
            continue
        text = path.read_text(encoding="utf-8")
        for lineno, line in enumerate(text.splitlines(), 1):
            if FORBIDDEN.search(line):
                offenders.append(f"{path.relative_to(root.parent)}:{lineno}: {line.strip()}")
    assert not offenders, "Legacy ascmc consumers remain:\n" + "\n".join(offenders)
```

**Step 3: Run test**

Run: `pytest tests/test_no_legacy_ascmc_references.py -v`
Expected: PASS (Task 1 already removed the only offender). If FAIL, fix the listed offenders by replacing with `angles.get(...)` per the western.py output keys.

**Step 4: Commit**

```bash
git add tests/test_no_legacy_ascmc_references.py
git commit -m "test(experience): guard against legacy ascmc field re-introduction"
```

### Task 3: Write a real-ephemeris Mercury day/night regression test

The existing `tests/test_mercury_quality.py` checks the *flag*, not the *element switch*. We need a paired night-vs-day-birth assertion that proves Mercury moves from Earth to Metal as expected.

**Files:**
- Create: `tests/test_mercury_day_night_regression.py`

**Step 1: Write the failing test**

```python
# tests/test_mercury_day_night_regression.py
"""Mercury must be Earth on day charts, Metal on night charts. Pre-fix this
failed because the experience layer always passed ascendant=None."""

import os
import pytest
from fastapi.testclient import TestClient
from bazi_engine.app import create_app

pytestmark = pytest.mark.skipif(
    not os.environ.get("SE_EPHE_PATH"),
    reason="Swiss Ephemeris files not configured",
)


@pytest.fixture
def client():
    return TestClient(create_app())


def _payload(date_iso, tz, lon, lat):
    return {
        "natal": {"date": date_iso, "tz": tz, "lon": lon, "lat": lat,
                  "birth_time_known": True},
        "today": "2026-05-09",
    }


def _mercury_element(daily_response: dict) -> str:
    """Locate Mercury's wu-xing element in whatever shape the response uses."""
    # Adjust the lookup to match the live response shape if needed.
    fusion = daily_response.get("fusion") or daily_response.get("western") or {}
    breakdown = fusion.get("element_breakdown") or fusion.get("contributions") or []
    for entry in breakdown:
        if entry.get("planet") == "Mercury":
            return entry.get("element") or entry.get("wuxing_element")
    raise AssertionError(f"Mercury entry not found in {daily_response!r}")


def test_mercury_is_earth_on_clear_day_birth(client):
    # Berlin noon — Sun strongly above horizon, Ascendant in the day arc
    body = client.post("/v1/experience/daily",
                       json=_payload("1990-06-15T12:00:00", "Europe/Berlin", 13.405, 52.52)).json()
    assert _mercury_element(body) == "Earth"


def test_mercury_is_metal_on_clear_night_birth(client):
    # Berlin midnight — Sun strongly below horizon
    body = client.post("/v1/experience/daily",
                       json=_payload("1990-06-15T00:00:00", "Europe/Berlin", 13.405, 52.52)).json()
    assert _mercury_element(body) == "Metal"
```

**Step 2: Run test to verify the helper finds Mercury**

Run: `SE_EPHE_PATH=/usr/local/share/swisseph pytest tests/test_mercury_day_night_regression.py -v`
Expected outcomes:
- If `_mercury_element` raises `AssertionError` because the live response shape doesn't match — adjust `_mercury_element` to the actual shape (inspect `bazi_engine/routers/experience.py` ~lines 593–700 to find what the daily endpoint returns).
- If both tests fail with `Earth != Metal` on the night case — confirms the post-Task-1 wiring still has gaps; investigate `is_night_chart()` call site.

This is not a "make it pass" task in one shot — it's the *probe*. Once both tests pass, the bug is genuinely killed.

**Step 3: If Mercury element is not surfaced in the daily response, skip the assertion and use the lower-level endpoint**

If the daily response does not expose per-planet element data, replace with calls to `/v1/calculate/wuxing` for the same two timestamps and assert on `entry["element"]` for `entry["planet"]=="Mercury"`. Read `bazi_engine/routers/western.py` or `bazi_engine/routers/fusion.py` to find the right endpoint.

**Step 4: Commit**

```bash
git add tests/test_mercury_day_night_regression.py
git commit -m "test(mercury): real-ephemeris day vs night regression for the fusion path

Pre-fix this would have shown Mercury locked to Earth for both
day and night charts because experience.py never resolved the Ascendant."
```

### Task 4: Tighten `is_night_chart` to fail loud when ascendant is missing in trusted contexts

`bazi_engine/wuxing/analysis.py:32` currently silently defaults to day chart when the ascendant is `None`. After Task 1 the ascendant should always be present, so a `None` arrival means the caller has a bug. Add an opt-in strict mode.

**Files:**
- Modify: `bazi_engine/wuxing/analysis.py`
- Test: extend `tests/test_mercury_quality.py`

**Step 1: Write failing test**

Add to `tests/test_mercury_quality.py`:

```python
def test_is_night_chart_strict_raises_when_ascendant_missing():
    from bazi_engine.wuxing.analysis import is_night_chart
    import pytest
    with pytest.raises(ValueError, match="ascendant"):
        is_night_chart(sun_longitude=120.0, ascendant=None, strict=True)


def test_is_night_chart_lenient_still_defaults_to_day():
    from bazi_engine.wuxing.analysis import is_night_chart
    assert is_night_chart(sun_longitude=120.0, ascendant=None, strict=False) is False
```

**Step 2: Run test**

Run: `pytest tests/test_mercury_quality.py -k "is_night_chart" -v`
Expected: FAIL — `strict` kwarg unknown.

**Step 3: Implement**

Edit `bazi_engine/wuxing/analysis.py:32`:

```python
def is_night_chart(sun_longitude: float, ascendant: Optional[float] = None,
                   strict: bool = False) -> bool:
    """Determine whether this is a night chart.

    Without an Ascendant, defaults to day chart (False) for back-compat,
    UNLESS strict=True, which raises ValueError. Trusted-tier callers
    must pass strict=True so silent fallbacks never reach paying B2B partners.
    """
    if ascendant is None:
        if strict:
            raise ValueError("ascendant is required in strict mode")
        return False
    # ... existing logic
```

**Step 4: Wire `strict=True` in trusted callers**

Find every call:

```bash
grep -rn "is_night_chart(" bazi_engine/ | grep -v analysis.py
```

For each call inside `routers/*.py` (B2B-facing), pass `strict=True`. Free-tier or research callers stay lenient.

**Step 5: Run full suite**

Run: `pytest -q`
Expected: PASS. If a router-level test fails because some legitimate path lacks ascendant, that path needs to either supply ascendant or accept the lenient call explicitly. Don't paper over it — investigate.

**Step 6: Commit**

```bash
git add bazi_engine/wuxing/analysis.py tests/test_mercury_quality.py bazi_engine/routers/
git commit -m "feat(wuxing): strict mode for is_night_chart in trusted-tier callers

Lenient default preserves back-compat for research/free paths.
Trusted endpoints (paid /v1/*) must pass strict=True so a missing
Ascendant triggers a 5xx instead of silently mis-classifying half of
all night-born users as day charts."
```

### Task 5: Make `chart_type_quality` flow up to `/v1/experience/*` responses

`chart_type_quality` is computed in `wuxing/analysis.py:86` and `fusion.py:159` but is not surfaced at the experience layer. Bubble it up.

**Files:**
- Modify: `bazi_engine/routers/experience.py` (response assembly around line 593+)
- Test: extend `tests/test_experience_ascendant_wiring.py`

**Step 1: Write the failing test**

Extend `tests/test_experience_ascendant_wiring.py`:

```python
def test_daily_response_includes_chart_type_quality_when_birth_time_unknown(client):
    payload = _daily_payload()
    payload["natal"]["birth_time_known"] = False
    payload["natal"].pop("date")  # date-only
    payload["natal"]["date"] = "1990-06-15"
    res = client.post("/v1/experience/daily", json=payload)
    assert res.status_code == 200
    body = res.json()
    quality = body.get("quality_flags") or {}
    assert (body.get("chart_type_quality") == "assumed_day"
            or quality.get("chart_type_quality") == "assumed_day")
```

**Step 2: Run test**

Run: `pytest tests/test_experience_ascendant_wiring.py -v`
Expected: FAIL — field absent from response body.

**Step 3: Implement**

In `bazi_engine/routers/experience.py`, locate the daily response builder (around `experience_daily()`). Add `chart_type_quality` derived from whether `ascendant` is `None`:

```python
chart_type_quality = "exact" if ascendant is not None else "assumed_day"
response_body["chart_type_quality"] = chart_type_quality  # additive, frozen surface preserved
```

(Phase B will move this into a `quality_flags` block; for now we add it as a top-level field so the test passes and downstream consumers can see it immediately.)

**Step 4: Run all experience tests**

Run: `pytest tests/test_experience_*.py -v`
Expected: PASS. Update any snapshot files that assert on the absence of this key.

**Step 5: Regenerate OpenAPI**

Run: `python scripts/export_openapi.py`
Verify: a new `chart_type_quality` field appears in the daily response schema.

**Step 6: Commit**

```bash
git add bazi_engine/routers/experience.py tests/test_experience_ascendant_wiring.py spec/openapi/openapi.json tests/snapshots/
git commit -m "feat(experience): surface chart_type_quality at /v1/experience/daily

Additive: paid B2B integrators can now distinguish exact (birth time
supplied + Ascendant resolved) from assumed_day (date-only or wiring
broken). No frozen field renamed."
```

### Task 6: Phase A guardrail — full regression run

**Step 1:** `pytest -q` — must pass with no skips beyond ephemeris-conditional tests.
**Step 2:** `ruff check bazi_engine/ --output-format=github` — clean.
**Step 3:** `mypy bazi_engine --ignore-missing-imports` — clean.
**Step 4:** `python scripts/export_openapi.py --check` — must report no drift.
**Step 5:** No commit; this is the gate.

---

# Phase B — Anti-Silent-Fallback (P0)

The cascading Placidus → Porphyry → Whole Sign substitution is *almost* surfaced (`western.py:115` already builds `{requested, used}`) but no boolean tells the consumer "you got a fallback". Add a `quality_flags` block — additive, sibling to `provenance`.

### Task 7: Add `quality_flags` block to western chart response

**Files:**
- Modify: `bazi_engine/western.py` (around line 173 where the response dict is assembled)
- Modify: `bazi_engine/routers/western.py` (around line 104 where the response is shaped)
- Modify: `bazi_engine/routers/shared.py` if needed (Pydantic model)
- Test: `tests/test_quality_flags_western.py` (new)

**Step 1: Write the failing test**

```python
# tests/test_quality_flags_western.py
import os
import pytest
from fastapi.testclient import TestClient
from bazi_engine.app import create_app

pytestmark = pytest.mark.skipif(
    not os.environ.get("SE_EPHE_PATH"),
    reason="Swiss Ephemeris files not configured",
)


@pytest.fixture
def client():
    return TestClient(create_app())


def _payload(lat):
    return {"date": "1990-06-15T12:00:00", "tz": "UTC", "lon": 0.0, "lat": lat}


def test_low_latitude_no_house_fallback(client):
    res = client.post("/v1/calculate/western", json=_payload(45.0))
    body = res.json()
    qf = body["quality_flags"]
    assert qf["house_system_fallback"] is False
    assert qf["house_system_used"] == "placidus"
    assert qf["house_system_requested"] == "placidus"


def test_extreme_latitude_triggers_explicit_fallback(client):
    res = client.post("/v1/calculate/western", json=_payload(78.0))
    body = res.json()
    qf = body["quality_flags"]
    assert qf["house_system_fallback"] is True
    assert qf["house_system_requested"] == "placidus"
    assert qf["house_system_used"] in ("porphyry", "whole_sign")
```

**Step 2: Run test**

Run: `pytest tests/test_quality_flags_western.py -v`
Expected: FAIL — `KeyError: 'quality_flags'`.

**Step 3: Implement at `bazi_engine/western.py`**

After the existing `house_system_meta` build (around line 110), add:

```python
quality_flags = {
    "house_system_fallback": used_label != requested_label,
    "house_system_requested": requested_label,
    "house_system_used": used_label,
    "ephemeris_mode": "SWIEPH",  # populated authoritatively by ephemeris.py
}
result["quality_flags"] = quality_flags
```

In `bazi_engine/routers/western.py`, add the field to the Pydantic response model so OpenAPI reflects it.

**Step 4: Update Pydantic model**

In `bazi_engine/routers/western.py` (or `routers/shared.py` if shared), add:

```python
class QualityFlags(BaseModel):
    house_system_fallback: bool
    house_system_requested: str
    house_system_used: str
    ephemeris_mode: Literal["SWIEPH", "MOSEPH"]
    chart_type_quality: Optional[Literal["exact", "assumed_day"]] = None
    model_config = ConfigDict(extra="forbid")

# in WesternResponse:
quality_flags: QualityFlags
```

**Step 5: Run tests**

Run: `pytest tests/test_quality_flags_western.py tests/test_western*.py -v`
Expected: PASS. Update snapshots if any `test_snapshot_stability.py` shapes broke (additive change, but snapshots may be exact).

**Step 6: Commit**

```bash
git add bazi_engine/western.py bazi_engine/routers/western.py tests/test_quality_flags_western.py tests/snapshots/
git commit -m "feat(western): add quality_flags block exposing house_system fallback"
```

### Task 8: Propagate `quality_flags` to fusion and experience responses

**Files:**
- Modify: `bazi_engine/routers/fusion.py`
- Modify: `bazi_engine/routers/experience.py`
- Test: `tests/test_quality_flags_propagation.py` (new)

**Step 1: Failing test**

```python
# tests/test_quality_flags_propagation.py
import os, pytest
from fastapi.testclient import TestClient
from bazi_engine.app import create_app

pytestmark = pytest.mark.skipif(not os.environ.get("SE_EPHE_PATH"), reason="ephemeris")


@pytest.fixture
def client():
    return TestClient(create_app())


def test_fusion_inherits_western_quality_flags(client):
    body = client.post("/v1/calculate/fusion", json={
        "date": "1990-06-15T12:00:00", "tz": "Europe/Berlin",
        "lon": 13.405, "lat": 52.52,
    }).json()
    assert body["quality_flags"]["house_system_used"] in {"placidus", "porphyry", "whole_sign"}


def test_daily_experience_includes_quality_flags(client):
    body = client.post("/v1/experience/daily", json={
        "natal": {"date": "1990-06-15T12:00:00", "tz": "Europe/Berlin",
                  "lon": 13.405, "lat": 52.52, "birth_time_known": True},
        "today": "2026-05-09",
    }).json()
    qf = body["quality_flags"]
    assert "chart_type_quality" in qf
    assert "house_system_fallback" in qf
```

**Step 2: Run test**

Expected: FAIL.

**Step 3: Implement**

In `routers/fusion.py`, when building the response, copy `western_chart["quality_flags"]` into the fusion response (and OR in any fusion-layer flags).

In `routers/experience.py`, do the same — and *move* (don't duplicate) the top-level `chart_type_quality` from Task 5 into `quality_flags`. Keep a top-level alias if any consumer already depends on it (check tests first via `grep -rn "chart_type_quality" tests/`).

**Step 4: Update Pydantic models**

`FusionResponse` and the daily-experience response model both need a `quality_flags: QualityFlags` field.

**Step 5: Run full suite + regenerate OpenAPI**

```bash
pytest -q
python scripts/export_openapi.py
```

**Step 6: Commit**

```bash
git add bazi_engine/routers/ tests/test_quality_flags_propagation.py spec/openapi/openapi.json tests/snapshots/
git commit -m "feat(api): propagate quality_flags through fusion and experience responses"
```

### Task 9: Forbid silent MOSEPH fallback in trusted-tier endpoints

`bazi_engine/ephemeris.py:31` already documents the intent. Verify it's enforced and tested.

**Files:**
- Modify: `bazi_engine/ephemeris.py`
- Test: `tests/test_ephemeris_strict.py` (extend if exists, else create)

**Step 1: Write failing test**

```python
# tests/test_ephemeris_strict.py
import pytest
from bazi_engine.ephemeris import SwissEphBackend
from bazi_engine.exc import EphemerisUnavailableError


def test_swieph_mode_rejects_silent_moseph_fallback(monkeypatch):
    """If swisseph silently returned MOSEPH flags despite a SWIEPH request,
    we MUST raise EphemerisUnavailableError, not return imprecise data."""
    backend = SwissEphBackend(mode="SWIEPH")
    # Force the backend's internal precision check to detect MOSEPH
    # (use the existing _verify_no_silent_fallback helper if present)
    with pytest.raises(EphemerisUnavailableError, match="MOSEPH"):
        # This requires a forced scenario; if the backend exposes a
        # _check_returned_flags helper, call it directly with FLG_MOSEPH set
        backend._check_returned_flags(returned_flags_with_moseph_bit=True)


def test_moseph_mode_explicitly_requested_does_not_raise(monkeypatch):
    backend = SwissEphBackend(mode="MOSEPH")
    backend._check_returned_flags(returned_flags_with_moseph_bit=True)  # OK
```

**Step 2: Run test**

Expected: FAIL — helper not exposed.

**Step 3: Implement**

In `bazi_engine/ephemeris.py`, around the existing `_verify_no_silent_fallback` logic (lines 31–115), expose a small public-but-underscored helper `_check_returned_flags(returned_flags_with_moseph_bit: bool)` that raises `EphemerisUnavailableError` when `self.mode == "SWIEPH"` and the bit is set.

**Step 4: Run tests**

```bash
pytest tests/test_ephemeris_strict.py -v
```

**Step 5: Commit**

```bash
git add bazi_engine/ephemeris.py tests/test_ephemeris_strict.py
git commit -m "fix(ephemeris): public helper for silent-MOSEPH detection + strict guard"
```

### Task 10: `birth_time_known=false` must NOT silently degrade — it must be a contract option

The audit demands no `assumed_day` fallback unless the *consumer explicitly opted in*. Add a 422 response when birth time is missing AND the consumer didn't set `birth_time_known: false`.

**Files:**
- Modify: `bazi_engine/routers/experience.py` (request validation)
- Modify: `bazi_engine/routers/shared.py` (Pydantic models — `BootstrapRequest`, `DailyRequest`, etc.)
- Test: `tests/test_natal_input_strictness.py` (new)

**Step 1: Failing test**

```python
# tests/test_natal_input_strictness.py
from fastapi.testclient import TestClient
from bazi_engine.app import create_app


def test_date_only_without_explicit_opt_in_returns_422():
    client = TestClient(create_app())
    # Missing time AND no birth_time_known flag → reject
    res = client.post("/v1/experience/daily", json={
        "natal": {"date": "1990-06-15", "tz": "Europe/Berlin",
                  "lon": 13.405, "lat": 52.52},
        "today": "2026-05-09",
    })
    assert res.status_code == 422
    assert "birth_time_known" in res.text


def test_date_only_with_explicit_opt_in_returns_200_and_assumed_day():
    client = TestClient(create_app())
    res = client.post("/v1/experience/daily", json={
        "natal": {"date": "1990-06-15", "tz": "Europe/Berlin",
                  "lon": 13.405, "lat": 52.52,
                  "birth_time_known": False},
        "today": "2026-05-09",
    })
    assert res.status_code == 200
    assert res.json()["quality_flags"]["chart_type_quality"] == "assumed_day"
```

**Step 2: Run test**

Expected: first assertion fails (returns 200 today).

**Step 3: Implement**

In `bazi_engine/routers/shared.py`, add a Pydantic root validator on the `NatalInput` model (or whatever it's called — discover via `grep -n "natal" bazi_engine/routers/shared.py`):

```python
@model_validator(mode="after")
def require_explicit_opt_in_for_date_only(self):
    has_time = "T" in self.date  # ISO-8601 dates with time include 'T'
    if not has_time and self.birth_time_known is None:
        raise ValueError(
            "Birth time missing. Set birth_time_known=false to opt into "
            "assumed_day quality, or supply an ISO-8601 datetime."
        )
    return self
```

**Step 4: Run tests**

```bash
pytest tests/test_natal_input_strictness.py tests/test_experience_*.py -v
```

Expected: PASS. Adjust any other test that previously sent date-only without `birth_time_known` — they're carrying the bug forward.

**Step 5: Commit**

```bash
git add bazi_engine/routers/shared.py tests/test_natal_input_strictness.py
git commit -m "feat(api): require explicit birth_time_known=false for date-only natal input

No more silent assumed_day. Consumers must opt into degraded precision."
```

### Task 11: Phase B regression gate

**Step 1:** `pytest -q` — green.
**Step 2:** `python scripts/export_openapi.py --check` — drift handled in tasks above; if it fails, regenerate and commit as `chore(openapi): regenerate after Phase B`.

---

# Phase C — Sprach- & Enum-Konsistenz (P0)

The audit calls out mixed German/English in keys/enums (e.g., `strength: "stark"` vs `"strong"`). British English is the standard for technical keys.

### Task 12: Inventory German strings in API responses

**Files:**
- Create: `tests/test_no_german_in_api_responses.py`

**Step 1: Probe**

Run:

```bash
grep -rnE '"(stark|leicht|mittel|niedrig|hoch|kalt|warm|aufsteigend|absteigend)"' \
  bazi_engine/ \
  | grep -v __pycache__ \
  | grep -v "wuxing/constants.py" \
  | grep -v "test_"
```

Document every offender. They divide into two buckets:
- **Internal labels** (Wu-Xing element names like "Erde"/"Metall") — these are domain terminology; document them as exceptions in the test.
- **API enum values** (e.g., `strength="stark"` returned from a router) — must be replaced with British English.

**Step 2: Write the guard test**

```python
# tests/test_no_german_in_api_responses.py
"""All public API enum/string values must use British English. Wu-Xing element
names are domain terminology — German remains by design (Holz/Feuer/Erde/Metall/Wasser)."""

import os, pytest
from fastapi.testclient import TestClient
from bazi_engine.app import create_app

GERMAN_ENUM_TOKENS = {"stark", "leicht", "mittel", "niedrig", "schwach",
                      "aufsteigend", "absteigend", "ruhend"}

ALLOWED_DOMAIN_TERMS = {"Holz", "Feuer", "Erde", "Metall", "Wasser",
                        "Yang", "Yin"}  # exempt: Wu-Xing element names


def _walk_strings(obj, path=""):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from _walk_strings(v, f"{path}.{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from _walk_strings(v, f"{path}[{i}]")
    elif isinstance(obj, str):
        yield path, obj


@pytest.mark.skipif(not os.environ.get("SE_EPHE_PATH"), reason="ephemeris")
def test_daily_response_has_no_german_enum_values():
    client = TestClient(create_app())
    body = client.post("/v1/experience/daily", json={
        "natal": {"date": "1990-06-15T12:00:00", "tz": "Europe/Berlin",
                  "lon": 13.405, "lat": 52.52, "birth_time_known": True},
        "today": "2026-05-09",
    }).json()

    offenders = []
    for path, value in _walk_strings(body):
        token = value.lower().strip()
        if token in GERMAN_ENUM_TOKENS and value not in ALLOWED_DOMAIN_TERMS:
            offenders.append(f"{path}={value!r}")
    assert not offenders, "German enum values in API response: " + ", ".join(offenders)
```

**Step 3: Run test**

Run: `pytest tests/test_no_german_in_api_responses.py -v`
Document failures. They drive Task 13.

**Step 4: Commit the test alone (it's diagnostic)**

```bash
git add tests/test_no_german_in_api_responses.py
git commit -m "test(api): guard against German enum values in public responses"
```

### Task 13: Replace each German enum value flagged in Task 12

**Files:** depends on what Task 12 found. Likely candidates: `bazi_engine/services/daily_*.py`, `bazi_engine/routers/experience.py`, `bazi_engine/wuxing/zones.py`.

**Process per offender (repeat as needed):**

1. Decide the British English replacement (`stark` → `strong`, `leicht` → `mild`, `mittel` → `moderate`, `niedrig` → `low`, `aufsteigend` → `ascending`, `absteigend` → `descending`, `ruhend` → `dormant`).
2. Update the source. If the value is in a translation lookup table, prefer adding an English key alongside or replacing the German entirely.
3. Rerun `pytest tests/test_no_german_in_api_responses.py` until it passes.
4. **Important:** check for translation/i18n usage. If German strings are also used in user-facing text (which they should be), keep them in `bazi_engine/data/translations/` (or wherever the i18n table lives) and reference via key, not direct enum value.

**Commit per logical batch:**

```bash
git commit -m "refactor(api): replace German enum values in <module> with British English"
```

### Task 14: Phase C regression gate

**Step 1:** `pytest -q` — green.
**Step 2:** Snapshot files under `tests/snapshots/` likely contain the German values. Regenerate with `pytest --snapshot-update tests/test_snapshot_stability.py` (verify the command in the test file's docstring) **only after** confirming the new values are correct.

---

# Phase D — OpenAPI / Request-Binding Hardening (P0)

The audit cites a syntax error at line 3858 (likely already fixed, since `python scripts/export_openapi.py --check` is in CI) and `slowapi` decorator misuse causing 422 errors. Verify both, lock them in.

### Task 15: Validate the live OpenAPI spec

**Files:**
- Create: `tests/test_openapi_spec_is_valid_jsonschema.py` (or extend existing `test_openapi_contract.py`)

**Step 1: Failing test**

First check: does `openapi-spec-validator` exist as a dep?

```bash
grep -E "openapi-spec-validator|openapi_spec_validator" pyproject.toml uv.lock
```

If not, add to `[project.optional-dependencies] dev` in `pyproject.toml`.

```python
# tests/test_openapi_spec_is_valid_jsonschema.py
import json
import pathlib
import pytest

openapi_spec_validator = pytest.importorskip("openapi_spec_validator")


def test_openapi_spec_is_structurally_valid():
    spec_path = pathlib.Path(__file__).resolve().parents[1] / "spec" / "openapi" / "openapi.json"
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    openapi_spec_validator.validate(spec)
```

**Step 2: Run**

```bash
pip install openapi-spec-validator  # if not already installed
pytest tests/test_openapi_spec_is_valid_jsonschema.py -v
```

Expected: PASS (the audit's line-3858 bracket bug is likely from a snapshot at a moment of in-progress edits — the current file passes `--check`). If it FAILS, the validator output will name the offending JSONPath; fix manually with `Read`/`Edit` of `spec/openapi/openapi.json`, then regenerate via `python scripts/export_openapi.py`.

**Step 3: Commit**

```bash
git add tests/test_openapi_spec_is_valid_jsonschema.py pyproject.toml uv.lock
git commit -m "test(openapi): structural JSONSchema validation guard

Blocks contract-breaking syntax bugs (e.g., '}' instead of ']' that
SDK generators choke on)."
```

### Task 16: Audit `slowapi` decorators for 422-causing binding mistakes

The audit reports 422s on POST endpoints because slowapi decorators may have been wrapping handlers in a way that breaks Pydantic body parsing. The current code (verified pre-plan) already has `request: Request` parameters — but make this an enforced contract.

**Files:**
- Create: `tests/test_rate_limited_endpoints_accept_post_bodies.py`

**Step 1: Failing test**

```python
# tests/test_rate_limited_endpoints_accept_post_bodies.py
"""Every @limiter.limit POST endpoint must successfully parse its body, not
422. Audit reported slowapi decorators were converting body params into query
params for some handlers."""

import importlib, inspect, pkgutil
import pytest
from fastapi.testclient import TestClient
from bazi_engine.app import create_app


def _all_post_routes():
    app = create_app()
    for r in app.routes:
        methods = getattr(r, "methods", None) or set()
        if "POST" in methods:
            yield r.path, r.endpoint


@pytest.mark.parametrize("path,endpoint", list(_all_post_routes()))
def test_post_endpoint_signature_uses_request_kw(path, endpoint):
    """slowapi-decorated handlers must accept `request: Request`. If the kw
    is absent, slowapi mis-binds body params to query."""
    sig = inspect.signature(endpoint)
    has_request = any(p.name == "request" for p in sig.parameters.values())
    is_rate_limited = getattr(endpoint, "__wrapped__", None) is not None
    if is_rate_limited:
        assert has_request, f"POST {path}: rate-limited handler missing `request: Request`"
```

**Step 2: Run test**

```bash
pytest tests/test_rate_limited_endpoints_accept_post_bodies.py -v
```

Document any failures (likely none, given the current grep showed `request: Request` everywhere — but this test stops the regression).

**Step 3: For each failing endpoint, add `request: Request` as the first positional parameter**

Pattern to follow (already used in `routers/bazi.py:159`):

```python
def calculate_bazi_endpoint(request: Request, req: BaziRequest) -> Dict[str, Any]:
```

**Step 4: Commit**

```bash
git add tests/test_rate_limited_endpoints_accept_post_bodies.py bazi_engine/routers/
git commit -m "test(routers): enforce request-kw on every rate-limited POST handler"
```

### Task 17: Live POST round-trip smoke test

**Files:**
- Create: `tests/test_v1_post_endpoints_smoke.py`

**Step 1: Test code**

```python
# tests/test_v1_post_endpoints_smoke.py
"""Every /v1/* POST endpoint accepts a minimal valid body and returns non-422.
Catches the audit's reported 'API faktisch unbenutzbar' regression class."""

import os, pytest
from fastapi.testclient import TestClient
from bazi_engine.app import create_app

pytestmark = pytest.mark.skipif(not os.environ.get("SE_EPHE_PATH"), reason="ephemeris")

NATAL = {"date": "1990-06-15T12:00:00", "tz": "Europe/Berlin",
         "lon": 13.405, "lat": 52.52, "birth_time_known": True}

PAYLOADS = {
    "/v1/calculate/bazi": NATAL,
    "/v1/calculate/western": NATAL,
    "/v1/calculate/wuxing": NATAL,
    "/v1/calculate/fusion": NATAL,
    "/v1/calculate/tst": NATAL,
    "/v1/experience/daily": {"natal": NATAL, "today": "2026-05-09"},
    # Add others as discovered via app.routes inspection
}


@pytest.fixture
def client():
    return TestClient(create_app())


@pytest.mark.parametrize("path,body", list(PAYLOADS.items()))
def test_post_returns_non_422(client, path, body):
    res = client.post(path, json=body)
    assert res.status_code != 422, (
        f"POST {path} returned 422; body parsed as query? "
        f"Response: {res.text[:500]}"
    )
```

**Step 2: Run test**

```bash
pytest tests/test_v1_post_endpoints_smoke.py -v
```

**Step 3: Fix any 422s found** — investigate per endpoint.

**Step 4: Commit**

```bash
git add tests/test_v1_post_endpoints_smoke.py
git commit -m "test(v1): smoke-test every POST endpoint accepts its body"
```

### Task 18: Phase D gate — full CI parity

**Step 1:** `pytest -q --cov=bazi_engine --cov-fail-under=75`
**Step 2:** `ruff check bazi_engine/ --output-format=github`
**Step 3:** `mypy bazi_engine --ignore-missing-imports`
**Step 4:** `python scripts/export_openapi.py --check`
**Step 5:** `python scripts/check_complexity.py` (if it exists; check `scripts/`)

---

# Phase E — Provenance & Contribution Ledger (P1)

`provenance.py` exists and is included on `/calculate/*`. Extend it with `tzdb_version`, `parameter_set_id`, and an `ephemeris_id` (SHA256 of the loaded ephemeris files). Then build the per-planet/pillar Wu-Xing Contribution Ledger.

### Task 19: Add `tzdb_version` and `ephemeris_id` to provenance

**Files:**
- Modify: `bazi_engine/provenance.py`
- Test: `tests/test_provenance.py` (extend)

**Step 1: Failing test**

Extend `tests/test_provenance.py`:

```python
def test_provenance_includes_tzdb_version():
    from bazi_engine.provenance import build_provenance
    prov = build_provenance(house_system="P", ephemeris_mode="SWIEPH")
    assert "tzdb_version" in prov
    assert prov["tzdb_version"]  # non-empty string


def test_provenance_includes_ephemeris_id():
    from bazi_engine.provenance import build_provenance
    prov = build_provenance(house_system="P", ephemeris_mode="SWIEPH")
    assert "ephemeris_id" in prov
    assert len(prov["ephemeris_id"]) >= 16  # short hash or fingerprint
```

**Step 2: Run test**

Expected: FAIL.

**Step 3: Implement in `bazi_engine/provenance.py`**

```python
import hashlib
import os
from functools import lru_cache

# tzdata: prefer importlib.resources; fall back to /usr/share/zoneinfo metadata
@lru_cache(maxsize=1)
def _tzdb_version() -> str:
    try:
        import tzdata
        return tzdata.__version__
    except ImportError:
        # System tzdb — read /usr/share/zoneinfo/+VERSION if present
        path = "/usr/share/zoneinfo/+VERSION"
        if os.path.exists(path):
            return open(path).read().strip()
        return "unknown"


@lru_cache(maxsize=1)
def _ephemeris_id(ephe_path: str | None = None) -> str:
    """SHA256 over concatenated checksums of the four required Swiss
    Ephemeris files. Cached because file I/O is slow."""
    base = ephe_path or os.environ.get("SE_EPHE_PATH", "/usr/local/share/swisseph")
    files = ["sepl_18.se1", "semo_18.se1", "seas_18.se1", "seplm06.se1"]
    h = hashlib.sha256()
    for fname in files:
        fpath = os.path.join(base, fname)
        if not os.path.exists(fpath):
            return "unavailable"
        with open(fpath, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
    return h.hexdigest()[:16]
```

Then add to `build_provenance(...)`:

```python
prov["tzdb_version"] = _tzdb_version()
prov["ephemeris_id"] = _ephemeris_id()
```

**Step 4: Run tests**

```bash
pytest tests/test_provenance.py -v
```

**Step 5: Commit**

```bash
git add bazi_engine/provenance.py tests/test_provenance.py
git commit -m "feat(provenance): include tzdb_version and ephemeris_id (sha256)"
```

### Task 20: Add `parameter_set_id` to provenance

**Step 1: Failing test**

```python
def test_provenance_includes_parameter_set_id():
    from bazi_engine.provenance import build_provenance
    prov = build_provenance(house_system="P", ephemeris_mode="SWIEPH",
                            parameter_set_id="WUXING_PARAMETER_SET_v3")
    assert prov["parameter_set_id"] == "WUXING_PARAMETER_SET_v3"
```

**Step 2: Run** → FAIL.

**Step 3: Implement** — accept `parameter_set_id` as a kwarg to `build_provenance`, default to the constant defined in `bazi_engine/wuxing/calibration.py` or wherever the parameter set is named. Surface it in routers (`routers/fusion.py`, `routers/wuxing` if separate).

**Step 4: Commit**

```bash
git commit -m "feat(provenance): expose parameter_set_id"
```

### Task 21: Wu-Xing Contribution Ledger — design the data shape

**Step 1: Read** `bazi_engine/wuxing/vector.py` and `bazi_engine/wuxing/analysis.py` to understand the existing per-planet computation. Look for where weights are applied (Heavenly Stems 1.0, Earthly Branches main 1.0 / mid 0.5 / residual 0.3, retrograde 1.3×).

**Step 2: Sketch the ledger entry shape (in plan, not yet code):**

```jsonc
{
  "ledger": [
    {
      "source": "natal_pillar.year_branch",
      "branch": "Yin",
      "qi_layer": "main",
      "element": "Wood",
      "weight": 1.0,
      "category": "Traditional"
    },
    {
      "source": "natal_pillar.year_branch",
      "qi_layer": "mid",
      "element": "Fire",
      "weight": 0.5,
      "category": "Traditional"
    },
    {
      "source": "transit_planet.Mercury",
      "element": "Earth",
      "weight": 1.0,
      "category": "Modern Heuristic",
      "modifiers": [{"reason": "retrograde", "factor": 1.3}]
    }
  ],
  "ledger_total_per_element": {"Wood": 4.2, "Fire": 3.1, "Earth": 5.0, "Metal": 2.0, "Water": 1.5}
}
```

Categories: `Traditional` (Stems, Branch main-qi, BaZi day master), `Modern Heuristic` (transits, retrograde modifiers), `Experimental` (anything not yet calibrated). Document in `docs/PROVENANCE.md`.

**Step 3: Write `docs/PROVENANCE.md`** documenting the ledger schema. Include the audit reference. ~50 lines.

**Step 4: Commit**

```bash
git add docs/PROVENANCE.md
git commit -m "docs(provenance): contribution ledger schema specification"
```

### Task 22: Implement the Contribution Ledger emitter

**Files:**
- Create: `bazi_engine/wuxing/ledger.py`
- Modify: `bazi_engine/wuxing/vector.py` (or `bazi_engine/fusion.py` — wherever the per-planet weights are summed)
- Test: `tests/test_contribution_ledger.py` (new)

**Step 1: Failing test**

```python
# tests/test_contribution_ledger.py
import os, pytest
from fastapi.testclient import TestClient
from bazi_engine.app import create_app

pytestmark = pytest.mark.skipif(not os.environ.get("SE_EPHE_PATH"), reason="ephemeris")

NATAL = {"date": "1990-06-15T12:00:00", "tz": "Europe/Berlin",
         "lon": 13.405, "lat": 52.52, "birth_time_known": True}


@pytest.fixture
def client():
    return TestClient(create_app())


def test_fusion_response_includes_contribution_ledger(client):
    body = client.post("/v1/calculate/fusion", json=NATAL).json()
    ledger = body["provenance"].get("contribution_ledger") or body.get("contribution_ledger")
    assert ledger is not None
    entries = ledger["entries"]
    assert len(entries) > 0
    # Every entry must have the contract fields
    for e in entries:
        assert e["source"]
        assert e["element"] in {"Wood", "Fire", "Earth", "Metal", "Water"}
        assert isinstance(e["weight"], (int, float))
        assert e["category"] in {"Traditional", "Modern Heuristic", "Experimental"}
    # Totals match the fusion vector
    totals = ledger["totals_per_element"]
    assert sum(totals.values()) > 0


def test_retrograde_modifier_appears_with_factor_1_3(client):
    """If any planet was retrograde at this birth time, its ledger entry
    must record the 1.3 multiplier explicitly."""
    body = client.post("/v1/calculate/fusion", json=NATAL).json()
    entries = body["provenance"]["contribution_ledger"]["entries"]
    retrograde_entries = [e for e in entries if any(
        m["reason"] == "retrograde" for m in e.get("modifiers", []))]
    if retrograde_entries:
        assert all(m["factor"] == 1.3
                   for e in retrograde_entries
                   for m in e["modifiers"] if m["reason"] == "retrograde")
```

**Step 2: Run test**

Expected: FAIL.

**Step 3: Implement `bazi_engine/wuxing/ledger.py`**

A pure builder that takes the per-source weights as already computed in `vector.py` and produces the ledger structure. ~80 lines. Categorize each source statically (Stems → Traditional, Branches main/mid/residual → Traditional, transit aspects → Modern Heuristic, Mercury day/night → Traditional, etc.).

**Step 4: Wire into `routers/fusion.py`**

Inject the ledger into the `provenance` block of the response. Update the `Provenance` Pydantic model to include `contribution_ledger: Optional[ContributionLedger]`.

**Step 5: Run tests + regenerate OpenAPI**

```bash
pytest tests/test_contribution_ledger.py -v
python scripts/export_openapi.py
```

**Step 6: Commit**

```bash
git add bazi_engine/wuxing/ledger.py bazi_engine/routers/fusion.py bazi_engine/provenance.py tests/test_contribution_ledger.py spec/openapi/openapi.json tests/snapshots/
git commit -m "feat(provenance): per-source Wu-Xing contribution ledger

Each weight contributing to the fusion vector is exposed with its
source, element, weight, category, and modifiers (e.g., retrograde).
Closes the audit's 'Black Box' criticism: B2B partners can defend
every fusion value against their end-users."
```

---

# Phase F — H_calibrated als Primary Signal (P1)

`H_calibrated` is implemented and partially wired. Make it the documented primary; mark `H_raw` as advisory.

### Task 23: Make `H_calibrated` mandatory in fusion responses

**Files:**
- Modify: `bazi_engine/routers/fusion.py`
- Modify: Pydantic `FusionResponse`
- Test: `tests/test_h_calibrated.py` (extend)

**Step 1: Failing test**

```python
def test_fusion_response_h_calibrated_is_primary():
    """h_calibrated must be present and non-null on every fusion response."""
    from fastapi.testclient import TestClient
    from bazi_engine.app import create_app
    client = TestClient(create_app())
    body = client.post("/v1/calculate/fusion", json={
        "date": "1990-06-15T12:00:00", "tz": "Europe/Berlin",
        "lon": 13.405, "lat": 52.52,
    }).json()
    assert "h_calibrated" in body["harmony_index"]
    assert body["harmony_index"]["h_calibrated"] is not None
    # h_raw remains for back-compat but is now annotated as advisory
    assert "h_raw" in body["harmony_index"]
```

**Step 2: Run** → FAIL if h_calibrated isn't surfaced at the top of the harmony_index block.

**Step 3: Implement** — ensure `routers/fusion.py` always includes `h_calibrated` in the response. Where it's currently `cal.get("h_calibrated", ...)`, harden to require it.

**Step 4: Run + commit**

```bash
git commit -m "feat(fusion): h_calibrated is the contractually required primary signal"
```

### Task 24: Update the daily/experience response to surface `h_calibrated`

The experience daily response already calls `cal.get("h_calibrated", ...)` at `routers/experience.py:375`. Verify it always returns a non-None value and add a test.

**Step 1: Failing test**

```python
def test_daily_response_harmony_uses_h_calibrated():
    # ... POST /v1/experience/daily ...
    body = client.post(...).json()
    assert body["harmony_index"]  # not None
    # Either expose the source, or document it as h_calibrated by contract
    assert body.get("harmony_source") == "h_calibrated"
```

**Step 2: Implement** — add `harmony_source: "h_calibrated"` to the daily response so consumers can verify.

**Step 3: Commit**

```bash
git commit -m "feat(experience): annotate harmony_source so consumers can audit"
```

### Task 25: OpenAPI documentation pass for `h_calibrated`

**Step 1:** Add a `description` to the `h_calibrated` field in the Pydantic model: *"Primary harmony signal. Calibrated against Monte-Carlo baseline to correct positive-orthant compression. Range [0, 1]. Use this, not h_raw."*

**Step 2:** Add deprecation-style description to `h_raw`: *"Advisory only. Raw cosine similarity prone to positive-orthant compression. Use h_calibrated as the contract metric."*

**Step 3:** Regenerate spec, commit.

```bash
git commit -m "docs(openapi): document h_calibrated as primary, h_raw as advisory"
```

---

# Phase G — Test-Hygiene & Redundanz-Audit (P1)

79 test files, 1483 test functions. The user requested a redundancy review. This phase produces a documented coverage matrix and consolidates duplicates.

### Task 26: Generate a test coverage matrix

**Files:**
- Create: `docs/test-coverage-matrix.md`

**Step 1: Inventory**

```bash
# Per-test-file: what feature it covers (from filename + first docstring)
for f in tests/test_*.py; do
  doc=$(grep -m1 -E '^"""' "$f" | head -1)
  echo "$(basename $f) | $doc"
done > /tmp/test_inventory.txt

# Per-source-module: which test files import it
for src in bazi_engine/*.py bazi_engine/*/*.py; do
  modname=$(echo "$src" | sed 's|bazi_engine/||;s|/|.|g;s|.py||')
  tests=$(grep -lr "import.*$modname\|from.*$modname" tests/ 2>/dev/null | xargs -n1 basename | tr '\n' ',')
  echo "$modname → $tests"
done > /tmp/source_to_tests.txt
```

**Step 2: Compose `docs/test-coverage-matrix.md`** as a 2-column table: `feature | test_files`. Identify clusters with ≥3 files where consolidation is plausible.

**Step 3: Mark redundancy candidates** in the matrix. Suspected clusters from the inventory:
- `test_calibration.py`, `test_calibration_simulation.py`, `test_h_calibrated.py` — overlapping?
- `test_impact_calc.py`, `test_impact_golden.py`, `test_impact_harmony.py`, `test_impact_resonance.py`, `test_impact_router.py`, `test_impact_types.py` — likely partially overlapping fixtures.
- `test_experience_daily_v2.py`, `test_experience_endpoints.py`, `test_experience_schemas.py` — verify they cover distinct concerns.

For each cluster, **document** what each file uniquely covers in the matrix — don't delete anything yet.

**Step 4: Commit**

```bash
git add docs/test-coverage-matrix.md
git commit -m "docs(tests): coverage matrix and redundancy candidates"
```

### Task 27: Run mutation-style coverage diff for each suspected cluster

For each cluster identified in Task 26:

**Step 1:** Run only one file at a time with line coverage:

```bash
pytest --cov=bazi_engine --cov-report=term-missing tests/test_h_calibrated.py
pytest --cov=bazi_engine --cov-report=term-missing tests/test_calibration.py
```

**Step 2:** If two files cover ≥80% of identical lines, they ARE redundant. If they each cover unique lines, they're complementary — leave both.

**Step 3:** When a true duplicate is found, **merge** rather than delete: move the unique assertions into one file, then delete the other. This preserves test intent.

**Step 4:** Commit per merge:

```bash
git commit -m "test(refactor): merge test_calibration_simulation into test_calibration

Both files exercised the same baseline computation paths. Unique
sigma assertions moved into the canonical file."
```

### Task 28: Update existing tests for new fields from Phases A–F

**Step 1:** `pytest -q --tb=short` and capture all failures.

**Step 2:** For each failing test, decide:
- **Snapshot-only failure** (a known-good output now includes a new additive field like `quality_flags`): regenerate snapshot.
- **Behaviour failure** (the test asserted a now-wrong value, e.g., `chart_type_quality == "assumed_day"` for a birth-time-known case): fix the assertion.
- **Genuine regression**: don't update the test — fix the source.

**Step 3:** Run the snapshot regeneration *only* for the additive-field cases:

```bash
# Discover the snapshot regeneration mechanism — likely an env var
grep -rn "snapshot" tests/test_snapshot_stability.py
# Run with regeneration flag (find the right invocation)
```

**Step 4:** Commit per update batch:

```bash
git commit -m "test: update snapshots for additive quality_flags / contribution_ledger fields"
```

### Task 29: Phase G gate

**Step 1:** `pytest -q --cov=bazi_engine --cov-fail-under=75` — green and at-or-above threshold.
**Step 2:** Verify final test count: `find tests -name 'test_*.py' | wc -l`. Document the new total in the test coverage matrix.

---

# Phase H — B2B Tenant Layer & Artifact Referencing (P2 — Design only)

These are **design tasks** that produce ADRs (Architecture Decision Records), not code, because the audit's tier-2 recommendations need cross-team alignment before implementation.

### Task 30: ADR — Tenant-Profile Parameter

**Files:**
- Create: `docs/adr/ADR-002-tenant-profile-parameter.md`

**Step 1:** Read existing `docs/adr/` to match style (if absent, create the directory and a brief template). Likely template fields: Context, Decision, Status, Consequences.

**Step 2:** Document the proposed `profile` request parameter:
- Values: `dating-premium`, `wellness-basic`, `compliance-audit`, `default`
- Mapping: each profile selects the response detail level and which optional sub-blocks (`contribution_ledger`, `aspects_full`, etc.) are included.
- Rejection criteria: invalid profile names → 400.
- Implementation path: a single `get_response_filter(profile)` function in a new `bazi_engine/tiering.py`; routers apply the filter at the end of response assembly.

**Step 3:** Commit:

```bash
git commit -m "docs(adr): ADR-002 tenant-profile parameter"
```

### Task 31: ADR — Artifact Referencing (`natalChartId`)

**Files:**
- Create: `docs/adr/ADR-003-artifact-referencing.md`

**Step 1:** Document:
- Endpoint sketch: `POST /v1/charts/natal` returns `{natalChartId, ...}`.
- Storage: in-memory TTL cache (24h) for free tier, Redis-backed for paid.
- Consumption: every transit/experience endpoint accepts `natalChartId` in lieu of `natal: {...}`.
- Cache key: SHA256 of canonical natal-input JSON (deterministic; no UUIDs).
- Eviction: LRU bound + TTL.
- Security: chart IDs are not secrets — they're opaque hashes; no PII leak.

**Step 2:** Commit:

```bash
git commit -m "docs(adr): ADR-003 artifact referencing for chart re-use"
```

### Task 32: Strategy doc — B2B vertical extensions

**Files:**
- Create: `docs/strategy/b2b-verticals.md`

**Step 1:** Catalogue the audit's B2B vertical hints (Dating, Fintech, plus likely candidates: HR/talent, Wellness, Insurance/risk, Education/career counselling). For each, list:
- What FuFirE primitive maps to the vertical's value? (e.g., Dating → Mercury day/night for communication style; HR → Wu-Xing element distribution for team composition)
- What new endpoint would they need? (e.g., HR → `/v1/match/team` taking ≥2 charts)
- Reuse vs. new endpoint? (Always prefer reuse via `profile` parameter from Task 30)

**Step 2:** Commit:

```bash
git commit -m "docs(strategy): B2B vertical extension hypotheses"
```

---

# Closing — Final Verification

After all phases:

**Step 1: Full test run**
```bash
pytest -q --cov=bazi_engine --cov-fail-under=75
```

**Step 2: Lint + typecheck**
```bash
ruff check bazi_engine/ --output-format=github
mypy bazi_engine --ignore-missing-imports
```

**Step 3: OpenAPI integrity**
```bash
python scripts/export_openapi.py --check
```

**Step 4: Bug-resurrection probe** — run the regression tests created in Phase A explicitly:
```bash
pytest tests/test_experience_ascendant_wiring.py tests/test_no_legacy_ascmc_references.py tests/test_mercury_day_night_regression.py tests/test_quality_flags_western.py tests/test_natal_input_strictness.py -v
```
All must PASS. If any one is skipped because of missing ephemeris, set `SE_EPHE_PATH` and re-run before declaring the plan complete.

**Step 5: Commit a closing changelog entry**

```bash
# In CHANGELOG.md, add under Unreleased / 1.0.0-rcN:
# - fix: Ascendant naming-mismatch (audit P0)
# - fix: Mercury day/night cascade (audit P0)
# - feat: quality_flags block exposes house_system fallback + chart_type_quality
# - feat: contribution_ledger per source with category and modifiers
# - feat: tzdb_version and ephemeris_id in provenance
# - docs: ADR-002 tenant profile, ADR-003 artifact referencing
git add CHANGELOG.md
git commit -m "docs(changelog): hardening release notes"
```

---

## Risk Register & Decision Points

| Risk | Mitigation |
|------|------------|
| Snapshot churn from quality_flags addition | Keep `quality_flags` strictly additive; never rename existing fields; test_snapshot_stability.py snapshots regenerated in Task 28 only |
| `birth_time_known` strict-mode breaks existing free-tier consumers | Task 10 makes the validation opt-in via explicit `false`; document in CHANGELOG and pin the API minor version bump |
| `H_calibrated` becomes load-bearing before all baselines are finalised | Task 23 only requires *presence*, not interpretation; Monte-Carlo recalibration is out-of-scope for this plan |
| Contribution Ledger response size inflates payloads | Task 22 emits ledger as part of `provenance`; Task 30 (ADR) routes the filtering via `profile` parameter so default tier can omit it |
| `slowapi` 422 audit was wrong (false positive) | Task 16 enforces the `request: Request` contract regardless; harmless if already correct |

## Execution Notes

- **Do not skip the failing-test step.** If a failing test passes immediately, the test is wrong — debug *the test*, not the code.
- **Frozen contract guarantee:** Every change in this plan is *additive* (new fields, new validators, new endpoints). No `/v1/*` field is renamed or removed. If you discover a need for a breaking change, STOP and escalate — that requires an API minor version bump and a separate plan.
- **Per-phase commit cadence:** at minimum one commit per task. Between tasks within a phase, run `pytest -q` to keep regressions out.
- **OpenAPI drift:** every behaviour-changing task must end with either `python scripts/export_openapi.py --check` PASS or a regenerated spec committed in the same change.
