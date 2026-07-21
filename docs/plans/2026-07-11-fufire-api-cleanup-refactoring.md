# FuFirE API Cleanup & Refactoring Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make the FuFirE engine (and its LIVE/BFF consumer) maintainable, modular for future endpoints, and contract-truthful — via TDD slices, hardened CI/CD, and conservative extraction (no rewrite, no domain-math changes).

**Architecture:** Conservative modularization (audit Option A). The ENGINE keeps its router/domain layering; `app.py` is decomposed into a thin factory + extracted OpenAPI post-processing, error handlers, and a declarative router-mount registry. Contract authority becomes CI-published artifacts consumed by LIVE. Security/quota claims are made truthful before any extraction.

**Tech Stack:** Python 3.10–3.12 / FastAPI / slowapi / pytest; Node 20 / Express 4 / vitest / Playwright (LIVE repo); GitHub Actions; Railway (engine deploy authority — confirm, see Decision D1).

**Repos:**
- ENGINE: `/Users/benjaminpoersch/Projects/SaaS/FuFire-API/FuFirE` (this repo — Phases 0–3, 5)
- LIVE/BFF: `/Users/benjaminpoersch/Projects/SaaS/FuFirEProject/Fufire_API-landingpage` (Phase 4 — separate PRs there)

---

## Context: validated audit findings (2026-07-11)

External audit (GPT-5.6, AUDIT_ONLY, run `fufire-rpe-audit-20260711-2123`) produced 15 findings. All were re-validated against the **current** working trees by 8 verification agents. Result:

| Finding | Verdict vs current code | Delta vs audit |
|---|---|---|
| FUFIRE-001 contract drift ENGINE↔LIVE | CONFIRMED | Drift is **larger**: local LIVE checkout is 13 commits behind origin/main; even origin/main misses 4 schemas, ~29 changed |
| FUFIRE-002 stale LIVE fixture (53 ops vs 65) | CONFIRMED | Deliberately frozen fixture; nothing verifies its age |
| FUFIRE-003 BFF spec omits 10 ops (4 keys + 6 orgs) | CONFIRMED | — |
| FUFIRE-004 unlimited protected routes | CONFIRMED | **6 routes, not 5** — audit missed `POST /chart` (chart.py:170). No `default_limits`, no `SlowAPIMiddleware` → undecorated = unlimited |
| FUFIRE-005 daily quotas unenforced | CONFIRMED | `requests_per_day` never consumed anywhere; OpenAPI description advertises a Requests/day table |
| FUFIRE-006 auth fail-open dev-mode | CONFIRMED | `auth.py:230-243`: empty keys + no store + `FUFIRE_REQUIRE_API_KEYS` unset → unlimited dev-mode KeyInfo |
| FUFIRE-007 non-durable KeyStore | CONFIRMED | Only email-funnel `ff_free_` keys affected; dashboard `ff_live_` keys are Supabase-durable. Engine restart silently invalidates emailed keys; jti idempotency also resets |
| FUFIRE-008 app.ts 1812-line hotspot | CONFIRMED | 15 modules already extracted; proxy/explain/horoscope/transit/key-email-flow/spec-loading still inline |
| FUFIRE-009 request-ID echoes anything vs `format: uuid` | CONFIRMED | 66 uuid-format declarations in spec; client value reaches logs + error bodies |
| FUFIRE-010 no green audit baseline | ARTIFACT of audit host (Python 3.13) | Engine CI **is** green on 3.10/3.11/3.12 — W0 shrinks massively |
| FUFIRE-013 version dual-source | CONFIRMED | `pyproject 1.0.0rc1` vs `__version__ 1.0.0-rc1-20260220` |
| FUFIRE-014 stale Fly refs | PARTIAL | `fly.toml` already deleted (commit 3cfd7ce, 2026-06-10); CLAUDE.md claim stale; `fly.launch.toml` + auth.py:146 comment remain |
| FUFIRE-015 validator compile failure → per-request throw | CONFIRMED | Express 4 async handler, no try/catch → hung request / unhandled rejection |

**Additional issues the audit missed** (found by inventory agents):
- Dead code: `bazi_engine/routers/chart_ui.py` (1,144 LOC, zero references, unmounted).
- Foreign code: `tools/` contains LeanDeep-project files; `pytest.ini` registers a stale LeanDeep `integration` marker and **shadows** `[tool.pytest.ini_options]` in pyproject.
- Root clutter: empty file `0`, `BAFE-patch.tar`, stale workflow copies `ci.yml`/`tests.yml`/`bazi_engine_actions.yml` at repo root (root `ci.yml` differs from `.github/workflows/ci.yml`), `fly.launch.toml`, license contradiction (`Lizenz: Creative Commons BY-NC-SA 4.0.md` vs `Proprietary` in pyproject), `test_ephe.py` at root, misc report .md files.
- **No `[tool.ruff]` / `[tool.mypy]` config at all** — ruff runs pure defaults (E4/E7/E9/F only), mypy non-strict; `tests/` and `scripts/` are never linted; ruff/mypy unpinned in CI and absent from dev extras.
- CI gaps: no security scanning (pip-audit/bandit/CodeQL/secret scan), no dependabot, no Docker build test, no SBOM, no contract-artifact publishing, no pip caching, no concurrency groups, no coverage upload; `deploy-cloudrun.yml` has `needs: []` (not gated on tests).
- **Two apparently-active deploy paths**: Railway (CLAUDE.md, railway.toml) *and* Cloud Run (`deploy-cloudrun.yml` + `cloudbuild.yaml`). Authority unclear.
- `routers/match.py` (912 LOC) + `bazi_engine/match/` missing from CLAUDE.md router table.

## Decisions — RESOLVED by Benjamin 2026-07-12

- **D1 — Deploy authority: Railway.** Task 1.11: archive `deploy-cloudrun.yml` + `cloudbuild.yaml`; Cloud Run service to be decommissioned (verify `api.fufire.space` DNS first). Fail-closed env (Task 2.17) is set in the Railway dashboard.
- **D2 — Daily quotas: truth-first.** Remove/reword the unenforced Requests/day claims (Task 2.18); durable metering is a later opt-in slice.
- **D3 — Key plane: Option A.** Retire engine email-issuance in favor of the Supabase-backed BFF key plane; ADR-002 (Task 2.19) records this; engine `/v1/admin/keys` gets deprecated. Implementation slice follows after this plan.
- **D4 — Root files: DELETE approved.** Task 0.3 may `git rm` (not just archive): `GEMINI.md`, `QWEN.md`, `ai-scrum-scaffold/`, `concilium/` (move its one report to `docs/archive/` first), `FuFirE_API_Strategy`, `Procfile`, `api/index.py`, `Lizenz: Creative Commons BY-NC-SA 4.0.md` (license = Proprietary per pyproject). **Exception: keep `3-code/`** — actively referenced by CLAUDE.md SDLC structure.

