from bazi_engine.dayun.direction import resolve_direction

# ── Mode A: traditional (year-stem yin/yang + sex_at_birth) ────────────────

def test_yang_year_male_is_forward():
    assert resolve_direction({
        "direction_method": "year_stem_yinyang_and_sex",
        "year_stem_polarity": "yang",
        "sex_at_birth": "male",
    }) == "forward"

def test_yang_year_female_is_backward():
    assert resolve_direction({
        "direction_method": "year_stem_yinyang_and_sex",
        "year_stem_polarity": "yang",
        "sex_at_birth": "female",
    }) == "backward"

def test_yin_year_male_is_backward():
    assert resolve_direction({
        "direction_method": "year_stem_yinyang_and_sex",
        "year_stem_polarity": "yin",
        "sex_at_birth": "male",
    }) == "backward"

def test_yin_year_female_is_forward():
    assert resolve_direction({
        "direction_method": "year_stem_yinyang_and_sex",
        "year_stem_polarity": "yin",
        "sex_at_birth": "female",
    }) == "forward"

# ── Mode B: explicit ──────────────────────────────────────────────────────

def test_explicit_forward_passes_through():
    assert resolve_direction({
        "direction_method": "explicit",
        "flow_direction": "forward",
    }) == "forward"

def test_explicit_backward_passes_through():
    assert resolve_direction({
        "direction_method": "explicit",
        "flow_direction": "backward",
    }) == "backward"
