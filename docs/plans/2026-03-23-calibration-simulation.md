# Monte Carlo Calibration Simulation Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Create a reproducible Monte Carlo simulation that generates the baseline calibration table for `calibration.py`, validates the existing hardcoded values, and replaces them with empirically verified data.

**Architecture:** A standalone script `scripts/calibrate_baselines.py` generates random Wu-Xing vector pairs at each density configuration (sparse/medium/dense x sparse/medium/dense), computes cosine similarity for each pair, and derives mean + stddev baselines. The script outputs JSON results and optionally patches `calibration.py` in-place. A test verifies the simulation is deterministic (seeded) and that results are statistically stable.

**Tech Stack:** Python stdlib only (random, math, json, statistics). No numpy/scipy needed — vectors are 5D.

---

### Task 1: Write the failing test for the simulation function

**Files:**
- Create: `tests/test_calibration_simulation.py`

**Step 1: Write the failing test**

```python
"""Tests for Monte Carlo calibration simulation."""
from __future__ import annotations


def test_simulate_baseline_returns_mean_and_std():
    from scripts.calibrate_baselines import simulate_baseline
    result = simulate_baseline(n_contributions=10, n_trials=100, seed=42)
    assert "mean" in result
    assert "std" in result
    assert 0.0 < result["mean"] < 1.0
    assert 0.0 < result["std"] < 0.5


def test_simulate_baseline_is_deterministic():
    from scripts.calibrate_baselines import simulate_baseline
    r1 = simulate_baseline(n_contributions=10, n_trials=500, seed=123)
    r2 = simulate_baseline(n_contributions=10, n_trials=500, seed=123)
    assert r1["mean"] == r2["mean"]
    assert r1["std"] == r2["std"]


def test_sparse_baseline_lower_than_dense():
    """Sparse vectors (fewer non-zero components) should have lower expected cosine."""
    from scripts.calibrate_baselines import simulate_baseline
    sparse = simulate_baseline(n_contributions=2, n_trials=1000, seed=99)
    dense = simulate_baseline(n_contributions=12, n_trials=1000, seed=99)
    assert sparse["mean"] < dense["mean"]
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_calibration_simulation.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.calibrate_baselines'`

**Step 3: Commit**

```bash
git add tests/test_calibration_simulation.py
git commit -m "test: add failing tests for Monte Carlo calibration simulation"
```

---

### Task 2: Implement the core simulation function

**Files:**
- Create: `scripts/calibrate_baselines.py`

**Step 1: Write the simulation script**

