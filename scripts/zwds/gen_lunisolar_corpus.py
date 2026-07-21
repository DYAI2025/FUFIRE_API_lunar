"""Offline generator for the ZWDS independent lunisolar boundary corpus.

*** OFFLINE-ONLY. This script is NEVER imported at runtime. ***

Task ZWDS-P1-04 — the correctness gate for the Swiss-Ephemeris lunisolar
calendar (:class:`bazi_engine.zwds.calendar_provider.SwissephLunisolarCalendar`).
Runtime design rule **D-1** forbids the provider from depending on any
third-party lunar library. This generator is the *offline* cross-check: it uses
an independent reference Chinese-calendar library to emit a boundary corpus that
adversarially stresses the leap-month logic across 40 years. The committed
corpus (``tests/zwds/fixtures/lunisolar_boundary_corpus.json``) is pure DATA; the
test reads that JSON — never this script, never the reference library. Nothing
here may be imported by the engine.

Install the reference library ONLY to (re)generate the corpus::

    .venv/bin/python -m pip install sxtwl
    .venv/bin/python scripts/zwds/gen_lunisolar_corpus.py
    .venv/bin/python -m pip uninstall -y sxtwl   # keep it out of the runtime env

Do **not** add ``sxtwl`` (or ``cnlunar``) to ``pyproject.toml``,
``requirements.lock`` or ``uv.lock``. It must never become a project dependency.

Reference library
------------------
**sxtwl** (寿星天文历 / Shòuxīng astronomical calendar) — an astronomy-based
Chinese-calendar library, the same modern 時憲曆 basis (true new moons +
中氣-anchored month numbering + no-中氣 leap rule) our Swiss-Ephemeris provider
implements. This makes it an *independent* second implementation of the same
astronomical definition rather than a lookup table, which is exactly what a
correctness gate wants.

Convention mapping (sxtwl → :class:`ResolvedLunarDate`)
------------------------------------------------------
* ``day.getLunarYear()``  → ``year_label``  (the civil year the lunar year is
  labelled by; months 11/12 *before* 正月 carry the previous civil year, matching
  our provider's "Gregorian year of the 正月 on or before this month" rule).
* ``day.getLunarMonth()`` → ``month`` (1..12).
* ``day.getLunarDay()``   → ``day`` (1..30).
* ``day.isLunarLeap()``   → ``is_leap_month``.

**Timezone / day-boundary convention.** sxtwl computes in Beijing civil time
(UT+8) and our provider is built with ``day_boundary_offset_hours=8`` (CST) — the
same fixed +8 frame, so civil-day attribution agrees. China used Beijing LMT
(≈UT+7:46) only *before* 1928; every date this corpus emits is ≥ 1984, so the
pre-1928 LMT boundary never applies and no LMT correction is needed. Both sides
therefore share one clean +8 civil-day boundary.

Determinism
-----------
Every row is *labelled* by round-tripping its final Gregorian date through
``sxtwl.fromSolar`` (the solar→lunar direction the provider also resolves), so a
row's expected fields are always self-consistent with the reference library's
solar→lunar map regardless of how the candidate date was picked. Output is a
flat JSON list sorted by Gregorian date with stable key order and 2-space
indent, so the committed file is byte-deterministic across regenerations.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Dict, List

_REPO_ROOT = Path(__file__).resolve().parents[2]
_OUT = _REPO_ROOT / "tests" / "zwds" / "fixtures" / "lunisolar_boundary_corpus.json"

# The corpus is expressed in the CST / Beijing (+8) civil frame — the frame the
# provider is built with (day_boundary_offset_hours=8) and the frame sxtwl uses.
LEAP_SCAN_YEARS = range(2000, 2041)  # every lunar year whose leap month we stress


def _row(sxtwl_mod, greg: date) -> Dict[str, object]:
    """Label a Gregorian date via the reference lib's solar→lunar map."""
    d = sxtwl_mod.fromSolar(greg.year, greg.month, greg.day)
    return {
        "gregorian": greg.isoformat(),
        "year_label": int(d.getLunarYear()),
        "month": int(d.getLunarMonth()),
        "day": int(d.getLunarDay()),
        "is_leap_month": bool(d.isLunarLeap()),
    }


def _greg_of(sxtwl_mod, y: int, m: int, d: int, leap: bool) -> date:
    """Gregorian date of a lunar (year, month, day, leap) via the reference lib."""
    day = sxtwl_mod.fromLunar(y, m, d, leap)
    return date(int(day.getSolarYear()), int(day.getSolarMonth()), int(day.getSolarDay()))


