"""Da-Yun (大運) luck-pillar direction resolver.

Resolves the flow direction (forward/backward) for a Da-Yun sequence.

Two modes are supported:

* ``year_stem_yinyang_and_sex`` — classical rule. Yang year + male → forward;
  Yang year + female → backward; Yin year + male → backward; Yin year +
  female → forward.
* ``explicit`` — caller passes the desired ``flow_direction`` straight through.
"""

from ..exc import InputError


class DirectionBasisMissingError(InputError):
    """Caller did not supply enough information to resolve a Da-Yun direction."""
    error_code = "direction_basis_missing"


_TRADITIONAL = {
    ("yang", "male"): "forward",
    ("yang", "female"): "backward",
    ("yin", "male"): "backward",
    ("yin", "female"): "forward",
}

_VALID_METHODS = ("explicit", "year_stem_yinyang_and_sex")
_VALID_FLOWS = ("forward", "backward")


def resolve_direction(payload):
    """Return ``"forward"`` or ``"backward"`` for the given payload.

    Raises:
        DirectionBasisMissingError: if the payload does not contain enough
            information to resolve a direction (missing ``direction_method``,
            missing ``flow_direction`` in explicit mode, or missing
            ``year_stem_polarity`` / ``sex_at_birth`` in traditional mode).
    """
    method = payload.get("direction_method")
    if method not in _VALID_METHODS:
        raise DirectionBasisMissingError(
            "direction_basis_missing: direction_method required",
            detail={"missing": ["direction_method"]},
        )

    if method == "explicit":
        flow = payload.get("flow_direction")
        if flow not in _VALID_FLOWS:
            raise DirectionBasisMissingError(
                "direction_basis_missing: flow_direction required when direction_method=explicit",
                detail={"missing": ["flow_direction"]},
            )
        return flow

    # method == "year_stem_yinyang_and_sex"
    polarity = payload.get("year_stem_polarity")
    sex = payload.get("sex_at_birth")
    missing = []
    if polarity is None:
        missing.append("year_stem_polarity")
    if sex is None:
        missing.append("sex_at_birth")
    if missing:
        raise DirectionBasisMissingError(
            "direction_basis_missing: " + ", ".join(missing)
            + " required when direction_method=year_stem_yinyang_and_sex",
            detail={"missing": missing},
        )

    return _TRADITIONAL[(polarity, sex)]


def resolve_direction_for_request(request: dict, year_pillar) -> str:
    """Resolve Da-Yun flow direction from a /calculate/bazi/dayun request payload."""
    method = request.get("direction_method")
    if method == "explicit":
        return resolve_direction({
            "direction_method": "explicit",
            "flow_direction": request.get("flow_direction"),
        })
    if method == "year_stem_yinyang_and_sex":
        if year_pillar is None:
            raise DirectionBasisMissingError(
                "direction_basis_missing: year_pillar required for year_stem_yinyang_and_sex mode",
                detail={"missing": ["year_pillar"]},
            )
        polarity = "yang" if year_pillar.stem_index % 2 == 0 else "yin"
        return resolve_direction({
            "direction_method": "year_stem_yinyang_and_sex",
            "year_stem_polarity": polarity,
            "sex_at_birth": request.get("sex_at_birth"),
        })
    return resolve_direction(request)
