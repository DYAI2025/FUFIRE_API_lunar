# release-please Setup for the FuFirE Engine

## Goal

Give the FuFirE **engine** repo (`DYAI2025/FuFirE`) the same fixed, automated GitHub release numbering the BFF repo (`DYAI2025/FuFire_API_LIVE`) already has: `googleapis/release-please-action` opens/updates a standing "Release PR" from Conventional Commit messages on `main`; merging it cuts a `vX.Y.Z` git tag + GitHub Release + `CHANGELOG.md` entry and bumps `pyproject.toml`'s `version` field. No more manual, ad-hoc version strings.

## Non-goals

- **Not** touching `bazi_engine.__version__` or `spec/openapi/openapi.json`'s `info.version`. Those stay a manually-bumped "engine build" label, decoupled from the release-please-owned package version (decision: **Entkoppeln**, confirmed by Benjamin — see Preconditions). release-please's Python release-type only writes `pyproject.toml`.
- **Not** regenerating the ~30 committed golden snapshot fixtures (`tests/snapshots/swieph/*.json`) — they hard-code `engine_version`/`algorithm_version` as an exact string; since `__version__` doesn't move, they don't need to.
- **Not** enforcing squash-merge-only on the repo (it currently allows merge/squash/rebase and that has worked fine with Conventional Commit messages so far).
- **Not** cutting the first real release inside this task — the plan produces the tooling; the first release-please PR opens automatically and Benjamin merges it when ready (a real, GitHub-Release-cutting action outside the scope of an unattended plan execution).

## Preconditions / known gaps (confirmed 2026-07-13)

- Repo `DYAI2025/FuFirE`, default branch `main`, current HEAD `bce4a0ae6a83aba9346875bd687367f06eeb9162`. No existing git tags, no GitHub Releases, no release-please config.
- `pyproject.toml` `version = "1.0.0rc1"` (PEP 440, no hyphen — not valid strict SemVer). `bazi_engine/__init__.py __version__ = "1.0.0-rc1-20260220"` is a separate, manually-bumped, date-suffixed label used in API responses, the OpenAPI spec, and baked into ~30 golden snapshot fixtures (`tests/test_snapshot_stability.py::_approx_equal` does exact string equality on `engine_version`/`algorithm_version` — any change there is a mass fixture-touching change, deliberately out of scope here).
- `tests/test_version_consistency.py` (added in the prior cleanup phase, FUFIRE-013) currently asserts `pyproject.toml` version is a **prefix** of `__version__`. Once release-please starts bumping `pyproject.toml` independently (e.g. to `1.1.0` while `__version__` stays `1.0.0-rc1-20260220`), that assertion goes stale on the FIRST release-please merge. Must be relaxed in this same change (Task 5).
- **Benjamin's decisions (confirmed):**
  1. Starting version: **`1.0.0`** (drop `rc1` — engine is already production-deployed per CLAUDE.md, contract is frozen).
  2. `__version__`/golden-snapshot scheme: **decoupled**, unaffected by release-please.
  3. Legacy release docs: **archive** `RELEASE_NOTES.md` + `RELEASE_CHECKLIST.md` to `docs/archive/`, **reset** `CHANGELOG.md` to a clean Keep-a-Changelog baseline for release-please to own going forward.
- Repo allows squash/merge-commit/rebase (`allow_squash_merge/allow_merge_commit/allow_rebase_merge` all true) — no PR-title-lint currently exists (BFF repo has one via `amannn/action-semantic-pull-request@v6`). Existing commit history already follows Conventional Commits (`feat:`, `fix:`, `chore:`, `docs:`, `ci:`, `refactor:`, `test:`) throughout the last several months of work, including Dependabot's auto-titles — low risk, but adding the same lint as a safety net is cheap and keeps the two repos consistent.
- Reference implementation to mirror (already working in the sibling BFF repo): `~/Projects/SaaS/FuFirEProject/Fufire_API-landingpage/{release-please-config.json,.release-please-manifest.json,.github/workflows/release-please.yml,.github/workflows/pr-title-lint.yml}`.

