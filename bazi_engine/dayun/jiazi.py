"""60-jiazi cycle helper: pairs 10 Heavenly Stems with 12 Earthly Branches."""

STEMS = ["Jia", "Yi", "Bing", "Ding", "Wu", "Ji", "Geng", "Xin", "Ren", "Gui"]
BRANCHES = ["Zi", "Chou", "Yin", "Mao", "Chen", "Si", "Wu", "Wei", "Shen", "You", "Xu", "Hai"]
STEMS_CN = ["甲", "乙", "丙", "丁", "戊", "己", "庚", "辛", "壬", "癸"]
BRANCHES_CN = ["子", "丑", "寅", "卯", "辰", "巳", "午", "未", "申", "酉", "戌", "亥"]

STEM_ELEMENT = {
    "Jia": "wood", "Yi": "wood",
    "Bing": "fire", "Ding": "fire",
    "Wu": "earth", "Ji": "earth",
    "Geng": "metal", "Xin": "metal",
    "Ren": "water", "Gui": "water",
}

STEM_POLARITY = {
    "Jia": "yang", "Yi": "yin",
    "Bing": "yang", "Ding": "yin",
    "Wu": "yang", "Ji": "yin",
    "Geng": "yang", "Xin": "yin",
    "Ren": "yang", "Gui": "yin",
}


def jiazi_at(index):
    """Return the pillar at position `index` in the 60-cycle (0..59, wraps via modulo)."""
    i = index % 60
    stem = STEMS[i % 10]
    branch = BRANCHES[i % 12]
    return {
        "stem": stem,
        "branch": branch,
        "stem_cn": STEMS_CN[i % 10],
        "branch_cn": BRANCHES_CN[i % 12],
        "element": STEM_ELEMENT[stem],
        "polarity": STEM_POLARITY[stem],
        "index60": i,
    }


def jiazi_next(index):
    """Return the pillar one step forward in the 60-cycle (wraps 59 -> 0)."""
    return jiazi_at((index + 1) % 60)


def jiazi_prev(index):
    """Return the pillar one step back in the 60-cycle (wraps 0 -> 59)."""
    return jiazi_at((index - 1) % 60)
