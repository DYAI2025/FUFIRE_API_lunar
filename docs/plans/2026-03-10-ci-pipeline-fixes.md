# CI Pipeline Fixes Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix all 3 CI failures on main: codegen chmod, ephemeris download, orphaned submodule.

**Architecture:** Three independent fixes to `.github/workflows/ci.yml` and git index cleanup. No application code changes.

**Tech Stack:** GitHub Actions, curl, git

---

### Task 1: Fix codegen chmod — use sudo

**Files:**
- Modify: `.github/workflows/ci.yml:104-105`

**Context:** The Docker openapi-generator action runs as root inside the container, writing files to `/github/workspace/generated/ts-client` as root. The GitHub Actions runner process can't `chmod` root-owned files. We need `sudo`.

**Step 1: Fix the chmod step**

Change line 105 from:
```yaml
        run: chmod -R u+w generated/ts-client
```
to:
```yaml
        run: sudo chmod -R u+w generated/ts-client
```

**Step 2: Commit**

```bash
git add .github/workflows/ci.yml
git commit -m "fix(ci): use sudo chmod for root-owned codegen files"
```

---

### Task 2: Fix ephemeris download URLs

**Files:**
- Modify: `.github/workflows/ci.yml:37-41`

**Context:** The current URLs (`https://www.astro.com/ftp/swisseph/ephe/...`) are returning HTML error pages instead of binary ephemeris files. The error message says: `Ephemeris file name 'sepl_18.se1' wrong; rename '<html xmlns="...">'`. Use the GitHub mirror at `https://github.com/aloistr/swisseph/raw/master/ephe/` which is reliable.

**Step 1: Replace download URLs**

Replace the curl block:
```yaml
          curl -sLO https://www.astro.com/ftp/swisseph/ephe/sepl_18.se1
          curl -sLO https://www.astro.com/ftp/swisseph/ephe/semo_18.se1
          curl -sLO https://www.astro.com/ftp/swisseph/ephe/seas_18.se1
          curl -sLO https://www.astro.com/ftp/swisseph/ephe/seplm06.se1
```

With:
```yaml
          curl -sLO https://github.com/aloistr/swisseph/raw/master/ephe/sepl_18.se1
          curl -sLO https://github.com/aloistr/swisseph/raw/master/ephe/semo_18.se1
          curl -sLO https://github.com/aloistr/swisseph/raw/master/ephe/seas_18.se1
          curl -sLO https://github.com/aloistr/swisseph/raw/master/ephe/seplm06.se1
```

**Step 2: Add a file validation step to prevent silent download failures**

After the download step, add:
```yaml
      - name: Verify ephemeris files are binary (not HTML error pages)
        run: |
          for f in /tmp/ephe/*.se1; do
            if head -c 5 "$f" | grep -q '<'; then
              echo "ERROR: $f contains HTML, not ephemeris data"
              exit 1
            fi
          done
          echo "All ephemeris files verified as binary"
```

**Step 3: Commit**

```bash
git add .github/workflows/ci.yml
git commit -m "fix(ci): use GitHub mirror for ephemeris downloads, add validation"
```

---

### Task 3: Remove orphaned submodule from git index

**Files:**
- Modify: git index (no file on disk)

**Context:** `BAFE-Bazi-zodiac-fusion-engine` exists in the git index as mode 160000 (submodule) but has no `.gitmodules` entry. This causes `fatal: No url found for submodule path` errors. It was added in commit `85bee74` but never properly configured. Remove the stale index entry.

**Step 1: Remove the orphaned submodule entry**

```bash
git rm --cached BAFE-Bazi-zodiac-fusion-engine
```

**Step 2: Remove the empty directory if it exists**

```bash
rmdir BAFE-Bazi-zodiac-fusion-engine 2>/dev/null || true
```

**Step 3: Commit**

```bash
git commit -m "fix: remove orphaned submodule entry (no .gitmodules URL)"
```

---

### Task 4: Verify and push

**Step 1: Run local tests to ensure nothing broke**

```bash
pytest -q --tb=short
```

Expected: All tests pass (unchanged — only CI config and git index modified).

**Step 2: Push to main**

```bash
git push origin main
```

**Step 3: Monitor CI**

```bash
gh run list --repo DYAI2025/BAFE --limit 1
# Wait for run to complete
gh run view <run-id> --repo DYAI2025/BAFE
```

Expected: All 4 jobs (test, typecheck, lint, codegen) pass.
