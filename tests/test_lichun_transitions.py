"""
tests/test_lichun_transitions.py — Comprehensive tests for BaZi year transitions at LiChun.

Verifies that the year pillar (animal year) correctly changes at LiChun (315° solar
longitude) across multiple years, timezones, time standards, and day boundaries.
Also validates the transition metadata in API endpoint responses.
"""
from __future__ import annotations

from datetime import timedelta
from zoneinfo import ZoneInfo

import pytest

from bazi_engine.bazi import _lichun_jd_ut_for_year, compute_bazi, year_pillar_from_solar_year
from bazi_engine.constants import ANIMALS, BRANCHES, STEMS
from bazi_engine.ephemeris import SwissEphBackend, jd_ut_to_datetime_utc
from bazi_engine.types import BaziInput

# ── Fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def backend():
    return SwissEphBackend()


@pytest.fixture(scope="module")
def lichun_times(backend):
    """Pre-compute LiChun times for years 2020-2028."""
    times = {}
    for year in range(2020, 2029):
        jd = _lichun_jd_ut_for_year(year, backend)
        times[year] = jd_ut_to_datetime_utc(jd)
    return times


# ── Reference data ──────────────────────────────────────────────────────────

EXPECTED_YEAR_PILLARS = {
    2020: ("Geng", "Zi", "Rat"),
    2021: ("Xin", "Chou", "Ox"),
    2022: ("Ren", "Yin", "Tiger"),
    2023: ("Gui", "Mao", "Rabbit"),
    2024: ("Jia", "Chen", "Dragon"),
    2025: ("Yi", "Si", "Snake"),
    2026: ("Bing", "Wu", "Horse"),
    2027: ("Ding", "Wei", "Goat"),
    2028: ("Wu", "Shen", "Monkey"),
}


TIMEZONES = [
    ("Europe/Berlin", 13.405, 52.52),
    ("Asia/Shanghai", 116.40, 39.90),
    ("America/New_York", -73.94, 40.67),
    ("Asia/Tokyo", 139.69, 35.68),
    ("Pacific/Auckland", 174.78, -36.85),
    ("Pacific/Honolulu", -157.86, 21.31),
]


# ── 1. Year pillar mapping sanity ──────────────────────────────────────────

class TestYearPillarMapping:
    """Verify that year_pillar_from_solar_year returns correct stem/branch/animal."""

    @pytest.mark.parametrize("year, expected", EXPECTED_YEAR_PILLARS.items(),
                             ids=[str(y) for y in EXPECTED_YEAR_PILLARS])
    def test_year_pillar_correct(self, year, expected):
        exp_stem, exp_branch, exp_animal = expected
        p = year_pillar_from_solar_year(year)
        assert STEMS[p.stem_index] == exp_stem, f"Stem mismatch for {year}"
        assert BRANCHES[p.branch_index] == exp_branch, f"Branch mismatch for {year}"
        assert ANIMALS[p.branch_index] == exp_animal, f"Animal mismatch for {year}"


# ── 2. LiChun boundary: 2 minutes before/after across timezones ───────────

def _make_transition_cases():
    """Generate test IDs and params for LiChun transition checks."""
    cases = []
    for year in range(2021, 2028):
        for tz_name, lon, lat in TIMEZONES:
            cases.append((year, tz_name, lon, lat))
    return cases


_TRANSITION_CASES = _make_transition_cases()
_TRANSITION_IDS = [f"{y}_{tz.split('/')[-1]}" for y, tz, _, _ in _TRANSITION_CASES]


