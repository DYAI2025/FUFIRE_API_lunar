"""ZWDS-P1-16 — immutable, hash-locked ruleset repository.

A ZWDS ``ruleset_id`` names an immutable directory of versioned data files under
``bazi_engine/data/zwds/rulesets/<ruleset_id>/``. This module loads that
directory into a frozen :class:`RulesetRef` — the exact ``ruleset`` envelope of
``ZwdsRawResponse`` (schema ``$defs/RulesetRef``) — and makes the ruleset
*hash-locked*: every component file's current sha256 is verified against a
digest recorded in ``manifest.json`` at authoring time. If any component's bytes
have changed, the load fails closed with
:class:`~bazi_engine.zwds.errors.ZwdsRulesetIntegrityFailedError`.

Two immutability guarantees:

* **Component integrity** — ``manifest.json`` carries a ``component_sha256`` map
  (filename -> sha256 of the file's raw bytes). ``manifest.json`` never hashes
  itself, so there is no chicken-and-egg on its own bytes.
* **Effective fingerprint** — ``ruleset_sha256`` is derived at load time from the
  four disclosed component hashes plus the manifest id fields, so it is never
  stored (and so cannot go stale or self-reference).

Import surface: stdlib (``hashlib``, ``json``, ``pathlib``) plus
:mod:`bazi_engine.zwds.errors` only. It never reaches into
``bazi``/``western``/``fusion``/``impact``/routers/``app`` or any zwds sibling
other than ``errors``.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Dict

from bazi_engine.resource_loader import package_resource
from bazi_engine.zwds.errors import (
    ZwdsRulesetIntegrityFailedError,
    ZwdsRulesetNotFoundError,
)

# Root of the versioned package-data tree (bazi_engine/data/zwds/rulesets/).
# The Traversable remains monkeypatchable with a pathlib.Path in integrity
# tests while working for wheel/zip resource readers as well.
RULESETS_DIR = package_resource(
    "bazi_engine.data", "zwds", "rulesets"
)

_MANIFEST_FILENAME = "manifest.json"


# --- Deterministic hashing helpers (local — never import bafe) ---------------


def sha256_of_file(path: Any) -> str:
    """Return the SHA-256 hex digest of ``path``'s raw bytes."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_sha256(obj: Any) -> str:
    """Return a stable SHA-256 hex digest of a JSON-serializable object.

    Uses sorted keys and the compact separators so the digest depends only on
    the logical content, never on key order or incidental whitespace.
    """
    encoded = json.dumps(
        obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class RulesetRef:
    """The immutable effective fingerprint of one ZWDS ruleset.

    Fields are exactly the required properties of ``ZwdsRawResponse``
    ``$defs/RulesetRef`` — all id fields, ``source_status``, ``school_label``,
    the four disclosed component hashes, and the overall ``ruleset_sha256``.
    """

    ruleset_id: str
    ruleset_version: str
    ruleset_sha256: str
    school_label: str | None
    calendar_policy_id: str
    time_policy_id: str
    leap_month_policy_id: str
    year_cycle_policy_id: str
    star_catalog_id: str
    transformation_table_id: str
    age_reckoning_id: str
    source_status: str
    star_catalog_sha256: str
    transformation_table_sha256: str
    calendar_policy_sha256: str
    time_policy_sha256: str


def _load_manifest(ruleset_id: str) -> tuple[Any, Dict[str, Any]]:
    """Locate and parse a ruleset's manifest, or fail with not-found."""
    # Reject anything that is not a single, in-tree path segment so a crafted
    # id can never traverse out of the ruleset root.
    if ruleset_id in ("", ".", "..") or "/" in ruleset_id or "\\" in ruleset_id:
        raise ZwdsRulesetNotFoundError(
            f"unknown ZWDS ruleset id: {ruleset_id!r}",
            detail={"ruleset_id": ruleset_id},
        )
    ruleset_dir = RULESETS_DIR / ruleset_id
    manifest_path = ruleset_dir / _MANIFEST_FILENAME
    if not manifest_path.is_file():
        raise ZwdsRulesetNotFoundError(
            f"unknown ZWDS ruleset id: {ruleset_id!r}",
            detail={"ruleset_id": ruleset_id},
        )
    manifest: Dict[str, Any] = json.loads(manifest_path.read_bytes())
    return ruleset_dir, manifest


def _verify_integrity(ruleset_id: str, ruleset_dir: Any, manifest: Dict[str, Any]) -> None:
    """Verify every recorded component file's bytes against the manifest.

    Raises :class:`ZwdsRulesetIntegrityFailedError` on the first divergence —
    either a component whose bytes changed, or one that has gone missing.
    """
    recorded: Dict[str, str] = manifest["component_sha256"]
    for filename, expected in sorted(recorded.items()):
        component_path = ruleset_dir / filename
        if not component_path.is_file():
            raise ZwdsRulesetIntegrityFailedError(
                f"ZWDS ruleset {ruleset_id!r} component missing: {filename}",
                detail={"ruleset_id": ruleset_id, "component": filename},
            )
        actual = sha256_of_file(component_path)
        if actual != expected:
            raise ZwdsRulesetIntegrityFailedError(
                f"ZWDS ruleset {ruleset_id!r} integrity check failed for "
                f"{filename}",
                detail={
                    "ruleset_id": ruleset_id,
                    "component": filename,
                    "expected_sha256": expected,
                    "actual_sha256": actual,
                },
            )


def load_ruleset(ruleset_id: str) -> RulesetRef:
    """Load an immutable, hash-locked ZWDS ruleset into a :class:`RulesetRef`.

    * Unknown ``ruleset_id`` -> :class:`ZwdsRulesetNotFoundError`.
    * Any component whose bytes diverge from the manifest record ->
      :class:`ZwdsRulesetIntegrityFailedError` (the hash lock).

    The four disclosed component hashes are the sha256 of each component file's
    raw bytes; ``ruleset_sha256`` is :func:`canonical_sha256` over the ordered
    component-hash map plus the manifest id fields.
    """
    ruleset_dir, manifest = _load_manifest(ruleset_id)
    _verify_integrity(ruleset_id, ruleset_dir, manifest)

    components: Dict[str, str] = manifest["components"]
    star_catalog_sha256 = sha256_of_file(ruleset_dir / components["star_catalog"])
    transformation_table_sha256 = sha256_of_file(
        ruleset_dir / components["transformation_table"]
    )
    calendar_policy_sha256 = sha256_of_file(
        ruleset_dir / components["calendar_policy"]
    )
    time_policy_sha256 = sha256_of_file(ruleset_dir / components["time_policy"])

    manifest_ids = {
        "ruleset_id": manifest["ruleset_id"],
        "ruleset_version": manifest["ruleset_version"],
        "school_label": manifest["school_label"],
        "source_status": manifest["source_status"],
        "calendar_policy_id": manifest["calendar_policy_id"],
        "time_policy_id": manifest["time_policy_id"],
        "leap_month_policy_id": manifest["leap_month_policy_id"],
        "year_cycle_policy_id": manifest["year_cycle_policy_id"],
        "star_catalog_id": manifest["star_catalog_id"],
        "transformation_table_id": manifest["transformation_table_id"],
        "age_reckoning_id": manifest["age_reckoning_id"],
    }
    ruleset_sha256 = canonical_sha256(
        {
            "component_sha256": {
                "star_catalog_sha256": star_catalog_sha256,
                "transformation_table_sha256": transformation_table_sha256,
                "calendar_policy_sha256": calendar_policy_sha256,
                "time_policy_sha256": time_policy_sha256,
            },
            "manifest_ids": manifest_ids,
        }
    )

    return RulesetRef(
        ruleset_id=manifest["ruleset_id"],
        ruleset_version=manifest["ruleset_version"],
        ruleset_sha256=ruleset_sha256,
        school_label=manifest["school_label"],
        calendar_policy_id=manifest["calendar_policy_id"],
        time_policy_id=manifest["time_policy_id"],
        leap_month_policy_id=manifest["leap_month_policy_id"],
        year_cycle_policy_id=manifest["year_cycle_policy_id"],
        star_catalog_id=manifest["star_catalog_id"],
        transformation_table_id=manifest["transformation_table_id"],
        age_reckoning_id=manifest["age_reckoning_id"],
        source_status=manifest["source_status"],
        star_catalog_sha256=star_catalog_sha256,
        transformation_table_sha256=transformation_table_sha256,
        calendar_policy_sha256=calendar_policy_sha256,
        time_policy_sha256=time_policy_sha256,
    )
