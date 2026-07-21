# Calculation Engine

**Responsibility**: Deterministic astronomical calculation engine — BaZi pillars, Western chart, Wu-Xing vectors, fusion, transit, aspects, phases, narrative generation, and provenance.

**Technology**: Python 3.10+ / Swiss Ephemeris (pyswisseph), frozen dataclasses, pure functions

## Source Mapping

Engine code lives in `bazi_engine/` (Levels 0–4 of the module hierarchy):

| Level | Modules |
|-------|---------|
| 0 | `constants.py` |
| 1 | `types.py`, `exc.py` |
| 2 | `ephemeris.py`, `time_utils.py`, `solar_time.py` |
| 3 | `jieqi.py` |
| 4 | `bazi.py`, `western.py`, `fusion.py`, `transit.py`, `aspects.py`, `narrative.py`, `provenance.py`, `wuxing/`, `phases/`, `research/` |

## Interfaces

- **Python class API** consumed by `api` component: `compute_bazi()`, `compute_western_chart()`, `compute_fusion()`, transit functions, aspect calculations
- **Swiss Ephemeris** (external): file-based ephemeris data via `SE_EPHE_PATH`

## Constraints

- All dataclasses use `frozen=True` — immutability is non-negotiable
- `DAY_OFFSET = 49` must not be modified
- Lower-level modules must never import higher-level modules (`test_import_hierarchy.py` enforces)
- Year boundary is LiChun (315° solar longitude), not Jan 1

## Requirements Addressed

Core calculation correctness, determinism, DST handling, solar-term boundary precision, Wu-Xing vector computation.

## Relevant Decisions

| File | Title | Trigger |
|------|-------|---------|
| — | Transit TTLCache (ADR-1) | When modifying transit calculations — 1-hour TTL cache |
| — | Immutable dataclasses | When adding/modifying data types — always `frozen=True` |
| — | Module hierarchy | When adding imports — respect level ordering |
