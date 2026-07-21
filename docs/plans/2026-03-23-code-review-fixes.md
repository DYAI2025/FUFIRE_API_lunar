# Code Review Fixes Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix all 6 issues from code review (H1, H2, M1, M4, M5, I2) in 2 commits.

**Architecture:** Batch fixes by file group. Task 1 = mock server + test imports. Task 2 = calibration script + snapshot test + config dedup. No new tests needed — existing tests cover all changes.

**Tech Stack:** Python stdlib only.

---

### Task 1: Fix mock server (H1, H2) + scripts __init__ (M5)

**Files:**
- Modify: `tests/mock_server.py`
- Create: `scripts/__init__.py`

**Step 1: Fix H1 + H2 in mock_server.py**

In `tests/mock_server.py`, make these 3 changes:

1. **H1** — Replace `time.sleep()` with a comment noting sync is intentional (async sleep would require all endpoints to be async, overengineering for a mock):

Replace the `_simulate_latency` function:
```python
def _simulate_latency() -> None:
    """Add simulated network latency.

    Uses blocking sleep intentionally — this mock server is designed for
    single-threaded dev/test use, not production concurrency.
    """
    if _LATENCY_MS > 0:
        time.sleep(_LATENCY_MS / 1000)
```

2. **H2** — Add thread-safety comment to the global mutation endpoints:

Add comment before `switch_scenario`:
```python
# Note: Global state mutation is intentional for this dev-only mock server.
# Not thread-safe — designed for single-client dev/test use.
```

3. **M5** — Create empty `scripts/__init__.py` so tests can import from `scripts/`:

```python
# scripts/__init__.py — makes scripts/ importable for tests
```

**Step 2: Verify**

Run: `pytest tests/test_mock_contract.py tests/test_calibration_simulation.py -q`
Expected: 33 pass

**Step 3: Commit**

```bash
git add tests/mock_server.py scripts/__init__.py
git commit -m "fix: address code review H1/H2/M5 — mock server docs, scripts __init__"
```

---

### Task 2: Fix calibration patching (M4) + snapshot import (M1) + dedup threshold (I2)

**Files:**
- Modify: `scripts/calibrate_baselines.py`
- Modify: `bazi_engine/wuxing/calibration.py`
- Modify: `tests/test_snapshot_stability.py`
- Modify: `pyproject.toml`

**Step 1: Fix M4 — Add sentinel comments to calibration.py baseline table**

In `bazi_engine/wuxing/calibration.py`, wrap the table with sentinels:

Replace the comment above the table:
```python
# ── BEGIN BASELINE_TABLE (do not edit manually — use scripts/calibrate_baselines.py) ──
```

After the closing `}`:
```python
# ── END BASELINE_TABLE ──
```

Then in `scripts/calibrate_baselines.py`, update `patch_calibration_file()` to use sentinels:

```python
def patch_calibration_file(results: list[dict]) -> None:
    """Replace _BASELINE_TABLE in calibration.py with simulation results."""
    cal_path = Path(__file__).resolve().parent.parent / "bazi_engine" / "wuxing" / "calibration.py"
    content = cal_path.read_text()

    begin = "# ── BEGIN BASELINE_TABLE"
    end = "# ── END BASELINE_TABLE"
    try:
        start_idx = content.index(begin)
        end_idx = content.index(end) + len(end)
    except ValueError:
        print(f"ERROR: Sentinel markers not found in {cal_path}", file=sys.stderr)
        print("Expected markers: '# ── BEGIN BASELINE_TABLE' and '# ── END BASELINE_TABLE'", file=sys.stderr)
        sys.exit(1)

    new_block = (
        "# ── BEGIN BASELINE_TABLE (do not edit manually — use scripts/calibrate_baselines.py) ──\n"
        + format_baseline_table(results)
        + "\n# ── END BASELINE_TABLE ──"
    )
    new_content = content[:start_idx] + new_block + content[end_idx:]
    cal_path.write_text(new_content)
    print(f"Patched: {cal_path}")
```

**Step 2: Fix M1 — Make snapshot ephemeris detection more robust**

In `tests/test_snapshot_stability.py`, replace the broad `except Exception` with a warning:

```python
def _ephemeris_tag() -> str:
    """Return 'swieph' or 'moseph' based on the active ephemeris backend."""
    mode = os.environ.get("EPHEMERIS_MODE", "").upper()
    if mode == "MOSEPH":
        return "moseph"
    try:
        from bazi_engine.ephemeris import EPHEMERIS_FILES_REQUIRED, _resolve_ephe_path
        path = _resolve_ephe_path(None)
        if all((path / name).exists() for name in EPHEMERIS_FILES_REQUIRED):
            return "swieph"
    except ImportError:
        pass  # ephemeris module not installed — fall back to moseph
    return "moseph"
```

Change `except Exception` to `except ImportError` — the only expected failure mode.

**Step 3: Fix I2 — Remove duplicate coverage threshold from pyproject.toml**

In `pyproject.toml`, remove `fail_under = 75` from `[tool.coverage.report]` since the CI command already passes `--cov-fail-under=75`. Keep only the CLI flag as the single source of truth. Add a comment:

```toml
[tool.coverage.report]
# fail_under is set via CLI (--cov-fail-under=75) in CI, not here
show_missing = true
skip_covered = true
```

**Step 4: Verify**

Run: `pytest tests/test_snapshot_stability.py tests/test_calibration_simulation.py tests/test_mock_contract.py -q`
Expected: all pass

Run: `python scripts/calibrate_baselines.py --trials 100 --seed 42 --quiet`
Expected: runs without error

**Step 5: Commit**

```bash
git add scripts/calibrate_baselines.py bazi_engine/wuxing/calibration.py tests/test_snapshot_stability.py pyproject.toml
git commit -m "fix: address code review M1/M4/I2 — sentinel markers, robust import, dedup threshold"
```

---

## Summary

| Issue | Fix | Task |
|-------|-----|------|
| H1 | Document blocking sleep as intentional | 1 |
| H2 | Document single-threaded assumption | 1 |
| M1 | `except ImportError` instead of `except Exception` | 2 |
| M4 | Sentinel markers for baseline table patching | 2 |
| M5 | Add `scripts/__init__.py` | 1 |
| I2 | Remove duplicate `fail_under` from pyproject.toml | 2 |

2 commits, ~15 minutes total.
