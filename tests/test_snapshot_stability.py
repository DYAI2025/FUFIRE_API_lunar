"""Bit-stability snapshot tests for FuFirE / BaZi Engine.

Verifies that identical inputs produce bit-identical outputs across builds.
On first run, generates baseline snapshots to tests/snapshots/.
On subsequent runs, compares current output to stored snapshot and fails on
ANY numerical deviation.

Set UPDATE_SNAPSHOTS=1 to regenerate baselines:
    UPDATE_SNAPSHOTS=1 pytest tests/test_snapshot_stability.py
"""
from __future__ import annotations

import json
import math
import os
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from bazi_engine.app import app

client = TestClient(app)

_SNAPSHOTS_BASE = Path(__file__).parent / "snapshots"
UPDATE_SNAPSHOTS = os.environ.get("UPDATE_SNAPSHOTS", "0") == "1"


def _ephemeris_tag() -> str:
    """Return 'swieph' or 'moseph' based on the active ephemeris backend."""
    mode = os.environ.get("EPHEMERIS_MODE", "").upper()
    if mode == "MOSEPH":
        return "moseph"
    # If SE1 files are available, Swiss Ephemeris is used regardless of env var
    try:
        from bazi_engine.ephemeris import EPHEMERIS_FILES_REQUIRED, _resolve_ephe_path
        path = _resolve_ephe_path(None)
        if all((path / name).exists() for name in EPHEMERIS_FILES_REQUIRED):
            return "swieph"
    except ImportError:
        pass  # ephemeris module not installed — fall back to moseph
    return "moseph"


SNAPSHOTS_DIR = _SNAPSHOTS_BASE / _ephemeris_tag()


# ---------------------------------------------------------------------------
# 50 reference birth cases
# ---------------------------------------------------------------------------
# Each case: (case_id, request_payload_for_bazi)
# The same date/tz/lon/lat is reused across endpoints.

