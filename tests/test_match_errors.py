"""test_match_errors.py — REQ-009 error-envelope consistency (T10).

Binding contract anchors (docs/testing/bazi-hehun.acceptance-tests.md §1
REQ-009). T10 completes the REQ-009 error contract the T9 security slice
started:

- T-009-01 ``test_malformed_request_422_error_envelope`` (AC-009a):
  malformed payloads (wrong types, out-of-range coords, garbage date) each
  yield a 422 whose body validates against ``ErrorEnvelope.schema.json``,
  whose ``error`` names a client-input class, with per-field detail — never
  a 500.
- T-009-02 ``test_deferred_capabilities_rejected_422_stable_detail``
  (AC-009b): ``mode=raw_bazi`` and any unknown deferred-capability option
  (e.g. ``include_scores``) are rejected 422 with a stable envelope, NEVER
  500; the error contract reserves the ``ruleset_incomplete`` code
  (present in ``RESERVED_ERROR_CODES``, unused in the MVP).
- T-009-03 ``test_compute_failure_returns_502_or_503_envelope`` (AC-009c):
  a monkeypatched chart-computation failure returns ≥500 with an
  ErrorEnvelope and no internal exception text; an
  ``EphemerisUnavailableError`` maps to 503.
- T-009-04 ``test_422_never_echoes_birth_data_or_api_keys`` (AC-009d,
  AC-012a-adjacent): a request with sentinel birth data but the ``options``
  object absent (whole-body echo vector) AND, separately, a type-invalid
  ``person_b.date``, each carrying an api-key header with a sentinel key
  string, must produce a 422/4xx body containing NO sentinel birth value
  and NO key material.
- ``test_dst_error_does_not_echo_second_person_birth_instant`` (AC-009d,
  AC-012a): a nonexistent-DST-gap ``person_b.date`` reaches the shared
  ``resolve_local_iso`` nonexistent branch; the resulting 422 body must not
  echo the raw birth instant or timezone of the second person.

Class: integration-fake — every test runs against the assembled app.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, Dict
from unittest.mock import patch

from fastapi.testclient import TestClient
from jsonschema import Draft7Validator

from bazi_engine.app import app
from bazi_engine.exc import EphemerisUnavailableError
from tests.fixtures.match_payloads import SENTINEL_A, SENTINEL_B, VALID_MATCH_REQUEST

client = TestClient(app)

_MATCH_PATH = "/v1/match/bazi-hehun"

# Canonical ErrorEnvelope schema (contract §0.3): every error body below must
# validate against it — required {error, message, request_id}.
_REPO_ROOT = Path(__file__).resolve().parents[1]
_ERROR_ENVELOPE_SCHEMA = json.loads(
    (_REPO_ROOT / "spec" / "schemas" / "ErrorEnvelope.schema.json").read_text()
)

# Client-input error classes: the ``error`` code of a 422 must name one of
# these (Pydantic schema violation, DST/parse input error) — never a generic
# server code like ``http_error``/``internal_error``/``calculation_error``.
_INPUT_ERROR_CODES = frozenset(
    {"validation_error", "input_error", "dst_time_error", "consent_required"}
)


def _validate_envelope(body: Dict[str, Any]) -> None:
    Draft7Validator(_ERROR_ENVELOPE_SCHEMA).validate(body)
    for key in ("error", "message", "request_id"):
        assert key in body, f"ErrorEnvelope missing {key!r}: {body}"

# A distinctive sentinel API key — never valid, only present to prove it is
# never reflected into an error body / proxy log.
_SENTINEL_API_KEY = "ff_pro_SENTINELKEYleakcanary9x7q"

_SENTINEL_HEADERS = {
    "Authorization": f"Bearer {_SENTINEL_API_KEY}",
    "X-API-Key": _SENTINEL_API_KEY,
}

# Every raw birth value (as a substring) that must never surface in a 4xx body.
_SENTINEL_BIRTH_TOKENS = (
    "1988-06-04",
    "07:31",
    "Pacific/Chatham",
    "173.9391",
    "-43.9502",
    "1979-11-23",
    "22:04",
    "America/Caracas",
    "-66.9036",
    "10.4806",
)


def _assert_no_leak(raw_body: str) -> None:
    for token in _SENTINEL_BIRTH_TOKENS:
        assert token not in raw_body, f"birth sentinel {token!r} echoed in error body"
    assert _SENTINEL_API_KEY not in raw_body, "api-key material echoed in error body"


def _options_absent() -> Dict[str, Any]:
    """Full sentinel payload with the entire ``options`` object removed —
    forces Pydantic's root ``input`` echo to reflect BOTH persons' data."""
    req = copy.deepcopy(VALID_MATCH_REQUEST)
    req.pop("options", None)
    return req


def _type_invalid_person_b_date() -> Dict[str, Any]:
    """A structurally type-invalid ``person_b.date`` whose value embeds a
    sentinel — the offending value must not be echoed back."""
    req = copy.deepcopy(VALID_MATCH_REQUEST)
    req["person_b"] = {**SENTINEL_B, "date": {"raw": "1979-11-23T22:04:00"}}
    return req


def test_422_never_echoes_birth_data_or_api_keys() -> None:
    """T-009-04 / AC-009d — 422 bodies strip the default ``input`` echo."""
    r1 = client.post(_MATCH_PATH, json=_options_absent(), headers=_SENTINEL_HEADERS)
    assert r1.status_code == 422, r1.text
    _assert_no_leak(r1.text)

    r2 = client.post(
        _MATCH_PATH, json=_type_invalid_person_b_date(), headers=_SENTINEL_HEADERS
    )
    assert r2.status_code == 422, r2.text
    _assert_no_leak(r2.text)


def test_dst_error_does_not_echo_second_person_birth_instant() -> None:
    """AC-009d / AC-012a — the shared DST error message omits raw PII."""
    req = copy.deepcopy(VALID_MATCH_REQUEST)
    # 2024-03-31T02:30 does not exist in Europe/Berlin (spring-forward gap).
    req["person_b"] = {
        "date": "2024-03-31T02:30:00",
        "tz": "Europe/Berlin",
        "lon": 13.405,
        "lat": 52.52,
        "nonexistentTime": "error",
    }
    resp = client.post(_MATCH_PATH, json=req, headers=_SENTINEL_HEADERS)
    assert resp.status_code == 422, resp.text
    body = resp.text
    assert "2024-03-31T02:30:00" not in body, "raw second-person birth instant echoed"
    assert "Europe/Berlin" not in body, "second-person timezone echoed"


# ── T-009-01 — malformed payloads → 422 ErrorEnvelope (AC-009a) ───────────────
def _malformed_cases() -> list[tuple[str, Dict[str, Any], bool]]:
    """(label, payload, expect_per_field_detail) — each is a malformed request.

    The first three are Pydantic schema violations (wrong type / out of the
    declared coordinate range) that must surface as ``validation_error`` with
    per-field ``loc`` detail. The last is a garbage (unparseable) date string:
    it passes the ``str`` field but fails downstream time resolution, so it is
    still a client-input 422 but without a Pydantic ``loc`` list.
    """
    lon_wrong = copy.deepcopy(VALID_MATCH_REQUEST)
    lon_wrong["person_a"] = {**SENTINEL_A, "lon": "not-a-number"}
    date_wrong = copy.deepcopy(VALID_MATCH_REQUEST)
    date_wrong["person_a"] = {**SENTINEL_A, "date": 12345}
    lat_range = copy.deepcopy(VALID_MATCH_REQUEST)
    lat_range["person_a"] = {**SENTINEL_A, "lat": 999.0}
    garbage_date = copy.deepcopy(VALID_MATCH_REQUEST)
    garbage_date["person_a"] = {**SENTINEL_A, "date": "not-a-real-date"}
    return [
        ("lon_wrong_type", lon_wrong, True),
        ("date_wrong_type", date_wrong, True),
        ("lat_out_of_range", lat_range, True),
        ("garbage_date_string", garbage_date, False),
    ]


def test_malformed_request_422_error_envelope() -> None:
    """T-009-01 / AC-009a — malformed payloads are 422 ErrorEnvelopes."""
    for label, payload, per_field in _malformed_cases():
        resp = client.post(_MATCH_PATH, json=payload, headers=_SENTINEL_HEADERS)
        assert resp.status_code == 422, (label, resp.text)  # never 500
        body = resp.json()
        _validate_envelope(body)
        assert body["error"] in _INPUT_ERROR_CODES, (label, body)
        if per_field:
            errors = body.get("detail", {}).get("errors")
            assert isinstance(errors, list) and errors, (label, body)
            assert any("loc" in e for e in errors), (label, body)
        _assert_no_leak(resp.text)


# ── T-009-02 — deferred capabilities rejected + reserved code (AC-009b) ───────
def test_deferred_capabilities_rejected_422_stable_detail() -> None:
    """T-009-02 / AC-009b — deferred modes/options are 422, never 500."""
    raw_mode = copy.deepcopy(VALID_MATCH_REQUEST)
    raw_mode["mode"] = "raw_bazi"
    scoring_opt = copy.deepcopy(VALID_MATCH_REQUEST)
    scoring_opt["options"] = {**VALID_MATCH_REQUEST["options"], "include_scores": True}
    matrix_opt = copy.deepcopy(VALID_MATCH_REQUEST)
    matrix_opt["options"] = {
        **VALID_MATCH_REQUEST["options"],
        "include_ten_gods_matrix": True,
    }

    rejection_bodies = ""
    for label, payload in (
        ("raw_bazi", raw_mode),
        ("include_scores", scoring_opt),
        ("ten_gods_matrix", matrix_opt),
    ):
        resp = client.post(_MATCH_PATH, json=payload, headers=_SENTINEL_HEADERS)
        assert resp.status_code == 422, (label, resp.text)  # NEVER 500
        _validate_envelope(resp.json())
        _assert_no_leak(resp.text)
        rejection_bodies += resp.text

    # The error contract RESERVES ``ruleset_incomplete`` (documented, unused in
    # the MVP) — it must exist in the reserved-code set and never be emitted by
    # any live rejection path while the deferred tables are gated.
    from bazi_engine.routers.match import RESERVED_ERROR_CODES

    assert "ruleset_incomplete" in RESERVED_ERROR_CODES
    assert "ruleset_incomplete" not in rejection_bodies


# ── T-009-03 — compute failure → ≥500 / 503 ErrorEnvelope (AC-009c) ───────────
def test_compute_failure_returns_502_or_503_envelope() -> None:
    """T-009-03 / AC-009c — a compute failure is ≥500 with no internal text."""
    secret = "SECRET_INTERNAL_/opt/ephemeris/leak_canary_9x7q.se1"

    # Generic compute failure ⇒ ≥500, ErrorEnvelope, internal text stripped.
    with patch(
        "bazi_engine.routers.match.compute_bazi", side_effect=RuntimeError(secret)
    ):
        resp = client.post(_MATCH_PATH, json=VALID_MATCH_REQUEST, headers=_SENTINEL_HEADERS)
    assert resp.status_code >= 500, resp.text
    _validate_envelope(resp.json())
    assert secret not in resp.text, "internal exception text leaked into body"
    _assert_no_leak(resp.text)

    # EphemerisUnavailableError ⇒ 503 (service dependency down, retryable).
    with patch(
        "bazi_engine.routers.match.compute_bazi",
        side_effect=EphemerisUnavailableError("ephemeris files missing"),
    ):
        resp503 = client.post(
            _MATCH_PATH, json=VALID_MATCH_REQUEST, headers=_SENTINEL_HEADERS
        )
    assert resp503.status_code == 503, resp503.text
    body = resp503.json()
    _validate_envelope(body)
    assert body["error"] == "ephemeris_unavailable", body
    _assert_no_leak(resp503.text)