class TestLiChunBoundary:
    """Year pillar must change precisely at the LiChun moment."""

    @pytest.mark.parametrize("year, tz_name, lon, lat", _TRANSITION_CASES, ids=_TRANSITION_IDS)
    def test_before_lichun_returns_previous_year_animal(self, year, tz_name, lon, lat, lichun_times):
        lichun_utc = lichun_times[year]
        tz = ZoneInfo(tz_name)
        before_local = (lichun_utc.astimezone(tz) - timedelta(minutes=2)).replace(tzinfo=None)

        res = compute_bazi(BaziInput(
            birth_local=before_local.isoformat(),
            timezone=tz_name,
            longitude_deg=lon, latitude_deg=lat,
            strict_local_time=False,
        ))
        _, _, exp_animal = EXPECTED_YEAR_PILLARS[year - 1]
        actual_animal = ANIMALS[res.pillars.year.branch_index]
        assert actual_animal == exp_animal, (
            f"2 min before LiChun {year} in {tz_name}: "
            f"expected {exp_animal}, got {actual_animal}"
        )

    @pytest.mark.parametrize("year, tz_name, lon, lat", _TRANSITION_CASES, ids=_TRANSITION_IDS)
    def test_after_lichun_returns_current_year_animal(self, year, tz_name, lon, lat, lichun_times):
        lichun_utc = lichun_times[year]
        tz = ZoneInfo(tz_name)
        after_local = (lichun_utc.astimezone(tz) + timedelta(minutes=2)).replace(tzinfo=None)

        res = compute_bazi(BaziInput(
            birth_local=after_local.isoformat(),
            timezone=tz_name,
            longitude_deg=lon, latitude_deg=lat,
            strict_local_time=False,
        ))
        _, _, exp_animal = EXPECTED_YEAR_PILLARS[year]
        actual_animal = ANIMALS[res.pillars.year.branch_index]
        assert actual_animal == exp_animal, (
            f"2 min after LiChun {year} in {tz_name}: "
            f"expected {exp_animal}, got {actual_animal}"
        )


# ── 3. Month pillar changes at LiChun ─────────────────────────────────────

class TestMonthPillarAtLiChun:
    """Month pillar must transition from Chou (last) to Yin (first) at LiChun."""

    @pytest.mark.parametrize("year", range(2022, 2028))
    def test_month_is_chou_before_lichun(self, year, lichun_times):
        lichun_utc = lichun_times[year]
        tz = ZoneInfo("Europe/Berlin")
        before = (lichun_utc.astimezone(tz) - timedelta(days=1)).replace(tzinfo=None)

        res = compute_bazi(BaziInput(
            birth_local=before.isoformat(),
            timezone="Europe/Berlin",
            longitude_deg=13.405, latitude_deg=52.52,
            strict_local_time=False,
        ))
        assert BRANCHES[res.pillars.month.branch_index] == "Chou", (
            f"1 day before LiChun {year}: month branch should be Chou"
        )

    @pytest.mark.parametrize("year", range(2022, 2028))
    def test_month_is_yin_after_lichun(self, year, lichun_times):
        lichun_utc = lichun_times[year]
        tz = ZoneInfo("Europe/Berlin")
        after = (lichun_utc.astimezone(tz) + timedelta(days=1)).replace(tzinfo=None)

        res = compute_bazi(BaziInput(
            birth_local=after.isoformat(),
            timezone="Europe/Berlin",
            longitude_deg=13.405, latitude_deg=52.52,
            strict_local_time=False,
        ))
        assert BRANCHES[res.pillars.month.branch_index] == "Yin", (
            f"1 day after LiChun {year}: month branch should be Yin"
        )


# ── 4. Calendar year boundary vs solar year ────────────────────────────────

class TestCalendarYearBoundary:
    """Gregorian Jan 1 does NOT change the BaZi year — only LiChun does."""

    @pytest.mark.parametrize("year", range(2022, 2028))
    def test_jan1_uses_previous_solar_year(self, year):
        res = compute_bazi(BaziInput(
            birth_local=f"{year}-01-01T12:00:00",
            timezone="Europe/Berlin",
            longitude_deg=13.405, latitude_deg=52.52,
            strict_local_time=False,
        ))
        _, _, exp_animal = EXPECTED_YEAR_PILLARS[year - 1]
        actual = ANIMALS[res.pillars.year.branch_index]
        assert actual == exp_animal, (
            f"Jan 1 {year}: solar year should be {year - 1} ({exp_animal}), got {actual}"
        )
        assert res.is_before_lichun is True
        assert res.solar_year == year - 1

    @pytest.mark.parametrize("year", range(2022, 2028))
    def test_dec31_uses_current_solar_year(self, year):
        res = compute_bazi(BaziInput(
            birth_local=f"{year}-12-31T12:00:00",
            timezone="Europe/Berlin",
            longitude_deg=13.405, latitude_deg=52.52,
            strict_local_time=False,
        ))
        _, _, exp_animal = EXPECTED_YEAR_PILLARS[year]
        actual = ANIMALS[res.pillars.year.branch_index]
        assert actual == exp_animal, (
            f"Dec 31 {year}: solar year should be {year} ({exp_animal}), got {actual}"
        )
        assert res.is_before_lichun is False
        assert res.solar_year == year


