"""Map natal profile → visual signature parameters."""
from __future__ import annotations

import hashlib
import json
import math
from typing import Any, Dict, List


def compute_signature_blueprint(
    soulprint_sectors: List[float],
    wuxing_vector: Dict[str, float],
    harmony_index: float,
) -> Dict[str, Any]:
    """Deterministic signature blueprint from natal data."""
    seed_input = json.dumps({"s": [round(x,6) for x in soulprint_sectors], "w": wuxing_vector, "h": round(harmony_index,4)}, sort_keys=True)
    seed = "sig_v1_" + hashlib.sha256(seed_input.encode()).hexdigest()[:16]

    mean = sum(soulprint_sectors) / len(soulprint_sectors)
    variance = sum((s - mean) ** 2 for s in soulprint_sectors) / len(soulprint_sectors)
    symmetry = max(0.0, min(1.0, 1.0 - math.sqrt(variance) * 10))

    curvature = max(0.0, min(1.0, wuxing_vector.get("Wasser", 0) + wuxing_vector.get("Holz", 0)))
    angularity = max(0.0, min(1.0, wuxing_vector.get("Metall", 0) + wuxing_vector.get("Feuer", 0)))

    sorted_sectors = sorted(soulprint_sectors, reverse=True)
    total = sum(soulprint_sectors) or 1.0
    density = max(0.0, min(1.0, sum(sorted_sectors[:3]) / total))

    contrast = max(0.0, min(1.0, max(soulprint_sectors) - min(soulprint_sectors)))
    orbit_count = max(2, min(5, math.ceil(harmony_index * 5) + 1))

    return {
        "seed": seed,
        "visual": {
            "symmetry": round(symmetry, 4),
            "curvature": round(curvature, 4),
            "angularity": round(angularity, 4),
            "density": round(density, 4),
            "contrast": round(contrast, 4),
            "orbit_count": orbit_count,
        },
        "elements": wuxing_vector,
    }
