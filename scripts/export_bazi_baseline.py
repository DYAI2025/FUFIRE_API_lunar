"""FBP-00-004 — Export the v1 BaZi engine baseline.

Produces ``tests/fixtures/bazi_baseline_v1.json``, a deterministic
snapshot of the engine's current output across boundary-relevant
cases. The snapshot is used by ``tests/test_regression_v1_compatibility.py``
to detect silent drift while ``BAZI-PRECISION-V2`` work is in flight.

Design constraints (from the implementation plan):

- Deterministic and offline. No network calls.
- Records the active ephemeris and parameter / ruleset versions so
  future readers know the conditions under which the snapshot was
  produced (Swiss Ephemeris vs Moshier analytic).
- Sorted JSON keys; UTF-8; trailing newline. Diff-friendly.
- Stable case set: only new cases may be **appended**. Removing or
  re-ordering cases requires a new baseline file and a migration
  entry (see ``docs/precision/deviations.md``).

Usage::

    python scripts/export_bazi_baseline.py                  # writes default path
    python scripts/export_bazi_baseline.py --out path.json  # alt destination
    python scripts/export_bazi_baseline.py --check          # exits non-zero on drift

``--check`` is the CI mode: regenerates the baseline in-memory and
diffs against the on-disk file. CI fails if the engine output has
drifted; the human then either fixes the engine or updates the
baseline with a deviation entry.

This script is **not** an "oracle" — see
``spec/golden/bazi_case.schema.json`` for the source_type taxonomy.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = REPO_ROOT / "tests" / "fixtures" / "bazi_baseline_v1.json"


# Cases chosen to exercise the categories called out by the plan's
# Phase-0 stop-gate: boundary, DST, LiChun, Jieqi, TLST-near. IDs are
# stable; do not renumber.
BASELINE_CASES: list[dict[str, Any]] = [
    {
        "id": "berlin_routine_afternoon",
        "category": "routine",
        "birth_local": "2024-02-10T14:30:00",
        "timezone": "Europe/Berlin",
        "longitude_deg": 13.4050,
        "latitude_deg": 52.52,
    },
    {
        "id": "berlin_lichun_2024_before",
        "category": "lichun_boundary",
        "birth_local": "2024-02-04T09:26:00",
        "timezone": "Europe/Berlin",
        "longitude_deg": 13.4050,
        "latitude_deg": 52.52,
    },
    {
        "id": "berlin_lichun_2024_after",
        "category": "lichun_boundary",
        "birth_local": "2024-02-04T09:28:00",
        "timezone": "Europe/Berlin",
        "longitude_deg": 13.4050,
        "latitude_deg": 52.52,
    },
    {
        "id": "beijing_lichun_2024_before",
        "category": "lichun_boundary",
        "birth_local": "2024-02-04T16:26:00",
        "timezone": "Asia/Shanghai",
        "longitude_deg": 116.40,
        "latitude_deg": 39.90,
    },
    {
        "id": "beijing_lichun_2024_after",
        "category": "lichun_boundary",
        "birth_local": "2024-02-04T16:28:00",
        "timezone": "Asia/Shanghai",
        "longitude_deg": 116.40,
        "latitude_deg": 39.90,
    },
    # Zi-hour day boundary (both sides of civil midnight).
    {
        "id": "berlin_zi_before_midnight",
        "category": "zi_day_boundary",
        "birth_local": "2024-06-15T23:30:00",
        "timezone": "Europe/Berlin",
        "longitude_deg": 13.4050,
        "latitude_deg": 52.52,
    },
    {
        "id": "berlin_zi_after_midnight",
        "category": "zi_day_boundary",
        "birth_local": "2024-06-16T00:30:00",
        "timezone": "Europe/Berlin",
        "longitude_deg": 13.4050,
        "latitude_deg": 52.52,
    },
    # DST transitions — spring forward and fall back, Europe/Berlin.
    {
        "id": "berlin_dst_spring_forward_2024_safe",
        "category": "dst",
        "birth_local": "2024-03-31T01:30:00",
        "timezone": "Europe/Berlin",
        "longitude_deg": 13.4050,
        "latitude_deg": 52.52,
    },
    {
        "id": "berlin_dst_fall_back_2024_earlier",
        "category": "dst",
        "birth_local": "2024-10-27T02:30:00",
        "timezone": "Europe/Berlin",
        "longitude_deg": 13.4050,
        "latitude_deg": 52.52,
        "ambiguousTime": "earlier",
    },
    {
        "id": "berlin_dst_fall_back_2024_later",
        "category": "dst",
        "birth_local": "2024-10-27T02:30:00",
        "timezone": "Europe/Berlin",
        "longitude_deg": 13.4050,
        "latitude_deg": 52.52,
        "ambiguousTime": "later",
    },
    # Jieqi crossings (months other than LiChun).
    {
        "id": "berlin_jingzhe_2024",
        "category": "jieqi_boundary",
        "birth_local": "2024-03-05T10:00:00",
        "timezone": "Europe/Berlin",
        "longitude_deg": 13.4050,
        "latitude_deg": 52.52,
    },
    {
        "id": "berlin_qiufen_2024",
        "category": "jieqi_boundary",
        "birth_local": "2024-09-22T22:30:00",
        "timezone": "Europe/Berlin",
        "longitude_deg": 13.4050,
        "latitude_deg": 52.52,
    },
    # TLST-near case (Madrid: civil time 23:30 in summer is very close
    # to LMT noon midpoint; the plan's day-boundary tests will compare
    # CIVIL/LMT/TLST here.)
    {
        "id": "madrid_late_evening_zi_LMT",
        "category": "tlst_neighborhood",
        "birth_local": "2024-02-04T23:30:00",
        "timezone": "Europe/Madrid",
        "longitude_deg": -3.7038,
        "latitude_deg": 40.4168,
        "time_standard": "LMT",
        "day_boundary": "zi",
    },
    # Historical: Singapore independence
    {
        "id": "singapore_independence_1965",
        "category": "historical",
        "birth_local": "1965-08-09T10:00:00",
        "timezone": "Asia/Singapore",
        "longitude_deg": 103.85,
        "latitude_deg": 1.29,
    },
]


def _detect_ephemeris_mode() -> str:
    """Pure inspection. Returns the ephemeris mode the engine *would*
    use given the current environment and SE1 file availability.

    Does NOT modify the environment. Use ``_apply_ephemeris_mode_to_env``
    if you need to force a particular mode for the duration of a call.
    """
    explicit = os.environ.get("EPHEMERIS_MODE")
    if explicit:
        return explicit.upper()
    try:
        from bazi_engine.ephemeris import (
            EPHEMERIS_FILES_REQUIRED,
            _resolve_ephe_path,
        )
        path = _resolve_ephe_path(None)
        if all((path / name).exists() for name in EPHEMERIS_FILES_REQUIRED):
            return "SWIEPH"
    except Exception:
        pass
    return "MOSEPH"


def _apply_ephemeris_mode_to_env(mode: str) -> str | None:
    """Set ``EPHEMERIS_MODE`` and return the prior value (or None).

    The caller is responsible for calling ``_restore_ephemeris_mode``
    once the work is done.
    """
    prior = os.environ.get("EPHEMERIS_MODE")
    os.environ["EPHEMERIS_MODE"] = mode
    return prior


def _restore_ephemeris_mode(prior: str | None) -> None:
    if prior is None:
        os.environ.pop("EPHEMERIS_MODE", None)
    else:
        os.environ["EPHEMERIS_MODE"] = prior


def _load_ruleset_id(ruleset_path: Path | None = None) -> str:
    """Read ``ruleset_id`` from the canonical ruleset JSON.

    Three fallback paths, each with an explicit stderr warning so the
    gap is visible. Sourcing from the ruleset itself keeps the baseline
    aligned with whatever the ruleset declares, independent of the
    (broken) default in ``bazi_engine/provenance.py`` (DEV-2026-002).
    """
    path = ruleset_path or (
        REPO_ROOT / "spec" / "rulesets" / "standard_bazi_2026.json"
    )
    try:
        data = json.loads(path.read_text())
    except FileNotFoundError:
        print(
            f"[warn] ruleset {path} not found; using filename as ruleset_id.",
            file=sys.stderr,
        )
        return path.stem
    except json.JSONDecodeError as exc:
        print(
            f"[warn] ruleset {path} is malformed JSON ({exc}); "
            "using filename as ruleset_id.",
            file=sys.stderr,
        )
        return path.stem
    declared = data.get("ruleset_id")
    if declared:
        return str(declared)
    print(
        f"[warn] {path} has no top-level 'ruleset_id'; falling back to filename.",
        file=sys.stderr,
    )
    return path.stem


def _compute_one(case: dict[str, Any]) -> dict[str, Any]:
    """Run the engine on a single case and return a plain-data record.

    Handles ``ambiguousTime`` and ``nonexistentTime`` the same way the
    API router does (``bazi_engine/routers/bazi.py:162``): resolve the
    local time first, then construct ``BaziInput`` with the chosen
    ``fold``. The chart UTC is recorded in the output so DST-fold
    regressions are visible in the baseline.
    """
    from bazi_engine.bazi import compute_bazi
    from bazi_engine.time_utils import resolve_local_iso
    from bazi_engine.types import BaziInput

    ambiguous = case.get("ambiguousTime", "earlier")
    nonexistent = case.get("nonexistentTime", "error")
    dt_local, _resolution = resolve_local_iso(
        case["birth_local"],
        case["timezone"],
        ambiguous=ambiguous,
        nonexistent=nonexistent,
    )
    resolved_naive = dt_local.replace(tzinfo=None).isoformat()
    chosen_fold = 0 if ambiguous == "earlier" else 1

    kwargs: dict[str, Any] = {
        "birth_local": resolved_naive,
        "timezone": case["timezone"],
        "longitude_deg": case["longitude_deg"],
        "latitude_deg": case["latitude_deg"],
        "fold": chosen_fold,
    }
    for opt in ("time_standard", "day_boundary"):
        if opt in case:
            kwargs[opt] = case[opt]

    res = compute_bazi(BaziInput(**kwargs))
    pillars = (
        str(res.pillars.year),
        str(res.pillars.month),
        str(res.pillars.day),
        str(res.pillars.hour),
    )
    return {
        "id": case["id"],
        "category": case["category"],
        "input": {k: v for k, v in case.items() if k not in {"id", "category"}},
        "output": {
            "pillars": {
                "year": pillars[0],
                "month": pillars[1],
                "day": pillars[2],
                "hour": pillars[3],
            },
            "is_before_lichun": bool(res.is_before_lichun),
            "birth_utc_iso": res.birth_utc_dt.isoformat(),
        },
    }


def build_baseline(cases: Iterable[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Assemble the full baseline document (deterministic)."""
    ephemeris_mode = _detect_ephemeris_mode()
    prior = _apply_ephemeris_mode_to_env(ephemeris_mode)
    try:
        from bazi_engine import __version__ as engine_version
        from bazi_engine.provenance import WUXING_PARAMETER_SET

        records = [_compute_one(c) for c in (cases or BASELINE_CASES)]
    finally:
        _restore_ephemeris_mode(prior)

    return {
        "schema_version": "1.0",
        "purpose": (
            "Engine-derived v1 baseline for regression detection only. "
            "NOT an external oracle. See "
            "spec/golden/bazi_case.schema.json source_type taxonomy."
        ),
        "metadata": {
            "engine_version": engine_version,
            "parameter_set_version": WUXING_PARAMETER_SET["version"],
            "ruleset_id": _load_ruleset_id(),
            "ephemeris_mode": ephemeris_mode,
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "exporter": "scripts/export_bazi_baseline.py",
        },
        "cases": records,
    }


def _serialize(doc: dict[str, Any]) -> str:
    return json.dumps(doc, sort_keys=True, indent=2, ensure_ascii=False) + "\n"


def _strip_volatile(doc: dict[str, Any]) -> dict[str, Any]:
    """Remove non-output volatile fields before comparison (--check)."""
    copy = json.loads(json.dumps(doc))
    copy["metadata"].pop("exported_at", None)
    return copy


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--check", action="store_true",
                        help="Compare against existing file; exit 1 on drift.")
    args = parser.parse_args(argv)

    doc = build_baseline()

    if args.check:
        if not args.out.exists():
            print(f"[FAIL] Baseline {args.out} does not exist.", file=sys.stderr)
            return 1
        existing = json.loads(args.out.read_text())
        if _strip_volatile(existing) != _strip_volatile(doc):
            print("[FAIL] Baseline drift detected.", file=sys.stderr)
            return 1
        print(f"[OK] Baseline unchanged ({len(doc['cases'])} cases).")
        return 0

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(_serialize(doc))
    print(f"[OK] Wrote baseline → {args.out} ({len(doc['cases'])} cases).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