# ── 5. Transition metadata correctness ─────────────────────────────────────

class TestTransitionMetadata:
    """BaziResult must carry correct transition metadata."""

    def test_before_lichun_metadata(self, lichun_times):
        res = compute_bazi(BaziInput(
            birth_local="2025-01-20T12:00:00",
            timezone="Europe/Berlin",
            longitude_deg=13.405, latitude_deg=52.52,
            strict_local_time=False,
        ))
        assert res.solar_year == 2024
        assert res.is_before_lichun is True
        assert res.lichun_next_local_dt is not None
        # lichun_next should be LiChun 2025
        assert res.lichun_next_local_dt.year == 2025

    def test_after_lichun_metadata(self, lichun_times):
        res = compute_bazi(BaziInput(
            birth_local="2025-03-15T12:00:00",
            timezone="Europe/Berlin",
            longitude_deg=13.405, latitude_deg=52.52,
            strict_local_time=False,
        ))
        assert res.solar_year == 2025
        assert res.is_before_lichun is False
        assert res.lichun_next_local_dt is not None
        # lichun_next should be LiChun 2026
        assert res.lichun_next_local_dt.year == 2026

    def test_lichun_year_start_matches_solar_year(self, lichun_times):
        """lichun_local_dt should be the LiChun of the solar year."""
        res = compute_bazi(BaziInput(
            birth_local="2025-01-15T12:00:00",
            timezone="Europe/Berlin",
            longitude_deg=13.405, latitude_deg=52.52,
            strict_local_time=False,
        ))
        # solar_year = 2024, so lichun_local should be LiChun 2024
        assert res.lichun_local_dt.year == 2024


# ── 6. LMT mode at LiChun ─────────────────────────────────────────────────

class TestLMTAtLiChun:
    """LMT time standard must produce correct year pillar at transitions."""

    @pytest.mark.parametrize("standard", ["CIVIL", "LMT"])
    def test_before_lichun_consistent_across_standards(self, standard, lichun_times):
        """Both CIVIL and LMT should agree on the year for a time well before LiChun."""
        res = compute_bazi(BaziInput(
            birth_local="2025-01-15T12:00:00",
            timezone="Europe/Berlin",
            longitude_deg=13.405, latitude_deg=52.52,
            time_standard=standard,
            strict_local_time=False,
        ))
        assert ANIMALS[res.pillars.year.branch_index] == "Dragon"
        assert res.solar_year == 2024

    @pytest.mark.parametrize("standard", ["CIVIL", "LMT"])
    def test_after_lichun_consistent_across_standards(self, standard, lichun_times):
        """Both CIVIL and LMT should agree on the year for a time well after LiChun."""
        res = compute_bazi(BaziInput(
            birth_local="2025-03-01T12:00:00",
            timezone="Europe/Berlin",
            longitude_deg=13.405, latitude_deg=52.52,
            time_standard=standard,
            strict_local_time=False,
        ))
        assert ANIMALS[res.pillars.year.branch_index] == "Snake"
        assert res.solar_year == 2025


# ── 7. Zi boundary does NOT affect year determination ──────────────────────

