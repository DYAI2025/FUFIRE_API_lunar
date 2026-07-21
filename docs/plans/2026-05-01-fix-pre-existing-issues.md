# Fix Pre-Existing Issues — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Bring the FuFirE main worktree to a fully clean state — zero pytest warnings, zero uncommitted dirt, zero stray files at repo root, slowapi deprecation resolved, and a CI guard added so configuration drift cannot recur silently.

**Architecture:** Pure repository hygiene + tooling tightening. No engine logic changes. Each task is one focused commit. Where possible, write a regression test that fails before the fix and passes after — for stateful issues (untracked files, deprecation warnings) we capture the precondition with a runnable check instead.

**Tech Stack:** Python 3.10+ / pytest 9 / slowapi / uv / git / GitHub Actions

---

## Inventory of Pre-Existing Issues (audit baseline, 2026-05-01)

### A. Code & tooling

1. **pytest dual config** — `pytest.ini` and `pyproject.toml` both define `[tool.pytest]` settings. pytest emits `WARNING: ignoring pytest config in pyproject.toml!` on every test invocation. Two configs are a future-bug factory.
2. **slowapi 0.1.9 deprecation** — Vendored slowapi calls `asyncio.iscoroutinefunction` (removed in Python 3.16). Surfaces as a DeprecationWarning on every pytest run that touches the API. Will become a hard failure when CI bumps to Python 3.16.

### B. Uncommitted dirt (main worktree, 5 modified files)

3. **`uv.lock`** — adds `httpx` (a runtime dep already declared in `pyproject.toml`) and `respx` (a test dep). Legitimate change, never committed.
4. **`3-code/tasks.md`** — pre-Phase 5 status updates (planetary dignities, daily-template-variants, phase4-manual-testing all `Todo → Done`) plus the `TASK-decanates-terms` flip just made.
5. **`CLAUDE.md`** — Phase 5 progress counter ("1/5 → 2/5 done").
6. **`tests/test_daily_eastern_jieqi.py`** — bug fix to a brittle string-parse assertion (`rstrip(".")` replaced with `split(".")[0]`).
7. **`.claude/homunculus/observations.jsonl`** — runtime telemetry artifact, **should be gitignored, not committed**.

### C. Untracked clutter at repo root

8. **`0`** — zero-byte file dated 21 Apr 23:32 (likely shell typo: `> 0` or stray redirect).
9. **`FuFirE-main/`** — appears to be a nested copy/clone of the project (contains its own `__pycache__`, `api/`, `ai-scrum-scaffold/`).
10. **`FuFirE_API_Strategy/`** — untracked subdirectory at root.
11. **`GEMINI.md`, `SDLC.md`** — untracked single-file docs at root.
12. **`ai-scrum-scaffold/`** — untracked scaffold dir at root (also nested inside `FuFirE-main/`).
13. **`hardening/`** — untracked dir at root containing one .md (different from the parent-level `FuFirE-hardening/` git worktree — possibly leftover).

### D. Pending working state (created this session, awaiting commit)

14. **`bazi_engine/decanates_terms.py` + `tests/test_decanates_terms.py`** — just-completed `TASK-decanates-terms`, ready to ship.
15. **`docs/plans/2026-04-14-daily-template-review-fixes.md`** — older planning doc.
16. **`docs/plans/2026-04-30-fufire-hardening-and-b2b-readiness.md`** — the hardening plan that drove the Phase A/B PRs.
17. **`docs/runbooks/phase4-enhanced-fusion.md`** — runbook from Phase 4.

The plan is sequenced so that **Task 1** (triage decisions) gates everything in section C — those files require human judgment about intent before deletion, and the agent should not silently prune them.

---

## Task 0: Capture audit baseline

**Files:**
- Create: `docs/runbooks/2026-05-01-pre-fix-baseline.md` (transient — will be deleted at the end)

**Step 1: Capture the current pytest warning count**

Run: `source .venv/bin/activate && pytest -q 2>&1 | tail -3`
Expected output includes: `2019 passed, 42 skipped, 14 warnings in ~53s`

**Step 2: Capture full git status**

Run: `git status --short`
Expected: 5 modified files, 12+ untracked items (matches inventory above).