## Task list

### RP-1 — `release-please-config.json` + `.release-please-manifest.json`

**Files:** create `release-please-config.json`, `.release-please-manifest.json` (repo root).

```json
// release-please-config.json
{
  "$schema": "https://raw.githubusercontent.com/googleapis/release-please/main/schemas/config.json",
  "release-type": "python",
  "bootstrap-sha": "bce4a0ae6a83aba9346875bd687367f06eeb9162",
  "packages": {
    ".": {
      "changelog-path": "CHANGELOG.md",
      "include-component-in-tag": false
    }
  }
}
```
```json
// .release-please-manifest.json
{ ".": "1.0.0" }
```
No `extra-files` entries (per the decoupling decision — release-please touches `pyproject.toml` only).

**Tests:** `python -c "import json; json.load(open('release-please-config.json')); json.load(open('.release-please-manifest.json'))"` — must parse. No repo test currently validates this file; none needed (it's config for an external GitHub Action, not application code).

**Acceptance evidence:** both files present, valid JSON, `bootstrap-sha` matches the pre-change HEAD so the first release-please PR only walks commits from this point forward (not the full ~160-commit history).

### RP-2 — `.github/workflows/release-please.yml`

**Files:** create `.github/workflows/release-please.yml`, mirroring the BFF's working workflow verbatim (language-agnostic action; config file decides the release-type).

```yaml
name: release-please

on:
  push:
    branches: [main]

permissions:
  contents: write
  pull-requests: write

concurrency:
  group: release-please
  cancel-in-progress: false

jobs:
  release-please:
    runs-on: ubuntu-latest
    steps:
      - uses: googleapis/release-please-action@v5
        with:
          config-file: release-please-config.json
          manifest-file: .release-please-manifest.json
```

**Tests:** `python -c "import yaml; yaml.safe_load(open('.github/workflows/release-please.yml'))"` clean.

**Acceptance evidence:** workflow file present; after this PR merges to `main`, the Actions tab shows a `release-please` run within a minute or two, and it either opens or updates a "chore(main): release 1.0.0" PR (verify post-merge — this is an observable side effect, not something `npm test`/`pytest` can assert).

### RP-3 — Bump `pyproject.toml` to the confirmed starting version

**Files:** modify `pyproject.toml` line 7.

```diff
- version = "1.0.0rc1"
+ version = "1.0.0"
```

This is the one-time manual "bootstrap" bump to the agreed starting point; release-please owns every bump after this.

**Tests:** `pytest tests/test_version_consistency.py -v` (will need Task 5's relaxation to pass — do Task 5 in the same commit or immediately after, before running the suite) and the full `pytest -q` (nothing else should reference `pyproject.toml`'s version directly except that test — verified in Preconditions research; re-grep to be sure: `grep -rn "1.0.0rc1" --include="*.py" --include="*.json"` should return nothing outside `pyproject.toml`/`.release-please-manifest.json` after this change).

**Acceptance evidence:** `pytest -q` still green at the baseline count; `python -c "import tomllib; print(tomllib.load(open('pyproject.toml','rb'))['project']['version'])"` prints `1.0.0`.

### RP-4 — PR title lint (safety net, mirrors BFF)

**Files:** create `.github/workflows/pr-title-lint.yml`.

```yaml
name: pr-title-lint

on:
  pull_request_target:
    types: [opened, edited, synchronize]

permissions:
  pull-requests: read

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: amannn/action-semantic-pull-request@v6
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

Verify against the BFF's actual file first (`cat ~/Projects/SaaS/FuFirEProject/Fufire_API-landingpage/.github/workflows/pr-title-lint.yml`) and copy its exact `types`/config (e.g. allowed commit types list, scopes) rather than retyping from memory, so both repos enforce identically.

**Tests:** `python -c "import yaml; yaml.safe_load(open('.github/workflows/pr-title-lint.yml'))"` clean.

**Acceptance evidence:** workflow present; this PR's own title (`ci: add release-please automated versioning`) passes the check once opened (observable on the PR itself post-push).

### RP-5 — Relax `tests/test_version_consistency.py`

**Files:** modify `tests/test_version_consistency.py`.

**Step 1 — read the current test** (already quoted in Preconditions) to see the exact assertion being removed.

**Step 2 — rewrite:** drop the cross-check between `pyproject.toml`'s version and `bazi_engine.__version__` (they are now two independently-versioned axes: release-please-owned package/release version vs. manually-curated engine-build label). Keep the still-valid half: `spec/openapi/openapi.json info.version == __version__` (that pairing is untouched by this change and still a real invariant — `scripts/export_openapi.py` derives the spec version from `__version__`, not from `pyproject.toml`).

```python
"""FUFIRE-013 guard, updated for release-please (2026-07): pyproject.toml's
`version` is now release-please-owned (bumped automatically from Conventional
Commits on every release) and is an independent axis from
`bazi_engine.__version__` — the manually-curated engine-build label embedded
in API responses, the OpenAPI spec, and the golden snapshot fixtures. This
test no longer cross-checks the two; it only guards the pairing that's still
a real invariant: the OpenAPI spec's info.version must track __version__
(scripts/export_openapi.py derives it from there, not from pyproject.toml).
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_openapi_spec_version_matches_engine_version() -> None:
    from bazi_engine import __version__

    spec = json.loads((ROOT / "spec/openapi/openapi.json").read_text())
    assert spec["info"]["version"] == __version__, (
        "spec/openapi/openapi.json info.version drifted from __version__ — "
        "run: python scripts/export_openapi.py"
    )
```

Consider renaming the file to `tests/test_openapi_spec_version.py` for clarity given the narrowed scope — check `tests/test_import_hierarchy.py`'s layer map and any other test that references this file by name before renaming (grep `test_version_consistency` repo-wide); if nothing hard-codes the filename, rename is safe and clearer. If anything does reference it by name, keep the filename and just update the docstring/body.

**Tests:** `pytest tests/test_version_consistency.py -v` (or the renamed path) passes; full `pytest -q` stays at the established baseline (2763 passed at last count on this branch's ancestor — confirm the exact current number by running the full suite once before starting, since more may have landed since).

**Acceptance evidence:** test file diff shows the cross-check removed and the docstring explains why (so a future reader doesn't "fix" it back); full suite green.

### RP-6 — CLAUDE.md versioning section

**Files:** modify `CLAUDE.md` (the "Versioning has two sources..." paragraph near the top).

Replace the current paragraph (which describes a manual dual-bump) with one describing the new split:

```markdown
Versioning has two independent axes: (1) the **package/release version** in
`pyproject.toml`, owned by [release-please](https://github.com/googleapis/release-please)
— it opens a release PR from Conventional Commit messages on every push to
`main`; merging it bumps the version, tags a GitHub Release, and updates
`CHANGELOG.md`. Never hand-edit `pyproject.toml`'s version. (2) the **engine
build label** `bazi_engine.__version__` (e.g. `1.0.0-rc1-20260220`), used in
API responses, the OpenAPI spec, and baked into golden snapshot fixtures —
still bumped manually, deliberately, alongside a snapshot regeneration, when
you want to move the engine's own build marker. Regenerate the OpenAPI spec
(`python scripts/export_openapi.py`) after changing `__version__`.
```

**Tests:** none (docs-only); sanity-read for internal consistency with the rest of the "Architecture" section directly below it.

**Acceptance evidence:** paragraph accurately describes the post-change state; no other part of CLAUDE.md still claims "update both".

### RP-7 — Archive legacy release docs, reset `CHANGELOG.md`

**Files:** `git mv RELEASE_NOTES.md docs/archive/`, `git mv RELEASE_CHECKLIST.md docs/archive/`, rewrite `CHANGELOG.md`.

**Step 1:** confirm `docs/archive/` exists (it does — created in the earlier cleanup phase) and move both files there with `git mv` (preserves history).

**Step 2:** rewrite `CHANGELOG.md` to a clean Keep-a-Changelog baseline release-please will prepend to:

```markdown
# Changelog

All notable changes to FuFirE — Fusion Firmament Engine — are documented here.
Format based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); this
project follows [Semantic Versioning](https://semver.org/) for the package
version in `pyproject.toml` (see CLAUDE.md — this is a different axis from
`bazi_engine.__version__`, the manually-curated engine build label).

Entries below this point are generated by
[release-please](https://github.com/googleapis/release-please) from
Conventional Commit messages on every merge to `main`.
```

The pre-existing stale "## [Unreleased] — codex/refactoring" section (documenting a security overhaul that predates and doesn't match this repo's actual visible git history — likely carried over from an earlier template/stub) is dropped entirely per Benjamin's decision; its content isn't lost (still in `git log` for `CHANGELOG.md` itself, retrievable via `git show <old-sha>:CHANGELOG.md` if ever needed).

**Tests:** none (docs-only). Grep repo-wide for anything that reads `RELEASE_NOTES.md`/`RELEASE_CHECKLIST.md` by path (CI, scripts, README links) before moving, so nothing breaks: `grep -rn "RELEASE_NOTES\|RELEASE_CHECKLIST" --include="*.py" --include="*.yml" --include="*.md" .` — fix any found reference to point at the new `docs/archive/` path.

**Acceptance evidence:** `git status` shows the two files as renames (not delete+add, so history is preserved); `CHANGELOG.md` is the clean baseline above; no dangling reference to the old paths remains.

### RP-8 — Full gate + PR

**Files:** none new; verification only.

```bash
ruff check bazi_engine/ tests/ scripts/
mypy bazi_engine --ignore-missing-imports
pytest -q
python scripts/export_openapi.py --check   # must stay clean — __version__ untouched
python -c "import yaml,glob; [yaml.safe_load(open(f)) for f in glob.glob('.github/workflows/*.yml')]; print('YAML OK')"
```

Commit as logical units (config+workflow / pyproject bump+test relax / docs), push, open a PR titled `ci: add release-please automated versioning` (itself must pass RP-4's new lint), get CI green, then **stop and report** — do not auto-merge. This PR's merge is what triggers `release-please.yml` to run for the first time and open the actual "chore(main): release 1.0.0" PR; that second PR is the one that cuts the real GitHub Release, and Benjamin should be the one who merges *that* (first-release sanity check), consistent with "Not cutting the first real release inside this task" in Non-goals.

**Acceptance evidence:** all gates above green; PR open, CI green, reported back with the PR URL and an explicit note that a second, bot-authored release PR will appear after this merges.

## Risks and rollback

- **Risk:** release-please's Python strategy might not auto-detect `[project].version` in this exact `pyproject.toml` shape (some versions of the strategy look for `[tool.poetry]` by default and need explicit config for PEP 621 `[project]` tables). **Mitigation:** RP-8's acceptance evidence is deliberately "PR open + CI green", not "release PR already appeared" — the release-please workflow only runs on **push to main**, so its real behavior can't be observed on a feature branch. After this PR merges, watch the Actions tab for the `release-please` run and inspect its logs/PR diff before trusting it; if it fails to bump `pyproject.toml` correctly, the fix is a one-line `extra-files` addition or switching to `release-type: simple` + explicit `extra-files` — cheap to correct in a follow-up, doesn't require reverting this PR.
- **Risk:** `bootstrap-sha` pinned to a specific commit becomes stale if this PR takes a long time to merge (commits land on `main` in between). **Mitigation:** re-verify `bootstrap-sha` equals `git rev-parse origin/main` immediately before the final push in RP-8, update if `main` moved.
- **Rollback:** every change here is additive-or-cosmetic (new config/workflow files, a version-string bump, a test relaxation, doc moves) with zero runtime/domain-math impact. Revert = revert the single squash-merged PR. No golden snapshots, no API contract, no deployed behavior changes.