## Definition of Done — every task

1. Characterization/failing test written **before** the change (TDD).
2. `pytest -q` green; `ruff check` green; `mypy bazi_engine --ignore-missing-imports` green.
3. `python scripts/export_openapi.py --check` passes (byte-identical spec) **unless the task explicitly changes the contract**, in which case regenerate + review the semantic diff.
4. No domain-math change, ever, in this plan (protected zone: `bazi.py`, `jieqi.py`, `solar_time.py`, `fusion.py` math, `wuxing/`, constants).
5. One commit per task (conventional commits, as in git history).
6. After any merge to `main`: Railway auto-deploys → run the live smoke (Task 5.31) — verify the deployed artifact, not just local tests.

---

# Phase 0 — Hygiene & Baseline (no behavior change)

### Task 0.1: Branch + green baseline

**Step 1:** Create the working branch:
```bash
cd /Users/benjaminpoersch/Projects/SaaS/FuFire-API/FuFirE
git checkout -b refactor/phase0-hygiene
```

**Step 2:** Record the baseline (all must pass before touching anything):
```bash
source .venv/bin/activate  # or: python3.10 -m venv .venv && pip install -e ".[dev]"
pytest -q                                  # expected: ~1500 passed, some skipped (ephemeris)
ruff check bazi_engine/                    # expected: clean
mypy bazi_engine --ignore-missing-imports  # expected: clean
python scripts/export_openapi.py --check   # expected: "OpenAPI spec is up to date"
```
If anything fails here, STOP — fix `main` first; this plan assumes a green baseline.

**Step 3:** Commit nothing yet (baseline only).

### Task 0.2: Delete dead code — `chart_ui.py` and LeanDeep leftovers

**Files:**
- Delete: `bazi_engine/routers/chart_ui.py` (1,144 LOC, unmounted, zero refs)
- Delete: `tools/leandeep_client.py` + other LeanDeep-only files in `tools/` (verify each)

**Step 1:** Verify zero references (must print nothing except the file itself):
```bash
grep -rn "chart_ui" bazi_engine/ tests/ scripts/ docs/ | grep -v "routers/chart_ui.py"
grep -rn "leandeep\|LeanDeep" bazi_engine/ tests/ scripts/ --include="*.py" | grep -v tools/
```

**Step 2:** Delete:
```bash
git rm bazi_engine/routers/chart_ui.py
# for each verified-unreferenced LeanDeep file:
git rm tools/leandeep_client.py
```

**Step 3:** Run: `pytest -q && ruff check bazi_engine/` — expected: green, same counts as baseline.

**Step 4:** Commit:
```bash
git commit -m "chore: remove dead chart_ui router (1144 LOC, never mounted) and LeanDeep leftovers in tools/"
```

### Task 0.3: Root-directory cleanup

**Files (delete):** `0` (empty), `BAFE-patch.tar`, root `ci.yml`, root `tests.yml`, root `bazi_engine_actions.yml`, `fly.launch.toml`
**Files (move to `docs/archive/`):** `claudeTest0502.md`, `gap_report.md`, `audit-fix-log.md`, `der_fix_drei_cascading_failures_dein_build_fehler.md`, `scripts/fufire_api_audit_report.md`
**Files (move):** `test_ephe.py` → `tests/` (or delete if redundant with existing ephemeris tests — check content first), `benchmark_performance.py` → `scripts/`
**Decision D4 items (do NOT touch without approval):** `GEMINI.md`, `QWEN.md`, `3-code/`, `ai-scrum-scaffold/`, `concilium/`, `FuFirE_API_Strategy`, `Procfile`, `api/index.py`, `Lizenz: Creative Commons BY-NC-SA 4.0.md` (license contradiction → Benjamin decides Proprietary vs CC)

**Step 1:** Verify the root workflow copies are unused duplicates:
```bash
diff ci.yml .github/workflows/ci.yml | head -20     # expected: differences → root copy is stale
grep -rn "bazi_engine_actions\|action_compute" .github/ || echo "unused in .github"
```
If `scripts/action_compute.py` is only consumed by root `bazi_engine_actions.yml`, delete both; otherwise keep the script.

**Step 2:** Execute deletions/moves:
```bash
mkdir -p docs/archive
git rm "0" BAFE-patch.tar ci.yml tests.yml bazi_engine_actions.yml fly.launch.toml
git mv claudeTest0502.md gap_report.md audit-fix-log.md der_fix_drei_cascading_failures_dein_build_fehler.md docs/archive/
git mv scripts/fufire_api_audit_report.md docs/archive/
git mv benchmark_performance.py scripts/
# inspect test_ephe.py first:
sed -n 1,40p test_ephe.py   # then either: git mv test_ephe.py tests/  OR  git rm test_ephe.py
```

**Step 3:** Run: `pytest -q` — expected green (nothing imported from moved files).

**Step 4:** Commit: `git commit -m "chore: clean repo root — remove stale workflow copies, fly.launch.toml, tars; archive one-off reports"`

### Task 0.4: Unify pytest config, fix coverage threshold location

**Files:**
- Delete: `pytest.ini` (currently shadows pyproject and registers a stale LeanDeep marker)
- Modify: `pyproject.toml`

**Step 1:** Read `pytest.ini` and `[tool.pytest.ini_options]` in pyproject; merge every still-relevant setting into pyproject. Register real markers:
```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
markers = [
    "swieph: requires Swiss Ephemeris SE1 data files (auto-skipped without them)",
    "anyio: async tests",
]
```
Drop the LeanDeep `integration` marker text. Add coverage threshold to config instead of CLI-only:
```toml
[tool.coverage.report]
fail_under = 75
```

**Step 2:** Delete `pytest.ini`:
```bash
git rm pytest.ini
```

**Step 3:** Run: `pytest -q` — expected: identical pass/skip counts (marker auto-skip for swieph still works — it lives in `tests/conftest.py`, not pytest.ini). Then `pytest -q --cov=bazi_engine` — expected: fails under 75 threshold now enforced from config too.

**Step 4:** Commit: `git commit -m "chore(test): single pytest config in pyproject; drop stale LeanDeep marker; coverage threshold in config"`

### Task 0.5: Fix stale docs (CLAUDE.md)

**Files:** Modify: `CLAUDE.md`

