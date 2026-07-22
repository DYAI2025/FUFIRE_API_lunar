"""Canonical quiz keyword → sector weight resolver."""
from __future__ import annotations

import logging
from typing import List

from bazi_engine.resource_loader import (
    PackageResourceIntegrityError,
    load_json_object_resource,
)

logger = logging.getLogger(__name__)

_MAP = load_json_object_resource("bazi_engine.data", "affinity_map.json")
if not isinstance(_MAP.get("keywords"), dict) or not isinstance(
    _MAP.get("tags"), dict
):
    raise PackageResourceIntegrityError(
        "required package resource has an invalid affinity-map shape: "
        "bazi_engine.data:affinity_map.json"
    )


def resolve_quiz_sectors(keyword: str) -> List[float]:
    """Return 12-sector weights for a quiz keyword. Falls back to uniform."""
    weights = _MAP["keywords"].get(keyword) or _MAP["tags"].get(keyword)
    if weights:
        return weights
    logger.warning("Unknown quiz keyword: %r — using uniform fallback", keyword)
    return [1 / 12] * 12  # uniform fallback
