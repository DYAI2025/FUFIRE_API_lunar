"""Tests for planetary dignities — domicile, detriment, exaltation, fall."""
from bazi_engine.dignities import (
    DIGNITY_MULTIPLIERS,
    PlanetDignity,
    dignity_multiplier,
    get_dignity,
    get_planet_dignity,
)


class TestGetDignity:
    def test_sun_domicile_in_leo(self):
        assert get_dignity("Sun", 4) == "domicile"

    def test_sun_detriment_in_aquarius(self):
        assert get_dignity("Sun", 10) == "detriment"

    def test_sun_exaltation_in_aries(self):
        assert get_dignity("Sun", 0) == "exaltation"

    def test_sun_fall_in_libra(self):
        assert get_dignity("Sun", 6) == "fall"

    def test_sun_peregrine_in_gemini(self):
        assert get_dignity("Sun", 2) is None

    def test_moon_domicile_in_cancer(self):
        assert get_dignity("Moon", 3) == "domicile"

    def test_moon_exaltation_in_taurus(self):
        assert get_dignity("Moon", 1) == "exaltation"

    def test_moon_detriment_in_capricorn(self):
        assert get_dignity("Moon", 9) == "detriment"

    def test_moon_fall_in_scorpio(self):
        assert get_dignity("Moon", 7) == "fall"

    def test_mercury_domicile_in_gemini(self):
        assert get_dignity("Mercury", 2) == "domicile"

    def test_mercury_domicile_in_virgo(self):
        assert get_dignity("Mercury", 5) == "domicile"

    def test_venus_domicile_in_taurus(self):
        assert get_dignity("Venus", 1) == "domicile"

    def test_venus_domicile_in_libra(self):
        assert get_dignity("Venus", 6) == "domicile"

    def test_mars_domicile_in_aries(self):
        assert get_dignity("Mars", 0) == "domicile"

    def test_mars_domicile_in_scorpio(self):
        assert get_dignity("Mars", 7) == "domicile"

    def test_mars_detriment_in_taurus(self):
        assert get_dignity("Mars", 1) == "detriment"

    def test_mars_exaltation_in_capricorn(self):
        assert get_dignity("Mars", 9) == "exaltation"

    def test_mars_fall_in_cancer(self):
        assert get_dignity("Mars", 3) == "fall"

    def test_jupiter_domicile_in_sagittarius(self):
        assert get_dignity("Jupiter", 8) == "domicile"

    def test_jupiter_domicile_in_pisces(self):
        assert get_dignity("Jupiter", 11) == "domicile"

    def test_saturn_domicile_in_capricorn(self):
        assert get_dignity("Saturn", 9) == "domicile"

    def test_saturn_exaltation_in_libra(self):
        assert get_dignity("Saturn", 6) == "exaltation"

    def test_saturn_fall_in_aries(self):
        assert get_dignity("Saturn", 0) == "fall"

    def test_uranus_domicile_in_aquarius(self):
        assert get_dignity("Uranus", 10) == "domicile"

    def test_neptune_domicile_in_pisces(self):
        assert get_dignity("Neptune", 11) == "domicile"

    def test_pluto_domicile_in_scorpio(self):
        assert get_dignity("Pluto", 7) == "domicile"

    def test_unknown_planet_returns_none(self):
        assert get_dignity("Chiron", 0) is None

    def test_exaltation_precedence_over_other(self):
        # Mercury in Virgo: both domicile and exaltation — domicile checked first
        result = get_dignity("Mercury", 5)
        assert result == "domicile"


class TestGetPlanetDignity:
    def test_returns_frozen_dataclass(self):
        pd = get_planet_dignity("Sun", 4)
        assert isinstance(pd, PlanetDignity)
        assert pd.planet == "Sun"
        assert pd.sign_index == 4
        assert pd.dignity == "domicile"
        assert pd.multiplier == 1.2

    def test_peregrine_multiplier_is_one(self):
        pd = get_planet_dignity("Sun", 2)
        assert pd.dignity is None
        assert pd.multiplier == 1.0

    def test_detriment_multiplier(self):
        pd = get_planet_dignity("Sun", 10)
        assert pd.multiplier == 0.85

    def test_fall_multiplier(self):
        pd = get_planet_dignity("Sun", 6)
        assert pd.multiplier == 0.8

    def test_exaltation_multiplier(self):
        pd = get_planet_dignity("Moon", 1)
        assert pd.multiplier == 1.15


class TestDignityMultiplier:
    def test_sun_in_leo_from_longitude(self):
        # Leo = sign 4, longitudes 120-150
        assert dignity_multiplier("Sun", 135.0) == 1.2

    def test_sun_peregrine_from_longitude(self):
        # Gemini = sign 2, longitudes 60-90
        assert dignity_multiplier("Sun", 75.0) == 1.0

    def test_mars_detriment_from_longitude(self):
        # Taurus = sign 1, longitudes 30-60
        assert dignity_multiplier("Mars", 45.0) == 0.85

    def test_mars_fall_from_longitude(self):
        # Cancer = sign 3, longitudes 90-120
        assert dignity_multiplier("Mars", 100.0) == 0.8

    def test_wraps_at_360(self):
        # 360 degrees should wrap to sign 0 (Aries)
        assert dignity_multiplier("Sun", 360.0) == dignity_multiplier("Sun", 0.0)

    def test_unknown_planet_returns_one(self):
        assert dignity_multiplier("Chiron", 0.0) == 1.0


class TestDignityMultiplierConstants:
    def test_all_four_types_defined(self):
        assert set(DIGNITY_MULTIPLIERS.keys()) == {"domicile", "exaltation", "detriment", "fall"}

    def test_domicile_and_exaltation_boost(self):
        assert DIGNITY_MULTIPLIERS["domicile"] > 1.0
        assert DIGNITY_MULTIPLIERS["exaltation"] > 1.0

    def test_detriment_and_fall_reduce(self):
        assert DIGNITY_MULTIPLIERS["detriment"] < 1.0
        assert DIGNITY_MULTIPLIERS["fall"] < 1.0

    def test_domicile_stronger_than_exaltation(self):
        assert DIGNITY_MULTIPLIERS["domicile"] > DIGNITY_MULTIPLIERS["exaltation"]

    def test_fall_weaker_than_detriment(self):
        assert DIGNITY_MULTIPLIERS["fall"] < DIGNITY_MULTIPLIERS["detriment"]
