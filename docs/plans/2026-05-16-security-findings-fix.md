# Security Findings Fix Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix all actionable security findings from the 2026-05-16 API security assessment — error envelope consistency, lat/lon input validation, tier-based rate limiting, and security header hardening.

**Architecture:** Five focused TDD tasks, each touching one concern. No new abstractions — minimal surgical edits. Tier-based rate limiting is the most cross-cutting change (adds one helper to `limiter.py`, updates eight router decorators). All tests go in `tests/test_security_findings.py` (new file).

**Tech Stack:** FastAPI, Pydantic v2, slowapi, pytest, starlette TestClient

---

## Findings addressed

| ID | Severity | Finding |
|---|---|---|
| ERR-1 | LOW | `webhooks.py`, `validate.py`, `western.py` raise `HTTPException` with `detail=<str>`, breaking the error envelope. Clients see `error: "http_error"` instead of the correct code. |
| INPUT-1 | LOW | `lat`/`lon` fields in `bazi.py`, `western.py`, `fusion.py`, `chart.py` have no range constraints. Values like `lat=9999` reach Swiss Ephemeris. |
| RATE-1 | MEDIUM | `@limiter.limit("30/minute")` decorators are static; they ignore key tier. A free-tier key (5/min) gets 30/min. |
| CORS-1 | INFO | `Content-Security-Policy` header absent from all responses. |
| AUTH-1 | LOW | No startup warning when `FUFIRE_API_KEYS` contains an `ff_enterprise_` key. Operator accidents grant unlimited access silently. |

**Not fixed here (by design):**
- IDOR-1: Superglue `user_id` routes are service-to-service (ElevenLabs agent key, not end-user keys). No code change needed; architecture note added in Task 5.
- RATE-2: Redis is already documented as optional in `limiter.py`. Multi-worker caveat will be added to that module's docstring in Task 5.
- CREDS-1: Superglue requires `?token=` in the URL. Operational risk documented.

---

## Task 1: Fix error envelopes (ERR-1)

**Files:**
- Create: `tests/test_security_findings.py`
- Modify: `bazi_engine/routers/webhooks.py:296`
- Modify: `bazi_engine/routers/validate.py:63-64`
- Modify: `bazi_engine/routers/western.py:115-117`

### Step 1: Write the failing tests

Create `tests/test_security_findings.py`:

```python
"""
Security findings regression tests.
Each test documents one finding from the 2026-05-16 security assessment.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

from bazi_engine.app import app

client = TestClient(app, raise_server_exceptions=False)

_API_KEY_HEADERS = {}  # dev-mode: no keys configured → no auth needed


# ── ERR-1: Error envelope consistency ─────────────────────────────────────────

def test_validate_valueerror_returns_structured_envelope():
    """validate.py ValueError must produce error='validation_error', not 'http_error'."""
    # Send a payload that causes a ValueError inside bafe_validate_request.
    # An empty payload with required fields missing triggers schema validation.
    resp = client.post("/v1/validate", json={}, headers=_API_KEY_HEADERS)
    # Either 422 or 500 is acceptable — we only care about the envelope shape.
    body = resp.json()
    assert "error" in body, "Missing 'error' key in response"
    assert body["error"] != "http_error", (
        f"validate.py is leaking 'http_error' — expected a specific error code, got: {body}"
    )
    assert "request_id" in body


def test_western_router_500_returns_structured_envelope():
    """western.py unhandled Exception must return a structured envelope, not bare string."""
    # Patch compute_western_chart to raise an unexpected exception.
    with patch("bazi_engine.routers.western.compute_western_chart", side_effect=RuntimeError("boom")):
        resp = client.post(
            "/v1/calculate/western",
            json={
                "date": "1990-06-15T14:30:00",
                "tz": "Europe/Berlin",
                "lon": 13.405,
                "lat": 52.52,
            },
            headers=_API_KEY_HEADERS,
        )
    assert resp.status_code == 500
    body = resp.json()
    assert body.get("error") not in (None, "http_error"), (
        f"western.py returns bare string detail: {body}"
    )
    assert "request_id" in body
```

### Step 2: Run to verify they fail

```bash
pytest tests/test_security_findings.py::test_validate_valueerror_returns_structured_envelope \
       tests/test_security_findings.py::test_western_router_500_returns_structured_envelope -v
```

Expected: at least one FAIL (the validate test may pass if BAFE raises before the ValueError path; the western test should fail showing `error='http_error'`).

