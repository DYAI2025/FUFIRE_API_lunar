"""Release-gated feature decisions with safe, explicit defaults."""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache

from fastapi import HTTPException


def _truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class FeatureDecision:
    feature_id: str
    env_var: str
    default_enabled: bool
    owner: str
    release_status: str


FEATURE_MATRIX: dict[str, FeatureDecision] = {
    "key_issuance": FeatureDecision(
        feature_id="key_issuance",
        env_var="FUFIRE_ENABLE_KEY_ISSUANCE",
        default_enabled=False,
        owner="Identity/BFF",
        release_status="disabled-engine-plane-retired",
    ),
    "zwds": FeatureDecision(
        feature_id="zwds",
        env_var="FUFIRE_ENABLE_ZWDS",
        default_enabled=False,
        owner="ZWDS domain owner",
        release_status="gated-pending-practitioner-signoff",
    ),
}


def feature_enabled(feature_id: str) -> bool:
    """Resolve a feature flag on every request; no cached rollout state."""

    try:
        decision = FEATURE_MATRIX[feature_id]
    except KeyError as exc:
        raise ValueError(f"unknown feature decision: {feature_id!r}") from exc
    raw = os.getenv(decision.env_var)
    return decision.default_enabled if raw is None else _truthy(raw)


@lru_cache(maxsize=None)
def feature_dependency(feature_id: str):
    """Return a FastAPI dependency that hides a disabled conditional surface."""

    if feature_id not in FEATURE_MATRIX:
        raise ValueError(f"unknown feature decision: {feature_id!r}")

    def _require_feature() -> None:
        if not feature_enabled(feature_id):
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "feature_disabled",
                    "message": "This API capability is not enabled.",
                    "detail": {"feature": feature_id},
                },
            )

    _require_feature.__name__ = f"require_{feature_id}"
    return _require_feature
