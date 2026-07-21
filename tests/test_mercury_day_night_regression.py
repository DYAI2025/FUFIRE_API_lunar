from __future__ import annotations

from bazi_engine.wuxing.analysis import is_night_chart, planet_to_wuxing


def test_is_night_chart_daytime_branch_non_wrapping() -> None:
    """Regression: daytime geometry (ASC < DSC) must not be night."""
    # Realistic noon-like geometry from ephemeris runs (Berlin pattern):
    # ASC≈174°, DSC≈354°, Sun≈84° (above horizon => day).
    assert is_night_chart(84.0, ascendant=174.0) is False


def test_is_night_chart_nighttime_branch_wrapping() -> None:
    """Regression: nighttime geometry (ASC > DSC) must be night."""
    # Realistic midnight-like geometry from ephemeris runs (Berlin pattern):
    # ASC≈354°, DSC≈174°, Sun≈84° (below horizon => night).
    assert is_night_chart(84.0, ascendant=354.0) is True


def test_mercury_is_earth_for_day_birth() -> None:
    is_night = is_night_chart(84.0, ascendant=174.0)
    element = planet_to_wuxing("Mercury", is_night=is_night)
    assert element == "Erde"


def test_mercury_is_metal_for_night_birth() -> None:
    is_night = is_night_chart(84.0, ascendant=354.0)
    element = planet_to_wuxing("Mercury", is_night=is_night)
    assert element == "Metall"


def test_is_night_chart_non_wrapping_night_arc() -> None:
    """ASC < DSC, Sun on genuine night-side arc must evaluate to night.

    Geometry: ASC=90°, DSC=270°.
    Night arc (forward, below horizon, houses 1-6): 90° → 180° → 270°.
    Sun=180° sits at the midpoint of that arc => night chart.
    """
    assert is_night_chart(180.0, ascendant=90.0) is True