```python
#!/usr/bin/env python3
"""Monte Carlo simulation for Wu-Xing cosine similarity baselines.

Generates random vector pairs in the positive orthant of R^5,
computes their cosine similarity, and derives mean + stddev
per density configuration.

Usage:
    python scripts/calibrate_baselines.py                    # run full simulation
    python scripts/calibrate_baselines.py --trials 10000     # more trials
    python scripts/calibrate_baselines.py --patch            # update calibration.py
    python scripts/calibrate_baselines.py --json results.json # export results
"""
from __future__ import annotations

import argparse
import json
import math
import random
import statistics
import sys
import textwrap
from pathlib import Path


def _random_wuxing_vector(rng: random.Random, n_contributions: int) -> list[float]:
    """Generate a random non-negative R^5 vector by distributing n contributions.

    Simulates the actual Wu-Xing accumulation process:
    each contribution adds weight 1.0 to a randomly chosen element bin.
    This mirrors how planets/stems/branches each add to one of 5 elements.
    """
    v = [0.0, 0.0, 0.0, 0.0, 0.0]
    for _ in range(n_contributions):
        idx = rng.randint(0, 4)
        v[idx] += 1.0
    return v


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Cosine similarity between two vectors. Returns 0 if either is zero."""
    dot = sum(x * y for x, y in zip(a, b))
    mag_a = math.sqrt(sum(x * x for x in a))
    mag_b = math.sqrt(sum(x * x for x in b))
    if mag_a == 0 or mag_b == 0:
        return 0.0
    return dot / (mag_a * mag_b)


def simulate_baseline(
    n_contributions: int,
    n_trials: int = 5000,
    seed: int = 42,
) -> dict[str, float]:
    """Run Monte Carlo simulation for a single density configuration.

    Args:
        n_contributions: Number of element contributions per vector.
                         Both vectors in each trial use this count.
        n_trials:        Number of random vector pairs to generate.
        seed:            RNG seed for reproducibility.

    Returns:
        {"mean": float, "std": float, "n_trials": int, "n_contributions": int}
    """
    rng = random.Random(seed)
    similarities = []
    for _ in range(n_trials):
        a = _random_wuxing_vector(rng, n_contributions)
        b = _random_wuxing_vector(rng, n_contributions)
        similarities.append(_cosine_similarity(a, b))

    return {
        "mean": round(statistics.mean(similarities), 4),
        "std": round(statistics.stdev(similarities), 4),
        "n_trials": n_trials,
        "n_contributions": n_contributions,
    }


def simulate_baseline_pair(
    n_west: int,
    n_bazi: int,
    n_trials: int = 5000,
    seed: int = 42,
) -> dict[str, float]:
    """Simulate baseline for asymmetric vector pair (different contribution counts).

    In practice, Western vectors have ~7-13 contributions (planets),
    BaZi vectors have ~8-20 contributions (stems + hidden stems).
    """
    rng = random.Random(seed)
    similarities = []
    for _ in range(n_trials):
        a = _random_wuxing_vector(rng, n_west)
        b = _random_wuxing_vector(rng, n_bazi)
        similarities.append(_cosine_similarity(a, b))

    return {
        "mean": round(statistics.mean(similarities), 4),
        "std": round(statistics.stdev(similarities), 4),
        "n_trials": n_trials,
        "n_west": n_west,
        "n_bazi": n_bazi,
    }


# Density configurations matching calibration.py bucket definitions:
# n_west_bucket: 1-3 = sparse, 4-8 = medium, 9+ = dense
# n_bazi_bucket: 1-8 = sparse, 9-16 = medium, 17+ = dense
# We use representative midpoints for each bucket.
DENSITY_CONFIGS: list[dict[str, int | str]] = [
    {"west_bucket": "sparse",  "bazi_bucket": "sparse",  "n_west": 2,  "n_bazi": 5},
    {"west_bucket": "sparse",  "bazi_bucket": "medium",  "n_west": 2,  "n_bazi": 12},
    {"west_bucket": "sparse",  "bazi_bucket": "dense",   "n_west": 2,  "n_bazi": 20},
    {"west_bucket": "medium",  "bazi_bucket": "sparse",  "n_west": 6,  "n_bazi": 5},
    {"west_bucket": "medium",  "bazi_bucket": "medium",  "n_west": 6,  "n_bazi": 12},
    {"west_bucket": "medium",  "bazi_bucket": "dense",   "n_west": 6,  "n_bazi": 20},
    {"west_bucket": "dense",   "bazi_bucket": "sparse",  "n_west": 11, "n_bazi": 5},
    {"west_bucket": "dense",   "bazi_bucket": "medium",  "n_west": 11, "n_bazi": 12},
    {"west_bucket": "dense",   "bazi_bucket": "dense",   "n_west": 11, "n_bazi": 20},
]


def run_full_simulation(n_trials: int = 5000, seed: int = 42) -> list[dict]:
    """Run simulation for all 9 density configurations."""
    results = []
    for config in DENSITY_CONFIGS:
        result = simulate_baseline_pair(
            n_west=config["n_west"],
            n_bazi=config["n_bazi"],
            n_trials=n_trials,
            seed=seed,
        )
        result["west_bucket"] = config["west_bucket"]
        result["bazi_bucket"] = config["bazi_bucket"]
        results.append(result)
    return results


def format_baseline_table(results: list[dict]) -> str:
    """Format results as Python source for _BASELINE_TABLE."""
    lines = [
        "_BASELINE_TABLE: dict[tuple[str, str], tuple[float, float]] = {",
    ]
    for r in results:
        wb = r["west_bucket"]
        bb = r["bazi_bucket"]
        lines.append(f'    ("{wb}",{" " * (8 - len(wb))}"{bb}"):{" " * (8 - len(bb))} ({r["mean"]}, {r["std"]}),')
    lines.append("}")
    return "\n".join(lines)


def compare_with_existing(results: list[dict]) -> str:
    """Compare simulation results with existing hardcoded baselines."""
    # Import existing table
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from bazi_engine.wuxing.calibration import _BASELINE_TABLE

    lines = []
    lines.append(f"{'Config':<25} {'Existing':>18} {'Simulated':>18} {'Delta mean':>12}")
    lines.append("-" * 75)

    for r in results:
        key = (r["west_bucket"], r["bazi_bucket"])
        existing = _BASELINE_TABLE.get(key, (0, 0))
        delta = r["mean"] - existing[0]
        flag = " ***" if abs(delta) > 0.02 else ""
        lines.append(
            f"({key[0]:>8}, {key[1]:<8})  "
            f"({existing[0]:.4f}, {existing[1]:.4f})  "
            f"({r['mean']:.4f}, {r['std']:.4f})  "
            f"{delta:+.4f}{flag}"
        )

    return "\n".join(lines)


def patch_calibration_file(results: list[dict]) -> None:
    """Replace _BASELINE_TABLE in calibration.py with simulation results."""
    cal_path = Path(__file__).resolve().parent.parent / "bazi_engine" / "wuxing" / "calibration.py"
    content = cal_path.read_text()

    # Find and replace the table
    start_marker = "_BASELINE_TABLE: dict[tuple[str, str], tuple[float, float]] = {"
    end_marker = "}"

    start_idx = content.index(start_marker)
    # Find the closing brace of the dict (first } after start on its own line)
    search_from = start_idx + len(start_marker)
    end_idx = content.index("\n}", search_from) + 2  # include \n}

    new_table = format_baseline_table(results)
    new_content = content[:start_idx] + new_table + content[end_idx:]
    cal_path.write_text(new_content)
    print(f"Patched: {cal_path}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Monte Carlo Wu-Xing baseline calibration")
    parser.add_argument("--trials", type=int, default=5000, help="Trials per config (default: 5000)")
    parser.add_argument("--seed", type=int, default=42, help="RNG seed (default: 42)")
    parser.add_argument("--json", type=str, help="Export results to JSON file")
    parser.add_argument("--patch", action="store_true", help="Update calibration.py with new values")
    parser.add_argument("--quiet", action="store_true", help="Suppress comparison output")
    args = parser.parse_args()

    print(f"Running Monte Carlo simulation: {args.trials} trials/config, seed={args.seed}")
    print(f"Configurations: {len(DENSITY_CONFIGS)}")
    print()

    results = run_full_simulation(n_trials=args.trials, seed=args.seed)

    if not args.quiet:
        print(compare_with_existing(results))
        print()
        print("New baseline table:")
        print(format_baseline_table(results))

    if args.json:
        Path(args.json).write_text(json.dumps(results, indent=2))
        print(f"\nExported: {args.json}")

    if args.patch:
        patch_calibration_file(results)

    return 0


if __name__ == "__main__":
    sys.exit(main())
```

