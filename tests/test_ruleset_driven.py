"""Tests: BaZi computation uses externalized ruleset, not hardcoded tables."""
from __future__ import annotations

import json
from pathlib import Path

from bazi_engine.bafe.ruleset_loader import load_ruleset

RULESET_PATH = Path(__file__).parent.parent / "spec" / "rulesets" / "standard_bazi_2026.json"
RULESET_ID = "standard_bazi_2026"


class TestRulesetStructure:
    """Ruleset JSON must contain all required sections."""

    def test_ruleset_file_exists(self):
        assert RULESET_PATH.exists()

    def test_ruleset_is_valid_json(self):
        data = json.loads(RULESET_PATH.read_text())
        assert isinstance(data, dict)

    def test_has_year_boundary(self):
        data = json.loads(RULESET_PATH.read_text())
        assert "year_boundary" in data

    def test_has_month_boundary(self):
        data = json.loads(RULESET_PATH.read_text())
        assert "month_boundary" in data

    def test_has_day_cycle_anchor(self):
        data = json.loads(RULESET_PATH.read_text())
        assert "day_cycle_anchor" in data

    def test_has_hidden_stems(self):
        data = json.loads(RULESET_PATH.read_text())
        assert "hidden_stems" in data

    def test_has_hour_stem_rule(self):
        data = json.loads(RULESET_PATH.read_text())
        assert "hour_stem_rule" in data

    def test_has_month_stem_rule(self):
        data = json.loads(RULESET_PATH.read_text())
        assert "month_stem_rule" in data

    def test_ruleset_id_in_metadata(self):
        data = json.loads(RULESET_PATH.read_text())
        assert "ruleset_id" in data
        assert data["ruleset_id"] == RULESET_ID


class TestRulesetLoader:
    """ruleset_loader provides correct lookup functions."""

    def test_load_ruleset_returns_dict(self):
        rs = load_ruleset(RULESET_ID)
        assert isinstance(rs, dict)

    def test_hidden_stems_for_zi(self):
        """Branch Zi should have hidden stem Gui."""
        rs = load_ruleset(RULESET_ID)
        hs = rs.get("hidden_stems", {}).get("branch_to_hidden", {})
        zi_stems = hs.get("Zi", [])
        assert len(zi_stems) >= 1
        assert "Gui" in zi_stems

    def test_month_stem_lookup_all_groups(self):
        """month_stem_for_year_stem returns correct stem index for all groups."""
        from bazi_engine.bafe.ruleset_loader import month_stem_for_year_stem
        rs = load_ruleset(RULESET_ID)
        # Group 0: year_stems [0, 5], month 0 (Yin) -> stem index 2
        assert month_stem_for_year_stem(rs, 0, 0) == 2
        assert month_stem_for_year_stem(rs, 5, 0) == 2
        # Group 1: year_stems [1, 6], month 0 (Yin) -> stem index 4
        assert month_stem_for_year_stem(rs, 1, 0) == 4
        assert month_stem_for_year_stem(rs, 6, 0) == 4

    def test_hour_stem_lookup_all_groups(self):
        """hour_stem_for_day_stem returns correct stem index for all groups."""
        from bazi_engine.bafe.ruleset_loader import hour_stem_for_day_stem
        rs = load_ruleset(RULESET_ID)
        # Group 0: day_stems [0, 5], hour branch 0 (Zi) -> stem index 0
        assert hour_stem_for_day_stem(rs, 0, 0) == 0
        assert hour_stem_for_day_stem(rs, 5, 0) == 0
        # Group 2: day_stems [2, 7], hour branch 0 (Zi) -> stem index 4
        assert hour_stem_for_day_stem(rs, 2, 0) == 4

    def test_month_stem_matches_formula_exhaustive(self):
        """Ruleset month-stem table must match the hardcoded formula for all 120 combos."""
        from bazi_engine.bafe.ruleset_loader import month_stem_for_year_stem
        rs = load_ruleset(RULESET_ID)
        for year_stem in range(10):
            for month_idx in range(12):
                formula_result = (year_stem * 2 + 2 + month_idx) % 10
                table_result = month_stem_for_year_stem(rs, year_stem, month_idx)
                assert table_result == formula_result, (
                    f"Mismatch: year_stem={year_stem}, month_idx={month_idx}: "
                    f"formula={formula_result}, table={table_result}"
                )

    def test_hour_stem_matches_formula_exhaustive(self):
        """Ruleset hour-stem table must match the hardcoded formula for all 120 combos."""
        from bazi_engine.bafe.ruleset_loader import hour_stem_for_day_stem
        rs = load_ruleset(RULESET_ID)
        for day_stem in range(10):
            for hour_branch in range(12):
                formula_result = (day_stem * 2 + hour_branch) % 10
                table_result = hour_stem_for_day_stem(rs, day_stem, hour_branch)
                assert table_result == formula_result, (
                    f"Mismatch: day_stem={day_stem}, hour_branch={hour_branch}: "
                    f"formula={formula_result}, table={table_result}"
                )


class TestRulesetInProvenance:
    """Provenance must include ruleset_id."""

    def test_provenance_has_ruleset_id(self):
        from bazi_engine.provenance import build_provenance
        prov = build_provenance()
        assert "ruleset_id" in prov

    def test_provenance_ruleset_id_value(self):
        from bazi_engine.provenance import build_provenance
        prov = build_provenance(ruleset_id=RULESET_ID)
        assert prov["ruleset_id"] == RULESET_ID