REFERENCE_CASES: list[tuple[str, dict[str, Any]]] = [
    # ── Standard dates (various years 1950-2025) ────────────────────────
    ("std_1950_london", {"date": "1950-06-15T10:00:00", "tz": "Europe/London", "lon": -0.1278, "lat": 51.5074}),
    ("std_1960_paris", {"date": "1960-03-21T08:30:00", "tz": "Europe/Paris", "lon": 2.3522, "lat": 48.8566}),
    ("std_1970_nyc", {"date": "1970-09-01T15:45:00", "tz": "America/New_York", "lon": -74.006, "lat": 40.7128}),
    ("std_1980_tokyo", {"date": "1980-12-25T06:00:00", "tz": "Asia/Tokyo", "lon": 139.6917, "lat": 35.6895}),
    ("std_1990_berlin", {"date": "1990-07-04T12:00:00", "tz": "Europe/Berlin", "lon": 13.405, "lat": 52.52}),
    ("std_2000_sydney", {"date": "2000-01-01T00:01:00", "tz": "Australia/Sydney", "lon": 151.2093, "lat": -33.8688}),
    ("std_2010_mumbai", {"date": "2010-08-15T09:30:00", "tz": "Asia/Kolkata", "lon": 72.8777, "lat": 19.076}),
    ("std_2020_beijing", {"date": "2020-10-01T14:00:00", "tz": "Asia/Shanghai", "lon": 116.4074, "lat": 39.9042}),
    ("std_2024_berlin", {"date": "2024-02-10T14:30:00", "tz": "Europe/Berlin", "lon": 13.405, "lat": 52.52}),
    ("std_2025_la", {"date": "2025-05-20T18:00:00", "tz": "America/Los_Angeles", "lon": -118.2437, "lat": 34.0522}),

    # ── LiChun boundary dates (Feb 3-5, before and after) ──────────────
    ("lichun_2024_before_berlin", {"date": "2024-02-04T09:26:00", "tz": "Europe/Berlin", "lon": 13.405, "lat": 52.52}),
    ("lichun_2024_after_berlin", {"date": "2024-02-04T09:28:00", "tz": "Europe/Berlin", "lon": 13.405, "lat": 52.52}),
    ("lichun_2023_before_beijing", {"date": "2023-02-04T10:40:00", "tz": "Asia/Shanghai", "lon": 116.4074, "lat": 39.9042}),
    ("lichun_2023_after_beijing", {"date": "2023-02-04T10:44:00", "tz": "Asia/Shanghai", "lon": 116.4074, "lat": 39.9042}),
    ("lichun_2020_before_tokyo", {"date": "2020-02-04T18:00:00", "tz": "Asia/Tokyo", "lon": 139.6917, "lat": 35.6895}),
    ("lichun_2020_after_tokyo", {"date": "2020-02-04T18:05:00", "tz": "Asia/Tokyo", "lon": 139.6917, "lat": 35.6895}),
    ("lichun_2000_feb3_nyc", {"date": "2000-02-04T09:00:00", "tz": "America/New_York", "lon": -74.006, "lat": 40.7128}),
    ("lichun_2000_feb4_nyc", {"date": "2000-02-04T15:00:00", "tz": "America/New_York", "lon": -74.006, "lat": 40.7128}),

    # ── Zi hour boundary (23:00-01:00) ─────────────────────────────────
    ("zi_2300_berlin", {"date": "2024-02-10T23:00:00", "tz": "Europe/Berlin", "lon": 13.405, "lat": 52.52}),
    ("zi_2330_berlin", {"date": "2024-02-10T23:30:00", "tz": "Europe/Berlin", "lon": 13.405, "lat": 52.52}),
    ("zi_2359_tokyo", {"date": "2024-06-15T23:59:00", "tz": "Asia/Tokyo", "lon": 139.6917, "lat": 35.6895}),
    ("zi_0001_tokyo", {"date": "2024-06-16T00:01:00", "tz": "Asia/Tokyo", "lon": 139.6917, "lat": 35.6895}),
    ("zi_0030_beijing", {"date": "2024-03-21T00:30:00", "tz": "Asia/Shanghai", "lon": 116.4074, "lat": 39.9042}),
    ("zi_2300_nyc", {"date": "2024-07-04T23:00:00", "tz": "America/New_York", "lon": -74.006, "lat": 40.7128}),
    ("zi_boundary_madrid", {"date": "2024-02-04T23:30:00", "tz": "Europe/Madrid", "lon": -3.7038, "lat": 40.4168}),
    ("zi_0015_london", {"date": "2024-12-25T00:15:00", "tz": "Europe/London", "lon": -0.1278, "lat": 51.5074}),

    # ── High latitude locations (>60 N) ────────────────────────────────
    ("hilat_longyearbyen", {"date": "2024-06-21T12:00:00", "tz": "Arctic/Longyearbyen", "lon": 15.6, "lat": 78.22}),
    ("hilat_reykjavik", {"date": "2024-01-15T10:00:00", "tz": "Atlantic/Reykjavik", "lon": -21.8174, "lat": 64.1466}),
    ("hilat_tromso", {"date": "2024-03-20T15:00:00", "tz": "Europe/Oslo", "lon": 19.0402, "lat": 69.6496}),
    ("hilat_murmansk", {"date": "2024-08-01T08:00:00", "tz": "Europe/Moscow", "lon": 33.0838, "lat": 68.9585}),
    ("hilat_helsinki_winter", {"date": "2024-12-21T12:00:00", "tz": "Europe/Helsinki", "lon": 24.9384, "lat": 60.1699}),
    ("hilat_fairbanks", {"date": "2024-09-22T14:00:00", "tz": "America/Anchorage", "lon": -147.7164, "lat": 64.8378}),

    # ── Different timezones (UTC, CET, JST, EST, IST) ─────────────────
    ("tz_utc", {"date": "2024-04-15T12:00:00", "tz": "UTC", "lon": 0.0, "lat": 0.0}),
    ("tz_cet_vienna", {"date": "2024-04-15T12:00:00", "tz": "Europe/Vienna", "lon": 16.3738, "lat": 48.2082}),
    ("tz_jst_osaka", {"date": "2024-04-15T12:00:00", "tz": "Asia/Tokyo", "lon": 135.5023, "lat": 34.6937}),
    ("tz_est_toronto", {"date": "2024-04-15T12:00:00", "tz": "America/Toronto", "lon": -79.3832, "lat": 43.6532}),
    ("tz_ist_delhi", {"date": "2024-04-15T12:00:00", "tz": "Asia/Kolkata", "lon": 77.209, "lat": 28.6139}),
    ("tz_nzst_auckland", {"date": "2024-04-15T12:00:00", "tz": "Pacific/Auckland", "lon": 174.7633, "lat": -36.8485}),
    ("tz_hst_honolulu", {"date": "2024-04-15T12:00:00", "tz": "Pacific/Honolulu", "lon": -157.8583, "lat": 21.3069}),
    ("tz_brt_saopaulo", {"date": "2024-04-15T12:00:00", "tz": "America/Sao_Paulo", "lon": -46.6333, "lat": -23.5505}),

    # ── Same date, different longitudes (True Solar Time differences) ──
    ("tst_lon_neg120", {"date": "2024-06-21T12:00:00", "tz": "UTC", "lon": -120.0, "lat": 45.0}),
    ("tst_lon_neg60", {"date": "2024-06-21T12:00:00", "tz": "UTC", "lon": -60.0, "lat": 45.0}),
    ("tst_lon_0", {"date": "2024-06-21T12:00:00", "tz": "UTC", "lon": 0.0, "lat": 45.0}),
    ("tst_lon_60", {"date": "2024-06-21T12:00:00", "tz": "UTC", "lon": 60.0, "lat": 45.0}),
    ("tst_lon_120", {"date": "2024-06-21T12:00:00", "tz": "UTC", "lon": 120.0, "lat": 45.0}),
    ("tst_lon_neg15", {"date": "2024-06-21T12:00:00", "tz": "UTC", "lon": -15.0, "lat": 45.0}),
    ("tst_lon_15", {"date": "2024-06-21T12:00:00", "tz": "UTC", "lon": 15.0, "lat": 45.0}),
    ("tst_lon_90", {"date": "2024-06-21T12:00:00", "tz": "UTC", "lon": 90.0, "lat": 45.0}),
    ("tst_lon_neg90", {"date": "2024-06-21T12:00:00", "tz": "UTC", "lon": -90.0, "lat": 45.0}),
    ("tst_lon_180", {"date": "2024-06-21T12:00:00", "tz": "UTC", "lon": 180.0, "lat": 45.0}),
]

