"""Start-age converter: classical BaZi rule 3 calendar days = 1 life-year (360-day year)."""

import warnings

MAX_LIFE_YEARS = 120


def compute_start_age(payload):
    """Convert calendar offset (days, hours, minutes) to life years/months/days.

    Classical rule: 3 calendar days = 1 life-year; 2 calendar hours = 10 life-days;
    12 calendar minutes = 1 life-day. The life-year has 360 days, months are 30 days.

    Caps at 120 life-years if the computed age exceeds that — emits a
    UserWarning whose message contains "start_age_capped_at_120_years".
    """
    life_days = (
        payload.get("days", 0) * 120
        + payload.get("hours", 0) * 5
        + payload.get("minutes", 0) / 12
    )

    if life_days >= MAX_LIFE_YEARS * 360:  # 43200
        warnings.warn(
            f"start_age_capped_at_120_years: computed {life_days/360:.1f} life-years "
            f"exceeds max {MAX_LIFE_YEARS}; clamped.",
            UserWarning,
            stacklevel=2,
        )
        return {
            "years": MAX_LIFE_YEARS,
            "months": 0,
            "days": 0,
            "decimal_years": float(MAX_LIFE_YEARS),
        }

    years = int(life_days // 360)
    remainder = life_days - years * 360
    months = int(remainder // 30)
    days = int(remainder - months * 30)
    decimal_years = life_days / 360
    return {"years": years, "months": months, "days": days, "decimal_years": decimal_years}
