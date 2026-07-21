from __future__ import annotations

import pytest

from bazi_engine.ephemeris import ensure_ephemeris_files
from bazi_engine.exc import EphemerisUnavailableError

try:
    ensure_ephemeris_files(None)
except (FileNotFoundError, EphemerisUnavailableError):
    pytest.skip("Legacy tests require Swiss Ephemeris files (no implicit downloads). Set SE_EPHE_PATH to run.", allow_module_level=True)

from bazi_engine.bazi import compute_bazi
from bazi_engine.types import BaziInput

# Note: the prior ``test_day_offset_reference_examples`` was moved to
# ``tests/test_bazi_day_anchor_invariants.py`` so it runs without
# Swiss Ephemeris (it only inspects a ruleset JSON and a constant).
# This module continues to host tests that *do* need the ephemeris.


def test_month_boundaries_strict_increasing():
    inp = BaziInput(
        birth_local="2024-02-10T14:30:00",
        timezone="Europe/Berlin",
        longitude_deg=13.4050,
        latitude_deg=52.52,
    )
    res = compute_bazi(inp)
    bounds = res.month_boundaries_local_dt
    assert len(bounds) == 13
    for a, b in zip(bounds, bounds[1:]):
        assert a < b
