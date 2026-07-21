"""Tests for bazi_engine/fixed_stars.py — Level 4 module.

Covers:
- FixedStar and FixedStarConjunction are frozen dataclasses
- Catalog integrity (uniqueness, valid longitudes, valid magnitudes, valid nature)
- fixed_star_conjunctions returns correct matches and orb values
- fixed_star_conjunctions sorts by ascending orb
- fixed_star_conjunctions handles 360°/0° wrap-around
- conjunctions_for_chart aggregates multiple planets
- Edge cases: exact conjunction, no conjunctions, orb=0
"""
from __future__ import annotations

import dataclasses

import pytest

from bazi_engine.fixed_stars import (
    FIXED_STARS,
    FixedStarConjunction,
    conjunctions_for_chart,
    fixed_star_conjunctions,
)


class TestDataclassFrozen:
    def test_fixed_star_is_frozen(self):
        star = FIXED_STARS[0]
        with pytest.raises((dataclasses.FrozenInstanceError, AttributeError)):
            star.name = "mutated"  # type: ignore[misc]

    def test_fixed_star_conjunction_is_frozen(self):
        star = FIXED_STARS[0]
        conj = FixedStarConjunction(star=star, planet="Sun", orb=0.5)
        with pytest.raises((dataclasses.FrozenInstanceError, AttributeError)):
            conj.orb = 9.9  # type: ignore[misc]


class TestCatalogIntegrity:
    def test_catalog_not_empty(self):
        assert len(FIXED_STARS) >= 10

    def test_all_names_unique(self):
        names = [s.name for s in FIXED_STARS]
        assert len(names) == len(set(names))

    def test_all_longitudes_in_range(self):
        for star in FIXED_STARS:
            assert 0.0 <= star.ecliptic_lon < 360.0, (
                f"{star.name} has out-of-range longitude {star.ecliptic_lon}"
            )

    def test_all_natures_valid(self):
        valid = {"benefic", "malefic", "neutral"}
        for star in FIXED_STARS:
            assert star.nature in valid, f"{star.name} has invalid nature {star.nature!r}"

    def test_royal_stars_present(self):
        names = {s.name for s in FIXED_STARS}
        for royal in ("Aldebaran", "Regulus", "Antares", "Fomalhaut"):
            assert royal in names

    def test_sirius_is_brightest(self):
        sirius = next(s for s in FIXED_STARS if s.name == "Sirius")
        for other in FIXED_STARS:
            assert sirius.magnitude <= other.magnitude, (
                f"Sirius ({sirius.magnitude}) should be <= {other.name} ({other.magnitude})"
            )


