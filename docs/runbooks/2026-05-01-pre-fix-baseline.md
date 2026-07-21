# Pre-Fix Baseline (transient, deleted in Task 8)

Captured: 2026-05-01

## Test signals

- `pytest -q`: **2019 passed, 42 skipped, 14 warnings** in ~300s
- slowapi version: **0.1.9**

## Repository state

- `git status --short`: **18 items** (5 modified + 13 untracked)
- Modified: `.claude/homunculus/observations.jsonl`, `3-code/tasks.md`, `CLAUDE.md`, `tests/test_daily_eastern_jieqi.py`, `uv.lock`
- Untracked clutter at repo root: `0`, `FuFirE-main/`, `FuFirE_API_Strategy/`, `GEMINI.md`, `SDLC.md`, `ai-scrum-scaffold/`, `hardening/`
- Untracked working state: `bazi_engine/decanates_terms.py`, `tests/test_decanates_terms.py`, `docs/plans/2026-04-14-…`, `docs/plans/2026-04-30-…`, `docs/runbooks/phase4-…`

## Inspected stray items (Section C from plan)

| Item | Type | Size / Notes |
|------|------|--------------|
| `0` | file | 0 bytes (empty) — clearly accidental shell typo from 21 Apr 23:32 |
| `GEMINI.md` | file | 69 lines — Gemini-targeted project description, mirrors much of CLAUDE.md |
| `SDLC.md` | file | 204 lines — SDLC dashboard initialised 2026-03-30; mentions Fly.io as deploy target (now Railway, per CLAUDE.md) |
| `FuFirE-main/` | dir | 6.4 MB — full nested copy of project (own `__pycache__`, `api/`, `ai-scrum-scaffold/`); appears to be a local clone or extraction |
| `FuFirE_API_Strategy/` | dir | 6 long-form German .md files about API strategy / "Mathematik des Schicksals" — strategic docs from external research |
| `ai-scrum-scaffold/` | dir | SDLC scaffold (`1-spec/`, `2-design/`, `3-code/`, `4-deploy/`, `decisions/`, `docs/`, etc.) — full SDLC template |
| `hardening/` | dir | One .md file (`ein_wissenschaftlich_korrekter_testaufbau_muss_zue.md`) — German notes on testing strategy, references Bazodiac Risk Framework |

## Per-item decisions

(To be populated by Task 1 user gate)

| Item | Decision | Rationale |
|------|----------|-----------|
| `0` | **delete** | Empty file from shell typo |
| `GEMINI.md` | **commit** | Parallel to CLAUDE.md, intentional |
| `SDLC.md` | **delete** | Stale dashboard, contradicts CLAUDE.md (Fly vs Railway) |
| `FuFirE-main/` | **delete** | Leftover nested copy of project |
| `FuFirE_API_Strategy/` | **move to `docs/strategy/` + commit** | Real strategic docs, wrong location |
| `ai-scrum-scaffold/` | **delete** | Unused template scaffold |
| `hardening/` | **move file to `docs/research/2026-04-30-testing-strategy-de.md` + delete dir** | Real research note, wrong location |
