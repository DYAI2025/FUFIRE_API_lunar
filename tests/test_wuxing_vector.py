"""
test_wuxing_vector.py — Unit tests for bazi_engine/wuxing/vector.py

Tests mathematical properties of WuXingVector in isolation.
No imports from fusion, analysis, or constants — pure dataclass math.
"""
from __future__ import annotations

from math import isclose, sqrt

from bazi_engine.wuxing.vector import WuXingVector


class TestConstruction:
    def test_fields_accessible(self):
        v = WuXingVector(1.0, 2.0, 3.0, 4.0, 5.0)
        assert v.holz == 1.0
        assert v.feuer == 2.0
        assert v.erde == 3.0
        assert v.metall == 4.0
        assert v.wasser == 5.0

    def test_zero_constructor(self):
        v = WuXingVector.zero()
        assert v.to_list() == [0.0, 0.0, 0.0, 0.0, 0.0]

    def test_zero_all_fields_are_zero(self):
        v = WuXingVector.zero()
        assert v.holz == v.feuer == v.erde == v.metall == v.wasser == 0.0


class TestToList:
    def test_order_matches_wuxing_cycle(self):
        """to_list() must return [Holz, Feuer, Erde, Metall, Wasser]."""
        v = WuXingVector(1, 2, 3, 4, 5)
        lst = v.to_list()
        assert lst[0] == 1  # Holz
        assert lst[1] == 2  # Feuer
        assert lst[2] == 3  # Erde
        assert lst[3] == 4  # Metall
        assert lst[4] == 5  # Wasser

    def test_length_is_five(self):
        assert len(WuXingVector(1, 2, 3, 4, 5).to_list()) == 5

    def test_returns_list_not_tuple(self):
        assert isinstance(WuXingVector(1, 2, 3, 4, 5).to_list(), list)


class TestToDict:
    def test_has_five_keys(self):
        d = WuXingVector(1, 2, 3, 4, 5).to_dict()
        assert len(d) == 5

    def test_keys_are_german_elements(self):
        d = WuXingVector(1, 2, 3, 4, 5).to_dict()
        assert set(d.keys()) == {"Holz", "Feuer", "Erde", "Metall", "Wasser"}

    def test_values_match_fields(self):
        v = WuXingVector(1.1, 2.2, 3.3, 4.4, 5.5)
        d = v.to_dict()
        assert d["Holz"]   == 1.1
        assert d["Feuer"]  == 2.2
        assert d["Erde"]   == 3.3
        assert d["Metall"] == 4.4
        assert d["Wasser"] == 5.5

    def test_roundtrip_list_dict(self):
        v = WuXingVector(1.0, 0.5, 2.0, 0.0, 1.5)
        assert list(v.to_dict().values()) == v.to_list()


class TestMagnitude:
    def test_pythagorean_triple_3_4_0_0_0(self):
        v = WuXingVector(3.0, 4.0, 0.0, 0.0, 0.0)
        assert isclose(v.magnitude(), 5.0)

    def test_unit_vector_magnitude_is_1(self):
        v = WuXingVector(1.0, 0.0, 0.0, 0.0, 0.0)
        assert isclose(v.magnitude(), 1.0)

    def test_zero_vector_magnitude_is_0(self):
        assert WuXingVector.zero().magnitude() == 0.0

    def test_uniform_vector(self):
        v = WuXingVector(1.0, 1.0, 1.0, 1.0, 1.0)
        assert isclose(v.magnitude(), sqrt(5.0))

    def test_magnitude_non_negative(self):
        v = WuXingVector(0.5, 1.2, 3.0, 0.1, 2.8)
        assert v.magnitude() >= 0.0


class TestNormalize:
    def test_normalized_magnitude_is_1(self):
        v = WuXingVector(3.0, 4.0, 0.0, 0.0, 0.0)
        n = v.normalize()
        assert isclose(n.magnitude(), 1.0, abs_tol=1e-9)

    def test_normalized_direction_preserved(self):
        v = WuXingVector(3.0, 4.0, 0.0, 0.0, 0.0)
        n = v.normalize()
        assert isclose(n.holz, 0.6, abs_tol=1e-9)
        assert isclose(n.feuer, 0.8, abs_tol=1e-9)

    def test_zero_normalize_returns_self(self):
        z = WuXingVector.zero()
        n = z.normalize()
        assert n.to_list() == [0.0, 0.0, 0.0, 0.0, 0.0]

    def test_already_unit_normalize_unchanged(self):
        v = WuXingVector(1.0, 0.0, 0.0, 0.0, 0.0)
        n = v.normalize()
        assert isclose(n.holz, 1.0)
        assert isclose(n.magnitude(), 1.0)

    def test_normalize_is_idempotent(self):
        v = WuXingVector(2.0, 3.0, 1.0, 0.5, 4.0)
        n1 = v.normalize()
        n2 = n1.normalize()
        for a, b in zip(n1.to_list(), n2.to_list()):
            assert isclose(a, b, abs_tol=1e-9)

    def test_all_equal_vector_normalizes_to_uniform(self):
        v = WuXingVector(2.0, 2.0, 2.0, 2.0, 2.0)
        n = v.normalize()
        expected = 1.0 / sqrt(5.0)
        for x in n.to_list():
            assert isclose(x, expected, abs_tol=1e-9)


class TestDotProduct:
    """Verify dot product properties using to_list() manually."""

    def test_self_dot_product_equals_magnitude_squared(self):
        v = WuXingVector(1.0, 2.0, 3.0, 0.5, 1.5)
        dot = sum(a * b for a, b in zip(v.to_list(), v.to_list()))
        assert isclose(dot, v.magnitude() ** 2, abs_tol=1e-9)

    def test_orthogonal_vectors_dot_zero(self):
        v1 = WuXingVector(1.0, 0.0, 0.0, 0.0, 0.0)
        v2 = WuXingVector(0.0, 1.0, 0.0, 0.0, 0.0)
        dot = sum(a * b for a, b in zip(v1.to_list(), v2.to_list()))
        assert isclose(dot, 0.0)

    def test_parallel_normalized_vectors_dot_1(self):
        v = WuXingVector(1.0, 2.0, 0.5, 0.0, 3.0)
        n = v.normalize()
        dot = sum(a * b for a, b in zip(n.to_list(), n.to_list()))
        assert isclose(dot, 1.0, abs_tol=1e-9)
