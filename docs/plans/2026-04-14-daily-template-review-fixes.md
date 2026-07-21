# Daily Template Review Fixes — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix all issues from the code review of TASK-daily-template-variants — typos, dead code, comment accuracy, and structured sub-fields for downstream consumers.

**Architecture:** Four surgical edits to `daily_templates.py`, one dead-code removal in `daily_eastern.py`, one Pydantic model extension in `experience.py` to expose `jieqi`/`weekday` through the API, and one summary refactor to keep `summary` short by moving enrichment text to dedicated fields.

**Tech Stack:** Python 3.10+, Pydantic v2, pytest

---

### Task 1: Fix typo and umlaut in daily_templates.py

**Files:**
- Modify: `bazi_engine/services/daily_templates.py:16` (typo)
- Modify: `bazi_engine/services/daily_templates.py:104` (umlaut)

**Step 1: Write the failing test**

```python
# tests/test_daily_templates.py — add to TestRelationVariants class
def test_no_non_ascii_in_templates(self):
    """All German template strings use ASCII transliteration (ae, ue, oe, ss)."""
    import re
    non_ascii = re.compile(r'[^\x00-\x7F]')
    for pool in [RELATION_SUMMARY_VARIANTS_DE, CAUTION_VARIANTS_DE, OPPORTUNITY_VARIANTS_DE]:
        for rel, variants in pool.items():
            for v in variants:
                match = non_ascii.search(v)
                assert match is None, f"{rel} variant contains non-ASCII char '{match.group()}': {v}"
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_daily_templates.py::TestRelationVariants::test_no_non_ascii_in_templates -v`
Expected: FAIL — resource variant 1 contains `ä` in "nährt"

**Step 3: Fix the two strings**

In `bazi_engine/services/daily_templates.py`:

Line 16 — fix typo:
```python
# OLD:
"Tatendrang und Entschlossenheit praeagen den Tag."
# NEW:
"Tatendrang und Entschlossenheit praegen den Tag."
```

Line 104 — fix umlaut:
```python
# OLD:
"Dein Day Master {dm} wird heute getragen. Die {element}-Energie nährt dich aus der Tiefe.",
# NEW:
"Dein Day Master {dm} wird heute getragen. Die {element}-Energie naehrt dich aus der Tiefe.",
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_daily_templates.py::TestRelationVariants::test_no_non_ascii_in_templates -v`
Expected: PASS

**Step 5: Also run the typo string in its weekday context**

Run: `uv run pytest tests/test_daily_templates.py::TestWeekdayModifier -v`
Expected: PASS (weekday energy dict is data, not tested for spelling, but confirm no breakage)

**Step 6: Commit**

```bash
git add bazi_engine/services/daily_templates.py tests/test_daily_templates.py
git commit -m "fix: typo praeagen→praegen, umlaut nährt→naehrt in daily templates"
```

---

### Task 2: Fix comment "6 seasonal groups" → "8 seasonal groups"

**Files:**
- Modify: `bazi_engine/services/daily_templates.py:25`

**Step 1: Fix the comment**

```python
# OLD (line 25):
# Jieqi seasonal energy (24 terms → 6 seasonal groups)
# NEW:
# Jieqi seasonal energy (24 terms → 8 seasonal groups)
```

**Step 2: Verify no test changes needed**

Run: `uv run pytest tests/test_daily_templates.py::TestJieqiSeason::test_all_seasons_have_flavors -v`
Expected: PASS (test already asserts 8)

**Step 3: Commit**

```bash
git add bazi_engine/services/daily_templates.py
git commit -m "fix: correct comment — 8 seasonal groups, not 6"
```

---

### Task 3: Remove dead _RELATION_SUMMARY_DE dict

**Files:**
- Modify: `bazi_engine/services/daily_eastern.py:57-64`

**Step 1: Verify it's unreachable**

Grep to confirm `_RELATION_SUMMARY_DE` is only used in the fallback `.get()` default on line 165, and that `RELATION_SUMMARY_VARIANTS_DE` covers all 6 relations (companion, resource, output, power, wealth, neutral):

