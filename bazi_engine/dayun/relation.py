"""Ten-God (十神) classification between a decade stem and the Day Master stem.

For a Day Master with element E/polarity P and a decade stem with element E'/polarity P',
classify the relationship using two axes:

1. Five-element relation:
   - same_element              (E == E')
   - produced_by_day_master    (E generates E')
   - controlled_by_day_master  (E overcomes E')
   - produces_day_master       (E' generates E)
   - controls_day_master       (E' overcomes E)

2. Polarity match (same vs opposite) → selects the variant of the Ten-God.

Production cycle: wood → fire → earth → metal → water → wood.
Control cycle:    wood → earth → water → fire → metal → wood.
"""

# STEMS table mirrored from jiazi.py; both must stay in sync.
STEMS = ("Jia", "Yi", "Bing", "Ding", "Wu", "Ji", "Geng", "Xin", "Ren", "Gui")

_ELEMENTS = ("wood", "fire", "earth", "metal", "water")


def _element_index(stem_index: int) -> int:
    """Map a stem index (0..9) to its element index (0..4)."""
    return stem_index // 2


def _polarity(stem_index: int) -> str:
    """Map a stem index (0..9) to 'yang' (even) or 'yin' (odd)."""
    return "yang" if stem_index % 2 == 0 else "yin"


def _produces(e_idx: int) -> int:
    """Element produced BY e_idx (生): wood→fire→earth→metal→water→wood."""
    return (e_idx + 1) % 5


def _controls(e_idx: int) -> int:
    """Element controlled BY e_idx (克): wood→earth→water→fire→metal→wood."""
    return (e_idx + 2) % 5


# (element_relation, polarity_match) → (ten_god_pinyin, label_de)
TEN_GODS = {
    ("same_element", "same"):                   ("Bi Jian",    "Gefährte"),
    ("same_element", "opposite"):               ("Jie Cai",    "Rivale"),
    ("produced_by_day_master", "same"):         ("Shi Shen",   "Schöpferische Ausgabe"),
    ("produced_by_day_master", "opposite"):     ("Shang Guan", "Disruptive Ausgabe"),
    ("controlled_by_day_master", "same"):       ("Pian Cai",   "Indirektes Vermögen"),
    ("controlled_by_day_master", "opposite"):   ("Zheng Cai",  "Direktes Vermögen"),
    ("controls_day_master", "same"):            ("Qi Sha",     "Druck / Struktur"),
    ("controls_day_master", "opposite"):        ("Zheng Guan", "Verantwortung"),
    ("produces_day_master", "same"):            ("Pian Yin",   "Indirekte Quelle"),
    ("produces_day_master", "opposite"):        ("Zheng Yin",  "Direkte Quelle"),
}


def _classify_element_relation(dm_e: int, dec_e: int) -> str:
    """Classify the five-element relation between DM element and decade element."""
    if dm_e == dec_e:
        return "same_element"
    if _produces(dm_e) == dec_e:
        return "produced_by_day_master"
    if _controls(dm_e) == dec_e:
        return "controlled_by_day_master"
    if _produces(dec_e) == dm_e:
        return "produces_day_master"
    if _controls(dec_e) == dm_e:
        return "controls_day_master"
    # Unreachable: the five arms partition the 5x5 element matrix exhaustively.
    raise AssertionError(
        f"unclassified element pair: dm={dm_e}, dec={dec_e}"
    )


def compute_relation_to_day_master(
    decade_stem_index: int,
    day_master_stem_index: int,
) -> dict:
    """Return the relational classification between a decade stem and the Day Master.

    Returns:
      {
        "day_master":       str,  # day_master Pinyin name, e.g. "Wu"
        "ten_god":          str,  # one of the 10 Pinyin labels, with space
        "element_relation": str,  # one of: same_element | produced_by_day_master |
                                  #         controlled_by_day_master | controls_day_master |
                                  #         produces_day_master
        "label_de":         str,  # German short label
      }

    Indices follow STEMS = [Jia, Yi, Bing, Ding, Wu, Ji, Geng, Xin, Ren, Gui] (0..9).
    """
    dm_element = _element_index(day_master_stem_index)
    dec_element = _element_index(decade_stem_index)

    element_relation = _classify_element_relation(dm_element, dec_element)

    dm_polarity = _polarity(day_master_stem_index)
    dec_polarity = _polarity(decade_stem_index)
    polarity_match = "same" if dm_polarity == dec_polarity else "opposite"

    ten_god, label_de = TEN_GODS[(element_relation, polarity_match)]

    return {
        "day_master": STEMS[day_master_stem_index],
        "ten_god": ten_god,
        "element_relation": element_relation,
        "label_de": label_de,
    }