### Step 3: Fix `bazi_engine/routers/webhooks.py`

Find the bare-string exception at line 296 (inside the final `except Exception` block):

```python
# BEFORE (line ~293-296):
    except LocalTimeError as e:
        raise HTTPException(status_code=422, detail={
            "error": str(e),
            "hint": "The given birth time does not exist. Please provide a valid local time.",
        })
    except BaziEngineError:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="Internal calculation error")

# AFTER:
    except LocalTimeError as e:
        raise HTTPException(status_code=422, detail={
            "error": str(e),
            "hint": "The given birth time does not exist. Please provide a valid local time.",
        })
    except BaziEngineError:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail={
            "error": "calculation_error",
            "message": "Internal calculation error",
            "detail": {},
        })
```

### Step 4: Fix `bazi_engine/routers/validate.py`

Find the `except ValueError` block (line ~63):

```python
# BEFORE:
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

# AFTER:
    except ValueError as e:
        raise HTTPException(status_code=422, detail={
            "error": "validation_error",
            "message": str(e),
            "detail": {},
        })
```

### Step 5: Fix `bazi_engine/routers/western.py`

Find the bare-string exception at line ~117:

```python
# BEFORE:
        raise HTTPException(status_code=500, detail="Internal calculation error")

# AFTER:
        raise HTTPException(status_code=500, detail={
            "error": "calculation_error",
            "message": "Internal calculation error",
            "detail": {},
        })
```

### Step 6: Run tests to verify they pass

```bash
pytest tests/test_security_findings.py::test_validate_valueerror_returns_structured_envelope \
       tests/test_security_findings.py::test_western_router_500_returns_structured_envelope -v
```

Expected: both PASS.

### Step 7: Full regression check

```bash
pytest -q --tb=short
```

Expected: no new failures.

### Step 8: Commit

```bash
git add bazi_engine/routers/webhooks.py \
        bazi_engine/routers/validate.py \
        bazi_engine/routers/western.py \
        tests/test_security_findings.py
git commit -m "fix(security): replace bare-string HTTPException detail with structured envelope (ERR-1)"
```

---

## Task 2: Add lat/lon range validation (INPUT-1)

**Files:**
- Modify: `bazi_engine/routers/bazi.py` — `BaziRequest.lat`, `BaziRequest.lon`
- Modify: `bazi_engine/routers/western.py` — `WesternRequest.lat`, `WesternRequest.lon`
- Modify: `bazi_engine/routers/fusion.py` — `FusionRequest.lat`, `FusionRequest.lon`
- Modify: `bazi_engine/routers/chart.py` — `geo_lat_deg`, `geo_lon_deg`
- Test: `tests/test_security_findings.py`

### Step 1: Write the failing tests

Append to `tests/test_security_findings.py`:

```python
# ── INPUT-1: Lat/lon range validation ─────────────────────────────────────────

@pytest.mark.parametrize("endpoint,payload_key", [
    ("/v1/calculate/bazi", {"date": "1990-06-15T14:30:00", "tz": "Europe/Berlin"}),
    ("/v1/calculate/western", {"date": "1990-06-15T14:30:00", "tz": "Europe/Berlin"}),
    ("/v1/calculate/fusion", {"date": "1990-06-15T14:30:00", "tz": "Europe/Berlin"}),
])
def test_out_of_range_lat_rejected(endpoint, payload_key):
    """Latitudes outside [-90, 90] must be rejected with 422."""
    payload = {**payload_key, "lat": 9999.0, "lon": 13.405}
    resp = client.post(endpoint, json=payload, headers=_API_KEY_HEADERS)
    assert resp.status_code == 422, (
        f"{endpoint}: lat=9999 was accepted (status={resp.status_code})"
    )


@pytest.mark.parametrize("endpoint,payload_key", [
    ("/v1/calculate/bazi", {"date": "1990-06-15T14:30:00", "tz": "Europe/Berlin"}),
    ("/v1/calculate/western", {"date": "1990-06-15T14:30:00", "tz": "Europe/Berlin"}),
    ("/v1/calculate/fusion", {"date": "1990-06-15T14:30:00", "tz": "Europe/Berlin"}),
])
def test_out_of_range_lon_rejected(endpoint, payload_key):
    """Longitudes outside [-180, 180] must be rejected with 422."""
    payload = {**payload_key, "lat": 52.52, "lon": -99999.0}
    resp = client.post(endpoint, json=payload, headers=_API_KEY_HEADERS)
    assert resp.status_code == 422, (
        f"{endpoint}: lon=-99999 was accepted (status={resp.status_code})"
    )
```

