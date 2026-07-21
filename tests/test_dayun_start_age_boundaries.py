"""Start-age converter boundary cases: zero delta + 120-year cap (DY-2)."""

import warnings

from bazi_engine.dayun.start_age import compute_start_age

# ── Boundary: zero delta ─────────────────────────────────────────────────

def test_zero_delta_yields_all_zeros():
    out = compute_start_age({"days": 0, "hours": 0, "minutes": 0})
    assert out["years"] == 0
    assert out["months"] == 0
    assert out["days"] == 0
    assert out["decimal_years"] == 0.0


def test_missing_keys_treated_as_zero():
    # delta_calendar with partial keys — implementer uses .get(..., 0).
    # Sanity: not requested by spec, but a real input shape from the jieqi adapter.
    out = compute_start_age({})
    assert out["decimal_years"] == 0.0


# ── Cap: exceeding 120 years ─────────────────────────────────────────────

def test_exactly_120_years_caps_silently():
    # 120 life-years = 43200 life-days = 360 calendar days at 1d=4mo.
    # Boundary: must emit warning even on the exact threshold.
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        out = compute_start_age({"days": 360, "hours": 0, "minutes": 0})
        assert out["years"] == 120
        assert out["months"] == 0
        assert out["days"] == 0
        assert out["decimal_years"] == 120.0
        assert any("start_age_capped_at_120_years" in str(w.message) for w in caught)


def test_exceeding_120_years_caps_and_warns():
    # 1000 calendar days = 333 life-years — well over the cap.
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        out = compute_start_age({"days": 1000, "hours": 0, "minutes": 0})
        assert out["years"] == 120
        assert out["months"] == 0
        assert out["days"] == 0
        assert out["decimal_years"] == 120.0
        assert len(caught) == 1
        assert issubclass(caught[0].category, UserWarning)
        assert "start_age_capped_at_120_years" in str(caught[0].message)


def test_just_under_cap_does_not_warn():
    # 119 life-years = 357 calendar days. No warning expected.
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        out = compute_start_age({"days": 357, "hours": 0, "minutes": 0})
        assert out["years"] == 119
        # decimal_years = 357/3 = 119.0 exactly
        assert abs(out["decimal_years"] - 119.0) < 1e-9
        cap_warnings = [w for w in caught if "start_age_capped_at_120_years" in str(w.message)]
        assert len(cap_warnings) == 0
