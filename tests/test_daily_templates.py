"""Tests for daily template variants — relation × jieqi × weekday."""
from bazi_engine.services.daily_templates import (
    CAUTION_VARIANTS_DE,
    JIEQI_FLAVOR_DE,
    OPPORTUNITY_VARIANTS_DE,
    RELATION_SUMMARY_VARIANTS_DE,
    WEEKDAY_ENERGY_DE,
    get_jieqi_flavor,
    get_jieqi_season,
    get_weekday_modifier,
    select_variant,
)


class TestWeekdayModifier:
    def test_monday_is_moon(self):
        # 2026-04-13 is a Monday
        name, planet, _ = get_weekday_modifier("2026-04-13")
        assert name == "Montag"
        assert planet == "Mond"

    def test_friday_is_venus(self):
        # 2026-04-17 is a Friday
        name, planet, _ = get_weekday_modifier("2026-04-17")
        assert name == "Freitag"
        assert planet == "Venus"

    def test_sunday_is_sun(self):
        # 2026-04-19 is a Sunday
        name, planet, _ = get_weekday_modifier("2026-04-19")
        assert name == "Sonntag"
        assert planet == "Sonne"

    def test_all_weekdays_covered(self):
        assert len(WEEKDAY_ENERGY_DE) == 7


class TestJieqiSeason:
    def test_lichun_is_spring(self):
        assert get_jieqi_season("Lichun") == "fruehling_aufbruch"

    def test_xiazhi_is_summer(self):
        assert get_jieqi_season("Xiazhi") == "sommer_aufbruch"

    def test_liqiu_is_autumn(self):
        assert get_jieqi_season("Liqiu") == "herbst_aufbruch"

    def test_dongzhi_is_winter(self):
        assert get_jieqi_season("Dongzhi") == "winter_aufbruch"

    def test_unknown_jieqi_fallback(self):
        assert get_jieqi_season("Unknown") == "fruehling_aufbruch"

    def test_flavor_returns_nonempty_string(self):
        for jieqi in ["Lichun", "Xiazhi", "Qiufen", "Dongzhi"]:
            flavor = get_jieqi_flavor(jieqi)
            assert isinstance(flavor, str)
            assert len(flavor) > 10

    def test_all_seasons_have_flavors(self):
        assert len(JIEQI_FLAVOR_DE) == 8  # 6 seasonal groups mapped to 8 keys


class TestSelectVariant:
    def test_deterministic(self):
        variants = ["a", "b", "c"]
        assert select_variant(variants, "2026-04-14") == select_variant(variants, "2026-04-14")

    def test_different_dates_can_differ(self):
        variants = ["a", "b", "c"]
        results = {select_variant(variants, f"2026-01-{d:02d}") for d in range(1, 10)}
        assert len(results) > 1  # at least 2 different selections

    def test_wraps_around(self):
        variants = ["x", "y"]
        r1 = select_variant(variants, "2026-01-01")  # doy=1, 1%2=1 → "y"
        r2 = select_variant(variants, "2026-01-02")  # doy=2, 2%2=0 → "x"
        assert r1 != r2


