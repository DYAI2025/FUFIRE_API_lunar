"""Tests for precise Jieqi determination in daily eastern horoscope.

Tests both the Swiss Ephemeris path (skipped when SE1 files are missing)
and the day-of-year fallback path (always runs).
"""
from __future__ import annotations

from unittest.mock import patch

import pytest

from bazi_engine.services.daily_eastern import (
    _JIEQI_24_NAMES,
    _determine_jieqi_fallback,
    _determine_jieqi_from_ephemeris,
    generate_eastern_daily,
)

# ── Ephemeris availability check ────────────────────────────────────────────

def _ephemeris_available() -> bool:
    try:
        from bazi_engine.ephemeris import SwissEphBackend
        SwissEphBackend()
        return True
    except Exception:
        return False


_HAS_EPHEMERIS = _ephemeris_available()
_skip_no_ephe = pytest.mark.skipif(
    not _HAS_EPHEMERIS,
    reason="Swiss Ephemeris files not available",
)


# ── Test: 24 Jieqi names are complete ───────────────────────────────────────

class TestJieqiNames:
    def test_24_names_defined(self):
        assert len(_JIEQI_24_NAMES) == 24

    def test_lichun_at_index_21(self):
        """LiChun = 315° / 15 = index 21."""
        assert _JIEQI_24_NAMES[21] == "Lichun"

    def test_chunfen_at_index_0(self):
        """Chunfen = 0° / 15 = index 0."""
        assert _JIEQI_24_NAMES[0] == "Chunfen"

    def test_xiazhi_at_index_6(self):
        """Xiazhi (summer solstice) = 90° / 15 = index 6."""
        assert _JIEQI_24_NAMES[6] == "Xiazhi"

    def test_dongzhi_at_index_18(self):
        """Dongzhi (winter solstice) = 270° / 15 = index 18."""
        assert _JIEQI_24_NAMES[18] == "Dongzhi"


# ── Test: Fallback path (always runs) ───────────────────────────────────────

class TestJieqiFallback:
    """Test the day-of-year approximation fallback."""

    def test_spring_equinox_area(self):
        """Around March 20 (day ~80) → Chunfen (0°)."""
        result = _determine_jieqi_fallback("2026-03-21")
        assert result == "Chunfen"

    def test_summer_solstice_area(self):
        """Around June 21 (day ~172) → Xiazhi (90°)."""
        result = _determine_jieqi_fallback("2026-06-22")
        assert result == "Xiazhi"

    def test_winter_solstice_area(self):
        """Around Dec 22 (day ~356) → Dongzhi (270°)."""
        result = _determine_jieqi_fallback("2026-12-22")
        assert result == "Dongzhi"

    def test_returns_valid_jieqi_name(self):
        """Any date should return a name from the 24 list."""
        for month in range(1, 13):
            result = _determine_jieqi_fallback(f"2026-{month:02d}-15")
            assert result in _JIEQI_24_NAMES, f"Month {month} returned unknown: {result}"


# ── Test: Ephemeris path (skip if SE1 files missing) ─────────────────────────

@_skip_no_ephe
class TestJieqiEphemeris:
    """Test Swiss Ephemeris-based Jieqi determination."""

    def test_lichun_boundary_before(self):
        """Day before LiChun (~Feb 3-4) should NOT return Lichun."""
        result = _determine_jieqi_from_ephemeris("2026-02-03")
        assert result != "Lichun"
        # Should be Dahan (300°) or Xiaohan (285°)
        assert result in ("Dahan", "Xiaohan")

    def test_lichun_boundary_after(self):
        """Day after LiChun (~Feb 4-5) should return Lichun."""
        result = _determine_jieqi_from_ephemeris("2026-02-05")
        assert result == "Lichun"

    def test_chunfen_march(self):
        """March 20-21 should be Chunfen (vernal equinox)."""
        result = _determine_jieqi_from_ephemeris("2026-03-21")
        assert result == "Chunfen"

    def test_liqiu_august(self):
        """Around Aug 7 should be near Liqiu (135°) boundary."""
        result = _determine_jieqi_from_ephemeris("2026-08-08")
        assert result == "Liqiu"

    def test_dongzhi_december(self):
        """Around Dec 22 should be Dongzhi (winter solstice)."""
        result = _determine_jieqi_from_ephemeris("2026-12-22")
        assert result == "Dongzhi"

    def test_consistency_with_fallback(self):
        """Ephemeris and fallback should agree for dates far from boundaries."""
        # Mid-month dates are far from any 15° boundary
        for date in ["2026-04-01", "2026-07-01", "2026-10-01"]:
            ephe = _determine_jieqi_from_ephemeris(date)
            fallback = _determine_jieqi_fallback(date)
            assert ephe == fallback, f"{date}: ephemeris={ephe}, fallback={fallback}"


# ── Test: Graceful fallback when ephemeris fails ─────────────────────────────

class TestJieqiGracefulFallback:
    """Ensure _determine_jieqi_from_ephemeris falls back gracefully."""

    def test_fallback_on_ephemeris_error(self):
        """When SwissEphBackend raises, should use fallback, not crash."""
        with patch(
            "bazi_engine.services.daily_eastern.SwissEphBackend",
            side_effect=Exception("SE1 files missing"),
        ):
            result = _determine_jieqi_from_ephemeris("2026-06-22")
        # Should get a valid Jieqi name from fallback
        assert result in _JIEQI_24_NAMES

    def test_jieqi_appears_in_daily_summary(self):
        """The generated summary should contain the Jieqi name."""
        result = generate_eastern_daily(
            day_master="Geng",
            target_date="2026-06-22",
        )
        # Check that some Jieqi name appears in summary
        assert "Solarterm:" in result["summary"]
        # Extract the term name after "Solarterm: " (first word before ".")
        after_solarterm = result["summary"].split("Solarterm: ")[1]
        term_in_summary = after_solarterm.split(".")[0]
        assert term_in_summary in _JIEQI_24_NAMES


# ── Test: No month-based approximation in code path ──────────────────────────

class TestNoMonthApproximation:
    """Verify the old (dt.month - 1) % 12 pattern is not used."""

    def test_generate_eastern_daily_uses_ephemeris_or_fallback(self):
        """The function should call _determine_jieqi_from_ephemeris, not hardcode month."""
        with patch(
            "bazi_engine.services.daily_eastern._determine_jieqi_from_ephemeris",
            return_value="Lichun",
        ) as mock_jieqi:
            generate_eastern_daily(day_master="Jia", target_date="2026-02-05")
            mock_jieqi.assert_called_once_with("2026-02-05")
