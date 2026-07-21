"""Start-age converter: classical 3-days-=-1-year rule (360-day life-year)."""


from bazi_engine.dayun.start_age import compute_start_age


def test_eight_days_fourteen_hours_yields_2y10m10d_2_86_years():
    # 8d × 120 = 960 life-days; 14h × 5 = 70 life-days; total = 1030 life-days
    # 1030 / 360 = 2 years rem 310; 310 / 30 = 10 months rem 10 days; decimal = 1030/360 ≈ 2.861
    out = compute_start_age({"days": 8, "hours": 14, "minutes": 0})
    assert out["years"] == 2
    assert out["months"] == 10
    assert out["days"] == 10
    assert abs(out["decimal_years"] - 2.86) < 0.01


def test_three_days_yields_exactly_one_year():
    # 3d × 120 = 360 life-days = exactly 1 year
    out = compute_start_age({"days": 3, "hours": 0, "minutes": 0})
    assert out["years"] == 1
    assert out["months"] == 0
    assert out["days"] == 0
    assert abs(out["decimal_years"] - 1.0) < 1e-9


def test_two_hours_twelve_minutes_yields_eleven_days():
    # 2h × 5 = 10 life-days; 12min × (1/12) = 1 life-day; total = 11 life-days
    # 11 / 360 = 0 years; 11 / 30 = 0 months rem 11 days
    out = compute_start_age({"days": 0, "hours": 2, "minutes": 12})
    assert out["years"] == 0
    assert out["months"] == 0
    assert out["days"] == 11