**Step 3: Write baseline note**

Write a single-paragraph baseline to `docs/runbooks/2026-05-01-pre-fix-baseline.md` with: warning count, modified file count, untracked item count, slowapi version (`pip show slowapi | grep Version`).

**Step 4: Do NOT commit yet** — this file is a scratchpad that the final task removes.

---

## Task 1: Triage Section C clutter (decision task — REQUIRES USER INPUT)

This task does not write code. It surfaces the unknown-intent items so the user decides per-item.

**Files (read-only):**
- Read: `0`, `GEMINI.md`, `SDLC.md`
- List: `FuFirE-main/`, `FuFirE_API_Strategy/`, `ai-scrum-scaffold/`, `hardening/`

**Step 1: Print the contents of small files**

Run: `wc -l 0 GEMINI.md SDLC.md && head -30 GEMINI.md SDLC.md`

**Step 2: List the directory structures one level deep**

Run: `for d in FuFirE-main FuFirE_API_Strategy ai-scrum-scaffold hardening; do echo "=== $d ==="; ls -la "$d" 2>&1 | head -10; done`

**Step 3: Surface each item to the user with a recommendation**

For each of the 6 items in Section C, present a one-line summary + a recommendation (`delete`, `keep + commit`, `keep + gitignore`, `move to <location>`).

Recommended defaults to propose:
- `0` → **delete** (zero-byte stray)
- `FuFirE-main/` → **delete if it's a duplicate clone, otherwise move to `~/Projects/codebase/FuFirE-main`**
- `FuFirE_API_Strategy/` → **move to `docs/strategy/` and commit, OR delete**
- `GEMINI.md`, `SDLC.md` → **commit to `docs/` if intentional, otherwise delete**
- `ai-scrum-scaffold/` → **delete if test scaffold is no longer used**
- `hardening/` → **move .md content into `docs/runbooks/` and delete the dir**

**Step 4: Wait for user decisions**

Capture the per-item disposition. Do not proceed to Task 6 until decisions are recorded.

**Step 5: Commit only the decision record**

Append a short table to `docs/runbooks/2026-05-01-pre-fix-baseline.md` recording each decision. No git commit yet.

---

## Task 2: Fix pytest dual config

**Files:**
- Read: `pytest.ini`, `pyproject.toml` (`[tool.pytest.ini_options]` block)
- Modify: `pyproject.toml`
- Delete: `pytest.ini`

**Step 1: Write a failing test that asserts pytest config lives in exactly one place**

Create `tests/test_pytest_config_canonical.py`:

```python
"""Regression: pytest config must live in pyproject.toml only.

A second config file (pytest.ini, setup.cfg, tox.ini) silently overrides
the pyproject.toml settings and emits 'WARNING: ignoring pytest config in
pyproject.toml!' on every test run. This test fails loudly if a duplicate
config file appears in the repo root.
"""
from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

FORBIDDEN_CONFIGS = ("pytest.ini", "setup.cfg", "tox.ini")


def test_no_duplicate_pytest_config_at_repo_root() -> None:
    offenders = [p for p in FORBIDDEN_CONFIGS if (REPO_ROOT / p).exists()]
    assert not offenders, (
        f"Duplicate pytest config file(s) found at repo root: {offenders}. "
        f"Pytest configuration must live exclusively in pyproject.toml under "
        f"[tool.pytest.ini_options] — a second config file silently overrides "
        f"pyproject.toml and triggers a startup warning."
    )
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_pytest_config_canonical.py -v`
Expected: FAIL with "Duplicate pytest config file(s) found at repo root: ['pytest.ini']"

**Step 3: Migrate `pytest.ini` settings into `pyproject.toml`**

Read current `pytest.ini`:
```ini
[pytest]
testpaths = tests
markers =
    integration: Tests die eine laufende LeanDeep-Instanz brauchen
```