**Step 2: Run tests to verify they pass**

Run: `pytest tests/test_calibration_simulation.py -v`
Expected: 3 PASS

**Step 3: Commit**

```bash
git add scripts/calibrate_baselines.py
git commit -m "feat: add Monte Carlo calibration simulation script"
```

---

### Task 3: Run the full simulation and validate existing values

**Step 1: Run simulation and compare**

Run: `python scripts/calibrate_baselines.py --trials 5000 --seed 42`

Expected output: comparison table showing existing vs. simulated baselines.
If any delta > 0.02, the existing values need correction.

**Step 2: Export results to JSON for audit trail**

Run: `python scripts/calibrate_baselines.py --trials 5000 --seed 42 --json docs/calibration-results.json`

**Step 3: Commit results**

```bash
git add docs/calibration-results.json
git commit -m "docs: add Monte Carlo calibration simulation results (5000 trials)"
```

---

### Task 4: Patch calibration.py if values differ

Only execute if Task 3 shows significant deltas (> 0.02).

**Step 1: Patch calibration.py**

Run: `python scripts/calibrate_baselines.py --trials 5000 --seed 42 --patch`

**Step 2: Update the docstring**

In `bazi_engine/wuxing/calibration.py`, update line 17:

```
KALIBRIERUNGSPARAMETER (empirisch aus 5000 Simulationen je Dichtekonfiguration):
```

