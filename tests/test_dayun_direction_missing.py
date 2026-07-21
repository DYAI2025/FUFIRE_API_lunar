import pytest

from bazi_engine.dayun.direction import DirectionBasisMissingError, resolve_direction


def test_explicit_without_flow_direction_raises():
    with pytest.raises(DirectionBasisMissingError, match="direction_basis_missing"):
        resolve_direction({"direction_method": "explicit"})


def test_traditional_without_sex_at_birth_raises():
    with pytest.raises(DirectionBasisMissingError, match="direction_basis_missing"):
        resolve_direction({
            "direction_method": "year_stem_yinyang_and_sex",
            "year_stem_polarity": "yang",
        })


def test_traditional_without_year_stem_polarity_raises():
    with pytest.raises(DirectionBasisMissingError, match="direction_basis_missing"):
        resolve_direction({
            "direction_method": "year_stem_yinyang_and_sex",
            "sex_at_birth": "male",
        })


def test_missing_direction_method_entirely_raises():
    with pytest.raises(DirectionBasisMissingError, match="direction_basis_missing"):
        resolve_direction({})
