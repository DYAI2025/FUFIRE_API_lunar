from bazi_engine.services.daily_western import generate_western_daily


def test_western_daily_has_required_fields():
    result = generate_western_daily(
        sun_sign_idx=4, moon_sign_idx=6, asc_sign_idx=5,
        soulprint_sectors=[0.08, 0.02, 0.07, 0.10, 0.14, 0.12, 0.09, 0.05, 0.11, 0.10, 0.07, 0.05],
        target_date="2026-03-16", tz="Europe/Berlin", lat=53.5511, lon=9.9937, locale="de-DE",
    )
    assert "summary" in result
    assert "themes" in result and len(result["themes"]) >= 1
    assert "caution" in result
    assert "opportunity" in result
    assert "evidence" in result
    assert "transit_sectors" in result["evidence"]


def test_western_daily_different_dates_differ():
    kwargs = dict(sun_sign_idx=4, moon_sign_idx=6, asc_sign_idx=5,
                  soulprint_sectors=[0.08]*12, tz="Europe/Berlin", lat=53.5511, lon=9.9937, locale="de-DE")
    a = generate_western_daily(target_date="2026-03-16", **kwargs)
    b = generate_western_daily(target_date="2026-06-21", **kwargs)
    # Evidence should differ (different transits on different days)
    assert a["evidence"]["transit_sectors"] != b["evidence"]["transit_sectors"] or a["themes"] != b["themes"]