Run: `uv run python -c "from bazi_engine.services.daily_templates import RELATION_SUMMARY_VARIANTS_DE; print(sorted(RELATION_SUMMARY_VARIANTS_DE.keys()))"`
Expected: `['companion', 'neutral', 'output', 'power', 'resource', 'wealth']` — all 6 covered, fallback never triggers.

**Step 2: Remove the dead dict and simplify the lookup**

In `bazi_engine/services/daily_eastern.py`:

Delete lines 57-64 (`_RELATION_SUMMARY_DE` dict).

Simplify line 165:
```python
# OLD:
summary_variants = RELATION_SUMMARY_VARIANTS_DE.get(relation, [_RELATION_SUMMARY_DE.get(relation, "Tag fuer {dm}.")])
# NEW:
summary_variants = RELATION_SUMMARY_VARIANTS_DE[relation]
```

Also simplify the caution and opportunity fallbacks (lines 176, 181):
```python
# OLD:
caution_variants = CAUTION_VARIANTS_DE.get(relation, [f"Die {relation.title()}-Dynamik kann heute zu Ueberreaktion fuehren. Bleibe geerdet."])
# NEW:
caution_variants = CAUTION_VARIANTS_DE[relation]

# OLD:
opp_variants = OPPORTUNITY_VARIANTS_DE.get(relation, [f"{themes[0]} ist heute dein staerkstes Feld."])
# NEW:
opp_variants = OPPORTUNITY_VARIANTS_DE[relation]
```

**Step 3: Run all daily tests**

Run: `uv run pytest tests/test_daily_eastern.py tests/test_daily_templates.py tests/test_daily_eastern_jieqi.py -v`
Expected: All PASS

**Step 4: Commit**

```bash
git add bazi_engine/services/daily_eastern.py
git commit -m "refactor: remove dead _RELATION_SUMMARY_DE, use direct dict access"
```

---

### Task 4: Add structured sub-fields to DailyEvidence and DailySection

This is the structural improvement: expose `jieqi` and `weekday` as dedicated evidence fields at the API level, and add `jieqi_note` + `weekday_note` to `DailySection` so the `summary` field stays short.

**Files:**
- Modify: `bazi_engine/routers/experience.py:190-203` (Pydantic models)
- Modify: `bazi_engine/routers/experience.py:660-677` (response construction)
- Modify: `bazi_engine/services/daily_eastern.py:162-198` (return structured fields)
- Modify: `bazi_engine/services/daily_western.py:50-71` (return structured fields)
- Test: `tests/test_daily_templates.py` (integration tests)

**Step 1: Write the failing test**

```python
# tests/test_daily_templates.py — add to TestEasternDailyIntegration
def test_eastern_daily_has_structured_subfields(self):
    from bazi_engine.services.daily_eastern import generate_eastern_daily

    result = generate_eastern_daily(day_master="Jia", target_date="2026-04-14")
    assert "jieqi_note" in result
    assert "weekday_note" in result
    assert isinstance(result["jieqi_note"], str)
    assert isinstance(result["weekday_note"], str)
    # Summary should NOT contain the jieqi_note or weekday_note text
    assert result["jieqi_note"] not in result["summary"]
    assert result["weekday_note"] not in result["summary"]
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_daily_templates.py::TestEasternDailyIntegration::test_eastern_daily_has_structured_subfields -v`
Expected: FAIL — `jieqi_note` key not in result

**Step 3: Refactor daily_eastern.py — move enrichment out of summary**

In `bazi_engine/services/daily_eastern.py`, replace lines 164-198 with:

