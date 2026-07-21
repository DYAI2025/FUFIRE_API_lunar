from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, Optional


def _round_floats(obj: Any, *, decimals: int) -> Any:
    if isinstance(obj, float):
        return round(obj, decimals)
    if isinstance(obj, list):
        return [_round_floats(x, decimals=decimals) for x in obj]
    if isinstance(obj, tuple):
        return [_round_floats(x, decimals=decimals) for x in obj]
    if isinstance(obj, dict):
        return {str(k): _round_floats(v, decimals=decimals) for k, v in obj.items()}
    return obj

def canonical_json_dumps(
    obj: Any,
    *,
    sorted_keys: bool = True,
    utf8: bool = True,
    float_mode: str = "shortest_roundtrip",
    fixed_decimals: Optional[int] = None,
) -> str:
    payload = obj
    if float_mode == "fixed":
        if fixed_decimals is None:
            raise ValueError("fixed_decimals is required when float_mode='fixed'")
        payload = _round_floats(payload, decimals=int(fixed_decimals))
    elif float_mode == "shortest_roundtrip":
        pass
    else:
        raise ValueError(f"Unsupported float_mode: {float_mode}")

    # Deterministic: separators remove spaces, sorted keys for stability.
    return json.dumps(
        payload,
        sort_keys=bool(sorted_keys),
        ensure_ascii=not bool(utf8),
        separators=(",", ":"),
        allow_nan=False,
    )

def sha256_hex(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()

def config_fingerprint(
    engine_config: Dict[str, Any],
    *,
    ruleset_id: str,
    ruleset_version: str,
    refdata_pack_id: str,
    float_format_policy: Dict[str, Any],
    json_canonicalization: Dict[str, Any],
) -> str:
    float_mode = (float_format_policy or {}).get("mode", "shortest_roundtrip")
    fixed_decimals = (float_format_policy or {}).get("fixed_decimals", None)
    sorted_keys = (json_canonicalization or {}).get("sorted_keys", True)
    utf8 = (json_canonicalization or {}).get("utf8", True)

    payload = {
        "engine_config": engine_config,
        "ruleset": {"id": ruleset_id, "version": ruleset_version},
        "refdata": {"refdata_pack_id": refdata_pack_id},
    }
    s = canonical_json_dumps(
        payload,
        sorted_keys=sorted_keys,
        utf8=utf8,
        float_mode=float_mode,
        fixed_decimals=fixed_decimals,
    )
    return sha256_hex(s)
