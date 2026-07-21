"""Tests for relation_to_day_master (Ten-God classification between decade stem and Day Master)."""

from bazi_engine.dayun.relation import compute_relation_to_day_master

# Day Master = Wu (index 4, earth, yang)

def test_jia_wood_yang_to_wu_earth_yang_is_qi_sha():
    """Jia (wood) controls Wu (earth)? No — earth is controlled BY wood.
       Reread: wood controls earth → Jia (wood) controls Wu (earth) →
       from Wu's perspective, the OTHER (Jia=wood) controls THE DAY MASTER (Wu=earth)
       → 'controls_day_master'. Same polarity (yang+yang) → Qi Sha (七殺) — matches plan §3."""
    out = compute_relation_to_day_master(decade_stem_index=0, day_master_stem_index=4)
    assert out["day_master"] == "Wu"
    assert out["ten_god"] == "Qi Sha"
    assert out["element_relation"] == "controls_day_master"
    assert out["label_de"] == "Druck / Struktur"


def test_yi_wood_yin_to_wu_earth_yang_is_zheng_guan():
    """Yi (wood, yin) controls Wu (earth, yang) → 'controls_day_master', opposite polarity → Zheng Guan."""
    out = compute_relation_to_day_master(1, 4)
    assert out["ten_god"] == "Zheng Guan"
    assert out["element_relation"] == "controls_day_master"


def test_bing_fire_yang_to_wu_earth_yang_is_pian_yin():
    """Bing (fire) produces Wu (earth) → 'produces_day_master', same polarity → Pian Yin."""
    out = compute_relation_to_day_master(2, 4)
    assert out["ten_god"] == "Pian Yin"
    assert out["element_relation"] == "produces_day_master"


def test_ding_fire_yin_to_wu_earth_yang_is_zheng_yin():
    """Ding (fire, yin) produces Wu (earth, yang) → 'produces_day_master', opposite → Zheng Yin."""
    out = compute_relation_to_day_master(3, 4)
    assert out["ten_god"] == "Zheng Yin"
    assert out["element_relation"] == "produces_day_master"


def test_wu_earth_yang_to_wu_earth_yang_is_bi_jian():
    """Same stem → same element + same polarity → Bi Jian (companion)."""
    out = compute_relation_to_day_master(4, 4)
    assert out["ten_god"] == "Bi Jian"
    assert out["element_relation"] == "same_element"


def test_ji_earth_yin_to_wu_earth_yang_is_jie_cai():
    """Ji (earth, yin) and Wu (earth, yang) → same element + opposite polarity → Jie Cai."""
    out = compute_relation_to_day_master(5, 4)
    assert out["ten_god"] == "Jie Cai"


def test_geng_metal_yang_to_wu_earth_yang_is_shi_shen():
    """Wu (earth) produces Geng (metal) → 'produced_by_day_master', same polarity → Shi Shen."""
    out = compute_relation_to_day_master(6, 4)
    assert out["ten_god"] == "Shi Shen"
    assert out["element_relation"] == "produced_by_day_master"


def test_xin_metal_yin_to_wu_earth_yang_is_shang_guan():
    """Wu (earth) produces Xin (metal, yin); Wu yang → opposite polarity → Shang Guan."""
    out = compute_relation_to_day_master(7, 4)
    assert out["ten_god"] == "Shang Guan"


def test_ren_water_yang_to_wu_earth_yang_is_pian_cai():
    """Wu (earth) controls Ren (water) → 'controlled_by_day_master', same polarity → Pian Cai."""
    out = compute_relation_to_day_master(8, 4)
    assert out["ten_god"] == "Pian Cai"
    assert out["element_relation"] == "controlled_by_day_master"


def test_gui_water_yin_to_wu_earth_yang_is_zheng_cai():
    """Wu (earth) controls Gui (water, yin); Wu yang → opposite → Zheng Cai."""
    out = compute_relation_to_day_master(9, 4)
    assert out["ten_god"] == "Zheng Cai"


# ── Other Day Masters ────────────────────────────────────────────────────

def test_jia_to_jia_is_bi_jian():
    """Identity case for DM=Jia (wood, yang)."""
    out = compute_relation_to_day_master(0, 0)
    assert out["day_master"] == "Jia"
    assert out["ten_god"] == "Bi Jian"


def test_gui_to_gui_is_bi_jian():
    """Identity case for DM=Gui (water, yin)."""
    out = compute_relation_to_day_master(9, 9)
    assert out["day_master"] == "Gui"
    assert out["ten_god"] == "Bi Jian"


def test_all_100_pairs_classified():
    """Sanity: every (decade, dm) pair (10x10=100) returns a valid ten-god, no None."""
    valid_ten_gods = {
        "Bi Jian", "Jie Cai", "Shi Shen", "Shang Guan",
        "Pian Cai", "Zheng Cai", "Qi Sha", "Zheng Guan",
        "Pian Yin", "Zheng Yin",
    }
    valid_relations = {
        "same_element", "produced_by_day_master", "controlled_by_day_master",
        "controls_day_master", "produces_day_master",
    }
    for dec in range(10):
        for dm in range(10):
            out = compute_relation_to_day_master(dec, dm)
            assert out["ten_god"] in valid_ten_gods, f"unknown ten_god for ({dec},{dm}): {out}"
            assert out["element_relation"] in valid_relations
            assert isinstance(out["label_de"], str) and len(out["label_de"]) > 0
            assert out["day_master"] in {"Jia", "Yi", "Bing", "Ding", "Wu", "Ji", "Geng", "Xin", "Ren", "Gui"}