### Step 2: Run to verify they fail

```bash
pytest tests/test_security_findings.py -k "lat_rejected or lon_rejected" -v
```

Expected: all 6 tests FAIL (values currently accepted).

### Step 3: Fix `bazi_engine/routers/bazi.py`

```python
# BEFORE:
    lon: float = Field(13.4050, description="Longitude in degrees")
    lat: float = Field(52.52, description="Latitude in degrees")

# AFTER:
    lon: float = Field(13.4050, ge=-180.0, le=180.0, description="Longitude in degrees")
    lat: float = Field(52.52, ge=-90.0, le=90.0, description="Latitude in degrees")
```

### Step 4: Fix `bazi_engine/routers/western.py`

```python
# BEFORE:
    lon: float = Field(13.4050, description="Longitude in degrees")
    lat: float = Field(52.52, description="Latitude in degrees")

# AFTER:
    lon: float = Field(13.4050, ge=-180.0, le=180.0, description="Longitude in degrees")
    lat: float = Field(52.52, ge=-90.0, le=90.0, description="Latitude in degrees")
```

### Step 5: Fix `bazi_engine/routers/fusion.py`

```python
# BEFORE:
    lon: float = Field(..., description="Longitude in degrees")
    lat: float = Field(..., description="Latitude in degrees")

# AFTER:
    lon: float = Field(..., ge=-180.0, le=180.0, description="Longitude in degrees")
    lat: float = Field(..., ge=-90.0, le=90.0, description="Latitude in degrees")
```

### Step 6: Fix `bazi_engine/routers/chart.py`

Locate `geo_lon_deg` and `geo_lat_deg` fields:

```python
# BEFORE:
    geo_lon_deg: float = Field(13.4050, description="Geographic longitude in degrees")
    geo_lat_deg: float = Field(52.5200, description="Geographic latitude in degrees")

# AFTER:
    geo_lon_deg: float = Field(13.4050, ge=-180.0, le=180.0, description="Geographic longitude in degrees")
    geo_lat_deg: float = Field(52.5200, ge=-90.0, le=90.0, description="Geographic latitude in degrees")
```

### Step 7: Run tests to verify they pass

```bash
pytest tests/test_security_findings.py -k "lat_rejected or lon_rejected" -v
```

Expected: all 6 PASS.

### Step 8: Full regression check

```bash
pytest -q --tb=short
```

Expected: no new failures.

### Step 9: Commit

```bash
git add bazi_engine/routers/bazi.py \
        bazi_engine/routers/western.py \
        bazi_engine/routers/fusion.py \
        bazi_engine/routers/chart.py \
        tests/test_security_findings.py
git commit -m "fix(security): add lat/lon range validators [ge=-90/90, ge=-180/180] across all routers (INPUT-1)"
```

---

## Task 3: Tier-based dynamic rate limits (RATE-1)

The current `@limiter.limit("30/minute")` decorators use static strings. slowapi supports callables that receive `(Request) -> str`. We add `tier_limit` to `limiter.py` and update all eight decorated endpoints.

**Files:**
- Modify: `bazi_engine/limiter.py` — add `tier_limit` function
- Modify: `bazi_engine/routers/bazi.py`
- Modify: `bazi_engine/routers/western.py`
- Modify: `bazi_engine/routers/fusion.py`
- Modify: `bazi_engine/routers/transit.py`
- Modify: `bazi_engine/routers/experience.py`
- Modify: `bazi_engine/routers/impact.py`
- Modify: `bazi_engine/routers/superglue.py`
- Modify: `bazi_engine/routers/validate.py`
- Test: `tests/test_security_findings.py`

### Step 1: Write failing tests

Append to `tests/test_security_findings.py`:

```python
# ── RATE-1: Tier-based rate limits ────────────────────────────────────────────

def test_tier_limit_helper_free_tier():
    """tier_limit() must return '5/minute' for a free-tier key_info."""
    from starlette.testclient import _TestClientTransport
    from starlette.requests import Request
    from bazi_engine.limiter import tier_limit
    from bazi_engine.auth import KeyInfo

    # Build a minimal mock Request with free-tier key_info on state
    scope = {"type": "http", "method": "GET", "path": "/", "query_string": b"",
             "headers": [], "state": MagicMock()}
    req = Request(scope)
    req.state.key_info = KeyInfo(key="ff_free_test", tier="free",
                                 requests_per_day=100, requests_per_minute=5)
    assert tier_limit(req) == "5/minute"


def test_tier_limit_helper_enterprise_tier():
    """tier_limit() must return a high limit for enterprise (rpm=0)."""
    from starlette.requests import Request
    from bazi_engine.limiter import tier_limit
    from bazi_engine.auth import KeyInfo

    scope = {"type": "http", "method": "GET", "path": "/", "query_string": b"",
             "headers": [], "state": MagicMock()}
    req = Request(scope)
    req.state.key_info = KeyInfo(key="ff_enterprise_test", tier="enterprise",
                                 requests_per_day=0, requests_per_minute=0)
    result = tier_limit(req)
    # Enterprise: returned string should represent a very high limit, not "0/minute"
    assert "/minute" in result
    limit_val = int(result.split("/")[0])
    assert limit_val >= 1000, f"Enterprise limit too low: {result}"


def test_tier_limit_helper_no_key_info():
    """tier_limit() must return a sensible fallback when key_info is absent."""
    from starlette.requests import Request
    from bazi_engine.limiter import tier_limit

    scope = {"type": "http", "method": "GET", "path": "/", "query_string": b"",
             "headers": [], "state": MagicMock(spec=[])}
    req = Request(scope)
    result = tier_limit(req)
    assert "/minute" in result
```

### Step 2: Run to verify they fail

```bash
pytest tests/test_security_findings.py -k "tier_limit" -v
```

Expected: ImportError (`tier_limit` not yet defined) or AttributeError.

### Step 3: Add `tier_limit` to `bazi_engine/limiter.py`

At the end of `limiter.py`, after `reset_limiter_storage`, add:

```python
def tier_limit(request: Request) -> str:
    """Return a slowapi limit string based on the authenticated key's tier.

    Called by @limiter.limit(tier_limit) on every protected endpoint.
    Enterprise keys (rpm=0) get an effectively unlimited rate (10 000/min).
    When key_info is absent (dev-mode, public endpoints) fall back to 30/min.
    """
    key_info = getattr(getattr(request, "state", None), "key_info", None)
    if key_info is None:
        return "30/minute"
    if key_info.requests_per_minute == 0:
        # Enterprise tier — unlimited. Use a high ceiling so slowapi still tracks.
        return "10000/minute"
    return f"{key_info.requests_per_minute}/minute"
```

### Step 4: Run tests to verify `tier_limit` tests pass

```bash
pytest tests/test_security_findings.py -k "tier_limit" -v
```

Expected: all 3 PASS.

### Step 5: Update all router decorators

In each router file below, change every `@limiter.limit("30/minute")` and `@limiter.limit("60/minute")` to `@limiter.limit(tier_limit)`.

Also add the import at the top of each router: `from ..limiter import limiter, tier_limit`

**`bazi_engine/routers/bazi.py`** (1 occurrence — line ~199):
```python
# BEFORE: from ..limiter import limiter
# AFTER:
from ..limiter import limiter, tier_limit

# BEFORE: @limiter.limit("30/minute")
# AFTER:  @limiter.limit(tier_limit)
```

**`bazi_engine/routers/western.py`** (1 occurrence):
```python
from ..limiter import limiter, tier_limit
# @limiter.limit("30/minute") → @limiter.limit(tier_limit)
```

**`bazi_engine/routers/fusion.py`** (1 occurrence):
```python
from ..limiter import limiter, tier_limit
# @limiter.limit("30/minute") → @limiter.limit(tier_limit)
```

**`bazi_engine/routers/transit.py`** (1 occurrence — `"60/minute"`):
```python
from ..limiter import limiter, tier_limit
# @limiter.limit("60/minute") → @limiter.limit(tier_limit)
```

**`bazi_engine/routers/experience.py`** (3 occurrences — mix of 30 and 60):
```python
from ..limiter import limiter, tier_limit
# All @limiter.limit("30/minute") → @limiter.limit(tier_limit)
# All @limiter.limit("60/minute") → @limiter.limit(tier_limit)
```

**`bazi_engine/routers/impact.py`** (1 occurrence):
```python
from ..limiter import limiter, tier_limit
# @limiter.limit("30/minute") → @limiter.limit(tier_limit)
```