to:

```
KALIBRIERUNGSPARAMETER (empirisch, 5000 Monte-Carlo-Trials je Zelle, Seed=42):
Reproduzierbar via: python scripts/calibrate_baselines.py --trials 5000 --seed 42
```

**Step 3: Run full test suite**

Run: `pytest -q --ignore=tests/test_snapshot_stability.py`
Expected: all pass (snapshot tests skipped because calibration change affects fusion outputs)

**Step 4: Regenerate snapshots if needed**

Run: `UPDATE_SNAPSHOTS=1 pytest tests/test_snapshot_stability.py -q`

**Step 5: Commit**

```bash
git add bazi_engine/wuxing/calibration.py tests/snapshots/
git commit -m "fix(calibration): replace hardcoded baselines with verified Monte Carlo values"
```

---

### Task 5: Add CI verification test

**Files:**
- Modify: `tests/test_calibration_simulation.py`

**Step 1: Add regression test that verifies calibration.py matches simulation**

Append to `tests/test_calibration_simulation.py`:

```python
def test_baseline_table_matches_simulation():
    """Verify calibration.py values match reproducible simulation."""
    from scripts.calibrate_baselines import run_full_simulation
    from bazi_engine.wuxing.calibration import _BASELINE_TABLE

    results = run_full_simulation(n_trials=5000, seed=42)
    for r in results:
        key = (r["west_bucket"], r["bazi_bucket"])
        existing_mean, existing_std = _BASELINE_TABLE[key]
        assert abs(r["mean"] - existing_mean) < 0.001, (
            f"{key}: mean {existing_mean} != simulated {r['mean']}"
        )
        assert abs(r["std"] - existing_std) < 0.001, (
            f"{key}: std {existing_std} != simulated {r['std']}"
        )


def test_simulation_stable_across_trial_counts():
    """Baselines should be stable whether we run 5000 or 10000 trials."""
    from scripts.calibrate_baselines import simulate_baseline_pair
    r5k = simulate_baseline_pair(n_west=11, n_bazi=12, n_trials=5000, seed=42)
    r10k = simulate_baseline_pair(n_west=11, n_bazi=12, n_trials=10000, seed=42)
    assert abs(r5k["mean"] - r10k["mean"]) < 0.01, "Baseline unstable at 5000 trials"
```

**Step 2: Run all calibration tests**

Run: `pytest tests/test_calibration_simulation.py -v`
Expected: 5 PASS

**Step 3: Commit**

```bash
git add tests/test_calibration_simulation.py
git commit -m "test: add CI verification that calibration matches simulation"
```

---

### Task 6: Update whitepaper with verified claim

**Files:**
- Modify: `docs/marketing/whitepaper-fusion-mathematics.md`

**Step 1: Update the Monte Carlo section**

Replace any mention of "5000 Simulationen" with the verified claim:

```
Baselines derived from 5000 Monte Carlo trials per density cell (seed=42),
reproducible via `python scripts/calibrate_baselines.py --trials 5000 --seed 42`.
Results archived in `docs/calibration-results.json`.
```

**Step 2: Commit**

```bash
git add docs/marketing/whitepaper-fusion-mathematics.md
git commit -m "docs: update whitepaper with verified Monte Carlo provenance"
```

---

## Summary

| Task | Purpose | Est. Time |
|------|---------|-----------|
| 1 | Failing tests (TDD red) | 2 min |
| 2 | Simulation script (TDD green) | 10 min |
| 3 | Run simulation, export results | 3 min |
| 4 | Patch calibration.py if needed | 5 min |
| 5 | CI regression test | 3 min |
| 6 | Update whitepaper provenance | 2 min |

Total: ~25 min. After this, the "5000 Monte Carlo simulations" claim is verifiably true.