**Step 1:** Fix: (a) "`fly.toml` is retained but Fly.io is not the active deployment target" → replace with "Fly.io is decommissioned (fly.toml removed 2026-06-10); Railway is the deploy target"; (b) add `match.py` router row to the router table (`/v1/match/bazi-hehun`, v1-only per DECISION-001) and mention `bazi_engine/match/` subpackage; (c) fix stale comment `bazi_engine/auth.py:146` ("update the Fly secret" → "update the Railway variable").

**Step 2:** Run: `pytest -q -k rebrand` (name-consistency tests) — expected green.

**Step 3:** Commit: `git commit -m "docs: CLAUDE.md matches reality — Fly decommissioned, match router documented; fix stale Fly comment in auth.py"`

**Phase 0 exit:** PR `refactor/phase0-hygiene` → main. All gates green. After merge + Railway deploy: live smoke.

---

# Phase 1 — Guardrails: lint/type config + CI/CD hardening

### Task 1.6: Pin and configure ruff + mypy

**Files:**
- Modify: `pyproject.toml`

**Step 1:** Add to dev extras (pinned minimums):
```toml
[project.optional-dependencies]
dev = [
    # ... existing entries ...
    "ruff>=0.8",
    "mypy>=1.13",
]
```

**Step 2:** Add tool config — deliberately gradual (do NOT jump to strict; 19.9k LOC):
```toml
[tool.ruff]
line-length = 120
target-version = "py310"

[tool.ruff.lint]
# current CI default (E4/E7/E9/F) + imports, bugbear, pyupgrade
select = ["E4", "E7", "E9", "F", "I", "B", "UP"]
ignore = []

[tool.mypy]
python_version = "3.10"
ignore_missing_imports = true
warn_unused_ignores = true
warn_redundant_casts = true
no_implicit_optional = true
```

**Step 3:** Run and auto-fix the fallout:
```bash
pip install -e ".[dev]"
ruff check bazi_engine/ tests/ scripts/ --fix
ruff check bazi_engine/ tests/ scripts/      # remaining findings: fix manually or add targeted per-file-ignores
mypy bazi_engine --ignore-missing-imports    # expected: clean or small fixable set
pytest -q
```
Rule of thumb: mechanical fixes (import order, `Optional[X]` → `X | None`) yes; anything touching domain modules' logic — DON'T, add a per-file-ignore instead.

**Step 4:** Commit: `git commit -m "chore(lint): pin ruff/mypy in dev extras; add ruff config (I,B,UP) and mypy config; apply autofixes"`

### Task 1.7: CI — lint everything, pin tools, cache pip, add concurrency

**Files:** Modify: `.github/workflows/ci.yml`

**Step 1:** Changes:
- Top-level concurrency group:
```yaml
concurrency:
  group: ci-${{ github.ref }}
  cancel-in-progress: true
```
- In `lint` and `typecheck` jobs: replace unpinned `pip install ruff` / `pip install mypy` with `pip install -e ".[dev]"` (tools now pinned via extras).
- Lint scope: `ruff check bazi_engine/ tests/ scripts/ --output-format=github`.
- Add `cache: pip` to every `actions/setup-python` step.

**Step 2:** Run locally what CI will run (same commands). Push branch, verify all CI jobs green on the PR.

**Step 3:** Commit: `git commit -m "ci: lint tests+scripts, pin tool versions via dev extras, pip caching, cancel-in-progress"`

### Task 1.8: CI — security job + dependabot

**Files:**
- Create: `.github/dependabot.yml`
- Modify: `.github/workflows/ci.yml`

**Step 1:** New CI job:
```yaml
  security:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
          cache: pip
      - name: Install audit tools
        run: pip install pip-audit bandit
      - name: Dependency vulnerabilities (lockfile)
        run: pip-audit -r requirements.lock --strict
      - name: SAST (bandit, medium+ severity)
        run: bandit -r bazi_engine -ll
```

**Step 2:** `.github/dependabot.yml`:
```yaml
version: 2
updates:
  - package-ecosystem: pip
    directory: /
    schedule: { interval: weekly }
    open-pull-requests-limit: 5
  - package-ecosystem: github-actions
    directory: /
    schedule: { interval: weekly }
  - package-ecosystem: docker
    directory: /
    schedule: { interval: weekly }
```

**Step 3:** Run `pip-audit -r requirements.lock --strict` and `bandit -r bazi_engine -ll` locally first; triage any existing findings (fix or documented `# nosec` with reason) so the job lands green.

**Step 4:** Commit: `git commit -m "ci: add security job (pip-audit on lockfile, bandit SAST) and dependabot for pip/actions/docker"`

### Task 1.9: CI — Docker build test

**Files:** Modify: `.github/workflows/ci.yml`

**Step 1:** New job (build only, no push — validates the multi-stage ephemeris SHA verification on every PR instead of at deploy time):
```yaml
  docker-build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: docker/setup-buildx-action@v3
      - uses: docker/build-push-action@v6
        with:
          context: .
          push: false
          tags: fufire-engine:ci
          cache-from: type=gha
          cache-to: type=gha,mode=max
```

**Step 2:** Push, verify job green (first run is slow — ephe download; cached afterwards).

**Step 3:** Commit: `git commit -m "ci: build Docker image on every PR (validates ephemeris SHA + multi-stage build before deploy)"`

### Task 1.10: CI — coverage artifact upload

**Files:** Modify: `.github/workflows/ci.yml` (test job)

**Step 1:** After the pytest step:
```yaml
      - name: Coverage XML
        if: matrix.python-version == '3.12'
        run: coverage xml
      - uses: actions/upload-artifact@v4
        if: matrix.python-version == '3.12'
        with:
          name: coverage-xml
          path: coverage.xml
```

**Step 2:** Commit: `git commit -m "ci: upload coverage report artifact"`

### Task 1.11: Deploy pipeline sanity (Decision D1)

**Files:** Modify: `.github/workflows/deploy-cloudrun.yml` (or delete it, per D1)

**Step 1:** Ask Benjamin (D1): Railway (auto-deploy on main, per CLAUDE.md + railway.toml) vs Cloud Run (`deploy-cloudrun.yml` + `cloudbuild.yaml`) — which is production?
- If **Railway**: archive `deploy-cloudrun.yml` + `cloudbuild.yaml` to `docs/archive/` (or delete), remove the ambiguity.
- If **Cloud Run stays** (even as secondary): gate it — change `needs: []` to reference the CI workflow (or convert to `workflow_run` on CI success), so an untested commit can never deploy.

**Step 2:** Commit: `git commit -m "ci(deploy): single documented deploy authority; deploys gated on green CI"`

### Task 1.12: Version-consistency test (FUFIRE-013)

**Files:**
- Create: `tests/test_version_consistency.py`

