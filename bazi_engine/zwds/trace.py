"""ZWDS-P1-17 — deterministic chart fingerprint.

A canonical, order-independent SHA-256 over the schema ``chart`` object.

The digest is stable across dict-*key* reordering (the canonical JSON form
sorts keys) but content-sensitive: reordering the ``palaces`` /
``star_placements`` LISTS or mutating any value changes the fingerprint,
because list order is content.

Level: stdlib-only (``hashlib`` + ``json``). Imports no zwds siblings.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any


def canonical_sha256(obj: Any) -> str:
    """Return the SHA-256 hex digest of ``obj`` under a canonical JSON form.

    Canonical form = ``json.dumps`` with sorted keys, no insignificant
    whitespace, and ``ensure_ascii=False`` so the encoded byte stream is a
    deterministic function of the object's *content* — independent of the
    insertion order of any dict key.
    """
    canonical = json.dumps(
        obj,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def chart_fingerprint(chart: dict) -> str:
    """Return the 64-hex canonical fingerprint of a schema ``chart`` object.

    Deterministic and order-independent at the dict-key level; content-sensitive
    at the list level — palace / star-placement order and every value matter.
    """
    return canonical_sha256(chart)
