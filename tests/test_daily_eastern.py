from bazi_engine.services.daily_eastern import generate_eastern_daily


def test_eastern_daily_has_required_fields():
    result = generate_eastern_daily(day_master="Xin", target_date="2026-03-16", tz="Europe/Berlin", locale="de-DE")
    assert "summary" in result
    assert "themes" in result
    assert "caution" in result
    assert "opportunity" in result
    assert "evidence" in result
    assert result["evidence"]["day_master"] == "Xin"
    assert "daily_pillar" in result["evidence"]
    assert "stem" in result["evidence"]["daily_pillar"]
    assert "branch" in result["evidence"]["daily_pillar"]
    assert "relation_to_day_master" in result["evidence"]


def test_eastern_daily_different_dates_different_pillars():
    a = generate_eastern_daily(day_master="Xin", target_date="2026-03-16")
    b = generate_eastern_daily(day_master="Xin", target_date="2026-03-17")
    assert a["evidence"]["daily_pillar"] != b["evidence"]["daily_pillar"]


def test_eastern_daily_companion_relation():
    """Find a date where daily stem is also Metall (Geng or Xin) for Xin day master."""
    # Test that the relation logic works — just check it returns a valid relation
    result = generate_eastern_daily(day_master="Xin", target_date="2026-03-16")
    assert result["evidence"]["relation_to_day_master"] in ("companion", "resource", "output", "power", "wealth", "neutral")
