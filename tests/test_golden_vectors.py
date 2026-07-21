from __future__ import annotations

import pytest

from bazi_engine.bazi import compute_bazi
from bazi_engine.ephemeris import ensure_ephemeris_files
from bazi_engine.exc import EphemerisUnavailableError
from bazi_engine.types import BaziInput

try:
    ensure_ephemeris_files(None)
except (FileNotFoundError, EphemerisUnavailableError):
    pytest.skip("Legacy tests require Swiss Ephemeris files (no implicit downloads). Set SE_EPHE_PATH to run.", allow_module_level=True)

# Format: (Name, Input, ExpectedPillars_Year_Month_Day_Hour)
VECTORS = [
    # 1. Standard Case (Berlin)
    (
        "Berlin_2024_Standard",
        BaziInput(
            birth_local="2024-02-10T14:30:00",
            timezone="Europe/Berlin",
            longitude_deg=13.4050,
            latitude_deg=52.52,
        ),
        ("JiaChen", "BingYin", "JiaChen", "XinWei")
    ),
    # 2. Before LiChun 2024 (Feb 4 ~09:27 local)
    (
        "Berlin_Pre_LiChun",
        BaziInput(
            birth_local="2024-02-04T09:00:00",
            timezone="Europe/Berlin",
            longitude_deg=13.4050,
            latitude_deg=52.52,
        ),
        ("GuiMao", "YiChou", "WuXu", "DingSi") 
        # Year is still GuiMao (2023)
    ),
    # 3. High Latitude (Longyearbyen 78N)
    # Testing that it doesn't crash even if Western houses fail (though BaZi doesn't use houses)
    # Solar terms should still work as Sun is always calculable.
    (
        "Longyearbyen_Winter",
        BaziInput(
            birth_local="2024-01-01T00:01:00",
            timezone="Arctic/Longyearbyen", 
            longitude_deg=15.6,
            latitude_deg=78.22,
        ),
        ("GuiMao", "JiaZi", "JiaZi", "JiaZi") 
        # Check: 2024 Jan 1 is still GuiMao year, Zi month. Day needs verification but shouldn't crash.
        # 2024-01-01 is JiaZi day. 00:01 is Zi hour (Early Rat) -> JiaZi hour.
    ),
    # 4. Custom Day Anchor
    # Shift 1949-10-01 from JiaZi (0) to YiChou (1)
    # Then 2024-02-10 (normally JiaChen 40) should shift to YiSi (41)
    (
        "Custom_Anchor_Shift_1",
        BaziInput(
            birth_local="2024-02-10T14:30:00",
            timezone="Europe/Berlin",
            longitude_deg=13.4050,
            latitude_deg=52.52,
            day_anchor_date_iso="1949-10-01",
            day_anchor_pillar_idx=1 
        ),
        ("JiaChen", "BingYin", "YiSi", "GuiWei")
    ),
     # 5. Day Anchor Validity Check
     # 1949-10-01 as JiaZi (0) -> Standard. Result should be standard.
     (
        "Custom_Anchor_Standard",
        BaziInput(
            birth_local="2024-02-10T14:30:00",
            timezone="Europe/Berlin",
            longitude_deg=13.4050,
            latitude_deg=52.52,
            day_anchor_date_iso="1949-10-01",
            day_anchor_pillar_idx=0
        ),
        ("JiaChen", "BingYin", "JiaChen", "XinWei")
    ),
]

@pytest.mark.parametrize("name, inp, exp", VECTORS, ids=[v[0] for v in VECTORS])
def test_golden_vectors_v04(name, inp, exp):
    res = compute_bazi(inp)
    got = (str(res.pillars.year), str(res.pillars.month), str(res.pillars.day), str(res.pillars.hour))
    assert got == exp, f"Case {name} failed. Expected {exp}, got {got}"
