from bazi_engine.services.daily_fusion import generate_fusion_daily


def test_fusion_has_required_fields():
    western = {"summary": "Leo focus", "themes": ["Ausdruck", "Kreativitaet"],
               "caution": "careful", "opportunity": "go", "evidence": {"transit_sectors": [4, 8]}}
    eastern = {"summary": "Xin companion", "themes": ["Gleichklang", "Staerkung"],
               "caution": "careful", "opportunity": "go",
               "evidence": {"day_master": "Xin", "daily_pillar": {"stem": "Xin", "branch": "Chou"}, "relation_to_day_master": "companion"}}
    result = generate_fusion_daily(western, eastern, locale="de-DE")
    assert "summary" in result
    assert "synthesis" in result
    assert "action" in result
    assert "pushworthy" in result
    assert isinstance(result["pushworthy"], bool)


def test_fusion_is_not_concatenation():
    western = {"summary": "W text", "themes": ["Ausdruck"], "caution": "W", "opportunity": "W", "evidence": {}}
    eastern = {"summary": "E text", "themes": ["Gleichklang"], "caution": "E", "opportunity": "E", "evidence": {"day_master": "Xin", "relation_to_day_master": "companion"}}
    result = generate_fusion_daily(western, eastern)
    assert result["summary"] != "W text E text"
    assert result["synthesis"] != ""
    assert len(result["synthesis"]) > 50  # substantive text


def test_fusion_pushworthy_for_power():
    western = {"themes": ["Fokus"], "evidence": {}}
    eastern = {"themes": ["Kontrolle"], "evidence": {"day_master": "Xin", "relation_to_day_master": "power"}}
    result = generate_fusion_daily(western, eastern)
    assert result["pushworthy"] is True
    assert result["push_text"] is not None


def test_fusion_not_pushworthy_for_companion():
    western = {"themes": ["Ausdruck"], "evidence": {}}
    eastern = {"themes": ["Gleichklang"], "evidence": {"day_master": "Xin", "relation_to_day_master": "companion"}}
    result = generate_fusion_daily(western, eastern)
    assert result["pushworthy"] is False
    assert result["push_text"] is None