Edit `pyproject.toml` `[tool.pytest.ini_options]` block to absorb the `markers` setting (testpaths is already there). The block should become:

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
markers = [
    "integration: Tests die eine laufende LeanDeep-Instanz brauchen",
]
```

**Step 4: Delete `pytest.ini`**

Run: `git rm pytest.ini`

**Step 5: Run the canonical-config test to verify it passes**

Run: `pytest tests/test_pytest_config_canonical.py -v`
Expected: PASS.

**Step 6: Run the full suite and confirm the warning is gone**

Run: `pytest -q 2>&1 | grep -i "ignoring pytest config" ; echo "exit=$?"`
Expected: `exit=1` (grep finds nothing). The "ignoring pytest config in pyproject.toml" warning must no longer appear.

**Step 7: Confirm the `integration` marker is still recognised**

Run: `pytest --markers 2>&1 | grep integration`
Expected: One line showing the `integration` marker definition.

**Step 8: Commit**

```bash
git add pyproject.toml tests/test_pytest_config_canonical.py
git commit -m "$(cat <<'EOF'
fix(test-config): consolidate pytest config into pyproject.toml

pytest emitted "WARNING: ignoring pytest config in pyproject.toml!" on
every run because pytest.ini took precedence and silently overrode the
pyproject.toml [tool.pytest.ini_options] block.

- Migrate the `integration` marker from pytest.ini into pyproject.toml.
- Delete pytest.ini.
- Add tests/test_pytest_config_canonical.py — a regression guard that
  fails if pytest.ini, setup.cfg, or tox.ini reappears at repo root.
EOF
)"
```

---

## Task 3: Resolve slowapi deprecation warning

**Background:** slowapi 0.1.9 uses `asyncio.iscoroutinefunction` (deprecated in Python 3.12, removed in 3.16). Path forward depends on upstream:
- If slowapi has a fixed release → upgrade.
- If not → either pin Python to <3.16 in `requires-python` (kicks the can) or vendor a one-line monkey-patch.

**Files:**
- Read: `pyproject.toml` (`dependencies` section)
- Modify: `pyproject.toml`

**Step 1: Check upstream for a fixed slowapi version**

Run: `pip index versions slowapi 2>&1 | head -5`
Expected: A list of available versions. Note the highest.

**Step 2: Read the changelog of any version > 0.1.9**

Run: `pip show slowapi 2>&1 | grep -i homepage` then visit the GitHub releases page (laurents/slowapi). Look for any release that mentions "asyncio.iscoroutinefunction", "Python 3.12", "Python 3.14", or "DeprecationWarning".

**Step 3: Write a failing test that asserts no slowapi-derived DeprecationWarning leaks**

Create `tests/test_no_slowapi_deprecation.py`:

```python
"""Regression: importing the FastAPI app must not raise DeprecationWarning
from slowapi.

slowapi <=0.1.9 calls asyncio.iscoroutinefunction (removed in Python 3.16).
This test fails if the import path triggers that warning, forcing us to
upgrade slowapi (or pin Python compatibility) before CI catches it.
"""
from __future__ import annotations

import warnings


def test_app_import_emits_no_slowapi_deprecation() -> None:
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        import bazi_engine.app  # noqa: F401

    slowapi_warnings = [
        w for w in caught
        if issubclass(w.category, DeprecationWarning)
        and "slowapi" in (w.filename or "")
    ]
    assert not slowapi_warnings, (
        f"slowapi emitted {len(slowapi_warnings)} DeprecationWarning(s) on "
        f"import — first: {slowapi_warnings[0].message} at "
        f"{slowapi_warnings[0].filename}:{slowapi_warnings[0].lineno}"
    )
