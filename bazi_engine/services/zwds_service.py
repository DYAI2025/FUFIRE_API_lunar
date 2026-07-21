"""ZWDS-P1-20/21 — thin HTTP-orchestration seam for the ZWDS engine.

Sits at the HTTP composition seam like the other ``services/*`` modules: the
router turns a validated request dict into a full ``ZwdsRawResponse`` via
:func:`calculate`, and reads immutable ruleset metadata via
:func:`ruleset_metadata`.

All astronomy / graph work lives in :mod:`bazi_engine.zwds.engine`; this module
only supplies the two per-request non-deterministic response fields (the
correlation ``request_id`` and the real UTC ``generated_at`` timestamp) so the
deterministic engine stays pure and injectable, and projects the frozen
:class:`~bazi_engine.zwds.ruleset_repository.RulesetRef` into a metadata dict
with the core-seed governance markers.
"""

from __future__ import annotations

import uuid
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any, Dict

from ..zwds.engine import compute_zwds_raw
from ..zwds.ruleset_repository import load_ruleset

#: Release maturity of the shipped ZWDS ruleset(s). The core-seed engine is
#: deterministic, but its source tables are not practitioner-reviewed, so every
#: metadata read advertises that a human domain review is still required.
_RELEASE_STATUS = "core-seed"


def _utc_now_z() -> str:
    """Return the current UTC time as an RFC-3339 ``...Z`` timestamp."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def calculate(request: Dict[str, Any]) -> Dict[str, Any]:
    """Compute a full ``ZwdsRawResponse`` dict for a validated request dict.

    ``request_id`` and ``generated_at`` are supplied here (not by the caller)
    so the deterministic engine remains pure: the engine takes both as
    injectable parameters and this seam owns the two response fields that must
    differ per request.
    """
    request_id = f"req_zwds_{uuid.uuid4().hex}"
    return compute_zwds_raw(
        request,
        request_id=request_id,
        generated_at=_utc_now_z(),
    )


def ruleset_metadata(ruleset_id: str) -> Dict[str, Any]:
    """Return the immutable ruleset envelope plus core-seed release markers.

    Loads (and hash-verifies) the ruleset via
    :func:`~bazi_engine.zwds.ruleset_repository.load_ruleset`, which raises
    :class:`~bazi_engine.zwds.errors.ZwdsRulesetNotFoundError` for an unknown
    id. The returned dict is the frozen ``RulesetRef`` — every policy id, the
    five sha256 fingerprints and ``source_status`` — with two governance
    markers appended: ``release_status`` (``"core-seed"``) and
    ``human_review_required`` (``True``).
    """
    ref = load_ruleset(ruleset_id)
    data: Dict[str, Any] = asdict(ref)
    data["release_status"] = _RELEASE_STATUS
    data["human_review_required"] = True
    return data
