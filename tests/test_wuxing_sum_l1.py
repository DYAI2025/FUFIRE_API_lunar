"""Phase A — WuXingVector.sum_l1_normalize() primitive (GT2).

The fusion engine already has L2 (``magnitude``/``normalize``) but NO L1.
``sum_l1_normalize`` divides each component by the sum of all components,
mirroring the zero-guard of the existing ``normalize`` (zero/empty vector →
returned unchanged). These are PURE math invariants — independently true
regardless of any astrology engine — so they kill a "vector fn → constant"
mutation at the primitive level.

REQ-F-006 naming is enforced at the endpoint layer (see
test_fusion_vector_map); here we lock the primitive's math.
"""
from __future__ import annotations

import math

from bazi_engine.wuxing.vector import WuXingVector

# ── sums to 1 (sum > 0) ──────────────────────────────────────────────────────

def test_sum_l1_sums_to_one():
    v = WuXingVector(1.0, 2.0, 3.0, 4.0, 5.0)
    out = v.sum_l1_normalize()
    assert math.isclose(sum(out.to_list()), 1.0, rel_tol=0, abs_tol=1e-12)


def test_sum_l1_component_values():
    """Each component is component / sum(components)."""
    v = WuXingVector(2.0, 0.0, 0.0, 0.0, 2.0)
    out = v.sum_l1_normalize()
    assert math.isclose(out.holz, 0.5, abs_tol=1e-12)
    assert math.isclose(out.wasser, 0.5, abs_tol=1e-12)
    assert out.feuer == 0.0
    assert out.erde == 0.0
    assert out.metall == 0.0


def test_sum_l1_preserves_proportions():
    """L1 normalization is a pure scaling — ratios between components are
    preserved exactly."""
    v = WuXingVector(1.0, 2.0, 0.0, 0.0, 0.0)
    out = v.sum_l1_normalize()
    # holz:feuer was 1:2 → must remain 1:2 (i.e. out.feuer == 2*out.holz)
    assert math.isclose(out.feuer, 2.0 * out.holz, abs_tol=1e-12)


# ── zero-guard (mirror existing normalize) ───────────────────────────────────

def test_zero_vector_unchanged():
    """A zero/empty vector is returned unchanged (no div-by-zero) — mirrors
    the existing L2 normalize() zero-guard."""
    z = WuXingVector.zero()
    out = z.sum_l1_normalize()
    assert out.to_list() == [0.0, 0.0, 0.0, 0.0, 0.0]


def test_zero_vector_returns_self_no_exception():
    """Documented result: zero in → zero out, no ZeroDivisionError raised."""
    z = WuXingVector(0.0, 0.0, 0.0, 0.0, 0.0)
    # must not raise
    out = z.sum_l1_normalize()
    assert isinstance(out, WuXingVector)
    assert sum(out.to_list()) == 0.0


# ── purity: does not mutate the source ──────────────────────────────────────

def test_sum_l1_is_pure():
    v = WuXingVector(1.0, 2.0, 3.0, 4.0, 5.0)
    before = v.to_list()
    _ = v.sum_l1_normalize()
    assert v.to_list() == before, "sum_l1_normalize must not mutate the source"
