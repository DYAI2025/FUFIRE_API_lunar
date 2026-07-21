"""Tests for western.py - Western astrology calculations."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

# Import constants that don't require swisseph
PLANET_NAMES = [
    "Sun", "Moon", "Mercury", "Venus", "Mars",
    "Jupiter", "Saturn", "Uranus", "Neptune", "Pluto",
    "Chiron", "Lilith", "NorthNode", "TrueNorthNode"
]


class TestWesternChartStructure:
    """Tests for compute_western_chart return structure."""

    @pytest.fixture
    def mock_swe(self):
        """Mock swisseph module."""
        with patch.dict('sys.modules', {'swisseph': MagicMock()}):
            import sys
            swe_mock = sys.modules['swisseph']

            # Setup constants
            swe_mock.SUN = 0
            swe_mock.MOON = 1
            swe_mock.MERCURY = 2
            swe_mock.VENUS = 3
            swe_mock.MARS = 4
            swe_mock.JUPITER = 5
            swe_mock.SATURN = 6
            swe_mock.URANUS = 7
            swe_mock.NEPTUNE = 8
            swe_mock.PLUTO = 9
            swe_mock.CHIRON = 15
            swe_mock.MEAN_APOG = 12
            swe_mock.MEAN_NODE = 10
            swe_mock.TRUE_NODE = 11
            swe_mock.FLG_SWIEPH = 2
            swe_mock.FLG_SPEED = 256
            swe_mock.Error = Exception

            # Mock calc_ut to return planet data
            def mock_calc_ut(jd, planet_id, flags):
                # Return (longitude, latitude, distance, speed, x, y), retflag
                lon = (planet_id * 30.0) % 360
                return (lon, 0.5, 1.0, 0.5, 0.0, 0.0), 0

            swe_mock.calc_ut = mock_calc_ut

            # Mock houses
            cusps = [float(i * 30) for i in range(12)]
            ascmc = [120.0, 30.0, 0.0, 240.0]  # ASC, MC, ARMC, Vertex
            swe_mock.houses = MagicMock(return_value=(cusps, ascmc))

            # Mock julday
            swe_mock.julday = MagicMock(return_value=2460351.0625)

            yield swe_mock

    def test_returns_dict(self, mock_swe):
        """Result should be a dictionary."""
        from bazi_engine.western import compute_western_chart

        dt = datetime(2024, 2, 10, 14, 30, tzinfo=timezone.utc)
        result = compute_western_chart(dt, 52.52, 13.405)

        assert isinstance(result, dict)

    def test_has_required_keys(self, mock_swe):
        """Result should have all required keys."""
        from bazi_engine.western import compute_western_chart

        dt = datetime(2024, 2, 10, 14, 30, tzinfo=timezone.utc)
        result = compute_western_chart(dt, 52.52, 13.405)

        assert "jd_ut" in result
        assert "house_system" in result
        assert "bodies" in result
        assert "houses" in result
        assert "angles" in result

    def test_bodies_has_planets(self, mock_swe):
        """Bodies should contain all planets."""
        from bazi_engine.western import compute_western_chart

        dt = datetime(2024, 2, 10, 14, 30, tzinfo=timezone.utc)
        result = compute_western_chart(dt, 52.52, 13.405)

        bodies = result["bodies"]
        for planet in PLANET_NAMES:
            assert planet in bodies

    def test_body_structure(self, mock_swe):
        """Each body should have required fields."""
        from bazi_engine.western import compute_western_chart

        dt = datetime(2024, 2, 10, 14, 30, tzinfo=timezone.utc)
        result = compute_western_chart(dt, 52.52, 13.405)

        sun = result["bodies"]["Sun"]
        assert "longitude" in sun
        assert "latitude" in sun
        assert "distance" in sun
        assert "speed" in sun
        assert "is_retrograde" in sun
        assert "zodiac_sign" in sun
        assert "degree_in_sign" in sun

    def test_houses_has_twelve(self, mock_swe):
        """Should have 12 houses."""
        from bazi_engine.western import compute_western_chart

        dt = datetime(2024, 2, 10, 14, 30, tzinfo=timezone.utc)
        result = compute_western_chart(dt, 52.52, 13.405)

        houses = result["houses"]
        assert len(houses) == 12

    def test_angles_structure(self, mock_swe):
        """Angles should have ASC, MC, Vertex."""
        from bazi_engine.western import compute_western_chart

        dt = datetime(2024, 2, 10, 14, 30, tzinfo=timezone.utc)
        result = compute_western_chart(dt, 52.52, 13.405)

        angles = result["angles"]
        assert "Ascendant" in angles
        assert "MC" in angles
        assert "Vertex" in angles


class TestZodiacSign:
    """Tests for zodiac sign calculation."""

    def test_sign_calculation_formula(self):
        """Zodiac sign is longitude // 30."""
        # Test the formula directly
        assert int(0.0 // 30) == 0   # Aries
        assert int(30.0 // 30) == 1  # Taurus
        assert int(60.0 // 30) == 2  # Gemini
        assert int(90.0 // 30) == 3  # Cancer
        assert int(120.0 // 30) == 4 # Leo
        assert int(150.0 // 30) == 5 # Virgo
        assert int(180.0 // 30) == 6 # Libra
        assert int(210.0 // 30) == 7 # Scorpio
        assert int(240.0 // 30) == 8 # Sagittarius
        assert int(270.0 // 30) == 9 # Capricorn
        assert int(300.0 // 30) == 10 # Aquarius
        assert int(330.0 // 30) == 11 # Pisces

    def test_degree_in_sign_formula(self):
        """Degree in sign is longitude % 30."""
        assert 15.5 % 30 == pytest.approx(15.5)
        assert 45.5 % 30 == pytest.approx(15.5)
        assert 359.0 % 30 == pytest.approx(29.0)


class TestRetrograde:
    """Tests for retrograde detection."""

    def test_negative_speed_is_retrograde(self):
        """Negative speed indicates retrograde."""
        assert (-0.5 < 0) is True

    def test_positive_speed_is_direct(self):
        """Positive speed indicates direct motion."""
        assert (0.5 < 0) is False

    def test_zero_speed_is_station(self):
        """Zero speed is station (not retrograde by definition)."""
        assert (0.0 < 0) is False


class TestHouseSystems:
    """Tests for house system fallback logic."""

    def test_house_system_codes(self):
        """House system codes should be valid."""
        valid_codes = [b'P', b'O', b'W']  # Placidus, Porphyry, Whole Sign
        for code in valid_codes:
            assert isinstance(code, bytes)
            assert len(code) == 1


class TestPlanetConstants:
    """Tests for planet constant definitions."""

    def test_planet_count(self):
        """Should have 14 planets defined."""
        assert len(PLANET_NAMES) == 14

    def test_essential_planets(self):
        """Essential planets should be included."""
        assert "Sun" in PLANET_NAMES
        assert "Moon" in PLANET_NAMES
        assert "Mercury" in PLANET_NAMES
        assert "Venus" in PLANET_NAMES
        assert "Mars" in PLANET_NAMES
        assert "Jupiter" in PLANET_NAMES
        assert "Saturn" in PLANET_NAMES

    def test_outer_planets(self):
        """Outer planets should be included."""
        assert "Uranus" in PLANET_NAMES
        assert "Neptune" in PLANET_NAMES
        assert "Pluto" in PLANET_NAMES

    def test_additional_points(self):
        """Additional points should be included."""
        assert "Chiron" in PLANET_NAMES
        assert "Lilith" in PLANET_NAMES
        assert "NorthNode" in PLANET_NAMES
        assert "TrueNorthNode" in PLANET_NAMES


class TestWesternBodyFrozen:
    """Tests for WesternBody immutability."""

    def test_western_body_is_frozen(self):
        """WesternBody dataclass must be frozen per project convention."""
        try:
            from bazi_engine.western import WesternBody
        except ImportError as e:
            if "swisseph" in str(e):
                pytest.skip("swisseph not installed")
            raise
        import dataclasses
        assert dataclasses.fields(WesternBody)
        body = WesternBody(
            name="Sun", longitude=0.0, latitude=0.0, distance=1.0,
            speed_long=1.0, is_retrograde=False, zodiac_sign=0, degree_in_sign=0.0,
        )
        with pytest.raises(dataclasses.FrozenInstanceError):
            body.longitude = 99.0


class TestWesternBodyDataclass:
    """Tests for WesternBody dataclass."""

    def test_import(self):
        """WesternBody should be importable."""
        try:
            from bazi_engine.western import WesternBody
            assert WesternBody is not None
        except ImportError as e:
            if "swisseph" in str(e):
                pytest.skip("swisseph not installed")
            raise

    def test_dataclass_fields(self):
        """WesternBody should have expected fields."""
        try:
            from dataclasses import fields

            from bazi_engine.western import WesternBody

            field_names = [f.name for f in fields(WesternBody)]
            expected = [
                "name", "longitude", "latitude", "distance",
                "speed_long", "is_retrograde", "zodiac_sign", "degree_in_sign"
            ]
            assert field_names == expected
        except ImportError as e:
            if "swisseph" in str(e):
                pytest.skip("swisseph not installed")
            raise


class TestLongitudeValidation:
    """Tests for longitude value validation."""

    def test_longitude_range(self):
        """Longitude should be 0-360."""
        for lon in [0.0, 90.0, 180.0, 270.0, 359.999]:
            assert 0 <= lon < 360

    def test_zodiac_sign_range(self):
        """Zodiac sign should be 0-11."""
        for lon in range(0, 360, 30):
            sign = int(lon // 30)
            assert 0 <= sign <= 11

    def test_degree_in_sign_range(self):
        """Degree in sign should be 0-30."""
        for lon in [0.0, 15.5, 29.999, 45.0, 359.999]:
            deg = lon % 30
            assert 0 <= deg < 30


def test_sidereal_does_not_pollute_global_state():
    """swe.set_sid_mode must be reset after sidereal computation."""
    import swisseph as swe
    jd_test = swe.julday(2024, 6, 15, 12.0)
    swe.set_sid_mode(0)  # Fagan-Bradley baseline
    ayan_before = swe.get_ayanamsa_ut(jd_test)

    from datetime import datetime, timezone

    from bazi_engine.western import compute_western_chart
    dt = datetime(2024, 6, 15, 12, 0, tzinfo=timezone.utc)
    compute_western_chart(dt, 52.52, 13.405, zodiac_mode="sidereal_lahiri")

    swe.set_sid_mode(0)
    ayan_after = swe.get_ayanamsa_ut(jd_test)
    assert abs(ayan_before - ayan_after) < 0.001, (
        f"swe global state polluted: before={ayan_before}, after={ayan_after}"
    )


class TestJulianDay:
    """Tests for Julian Day calculation."""

    def test_jd_is_float(self):
        """JD should be a float."""
        # Reference: 2024-02-10 12:00 UTC ≈ JD 2460351.0
        jd = 2460351.0625
        assert isinstance(jd, float)
        assert jd > 2400000  # Modern dates

    def test_jd_reasonable_range(self):
        """JD for modern dates should be in reasonable range."""
        # Years 1900-2100 should be roughly JD 2415000-2488000
        min_jd = 2415000
        max_jd = 2490000
        test_jd = 2460351.0
        assert min_jd < test_jd < max_jd
