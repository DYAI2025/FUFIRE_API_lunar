"""Unit tests for the deterministic Da-Yun interpretation layer
(``bazi_engine/dayun/interpretation.py``).

DL-1 covers the classical branch-relation primitives (六冲 clash / 六合 combine);
DL-2 covers ``build_semantic_summary`` assembly, its Ten-God bucket coverage,
determinism, and schema conformance against ``$defs.SemanticSummary``.
"""
from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator

from bazi_engine.constants import BRANCHES, STEMS
from bazi_engine.dayun.interpretation import (
    SIX_COMBINE,
    _clashes,
    _combines,
    branch_interactions,
    build_semantic_summary,
)
from bazi_engine.dayun.jiazi import jiazi_at

# Canonical 10 Ten-God strings produced by relation.compute_relation_to_day_master.
TEN_GODS = [
    "Bi Jian",
    "Jie Cai",
    "Shi Shen",
    "Shang Guan",
    "Pian Cai",
    "Zheng Cai",
    "Qi Sha",
    "Zheng Guan",
    "Pian Yin",
    "Zheng Yin",
]

REPO_ROOT = Path(__file__).resolve().parent.parent
RESPONSE_SCHEMA = (
    REPO_ROOT / "schemas" / "calculate" / "bazi" / "dayun.response.schema.json"
)


def _semantic_summary_validator() -> Draft202012Validator:
    schema = json.loads(RESPONSE_SCHEMA.read_text(encoding="utf-8"))
    return Draft202012Validator(schema["$defs"]["SemanticSummary"])


# ── DL-1: branch relation primitives ─────────────────────────────────────────


def test_zi_clashes_wu_not_chou():
    zi, chou, wu = 0, 1, 6
    assert _clashes(zi, wu) is True
    assert _clashes(zi, chou) is False


def test_combines_zi_chou_true_zi_wu_false():
    zi, chou, wu = 0, 1, 6
    assert _combines(zi, chou) is True
    assert _combines(zi, wu) is False


def test_branch_interactions_exact_positions():
    # Decade branch Zi(0): clashes Wu(6), combines Chou(1).
    natal = {"year": 6, "month": 1, "day": 0, "hour": 3}
    result = branch_interactions(0, natal)
    assert result["clashes"] == ["year"]
    assert result["combines"] == ["month"]


def test_branch_interactions_multiple_and_ordered():
    # Zi(0) clashes Wu(6) at year & day; combines Chou(1) at month & hour.
    natal = {"year": 6, "month": 1, "day": 6, "hour": 1}
    result = branch_interactions(0, natal)
    assert result["clashes"] == ["year", "day"]
    assert result["combines"] == ["month", "hour"]


def test_clash_symmetry():
    for a in range(12):
        for b in range(12):
            assert _clashes(a, b) == _clashes(b, a)


def test_clash_partition_each_branch_clashes_exactly_one():
    for a in range(12):
        partners = [b for b in range(12) if _clashes(a, b)]
        assert partners == [(a + 6) % 12]
        assert len(partners) == 1


def test_combine_partition_each_branch_combines_exactly_one():
    # SIX_COMBINE holds six disjoint pairs covering all 12 branches once each.
    assert len(SIX_COMBINE) == 6
    for a in range(12):
        partners = [b for b in range(12) if b != a and _combines(a, b)]
        assert len(partners) == 1


# ── DL-2: branch-index derivation from index60 ────────────────────────────────


def test_decade_branch_index_derivation_matches_jiazi():
    """decade_pillar['branch'] == BRANCHES[decade_pillar['index60'] % 12] for
    every position in the 60-cycle — the derivation build_semantic_summary uses."""
    for i in range(60):
        p = jiazi_at(i)
        assert p["branch"] == BRANCHES[p["index60"] % 12]


# ── DL-2: build_semantic_summary ──────────────────────────────────────────────


def test_qi_sha_with_clash_gives_both_friction_lines():
    decade = jiazi_at(0)  # branch Zi(0)
    natal = {"year": 0, "month": 0, "day": 6, "hour": 0}  # day = Wu(6) → clash
    out = build_semantic_summary(
        day_master_stem_index=4,  # Wu
        decade_pillar=decade,
        natal_branches=natal,
        relation={"ten_god": "Qi Sha"},
    )
    ten_god_phrase = "Druck/Struktur — Belastung, die zu Disziplin zwingt."
    assert ten_god_phrase in out["frictions"]
    assert any(line.startswith("六冲") for line in out["frictions"])
    assert len(out["frictions"]) == 2
    assert out["supports"] == []


