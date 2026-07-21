from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .errors import make_issue


def _parse_dt(dt_str: str) -> Optional[datetime]:
    try:
        # Accept Z suffix
        s = dt_str.replace("Z", "+00:00")
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None

def _sha256_file(path: Path) -> str:
    import hashlib
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def _artifact_from_manifest(manifest: Dict[str, Any], logical_id: str) -> Optional[Dict[str, Any]]:
    arts = manifest.get("artifacts")
    if isinstance(arts, list):
        for a in arts:
            if isinstance(a, dict) and a.get("logical_id") == logical_id:
                return a
    # Some manifests might use dict mapping
    if isinstance(arts, dict):
        a = arts.get(logical_id)
        if isinstance(a, dict):
            return a
    return None

def _artifact_evidence(logical_id: str, *, present: bool, verified: Optional[bool] = None, hash_sha256: Optional[str] = None,
                       signature_ok: Optional[bool] = None, expires_utc: Optional[str] = None, stale: Optional[bool] = None,
                       notes: Optional[List[str]] = None) -> Dict[str, Any]:
    return {
        "logical_id": logical_id,
        "present": bool(present),
        "verified": verified,
        "hash_sha256": hash_sha256,
        "signature_ok": signature_ok,
        "expires_utc": expires_utc,
        "stale": stale,
        "notes": notes or [],
    }

