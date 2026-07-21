"""Tests for the 60-jiazi cycle helper (TASK-DY-005)."""

from bazi_engine.dayun.jiazi import jiazi_at, jiazi_next, jiazi_prev


def test_jiazi_at_0_is_jia_zi():
    out = jiazi_at(0)
    assert out["stem"] == "Jia"
    assert out["branch"] == "Zi"
    assert out["stem_cn"] == "甲"
    assert out["branch_cn"] == "子"
    assert out["element"] == "wood"
    assert out["polarity"] == "yang"
    assert out["index60"] == 0


def test_jiazi_at_40_is_jia_chen():
    # Standard 0-indexed jiazi: position 40 = (stem 0=Jia, branch 4=Chen)
    out = jiazi_at(40)
    assert out["stem"] == "Jia"
    assert out["branch"] == "Chen"
    assert out["element"] == "wood"
    assert out["polarity"] == "yang"
    assert out["index60"] == 40


def test_jiazi_at_59_is_gui_hai():
    out = jiazi_at(59)
    assert out["stem"] == "Gui"
    assert out["branch"] == "Hai"
    assert out["element"] == "water"
    assert out["polarity"] == "yin"
    assert out["index60"] == 59


def test_jiazi_next_from_0_is_yi_chou():
    out = jiazi_next(0)
    assert out["index60"] == 1
    assert out["stem"] == "Yi"
    assert out["branch"] == "Chou"


def test_jiazi_next_from_59_wraps_to_jia_zi():
    out = jiazi_next(59)
    assert out["index60"] == 0
    assert out["stem"] == "Jia"
    assert out["branch"] == "Zi"


def test_jiazi_prev_from_0_wraps_to_gui_hai():
    out = jiazi_prev(0)
    assert out["index60"] == 59
    assert out["stem"] == "Gui"
    assert out["branch"] == "Hai"


def test_jiazi_prev_from_59_is_ren_xu():
    out = jiazi_prev(59)
    assert out["index60"] == 58
    assert out["stem"] == "Ren"
    assert out["branch"] == "Xu"
