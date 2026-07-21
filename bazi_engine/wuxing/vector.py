"""
wuxing/vector.py — WuXingVector dataclass.

A normalized 5-dimensional vector representing the Wu-Xing
(Five Elements) distribution of a chart or planet set.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import sqrt
from typing import Dict, List


@dataclass
class WuXingVector:
    """Elemental distribution as a 5D vector (Holz, Feuer, Erde, Metall, Wasser)."""

    holz: float
    feuer: float
    erde: float
    metall: float
    wasser: float

    def to_list(self) -> List[float]:
        return [self.holz, self.feuer, self.erde, self.metall, self.wasser]

    def to_dict(self) -> Dict[str, float]:
        return {
            "Holz":   self.holz,
            "Feuer":  self.feuer,
            "Erde":   self.erde,
            "Metall": self.metall,
            "Wasser": self.wasser,
        }

    def magnitude(self) -> float:
        """L2 norm of the vector."""
        return sqrt(sum(x ** 2 for x in self.to_list()))

    def normalize(self) -> WuXingVector:
        """Return unit vector. Returns self unchanged if magnitude is zero."""
        mag = self.magnitude()
        if mag == 0:
            return self
        return WuXingVector(*[x / mag for x in self.to_list()])

    def sum_l1_normalize(self) -> WuXingVector:
        """Return the L1 (sum)-normalized vector: each component / sum(components).

        For a non-negative vector the result sums to 1 — a probability-like
        distribution over the five elements. Returns self unchanged if the
        component sum is zero (zero/empty vector), mirroring the zero-guard of
        :meth:`normalize` so callers never hit a division by zero.

        Pure: does not mutate ``self``.
        """
        total = sum(self.to_list())
        if total == 0:
            return self
        return WuXingVector(*[x / total for x in self.to_list()])

    @staticmethod
    def zero() -> WuXingVector:
        return WuXingVector(0.0, 0.0, 0.0, 0.0, 0.0)