class TestZiBoundaryDoesNotAffectYear:
    """Day boundary='zi' shifts the day pillar, not the year/month pillar."""

    def test_year_same_regardless_of_day_boundary(self, lichun_times):
        """Year pillar must be identical for midnight vs zi boundary."""
        for boundary in ("midnight", "zi"):
            res = compute_bazi(BaziInput(
                birth_local="2025-02-03T23:30:00",
                timezone="Europe/Berlin",
                longitude_deg=13.405, latitude_deg=52.52,
                day_boundary=boundary,
                strict_local_time=False,
            ))
            # Feb 3 23:30 Berlin is after LiChun 2025 (15:10 CET)
            assert ANIMALS[res.pillars.year.branch_index] == "Snake"
            assert BRANCHES[res.pillars.month.branch_index] == "Yin"

    def test_zi_boundary_shifts_day_not_year(self, lichun_times):
        """With zi boundary, day pillar changes at 23:00 but year stays the same."""
        res_mid = compute_bazi(BaziInput(
            birth_local="2025-02-03T23:30:00",
            timezone="Europe/Berlin",
            longitude_deg=13.405, latitude_deg=52.52,
            day_boundary="midnight",
            strict_local_time=False,
        ))
        res_zi = compute_bazi(BaziInput(
            birth_local="2025-02-03T23:30:00",
            timezone="Europe/Berlin",
            longitude_deg=13.405, latitude_deg=52.52,
            day_boundary="zi",
            strict_local_time=False,
        ))
        # Year and month must be identical
        assert res_mid.pillars.year == res_zi.pillars.year
        assert res_mid.pillars.month == res_zi.pillars.month
        # Day pillar differs (zi shifts to next day)
        assert res_mid.pillars.day != res_zi.pillars.day


# ── 8. API endpoint response validation at transitions ────────────────────

class TestBaziEndpointTransitions:
    """Test /calculate/bazi endpoint response at year transitions."""

    @pytest.fixture(autouse=True)
    def setup_client(self):
        from fastapi.testclient import TestClient

        from bazi_engine.app import app
        self.client = TestClient(app)

    @pytest.mark.parametrize("date, exp_animal, exp_solar_year, exp_before", [
        ("2024-01-15T12:00:00", "Rabbit", 2023, True),
        ("2024-02-03T12:00:00", "Rabbit", 2023, True),
        ("2024-02-05T12:00:00", "Dragon", 2024, False),
        ("2024-06-15T12:00:00", "Dragon", 2024, False),
        ("2025-01-20T12:00:00", "Dragon", 2024, True),
        ("2025-02-04T12:00:00", "Snake",  2025, False),
        ("2026-01-20T12:00:00", "Snake",  2025, True),
        ("2026-02-04T12:00:00", "Horse",  2026, False),
    ], ids=[
        "2024_jan_rabbit", "2024_feb3_rabbit", "2024_feb5_dragon", "2024_jun_dragon",
        "2025_jan_dragon", "2025_feb4_snake", "2026_jan_snake", "2026_feb4_horse",
    ])
    def test_year_animal_and_transition_in_response(self, date, exp_animal, exp_solar_year, exp_before):
        r = self.client.post("/calculate/bazi", json={
            "date": date, "tz": "Europe/Berlin", "lon": 13.405, "lat": 52.52,
        })
        assert r.status_code == 200
        data = r.json()

        assert data["chinese"]["year"]["animal"] == exp_animal
        assert data["transition"]["solar_year"] == exp_solar_year
        assert data["transition"]["is_before_lichun"] == exp_before
        assert data["transition"]["lichun_next"] is not None


class TestChartEndpointTransitions:
    """Test /chart endpoint response at year transitions."""

    @pytest.fixture(autouse=True)
    def setup_client(self):
        from fastapi.testclient import TestClient

        from bazi_engine.app import app
        self.client = TestClient(app)

    @pytest.mark.parametrize("date, exp_animal, exp_solar_year, exp_before", [
        ("2024-01-15T12:00:00", "Rabbit", 2023, True),
        ("2024-02-05T12:00:00", "Dragon", 2024, False),
        ("2025-01-20T12:00:00", "Dragon", 2024, True),
        ("2025-02-10T12:00:00", "Snake",  2025, False),
    ], ids=["2024_jan_rabbit", "2024_feb5_dragon", "2025_jan_dragon", "2025_feb10_snake"])
    def test_chart_year_animal_and_transition(self, date, exp_animal, exp_solar_year, exp_before):
        r = self.client.post("/chart", json={
            "local_datetime": date,
            "tz_id": "Europe/Berlin",
            "geo_lon_deg": 13.405,
            "geo_lat_deg": 52.52,
        })
        assert r.status_code == 200
        data = r.json()

        assert data["bazi"]["pillars"]["year"]["animal"] == exp_animal
        assert data["bazi"]["transition"]["solar_year"] == exp_solar_year
        assert data["bazi"]["transition"]["is_before_lichun"] == exp_before
        assert data["bazi"]["transition"]["lichun_next"] is not None