**Step 1: Write the failing-or-green test** (it documents the invariant; today it should pass — it will catch the next unsynchronized bump):
```python
"""FUFIRE-013 guard: the three version surfaces must stay consistent.

pyproject `1.0.0rc1` is the PEP440 package version; `__version__`
`1.0.0-rc1-20260220` adds a build-date suffix; the OpenAPI spec must carry
exactly `__version__`.
"""
import json
import sys
from pathlib import Path

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

ROOT = Path(__file__).resolve().parents[1]


def test_version_sources_consistent() -> None:
    from bazi_engine import __version__

    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text())
    pkg_version = pyproject["project"]["version"]           # e.g. 1.0.0rc1
    normalized = __version__.replace("-rc", "rc")           # 1.0.0rc1-20260220
    assert normalized.startswith(pkg_version), (
        f"bazi_engine.__version__={__version__!r} does not extend "
        f"pyproject version {pkg_version!r} — bump BOTH (see CLAUDE.md)"
    )

    spec = json.loads((ROOT / "spec/openapi/openapi.json").read_text())
    assert spec["info"]["version"] == __version__, (
        "spec/openapi/openapi.json info.version drifted from __version__ — "
        "run: python scripts/export_openapi.py"
    )
```

**Step 2:** Run: `pytest tests/test_version_consistency.py -v` — expected: PASS (if it fails, the surfaces have already drifted — fix them first).

**Step 3:** Commit: `git commit -m "test: guard pyproject/__version__/openapi version consistency (FUFIRE-013)"`

### Task 1.13: CI — contract artifact publishing (engine side of W1)

**Files:** Modify: `.github/workflows/ci.yml`

**Step 1:** New job — publishes the OpenAPI spec with provenance so LIVE can consume an exact artifact instead of hand-copying (root cause of FUFIRE-001):
```yaml
  contract-artifact:
    needs: test
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12", cache: pip }
      - run: pip install -e .
      - name: Verify spec is current
        run: python scripts/export_openapi.py --check
      - name: Provenance metadata
        run: |
          python - <<'EOF'
          import hashlib, json, os, pathlib
          spec = pathlib.Path("spec/openapi/openapi.json").read_bytes()
          meta = {
              "sha256": hashlib.sha256(spec).hexdigest(),
              "commit": os.environ["GITHUB_SHA"],
              "ref": os.environ["GITHUB_REF"],
              "version": json.loads(spec)["info"]["version"],
          }
          pathlib.Path("openapi.provenance.json").write_text(json.dumps(meta, indent=2))
          print(meta)
          EOF
      - uses: actions/upload-artifact@v4
        with:
          name: openapi-contract
          path: |
            spec/openapi/openapi.json
            openapi.provenance.json
```

**Step 2:** Push, verify artifact appears on the workflow run.

**Step 3:** Commit: `git commit -m "ci: publish OpenAPI contract artifact with sha256+commit provenance (contract authority, FUFIRE-001)"`

**Phase 1 exit:** PR → main. CI now: test matrix + lint(all) + typecheck + complexity + codegen + security + docker-build + contract-artifact, all cached/pinned/concurrent.

---

# Phase 2 — Security & contract-truth fixes (strict TDD)

### Task 2.14: Failing test — every protected route must be rate-limited (FUFIRE-004)

**Files:**
- Create: `tests/test_rate_limit_coverage.py`

**Step 1: Write the failing test.** slowapi registers decorated endpoints in `limiter._route_limits` keyed by `"<module>.<qualname>"` (verified against installed slowapi source, `extension.py:704`). The app has no `default_limits` and no `SlowAPIMiddleware`, so an undecorated protected route has **no limit at all**:
```python
"""FUFIRE-004 guard: every API-key-protected route carries @limiter.limit.

Without default_limits/SlowAPIMiddleware, a route missing the decorator is
completely unlimited — an authenticated free-tier key could hammer ephemeris-
heavy endpoints unboundedly. This test makes that class of bug impossible.
"""
from fastapi.routing import APIRoute

from bazi_engine.app import app
from bazi_engine.limiter import limiter

# Routes that are deliberately NOT rate-limited must be listed here with a reason.
UNLIMITED_ALLOWLIST: set[str] = set()


def _is_protected(route: APIRoute) -> bool:
    names = {d.call.__name__ for d in route.dependant.dependencies if d.call is not None}
    return "require_api_key" in names


def _is_limited(route: APIRoute) -> bool:
    fn = route.endpoint
    return f"{fn.__module__}.{fn.__qualname__}" in limiter._route_limits


def test_every_protected_route_is_rate_limited() -> None:
    missing = sorted(
        {
            f"{sorted(r.methods)} {r.path}"
            for r in app.routes
            if isinstance(r, APIRoute)
            and _is_protected(r)
            and not _is_limited(r)
            and r.path not in UNLIMITED_ALLOWLIST
        }
    )
    assert not missing, "Protected routes without @limiter.limit:\n" + "\n".join(missing)
```

**Step 2:** Run: `pytest tests/test_rate_limit_coverage.py -v`
Expected: **FAIL**, listing exactly these logical routes on both mounts (12 entries): `/calculate/wuxing`, `/calculate/tst`, `/transit/state`, `/transit/timeline`, `/transit/narrative` (+ `/v1/...` twins), and `/chart` (legacy mount only).
If the listed set differs, investigate before proceeding.

**Step 3:** Commit the red test (it pins the current gap):
```bash
git add tests/test_rate_limit_coverage.py
git commit -m "test: failing coverage test — 6 protected routes lack rate limiting (FUFIRE-004)"
```

### Task 2.15: Decorate the 6 unlimited routes

**Files:**
- Modify: `bazi_engine/routers/fusion.py` (`/wuxing` ~line 264, `/tst` ~line 290)
- Modify: `bazi_engine/routers/transit.py` (`/state` ~238, `/timeline` ~247, `/narrative` ~255)
- Modify: `bazi_engine/routers/chart.py` (`/chart` ~170; also add the limiter import)

**Step 1:** Follow the existing house pattern exactly (see `transit.py:202-205`): `@router.<method>` outermost, `@limiter.limit(tier_limit)` beneath, and slowapi **requires** `request: Request` as a handler parameter — all 6 handlers currently lack it. Pattern:
```python
@router.post("/wuxing", response_model=WxResponse)
@limiter.limit(tier_limit)
def calculate_wuxing_endpoint(request: Request, req: WxRequest) -> ...:
```
In `chart.py` add: `from ..limiter import limiter, tier_limit` and `from fastapi import Request` (match existing imports in transit.py).

**Step 2:** Run: `pytest tests/test_rate_limit_coverage.py -v` — expected: PASS.

**Step 3:** Run the full suite: `pytest -q` — expected green (the `reset_rate_limiter` autouse fixture in conftest keeps tests isolated).

