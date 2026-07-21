# Superglue Chart Request Defaulting

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make `POST /api/profile/{user_id}/chart` and `POST /v1/profile/{user_id}/chart` accept an omitted JSON body and default `force_recalculate=false` without breaking clients that already send an explicit body.

**Architecture:** Backward-compatible API contract change. `body: ChartRequest = ...` (required) → `body: Optional[ChartRequest] = Body(None)` (optional). Force value extracted with `body.force_recalculate if body is not None else False`. OpenAPI spec regenerated so the committed artifact stays in sync.

**Tech Stack:** FastAPI, Pydantic v2, respx (test mocking), `scripts/export_openapi.py`

---

## Status: IMPLEMENTED (2026-04-12)

This plan was implemented directly. See commit for diff. Tasks below are for reference only.

---

### Task 1: Make request body optional

**Files:**
- Modify: `bazi_engine/routers/superglue.py`

**Change:** In `trigger_user_chart`, replace:
```python
body: ChartRequest = ...
```
with:
```python
body: Optional[ChartRequest] = Body(None)
```

Add `from typing import Optional` and `from fastapi import ..., Body` to imports.

Extract force value:
```python
force = body.force_recalculate if body is not None else False
```

**Verification:** `POST /api/profile/{user_id}/chart` without body returns 200 (not 422).

---

### Task 2: Add regression tests

**Files:**
- Modify: `tests/test_superglue_router.py`

**Tests added:**
- `test_post_chart_omitted_body_defaults_to_no_force` — POST without body → 200, `force_recalculate=false` forwarded to Superglue
- `test_post_chart_force_recalculate_true` — POST with `{"force_recalculate": true}` → forwarded correctly

**Run:** `uv run pytest tests/test_superglue_router.py -v`
Expected: 11 passed → 14 passed

---

### Task 3: Regenerate OpenAPI spec

**Files:**
- Update: `spec/openapi/openapi.json` (auto-generated)

**Run:**
```bash
uv run python scripts/export_openapi.py
uv run python scripts/export_openapi.py --check  # must print: OK: OpenAPI spec is up-to-date.
```

The `requestBody` for `POST /api/profile/{user_id}/chart` becomes optional (`required: false`) in the generated spec.

---

## Context

**Root cause:** `body: ChartRequest = ...` used FastAPI's "required body" convention. Clients (e.g. ElevenLabs tool call, Superglue webhook) that omit the body receive `422 Field required`. Since `force_recalculate` defaults to `False` in the model, an absent body is semantically equivalent to `{"force_recalculate": false}`.

**Downstream impact:** Both legacy (`/api/`) and v1 (`/v1/`) route prefixes are covered because `app.py` mounts the same router under both prefixes. No other endpoints affected.
