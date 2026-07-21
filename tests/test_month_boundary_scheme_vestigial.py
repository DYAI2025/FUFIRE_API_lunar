"""FBP-02-006 — month_boundary_scheme is vestigial.

The field exists in BaziInput for backward compatibility but is not
consulted by compute_bazi(). The ruleset's month_boundary block is
the actual source. This test pins the no-effect property so a future
implementation that accidentally wires this field surfaces as a
failing test.
"""
from __future__ import annotations

import warnings

import pytest

from bazi_engine.ephemeris import ensure_ephemeris_files
from bazi_engine.exc import EphemerisUnavailableError

try:
    ensure_ephemeris_files(None)
except (FileNotFoundError, EphemerisUnavailableError):
    pytest.skip("Swiss Ephemeris files not available.", allow_module_level=True)

from bazi_engine.bazi import compute_bazi
from bazi_engine.types import BaziInput

BASE = dict(
    birth_local="2024-02-10T14:30:00",
    timezone="Europe/Berlin",
    longitude_deg=13.4050,
    latitude_deg=52.52,
)


def test_month_boundary_scheme_does_not_affect_pillars():
    """jie_only vs all_24 must produce identical pillars (today).

    If this assertion ever fails, either the field has finally been
    wired up (then this test should be replaced with a real
    behavior test) or there is a regression.
    """
    jie = compute_bazi(BaziInput(**BASE, month_boundary_scheme="jie_only"))
    all24 = compute_bazi(BaziInput(**BASE, month_boundary_scheme="all_24"))
    assert str(jie.pillars.year) == str(all24.pillars.year)
    assert str(jie.pillars.month) == str(all24.pillars.month)
    assert str(jie.pillars.day) == str(all24.pillars.day)
    assert str(jie.pillars.hour) == str(all24.pillars.hour)


def test_non_default_month_boundary_scheme_emits_deprecation_warning():
    """Phase 2 marks the field deprecated; non-default values warn."""
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        compute_bazi(BaziInput(**BASE, month_boundary_scheme="all_24"))
    deprecation_warnings = [
        w for w in caught if issubclass(w.category, DeprecationWarning)
        and "month_boundary_scheme" in str(w.message)
    ]
    assert len(deprecation_warnings) >= 1, (
        f"Expected DeprecationWarning mentioning month_boundary_scheme; "
        f"got: {[str(w.message) for w in caught]}"
    )


def test_default_month_boundary_scheme_does_not_warn():
    """Setting the default value (or omitting the field) must not warn."""
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        compute_bazi(BaziInput(**BASE))
        compute_bazi(BaziInput(**BASE, month_boundary_scheme="jie_only"))
    deprecation_warnings = [
        w for w in caught if issubclass(w.category, DeprecationWarning)
        and "month_boundary_scheme" in str(w.message)
    ]
    assert deprecation_warnings == [], (
        f"Default value must not warn; got: "
        f"{[str(w.message) for w in deprecation_warnings]}"
    )
