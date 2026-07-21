"""Tests for impact_types.py — Pydantic models for /impact/active."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from bazi_engine.impact_types import (
    ActivePlanet,
    BaziResonance,
    BirthData,
    Driver,
    Evidence,
    ImpactRequest,
    ImpactResponse,
    ResonanceBadge,
    SpaceWeather,
)

# ── Fixtures ────────────────────────────────────────────────────────────────

def _birth() -> BirthData:
    return BirthData(date="1990-05-23", time="14:30", tz="Europe/Berlin", lat=52.52, lon=13.405)


def _resonance() -> BaziResonance:
    return BaziResonance(element="fire", type="gleichklang", intensity="stark")


def _planet() -> ActivePlanet:
    return ActivePlanet(
        planet="mars",
        aspect="conjunction",
        orb=2.3,
        strength="high",
        is_retrograde=False,
        natal_position=120.5,
        transit_position=122.8,
        sector="fire",
        weight=0.85,
        bazi_resonance=_resonance(),
    )


def _space_weather() -> SpaceWeather:
    return SpaceWeather(kp_index=3.0, solar_pressure=2.1, storm_active=False)


def _evidence() -> Evidence:
    return Evidence(
        resonance_formula="cos(natal_vec, transit_vec) * planet_weight",
        parameters={"natal_vec": [0.3, 0.2, 0.1, 0.2, 0.2], "method": "cosine"},
    )


def _drivers() -> list:
    return [
        Driver(name="geomagnetic", level="calm"),
        Driver(name="solar", level="active"),
        Driver(name="transit", level="tense"),
        Driver(name="day_field", level="calm"),
    ]


def _impact_response() -> ImpactResponse:
    return ImpactResponse(
        harmony_index=0.72,
        day_mode="active",
        intensity=0.65,
        active_planets=[_planet()],
        space_weather=_space_weather(),
        space_weather_score=0.3,
        drivers=_drivers(),
        resonance_badges=[
            ResonanceBadge(
                label="Feuer-Gleichklang",
                element="fire",
                type="gleichklang",
                intensity="stark",
                source_planet="mars",
            ),
        ],
        top_sector="fire",
        day_master="fire",
        evidence=_evidence(),
    )


# ── BirthData ───────────────────────────────────────────────────────────────

class TestBirthData:
    def test_valid_birth(self):
        b = _birth()
        assert b.date == "1990-05-23"
        assert b.lat == 52.52

    def test_time_defaults_to_noon(self):
        b = BirthData(date="2000-01-01", tz="UTC", lat=0, lon=0)
        assert b.time == "12:00"

    def test_time_with_seconds_accepted(self):
        b = BirthData(date="2000-01-01", time="14:30:00", tz="UTC", lat=0, lon=0)
        assert b.time == "14:30:00"

    def test_lat_out_of_range_rejects(self):
        with pytest.raises(ValidationError):
            BirthData(date="2000-01-01", tz="UTC", lat=91, lon=0)

    def test_lon_out_of_range_rejects(self):
        with pytest.raises(ValidationError):
            BirthData(date="2000-01-01", tz="UTC", lat=0, lon=181)

    def test_frozen(self):
        b = _birth()
        with pytest.raises(ValidationError):
            b.date = "2000-01-01"

    def test_invalid_date_format_rejects(self):
        with pytest.raises(ValidationError):
            BirthData(date="23-05-1990", tz="UTC", lat=0, lon=0)

    def test_invalid_time_format_rejects(self):
        with pytest.raises(ValidationError):
            BirthData(date="2000-01-01", time="2pm", tz="UTC", lat=0, lon=0)

    def test_invalid_timezone_rejects(self):
        with pytest.raises(ValidationError, match="Unknown IANA timezone"):
            BirthData(date="2000-01-01", tz="Not/A/Timezone", lat=0, lon=0)

    def test_nan_lat_rejects(self):
        with pytest.raises(ValidationError):
            BirthData(date="2000-01-01", tz="UTC", lat=float("nan"), lon=0)

    def test_inf_lon_rejects(self):
        with pytest.raises(ValidationError):
            BirthData(date="2000-01-01", tz="UTC", lat=0, lon=float("inf"))


# ── ImpactRequest ───────────────────────────────────────────────────────────

class TestImpactRequest:
    def test_minimal_request(self):
        req = ImpactRequest(birth=_birth())
        assert req.target_date is None
        assert req.locale == "de"
        assert req.soulprint_sectors is None

    def test_full_request(self):
        from datetime import date
        req = ImpactRequest(
            birth=_birth(),
            soulprint_sectors={"wood": 0.3, "fire": 0.25, "earth": 0.15, "metal": 0.2, "water": 0.1},
            quiz_sectors={"wood": 0.2, "fire": 0.3, "earth": 0.2, "metal": 0.1, "water": 0.2},
            target_date=date(2026, 4, 13),
            locale="en",
        )
        assert req.target_date.isoformat() == "2026-04-13"
        assert req.soulprint_sectors["fire"] == 0.25

    def test_invalid_sector_key_rejects(self):
        with pytest.raises(ValidationError, match="Invalid sector keys"):
            ImpactRequest(
                birth=_birth(),
                soulprint_sectors={"wood": 0.5, "plasma": 0.5},
            )

    def test_frozen(self):
        req = ImpactRequest(birth=_birth())
        with pytest.raises(ValidationError):
            req.locale = "en"


# ── BaziResonance ───────────────────────────────────────────────────────────

class TestBaziResonance:
    def test_valid_resonance(self):
        r = _resonance()
        assert r.element == "fire"
        assert r.type == "gleichklang"
        assert r.intensity == "stark"

    def test_invalid_type_rejects(self):
        with pytest.raises(ValidationError):
            BaziResonance(element="fire", type="invalid", intensity="stark")

    def test_invalid_intensity_rejects(self):
        with pytest.raises(ValidationError):
            BaziResonance(element="fire", type="naehrung", intensity="extreme")

    def test_invalid_element_rejects(self):
        with pytest.raises(ValidationError):
            BaziResonance(element="plasma", type="gleichklang", intensity="stark")


# ── ActivePlanet ────────────────────────────────────────────────────────────

class TestActivePlanet:
    def test_valid_planet(self):
        p = _planet()
        assert p.planet == "mars"
        assert p.strength == "high"
        assert p.bazi_resonance.type == "gleichklang"

    def test_orb_negative_rejects(self):
        with pytest.raises(ValidationError):
            ActivePlanet(
                planet="mars", aspect="conjunction", orb=-1.0, strength="high",
                is_retrograde=False, natal_position=0, transit_position=0,
                sector="fire", weight=0.5, bazi_resonance=_resonance(),
            )

    def test_weight_above_one_rejects(self):
        with pytest.raises(ValidationError):
            ActivePlanet(
                planet="mars", aspect="conjunction", orb=1.0, strength="high",
                is_retrograde=False, natal_position=0, transit_position=0,
                sector="fire", weight=1.5, bazi_resonance=_resonance(),
            )

    def test_natal_position_360_rejects(self):
        with pytest.raises(ValidationError):
            ActivePlanet(
                planet="mars", aspect="conjunction", orb=1.0, strength="high",
                is_retrograde=False, natal_position=360.0, transit_position=0,
                sector="fire", weight=0.5, bazi_resonance=_resonance(),
            )

    def test_transit_position_negative_rejects(self):
        with pytest.raises(ValidationError):
            ActivePlanet(
                planet="mars", aspect="conjunction", orb=1.0, strength="high",
                is_retrograde=False, natal_position=0, transit_position=-1.0,
                sector="fire", weight=0.5, bazi_resonance=_resonance(),
            )

    def test_empty_planet_name_rejects(self):
        with pytest.raises(ValidationError):
            ActivePlanet(
                planet="", aspect="conjunction", orb=1.0, strength="high",
                is_retrograde=False, natal_position=0, transit_position=0,
                sector="fire", weight=0.5, bazi_resonance=_resonance(),
            )

    def test_invalid_sector_rejects(self):
        with pytest.raises(ValidationError):
            ActivePlanet(
                planet="mars", aspect="conjunction", orb=1.0, strength="high",
                is_retrograde=False, natal_position=0, transit_position=0,
                sector="plasma", weight=0.5, bazi_resonance=_resonance(),
            )

    def test_nan_orb_rejects(self):
        with pytest.raises(ValidationError):
            ActivePlanet(
                planet="mars", aspect="conjunction", orb=float("nan"), strength="high",
                is_retrograde=False, natal_position=0, transit_position=0,
                sector="fire", weight=0.5, bazi_resonance=_resonance(),
            )


# ── SpaceWeather ────────────────────────────────────────────────────────────

class TestSpaceWeather:
    def test_valid_weather(self):
        sw = _space_weather()
        assert sw.kp_index == 3.0
        assert sw.source == "noaa"
        assert sw.storm_active is False
        assert sw.fetched_at is None

    def test_kp_above_9_rejects(self):
        with pytest.raises(ValidationError):
            SpaceWeather(kp_index=10, solar_pressure=1.0)

    def test_inf_solar_pressure_rejects(self):
        with pytest.raises(ValidationError):
            SpaceWeather(kp_index=3.0, solar_pressure=float("inf"))


# ── Driver ──────────────────────────────────────────────────────────────────

class TestDriver:
    def test_valid_driver(self):
        d = Driver(name="geomagnetic", level="calm")
        assert d.name == "geomagnetic"
        assert d.level == "calm"

    def test_invalid_level_rejects(self):
        with pytest.raises(ValidationError):
            Driver(name="geomagnetic", level="extreme")


# ── ResonanceBadge ──────────────────────────────────────────────────────────

class TestResonanceBadge:
    def test_valid_badge(self):
        b = ResonanceBadge(
            label="Feuer-Gleichklang", element="fire",
            type="gleichklang", intensity="stark", source_planet="mars",
        )
        assert b.label == "Feuer-Gleichklang"

    def test_invalid_element_rejects(self):
        with pytest.raises(ValidationError):
            ResonanceBadge(
                label="test", element="plasma",
                type="gleichklang", intensity="stark", source_planet="mars",
            )

    def test_empty_source_planet_rejects(self):
        with pytest.raises(ValidationError):
            ResonanceBadge(
                label="test", element="fire",
                type="gleichklang", intensity="stark", source_planet="",
            )


# ── ImpactResponse ──────────────────────────────────────────────────────────

class TestImpactResponse:
    def test_full_response_round_trip(self):
        resp = _impact_response()
        data = resp.model_dump()
        restored = ImpactResponse.model_validate(data)
        assert restored.harmony_index == 0.72
        assert len(restored.active_planets) == 1
        assert restored.active_planets[0].planet == "mars"
        assert len(restored.drivers) == 4
        assert restored.evidence.resonance_formula == "cos(natal_vec, transit_vec) * planet_weight"

    def test_harmony_index_out_of_range_rejects(self):
        with pytest.raises(ValidationError):
            ImpactResponse(
                harmony_index=1.5, day_mode="calm", intensity=0.5,
                active_planets=[], space_weather=_space_weather(),
                space_weather_score=0.3, drivers=_drivers(),
                top_sector="fire", day_master="fire", evidence=_evidence(),
            )

    def test_empty_active_planets_is_valid(self):
        resp = ImpactResponse(
            harmony_index=0.5, day_mode="calm", intensity=0.3,
            active_planets=[], space_weather=_space_weather(),
            space_weather_score=0.1, drivers=_drivers(),
            top_sector="earth", day_master="water", evidence=_evidence(),
        )
        assert resp.active_planets == []

    def test_partial_flag_default_false(self):
        resp = _impact_response()
        assert resp.partial is False

    def test_json_serialization(self):
        resp = _impact_response()
        json_str = resp.model_dump_json()
        assert '"harmony_index"' in json_str
        assert '"bazi_resonance"' in json_str
        assert '"resonance_formula"' in json_str

    def test_drivers_must_be_exactly_four(self):
        with pytest.raises(ValidationError):
            ImpactResponse(
                harmony_index=0.5, day_mode="calm", intensity=0.3,
                active_planets=[], space_weather=_space_weather(),
                space_weather_score=0.1,
                drivers=[Driver(name="geomagnetic", level="calm")],
                top_sector="fire", day_master="fire", evidence=_evidence(),
            )

    def test_invalid_top_sector_rejects(self):
        with pytest.raises(ValidationError):
            ImpactResponse(
                harmony_index=0.5, day_mode="calm", intensity=0.3,
                active_planets=[], space_weather=_space_weather(),
                space_weather_score=0.1, drivers=_drivers(),
                top_sector="plasma", day_master="fire", evidence=_evidence(),
            )

    def test_nan_harmony_index_rejects(self):
        with pytest.raises(ValidationError):
            ImpactResponse(
                harmony_index=float("nan"), day_mode="calm", intensity=0.5,
                active_planets=[], space_weather=_space_weather(),
                space_weather_score=0.3, drivers=_drivers(),
                top_sector="fire", day_master="fire", evidence=_evidence(),
            )

    def test_frozen(self):
        resp = _impact_response()
        with pytest.raises(ValidationError):
            resp.harmony_index = 0.99


# ── Evidence ────────────────────────────────────────────────────────────────

class TestEvidence:
    def test_valid_evidence(self):
        e = _evidence()
        assert e.resonance_formula == "cos(natal_vec, transit_vec) * planet_weight"
        assert "method" in e.parameters

    def test_empty_parameters_default(self):
        e = Evidence(resonance_formula="test")
        assert e.parameters == {}
