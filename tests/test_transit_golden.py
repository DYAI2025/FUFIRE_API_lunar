"""Golden vector tests for transit calculations.

These tests use the real Swiss Ephemeris (no mocks) to verify
that planetary position calculations are astronomically correct.
Tests skip gracefully if ephemeris files are not available.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

try:
    from bazi_engine.transit import compute_transit_now
    HAS_EPHE = True
except Exception:
    HAS_EPHE = False

pytestmark = pytest.mark.skipif(
    not HAS_EPHE,
    reason="Swiss Ephemeris not available",
)


class TestTransitGoldenVectors:
    """Verify known planetary positions against Swiss Ephemeris."""

    def _compute(self, iso: str):
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(timezone.utc)
        return compute_transit_now(dt_utc=dt)

    def test_sun_in_pisces_march_2026(self):
        """Sun should be in Pisces (sector 11) on 2026-03-09."""
        result = self._compute("2026-03-09T12:00:00Z")
        sun = result["planets"]["sun"]
        assert sun["sector"] == 11, f"Expected Pisces (11), got sector {sun['sector']}"
        assert sun["sign"] == "pisces"

    def test_sector_intensity_sums_to_positive(self):
        """At least one sector should have non-zero intensity."""
        result = self._compute("2026-03-09T12:00:00Z")
        assert sum(result["sector_intensity"]) > 0

    def test_all_ten_planets_present(self):
        """All 10 planets (7 classical + 3 outer) should be computed."""
        result = self._compute("2026-03-09T12:00:00Z")
        expected = {"sun", "moon", "mercury", "venus", "mars", "jupiter", "saturn",
                    "uranus", "neptune", "pluto"}
        assert set(result["planets"].keys()) == expected

    def test_longitudes_in_valid_range(self):
        """All longitudes should be 0-360."""
        result = self._compute("2026-03-09T12:00:00Z")
        for name, pdata in result["planets"].items():
            assert 0 <= pdata["longitude"] < 360, f"{name} longitude {pdata['longitude']} out of range"

    def test_sectors_match_longitudes(self):
        """Each sector should equal int(longitude / 30)."""
        result = self._compute("2026-03-09T12:00:00Z")
        for name, pdata in result["planets"].items():
            expected_sector = int(pdata["longitude"] // 30)
            assert pdata["sector"] == expected_sector, (
                f"{name}: sector {pdata['sector']} != expected {expected_sector} "
                f"(lon={pdata['longitude']})"
            )

    def test_moon_speed_is_positive(self):
        """Moon should always move forward (positive speed)."""
        result = self._compute("2026-03-09T12:00:00Z")
        moon = result["planets"]["moon"]
        assert moon["speed"] > 0, f"Moon speed {moon['speed']} should be positive"
