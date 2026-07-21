from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from jsonschema import Draft7Validator

from .canonical_json import config_fingerprint as compute_fingerprint
from .errors import make_issue
from .mapping import (
    branch_index_shift_boundaries,
    branch_index_shift_longitudes,
    nearest_boundary_distance_deg,
    nearest_hour_boundary_distance_minutes,
)
from .refdata import evaluate_refdata
from .ruleset_loader import day_cycle_anchor_status, load_ruleset, ruleset_version
from .time_model import evaluate_time


def _repo_root_from_here() -> Path:
    here = Path(__file__).resolve()
    return here.parents[2]

def _load_schema(name: str) -> Dict[str, Any]:
    path = _repo_root_from_here() / "spec" / "schemas" / name
    return json.loads(path.read_text(encoding="utf-8"))

_VALIDATE_REQUEST_SCHEMA = _load_schema("ValidateRequest.schema.json")
_VALIDATE_RESPONSE_SCHEMA = _load_schema("ValidateResponse.schema.json")

_REQ_VALIDATOR = Draft7Validator(_VALIDATE_REQUEST_SCHEMA)
_RESP_VALIDATOR = Draft7Validator(_VALIDATE_RESPONSE_SCHEMA)

def _now_utc(now_override: Optional[str]) -> datetime:
    if now_override:
        s = str(now_override).replace("Z", "+00:00")
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    return datetime.now(timezone.utc)

def _apply_defaults_engine_config(engine_config: Dict[str, Any]) -> Dict[str, Any]:
    cfg = dict(engine_config)
    cfg.setdefault("compliance_mode", "RELAXED")
    cfg.setdefault("epoch_id", "ofDate")
    cfg.setdefault("zodiac_mode", "tropical")
    cfg.setdefault("time_standard", "CIVIL")
    cfg.setdefault("dst_policy", "error")
    cfg.setdefault("interval_convention", "HALF_OPEN")
    cfg.setdefault("branch_coordinate_convention", "SHIFT_BOUNDARIES")
    cfg.setdefault("phi_apex_offset_deg", 15.0)
    cfg.setdefault("zi_apex_deg", 270.0)
    cfg.setdefault("branch_width_deg", 30.0)
    cfg.setdefault("month_boundary_mode", "JIEQI_CROSSING")
    cfg.setdefault("month_start_solar_longitude_deg", 315.0)
    # Canonicalization policies
    cfg.setdefault("json_canonicalization", {"sorted_keys": True, "utf8": True})
    cfg.setdefault("float_format_policy", {"mode": "shortest_roundtrip", "fixed_decimals": None})
    return cfg