```python
    themes = _RELATION_THEMES_DE.get(relation, ["Energie"])

    # Select variant templates based on (relation × day-of-year)
    summary_variants = RELATION_SUMMARY_VARIANTS_DE[relation]
    summary = select_variant(summary_variants, target_date).format(dm=day_master, element=daily_element)
    summary += f" Solarterm: {jieqi_name}."

    # Structured sub-fields for downstream consumers
    jieqi_flavor = get_jieqi_flavor(jieqi_name)
    weekday_name, weekday_planet, weekday_energy = get_weekday_modifier(target_date)
    jieqi_note = jieqi_flavor
    weekday_note = f"{weekday_name} ({weekday_planet}): {weekday_energy}"

    caution_variants = CAUTION_VARIANTS_DE[relation]
    caution = select_variant(caution_variants, target_date).format(
        relation=relation, element=daily_element,
    )

    opp_variants = OPPORTUNITY_VARIANTS_DE[relation]
    opportunity = select_variant(opp_variants, target_date).format(
        theme=themes[0], element=daily_element,
    )

    return {
        "summary": summary,
        "themes": themes,
        "caution": caution,
        "opportunity": opportunity,
        "jieqi_note": jieqi_note,
        "weekday_note": weekday_note,
        "evidence": {
            "day_master": day_master,
            "daily_pillar": {"stem": daily_stem, "branch": daily_branch},
            "relation_to_day_master": relation,
            "jieqi": jieqi_name,
            "weekday": weekday_name,
        },
    }
```

**Step 4: Refactor daily_western.py — same pattern**

In `bazi_engine/services/daily_western.py`, replace lines 50-71 with:

```python
    weekday_name, weekday_planet, weekday_energy = get_weekday_modifier(target_date)

    summary = (
        f"Fuer dich als {sun_sign.title()} stehen heute {', '.join(themes)} im Fokus. "
        f"Die Planetenkonstellation aktiviert deine Sektoren {active_indices[0]+1} und {active_indices[1]+1}."
    )
    weekday_note = f"{weekday_name} ({weekday_planet}): {weekday_energy}"
    caution = f"Achte in Sektor {active_indices[1]+1} auf Ueberanstrengung — hier liegt heute Spannung."
    opportunity = f"Sektor {active_indices[0]+1} bietet dir heute besonderes Potenzial. Nutze die Energie aktiv."

    return {
        "summary": summary,
        "themes": themes,
        "caution": caution,
        "opportunity": opportunity,
        "weekday_note": weekday_note,
        "evidence": {
            "transit_sectors": active_indices,
            "natal_focus": ["sun", "ascendant"],
            "weekday": weekday_name,
        },
    }
```

**Step 5: Refactor daily_fusion.py — same pattern**

In `bazi_engine/services/daily_fusion.py`, replace the jieqi/weekday block (lines 44-53) with:

```python
    jieqi = eastern.get("evidence", {}).get("jieqi", "")
    weekday = eastern.get("evidence", {}).get("weekday", western.get("evidence", {}).get("weekday", ""))

    summary = (
        f"Dein Fusionstag verbindet {shared_str} aus beiden Systemen. "
        f"Westlich staerkt dein Transitfeld, oestlich arbeitet dein Day Master {day_master} in {relation}-Dynamik."
    )
    jieqi_note = f"Solarterm {jieqi} faerbt beide Systeme." if jieqi else ""
    weekday_note = f"{weekday}-Energie verbindet die Impulse." if weekday else ""
```

And add them to the return dict:

```python
    return {
        "summary": summary,
        ...existing fields...,
        "jieqi_note": jieqi_note,
        "weekday_note": weekday_note,
    }
```

**Step 6: Run the failing test — should now pass**

Run: `uv run pytest tests/test_daily_templates.py::TestEasternDailyIntegration::test_eastern_daily_has_structured_subfields -v`
Expected: PASS

**Step 7: Update DailyEvidence Pydantic model**

In `bazi_engine/routers/experience.py`, add fields to `DailyEvidence` (line 190):

```python
class DailyEvidence(BaseModel):
    transit_sectors: Optional[List[int]] = None
    natal_focus: Optional[List[str]] = None
    day_master: Optional[str] = None
    daily_pillar: Optional[DailyPillar] = None
    relation_to_day_master: Optional[str] = None
    jieqi: Optional[str] = None
    weekday: Optional[str] = None
```

And add optional sub-fields to `DailySection` (line 198):

```python
class DailySection(BaseModel):
    summary: str
    themes: List[str]
    caution: str
    opportunity: str
    evidence: DailyEvidence
    jieqi_note: Optional[str] = None
    weekday_note: Optional[str] = None
```

And add them to `DailyFusion` (line 206):

