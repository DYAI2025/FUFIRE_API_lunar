"""test_match_privacy.py — REQ-012 privacy defaults + server-side consent.

Binding contract anchors (docs/testing/bazi-hehun.acceptance-tests.md §1
REQ-012, docs/plans/2026-07-02-bazi-hehun.md §5). This file carries the
consent-gate + log-redaction subset that guards the T9 security fix
(consent bypass + PII echo). The remaining REQ-012 cases (T-012-04/05/06,
persistence + hash-log + copy scan) land with T10/T11.

- T-012-01 ``test_consent_absent_returns_422`` (AC-012c): omitting the
  consent boolean yields a 422 naming the field; the schema path to the
  field is fully ``required`` in OpenAPI (no optional ancestor).
- T-012-02 ``test_consent_false_returns_422`` (AC-012c / D5): a ``false``
  consent value is REJECTED with a stable consent-specific detail code —
  never 200-with-a-warning. This is the server-side consent gate; without
  it the endpoint would compute the non-consenting second person's chart.
- T-012-03 ``test_no_raw_birth_data_in_logs_at_any_level`` (AC-012a,
  EV-005): a ROOT-logger DEBUG capture over both the happy path and the
  consent-absent 422 path contains none of the sentinel birth values.
- T-012-04 ``test_consent_value_is_hash_logged_with_request_id`` (AC-012f):
  the match privacy logger emits at least one record tying the request_id
  to a documented 64-hex sha256 hash of the consent value — and that audit
  record carries NO person field (T11).
- T-012-05 ``test_persist_raw_defaults_false_and_no_raw_artifact_written``
  (AC-012b): ``persist_raw`` defaults ``false`` in the published schema and
  no raw birth artifact is written to disk for a valid request — even when
  ``persist_raw`` is explicitly ``true`` (no persistence path exists) (T11).

Class: integration-fake — every test runs against the assembled app.
"""
from __future__ import annotations

import copy
import json
import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, List

from fastapi.testclient import TestClient

from bazi_engine.app import app
from tests.fixtures.match_payloads import SENTINEL_A, SENTINEL_B, VALID_MATCH_REQUEST

client = TestClient(app)

_MATCH_PATH = "/v1/match/bazi-hehun"

# Documented match-privacy logger namespace (T11 / AC-012f). The consent
# audit record is emitted here so the caplog scan can target it and so
# operators can route/redact it independently of the app loggers.
_PRIVACY_LOGGER = "bazi_engine.match.privacy"

# A lowercase 64-char hex sha256 digest — the documented consent-hash form.
_SHA256_HEX = re.compile(r"\b[0-9a-f]{64}\b")

# The distinctive sentinel substrings (contract §0.2 / §T-012-03). Their
# presence in any returned error body or any captured log record is a
# lexically-falsifiable privacy failure.
_SENTINEL_TOKENS = (
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


def _without_consent_field() -> Dict[str, Any]:
    """VALID_MATCH_REQUEST minus the consent boolean (options object kept)."""
    req = copy.deepcopy(VALID_MATCH_REQUEST)
    req["options"].pop("second_person_consent_confirmed", None)
    return req


def _with_consent(value: bool) -> Dict[str, Any]:
    req = copy.deepcopy(VALID_MATCH_REQUEST)
    req["options"]["second_person_consent_confirmed"] = value
    return req


def _with_persist_raw(value: bool) -> Dict[str, Any]:
    req = copy.deepcopy(VALID_MATCH_REQUEST)
    req["options"]["persist_raw"] = value
    return req


def _all_log_text(records: List[logging.LogRecord]) -> str:
    """Flatten every captured record (message + args + formatted) to one blob."""
    chunks: List[str] = []
    for rec in records:
        chunks.append(rec.getMessage())
        chunks.append(str(rec.args))
        chunks.append(str(getattr(rec, "msg", "")))
    return "\n".join(chunks)


def _every_request_field_value() -> List[str]:
    """Every distinctive leaf value from BOTH person payloads (T11 scan).

    The prompt binds a *full-record scan for EVERY request field value*: the
    curated §0.2 sentinels PLUS the raw ``str()`` form of each person field
    (e.g. the full ``1988-06-04T07:31:00`` datetime and the exact float
    coordinates) so no formatting variant of any birth value can slip past.
    """
    tokens: List[str] = list(_SENTINEL_TOKENS)
    for person in (SENTINEL_A, SENTINEL_B):
        for value in person.values():
            tokens.append(str(value))
    return tokens


def _snapshot_files(root: Path) -> set:
    """Set of file paths under ``root``, skipping heavy/volatile dirs."""
    skip = {".git", ".venv", "__pycache__", ".pytest_cache", ".mypy_cache", "node_modules"}
    found: set = set()
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in skip]
        for name in filenames:
            found.add(os.path.join(dirpath, name))
    return found