**`bazi_engine/routers/superglue.py`** (4 occurrences — profile, daily, trigger_chart, query variants):
```python
from ..limiter import limiter, tier_limit
# All @limiter.limit("30/minute") → @limiter.limit(tier_limit)
# @limiter.limit("10/minute") → @limiter.limit(tier_limit)
```

**`bazi_engine/routers/validate.py`** (1 occurrence — `"60/minute"`):
```python
from ..limiter import limiter, tier_limit
# @limiter.limit("60/minute") → @limiter.limit(tier_limit)
```

### Step 6: Full regression check

```bash
pytest -q --tb=short
```

Expected: no new failures. The rate-limiting behaviour in tests is transparent (limits are high relative to test call counts).

### Step 7: Verify `tier_limit` is referenced in all routers

```bash
grep -rn "@limiter.limit" bazi_engine/routers/ --include="*.py"
```

Expected: every line shows `tier_limit`, none show a quoted string literal like `"30/minute"` or `"60/minute"`.

### Step 8: Commit

```bash
git add bazi_engine/limiter.py \
        bazi_engine/routers/bazi.py \
        bazi_engine/routers/western.py \
        bazi_engine/routers/fusion.py \
        bazi_engine/routers/transit.py \
        bazi_engine/routers/experience.py \
        bazi_engine/routers/impact.py \
        bazi_engine/routers/superglue.py \
        bazi_engine/routers/validate.py \
        tests/test_security_findings.py
git commit -m "fix(security): enforce tier-based rate limits via tier_limit() callable; replace static '30/minute' decorators (RATE-1)"
```

---

## Task 4: Security header hardening (CORS-1 + AUTH-1)

**Files:**
- Modify: `bazi_engine/middleware.py` — add `Content-Security-Policy`
- Modify: `bazi_engine/auth.py` — add enterprise key startup warning
- Test: `tests/test_security_findings.py`

### Step 1: Write failing tests

Append to `tests/test_security_findings.py`:

```python
# ── CORS-1: Content-Security-Policy header ────────────────────────────────────

def test_csp_header_present_on_api_response():
    """All API responses must include Content-Security-Policy."""
    resp = client.get("/health")
    assert "content-security-policy" in {k.lower() for k in resp.headers}, (
        "Missing Content-Security-Policy header"
    )
    # For a pure JSON API, 'none' is the correct restrictive policy.
    assert "default-src" in resp.headers.get("content-security-policy", "").lower()


# ── AUTH-1: Enterprise key startup warning ────────────────────────────────────

def test_enterprise_key_warning_logged(caplog):
    """_load_keys() must emit a warning when an enterprise-prefixed key is present."""
    import logging
    from bazi_engine.auth import _load_keys, _load_tier_overrides

    _load_keys.cache_clear()
    _load_tier_overrides.cache_clear()

    with patch.dict("os.environ", {"FUFIRE_API_KEYS": "ff_enterprise_abc123,ff_pro_xyz"}):
        with caplog.at_level(logging.WARNING, logger="bazi_engine.auth"):
            _load_keys()

    _load_keys.cache_clear()
    _load_tier_overrides.cache_clear()

    assert any(
        "enterprise" in record.message.lower() for record in caplog.records
    ), f"No enterprise key warning logged. Records: {[r.message for r in caplog.records]}"
```

### Step 2: Run to verify they fail

```bash
pytest tests/test_security_findings.py -k "csp_header or enterprise_key" -v
```

Expected: both FAIL.

### Step 3: Add CSP header to `bazi_engine/middleware.py`

In `dispatch`, after the existing `.setdefault(...)` calls, add:

```python
# EXISTING BLOCK (find this):
        response.headers.setdefault("Permissions-Policy", "accelerometer=(),camera=(),geolocation=(),microphone=()")
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")

# ADD THIS LINE AFTER:
        response.headers.setdefault("Content-Security-Policy", "default-src 'none'")
```

### Step 4: Add enterprise key warning to `bazi_engine/auth.py`

In `_load_keys()`, after building the `frozenset`, add the warning before returning:

```python
# BEFORE (end of _load_keys):
    return frozenset(k.strip() for k in raw.split(",") if k.strip())

# AFTER:
    keys = frozenset(k.strip() for k in raw.split(",") if k.strip())
    enterprise_keys = [k for k in keys if k.startswith("ff_enterprise_")]
    if enterprise_keys:
        _log.warning(
            "auth.enterprise_keys_detected count=%d key_suffixes=%s — "
            "verify these are intentionally enterprise tier",
            len(enterprise_keys),
            [k[-6:] for k in enterprise_keys],  # last 6 chars only
        )
    return keys
```