```python
class DailyFusion(BaseModel):
    summary: str
    synthesis: str
    action: str
    pushworthy: bool
    push_text: Optional[str] = None
    jieqi_note: Optional[str] = None
    weekday_note: Optional[str] = None
```

**Step 8: Wire up sub-fields in response construction**

In `bazi_engine/routers/experience.py`, update the `DailyResponse` construction (~line 658):

For western section:
```python
western=DailySection(
    summary=western_result["summary"],
    themes=western_result["themes"],
    caution=western_result["caution"],
    opportunity=western_result["opportunity"],
    evidence=DailyEvidence(**western_result["evidence"]),
    weekday_note=western_result.get("weekday_note"),
),
```

For eastern section:
```python
eastern=DailySection(
    summary=eastern_result["summary"],
    themes=eastern_result["themes"],
    caution=eastern_result["caution"],
    opportunity=eastern_result["opportunity"],
    evidence=DailyEvidence(
        day_master=eastern_evidence.get("day_master"),
        daily_pillar=daily_pillar,
        relation_to_day_master=eastern_evidence.get("relation_to_day_master"),
        jieqi=eastern_evidence.get("jieqi"),
        weekday=eastern_evidence.get("weekday"),
    ),
    jieqi_note=eastern_result.get("jieqi_note"),
    weekday_note=eastern_result.get("weekday_note"),
),
```

For fusion section:
```python
fusion=DailyFusion(
    summary=fusion_result["summary"],
    synthesis=fusion_result["synthesis"],
    action=fusion_result["action"],
    pushworthy=fusion_result["pushworthy"],
    push_text=fusion_result.get("push_text"),
    jieqi_note=fusion_result.get("jieqi_note"),
    weekday_note=fusion_result.get("weekday_note"),
),
```

**Step 9: Update the existing tests that parse long summary**

In `tests/test_daily_eastern_jieqi.py:153-157`, the test already uses `.split("Solarterm: ")[1].split(".")[0]` which still works since `summary` still ends with "Solarterm: {name}." — no change needed.

In `tests/test_daily_templates.py`, update `test_eastern_different_dates_vary_summary` — summaries will still differ because the variant template + jieqi changes, so this should still pass.

Update `test_fusion_includes_jieqi_note`:
```python
def test_fusion_includes_jieqi_note(self):
    from bazi_engine.services.daily_fusion import generate_fusion_daily

    western = {"themes": ["Ausdruck"], "evidence": {"weekday": "Dienstag"}}
    eastern = {
        "themes": ["Gleichklang"],
        "evidence": {
            "day_master": "Jia",
            "relation_to_day_master": "companion",
            "jieqi": "Chunfen",
            "weekday": "Dienstag",
        },
    }
    result = generate_fusion_daily(western, eastern)
    # Jieqi and weekday are now in structured fields, not in summary
    assert "Chunfen" in result["jieqi_note"]
    assert "Dienstag" in result["weekday_note"]
```

**Step 10: Run full test suite**

Run: `uv run pytest -q`
Expected: All pass (1934+)

**Step 11: Regenerate OpenAPI spec**

Run: `uv run python scripts/export_openapi.py`

This picks up the new optional fields on `DailySection`, `DailyFusion`, and `DailyEvidence`. Then verify:

Run: `uv run python scripts/export_openapi.py --check`
Expected: Up to date

**Step 12: Commit**

```bash
git add bazi_engine/services/daily_eastern.py bazi_engine/services/daily_western.py bazi_engine/services/daily_fusion.py bazi_engine/routers/experience.py tests/test_daily_templates.py spec/openapi/openapi.json
git commit -m "feat: structured jieqi_note/weekday_note sub-fields, keep summary concise"
```

---

### Task 5: Final verification

**Step 1: Run full suite one more time**

Run: `uv run pytest -q`
Expected: All pass, 0 failures

**Step 2: Run lint and typecheck**

Run: `uv run ruff check bazi_engine/ --output-format=github`
Expected: No errors

Run: `uv run mypy bazi_engine --ignore-missing-imports`
Expected: No new errors

**Step 3: Verify OpenAPI drift check**

Run: `uv run python scripts/export_openapi.py --check`
Expected: "Up to date"
