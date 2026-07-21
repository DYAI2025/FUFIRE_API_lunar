from __future__ import annotations

from math import atan2, cos, degrees, radians, sin
from typing import Any, Dict, List

from .mapping import wrap360


def phasor(angles_deg: List[float], weights: List[float], k: int) -> complex:
    if len(angles_deg) != len(weights):
        raise ValueError("angles and weights length mismatch")
    if k <= 0:
        raise ValueError("k must be positive")
    re = 0.0
    im = 0.0
    for ang, w in zip(angles_deg, weights):
        th = radians(wrap360(float(ang))) * k
        re += float(w) * cos(th)
        im += float(w) * sin(th)
    return complex(re, im)

def phasor_features(angles_deg: List[float], weights: List[float], ks: List[int], *, eps: float = 1e-12) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for k in ks:
        z = phasor(angles_deg, weights, int(k))
        amp = abs(z)
        if amp <= eps:
            out[str(k)] = {
                "R_k": [0.0, 0.0],
                "A_k": 0.0,
                "O_k_deg": None,
                "degenerate": True,
            }
            continue
        phase_deg = wrap360(degrees(atan2(z.imag, z.real)))
        out[str(k)] = {
            "R_k": [float(z.real), float(z.imag)],
            "A_k": float(amp),
            # Convention: orientation in degrees of the underlying fundamental (divide by k)
            "O_k_deg": float(wrap360(phase_deg / float(k))),
            "degenerate": False,
        }
    return out