def evaluate_refdata(
    *,
    engine_refdata: Dict[str, Any],
    refdata_manifest: Optional[Dict[str, Any]],
    now_utc: datetime,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], Dict[str, Any], Dict[str, Any]]:
    """
    Returns (errors, warnings, refdata_evidence, component_status)
    """
    errors: List[Dict[str, Any]] = []
    warnings: List[Dict[str, Any]] = []

    mode = str(engine_refdata.get("refdata_mode"))
    allow_network = bool(engine_refdata.get("allow_network", False))
    pack_id = str(engine_refdata.get("refdata_pack_id", "MISSING"))
    root_path = engine_refdata.get("refdata_root_path", None)
    verification_policy = engine_refdata.get("verification_policy", {}) or {}

    # Network guard
    if mode in {"BUNDLED_OFFLINE", "LOCAL_MIRROR"} and allow_network:
        errors.append(make_issue(
            "REFDATA_NETWORK_FORBIDDEN",
            f"refdata_mode={mode} forbids allow_network=true",
            path="/engine_config/refdata/allow_network",
        ))

    # Manifest requirement for offline modes
    if mode in {"BUNDLED_OFFLINE", "LOCAL_MIRROR"} and not refdata_manifest:
        errors.append(make_issue(
            "REFDATA_MANIFEST_MISSING",
            f"refdata_mode={mode} requires a refdata manifest (inline or on disk)",
            path="/refdata_manifest_inline",
        ))

    # Build artifacts evidence (default: missing)
    artifacts_evd: Dict[str, Any] = {}
    for logical_id in ["ephemeris", "tzdb", "leaps", "eop"]:
        artifacts_evd[logical_id] = _artifact_evidence(logical_id, present=False, verified=None)

    # If we have a manifest, extract artifact info + perform checks
    if refdata_manifest:
        # Optional pack id consistency check
        # No dedicated error code in contract; record as note only.
        m_pack = refdata_manifest.get("pack_id") or refdata_manifest.get("refdata_pack_id")
        pack_mismatch = bool(m_pack) and str(m_pack) != pack_id

        # Determine root path for file hashing (best-effort)
        root = Path(str(root_path)) if root_path else None

        # ephemeris
        ephe = _artifact_from_manifest(refdata_manifest, "ephemeris")
        if ephe:
            artifacts_evd["ephemeris"] = _artifact_evidence(
                "ephemeris",
                present=bool(ephe.get("present", True)),
                verified=ephe.get("verified", None),
                hash_sha256=ephe.get("hash_sha256", None),
                signature_ok=ephe.get("signature_ok", None),
                expires_utc=ephe.get("expires_utc", None),
                stale=ephe.get("stale", None),
                notes=ephe.get("notes", []) if isinstance(ephe.get("notes", []), list) else [],
            )

        # tzdb
        tzdb = _artifact_from_manifest(refdata_manifest, "tzdb")
        if tzdb:
            artifacts_evd["tzdb"] = _artifact_evidence(
                "tzdb",
                present=bool(tzdb.get("present", True)),
                verified=tzdb.get("verified", None),
                hash_sha256=tzdb.get("hash_sha256", None),
                signature_ok=tzdb.get("signature_ok", None),
                expires_utc=tzdb.get("expires_utc", None),
                stale=tzdb.get("stale", None),
                notes=tzdb.get("notes", []) if isinstance(tzdb.get("notes", []), list) else [],
            )

        # leaps
        leaps = _artifact_from_manifest(refdata_manifest, "leaps")
        if leaps:
            artifacts_evd["leaps"] = _artifact_evidence(
                "leaps",
                present=bool(leaps.get("present", True)),
                verified=leaps.get("verified", None),
                hash_sha256=leaps.get("hash_sha256", None),
                signature_ok=leaps.get("signature_ok", None),
                expires_utc=leaps.get("expires_utc", None),
                stale=leaps.get("stale", None),
                notes=leaps.get("notes", []) if isinstance(leaps.get("notes", []), list) else [],
            )

        # eop
        eop = _artifact_from_manifest(refdata_manifest, "eop")
        if eop:
            artifacts_evd["eop"] = _artifact_evidence(
                "eop",
                present=bool(eop.get("present", True)),
                verified=eop.get("verified", None),
                hash_sha256=eop.get("hash_sha256", None),
                signature_ok=eop.get("signature_ok", None),
                expires_utc=eop.get("expires_utc", None),
                stale=eop.get("stale", None),
                notes=eop.get("notes", []) if isinstance(eop.get("notes", []), list) else [],
            )

        # Verification policy checks (best-effort, offline deterministic)
        tzdb_gpg_required = bool(verification_policy.get("tzdb_gpg_required", False))
        ephemeris_hash_required = bool(verification_policy.get("ephemeris_hash_required", False))
        eop_redundancy_required = bool(verification_policy.get("eop_redundancy_required", False))
        leaps_expiry_enforced = bool(verification_policy.get("leaps_expiry_enforced", False))

        # tzdb signature check
        if tzdb_gpg_required:
            sig_ok = artifacts_evd["tzdb"].get("signature_ok", None)
            if sig_ok is not True:
                errors.append(make_issue(
                    "TZDB_SIGNATURE_INVALID",
                    "tzdb_gpg_required=true but tzdb signature_ok is not true",
                    path="/refdata_manifest_inline/artifacts/tzdb/signature_ok",
                ))

        # ephemeris hash check
        if ephemeris_hash_required:
            ephe_present = bool(artifacts_evd["ephemeris"].get("present", False))
            if not ephe_present:
                errors.append(make_issue(
                    "EPHEMERIS_MISSING",
                    "ephemeris_hash_required=true but ephemeris is missing",
                    path="/refdata_manifest_inline/artifacts/ephemeris/present",
                ))
            else:
                declared_hash = artifacts_evd["ephemeris"].get("hash_sha256", None)
                # If we have a root path and a file path, we can verify.
                # Manifest may provide either absolute path or relative path under root.
                file_path = None
                if ephe and isinstance(ephe.get("path"), str):
                    p = Path(ephe["path"])
                    file_path = p if p.is_absolute() else (root / p if root else None)
                if file_path and file_path.exists() and declared_hash and declared_hash not in {"MISSING", ""}:
                    actual = _sha256_file(file_path)
                    if actual != declared_hash:
                        errors.append(make_issue(
                            "EPHEMERIS_HASH_MISMATCH",
                            "ephemeris hash mismatch (sha256)",
                            path="/refdata_manifest_inline/artifacts/ephemeris/hash_sha256",
                            details={"declared": declared_hash, "actual": actual},
                        ))
                    else:
                        artifacts_evd["ephemeris"]["verified"] = True
                else:
                    # Cannot verify => treat as mismatch in STRICT offline policy
                    errors.append(make_issue(
                        "EPHEMERIS_HASH_MISMATCH",
                        "ephemeris_hash_required=true but ephemeris hash could not be verified (missing file or hash)",
                        path="/refdata_manifest_inline/artifacts/ephemeris/hash_sha256",
                    ))

        # leaps expiry check
        if leaps_expiry_enforced:
            expires = artifacts_evd["leaps"].get("expires_utc", None)
            if isinstance(expires, str):
                dt = _parse_dt(expires)
                if dt and dt < now_utc:
                    errors.append(make_issue(
                        "LEAP_SECONDS_FILE_EXPIRED",
                        "leap seconds file expired under leaps_expiry_enforced=true",
                        path="/refdata_manifest_inline/artifacts/leaps/expires_utc",
                        details={"expires_utc": expires, "now_utc": now_utc.isoformat().replace("+00:00","Z")},
                    ))
            else:
                # Missing expiry treated as warning (no dedicated code besides LEAP_SECONDS_FILE_EXPIRED)
                warnings.append(make_issue(
                    "LEAP_SECONDS_FILE_EXPIRED",
                    "leaps_expiry_enforced=true but leaps.expires_utc is missing; cannot enforce deterministically",
                    severity="WARNING",
                    path="/refdata_manifest_inline/artifacts/leaps/expires_utc",
                ))

        # EOP checks (optional)
        if eop_redundancy_required:
            eop_present = bool(artifacts_evd["eop"].get("present", False))
            if not eop_present:
                errors.append(make_issue(
                    "EOP_MISSING",
                    "eop_redundancy_required=true but EOP artifact missing",
                    path="/refdata_manifest_inline/artifacts/eop/present",
                ))
            else:
                if artifacts_evd["eop"].get("stale", None) is True:
                    warnings.append(make_issue(
                        "EOP_STALE",
                        "EOP artifact marked stale",
                        severity="WARNING",
                        path="/refdata_manifest_inline/artifacts/eop/stale",
                    ))

    # Component status
    status = "OK"
    notes: List[str] = []
    if errors:
        status = "FAIL"
    elif warnings:
        status = "DEGRADED"
    # Provide a small deterministic note set
    notes.append(f"mode={mode}")
    notes.append(f"allow_network={allow_network}")
    if refdata_manifest and 'pack_mismatch' in locals() and pack_mismatch:
        notes.append('manifest_pack_id_mismatch=true')
    comp = {"status": status, "notes": notes}

    evidence = {
        "refdata_pack_id": pack_id,
        "allow_network": allow_network,
        "mode": mode,
        "artifacts": {
            "ephemeris": artifacts_evd["ephemeris"],
            "tzdb": artifacts_evd["tzdb"],
            "leaps": artifacts_evd["leaps"],
            "eop": artifacts_evd["eop"],
        },
    }
    return errors, warnings, evidence, comp
