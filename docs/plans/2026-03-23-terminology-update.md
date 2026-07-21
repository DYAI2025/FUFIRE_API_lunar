# Terminology Update Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Update all user-facing documentation to use current FuFirE branding and "Coherence Index" terminology, without touching code identifiers, file paths, import statements, API field names, or snapshot data.

**Architecture:** Pure documentation/prose changes. The API field `harmony_index` stays as-is (endpoints are frozen per CLAUDE.md). Only human-readable text in `.md`, `.txt`, and `.html` files is updated. A verification step ensures no code or paths were accidentally modified.

**Tech Stack:** grep, sed-free (Edit tool only), pytest for regression.

---

## Scope Rules (CRITICAL)

### DO rename (prose/display text only):
- "BAFE" → "FuFirE" (when referring to the product, not the directory)
- "BaZodiac" → "FuFirE"
- "bazi_engine v1.0.0-rc0" → "FuFirE v1.0.0-rc1"
- "Harmony Index" → "Coherence Index" (in prose)
- "baziengine-v2.fly.dev" → "bafe-2u0e2a.fly.dev"

### DO NOT rename (referential/structural):
- `bazi_engine` in import statements, module paths, CLI commands (`python -m bazi_engine.cli`)
- `harmony_index` as API response field name (frozen contract)
- `calculate_harmony_index()` function name
- `bafe-2u0e2a` in URLs (that's the actual Fly.io app name)
- `/BAFE/` in directory paths
- `harmony_index` in snapshot JSON files
- `harmony_method` in parameter sets
- Any `.py` file content

---

### Task 1: Rewrite README.md

**Files:**
- Modify: `README.md`

**Step 1: Rewrite the README**

Replace the entire README with a modern FuFirE-branded version. Key changes:
- Title: `# FuFirE — Fusion Firmament Engine`
- Remove "BaZodiac / BAFE" references
- Update version to 1.0.0-rc1
- Add fusion, Western, transit, experience endpoints to feature list
- Fix Fly.io URL from `baziengine-v2.fly.dev` to `bafe-2u0e2a.fly.dev`
- Keep CLI examples with `python -m bazi_engine.cli` (that's the real module name)
- Keep `bazi_engine` in import/module references (it's the package name)
- Add links to: developer reference, whitepaper, fusion explainer (EN/DE), landing page demo
- Add quickstart curl example
- Remove GitHub Actions dispatch section (outdated, uses old URL)

**Step 2: Verify no test breaks**

Run: `pytest tests/test_rebrand.py -v`
Expected: PASS (README is not tested by rebrand tests, but good to confirm)

**Step 3: Commit**

```bash
git add README.md
git commit -m "docs: rewrite README for FuFirE branding"
```

---

### Task 2: Update docs/fusion/ terminology

**Files:**
- Modify: `docs/fusion/06_fusion_orchestration.md`
- Modify: `docs/fusion/11_ground_truth_integrity.md`
- Modify: `docs/fusion/ASTROLOGEN_LEITFADEN.md`

**Renaming rules for these files:**
- "Harmony Index" → "Kohärenz-Index" (German docs) or "Coherence Index" (English docs)
- BUT keep `harmony_index` when it appears as a code reference (field name, function name, JSON key)
- "BAFE" → "FuFirE" when referring to the product

**How to distinguish:**
- `harmony_index` (monospace/backticks) = code reference → KEEP
- "Harmony Index" (prose) = display name → RENAME
- `calculate_harmony_index()` = function name → KEEP
- "der Harmony Index von 72%" = prose → RENAME to "der Kohärenz-Index von 72%"

**Step 1: Update 06_fusion_orchestration.md**

In prose sections only:
- "Harmony Index" → "Coherence Index" / "Kohärenz-Index"
- Keep all backtick-quoted `harmony_index` references unchanged

**Step 2: Update 11_ground_truth_integrity.md**

- "Der rohe Harmony Index H" → "Der rohe Kohärenz-Index H"

**Step 3: Update ASTROLOGEN_LEITFADEN.md**

- All prose "Harmony Index" → "Kohärenz-Index"
- "BAFE-Repository" → "FuFirE-Repository"
- Keep any code/JSON references as-is

**Step 4: Commit**

```bash
git add docs/fusion/
git commit -m "docs(fusion): rename Harmony Index to Kohärenz-Index in prose"
```

---

### Task 3: Update docs/REPO_ANALYSIS_DE.md and docs/REPORT-Stabilization050326.md

**Files:**
- Modify: `docs/REPO_ANALYSIS_DE.md`
- Modify: `docs/REPORT-Stabilization050326.md`

**Step 1: Update REPO_ANALYSIS_DE.md**

- Title: "BAFE / BaZi Engine" → "FuFirE — Fusion Firmament Engine"
- Body: "BAFE" → "FuFirE" in prose only

**Step 2: Update REPORT-Stabilization050326.md**

- "BAFE" → "FuFirE" in prose (e.g., "Die BAFE-API" → "Die FuFirE-API")
- Keep "`test_api.py` | BAFE Contract-Schema-Validierung" → rename "BAFE" to "FuFirE" (it's a description, not a path)

**Step 3: Commit**

```bash
git add docs/REPO_ANALYSIS_DE.md docs/REPORT-Stabilization050326.md
git commit -m "docs: update BAFE references to FuFirE in analysis/report docs"
```

---

### Task 4: Update docs/fusion/05_harmony_index.md title

**Files:**
- Modify: `docs/fusion/05_harmony_index.md`

**Step 1: Update title and prose**

- Title: if it says "Harmony Index" → "Kohärenz-Index (Coherence Index)"
- Prose references: "Harmony Index" → "Kohärenz-Index"
- Keep any `harmony_index` code references

**Step 2: Commit**

```bash
git add docs/fusion/05_harmony_index.md
git commit -m "docs(fusion): rename Harmony Index title to Kohärenz-Index"
```

---

### Task 5: Verification — ensure no code was touched

**Step 1: Verify only .md/.txt/.html files were modified**

Run: `git diff --name-only HEAD~4 | grep -v '\.md$\|\.txt$\|\.html$'`
Expected: empty output (no .py, .json, or other files changed)

**Step 2: Run full test suite**

Run: `pytest -q --ignore=tests/test_snapshot_stability.py --tb=short`
Expected: all pass, no regressions

**Step 3: Run rebrand tests specifically**

Run: `pytest tests/test_rebrand.py -v`
Expected: all pass

**Step 4: Verify harmony_index still works as API field**

Run: `pytest tests/test_fusion.py -v -k "harmony"`
Expected: all pass (function and field names unchanged)

**Step 5: Commit verification**

No commit needed — this is a validation step only.

---

## Summary

| Task | Files | What changes |
|------|-------|-------------|
| 1 | `README.md` | Full rewrite: FuFirE branding, current endpoints, fixed URLs |
| 2 | `docs/fusion/` (3 files) | "Harmony Index" → "Kohärenz-Index" in prose only |
| 3 | `docs/REPO_ANALYSIS_DE.md`, `docs/REPORT-*.md` | "BAFE" → "FuFirE" in prose |
| 4 | `docs/fusion/05_harmony_index.md` | Title + prose rename |
| 5 | (none) | Verification: no code touched, all tests pass |

**What is NOT touched:**
- Any `.py` file
- Any `.json` file (OpenAPI, schemas, snapshots)
- `bazi_engine` as a module/package name
- `harmony_index` as an API field name
- `bafe-2u0e2a` in Fly.io URLs
- Any file in `docs/plans/`