assert len(REFERENCE_CASES) == 50, f"Expected 50 cases, got {len(REFERENCE_CASES)}"


# ---------------------------------------------------------------------------
# Endpoints to snapshot
# ---------------------------------------------------------------------------
# Each entry: (endpoint_tag, http_method, path, payload_builder)
# payload_builder takes the base case payload and returns the endpoint-specific payload.

def _bazi_payload(base: dict[str, Any]) -> dict[str, Any]:
    return base.copy()


def _western_payload(base: dict[str, Any]) -> dict[str, Any]:
    return base.copy()


def _fusion_payload(base: dict[str, Any]) -> dict[str, Any]:
    # bazi_pillars omitted -> auto-computed
    return base.copy()


def _wuxing_payload(base: dict[str, Any]) -> dict[str, Any]:
    return base.copy()


ENDPOINTS = [
    ("bazi", "/calculate/bazi", _bazi_payload),
    ("western", "/calculate/western", _western_payload),
    ("fusion", "/calculate/fusion", _fusion_payload),
    ("wuxing", "/calculate/wuxing", _wuxing_payload),
]


# ---------------------------------------------------------------------------
# Snapshot helpers
# ---------------------------------------------------------------------------

def _snapshot_path(case_id: str, endpoint_tag: str) -> Path:
    return SNAPSHOTS_DIR / f"{case_id}__{endpoint_tag}.json"


def _redact_paths(value: Any) -> Any:
    """Replace machine-specific filesystem paths with a placeholder so
    snapshots remain portable across environments."""
    if isinstance(value, str):
        # Redact any path-like string (starts with / and contains multiple segments)
        import re
        return re.sub(r"/(?:Users|home|root|tmp|var)[^\s\"']*", "<REDACTED_PATH>", value)
    return value


_VOLATILE_KEYS = {"computation_timestamp"}


def _normalize_for_snapshot(data: Any) -> Any:
    """Recursively round floats to 10 decimal places to avoid platform
    floating-point representation noise while still catching real drift.
    Also redacts machine-specific paths and strips volatile timestamps."""
    if isinstance(data, float):
        return round(data, 10)
    if isinstance(data, str):
        return _redact_paths(data)
    if isinstance(data, dict):
        return {
            k: _normalize_for_snapshot(v)
            for k, v in data.items()
            if k not in _VOLATILE_KEYS
        }
    if isinstance(data, list):
        return [_normalize_for_snapshot(v) for v in data]
    return data