def test_consent_absent_returns_422() -> None:
    """T-012-01 / AC-012c — omission is a 422 and the path is fully required."""
    resp = client.post(_MATCH_PATH, json=_without_consent_field())
    assert resp.status_code == 422, resp.text
    body = resp.json()
    for key in ("error", "message", "request_id"):
        assert key in body
    # The envelope names the missing consent field somewhere in the body.
    assert "second_person_consent_confirmed" in json.dumps(body)

    # The schema path to the field is fully required — no optional ancestor.
    app.openapi_schema = None
    spec = app.openapi()
    schemas = spec["components"]["schemas"]
    assert "options" in schemas["MatchRequest"]["required"]
    assert "second_person_consent_confirmed" in schemas["MatchOptions"]["required"]


def test_consent_false_returns_422() -> None:
    """T-012-02 / AC-012c / D5 — a false consent value is rejected, not honored."""
    resp = client.post(_MATCH_PATH, json=_with_consent(False))
    assert resp.status_code == 422, resp.text
    body = resp.json()
    # Stable, consent-specific detail code — not a generic literal/type error.
    code = body.get("error", "")
    detail_code = body.get("detail", {}).get("code") if isinstance(body.get("detail"), dict) else None
    assert "consent_required" in (code, detail_code), body
    # And it did NOT compute the second person's analysis.
    assert "individual" not in body


def test_no_raw_birth_data_in_logs_at_any_level(caplog: Any) -> None:
    """T-012-03 / AC-012a, EV-005 — no sentinel birth value ever hits the logs."""
    with caplog.at_level(logging.DEBUG):
        ok = client.post(_MATCH_PATH, json=VALID_MATCH_REQUEST)
        assert ok.status_code == 200, ok.text
        rejected = client.post(_MATCH_PATH, json=_without_consent_field())
        assert rejected.status_code == 422, rejected.text

    blob = _all_log_text(caplog.records)
    for token in _SENTINEL_TOKENS:
        assert token not in blob, f"sentinel birth value {token!r} leaked into logs"


def test_consent_value_is_hash_logged_with_request_id(caplog: Any) -> None:
    """T-012-04 / AC-012f — consent value is hash-logged with the request_id.

    The match privacy logger must emit at least one PII-free audit record
    that ties the request_id to a documented 64-hex sha256 hash of the
    consent value. Fails against a naive handler that emits no such record.
    """
    with caplog.at_level(logging.DEBUG):
        ok = client.post(_MATCH_PATH, json=VALID_MATCH_REQUEST)
        assert ok.status_code == 200, ok.text

    request_id = ok.json()["meta"]["request_id"]

    privacy_records = [r for r in caplog.records if r.name == _PRIVACY_LOGGER]
    assert privacy_records, "no consent audit record emitted by the match privacy logger"

    matched = [
        r
        for r in privacy_records
        if request_id in r.getMessage() and _SHA256_HEX.search(r.getMessage())
    ]
    assert matched, (
        "no match-privacy record ties the request_id to a 64-hex consent hash"
    )

    # The audit record(s) must carry NO person field value — full scan over
    # every distinctive request field value, not just the curated sentinels.
    audit_blob = _all_log_text(privacy_records)
    for token in _every_request_field_value():
        assert token not in audit_blob, (
            f"birth value {token!r} leaked into the consent audit log"
        )


def test_persist_raw_defaults_false_and_no_raw_artifact_written(tmp_path: Any) -> None:
    """T-012-05 / AC-012b — persist_raw defaults false; nothing raw is written.

    (a) the published schema default for ``persist_raw`` is ``false``;
    (b) a valid request writes no on-disk artifact containing a birth value —
        even when ``persist_raw`` is explicitly ``true`` (there is no
        persistence path; the field is an accepted no-op option).
    """
    # (a) OpenAPI default.
    app.openapi_schema = None
    spec = app.openapi()
    persist_raw = spec["components"]["schemas"]["MatchOptions"]["properties"]["persist_raw"]
    assert persist_raw.get("default") is False, persist_raw

    # (b) no raw artifact written anywhere under the repo tree.
    repo_root = Path(__file__).resolve().parents[1]
    before = _snapshot_files(repo_root)
    for req in (VALID_MATCH_REQUEST, _with_persist_raw(True)):
        resp = client.post(_MATCH_PATH, json=req)
        assert resp.status_code == 200, resp.text
    after = _snapshot_files(repo_root)

    tokens = _every_request_field_value()
    for path in after - before:
        try:
            content = Path(path).read_text(errors="ignore")
        except OSError:
            continue
        for token in tokens:
            assert token not in content, (
                f"birth value {token!r} written to new artifact {path}"
            )
