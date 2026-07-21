from bazi_engine.services.signature_blueprint import compute_signature_blueprint


def test_blueprint_returns_visual_params():
    result = compute_signature_blueprint(
        [0.08, 0.02, 0.07, 0.10, 0.14, 0.12, 0.09, 0.05, 0.11, 0.10, 0.07, 0.05],
        {"Holz": 0.22, "Feuer": 0.28, "Erde": 0.19, "Metall": 0.16, "Wasser": 0.15},
        0.78,
    )
    assert result["seed"].startswith("sig_v1_")
    v = result["visual"]
    for key in ("symmetry", "curvature", "angularity", "density", "contrast"):
        assert 0 <= v[key] <= 1, f"{key} out of range"
    assert 2 <= v["orbit_count"] <= 5

def test_blueprint_deterministic():
    kwargs = dict(soulprint_sectors=[0.08]*12, wuxing_vector={"Holz":0.2,"Feuer":0.2,"Erde":0.2,"Metall":0.2,"Wasser":0.2}, harmony_index=0.5)
    assert compute_signature_blueprint(**kwargs)["seed"] == compute_signature_blueprint(**kwargs)["seed"]

def test_different_inputs_different_blueprints():
    a = compute_signature_blueprint([0.2]+[0.072]*11, {"Holz":0.5,"Feuer":0.1,"Erde":0.1,"Metall":0.2,"Wasser":0.1}, 0.3)
    b = compute_signature_blueprint([0.072]*11+[0.2], {"Holz":0.1,"Feuer":0.5,"Erde":0.1,"Metall":0.1,"Wasser":0.2}, 0.9)
    assert a["visual"] != b["visual"]