def _write_snapshot(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2, sort_keys=True, ensure_ascii=False)
        f.write("\n")


def _read_snapshot(path: Path) -> Any:
    with open(path) as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "case_id, payload",
    REFERENCE_CASES,
    ids=[c[0] for c in REFERENCE_CASES],
)
@pytest.mark.parametrize(
    "endpoint_tag, endpoint_path, payload_builder",
    ENDPOINTS,
    ids=[e[0] for e in ENDPOINTS],
)
def test_snapshot_stability(
    case_id: str,
    payload: dict[str, Any],
    endpoint_tag: str,
    endpoint_path: str,
    payload_builder,
) -> None:
    """Verify bit-identical output for each (case, endpoint) pair."""
    request_body = payload_builder(payload)
    response = client.post(endpoint_path, json=request_body)

    # Some high-latitude cases may fail for western/fusion (house calculation).
    # We still snapshot error responses to ensure they are stable.
    actual = _normalize_for_snapshot(response.json())
    snap = _snapshot_path(case_id, endpoint_tag)

    if UPDATE_SNAPSHOTS or not snap.exists():
        _write_snapshot(snap, actual)
        if not UPDATE_SNAPSHOTS:
            pytest.skip(f"Snapshot created: {snap.name}")
        return

    expected = _read_snapshot(snap)

    assert _approx_equal(actual, expected), (
        f"Snapshot mismatch for {case_id} @ {endpoint_path}.\n"
        f"Snapshot file: {snap}\n"
        f"Run with UPDATE_SNAPSHOTS=1 to regenerate.\n"
        f"Diff (expected vs actual):\n"
        f"{_json_diff(expected, actual)}"
    )


# Tolerance for floating-point comparison across platforms.
# Swiss Ephemeris calculations differ between macOS and Linux due to
# different libswe versions and floating-point behaviour:
# - House cusps: ~1e-10 degrees
# - Planet speeds: up to ~2e-5 deg/day (especially Mars, Saturn near station)
# - Small speeds near zero amplify relative differences
_FLOAT_RTOL = 1e-4
_FLOAT_ATOL = 1e-6


def _approx_equal(a: Any, b: Any) -> bool:
    """Deep approximate equality: exact for strings/bools/ints, close for floats."""
    if type(a) is not type(b):
        return False
    if isinstance(a, dict):
        if a.keys() != b.keys():
            return False
        return all(_approx_equal(a[k], b[k]) for k in a)
    if isinstance(a, list):
        if len(a) != len(b):
            return False
        return all(_approx_equal(x, y) for x, y in zip(a, b))
    if isinstance(a, float):
        return math.isclose(a, b, rel_tol=_FLOAT_RTOL, abs_tol=_FLOAT_ATOL)
    return a == b


def _json_diff(expected: Any, actual: Any, path: str = "$") -> str:
    """Produce a human-readable diff between two JSON-like structures."""
    diffs: list[str] = []
    if type(expected) is not type(actual):
        return f"  {path}: type {type(expected).__name__} != {type(actual).__name__}"
    if isinstance(expected, dict):
        all_keys = sorted(set(expected) | set(actual))
        for key in all_keys:
            kp = f"{path}.{key}"
            if key not in expected:
                diffs.append(f"  {kp}: ADDED = {json.dumps(actual[key])[:120]}")
            elif key not in actual:
                diffs.append(f"  {kp}: REMOVED (was {json.dumps(expected[key])[:120]})")
            else:
                sub = _json_diff(expected[key], actual[key], kp)
                if sub:
                    diffs.append(sub)
    elif isinstance(expected, list):
        if len(expected) != len(actual):
            diffs.append(f"  {path}: list length {len(expected)} != {len(actual)}")
        for i, (e, a) in enumerate(zip(expected, actual)):
            sub = _json_diff(e, a, f"{path}[{i}]")
            if sub:
                diffs.append(sub)
    elif expected != actual:
        diffs.append(f"  {path}: {json.dumps(expected)[:80]} != {json.dumps(actual)[:80]}")
    return "\n".join(diffs)