def _month_len(sxtwl_mod, y: int, m: int, leap: bool) -> int:
    return int(sxtwl_mod.getLunarMonthNum(y, m, leap))


def build_candidates(sxtwl_mod) -> List[date]:
    """Assemble the adversarial set of Gregorian candidate dates to label."""
    cands: List[date] = []

    # 1. Every leap month 2000–2040 — the core adversarial set. For each leap
    #    month M of lunar year Y: several days INTO the leap M (expect
    #    is_leap_month True at the repeated number) AND several days in the
    #    immediately preceding NON-leap month M (expect is_leap_month False).
    leap_years: List[int] = []
    for y in LEAP_SCAN_YEARS:
        rm = int(sxtwl_mod.getRunMonth(y))
        if rm == 0:
            continue
        leap_years.append(y)
        leap_len = _month_len(sxtwl_mod, y, rm, True)
        prev_len = _month_len(sxtwl_mod, y, rm, False)
        for d in (2, 4, 18, leap_len):  # into the leap month (incl. its last day)
            cands.append(_greg_of(sxtwl_mod, y, rm, min(d, leap_len), True))
        for d in (1, 8, 25, prev_len):  # the preceding non-leap month of same number
            cands.append(_greg_of(sxtwl_mod, y, rm, min(d, prev_len), False))
    print(f"  leap years found ({len(leap_years)}): {leap_years}")

    # 2. 29- vs 30-day month ends sampled across years. Record the true last day
    #    (day == month_length) so both a 29-ender and a 30-ender are exercised.
    for y in (2003, 2007, 2011, 2015, 2019, 2024, 2028, 2032, 2036, 2040):
        for m in (1, 3, 5, 7, 9, 11):
            length = _month_len(sxtwl_mod, y, m, False)
            cands.append(_greg_of(sxtwl_mod, y, m, length, False))  # last day (29 or 30)
            cands.append(_greg_of(sxtwl_mod, y, m, 1, False))       # first day, for contrast

    # 3. Lunar-year transitions: last day of month 12 of year Y and 正月初一 of
    #    year Y+1, for a spread of years including 1984, 2017, 2020, 2023, 2024.
    for y in (1983, 1999, 2005, 2010, 2016, 2017, 2019, 2020, 2022, 2023, 2032):
        len12 = _month_len(sxtwl_mod, y, 12, False)
        cands.append(_greg_of(sxtwl_mod, y, 12, len12, False))  # 除夕 (last day M12)
        cands.append(_greg_of(sxtwl_mod, y + 1, 1, 1, False))   # 正月初一 (M1 D1)

    # 4. 冬至 month == 11: a date a few days after the winter solstice each year
    #    (records whatever the reference lib assigns — normally 11; the leap-11
    #    2033/34 window is deliberately included to stress that edge).
    for y in range(2004, 2035):
        cands.append(date(y, 12, 25))

    # 5. Broad monthly baseline scan: the 15th of every Gregorian month 2015–2025.
    for y in range(2015, 2026):
        for m in range(1, 13):
            cands.append(date(y, m, 15))

    return cands


def main() -> None:
    try:
        import sxtwl  # noqa: PLC0415 — offline-only import, never at runtime
    except ModuleNotFoundError as exc:  # pragma: no cover - offline generator guard
        raise SystemExit(
            "sxtwl not installed. This offline generator needs it:\n"
            "  .venv/bin/python -m pip install sxtwl\n"
            "Do NOT add sxtwl to pyproject.toml / requirements.lock / uv.lock."
        ) from exc

    cands = build_candidates(sxtwl)

    # Dedup by Gregorian date, label each via the reference lib, sort by date.
    by_date: Dict[str, Dict[str, object]] = {}
    for greg in cands:
        row = _row(sxtwl, greg)
        by_date[row["gregorian"]] = row  # type: ignore[index]
    rows = [by_date[k] for k in sorted(by_date)]

    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    n_leap = sum(1 for r in rows if r["is_leap_month"])
    years = sorted({int(r["gregorian"][:4]) for r in rows})
    print(f"Wrote {len(rows)} rows to {_OUT.relative_to(_REPO_ROOT)}")
    print(f"  leap rows: {n_leap}")
    print(f"  Gregorian year span: {years[0]}–{years[-1]}")


if __name__ == "__main__":
    main()
