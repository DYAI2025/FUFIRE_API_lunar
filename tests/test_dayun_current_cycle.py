from datetime import date, datetime, timezone

from bazi_engine.dayun.current_cycle import select_current

# Article-example cycles (synthetic — start_age 2.86 derived from 8d14h delta in DY-008 stub):
ARTICLE_CYCLES = [
    {"sequence": 1, "age_start": 2.86, "age_end": 12.86, "pillar": {"stem": "Jia"}},
    {"sequence": 2, "age_start": 12.86, "age_end": 22.86, "pillar": {"stem": "Yi"}},
    {"sequence": 3, "age_start": 22.86, "age_end": 32.86, "pillar": {"stem": "Bing"}},
    {"sequence": 4, "age_start": 32.86, "age_end": 42.86, "pillar": {"stem": "Ding"}},
    {"sequence": 5, "age_start": 42.86, "age_end": 52.86, "pillar": {"stem": "Wu"}},
]

# ── Happy path ───────────────────────────────────────────────────────────

def test_article_example_returns_cycle_4():
    """1987-07-04 → 2026-05-22 yields age in cycle 4's [32.86, 42.86) window."""
    out = select_current(ARTICLE_CYCLES, birth="1987-07-04", as_of="2026-05-22")
    assert out is not None
    assert out["sequence"] == 4

def test_accepts_date_objects():
    out = select_current(ARTICLE_CYCLES, birth=date(1987, 7, 4), as_of=date(2026, 5, 22))
    assert out["sequence"] == 4

def test_accepts_datetime_objects():
    out = select_current(
        ARTICLE_CYCLES,
        birth=datetime(1987, 7, 4, 12, 0, tzinfo=timezone.utc),
        as_of=datetime(2026, 5, 22, 0, 0, tzinfo=timezone.utc),
    )
    assert out["sequence"] == 4

def test_iso_datetime_string_accepted():
    out = select_current(
        ARTICLE_CYCLES,
        birth="1987-07-04T21:30:00",
        as_of="2026-05-22T12:00:00",
    )
    assert out["sequence"] == 4

# ── Boundaries ───────────────────────────────────────────────────────────

def test_before_first_cycle_returns_none():
    """birth 2024-01-01, as_of 2025-01-01 → age ~1.0 (Gregorian) ≈ 1.014 (360-day)
       — well below first cycle's age_start of 2.86. Returns None."""
    out = select_current(
        ARTICLE_CYCLES, birth="2024-01-01", as_of="2025-01-01"
    )
    assert out is None

def test_after_last_cycle_returns_none():
    """A 100-year-old hits age ~101.4 in 360-day units — past last cycle's age_end of 52.86. None."""
    out = select_current(
        ARTICLE_CYCLES, birth="1925-01-01", as_of="2026-05-22"
    )
    assert out is None

def test_inclusive_lower_bound():
    """age exactly == cycle.age_start → cycle returned (inclusive)."""
    # Real mean-years × 2.86 = 2.86 * 365.2425 calendar days. Birth + that
    # delta lands the age exactly on cycle 1's age_start (2.86), inclusive.
    out = select_current(
        ARTICLE_CYCLES,
        birth=datetime(2020, 1, 1, tzinfo=timezone.utc),
        as_of=datetime(2020, 1, 1, tzinfo=timezone.utc).replace() + __import__("datetime").timedelta(days=2.86 * 365.2425),
    )
    # On the boundary, allow either cycle 1 or None (depends on float rounding).
    # The strict spec: age_start inclusive, so cycle 1 expected.
    assert out is not None
    assert out["sequence"] == 1

def test_exclusive_upper_bound():
    """age exactly == cycle.age_end → next cycle (or None)."""
    # Real mean-years × 12.86 = 12.86 * 365.2425 calendar days. Birth + that
    # delta lands the age exactly on cycle 1's age_end / cycle 2's age_start (12.86).
    from datetime import timedelta
    birth_dt = datetime(2010, 1, 1, tzinfo=timezone.utc)
    as_of_dt = birth_dt + timedelta(days=12.86 * 365.2425)
    out = select_current(ARTICLE_CYCLES, birth=birth_dt, as_of=as_of_dt)
    # On exact 12.86 boundary → cycle 2 (whose age_start is 12.86 inclusive).
    assert out is not None
    assert out["sequence"] == 2

# ── Defensive ────────────────────────────────────────────────────────────

def test_as_of_before_birth_returns_none():
    """Negative age (as_of < birth) returns None, no crash."""
    out = select_current(ARTICLE_CYCLES, birth="2026-01-01", as_of="2020-01-01")
    assert out is None

def test_empty_cycles_returns_none():
    """No cycles at all → None, no IndexError."""
    out = select_current([], birth="1987-07-04", as_of="2026-05-22")
    assert out is None

def test_no_mutation_of_input():
    """Function does not mutate the cycles list."""
    cycles_copy = [dict(c) for c in ARTICLE_CYCLES]
    select_current(cycles_copy, birth="1987-07-04", as_of="2026-05-22")
    assert cycles_copy == ARTICLE_CYCLES