def test_shi_shen_with_combine_gives_both_support_lines():
    decade = jiazi_at(0)  # branch Zi(0)
    natal = {"year": 0, "month": 1, "day": 0, "hour": 0}  # month = Chou(1) → combine
    out = build_semantic_summary(
        day_master_stem_index=0,  # Jia
        decade_pillar=decade,
        natal_branches=natal,
        relation={"ten_god": "Shi Shen"},
    )
    ten_god_phrase = "Schöpferische Ausgabe fließt leicht (Ausdruck, Genuss)."
    assert ten_god_phrase in out["supports"]
    assert any(line.startswith("六合") for line in out["supports"])
    assert len(out["supports"]) == 2
    assert out["frictions"] == []


def test_output_keys_and_types():
    decade = jiazi_at(0)
    natal = {"year": 6, "month": 1, "day": 0, "hour": 3}
    out = build_semantic_summary(
        day_master_stem_index=4,
        decade_pillar=decade,
        natal_branches=natal,
        relation={"ten_god": "Zheng Yin"},
    )
    assert set(out.keys()) == {"road_metaphor", "supports", "frictions", "practice"}
    assert isinstance(out["road_metaphor"], str)
    for key in ("supports", "frictions", "practice"):
        assert isinstance(out[key], list)
        assert all(isinstance(item, str) for item in out[key])


def test_practice_always_length_one_and_matches_bucket():
    from bazi_engine.dayun.interpretation import _PRACTICE, _TEN_GOD_BUCKET

    decade = jiazi_at(0)
    natal = {"year": 0, "month": 0, "day": 0, "hour": 0}  # Zi(0): no interaction
    for tg in TEN_GODS:
        out = build_semantic_summary(
            day_master_stem_index=4,
            decade_pillar=decade,
            natal_branches=natal,
            relation={"ten_god": tg},
        )
        assert len(out["practice"]) == 1
        bucket = _TEN_GOD_BUCKET[tg][0]
        assert out["practice"][0] == _PRACTICE[bucket]


def test_all_ten_gods_bucketed_no_keyerror():
    decade = jiazi_at(0)
    natal = {"year": 0, "month": 0, "day": 0, "hour": 0}
    for tg in TEN_GODS:
        out = build_semantic_summary(
            day_master_stem_index=4,
            decade_pillar=decade,
            natal_branches=natal,
            relation={"ten_god": tg},
        )
        assert len(out["practice"]) == 1


def test_determinism_identical_output_two_calls():
    decade = jiazi_at(0)
    natal = {"year": 6, "month": 1, "day": 0, "hour": 3}
    kwargs = dict(
        day_master_stem_index=4,
        decade_pillar=decade,
        natal_branches=natal,
        relation={"ten_god": "Qi Sha"},
    )
    first = build_semantic_summary(**kwargs)
    second = build_semantic_summary(**kwargs)
    assert first == second


def test_sample_output_validates_against_semantic_summary_schema():
    validator = _semantic_summary_validator()
    decade = jiazi_at(0)
    natal = {"year": 6, "month": 1, "day": 0, "hour": 3}
    for tg in TEN_GODS:
        out = build_semantic_summary(
            day_master_stem_index=4,
            decade_pillar=decade,
            natal_branches=natal,
            relation={"ten_god": tg},
        )
        errors = list(validator.iter_errors(out))
        assert not errors, f"{tg}: " + "; ".join(e.message for e in errors)


def test_road_metaphor_uses_day_master_stem():
    decade = jiazi_at(0)
    natal = {"year": 0, "month": 0, "day": 0, "hour": 0}
    for idx, name in enumerate(STEMS):
        out = build_semantic_summary(
            day_master_stem_index=idx,
            decade_pillar=decade,
            natal_branches=natal,
            relation={"ten_god": "Bi Jian"},
        )
        assert f"{name}-Kern" in out["road_metaphor"]
