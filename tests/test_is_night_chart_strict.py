"""Strict mode for is_night_chart() — Task 4 of hardening/2026-04-30.

Background:
    is_night_chart() in bazi_engine/wuxing/analysis.py silently accepts a
    None ascendant and falls back to a default day chart. Combined with the
    Task 1 P0 bug (ascendant naming mismatch — angles vs. ascmc), this
    caused every paid request to map Mercury wrong for nighttime births.

    Task 1 fixed the data flow. Task 4 adds a `strict=True` mode so that
    future regressions where the ascendant fails to wire through fail
    loudly at the call site instead of silently mis-classifying the chart.

Tests:
  1. strict=False (default) with None ascendant → returns False (day chart),
     preserving backward compatibility.
  2. strict=True with None ascendant → raises ValueError with an actionable
     hint pointing at western['angles']['Ascendant'].
  3. strict=True with a real ascendant float → works normally (no need to
     touch ephemeris; a literal float is enough to verify the happy path).
"""
from __future__ import annotations

import pytest

from bazi_engine.wuxing.analysis import is_night_chart


def test_strict_false_with_none_ascendant_returns_day() -> None:
    """Backward compatibility: legacy callers without ascendant still work."""
    assert is_night_chart(sun_longitude=180.0, ascendant=None) is False
    # Default kwarg also keeps the old behavior.
    assert is_night_chart(sun_longitude=180.0) is False


def test_strict_true_with_none_ascendant_raises_value_error() -> None:
    """Strict mode must fail loudly — silent fallback is the regression we
    are guarding against."""
    with pytest.raises(ValueError) as excinfo:
        is_night_chart(sun_longitude=180.0, ascendant=None, strict=True)

    msg = str(excinfo.value)
    assert "ascendant" in msg.lower()
    assert "strict" in msg.lower()
    # Actionable hint: tell the caller where the ascendant should come from.
    assert "angles" in msg.lower() or "Ascendant" in msg


def test_strict_true_with_real_ascendant_works() -> None:
    """Happy path: a real ascendant float lets strict mode resolve normally,
    no ephemeris required.  Uses the same Berlin-midnight / Berlin-noon geometry
    validated by test_mercury_day_night_regression.py."""
    # Night: ASC=354° (late Pisces rising) — Berlin midnight geometry.
    # Sun=84° (Gemini) is below the horizon.
    assert is_night_chart(sun_longitude=84.0, ascendant=354.0, strict=True) is True

    # Day: ASC=174° (Virgo rising) — Berlin noon geometry.
    # Sun=84° (Gemini) is above the horizon (near the MC).
    assert is_night_chart(sun_longitude=84.0, ascendant=174.0, strict=True) is False
