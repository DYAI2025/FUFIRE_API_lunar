import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from jsonschema import Draft7Validator

from bazi_engine.app import app
from bazi_engine.bafe import validate_request as validate_request_core
from bazi_engine.bafe.kernel import soft_branch_weights
from bazi_engine.bafe.mapping import (
    branch_index_shift_boundaries,
    branch_index_shift_longitudes,
    branch_index_shift_longitudes_misused,
    hour_branch_index_from_tlst,
    shift_longitudes_equivalence_ok,
)
from bazi_engine.bafe.ruleset_loader import branch_order, hidden_stems_for_branch, load_ruleset

ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "spec"
TV_MATRIX = json.loads((SPEC / "tests" / "tv_matrix.json").read_text(encoding="utf-8"))
REQ_SCHEMA = json.loads((SPEC / "schemas" / "ValidateRequest.schema.json").read_text(encoding="utf-8"))
RESP_SCHEMA = json.loads((SPEC / "schemas" / "ValidateResponse.schema.json").read_text(encoding="utf-8"))

REQ_VALIDATOR = Draft7Validator(REQ_SCHEMA)
RESP_VALIDATOR = Draft7Validator(RESP_SCHEMA)

RULESET = load_ruleset("standard_bazi_2026")
BRANCH_ORDER = branch_order(RULESET)

def _branch_name(idx: int) -> str:
    return BRANCH_ORDER[idx % 12]

def _base_validate_payload():
    return {
        "validate_level": "FULL",
        "now_utc_override": "2026-01-01T00:00:00Z",
        "engine_config": {
            "engine_version": "1.0.0-rc0",
            "parameter_set_id": "standard",
            "deterministic": True,
            "compliance_mode": "RELAXED",
            "bazi_ruleset_id": "standard_bazi_2026",
            "refdata": {
                "refdata_pack_id": "refpack-test-001",
                "refdata_mode": "BUNDLED_OFFLINE",
                "allow_network": False,
                "refdata_root_path": None,
                "ephemeris_id": "swisseph-2026",
                "tzdb_version_id": "tzdb-2026a",
                "leaps_source_id": "leaps-iers",
                "eop_source_id": None,
                "verification_policy": {
                    "tzdb_gpg_required": False,
                    "ephemeris_hash_required": False,
                    "leaps_expiry_enforced": False,
                    "eop_redundancy_required": False,
                },
            },
        },
    }

def test_TV1_branch_boundary_half_open():
    tv = TV_MATRIX["TV1"]
    cfg = tv["engine_config_overrides"]
    for case in tv["cases"]:
        idx = branch_index_shift_boundaries(
            case["lambda_deg"],
            zi_apex_deg=cfg["zi_apex_deg"],
            branch_width_deg=cfg["branch_width_deg"],
        )
        assert idx == case["expected_branch_index"]
        assert _branch_name(idx) == case["expected_branch"]

def test_TV2_convention_equivalence_k1_eq_k2():
    tv = TV_MATRIX["TV2"]
    for case in tv["cases"]:
        lam = case["lambda_deg"]
        k1 = branch_index_shift_boundaries(lam, zi_apex_deg=270.0, branch_width_deg=30.0)
        k2 = branch_index_shift_longitudes(lam, zi_apex_deg=270.0, branch_width_deg=30.0, phi_apex_offset_deg=15.0)
        assert k1 == k2

def test_TV3_forbidden_mixing_detector_shift_longitudes():
    # Correct impl must pass equivalence check; misused impl must fail.
    assert shift_longitudes_equivalence_ok(
        branch_index_shift_longitudes,
        zi_apex_deg=270.0,
        branch_width_deg=30.0,
        phi_apex_offset_deg=15.0,
    )
    assert not shift_longitudes_equivalence_ok(
        branch_index_shift_longitudes_misused,
        zi_apex_deg=270.0,
        branch_width_deg=30.0,
        phi_apex_offset_deg=15.0,
    )

def test_TV4_tlst_hour_boundary_rule():
    tv = TV_MATRIX["TV4"]
    for case in tv["cases"]:
        idx = hour_branch_index_from_tlst(case["tlst_hours"])
        assert idx == case["expected_branch_index"]
        assert _branch_name(idx) == case["expected_branch"]

def test_TV5_soft_kernel_symmetry_and_normalization():
    tv = TV_MATRIX["TV5"]
    lam = tv["cases"][0]["lambda_deg"]
    symmetry = tv["cases"][0]["symmetry_branches"]
    weights = soft_branch_weights(
        lam,
        kernel=tv["kernel"],
        zi_apex_deg=270.0,
        branch_width_deg=30.0,
    )
    assert len(weights) == 12
    assert pytest.approx(sum(weights), rel=0, abs=1e-12) == 1.0
    assert all(w >= 0.0 for w in weights)
    a, b = symmetry
    assert pytest.approx(weights[a], rel=0, abs=1e-12) == weights[b]

