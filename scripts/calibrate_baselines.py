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

    begin = "# ── BEGIN BASELINE_TABLE"
    end = "# ── END BASELINE_TABLE"
    try:
        start_idx = content.index(begin)
        end_marker_idx = content.index(end)
        newline_idx = content.find("\n", end_marker_idx)
        if newline_idx == -1:
            end_idx = len(content)
        else:
            end_idx = newline_idx + 1
    except ValueError:
        print(f"ERROR: Sentinel markers not found in {cal_path}", file=sys.stderr)
        print("Expected: '# ── BEGIN BASELINE_TABLE' and '# ── END BASELINE_TABLE'", file=sys.stderr)
        sys.exit(1)

    new_block = (
        "# ── BEGIN BASELINE_TABLE (do not edit manually — use scripts/calibrate_baselines.py) ──\n"
        + format_baseline_table(results)
        + "\n# ── END BASELINE_TABLE ──"
    )
    new_content = content[:start_idx] + new_block + content[end_idx:]
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