class TestFixedStarConjunctions:
    def test_exact_conjunction_found(self):
        """Planet at Regulus longitude → conjunction with orb 0."""
        regulus = next(s for s in FIXED_STARS if s.name == "Regulus")
        results = fixed_star_conjunctions("Sun", regulus.ecliptic_lon, orb=1.0)
        assert any(c.star.name == "Regulus" for c in results)
        regulus_conj = next(c for c in results if c.star.name == "Regulus")
        assert regulus_conj.orb == pytest.approx(0.0, abs=1e-9)

    def test_within_orb_found(self):
        regulus = next(s for s in FIXED_STARS if s.name == "Regulus")
        results = fixed_star_conjunctions("Sun", regulus.ecliptic_lon + 0.5, orb=1.0)
        assert any(c.star.name == "Regulus" for c in results)
        regulus_conj = next(c for c in results if c.star.name == "Regulus")
        assert regulus_conj.orb == pytest.approx(0.5, abs=1e-9)

    def test_outside_orb_not_found(self):
        regulus = next(s for s in FIXED_STARS if s.name == "Regulus")
        results = fixed_star_conjunctions("Sun", regulus.ecliptic_lon + 2.0, orb=1.0)
        assert not any(c.star.name == "Regulus" for c in results)

    def test_sorted_by_ascending_orb(self):
        """Multiple stars in orb → result sorted ascending by orb."""
        results = fixed_star_conjunctions("Moon", 204.0, orb=2.0)
        orbs = [c.orb for c in results]
        assert orbs == sorted(orbs)

    def test_planet_name_propagated(self):
        regulus = next(s for s in FIXED_STARS if s.name == "Regulus")
        results = fixed_star_conjunctions("Mars", regulus.ecliptic_lon, orb=1.0)
        assert results[0].planet == "Mars"

    def test_no_conjunction_returns_empty(self):
        """Position with no star within 0.01° → empty list."""
        # Find a longitude that has no star nearby
        occupied = {s.ecliptic_lon for s in FIXED_STARS}
        lon = 0.0
        while any(abs(lon - o) < 0.01 or abs(lon - o - 360) < 0.01 for o in occupied):
            lon += 0.5
        results = fixed_star_conjunctions("Venus", lon, orb=0.01)
        assert results == []

    def test_zero_orb_only_exact(self):
        """orb=0 → only stars at exactly the planet longitude."""
        regulus = next(s for s in FIXED_STARS if s.name == "Regulus")
        results = fixed_star_conjunctions("Sun", regulus.ecliptic_lon, orb=0.0)
        assert len(results) == 1
        assert results[0].star.name == "Regulus"
        assert results[0].orb == pytest.approx(0.0, abs=1e-9)

    def test_wrap_around_zero_degrees(self):
        """Scheat is near 359.37°; planet at 0.5° should find it within 2° orb."""
        scheat = next(s for s in FIXED_STARS if s.name == "Scheat")
        results = fixed_star_conjunctions("Moon", 0.5, orb=2.0)
        assert any(c.star.name == "Scheat" for c in results)
        scheat_conj = next(c for c in results if c.star.name == "Scheat")
        # separation: 360 - 359.37 + 0.5 = 1.13
        assert scheat_conj.orb == pytest.approx(360.0 - scheat.ecliptic_lon + 0.5, abs=1e-6)

    def test_wrap_around_other_direction(self):
        """Planet at 358° should find Scheat (359.37°) within 2° orb."""
        scheat = next(s for s in FIXED_STARS if s.name == "Scheat")
        results = fixed_star_conjunctions("Moon", 358.0, orb=2.0)
        assert any(c.star.name == "Scheat" for c in results)
        scheat_conj = next(c for c in results if c.star.name == "Scheat")
        assert scheat_conj.orb == pytest.approx(scheat.ecliptic_lon - 358.0, abs=1e-6)


class TestConjunctionsForChart:
    def test_multi_planet_aggregation(self):
        regulus = next(s for s in FIXED_STARS if s.name == "Regulus")
        aldebaran = next(s for s in FIXED_STARS if s.name == "Aldebaran")
        positions = {
            "Sun": regulus.ecliptic_lon,
            "Mars": aldebaran.ecliptic_lon,
        }
        results = conjunctions_for_chart(positions, orb=0.5)
        planets_hit = {c.planet for c in results}
        assert "Sun" in planets_hit
        assert "Mars" in planets_hit

    def test_sorted_by_ascending_orb(self):
        regulus = next(s for s in FIXED_STARS if s.name == "Regulus")
        aldebaran = next(s for s in FIXED_STARS if s.name == "Aldebaran")
        positions = {
            "Sun": regulus.ecliptic_lon + 0.3,
            "Moon": aldebaran.ecliptic_lon + 0.1,
        }
        results = conjunctions_for_chart(positions, orb=1.0)
        orbs = [c.orb for c in results]
        assert orbs == sorted(orbs)

    def test_empty_positions_returns_empty(self):
        assert conjunctions_for_chart({}, orb=1.0) == []

    def test_no_hits_returns_empty(self):
        results = conjunctions_for_chart({"Venus": 180.0}, orb=0.0)
        # 180.0° — check if no star is exactly there
        star_at_180 = any(abs(s.ecliptic_lon - 180.0) == 0.0 for s in FIXED_STARS)
        if not star_at_180:
            assert results == []