### Step 5: Run tests to verify they pass

```bash
pytest tests/test_security_findings.py -k "csp_header or enterprise_key" -v
```

Expected: both PASS.

### Step 6: Full regression check

```bash
pytest -q --tb=short
```

Expected: no new failures.

### Step 7: Commit

```bash
git add bazi_engine/middleware.py \
        bazi_engine/auth.py \
        tests/test_security_findings.py
git commit -m "fix(security): add Content-Security-Policy header; log warning on enterprise key presence (CORS-1, AUTH-1)"
```

---

## Task 5: Document open/accepted risks

**Files:**
- Modify: `docs/precision/deviations.md` — add DEV-2026-009 (deferred from Phase 2) and three security risk entries

### Step 1: Append to `docs/precision/deviations.md`

Add these entries to the existing deviations file:

```markdown
---

## DEV-2026-009

**ID:** DEV-2026-009
**Title:** `_build_derivation_trace` re-derives `sexagenary_index` independently — stale for TLST inputs
**Severity:** Medium (data quality)
**Component:** `bazi_engine/routers/bazi.py` → `_build_derivation_trace`
**Evidence:** The derivation trace re-computes `sexagenary_index` using `jdn_gregorian(chart_local_dt)` + `DAY_OFFSET`, which does not account for TLST-based day rollover (FBP-02-004). For TLST inputs near the Zi boundary (22:50–23:10), the trace may show the wrong day index.
**Status:** Deferred to Phase 3 (FBP-03-002 — Typed Derivation Trace).
**Owner:** Phase 3 executor

---

## SEC-2026-001

**ID:** SEC-2026-001
**Title:** IDOR risk accepted — Superglue user_id routes are service-to-service only
**Severity:** Low (accepted design risk)
**Component:** `bazi_engine/routers/superglue.py`
**Evidence:** `GET /v1/api/profile/{user_id}` and `/v1/api/daily/{user_id}` accept any `user_id` from any valid API key. If end-user keys are ever issued, users can query each other's profiles.
**Decision:** Accepted. These routes are called exclusively by the ElevenLabs agent service (one shared service API key), not by end users. If end-user keys are ever issued, ownership checking must be added here.
**Owner:** Architecture review before issuing end-user keys
**Status:** Accepted / Monitor

---

## SEC-2026-002

**ID:** SEC-2026-002
**Title:** Rate limits not shared across workers without Redis
**Severity:** Low (operational)
**Component:** `bazi_engine/limiter.py`
**Evidence:** When `REDIS_URL` is absent, in-memory counters are per-process. N Railway workers each get their own counter → actual burst capacity is N × advertised limit.
**Decision:** Redis is required for correct rate enforcement in multi-worker deployments. `REDIS_URL` must be set in Railway production secrets.
**Owner:** DevOps / Railway configuration
**Status:** Open — pending Redis provisioning confirmation

---

## SEC-2026-003

**ID:** SEC-2026-003
**Title:** Superglue API token in URL query parameter (`?token=`)
**Severity:** Low (operational, required by Superglue API)
**Component:** `bazi_engine/services/superglue_client.py`
**Evidence:** Token appears in upstream Superglue access logs. This is required by Superglue's hook API — no alternative auth mechanism is available.
**Decision:** Accepted. Monitor for Superglue to offer header-based auth. Consider rotating the token periodically.
**Owner:** Backend maintainer
**Status:** Accepted / Watch
```

### Step 2: Run full test suite one final time

```bash
pytest -q --tb=short
```

Expected: all tests pass, no regressions.

### Step 3: Commit

```bash
git add docs/precision/deviations.md
git commit -m "docs(security): add DEV-2026-009 and SEC-2026-001/002/003 to deviations register"
```

---

## Final verification checklist

```bash
# All security finding tests pass
pytest tests/test_security_findings.py -v

# No regressions anywhere
pytest -q --tb=short

# Verify no static rate limit strings remain in routers
grep -rn "@limiter.limit" bazi_engine/routers/ --include="*.py"
# Expected: all lines show tier_limit, no quoted "30/minute" or "60/minute"

# Verify CSP header is present
python -c "
from fastapi.testclient import TestClient
from bazi_engine.app import app
c = TestClient(app)
r = c.get('/health')
print('CSP:', r.headers.get('content-security-policy'))
"
# Expected: Content-Security-Policy: default-src 'none'
```
