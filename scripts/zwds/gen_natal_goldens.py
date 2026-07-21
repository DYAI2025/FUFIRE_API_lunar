"""Offline generator for the ZWDS natal golden corpus (ZWDS-P1-23 / GATE-1).

*** OFFLINE-ONLY. This script is NEVER imported at runtime. ***

It LOCKS the ZWDS core-seed engine's current deterministic natal output for
regression. Each golden is engine-deterministic-truth, NOT a historically
validated natal chart: practitioner review (GATE-1) is still PENDING — see
``docs/zwds/golden-review.md``.

How determinism is achieved
---------------------------
:func:`bazi_engine.zwds.engine.compute_zwds_raw` is a pure function of
``(request, request_id, generated_at)`` once the ephemeris is fixed. Every case
below pins a FIXED ``request_id`` and the FIXED ``generated_at`` constant
:data:`GENERATED_AT`, so the full response (fingerprint + every field) is
byte-stable across regenerations.

Ephemeris requirement (SWIEPH)
------------------------------
The lunisolar calendar half converts the civil chart date onto the Chinese
lunisolar calendar via Swiss-Ephemeris (true new-moon search). The committed
goldens — and the ``swieph``-marked golden test that re-checks them — are
SWIEPH-mode truth. Regenerate ONLY with the verified SE1 files present::

    export SE_EPHE_PATH=/path/to/verified/swisseph   # sepl_18/semo_18/seas_18/seplm06.se1
    .venv/bin/python scripts/zwds/gen_natal_goldens.py

With SE1 present the backend runs in SWIEPH mode (its default). Do NOT generate
in MOSEPH mode: a MOSEPH new-moon instant can land a hair either side of a lunar
day boundary and shift a lunar date, which would make the ``swieph`` test — run
where SE1 IS present — disagree with a MOSEPH-baked golden.

Coverage (every case's purpose is stated in its ``purpose`` field below)
-----------------------------------------------------------------------
* All 5 Five-Elements Bureaus: WATER_2, WOOD_3, METAL_4, FIRE_6, EARTH_5.
* All 10 year stems JIA..GUI — so every Four-Transformations row is exercised
  (incl. the contested GENG/REN HUA_KE cells).
* >=1 leap-month birth (2023 闰二月 / leap 2nd month) — also exercises the
  ``split-after-day-15.guide-v1`` policy (chart_lunar_date is leap month 2, yet
  effective_month_for_chart splits to 3).
* >=1 late-Zi birth (23:00-23:59 local) — the canonical 1984 vector and the
  Berlin case.
* Both direction methods (``year_stem_yinyang_and_sex`` + ``explicit``) plus one
  ``omit`` (no decadals). Male + female + no-sex direction paths all exercised.
* >=1 non-CST birth (Europe/Berlin) — exercises day_boundary_offset_hours != 8.
* The canonical 1984 Shanghai example vector.

Output
------
One file per case at ``tests/zwds/goldens/<case_id>.json``::

    {"request": {...}, "request_id": "...", "generated_at": "...",
     "response": {<full compute_zwds_raw output>}}

Emitted as stable, sorted JSON (2-space indent, trailing newline) so the
committed files are byte-deterministic across regenerations. ``sort_keys`` only
orders object keys; list order (star_placements[], palaces[], ...) is preserved
as the engine emits it, because that order is itself part of the locked output.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from bazi_engine.zwds.engine import compute_zwds_raw

_REPO_ROOT = Path(__file__).resolve().parents[2]
_GOLDENS_DIR = _REPO_ROOT / "tests" / "zwds" / "goldens"

#: The single fixed generation timestamp that makes every response deterministic.
GENERATED_AT = "2026-07-14T00:00:00Z"

_RULESET_ID = "zwds.fufire.core-seed.v1"


def _birth(
    datetime_local: str,
    timezone: str,
    lat: float,
    lon: float,
    *,
    sex_at_birth: str | None = None,
    ambiguous_time: str = "earlier",
    nonexistent_time: str = "error",
) -> Dict[str, Any]:
    """Assemble a schema-valid ``CivilBirthInput`` block."""
    birth: Dict[str, Any] = {
        "datetime_local": datetime_local,
        "timezone": timezone,
        "location": {"lat": lat, "lon": lon},
        "ambiguousTime": ambiguous_time,
        "nonexistentTime": nonexistent_time,
    }
    if sex_at_birth is not None:
        birth["sex_at_birth"] = sex_at_birth
    return birth


def _calculation(
    direction_method: str, *, flow_direction: str | None = None
) -> Dict[str, Any]:
    """Assemble a schema-valid ``CalculationOptions`` block."""
    calc: Dict[str, Any] = {
        "ruleset_id": _RULESET_ID,
        "direction_method": direction_method,
    }
    if flow_direction is not None:
        calc["flow_direction"] = flow_direction
    return calc


def _output(
    *,
    include_trace: bool = False,
    include_decadal_limits: bool = True,
    include_layout: bool = False,
    include_catalog: bool = False,
    star_scope: str = "core",
    script_variant: str = "ids_only",
    locale: str = "de-DE",
) -> Dict[str, Any]:
    """Assemble a schema-valid ``OutputOptions`` block."""
    return {
        "locale": locale,
        "script_variant": script_variant,
        "include_trace": include_trace,
        "include_decadal_limits": include_decadal_limits,
        "include_layout": include_layout,
        "include_catalog": include_catalog,
        "star_scope": star_scope,
    }


# --- The natal golden corpus -------------------------------------------------
# Each case documents WHY it exists. Together they satisfy the ZWDS-P1-23
# coverage contract (see module docstring). Bureau / stem tags in the comments
# are informational; the test locks the full response, not just those fields.
CASES: List[Dict[str, Any]] = [
    {
        "case_id": "canonical_1984_shanghai_jia_fire6",
        "purpose": (
            "Canonical 1984 Shanghai example vector. Stem JIA (Four-Transf. row "
            "JIA), Bureau FIRE_6, late-Zi (23:30 -> next chart day, hour ZI), "
            "CST/+8 civil frame, traditional direction (male). Trace on."
        ),
        "request": {
            "birth": _birth(
                "1984-02-01T23:30:00", "Asia/Shanghai", 31.2304, 121.4737,
                sex_at_birth="male",
            ),
            "calculation": _calculation("year_stem_yinyang_and_sex"),
            "output": _output(include_trace=True),
        },
    },
    {
        "case_id": "yi_1985_shanghai_water2_female",
        "purpose": (
            "Stem YI (row YI), Bureau WATER_2. Traditional direction with "
            "sex=female (female polarity path for the decadal walk direction)."
        ),
        "request": {
            "birth": _birth(
                "1985-03-15T10:20:00", "Asia/Shanghai", 31.2304, 121.4737,
                sex_at_birth="female",
            ),
            "calculation": _calculation("year_stem_yinyang_and_sex"),
            "output": _output(),
        },
    },
    {
        "case_id": "bing_1986_shanghai_wood3_explicit_forward",
        "purpose": (
            "Stem BING (row BING), Bureau WOOD_3. Explicit direction method "
            "(flow_direction=forward, no sex_at_birth) — exercises the explicit "
            "decadal path and the no-sex birth branch."
        ),
        "request": {
            "birth": _birth(
                "1986-03-15T02:20:00", "Asia/Shanghai", 31.2304, 121.4737,
            ),
            "calculation": _calculation("explicit", flow_direction="forward"),
            "output": _output(),
        },
    },
    {
        "case_id": "ding_1987_shanghai_metal4_omit",
        "purpose": (
            "Stem DING (row DING), Bureau METAL_4. direction_method=omit -> "
            "include_decadal_limits=false (decadal_limits null). No sex_at_birth."
        ),
        "request": {
            "birth": _birth(
                "1987-03-15T02:20:00", "Asia/Shanghai", 31.2304, 121.4737,
            ),
            "calculation": _calculation("omit"),
            "output": _output(include_decadal_limits=False),
        },
    },
    {
        "case_id": "wu_1988_shanghai_earth5_female",
        "purpose": (
            "Stem WU (row WU), Bureau EARTH_5. Traditional direction (female). "
            "Trace on for a second trace-enabled response."
        ),
        "request": {
            "birth": _birth(
                "1988-03-15T18:20:00", "Asia/Shanghai", 31.2304, 121.4737,
                sex_at_birth="female",
            ),
            "calculation": _calculation("year_stem_yinyang_and_sex"),
            "output": _output(include_trace=True),
        },
    },
    {
        "case_id": "ji_1989_shanghai_fire6_male",
        "purpose": (
            "Stem JI (row JI), Bureau FIRE_6. Traditional direction (male)."
        ),
        "request": {
            "birth": _birth(
                "1989-03-15T02:20:00", "Asia/Shanghai", 31.2304, 121.4737,
                sex_at_birth="male",
            ),
            "calculation": _calculation("year_stem_yinyang_and_sex"),
            "output": _output(),
        },
    },
    {
        "case_id": "geng_1990_shanghai_metal4_male_fullscope",
        "purpose": (
            "Stem GENG (row GENG — the CONTESTED GENG.HUA_KE cell), Bureau "
            "METAL_4. star_scope=full_ruleset (completeness.requested_scope echo)."
        ),
        "request": {
            "birth": _birth(
                "1990-03-15T22:20:00", "Asia/Shanghai", 31.2304, 121.4737,
                sex_at_birth="male",
            ),
            "calculation": _calculation("year_stem_yinyang_and_sex"),
            "output": _output(star_scope="full_ruleset"),
        },
    },
    {
        "case_id": "xin_1991_shanghai_wood3_female",
        "purpose": (
            "Stem XIN (row XIN), Bureau WOOD_3. Traditional direction (female)."
        ),
        "request": {
            "birth": _birth(
                "1991-03-15T06:20:00", "Asia/Shanghai", 31.2304, 121.4737,
                sex_at_birth="female",
            ),
            "calculation": _calculation("year_stem_yinyang_and_sex"),
            "output": _output(),
        },
    },
    {
        "case_id": "ren_1992_shanghai_water2_explicit_backward",
        "purpose": (
            "Stem REN (row REN — the CONTESTED REN.HUA_KE cell), Bureau WATER_2. "
            "Explicit direction (flow_direction=backward, no sex) — the backward "
            "explicit decadal path."
        ),
        "request": {
            "birth": _birth(
                "1992-03-15T18:20:00", "Asia/Shanghai", 31.2304, 121.4737,
            ),
            "calculation": _calculation("explicit", flow_direction="backward"),
            "output": _output(),
        },
    },
    {
        "case_id": "gui_2023_shanghai_leap2_wood3",
        "purpose": (
            "Stem GUI (row GUI), Bureau WOOD_3. LEAP-MONTH birth in 2023 闰二月 "
            "(leap 2nd month): chart_lunar_date is leap month 2, day 18, and the "
            "split-after-day-15.guide-v1 policy sets effective_month_for_chart=3. "
            "Traditional direction (male)."
        ),
        "request": {
            "birth": _birth(
                "2023-04-08T14:20:00", "Asia/Shanghai", 31.2304, 121.4737,
                sex_at_birth="male",
            ),
            "calculation": _calculation("year_stem_yinyang_and_sex"),
            "output": _output(include_trace=True),
        },
    },
    {
        "case_id": "berlin_1985_yi_latezi_noncst",
        "purpose": (
            "NON-CST birth (Europe/Berlin, +02:00 DST) — day_boundary_offset_hours "
            "!= 8 — combined with a late-Zi birth (23:30 -> next chart day, hour "
            "ZI). Stem YI, traditional direction (male). Trace on."
        ),
        "request": {
            "birth": _birth(
                "1985-07-15T23:30:00", "Europe/Berlin", 52.52, 13.405,
                sex_at_birth="male",
            ),
            "calculation": _calculation("year_stem_yinyang_and_sex"),
            "output": _output(include_trace=True),
        },
    },
]


def _dump(obj: Dict[str, Any], path: Path) -> None:
    """Write ``obj`` as stable, sorted JSON (2-space indent, trailing newline)."""
    path.write_text(
        json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    _GOLDENS_DIR.mkdir(parents=True, exist_ok=True)

    seen_ids: set[str] = set()
    written: List[str] = []
    bureaus_hit: set[str] = set()
    stems_hit: set[str] = set()
    for case in CASES:
        case_id = case["case_id"]
        if case_id in seen_ids:
            raise SystemExit(f"duplicate case_id: {case_id!r}")
        seen_ids.add(case_id)

        request_id = f"req_zwds_{case_id}"
        response = compute_zwds_raw(
            case["request"],
            request_id=request_id,
            generated_at=GENERATED_AT,
        )
        golden = {
            "request": case["request"],
            "request_id": request_id,
            "generated_at": GENERATED_AT,
            "response": response,
        }
        _dump(golden, _GOLDENS_DIR / f"{case_id}.json")
        written.append(case_id)

        bureau = response["chart"]["five_elements_bureau"]["id"]
        stem = response["chart"]["birth_cycle"]["year_stem_id"]
        bureaus_hit.add(bureau)
        stems_hit.add(stem)
        print(f"  wrote {case_id}.json  (stem={stem}, bureau={bureau})")

    print(
        f"Wrote {len(written)} goldens to "
        f"{_GOLDENS_DIR.relative_to(_REPO_ROOT)}"
    )
    print(f"  bureaus hit ({len(bureaus_hit)}): {sorted(bureaus_hit)}")
    print(f"  stems hit ({len(stems_hit)}): {sorted(stems_hit)}")


if __name__ == "__main__":
    main()