```

**Step 4: Run test to verify it fails (or passes — see Step 5 branch)**

Run: `pytest tests/test_no_slowapi_deprecation.py -v`

**Step 5: Branch on the result**

- **5a. Test PASSES** (slowapi already silent on import — warning only fires under load):
  - Adjust the test to also exercise a request: add a `TestClient(app).get("/health")` call inside the `catch_warnings` block.
  - Re-run; if it still passes, drop this task and commit only the test as a permanent guard. If it now fails, continue to 5b.

- **5b. Test FAILS:**
  - **If a fixed slowapi version exists** (from Step 2): bump the dependency.
    - Edit `pyproject.toml`: change `"slowapi>=0.1.9"` to `"slowapi>=0.X.Y"` (substituting the fixed version).
    - Run: `uv lock --upgrade-package slowapi`
    - Re-run the test.
  - **If no fix is available upstream**: file an upstream issue/PR, then apply a local mitigation:
    - Add a warning filter in `pyproject.toml` `[tool.pytest.ini_options]`:
      ```toml
      filterwarnings = [
          # slowapi 0.1.9 — upstream issue <link>; remove once fixed
          "ignore:'asyncio.iscoroutinefunction' is deprecated:DeprecationWarning:slowapi",
      ]
      ```
    - This narrowly silences only the slowapi case; other DeprecationWarnings still surface.
    - Update the test to assert the filter is in place rather than no-warning.

**Step 6: Verify no other DeprecationWarnings appeared**

Run: `pytest -q 2>&1 | grep -i deprecation | head -5`
Expected: empty (or only the explicitly-filtered slowapi case if 5b filter path was taken).

**Step 7: Commit**

```bash
git add pyproject.toml uv.lock tests/test_no_slowapi_deprecation.py
git commit -m "$(cat <<'EOF'
fix(deps): resolve slowapi asyncio.iscoroutinefunction deprecation

slowapi 0.1.9 used asyncio.iscoroutinefunction (removed in Python 3.16),
emitting a DeprecationWarning on every test run. <Strategy chosen above
— "upgraded to slowapi X.Y" or "added narrow filterwarning + upstream
issue ABC123">.

