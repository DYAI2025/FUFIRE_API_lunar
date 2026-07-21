from bazi_engine.services.soulprint import compute_soulprint


def test_soulprint_returns_12_sectors():
    result = compute_soulprint(
        sun_sign_idx=4, moon_sign_idx=6, asc_sign_idx=5,
        personal_planets={"mercury": 4, "venus": 6, "mars": 0},
        wuxing_vector={"Holz": 0.22, "Feuer": 0.28, "Erde": 0.19, "Metall": 0.16, "Wasser": 0.15},
    )
    assert len(result) == 12
    assert abs(sum(result) - 1.0) < 0.01

def test_soulprint_different_inputs_differ():
    a = compute_soulprint(0, 0, 0, {}, {"Holz":0.2,"Feuer":0.2,"Erde":0.2,"Metall":0.2,"Wasser":0.2})
    b = compute_soulprint(6, 9, 3, {}, {"Holz":0.5,"Feuer":0.1,"Erde":0.1,"Metall":0.2,"Wasser":0.1})
    assert a != b

def test_soulprint_sun_has_highest_base_weight():
    result = compute_soulprint(0, 6, 9, {}, {"Holz":0.0,"Feuer":0.0,"Erde":0.0,"Metall":0.0,"Wasser":0.0})
    # Sun (sector 0) should have weight 1.0, moon (6) 0.8, asc (9) 0.6
    assert result[0] > result[6] > result[9]
