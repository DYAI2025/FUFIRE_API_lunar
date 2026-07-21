import pytest

from bazi_engine.bafe.canonical_json import config_fingerprint
from bazi_engine.bafe.harmonics import phasor_features
from bazi_engine.bafe.kernel import soft_branch_weights_von_mises
from bazi_engine.bafe.mapping import wrap180, wrap360


def test_PT1_wrap_periodicity_and_ranges():
    values = [-1080.0, -721.234, -360.0, -181.0, -180.0, -179.999, -1.0, 0.0, 1.0, 179.999, 180.0, 359.999, 360.0, 720.0, 1080.0]
    for x in values:
        w = wrap360(x)
        assert 0.0 <= w < 360.0
        w2 = wrap180(x)
        assert -180.0 < w2 <= 180.0
        for n in [-2, -1, 0, 1, 2]:
            assert wrap360(x + 360.0*n) == pytest.approx(w, rel=0, abs=1e-12)
            assert wrap180(x + 360.0*n) == pytest.approx(w2, rel=0, abs=1e-12)

def test_PT2_kernel_weights_sum_to_one_and_nonnegative():
    for lam in [0.0, 14.999, 15.0, 123.456, 284.999, 285.0, 359.999]:
        w = soft_branch_weights_von_mises(lam, zi_apex_deg=270.0, branch_width_deg=30.0, kappa=4.0)
        assert len(w) == 12
        assert all(x >= 0.0 for x in w)
        assert pytest.approx(sum(w), rel=0, abs=1e-12) == 1.0

def test_PT3_harmonic_periodicity_and_degeneracy():
    # Periodicity: angles + 360 should not change features
    angles = [0.0, 90.0, 180.0, 270.0]
    weights = [0.25, 0.25, 0.25, 0.25]
    f1 = phasor_features(angles, weights, ks=[2,3,4,6,12])
    f2 = phasor_features([a + 360.0 for a in angles], weights, ks=[2,3,4,6,12])
    assert f1 == f2

    # Degeneracy: two opposite points cancel for k=1 (not in list), use k=2 where they also cancel if separated by 90? choose k=1 explicitly
    angles2 = [0.0, 180.0]
    weights2 = [0.5, 0.5]
    fdeg = phasor_features(angles2, weights2, ks=[1])
    assert fdeg["1"]["degenerate"] is True
    assert fdeg["1"]["A_k"] == pytest.approx(0.0, rel=0, abs=1e-12)

def test_PT4_config_fingerprint_determinism_key_order():
    engine_config_a = {
        "engine_version": "1.0.0-rc0",
        "parameter_set_id": "standard",
        "deterministic": True,
        "bazi_ruleset_id": "standard_bazi_2026",
        "refdata": {
            "refdata_pack_id": "refpack-test-001",
        },
        "json_canonicalization": {"sorted_keys": True, "utf8": True},
        "float_format_policy": {"mode": "shortest_roundtrip", "fixed_decimals": None},
    }
    # Same content, different key insertion order
    engine_config_b = {
        "parameter_set_id": "standard",
        "engine_version": "1.0.0-rc0",
        "bazi_ruleset_id": "standard_bazi_2026",
        "deterministic": True,
        "json_canonicalization": {"utf8": True, "sorted_keys": True},
        "float_format_policy": {"fixed_decimals": None, "mode": "shortest_roundtrip"},
        "refdata": {
            "refdata_pack_id": "refpack-test-001",
        },
    }
    fp_a = config_fingerprint(
        engine_config_a,
        ruleset_id="standard_bazi_2026",
        ruleset_version="2026.0",
        refdata_pack_id="refpack-test-001",
        float_format_policy=engine_config_a["float_format_policy"],
        json_canonicalization=engine_config_a["json_canonicalization"],
    )
    fp_b = config_fingerprint(
        engine_config_b,
        ruleset_id="standard_bazi_2026",
        ruleset_version="2026.0",
        refdata_pack_id="refpack-test-001",
        float_format_policy=engine_config_b["float_format_policy"],
        json_canonicalization=engine_config_b["json_canonicalization"],
    )
    assert fp_a == fp_b