def test_TV6_hidden_stems_mapping_correctness():
    tv = TV_MATRIX["TV6"]
    for case in tv["cases"]:
        stems = hidden_stems_for_branch(RULESET, case["branch"])
        assert stems == case["expected_hidden_stems"]

@pytest.mark.parametrize("scenario,expected_code", [
    ("offline_allow_network_true", "REFDATA_NETWORK_FORBIDDEN"),
    ("offline_missing_manifest", "REFDATA_MANIFEST_MISSING"),
    ("leaps_expired_strict", "LEAP_SECONDS_FILE_EXPIRED"),
    ("tzdb_signature_invalid", "TZDB_SIGNATURE_INVALID"),
    ("ephemeris_missing", "EPHEMERIS_MISSING"),
    ("ephemeris_hash_mismatch", "EPHEMERIS_HASH_MISMATCH"),
])
def test_TV7_refdata_policy_checks_via_validate_core(scenario, expected_code):
    payload = _base_validate_payload()

    if scenario == "offline_allow_network_true":
        payload["engine_config"]["refdata"]["allow_network"] = True
        payload["refdata_manifest_inline"] = {"pack_id": "refpack-test-001", "artifacts": []}

    if scenario == "offline_missing_manifest":
        payload["engine_config"]["refdata"]["allow_network"] = False
        payload.pop("refdata_manifest_inline", None)

    if scenario == "leaps_expired_strict":
        payload["engine_config"]["refdata"]["verification_policy"]["leaps_expiry_enforced"] = True
        payload["refdata_manifest_inline"] = {
            "pack_id": "refpack-test-001",
            "artifacts": [
                {"logical_id": "leaps", "present": True, "expires_utc": "2020-01-01T00:00:00Z"},
                {"logical_id": "ephemeris", "present": True},
                {"logical_id": "tzdb", "present": True, "signature_ok": True},
            ]
        }

    if scenario == "tzdb_signature_invalid":
        payload["engine_config"]["refdata"]["verification_policy"]["tzdb_gpg_required"] = True
        payload["refdata_manifest_inline"] = {
            "pack_id": "refpack-test-001",
            "artifacts": [
                {"logical_id": "tzdb", "present": True, "signature_ok": False},
                {"logical_id": "ephemeris", "present": True},
                {"logical_id": "leaps", "present": True, "expires_utc": "2099-01-01T00:00:00Z"},
            ]
        }

    if scenario == "ephemeris_missing":
        payload["engine_config"]["refdata"]["verification_policy"]["ephemeris_hash_required"] = True
        payload["refdata_manifest_inline"] = {
            "pack_id": "refpack-test-001",
            "artifacts": [
                {"logical_id": "ephemeris", "present": False, "hash_sha256": "deadbeef"},
                {"logical_id": "tzdb", "present": True, "signature_ok": True},
                {"logical_id": "leaps", "present": True, "expires_utc": "2099-01-01T00:00:00Z"},
            ]
        }

    if scenario == "ephemeris_hash_mismatch":
        payload["engine_config"]["refdata"]["verification_policy"]["ephemeris_hash_required"] = True
        # present=true but no verifiable hash/file -> treated as mismatch
        payload["refdata_manifest_inline"] = {
            "pack_id": "refpack-test-001",
            "artifacts": [
                {"logical_id": "ephemeris", "present": True, "hash_sha256": "MISSING"},
                {"logical_id": "tzdb", "present": True, "signature_ok": True},
                {"logical_id": "leaps", "present": True, "expires_utc": "2099-01-01T00:00:00Z"},
            ]
        }

    # Sanity: request must be schema-valid
    assert not list(REQ_VALIDATOR.iter_errors(payload))

    resp = validate_request_core(payload)

    # Response must be schema-valid
    assert not list(RESP_VALIDATOR.iter_errors(resp))

    codes = [e["code"] for e in resp["errors"]]
    assert expected_code in codes


def test_missing_tt_in_strict_mode_when_required_by_ruleset():
    payload = _base_validate_payload()
    payload["engine_config"]["compliance_mode"] = "STRICT"
    payload["refdata_manifest_inline"] = {"pack_id": "refpack-test-001", "artifacts": []}
    # No positions_override => TT missing
    resp = validate_request_core(payload)
    codes = [e["code"] for e in resp["errors"]]
    assert "MISSING_TT" in codes
def test_validate_endpoint_smoke_schema_valid():
    client = TestClient(app)
    payload = _base_validate_payload()
    payload["refdata_manifest_inline"] = {"pack_id": "refpack-test-001", "artifacts": []}
    r = client.post("/validate", json=payload)
    assert r.status_code == 200
    data = r.json()
    assert not list(RESP_VALIDATOR.iter_errors(data))