Add tests/test_no_slowapi_deprecation.py to fail loudly if the warning
ever reappears.
EOF
)"
```

---

## Task 4: Gitignore runtime artifacts

**Files:**
- Modify: `.gitignore`

**Step 1: Check current `.gitignore` for the runtime artifact paths**

Run: `grep -E "homunculus|observations\.jsonl" .gitignore`
Expected: empty (artifact is not yet ignored).

**Step 2: Append runtime-artifact patterns**

Edit `.gitignore` — append a clearly-labelled section:

```
# ── Runtime / local-only artifacts ──────────────────────────────────────────
# Telemetry and ephemeral runtime state from local Claude Code / homunculus
# integrations. These should never be committed.
.claude/homunculus/observations.jsonl
.claude/homunculus/*.local.jsonl
```

**Step 3: Confirm git stops tracking the modified file**

The file is currently tracked-and-modified. To stop tracking without deleting from disk:

Run: `git rm --cached .claude/homunculus/observations.jsonl`

**Step 4: Verify the file no longer appears in `git status`**

Run: `git status --short .claude/homunculus/`
Expected: `D  .claude/homunculus/observations.jsonl` (deletion of the tracked entry, real file untouched on disk).

**Step 5: Commit**

```bash
git add .gitignore .claude/homunculus/observations.jsonl
git commit -m "$(cat <<'EOF'
chore(git): gitignore runtime telemetry artifacts

.claude/homunculus/observations.jsonl is local runtime state that should
never be committed. Add the path (and a glob for related .local.jsonl
files) to .gitignore and untrack the existing file.
EOF
)"
```

---

## Task 5: Commit pre-existing legitimate dirty files

**Background:** `uv.lock` and `tests/test_daily_eastern_jieqi.py` are real, legitimate changes that have been in working state for multiple sessions. They should be committed as-is so the working tree is clean.

**Files:**
- Modify: none (just stage and commit existing changes)

**Step 1: Confirm `uv.lock` diff is purely the httpx + respx additions**

Run: `git diff uv.lock | grep -E "^[+-]" | grep -v "^+++\|^---"`
Expected: only `+ { name = "httpx" }` and `+ { name = "respx" }` lines (and matching package metadata blocks).

**Step 2: Verify `httpx` and `respx` are real declared deps in `pyproject.toml`**

Run: `grep -E '"httpx|"respx' pyproject.toml`
Expected: `httpx` in `dependencies`, `respx` in `[project.optional-dependencies] dev` or similar.

**Step 3: Run lockfile verification**

Run: `uv lock --check` (or `uv sync --check` if `--check` not supported)
Expected: lockfile matches pyproject.toml — no further updates needed.

**Step 4: Confirm the test fix is correct**

Run: `pytest tests/test_daily_eastern_jieqi.py::TestJieqiGracefulFallback -v`
Expected: PASS.

**Step 5: Commit the lockfile**

```bash
git add uv.lock
git commit -m "$(cat <<'EOF'
chore(deps): sync uv.lock with httpx + respx declared in pyproject.toml

httpx and respx have been declared in pyproject.toml for several sessions
but the lockfile entries were never committed. uv.lock is now consistent
with pyproject.toml; no version changes.
EOF
)"
```

**Step 6: Commit the test fix**

```bash
git add tests/test_daily_eastern_jieqi.py
git commit -m "$(cat <<'EOF'
fix(tests): make Jieqi summary parser tolerate trailing punctuation

TestJieqiGracefulFallback parsed the Solarterm name with rstrip(".")
which only worked if the name was the last token in the summary. The
template now appends a sentence after the term name, so split(".")[0]
correctly extracts the term token regardless of what follows.
EOF
)"
```

---

## Task 6: Triage and resolve Section C clutter

**Background:** Task 1 produced per-item decisions. This task executes them.

**Files:** depends on per-item decisions from Task 1.

**Step 1: For each item the user said `delete`**

Run: `git clean -fd <path>` for untracked dirs, or `rm <path>` for stray files.
Verify: `git status --short` no longer lists the item.

**Step 2: For each item the user said `move to <location>`**

Run: `mv <source> <destination>`.
Update any references if the moved item was a doc that linked to other docs.

**Step 3: For each item the user said `keep + commit`**

Run: `git add <path>` and include in a single hygiene commit.

**Step 4: For each item the user said `keep + gitignore`**

Append the path to `.gitignore` (separate hunk from Task 4's runtime artifacts) and commit `.gitignore` only.

**Step 5: Verify no Section C items remain**

Run: `ls 0 FuFirE-main/ FuFirE_API_Strategy/ GEMINI.md SDLC.md ai-scrum-scaffold/ hardening/ 2>&1 | grep -v "No such file"`
Expected: empty (or only the items the user explicitly chose to keep).

**Step 6: Commit per-decision**

Use one commit per disposition cluster:
- `chore(repo): remove stray empty file '0' and abandoned scaffolds`
- `chore(repo): move strategy docs to docs/strategy/`
- `chore(repo): gitignore generated working dirs`

(Adjust message per actual decisions.)

---

## Task 7: Add CI guard against stale snapshot regressions

**Background:** During the Phase B work, 50 wuxing/fusion snapshots had been left stale by an earlier algorithm fix (Codex PR #106 fixed `is_night_chart` but didn't refresh snapshots). Snapshots silently encoded the previous bug for weeks. A CI guard against snapshot mismatches that exist *but were never refreshed when source changed* is hard to write generically — a pragmatic alternative is to ensure CI runs the snapshot suite without `UPDATE_SNAPSHOTS=1` and fails on any mismatch. Verify that.

**Files:**
- Read: `.github/workflows/*.yml`
- Modify (only if missing): `.github/workflows/ci.yml`

**Step 1: Locate the CI workflow that runs pytest**

Run: `grep -rln "pytest" .github/workflows/ 2>&1`
Capture the workflow file path.

**Step 2: Confirm UPDATE_SNAPSHOTS is NOT set in any CI step**

Run: `grep -rn "UPDATE_SNAPSHOTS" .github/workflows/`
Expected: empty (the env var is only set locally for refresh runs).

**Step 3: Confirm the snapshot suite runs as part of `pytest -q`**

Run locally: `source .venv/bin/activate && pytest tests/test_snapshot_stability.py -q 2>&1 | tail -3`
Expected: PASS for all 200 snapshot tests.

**Step 4: If CI does not currently run the snapshot suite, add a dedicated step**

Edit the CI workflow to add (or confirm existence of) a step:

```yaml
      - name: Snapshot stability (no UPDATE_SNAPSHOTS)
        run: |
          # Explicit invocation guards against accidental UPDATE_SNAPSHOTS=1
          # leaking from cache or workflow env. A failure here means a source
          # change corrupted snapshots without a corresponding refresh commit.
          unset UPDATE_SNAPSHOTS
          pytest tests/test_snapshot_stability.py -q
```

**Step 5: Verify locally that the step would catch a corrupted snapshot**

Run a quick experiment:
```bash
# Temporarily corrupt one snapshot
sed -i.bak 's/"Erde"/"INVALID"/' tests/snapshots/moseph/std_2024_berlin__wuxing.json
pytest tests/test_snapshot_stability.py -q 2>&1 | tail -5
# Should FAIL with snapshot mismatch
mv tests/snapshots/moseph/std_2024_berlin__wuxing.json.bak tests/snapshots/moseph/std_2024_berlin__wuxing.json
pytest tests/test_snapshot_stability.py -q 2>&1 | tail -3
# Should PASS again
```

**Step 6: Commit (only if Step 4 was needed)**

```bash
git add .github/workflows/<file>.yml
git commit -m "$(cat <<'EOF'
ci: explicit snapshot stability gate (no UPDATE_SNAPSHOTS leak)

A dedicated CI step runs tests/test_snapshot_stability.py with
UPDATE_SNAPSHOTS unset, preventing the class of bug where an algorithm
change silently corrupts snapshots and the CI run masks it by treating
the new output as the new ground truth.
EOF
)"
```

If Step 4 was not needed (CI already runs snapshot tests as part of `pytest -q` and has no UPDATE_SNAPSHOTS leak), skip the commit and document the verification in `docs/runbooks/2026-05-01-pre-fix-baseline.md`.

---

## Task 8: Final verification + cleanup of baseline note

**Files:**
- Delete: `docs/runbooks/2026-05-01-pre-fix-baseline.md`

**Step 1: Run the full test suite**

Run: `source .venv/bin/activate && pytest -q 2>&1 | tail -5`
Expected: all green, **0 warnings** (or only the explicitly-filtered slowapi case if Task 3 took the filter path), warning count strictly less than the Task 0 baseline of 14.

**Step 2: Confirm `git status --short` is fully clean**

Run: `git status --short`
Expected: empty output. Any remaining dirty file is a regression of an earlier task — rerun that task.

**Step 3: Confirm OpenAPI is still in sync**

Run: `python scripts/export_openapi.py --check`
Expected: `OK: OpenAPI spec is up-to-date.`

**Step 4: Confirm linters and typecheck pass**

Run: `ruff check bazi_engine/ --output-format=github && mypy bazi_engine --ignore-missing-imports`
Expected: both succeed with no errors.

**Step 5: Delete the transient baseline note**

```bash
git rm docs/runbooks/2026-05-01-pre-fix-baseline.md
```

**Step 6: Commit**

```bash
git commit -m "$(cat <<'EOF'
chore(docs): remove transient pre-fix baseline note

The baseline captured during the pre-existing-issue cleanup is no
longer needed — every metric it referenced now lives as a regression
test (test_pytest_config_canonical.py, test_no_slowapi_deprecation.py)
or a CI guard.
EOF
)"
```

**Step 7: Final sanity check**

Run: `git log --oneline -10`
Expected: a clean sequence of small, well-scoped commits — one per task.

---

## Done criteria

When this plan is fully executed:

- [ ] `pytest -q` produces zero "ignoring pytest config" warnings
- [ ] `pytest -q` produces zero slowapi-related DeprecationWarnings (or only one filterwarning-suppressed case with an upstream issue link)
- [ ] `git status --short` is empty
- [ ] `ls` at repo root shows no stray files (`0`, `GEMINI.md`, etc. are either committed to a sensible location or deleted)
- [ ] `python scripts/export_openapi.py --check` passes
- [ ] `ruff check` and `mypy` pass
- [ ] Two new regression tests are in place: `test_pytest_config_canonical.py` and `test_no_slowapi_deprecation.py`
- [ ] CI runs the snapshot suite without `UPDATE_SNAPSHOTS` set

---

## Notes for the executor

- **Do NOT bundle Task 1 with anything that touches files in Section C** — Task 1 is a decision gate. The user must respond before Task 6 starts.
- **Each task is its own commit.** Do not squash. The history is a feature here — anyone reading `git log` should be able to see exactly which file each fix changed and why.
- **No `--force` or `--no-verify` git operations.** The repository hooks are part of the safety net being built.
- **The plan is intentionally separate from the in-flight Phase B PR #107 and Phase 5 work** (TASK-decanates-terms, TASK-fixed-star-conjunctions). Run this plan in `main` worktree only; do not interleave with feature branches.
