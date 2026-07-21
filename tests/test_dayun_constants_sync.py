"""Lock the STEMS table across dayun modules.

`jiazi.py` and `relation.py` both define a STEMS sequence — the order is the
Jiazi convention (Jia..Gui, 10 entries). The two modules duplicate the table
intentionally (decoupled domain logic per task DY-010a's YAGNI guardrail). This
test prevents silent drift between the duplicates and against the response
schema's StemEnum.
"""
import json
from pathlib import Path

from bazi_engine.dayun.jiazi import STEMS as JIAZI_STEMS
from bazi_engine.dayun.relation import STEMS as RELATION_STEMS

REPO_ROOT = Path(__file__).resolve().parent.parent
RESPONSE_SCHEMA = (
    REPO_ROOT / "schemas" / "calculate" / "bazi" / "dayun.response.schema.json"
)


def test_jiazi_and_relation_stems_match():
    """Mirror invariant: both modules' STEMS hold the same 10 names in order."""
    assert tuple(JIAZI_STEMS) == tuple(RELATION_STEMS)


def test_stems_match_response_schema_stem_enum():
    """Both module STEMS must also match the response schema's StemEnum."""
    schema = json.loads(RESPONSE_SCHEMA.read_text(encoding="utf-8"))
    schema_stems = tuple(schema["$defs"]["StemEnum"]["enum"])
    assert tuple(JIAZI_STEMS) == schema_stems
    assert tuple(RELATION_STEMS) == schema_stems


def test_branches_match_response_schema_branch_enum():
    """jiazi.py BRANCHES tuple must match the response schema's BranchEnum."""
    from bazi_engine.dayun.jiazi import BRANCHES
    schema = json.loads(RESPONSE_SCHEMA.read_text(encoding="utf-8"))
    schema_branches = tuple(schema["$defs"]["BranchEnum"]["enum"])
    assert tuple(BRANCHES) == schema_branches


def test_jieqi_names_match_response_schema_jieqi_enum():
    """dayun.jieqi._JIEQI_NAMES_SCHEMA_FORM must match the response schema's JieqiEnum.

    Reads the private constant by walking the module (acceptable for a sync
    test that needs to enforce the contract; production code does not depend
    on the constant being public).
    """
    from bazi_engine.dayun import jieqi as _jieqi_mod
    schema = json.loads(RESPONSE_SCHEMA.read_text(encoding="utf-8"))
    schema_jieqi = tuple(schema["$defs"]["JieqiEnum"]["enum"])
    assert tuple(_jieqi_mod._JIEQI_NAMES_SCHEMA_FORM) == schema_jieqi


def test_ten_gods_match_response_schema_ten_god_enum():
    """relation.TEN_GODS dict values' first element must match the response schema's TenGodEnum.

    TEN_GODS is keyed by (element_relation, polarity_match) tuples; values are
    (pinyin, german) tuples. The Pinyin side is the schema-locked vocabulary.
    """
    from bazi_engine.dayun.relation import TEN_GODS
    schema = json.loads(RESPONSE_SCHEMA.read_text(encoding="utf-8"))
    schema_ten_gods = set(schema["$defs"]["TenGodEnum"]["enum"])
    ten_gods_in_table = {pinyin for (pinyin, _german) in TEN_GODS.values()}
    assert ten_gods_in_table == schema_ten_gods


def test_element_relations_match_response_schema_enum():
    """relation.TEN_GODS keys (first element) must match the response schema's
    RelationToDayMaster.element_relation enum."""
    from bazi_engine.dayun.relation import TEN_GODS
    schema = json.loads(RESPONSE_SCHEMA.read_text(encoding="utf-8"))
    schema_relations = set(
        schema["$defs"]["RelationToDayMaster"]["properties"]
              ["element_relation"]["enum"]
    )
    relations_in_table = {rel for (rel, _polarity) in TEN_GODS.keys()}
    assert relations_in_table == schema_relations
