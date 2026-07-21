"""ZWDS-P1-20/21 — HTTP-boundary tests for the /v1 ZWDS endpoints.

Assertions are made at the real boundary (``TestClient`` on ``resp.json()`` /
``resp.text``) per the WS-A retro. The full ``/v1/calculate/zwds`` path is
marked ``swieph`` (the calendar half converts the civil chart date onto the
lunisolar calendar via Swiss Ephemeris); every fail-fast path (metadata,
missing datetime, DST-gap PII scrub, catalog gate, ``/v1``-only, api-key)
errors out before any ephemeris call and runs everywhere.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict

import pytest
from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator

from bazi_engine.app import app

ROOT = Path(__file__).resolve().parents[2]
SCHEMA_DIR = ROOT / "spec" / "schemas" / "zwds"
RAW_RESPONSE_SCHEMA = SCHEMA_DIR / "ZwdsRawResponse.schema.json"
RESPONSE_EXAMPLE = ROOT / "docs" / "zwds" / "design-pack" / "response_example_core.json"

RULESET_ID = "zwds.fufire.core-seed.v1"


@pytest.fixture(autouse=True)
def _dev_mode_no_api_key(monkeypatch):
    """Force dev-mode auth bypass so /v1/* is reachable without a key.

    The dedicated api-key test overrides this in its own body. The
    ``_load_keys`` cache_clear stops a prior test's ``FUFIRE_API_KEYS`` from
    leaking an enforced key list into this module (mirrors
    tests/test_dst_pii_http.py).
    """
    monkeypatch.setenv("FUFIRE_REQUIRE_API_KEYS", "false")
    monkeypatch.setenv("FUFIRE_ENABLE_ZWDS", "true")
    monkeypatch.delenv("FUFIRE_API_KEYS", raising=False)
    from bazi_engine.auth import _load_keys

    _load_keys.cache_clear()
    yield
    _load_keys.cache_clear()


@pytest.fixture
def client() -> TestClient:
    return TestClient(app, raise_server_exceptions=False)


def _example_request() -> Dict[str, Any]:
    """The canonical design-pack ``normalized_input`` as a ZwdsRequest body."""
    normalized = json.loads(RESPONSE_EXAMPLE.read_text(encoding="utf-8"))[
        "normalized_input"
    ]
    return {
        "birth": dict(normalized["birth"]),
        "calculation": dict(normalized["calculation"]),
        "output": dict(normalized["output"]),
    }


# --- 1. metadata endpoint -----------------------------------------------------


def test_metadata_known_ruleset_returns_full_envelope(client):
    resp = client.get(f"/v1/metadata/zwds/rulesets/{RULESET_ID}")
    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert body["ruleset_id"] == RULESET_ID
    assert body["source_status"] == "SOURCE_NEEDED"
    assert body["release_status"] == "core-seed"
    assert body["human_review_required"] is True

    # every policy id is present and non-empty
    for policy_id in (
        "calendar_policy_id",
        "time_policy_id",
        "leap_month_policy_id",
        "year_cycle_policy_id",
        "star_catalog_id",
        "transformation_table_id",
        "age_reckoning_id",
    ):
        assert body[policy_id], f"missing policy id: {policy_id}"

    # exactly the five disclosed sha256 fingerprints (64-hex each)
    for sha_field in (
        "ruleset_sha256",
        "star_catalog_sha256",
        "transformation_table_sha256",
        "calendar_policy_sha256",
        "time_policy_sha256",
    ):
        assert re.fullmatch(r"[a-f0-9]{64}", body[sha_field]), sha_field


def test_metadata_unknown_ruleset_returns_404_envelope(client):
    resp = client.get("/v1/metadata/zwds/rulesets/does.not.exist.v9")
    assert resp.status_code == 404, resp.text
    body = resp.json()
    assert body["error"] == "zwds_ruleset_not_found"
    # ErrorEnvelope shape at the boundary
    assert body["status"] == 404
    assert body["path"] == "/v1/metadata/zwds/rulesets/does.not.exist.v9"
    assert "request_id" in body


# --- 2. calculate endpoint ----------------------------------------------------


@pytest.mark.swieph
def test_calculate_zwds_returns_schema_valid_chart(client):
    resp = client.post("/v1/calculate/zwds", json=_example_request())
    assert resp.status_code == 200, resp.text
    body = resp.json()

    schema = json.loads(RAW_RESPONSE_SCHEMA.read_text(encoding="utf-8"))
    errors = sorted(
        Draft202012Validator(schema).iter_errors(body),
        key=lambda e: list(e.path),
    )
    assert errors == [], "; ".join(
        f"{list(e.path)}: {e.message}" for e in errors
    )

    assert body["chart"]["ming_palace_branch_id"] == "YIN"
    assert body["chart"]["five_elements_bureau"]["id"] == "FIRE_6"
    assert len(body["chart"]["star_placements"]) == 18


# --- 3. missing birth time ----------------------------------------------------


def test_missing_datetime_local_is_a_4xx(client):
    req = _example_request()
    del req["birth"]["datetime_local"]
    resp = client.post("/v1/calculate/zwds", json=req)
    assert 400 <= resp.status_code < 500, resp.text
    assert resp.json()["error"] in {"zwds_birth_time_required", "validation_error"}


def test_omitted_birth_is_a_4xx(client):
    req = _example_request()
    del req["birth"]
    resp = client.post("/v1/calculate/zwds", json=req)
    assert 400 <= resp.status_code < 500, resp.text
    assert resp.json()["error"] in {"zwds_birth_time_required", "validation_error"}


# --- 4. DST spring-forward gap — 422 with NO PII in the body ------------------


def test_dst_gap_returns_422_without_pii(client):
    req = _example_request()
    req["birth"]["datetime_local"] = "2024-03-31T02:30:00"
    req["birth"]["timezone"] = "Europe/Berlin"
    req["birth"]["nonexistentTime"] = "error"

    resp = client.post("/v1/calculate/zwds", json=req)
    assert resp.status_code == 422, resp.text
    body = resp.text
    assert "02:30" not in body, f"raw birth instant leaked: {body}"
    assert "2024-03-31" not in body, f"raw birth date leaked: {body}"


# --- 5. unsupported catalog toggle -------------------------------------------


def test_include_catalog_true_is_scope_unavailable(client):
    req = _example_request()
    req["output"]["include_catalog"] = True
    resp = client.post("/v1/calculate/zwds", json=req)
    assert 400 <= resp.status_code < 500, resp.text
    assert resp.json()["error"] == "zwds_requested_scope_unavailable"


# --- 6. /v1-only — no legacy alias -------------------------------------------


def test_legacy_calculate_path_is_404(client):
    resp = client.post("/calculate/zwds", json=_example_request())
    assert resp.status_code == 404, resp.text


def test_legacy_metadata_path_is_404(client):
    resp = client.get(f"/metadata/zwds/rulesets/{RULESET_ID}")
    assert resp.status_code == 404, resp.text


# --- 7. API-key enforcement ---------------------------------------------------


def test_v1_zwds_routes_require_api_key(monkeypatch):
    """With FUFIRE_API_KEYS configured, calls without a key are rejected."""
    monkeypatch.setenv("FUFIRE_REQUIRE_API_KEYS", "true")
    monkeypatch.setenv("FUFIRE_API_KEYS", "ff_pro_zwds_test_key_0001")
    from bazi_engine.auth import _load_keys

    _load_keys.cache_clear()
    try:
        c = TestClient(app, raise_server_exceptions=False)

        calc = c.post("/v1/calculate/zwds", json=_example_request())
        assert calc.status_code in (401, 403), calc.text

        meta = c.get(f"/v1/metadata/zwds/rulesets/{RULESET_ID}")
        assert meta.status_code in (401, 403), meta.text

        # sanity: a valid key passes the auth gate on the metadata route
        ok = c.get(
            f"/v1/metadata/zwds/rulesets/{RULESET_ID}",
            headers={"X-API-Key": "ff_pro_zwds_test_key_0001"},
        )
        assert ok.status_code == 200, ok.text
    finally:
        _load_keys.cache_clear()