def _issue_list_sorted(issues: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    # Deterministic ordering for CI stability
    return sorted(issues, key=lambda x: (x.get("code",""), x.get("severity",""), x.get("path") or "", x.get("message","")))

def validate_request(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Contract-first validator. Raises ValueError on invalid request schema.
    Returns ValidateResponse dict (guaranteed schema-valid by self-check).
    """
    errs = list(_REQ_VALIDATOR.iter_errors(payload))
    if errs:
        # Prefer deterministic first error message
        e = sorted(errs, key=lambda x: x.path)[0]
        raise ValueError(f"ValidateRequest schema violation: {e.message}")

    validate_level = str(payload.get("validate_level", "BASIC")).upper()
    now_utc = _now_utc(payload.get("now_utc_override"))

    engine_config_in = payload["engine_config"]
    engine_config = _apply_defaults_engine_config(engine_config_in)
    compliance_mode = str(engine_config.get("compliance_mode", "RELAXED")).upper()

    ruleset_id = str(engine_config.get("bazi_ruleset_id"))
    try:
        ruleset = load_ruleset(ruleset_id)
    except FileNotFoundError as e:
        raise ValueError(str(e))
    except Exception as e:
        raise ValueError(f"Failed to load ruleset: {type(e).__name__}")
    r_version = ruleset_version(ruleset)

    errors: List[Dict[str, Any]] = []
    warnings: List[Dict[str, Any]] = []

    # --- RefData ---
    refdata_manifest = payload.get("refdata_manifest_inline", None)
    ref_errors, ref_warnings, ref_evd, ref_comp = evaluate_refdata(
        engine_refdata=engine_config["refdata"],
        refdata_manifest=refdata_manifest,
        now_utc=now_utc,
    )
    errors.extend(ref_errors)
    warnings.extend(ref_warnings)

    # --- Time ---
    time_errors, time_warnings, time_evd, time_comp, tlst_hours = evaluate_time(
        engine_config=engine_config,
        birth_event=payload.get("birth_event", None),
        positions_override=payload.get("positions_override", None),
        compliance_mode=compliance_mode,
        now_utc=now_utc,
    )
    errors.extend(time_errors)
    warnings.extend(time_warnings)

    # STRICT TT requirement (ruleset-bound): year/month boundaries in standard_bazi_2026 use TT.
    if validate_level == "FULL" and compliance_mode == "STRICT":
        y_ts = str((ruleset.get("year_boundary") or {}).get("time_scale", "")).upper()
        m_ts = str((ruleset.get("month_boundary") or {}).get("time_scale", "")).upper()
        requires_tt = (y_ts == "TT") or (m_ts == "TT")
        if requires_tt and str(time_evd.get("tt_quality", "missing")) != "ok":
            errors.append(make_issue(
                "MISSING_TT",
                "STRICT mode requires TT availability for year/month boundary computations (ruleset time_scale=TT)",
                path="/positions_override/time_scale",
            ))

    # --- Frames ---
    frames_errors: List[Dict[str, Any]] = []
    frames_warnings: List[Dict[str, Any]] = []
    zodiac_mode = str(engine_config.get("zodiac_mode", "tropical")).lower()
    ayanamsa_id = engine_config.get("ayanamsa_id", None)
    if zodiac_mode == "sidereal":
        if not ayanamsa_id or str(ayanamsa_id).upper().startswith("MISSING"):
            frames_errors.append(make_issue(
                "MISSING_AYANAMSA_ID",
                "zodiac_mode=sidereal requires ayanamsa_id",
                path="/engine_config/ayanamsa_id",
            ))
    errors.extend(frames_errors)
    warnings.extend(frames_warnings)

    frames_evd = {
        "epoch_id": engine_config.get("epoch_id", None),
        "precession_model_id": engine_config.get("precession_model_id", None),
        "obliquity_model_id": engine_config.get("obliquity_model_id", None),
        "zodiac_mode": engine_config.get("zodiac_mode", None),
        "ayanamsa_id": engine_config.get("ayanamsa_id", None),
    }
    frames_status = "OK"
    if frames_errors:
        frames_status = "FAIL"
    elif frames_warnings:
        frames_status = "DEGRADED"
    frames_comp = {"status": frames_status, "notes": []}

    # --- Ephemeris evidence (override-only here) ---
    positions_override = payload.get("positions_override", None)
    eph_evd = None
    eph_status = "DEGRADED"
    if isinstance(positions_override, dict):
        eph_status = "OK"
        eph_evd = {
            "ephemeris_id": engine_config["refdata"].get("ephemeris_id", None),
            "time_scale": str(positions_override.get("time_scale", None)).upper() if positions_override.get("time_scale") is not None else None,
            "bodies": sorted(list((positions_override.get("bodies") or {}).keys())),
        }
    else:
        eph_evd = {
            "ephemeris_id": engine_config["refdata"].get("ephemeris_id", None),
            "time_scale": None,
            "bodies": [],
        }
    eph_comp = {"status": eph_status, "notes": ["positions_override_only=true"]}

    # --- Discretization ---
    interval_convention = str(engine_config.get("interval_convention", "HALF_OPEN")).upper()
    branch_conv = str(engine_config.get("branch_coordinate_convention", "SHIFT_BOUNDARIES")).upper()
    zi_apex_deg = float(engine_config.get("zi_apex_deg", 270.0))
    branch_width_deg = float(engine_config.get("branch_width_deg", 30.0))
    phi = float(engine_config.get("phi_apex_offset_deg", 15.0))

    disc_errors: List[Dict[str, Any]] = []

    # SHIFT_LONGITUDES equivalence self-check (detect wrong origin handling)
    if branch_conv == "SHIFT_LONGITUDES":
        for lam in [0.0, 14.999, 15.0, 123.456, 284.999, 285.0, 359.999]:
            k1 = branch_index_shift_boundaries(lam, zi_apex_deg=zi_apex_deg, branch_width_deg=branch_width_deg)
            k2 = branch_index_shift_longitudes(lam, zi_apex_deg=zi_apex_deg, branch_width_deg=branch_width_deg, phi_apex_offset_deg=phi)
            if k1 != k2:
                disc_errors.append(make_issue(
                    "INCONSISTENT_BRANCH_ORIGIN_FOR_SHIFTED_LONGITUDES",
                    "SHIFT_LONGITUDES mapping is inconsistent with canonical origin (K1 != K2)",
                    path="/engine_config/branch_coordinate_convention",
                    details={"lambda_deg": lam, "k1": k1, "k2": k2},
                ))
                break

    # Anchor gating (ruleset)
    anchor_jdn, anchor_verification = day_cycle_anchor_status(ruleset)
    if anchor_jdn is None or anchor_verification != "verified":
        if compliance_mode == "STRICT":
            disc_errors.append(make_issue(
                "MISSING_DAY_CYCLE_ANCHOR",
                f"Day-cycle anchor not verified (anchor_verification={anchor_verification}); STRICT mode gates computation",
                path="/ruleset/day_cycle_anchor",
            ))
        else:
            warnings.append(make_issue(
                "MISSING_DAY_CYCLE_ANCHOR",
                f"Day-cycle anchor not verified (anchor_verification={anchor_verification}); RELAXED/DEV mode allows degraded operation",
                severity="WARNING",
                path="/ruleset/day_cycle_anchor",
            ))

    errors.extend(disc_errors)

    # boundary distance evidence: derive from Sun lambda if provided, else from TLST hour boundary
    boundary_distance_deg = None
    classification_unstable = None

    if isinstance(positions_override, dict):
        bodies = positions_override.get("bodies") or {}
        if isinstance(bodies, dict) and "Sun" in bodies and isinstance(bodies["Sun"], dict):
            lam_raw = bodies["Sun"].get("lambda_deg")
            lam = float(lam_raw) if lam_raw is not None else 0.0
            boundary_distance_deg = float(nearest_boundary_distance_deg(lam, zi_apex_deg=zi_apex_deg, branch_width_deg=branch_width_deg))
            classification_unstable = boundary_distance_deg < 0.1
    if boundary_distance_deg is None and tlst_hours is not None:
        # Convert minutes to degrees (15deg/hour = 0.25deg/min)
        dist_min = nearest_hour_boundary_distance_minutes(float(tlst_hours))
        boundary_distance_deg = float(dist_min * 0.25)
        classification_unstable = dist_min < 1.0

    disc_evd = {
        "interval_convention": "HALF_OPEN" if interval_convention != "HALF_OPEN" else "HALF_OPEN",
        "branch_coordinate_convention": branch_conv if branch_conv in {"SHIFT_BOUNDARIES","SHIFT_LONGITUDES"} else "SHIFT_BOUNDARIES",
        "boundary_distance_deg": boundary_distance_deg,
        "classification_unstable": classification_unstable,
    }
    disc_status = "OK"
    if disc_errors:
        disc_status = "FAIL"
    disc_comp = {"status": disc_status, "notes": []}

    # --- Reproducibility ---
    repro_errors: List[Dict[str, Any]] = []
    repro_warnings: List[Dict[str, Any]] = []
    fp = compute_fingerprint(
        engine_config,
        ruleset_id=ruleset_id,
        ruleset_version=r_version,
        refdata_pack_id=str(engine_config["refdata"].get("refdata_pack_id")),
        float_format_policy=engine_config.get("float_format_policy") or {},
        json_canonicalization=engine_config.get("json_canonicalization") or {},
    )
    repro_evd = {
        "config_fingerprint": fp,
        "float_format_policy": engine_config.get("float_format_policy") or {},
        "json_canonicalization": engine_config.get("json_canonicalization") or {},
    }
    repro_status = "OK"
    if repro_errors:
        repro_status = "FAIL"
    elif repro_warnings:
        repro_status = "DEGRADED"
    repro_comp = {"status": repro_status, "notes": []}

    # --- Interpretation Policy ---
    interp_comp = {"status": "OK", "notes": ["interpretation_layer=not_executed_in_validate"]}
    interp_evd = {"lint_status": None, "statements_returned": None}

    # Compose compliance components
    comp = {
        "REFDATA": ref_comp,
        "TIME": time_comp,
        "FRAMES": frames_comp,
        "EPHEMERIS": eph_comp,
        "DISCRETIZATION": disc_comp,
        "REPRODUCIBILITY": repro_comp,
        "INTERPRETATION_POLICY": interp_comp,
    }

    # Determine overall compliance
    any_fail = any(c.get("status") == "FAIL" for c in comp.values())
    any_degraded = any(c.get("status") == "DEGRADED" for c in comp.values())
    if errors or any_fail:
        compliance_status = "NON_COMPLIANT"
    elif warnings or any_degraded:
        compliance_status = "DEGRADED"
    else:
        compliance_status = "COMPLIANT"

    resp: Dict[str, Any] = {
        "compliance_status": compliance_status,
        "compliance_components": comp,
        "errors": _issue_list_sorted([i for i in errors if i.get("severity","ERROR") == "ERROR"]),
        "warnings": _issue_list_sorted([i for i in warnings if i.get("severity","WARNING") == "WARNING"]),
        "evidence": {
            "refdata": ref_evd,
            "time": time_evd,
            "frames": frames_evd,
            "ephemeris": eph_evd,
            "discretization": disc_evd,
            "reproducibility": repro_evd,
            "interpretation": interp_evd,
        },
    }

    # Self-check: response must validate against contract schema.
    resp_errs = list(_RESP_VALIDATOR.iter_errors(resp))
    if resp_errs:
        first_err = sorted(resp_errs, key=lambda x: x.path)[0]
        raise RuntimeError(f"ValidateResponse schema violation (BUG): {first_err.message} at {list(first_err.path)}")

    return resp