**Step 4:** Verify no contract drift: `python scripts/export_openapi.py --check` — expected: pass (decorators don't change schemas; the spec already advertised 429/X-RateLimit on these routes — now it's true).

**Step 5:** Commit: `git commit -m "fix(security): rate-limit all protected routes — wuxing, tst, transit state/timeline/narrative, chart (FUFIRE-004)"`

### Task 2.16: Request-ID hardening (FUFIRE-009)

**Files:**
- Create: `tests/test_request_id_http.py`
- Modify: `bazi_engine/middleware.py`

**Step 1: Write failing boundary tests** (WS-A convention: assert at the HTTP boundary via TestClient, never on internals):
```python
"""FUFIRE-009: X-Request-ID must honour the contract (format: uuid).

Spec declares format:uuid at every endpoint; runtime previously echoed any
client bytes into the response header, error envelopes and logs.
"""
import uuid

from fastapi.testclient import TestClient

from bazi_engine.app import app

client = TestClient(app)


def test_valid_uuid_is_echoed() -> None:
    rid = str(uuid.uuid4())
    resp = client.get("/health", headers={"X-Request-ID": rid})
    assert resp.headers["X-Request-ID"] == rid


def test_garbage_request_id_is_replaced_with_fresh_uuid() -> None:
    resp = client.get("/health", headers={"X-Request-ID": "A" * 4096 + "<script>"})
    echoed = resp.headers["X-Request-ID"]
    uuid.UUID(echoed)  # must parse — i.e. NOT the attacker bytes


def test_error_envelope_request_id_is_uuid() -> None:
    resp = client.post(
        "/v1/calculate/bazi",
        json={"nonsense": True},
        headers={"X-Request-ID": "not-a-uuid", "X-API-Key": "irrelevant"},
    )
    body = resp.json()
    if "request_id" in body:
        uuid.UUID(body["request_id"])
```

**Step 2:** Run: `pytest tests/test_request_id_http.py -v` — expected: 2nd and 3rd tests FAIL (garbage echoed today).

**Step 3:** Implement in `middleware.py` (replace line 25):
```python
def _safe_request_id(raw: str | None) -> str:
    """Return the client id iff it is a canonical UUID, else mint one.

    The OpenAPI contract declares X-Request-ID as format:uuid; anything else
    would put attacker-controlled bytes into response headers, error bodies
    and logs (FUFIRE-009).
    """
    if raw:
        try:
            return str(uuid.UUID(raw))
        except ValueError:
            pass
    return str(uuid.uuid4())
```
and in `dispatch`: `request_id = _safe_request_id(request.headers.get("X-Request-ID"))`.

**Step 4:** Run: `pytest tests/test_request_id_http.py -v && pytest -q` — expected: PASS / green. `python scripts/export_openapi.py --check` — pass (code now matches the existing contract; no spec change).

**Step 5:** Commit: `git commit -m "fix(security): validate X-Request-ID as UUID, mint fresh id otherwise (FUFIRE-009)"`

### Task 2.17: Fail-closed production auth (FUFIRE-006)

**Files:**
- Create: `tests/test_production_profile.py`
- Modify: `bazi_engine/auth.py` (add helper), `bazi_engine/app.py` (startup check)
- Modify: deploy config per D1 (Railway dashboard variable and/or `deploy-cloudrun.yml` env_vars)

**Step 1: Write failing tests:**
```python
"""FUFIRE-006: FUFIRE_ENV=production must never boot with auth disabled."""
import pytest

from bazi_engine.config_guard import assert_production_auth_config


def test_production_without_keys_refuses_to_start(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FUFIRE_ENV", "production")
    monkeypatch.delenv("FUFIRE_API_KEYS", raising=False)
    monkeypatch.delenv("KEY_STORE_BACKEND", raising=False)
    with pytest.raises(RuntimeError, match="auth disabled"):
        assert_production_auth_config()


def test_production_with_keys_boots(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FUFIRE_ENV", "production")
    monkeypatch.setenv("FUFIRE_API_KEYS", "ff_pro_testkey123")
    assert_production_auth_config()  # no raise


def test_dev_env_unaffected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("FUFIRE_ENV", raising=False)
    monkeypatch.delenv("FUFIRE_API_KEYS", raising=False)
    assert_production_auth_config()  # no raise — local dev keeps working
```

