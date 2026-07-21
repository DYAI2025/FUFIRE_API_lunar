"""Tests for the Da-Yun jieqi anchor resolver adapter.

TASK-DY-007: thin adapter over the existing FuFirE solar-terms engine that
returns the nearest jieqi anchor in a given direction from a birth datetime.
"""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from bazi_engine.ephemeris import ensure_ephemeris_files
from bazi_engine.exc import EphemerisUnavailableError

try:
    ensure_ephemeris_files(None)
except (FileNotFoundError, EphemerisUnavailableError):
    pytest.skip(
        "Jieqi anchor tests require Swiss Ephemeris files. "
        "Set SE_EPHE_PATH to run.",
        allow_module_level=True,
    )

from bazi_engine.dayun.jieqi import resolve_jieqi_anchor

# ── Schema-shape assertions ──────────────────────────────────────────────

def test_forward_returns_required_keys():
    """Forward anchor returns dict with the four required keys + correct types."""
    birth = datetime(1987, 7, 4, 21, 30, tzinfo=ZoneInfo("Europe/Berlin"))
    out = resolve_jieqi_anchor(birth, "forward")
    assert set(out.keys()) == {"name", "direction", "local_dt", "delta"}
    assert out["direction"] == "next"
    assert isinstance(out["name"], str)
    assert isinstance(out["local_dt"], str)
    assert set(out["delta"].keys()) == {"days", "hours", "minutes"}
    assert all(isinstance(v, int) for v in out["delta"].values())


def test_backward_returns_required_keys():
    birth = datetime(1987, 7, 4, 21, 30, tzinfo=ZoneInfo("Europe/Berlin"))
    out = resolve_jieqi_anchor(birth, "backward")
    assert out["direction"] == "previous"


def test_name_is_in_schema_enum():
    """Returned name MUST match the schema's JieqiEnum (space-separated Pinyin)."""
    JIEQI_SCHEMA_NAMES = {
        "Li Chun", "Yu Shui", "Jing Zhe", "Chun Fen", "Qing Ming", "Gu Yu",
        "Li Xia", "Xiao Man", "Mang Zhong", "Xia Zhi", "Xiao Shu", "Da Shu",
        "Li Qiu", "Chu Shu", "Bai Lu", "Qiu Fen", "Han Lu", "Shuang Jiang",
        "Li Dong", "Xiao Xue", "Da Xue", "Dong Zhi", "Xiao Han", "Da Han",
    }
    birth = datetime(2026, 1, 15, 12, 0, tzinfo=ZoneInfo("Europe/Berlin"))
    assert resolve_jieqi_anchor(birth, "forward")["name"] in JIEQI_SCHEMA_NAMES
    assert resolve_jieqi_anchor(birth, "backward")["name"] in JIEQI_SCHEMA_NAMES


def test_delta_is_non_negative():
    """Delta components are always >= 0 (the adapter takes absolute value)."""
    birth = datetime(1987, 7, 4, 21, 30, tzinfo=ZoneInfo("Europe/Berlin"))
    for d in ("forward", "backward"):
        delta = resolve_jieqi_anchor(birth, d)["delta"]
        assert delta["days"] >= 0
        assert 0 <= delta["hours"] < 24
        assert 0 <= delta["minutes"] < 60


def test_local_dt_is_in_birth_tz():
    """local_dt offset matches the birth datetime's tz offset."""
    birth = datetime(1987, 7, 4, 21, 30, tzinfo=ZoneInfo("Europe/Berlin"))
    out = resolve_jieqi_anchor(birth, "forward")
    # Europe/Berlin in July = CEST = UTC+02:00. ISO suffix should reflect this.
    assert "+02:00" in out["local_dt"], f"Expected +02:00 in {out['local_dt']}"


# ── Article-example sanity (values discovered, not asserted from article) ──

def test_article_example_forward_anchor_is_xiao_shu():
    """For birth 1987-07-04T21:30 Berlin forward, the next jieqi should be Xiao Shu (105°)."""
    birth = datetime(1987, 7, 4, 21, 30, tzinfo=ZoneInfo("Europe/Berlin"))
    out = resolve_jieqi_anchor(birth, "forward")
    assert out["name"] == "Xiao Shu", f"Expected Xiao Shu, got {out['name']}"
    assert out["direction"] == "next"
    # The article claims 8d14h; live engine value to be confirmed during impl.
    # Acceptable bounds: delta must be < 16 days (max gap between jieqi).
    delta_days_total = (
        out["delta"]["days"]
        + out["delta"]["hours"] / 24
        + out["delta"]["minutes"] / 1440
    )
    assert delta_days_total < 16, f"Delta {delta_days_total}d exceeds max jieqi gap"


# ── Input validation ─────────────────────────────────────────────────────

def test_naive_birth_datetime_raises():
    naive = datetime(1987, 7, 4, 21, 30)  # no tzinfo
    with pytest.raises(Exception, match="(naive|tz|timezone|aware)"):
        resolve_jieqi_anchor(naive, "forward")


def test_invalid_direction_raises():
    birth = datetime(1987, 7, 4, 21, 30, tzinfo=ZoneInfo("Europe/Berlin"))
    with pytest.raises(Exception, match="(direction|forward|backward)"):
        resolve_jieqi_anchor(birth, "sideways")
