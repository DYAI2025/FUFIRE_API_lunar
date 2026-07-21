"""
Extended golden reference cases for BaZi Engine.

Each case is a tuple of:
    (id, birth_local, timezone, longitude, latitude, expected_pillars,
     source_note, source_type)

``expected_pillars`` is a tuple of (Year, Month, Day, Hour) pillar
strings, e.g. ("JiaChen", "BingYin", "WuXu", "DingSi").

``source_type`` follows ``spec/golden/bazi_case.schema.json``:

- ``ENGINE_BASELINE``       — expected values were produced by the
                              engine itself (here: BaZi Engine
                              v1.0.0-rc0 under Swiss Ephemeris). Useful
                              **only** for regression detection. Cannot
                              be promoted to "truth" without an
                              external oracle.
- ``EXTERNAL_ORACLE``       — expected values verified against a
                              domain-authoritative external source.
                              These can block default behavior changes
                              (see release gate).
- ``DOMAIN_REVIEW_REQUIRED`` — case is included but expected pillars
                              are *not yet* verified; test_golden.py
                              treats it as a known gap (xfail / skip
                              with reason).

History: Prior to BAZI-PRECISION-V2 all entries below were tagged as
informal "source" categories (engine / lichun / zi_hour / geo /
historical) without distinguishing engine-derived from
externally-verified values. They have all been re-classified as
``ENGINE_BASELINE`` because every value was produced by the engine
v1.0.0-rc0. EXTERNAL_ORACLE entries will be added under FBP-00-005 /
FBP-02-007 with citations.
"""
from __future__ import annotations

from typing import Literal, Tuple

# (id, birth_local, timezone, lon, lat, (year, month, day, hour),
#  source_note, source_type)
SourceType = Literal["ENGINE_BASELINE", "EXTERNAL_ORACLE", "DOMAIN_REVIEW_REQUIRED"]
GoldenCase = Tuple[str, str, str, float, float, Tuple[str, str, str, str], str, SourceType]


def split_by_source_type(
    cases: list[GoldenCase],
) -> dict[SourceType, list[GoldenCase]]:
    """Group cases by source_type so tests can apply different policies.

    EXTERNAL_ORACLE failures = blocker.
    ENGINE_BASELINE failures = regression-only (still a signal, but
    cannot retroactively define truth).
    DOMAIN_REVIEW_REQUIRED   = xfail / informational.
    """
    out: dict[SourceType, list[GoldenCase]] = {
        "ENGINE_BASELINE": [],
        "EXTERNAL_ORACLE": [],
        "DOMAIN_REVIEW_REQUIRED": [],
    }
    for case in cases:
        out[case[7]].append(case)
    return out


EXTENDED_GOLDEN_CASES: list[GoldenCase] = [
    # --- Historical / Notable Dates ---
    (
        "singapore_independence",
        "1965-08-09T10:00:00",
        "Asia/Singapore",
        103.85,
        1.29,
        ("YiSi", "JiaShen", "YiWei", "XinSi"),
        "historical: Singapore independence proclamation, 9 Aug 1965 10:00 SGT",
        "ENGINE_BASELINE",
    ),
    # --- Timezone Diversity ---
    (
        "tokyo_midnight",
        "2024-01-01T00:05:00",
        "Asia/Tokyo",
        139.69,
        35.69,
        ("GuiMao", "JiaZi", "JiaZi", "JiaZi"),
        "geo: Tokyo just after midnight on New Year 2024 (JST, UTC+9)",
        "ENGINE_BASELINE",
    ),
    (
        "sydney_summer",
        "2024-01-15T15:00:00",
        "Australia/Sydney",
        151.21,
        -33.87,
        ("GuiMao", "YiChou", "WuYin", "GengShen"),
        "geo: Sydney in southern-hemisphere summer, AEDT (UTC+11)",
        "ENGINE_BASELINE",
    ),
    (
        "cape_town_winter",
        "2024-07-15T09:00:00",
        "Africa/Johannesburg",
        18.42,
        -33.92,
        ("JiaChen", "XinWei", "GengChen", "XinSi"),
        "geo: Cape Town in southern-hemisphere winter, SAST (UTC+2)",
        "ENGINE_BASELINE",
    ),
    (
        "bangkok_equinox",
        "2024-03-20T12:00:00",
        "Asia/Bangkok",
        100.50,
        13.76,
        ("JiaChen", "DingMao", "GuiWei", "WuWu"),
        "geo: Bangkok near vernal equinox, tropical latitude (ICT, UTC+7)",
        "ENGINE_BASELINE",
    ),
    # --- LiChun Boundary (Beijing) ---
    # LiChun 2024 falls at ~16:27 CST on Feb 4.
    # One minute before: year = GuiMao (2023).
    # One minute after: year = JiaChen (2024).
    (
        "lichun_2024_before_beijing",
        "2024-02-04T16:26:00",
        "Asia/Shanghai",
        116.40,
        39.90,
        ("GuiMao", "YiChou", "WuXu", "GengShen"),
        "lichun: 1 min before LiChun 2024 in Beijing — year still GuiMao",
        "ENGINE_BASELINE",
    ),
    (
        "lichun_2024_after_beijing",
        "2024-02-04T16:28:00",
        "Asia/Shanghai",
        116.40,
        39.90,
        ("JiaChen", "BingYin", "WuXu", "GengShen"),
        "lichun: 1 min after LiChun 2024 in Beijing — year flips to JiaChen",
        "ENGINE_BASELINE",
    ),
    # --- Zi Hour / Day Boundary ---
    # 23:30 Berlin is Zi hour (early rat), same calendar day.
    # 00:30 Berlin next day is also Zi hour but next calendar day.
    (
        "zi_hour_before_midnight",
        "2024-06-15T23:30:00",
        "Europe/Berlin",
        13.405,
        52.52,
        ("JiaChen", "GengWu", "GengXu", "BingZi"),
        "zi_hour: 23:30 Berlin — Zi hour, still Jun 15 day pillar",
        "ENGINE_BASELINE",
    ),
    (
        "zi_hour_after_midnight",
        "2024-06-16T00:30:00",
        "Europe/Berlin",
        13.405,
        52.52,
        ("JiaChen", "GengWu", "XinHai", "WuZi"),
        "zi_hour: 00:30 Berlin — Zi hour, Jun 16 day pillar (next day)",
        "ENGINE_BASELINE",
    ),
    # --- High Latitude ---
    (
        "reykjavik_summer_solstice",
        "2024-06-21T12:00:00",
        "Atlantic/Reykjavik",
        -21.9,
        64.15,
        ("JiaChen", "GengWu", "BingChen", "JiaWu"),
        "geo: Reykjavik at summer solstice, high latitude 64N (GMT, UTC+0)",
        "ENGINE_BASELINE",
    ),
    # --- Tropical ---
    (
        "mumbai_monsoon",
        "2024-07-01T06:00:00",
        "Asia/Kolkata",
        72.88,
        19.08,
        ("JiaChen", "GengWu", "BingYin", "XinMao"),
        "geo: Mumbai early monsoon season, IST (UTC+5:30)",
        "ENGINE_BASELINE",
    ),
    # --- South America ---
    (
        "sao_paulo_new_year",
        "2024-01-01T00:01:00",
        "America/Sao_Paulo",
        -46.63,
        -23.55,
        ("GuiMao", "JiaZi", "JiaZi", "JiaZi"),
        "geo: São Paulo just after midnight on New Year, BRT (UTC-3)",
        "ENGINE_BASELINE",
    ),
]