class TestRelationVariants:
    RELATIONS = ["companion", "resource", "output", "power", "wealth", "neutral"]

    def test_all_relations_have_summary_variants(self):
        for rel in self.RELATIONS:
            assert rel in RELATION_SUMMARY_VARIANTS_DE
            assert len(RELATION_SUMMARY_VARIANTS_DE[rel]) >= 3

    def test_all_relations_have_caution_variants(self):
        for rel in self.RELATIONS:
            assert rel in CAUTION_VARIANTS_DE
            assert len(CAUTION_VARIANTS_DE[rel]) >= 3

    def test_all_relations_have_opportunity_variants(self):
        for rel in self.RELATIONS:
            assert rel in OPPORTUNITY_VARIANTS_DE
            assert len(OPPORTUNITY_VARIANTS_DE[rel]) >= 3

    def test_summary_variants_contain_dm_placeholder(self):
        for rel, variants in RELATION_SUMMARY_VARIANTS_DE.items():
            for v in variants:
                assert "{dm}" in v, f"{rel} variant missing {{dm}}: {v}"

    def test_no_non_ascii_in_templates(self):
        """All German template strings use ASCII transliteration (ae, ue, oe, ss)."""
        import re
        non_ascii = re.compile(r'[^\x00-\x7F]')
        for pool in [RELATION_SUMMARY_VARIANTS_DE, CAUTION_VARIANTS_DE, OPPORTUNITY_VARIANTS_DE]:
            for rel, variants in pool.items():
                for v in variants:
                    match = non_ascii.search(v)
                    assert match is None, f"{rel} variant contains non-ASCII char '{match.group()}': {v}"


class TestEasternDailyIntegration:
    def test_eastern_daily_has_structured_subfields(self):
        from bazi_engine.services.daily_eastern import generate_eastern_daily

        result = generate_eastern_daily(day_master="Jia", target_date="2026-04-14")
        assert "jieqi_note" in result
        assert "weekday_note" in result
        assert isinstance(result["jieqi_note"], str)
        assert isinstance(result["weekday_note"], str)
        # Summary should NOT contain the jieqi_note or weekday_note text
        assert result["jieqi_note"] not in result["summary"]
        assert result["weekday_note"] not in result["summary"]

    def test_eastern_daily_includes_jieqi_and_weekday(self):
        from bazi_engine.services.daily_eastern import generate_eastern_daily

        result = generate_eastern_daily(day_master="Jia", target_date="2026-04-14")
        assert "jieqi" in result["evidence"]
        assert "weekday" in result["evidence"]
        assert result["evidence"]["jieqi"] in [
            "Chunfen", "Qingming", "Guyu", "Lixia", "Xiaoman", "Mangzhong",
            "Xiazhi", "Xiaoshu", "Dashu", "Liqiu", "Chushu", "Bailu",
            "Qiufen", "Hanlu", "Shuangjiang", "Lidong", "Xiaoxue", "Daxue",
            "Dongzhi", "Xiaohan", "Dahan", "Lichun", "Yushui", "Jingzhe",
        ]

    def test_eastern_different_dates_vary_summary(self):
        from bazi_engine.services.daily_eastern import generate_eastern_daily

        a = generate_eastern_daily(day_master="Jia", target_date="2026-04-14")
        b = generate_eastern_daily(day_master="Jia", target_date="2026-07-15")
        # Different jieqi seasons → different summaries
        assert a["summary"] != b["summary"]


class TestWesternDailyIntegration:
    def test_western_daily_includes_weekday(self):
        from bazi_engine.services.daily_western import generate_western_daily

        result = generate_western_daily(
            sun_sign_idx=0, moon_sign_idx=4, asc_sign_idx=8,
            soulprint_sectors=[0.08] * 12,
            target_date="2026-04-14", tz="Europe/Berlin",
            lat=52.52, lon=13.405,
        )
        assert "weekday" in result["evidence"]


class TestFusionDailyIntegration:
    def test_fusion_includes_jieqi_note(self):
        from bazi_engine.services.daily_fusion import generate_fusion_daily

        western = {"themes": ["Ausdruck"], "evidence": {"weekday": "Dienstag"}}
        eastern = {
            "themes": ["Gleichklang"],
            "evidence": {
                "day_master": "Jia",
                "relation_to_day_master": "companion",
                "jieqi": "Chunfen",
                "weekday": "Dienstag",
            },
        }
        result = generate_fusion_daily(western, eastern)
        # Jieqi and weekday are in structured sub-fields, not concatenated into summary
        assert "Chunfen" in result["jieqi_note"]
        assert "Dienstag" in result["weekday_note"]
        assert "Chunfen" not in result["summary"]
        assert "Dienstag" not in result["summary"]