# ── 9. Extreme timezone: LiChun on different calendar day ──────────────────

class TestExtremeTimezones:
    """In far-east/far-west timezones, LiChun falls on a different calendar day."""

    def test_auckland_lichun_2025_straddles_feb3_feb4(self, lichun_times):
        """LiChun 2025 is Feb 3 14:10 UTC = Feb 4 03:10 NZDT."""
        # Feb 3 23:00 NZDT (= Feb 3 10:00 UTC) → before LiChun → Dragon
        res_before = compute_bazi(BaziInput(
            birth_local="2025-02-03T23:00:00",
            timezone="Pacific/Auckland",
            longitude_deg=174.78, latitude_deg=-36.85,
            strict_local_time=False,
        ))
        assert ANIMALS[res_before.pillars.year.branch_index] == "Dragon"

        # Feb 4 04:00 NZDT (= Feb 3 15:00 UTC) → after LiChun → Snake
        res_after = compute_bazi(BaziInput(
            birth_local="2025-02-04T04:00:00",
            timezone="Pacific/Auckland",
            longitude_deg=174.78, latitude_deg=-36.85,
            strict_local_time=False,
        ))
        assert ANIMALS[res_after.pillars.year.branch_index] == "Snake"

    def test_honolulu_lichun_2024_on_feb3_local(self, lichun_times):
        """LiChun 2024 is Feb 4 08:27 UTC = Feb 3 22:27 HST."""
        # Feb 3 21:00 HST → before LiChun → Rabbit
        res_before = compute_bazi(BaziInput(
            birth_local="2024-02-03T21:00:00",
            timezone="Pacific/Honolulu",
            longitude_deg=-157.86, latitude_deg=21.31,
            strict_local_time=False,
        ))
        assert ANIMALS[res_before.pillars.year.branch_index] == "Rabbit"

        # Feb 3 23:00 HST → after LiChun → Dragon
        res_after = compute_bazi(BaziInput(
            birth_local="2024-02-03T23:00:00",
            timezone="Pacific/Honolulu",
            longitude_deg=-157.86, latitude_deg=21.31,
            strict_local_time=False,
        ))
        assert ANIMALS[res_after.pillars.year.branch_index] == "Dragon"


# ── 10. Day-by-day consistency around LiChun ──────────────────────────────

class TestDayByDayConsistency:
    """Every day Jan 15 - Feb 15 must have the correct year pillar."""

    @pytest.mark.parametrize("year", [2024, 2025, 2026])
    def test_daily_year_pillar_jan15_to_feb15(self, year, lichun_times):
        from datetime import datetime

        lichun_utc = lichun_times[year]
        tz = ZoneInfo("Europe/Berlin")
        lichun_local = lichun_utc.astimezone(tz)

        dt = datetime(year, 1, 15, 12, 0, 0)
        end = datetime(year, 2, 15, 12, 0, 0)

        while dt <= end:
            dt_aware = dt.replace(tzinfo=tz)
            expected_solar_year = year - 1 if dt_aware < lichun_local else year

            res = compute_bazi(BaziInput(
                birth_local=dt.isoformat(),
                timezone="Europe/Berlin",
                longitude_deg=13.405, latitude_deg=52.52,
                strict_local_time=False,
            ))
            expected_pillar = year_pillar_from_solar_year(expected_solar_year)
            assert res.pillars.year == expected_pillar, (
                f"Day {dt.date()} year={year}: "
                f"expected {expected_pillar} (solar {expected_solar_year}), "
                f"got {res.pillars.year}"
            )
            assert res.solar_year == expected_solar_year
            dt += timedelta(days=1)