**Step 2:** Run — expected: FAIL (`config_guard` doesn't exist).

**Step 3:** Create `bazi_engine/config_guard.py`:
```python
"""Startup configuration validation — fail-closed production profile.

FUFIRE-006: dev-mode auth bypass (empty FUFIRE_API_KEYS + no KeyStore) is a
feature for local development, but in production a missing/renamed secret
must abort startup instead of silently exposing every protected route.
"""
from __future__ import annotations

import os

_PRODUCTION_ENVS = {"production", "prod", "staging"}


def assert_production_auth_config() -> None:
    env = os.getenv("FUFIRE_ENV", "").strip().lower()
    if env not in _PRODUCTION_ENVS:
        return
    from bazi_engine.auth import _load_keys, _store_is_configured

    if not _load_keys() and not _store_is_configured():
        raise RuntimeError(
            f"FUFIRE_ENV={env} but auth disabled: FUFIRE_API_KEYS is empty and no "
            "KeyStore is configured. Refusing to start (fail-closed, FUFIRE-006)."
        )
```
Call it in `app.py` during app creation (module level, right before/inside the factory — before routers mount).

**Step 4:** Run: `pytest tests/test_production_profile.py -v && pytest -q` — expected green.

**Step 5:** Wire the env: set `FUFIRE_ENV=production` in the Railway service variables (dashboard — document in README/runbook) and, if Cloud Run stays (D1), add to `deploy-cloudrun.yml` env_vars. Note: `FUFIRE_REQUIRE_API_KEYS=true` stays supported and is independent; this adds a second, deployment-profile-derived belt.

**Step 6:** Commit: `git commit -m "feat(security): fail-closed startup guard — production refuses to boot with auth disabled (FUFIRE-006)"`

### Task 2.18: Quota truth (FUFIRE-005, per Decision D2 default)

**Files:**
- Create: `tests/test_quota_claims.py`
- Modify: `bazi_engine/app.py` (OpenAPI description, ~lines 55-60 tier table + header descriptions ~432)
- Regenerate: `spec/openapi/openapi.json`

**Step 1: Failing test** — the published contract must not advertise unenforced daily quotas:
```python
"""FUFIRE-005: don't advertise Requests/day until a daily counter enforces it."""
import json
from pathlib import Path

SPEC = json.loads((Path(__file__).resolve().parents[1] / "spec/openapi/openapi.json").read_text())


def test_no_unenforced_daily_quota_claims() -> None:
    desc = SPEC["info"]["description"].lower()
    assert "requests/day" not in desc and "requests per day" not in desc, (
        "Spec advertises daily quotas but only per-minute limits are enforced "
        "(limiter.py builds minute windows only). Either implement daily "
        "metering or keep the contract truthful."
    )
```

**Step 2:** Run — expected FAIL.

**Step 3:** Edit the `app.py` OpenAPI description: replace the Requests/day tier table with the per-minute limits that are actually enforced (keep tier names; keep `requests_per_day` fields in `auth.py` for the future metering slice — they're internal). Adjust the X-RateLimit-Remaining description if it references daily windows. Regenerate:
```bash
python scripts/export_openapi.py
```

**Step 4:** Run: `pytest tests/test_quota_claims.py -v && pytest -q && python scripts/export_openapi.py --check` — green. Review the spec diff: description-only changes (paths/schemas untouched — frozen-endpoint rule respected).

**Step 5:** Commit: `git commit -m "fix(contract): advertise only enforced per-minute limits; daily metering deferred to its own slice (FUFIRE-005, D2)"`

### Task 2.19: Key-plane ADR (FUFIRE-007/012, Decision D3)

**Files:**
- Create: `docs/adr/ADR-002-key-plane-ownership.md`

**Step 1:** Write the ADR covering: the two key planes as-built (`ff_live_*` Supabase-backed dashboard keys — durable, hashed at rest, never forwarded upstream; `ff_free_*` engine-minted email keys — memory-only, die on every deploy, jti idempotency resets), issuance/storage/hashing/rotation/revocation/scopes/quota correlation, and the decision:
- **Option A (recommended):** retire engine email-issuance; free-tier keys become Supabase-backed in the BFF like `ff_live_`; engine `/v1/admin/keys` marked deprecated in the spec (deprecation is contract-legal; removal only after W6 lifecycle gate).
- **Option B:** implement the documented-as-planned Postgres KeyStore backend in the engine (`key_store.py` explicitly names this direction).
Include the interim risk statement: every Railway deploy currently invalidates all emailed free keys silently.

**Step 2:** Get D3 decided; the implementation is a follow-up slice (not in this plan's critical path — Phases 3-5 don't depend on it).

**Step 3:** Commit: `git commit -m "docs(adr): ADR-002 key-plane ownership — two planes documented, issuance direction decided (FUFIRE-007/012)"`

**Phase 2 exit:** PR → main. After merge: live smoke MUST include one 429 check against a decorated route and one garbage-X-Request-ID check (Task 5.31 covers both).

---

# Phase 3 — Engine modularization (app.py 639 LOC → thin factory)

Rationale: `app.py` currently owns 8 exception handlers, CORS + wildcard validation, dual-mount wiring for 14 routers, and ~250 LOC of OpenAPI post-processing. Every new endpoint touches this hotspot. Target layout (audit `12_target_architecture.md`, adapted to existing conventions — no new top-level packages, minimal moves):

```
bazi_engine/
  app.py               # thin factory: create_app(), middleware, mount_all(), custom_openapi hookup   (<150 LOC)
  openapi_ext.py       # ALL OpenAPI post-processing (headers, error responses, servers, description)
  error_handlers.py    # register_exception_handlers(app) — the 8 handlers
  routers/
    registry.py        # declarative mount table (single source of the dual-mount idiom)
```

### Task 3.20: Characterization tests FIRST (route table + spec bytes)

**Files:**
- Create: `tests/test_app_composition.py`
- Create: `tests/golden/route_table.json` (generated)

**Step 1:** Write the snapshot test:
```python
"""Characterization: the composed app's route table must not change during
the Phase-3 extraction. Regenerate the golden ONLY for an intentional
endpoint change: pytest tests/test_app_composition.py --regen (see conftest).
"""
import json
from pathlib import Path

from fastapi.routing import APIRoute

from bazi_engine.app import app

GOLDEN = Path(__file__).parent / "golden" / "route_table.json"


def _table() -> list[list]:
    rows = []
    for r in app.routes:
        if isinstance(r, APIRoute):
            deps = {d.call.__name__ for d in r.dependant.dependencies if d.call}
            rows.append([r.path, sorted(r.methods), "require_api_key" in deps, r.include_in_schema])
    return sorted(rows)


def test_route_table_unchanged() -> None:
    assert json.loads(GOLDEN.read_text()) == _table()
```

**Step 2:** Generate the golden once (small helper script or a `--regen` conftest flag; simplest: `python -c` snippet writing `_table()` to the file), run the test — expected PASS.

**Step 3:** Note the second invariant already exists: `python scripts/export_openapi.py --check` (byte-identical spec). Both must pass after every extraction step below.

**Step 4:** Commit: `git commit -m "test: characterization snapshot of route table before app.py decomposition"`

### Task 3.21: Extract OpenAPI post-processing → `bazi_engine/openapi_ext.py`

**Files:**
- Create: `bazi_engine/openapi_ext.py`
- Modify: `bazi_engine/app.py`

**Step 1:** Move the custom-openapi function plus its helpers (`_add_standard_response_headers`, `_common_error_responses`, servers list, description building — app.py ~386-634) verbatim into `openapi_ext.py` exposing `install_custom_openapi(app: FastAPI) -> None`. Pure move — zero logic edits.

**Step 2:** In `app.py`: `from bazi_engine.openapi_ext import install_custom_openapi` + call it. Delete the moved code.

**Step 3:** Run: `python scripts/export_openapi.py --check` — **must pass byte-identical**; `pytest -q` green; route-table snapshot green.

**Step 4:** Commit: `git commit -m "refactor: extract OpenAPI post-processing from app.py into openapi_ext.py (spec byte-identical)"`

### Task 3.22: Extract exception handlers → `bazi_engine/error_handlers.py`

**Files:**
- Create: `bazi_engine/error_handlers.py`
- Modify: `bazi_engine/app.py`

**Step 1:** Move the 8 handlers + `_get_request_id` helper verbatim; expose `register_exception_handlers(app: FastAPI) -> None`.

**Step 2:** Wire in `app.py`; delete moved code.

**Step 3:** Run: `pytest -q` (error-envelope tests, incl. `tests/test_dst_pii_http.py`, prove behavior) + `export_openapi.py --check` + snapshot — all green.

**Step 4:** Commit: `git commit -m "refactor: extract exception handlers from app.py into error_handlers.py"`

### Task 3.23: Declarative router registry → `bazi_engine/routers/registry.py`

**Files:**
- Create: `bazi_engine/routers/registry.py`
- Modify: `bazi_engine/app.py`

**Step 1:** Encode the mount table exactly as it stands in app.py:332-383 (respect every special case: info public, chart legacy-only, admin v1-only + own auth, match v1-only per DECISION-001, superglue legacy prefix `/api` but v1 prefix `/v1`, webhooks `/internal` + hidden):
```python
"""Single source of the dual-mount idiom (CLAUDE.md 'Mount idiom').

Adding an endpoint = one router module + ONE line here. The route-table
snapshot test and rate-limit coverage test enforce the rest.
"""
from __future__ import annotations

from dataclasses import dataclass

from fastapi import Depends, FastAPI
from fastapi.routing import APIRouter

from bazi_engine.routers import (
    admin, bazi, chart, chronometry, dayun, experience, fusion, geocode,
    impact, info, match, personalize, superglue, transit, validate, webhooks,
    western,
)
from bazi_engine.services.auth import require_api_key  # verify actual import used by app.py today


@dataclass(frozen=True)
class Mount:
    router: APIRouter
    legacy_prefix: str | None = ""      # None = no legacy mount
    v1_prefix: str | None = "/v1"       # None = no v1 mount
    protected: bool = True
    include_in_schema: bool = True


MOUNTS: tuple[Mount, ...] = (
    Mount(info.router, protected=False),
    Mount(validate.router),
    Mount(bazi.router),
    Mount(dayun.router),
    Mount(western.router),
    Mount(fusion.router),
    Mount(chart.router, v1_prefix=None),                      # legacy-only, internal
    Mount(transit.router),
    Mount(experience.router),
    Mount(superglue.router, legacy_prefix="/api"),
    Mount(impact.router),
    Mount(chronometry.router),
    Mount(geocode.router),
    Mount(personalize.router),
    Mount(admin.router, legacy_prefix=None, protected=False),  # own X-Admin-Token gate
    Mount(match.router, legacy_prefix=None),                   # DECISION-001: v1-only
    Mount(webhooks.router, legacy_prefix="/internal", v1_prefix=None,
          protected=False, include_in_schema=False),
)


def mount_all(app: FastAPI) -> None:
    protected = [Depends(require_api_key)]
    for m in MOUNTS:
        deps = protected if m.protected else None
        if m.legacy_prefix is not None:
            app.include_router(m.router, prefix=m.legacy_prefix,
                               dependencies=deps, include_in_schema=m.include_in_schema)
        if m.v1_prefix is not None:
            app.include_router(m.router, prefix=m.v1_prefix,
                               dependencies=deps, include_in_schema=m.include_in_schema)
```
**Important:** check which module `app.py` imports `require_api_key` from today (`bazi_engine/auth.py` vs `bazi_engine/services/auth.py` — CLAUDE.md gotcha #9) and use exactly that one.

**Step 2:** Replace the 50-line mount block in `app.py` with `mount_all(app)`.

**Step 3:** Run the two invariants — route-table snapshot AND `export_openapi.py --check`. Both must be **exactly** green. Any diff = a mount-table transcription error; fix registry, not the golden.

**Step 4:** Full suite: `pytest -q` green. Also confirm `tests/test_import_hierarchy.py` still passes (registry sits at Level 5 with app.py — no violation).

**Step 5:** Commit: `git commit -m "refactor: declarative router mount registry — dual-mount idiom has one source of truth"`

### Task 3.24: Thin factory + "adding an endpoint" guide

**Files:**
- Modify: `bazi_engine/app.py` (final tidy — target <150 LOC: factory, middleware, CORS, limiter state, registry + installer calls)
- Create: `docs/adding-an-endpoint.md`
- Modify: `CLAUDE.md` (architecture section: new modules)

**Step 1:** Final `app.py` pass; no logic changes, just ordering/docstring.

**Step 2:** Write `docs/adding-an-endpoint.md` — the checklist that makes future endpoints cheap and safe:
1. New router module in `bazi_engine/routers/<domain>.py` — business logic in a domain module, router only translates HTTP.
2. Every handler: `@limiter.limit(tier_limit)` + `request: Request` (enforced by `tests/test_rate_limit_coverage.py`).
3. One `Mount(...)` line in `routers/registry.py` (dual-mount unless a DECISION says otherwise).
4. Boundary tests via TestClient on `resp.json()`/`resp.text` (WS-A convention in CLAUDE.md).
5. `python scripts/export_openapi.py` + commit the spec.
6. Regenerate route-table golden intentionally.
7. LIVE repo: sync the spec mirror (Phase 4 tooling).

**Step 3:** Run everything: `pytest -q && ruff check bazi_engine/ tests/ scripts/ && mypy bazi_engine --ignore-missing-imports && python scripts/export_openapi.py --check`

**Step 4:** Commit: `git commit -m "refactor: app.py is a thin factory; document the add-an-endpoint checklist"`

**Phase 3 exit:** PR → main. Live smoke after deploy. `app.py` <150 LOC; new endpoints = router module + 1 registry line.

---

# Phase 4 — LIVE/BFF repo (separate PRs in `Fufire_API-landingpage`)

> All tasks in `/Users/benjaminpoersch/Projects/SaaS/FuFirEProject/Fufire_API-landingpage`. Gates: `npm run predeploy:gate` (or per-stage scripts). Express is **4** — async handlers do not auto-route rejections.

### Task 4.25: Sync the checkout (precondition)

```bash
cd /Users/benjaminpoersch/Projects/SaaS/FuFirEProject/Fufire_API-landingpage
git stash -u   # if the untracked sandbox docs matter, otherwise leave them
git pull origin main   # local is 13 commits behind — origin already has the hehun mirror sync
npm ci && npm test     # green baseline
```

### Task 4.26: BFF spec route parity (FUFIRE-003)

**Files:**
- Create: `src/server/route-manifest.ts` — exported list of every mounted `(method, path)` incl. keys/orgs routers
- Create: `tests/unit/bff-spec-route-parity.test.ts`
- Modify: `src/api/bff-openapi.json` + `public/bff-openapi.json` (add the 10 missing ops: `GET /keys/list`, `POST /keys/create|rotate|revoke`, `POST /orgs`, `GET /orgs`, `GET /orgs/:id/members`, `POST /orgs/:id/invite`, `POST /orgs/accept`, `GET /orgs/accept`)

**Step 1 (red):** Test asserts: every manifest entry exists in `bff-openapi.json` paths (mount-relative, no `/api/v1` prefix — document the dual-mount convention in the spec description) and vice versa. Run → FAIL listing the 10.

**Step 2 (green):** Add the 10 operations to **both** spec copies (authority check requires deep-equality). Decide per route: public (documented) vs internal (`x-internal: true` + excluded from parity, explicitly).

**Step 3:** `npm run test:authority && npm test` green. Commit: `feat(contract): BFF OpenAPI covers keys+orgs dashboard APIs; parity test prevents recurrence (FUFIRE-003)`.

### Task 4.27: Validator compile-failure handling (FUFIRE-015)

**Files:**
- Modify: `src/lib/request-validator.ts` — cache compile failures (`compiled.set(key, null)` sentinel or a `failures: Map<string, Error>`); a failed schema must not recompile-and-throw per request
- Modify: `src/server/app.ts` — wrap the `validateBody` call (~line 1131) in try/catch → `sendProblem(res, 500, "schema_compile_error", ...)`; make boot-warm fail startup when `warmFailures > 0` (fail visible — Dev Principles)
- Create: `tests/unit/request-validator-failure.test.ts` — inject a deliberately broken schema, assert: (a) boot-warm reports it, (b) request gets a clean problem+json 500, not a hang

**TDD order:** red test with broken-schema fixture → implement → green → `npm test` → commit `fix(reliability): schema compile failures fail boot and degrade to problem+json, never hang requests (FUFIRE-015)`.

### Task 4.28: Automated engine→LIVE contract sync + drift gate (FUFIRE-001/002 root cause)

**Files:**
- Create: `scripts/sync-upstream-openapi.mjs` — fetch the engine spec (from `FUFIRE_OPENAPI_URL` live endpoint or a downloaded `openapi-contract` CI artifact), write **both** copies (`src/api/openapi.json`, `public/openapi.json`), print sha256 + version
- Modify: `scripts/verify-openapi-authority.mjs` or add `scripts/check-upstream-drift.mjs` — close the blind spot: compare **schema name sets + sha256** between repo mirror and upstream; missing-schema/hash drift → exit 1 (today additive drift only warns and schema drift is invisible)
- Modify: `package.json` scripts: `sync:upstream`, wire drift check into `predeploy-gate.sh` after the existing authority checks

**Steps:** red test for the drift checker (fixture pair with a missing schema) → implement → run `npm run sync:upstream` once to converge the mirror with engine spec sha `1045cd1e…` → refresh `tests/fixtures/openapi-live.json` deliberately (documented provenance line in `tests/fixtures/README.md`, per FUFIRE-002) → full gate green → commit `feat(contract): scripted engine→LIVE spec sync + hard drift gate; fixture refreshed with provenance`.

### Task 4.29: app.ts extraction (FUFIRE-008) — one route family at a time

Follow the proven factory pattern (`createKeysRouter`/`createOrgsRouter`). Order (each = characterization test via supertest first → extract → green → commit):
1. `src/server/spec-loader.ts` — contract loading (app.ts:104-140) + validator boot-warm (375-420)
2. `src/server/proxy-router.ts` — the ~360-line `/proxy` handler (980-1341)
3. `src/server/legacy-keys-router.ts` — email key flow `/keys/request` + `/keys/confirm` (719-975)
4. `src/server/insights-router.ts` — `/explain`, `/horoscope`, `/transit` (1342-1773)
5. `src/server/meta-router.ts` — `/openapi.json`, `/bff-openapi.json`, `/config-status`, `/version`, `/status` + static/docs routes

Characterization = supertest snapshot of status+headers+body shape for each route before touching it; 13 recorded upstream fixtures in `tests/fixtures/responses/` support the proxy tests. Target: `app.ts` < 400 LOC composition-only. Commits: `refactor(server): extract <family> from app.ts (characterized, behavior-identical)`.

---

# Phase 5 — Production evidence (W6)

### Task 5.31: Engine live smoke script + post-merge ritual

**Files:**
- Create: `scripts/live_smoke.sh` (ENGINE repo)

**Step 1:** Script (uses real deployed URL + real key from env, never committed):
```bash
#!/usr/bin/env bash
# Live smoke against the DEPLOYED engine — verify the artifact, not the tests.
# Usage: FUFIRE_URL=https://... FUFIRE_KEY=ff_... scripts/live_smoke.sh
set -euo pipefail
: "${FUFIRE_URL:?}" "${FUFIRE_KEY:?}"

echo "1) health";        curl -fsS "$FUFIRE_URL/health" | grep -q '"ok"\|healthy'
echo "2) auth enforced"; test "$(curl -s -o /dev/null -w '%{http_code}' "$FUFIRE_URL/v1/calculate/tst" -X POST -H 'Content-Type: application/json' -d '{}')" = "401"
echo "3) real calc";     curl -fsS -X POST "$FUFIRE_URL/v1/calculate/bazi" -H "X-API-Key: $FUFIRE_KEY" -H 'Content-Type: application/json' \
                           -d '{"datetime":"2024-02-10T14:30:00","timezone":"Europe/Berlin","longitude":13.405,"latitude":52.52}' | grep -q '"pillars"\|"year"'
echo "4) request-id contract"; RID=$(curl -fsS -D- -o /dev/null "$FUFIRE_URL/health" -H 'X-Request-ID: not-a-uuid' | awk -F': ' 'tolower($1)=="x-request-id"{print $2}' | tr -d '\r')
python3 -c "import uuid,sys; uuid.UUID('$RID')" && echo "   replaced with UUID ✓"
echo "5) rate limit visible"; curl -fsS -D- -o /dev/null -X POST "$FUFIRE_URL/v1/calculate/wuxing" -H "X-API-Key: $FUFIRE_KEY" -H 'Content-Type: application/json' -d '{"datetime":"2024-02-10T14:30:00","timezone":"Europe/Berlin"}' | grep -i 'x-ratelimit-limit'
echo "SMOKE PASSED"
```

**Step 2:** Document in CLAUDE.md/runbook: after every merge to main (Railway auto-deploy), run the smoke. This is the standing rule from Development Principles — deployed-artifact verification with real secrets.

**Step 3:** Commit: `git commit -m "chore(ops): live smoke script — verify deployed engine after every main merge"`

---

## Execution order & dependencies

```
Phase 0 (hygiene)      → PR #1   independent
Phase 1 (CI/tooling)   → PR #2   after Phase 0 (root workflow copies removed first)
Phase 2 (security TDD) → PR #3   independent of 1, but land after 1 so new CI gates run on it
Phase 3 (modularize)   → PR #4   REQUIRES Phase 2 merged (rate-limit coverage test guards the registry)
Phase 4 (LIVE repo)    → PRs in Fufire_API-landingpage; 4.28 needs Task 1.13 artifact job merged
Phase 5 (smoke)        → tiny PR, anytime; run after every merge
```

Deferred (explicitly out of this plan, tracked via ADR-002 / D2): durable daily-quota metering, persistent KeyStore implementation or issuance retirement, engine `fusion.py`/`match.py` internal splits, mutation testing, CodeQL.
