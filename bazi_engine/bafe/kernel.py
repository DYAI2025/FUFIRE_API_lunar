from __future__ import annotations

from math import cos, exp, radians
from typing import Any, Dict, List

from .mapping import wrap180


def _von_mises_unnormalized(delta_deg: float, kappa: float) -> float:
    # delta in degrees, mapped to [-180,180]
    d = radians(wrap180(delta_deg))
    return exp(kappa * cos(d))

def branch_centers_deg(*, zi_apex_deg: float, branch_width_deg: float) -> List[float]:
    return [ (zi_apex_deg + k*branch_width_deg) % 360.0 for k in range(12) ]

def soft_branch_weights_von_mises(
    lambda_deg: float,
    *,
    zi_apex_deg: float,
    branch_width_deg: float,
    kappa: float,
) -> List[float]:
    centers = branch_centers_deg(zi_apex_deg=zi_apex_deg, branch_width_deg=branch_width_deg)
    ws = [_von_mises_unnormalized(lambda_deg - c, float(kappa)) for c in centers]
    s = sum(ws)
    if s <= 0.0:
        # Degenerate: fall back to uniform deterministic distribution
        return [1.0/12.0] * 12
    return [w / s for w in ws]

def soft_branch_weights(
    lambda_deg: float,
    *,
    kernel: Dict[str, Any],
    zi_apex_deg: float,
    branch_width_deg: float,
) -> List[float]:
    ktype = (kernel or {}).get("type", "von_mises")
    if ktype != "von_mises":
        raise ValueError(f"Unsupported kernel type: {ktype}")
    kappa = float((kernel or {}).get("kappa", 4.0))
    if kappa < 0:
        raise ValueError("kappa must be >= 0")
    return soft_branch_weights_von_mises(
        lambda_deg,
        zi_apex_deg=zi_apex_deg,
        branch_width_deg=branch_width_deg,
        kappa=kappa,
    )
