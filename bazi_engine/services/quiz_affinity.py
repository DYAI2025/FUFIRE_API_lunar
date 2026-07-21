"""Canonical quiz keyword → sector weight resolver."""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import List

logger = logging.getLogger(__name__)

_MAP_PATH = Path(__file__).parent.parent / "data" / "affinity_map.json"

try:
    _MAP = json.loads(_MAP_PATH.read_text(encoding="utf-8"))
except (FileNotFoundError, json.JSONDecodeError, OSError) as exc:
    logger.error("Failed to load affinity_map.json: %s", exc)
    _MAP = {"keywords": {}, "tags": {}}


def resolve_quiz_sectors(keyword: str) -> List[float]:
    """Return 12-sector weights for a quiz keyword. Falls back to uniform."""
    weights = _MAP["keywords"].get(keyword) or _MAP["tags"].get(keyword)
    if weights:
        return weights
    logger.warning("Unknown quiz keyword: %r — using uniform fallback", keyword)
    return [1 / 12] * 12  # uniform fallback
