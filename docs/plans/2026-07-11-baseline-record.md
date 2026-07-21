# Green Baseline Record — FuFirE API Cleanup Refactoring (Task 0.1)

Recorded: 2026-07-12
Branch: `worktree-fufire-cleanup-refactor`
Git HEAD: `d0fc721010340b7280afa12540f10af01c849226` (d0fc721, "Merge pull request #147 from DYAI2025/docs/testing-conventions-reflect")

All four gates passed with zero changes to the codebase. This is the reference
baseline for the cleanup refactoring plan
(`docs/plans/2026-07-11-fufire-api-cleanup-refactoring.md`).

## Environment

| Item | Value |
|------|-------|
| Interpreter | Python 3.12.11 (`/usr/local/bin/python3.12`, venv at `.venv/`) |
| Ephemeris mode | **MOSEPH** (no SE1 files at `/usr/local/share/swisseph`; `tests/conftest.py` auto-fallback, `swieph`-marked tests skipped) |
| pytest | 9.1.1 |
| ruff | 0.15.21 (installed ad hoc — not yet pinned in dev extras) |
| mypy | 2.2.0 (installed ad hoc — not yet pinned in dev extras) |

## Gate Results

### 1. pytest -q — PASS (exit 0)

```
2743 passed, 61 skipped, 1 xfailed, 1 warning in 29.39s
```

- Skips: 61 (ephemeris-dependent `swieph` tests, SE1 files absent)
- The single warning is an intentional `DeprecationWarning` exercised by
  `tests/test_month_boundary_scheme_vestigial.py` (deprecated
  `BaziInput.month_boundary_scheme`).
- Note: the plan's estimate of "~1500 passed" is stale; the suite has grown
  to 2743 passing tests.

### 2. ruff check bazi_engine/ — PASS (exit 0)

```
All checks passed!
```

### 3. mypy bazi_engine --ignore-missing-imports — PASS (exit 0)

```
Success: no issues found in 105 source files
```

### 4. python scripts/export_openapi.py --check — PASS (exit 0)

```
OK: OpenAPI spec is up-to-date.
```

## Baseline Contract

Any subsequent task in the refactoring plan must keep all four gates at
these results (pass counts may only grow; skip count may change only if
ephemeris availability changes). Regressions against this record block merge.
