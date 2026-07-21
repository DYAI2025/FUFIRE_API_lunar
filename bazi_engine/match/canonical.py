"""match/canonical.py — REQ-014: order-independent canonical hash.

Level 4 (plan §4.1, docs/plans/2026-07-02-bazi-hehun.md). Deliberately
stdlib-only — it imports NOTHING from ``bazi_engine`` (and therefore never
``routers/*``, ``app``, ``limiter`` or ``services/*``), so the module
hierarchy holds trivially and no Level-5 carve-out is widened (plan §4.4:
a small ``json.dumps(sort_keys=True)`` + ``sha256`` helper in ``match/``
rather than importing ``bafe.canonical_json``).

Binding contract anchors (docs/testing/bazi-hehun.acceptance-tests.md):
- AC-014a (T-014-01): the canonicalization is INDEPENDENT of JSON object
  key order — two semantically identical documents hash equal, and any
  changed value changes the hash. Realized via ``sort_keys=True``, so key
  order in the input is irrelevant while every value is significant.
- AC-014b (T-014-02/03): the FULL engine output (frozen dataclasses,
  enums, tuples) projects to a deterministic JSON-plain structure and
  serializes byte-stably, so identical inputs yield identical bytes and an
  identical digest WITHIN an ephemeris mode.
- D1/REQ-007: nothing here computes or names a score — it is a pure
  serializer/hasher over whatever structure it is handed.

Determinism guarantees (same discipline as ``bafe/canonical_json.py``):
sorted keys, no insignificant whitespace, non-ASCII preserved verbatim,
and non-finite floats (``NaN``/``Infinity``) rejected — they are neither
order-stable nor valid JSON, so they must fail loudly rather than corrupt
a digest.
"""
from __future__ import annotations

import dataclasses
import hashlib
import json
import math
from enum import Enum
from typing import Any

__all__ = [
    "canonical_dumps",
    "canonical_hash",
    "to_jsonable",
]


def to_jsonable(obj: Any) -> Any:
    """Project ``obj`` into a deterministic JSON-plain structure.

    Recursively converts the engine's value vocabulary:

    * :class:`enum.Enum` → its ``value`` (e.g. ``SourceStatus`` → ``str``),
    * frozen dataclass instance → ``dict`` keyed by field name,
    * ``dict`` → ``dict`` with stringified keys,
    * ``tuple`` / ``list`` → ``list`` (order preserved — arrays are
      order-significant, unlike object keys),
    * ``bool`` / ``int`` / ``str`` / ``None`` → passed through,
    * ``float`` → passed through only when finite.

    Args:
        obj: Any engine value — a plain JSON document or a tree of frozen
            dataclasses/enums/tuples (the full pre-HTTP engine output).

    Returns:
        A structure built only from ``dict``/``list``/``str``/``int``/
        ``float``/``bool``/``None``.

    Raises:
        ValueError: If a ``float`` is ``NaN`` or infinite — non-finite
            values are not canonicalizable (they break byte-stability and
            are invalid JSON).
        TypeError: If ``obj`` contains a type with no canonical projection.
    """
    if isinstance(obj, Enum):
        return to_jsonable(obj.value)
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return {
            f.name: to_jsonable(getattr(obj, f.name))
            for f in dataclasses.fields(obj)
        }
    if isinstance(obj, dict):
        return {str(k): to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [to_jsonable(v) for v in obj]
    # bool is a subclass of int — keep it before the int/float branches so
    # it serializes as ``true``/``false``, not ``1``/``0``.
    if isinstance(obj, bool) or obj is None or isinstance(obj, (int, str)):
        return obj
    if isinstance(obj, float):
        if not math.isfinite(obj):
            raise ValueError(
                f"non-finite float {obj!r} cannot be canonicalized"
            )
        return obj
    raise TypeError(
        f"cannot canonicalize value of type {type(obj).__name__!r}"
    )


def canonical_dumps(obj: Any) -> str:
    """Serialize ``obj`` to its canonical, order-independent JSON string.

    Object key order in the input is irrelevant (``sort_keys=True``);
    array order is preserved; whitespace is stripped; non-ASCII is kept
    verbatim; ``NaN``/``Infinity`` are rejected (``allow_nan=False`` plus
    the finiteness guard in :func:`to_jsonable`).
    """
    return json.dumps(
        to_jsonable(obj),
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
        allow_nan=False,
    )


def canonical_hash(obj: Any) -> str:
    """Return the SHA-256 hex digest of ``canonical_dumps(obj)`` (AC-014a).

    Two semantically identical documents (any key order) share a digest;
    any changed value changes it. The digest is recomputable from the
    serialized body via ``canonical_dumps`` + ``hashlib.sha256``.
    """
    return hashlib.sha256(canonical_dumps(obj).encode("utf-8")).hexdigest()
