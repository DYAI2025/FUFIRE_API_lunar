"""test_match_contract.py — T9 route existence + /v1-only mount (REQ-001).

Binding contract anchors (docs/testing/bazi-hehun.acceptance-tests.md §1
REQ-001, docs/plans/2026-07-02-bazi-hehun.md §5 T9):

- AC-001a: the route exists at ``POST /v1/match/bazi-hehun`` on the
  ASSEMBLED production app and answers (200), and the OpenAPI schema
  publishes it with resolvable request/response schema refs (T-001-01/02).
- AC-001c (DECISION-001): the endpoint is mounted ``/v1``-ONLY — there is
  NO legacy unversioned ``/match/bazi-hehun`` mount; the legacy path 404s
  with a stable ErrorEnvelope (T-001-03). Kills audit chain D.
- AC-001d/AC-010c (backend half): the match operation is tagged ``Hehun``,
  the exact literal the frontend ``TAG_TO_CATEGORY`` maps (T-001-05). Kills
  chain B's backend half.

Class: integration-fake — every test runs against the assembled app
(``from bazi_engine.app import app``), never a hand-built router.

Scope note: the committed-spec / drift / example tests (T-010-01/02/03),
the ``CanonicalBaziChartInput`` absence pin (T-002-05, AC-002d) and the
OpenAPI-level D4 readiness scan (T-008-03 lift, AC-008b) are added here by
T15 — they assert against the ASSEMBLED app and the on-disk exported spec,
so their contract-designated home is this route-contract file. The
non-existent-path envelope test (T-001-04, AC-001b) is added here by T10 —
its contract-designated home (REQ-001), alongside the other route-existence
tests.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, Set

from fastapi.testclient import TestClient
from jsonschema import Draft7Validator

from bazi_engine.app import app
from tests.fixtures.match_payloads import VALID_MATCH_REQUEST

client = TestClient(app)

_MATCH_PATH = "/v1/match/bazi-hehun"
_LEGACY_MATCH_PATH = "/match/bazi-hehun"
_HEHUN_TAG = "Hehun"

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SPEC_PATH = _REPO_ROOT / "spec" / "openapi" / "openapi.json"
_ERROR_ENVELOPE_SCHEMA = json.loads(
    (_REPO_ROOT / "spec" / "schemas" / "ErrorEnvelope.schema.json").read_text()
)

# D4 (AC-008b): no readiness claim may appear in the match operation's OpenAPI
# descriptions/examples. Same lexicon as the engine-level scan in
# ``tests/test_match_raw_blocks.py`` (LLM_READINESS_TOKENS); a substring scan
# cannot tell a denial from a claim, so the descriptions are worded to avoid
# the tokens entirely (the T15 docstring polish).
_D4_READINESS_TOKENS = (
    "llm",
    "interpretation-ready",
    "interpretation ready",
    "fusion interpretation",
)


def _ref_names(obj: Any) -> Set[str]:
    """Collect all ``#/components/schemas/<Name>`` refs anywhere in ``obj``."""
    found: Set[str] = set()
    if isinstance(obj, dict):
        ref = obj.get("$ref")
        if isinstance(ref, str):
            found.add(ref.split("/")[-1])
        for value in obj.values():
            found |= _ref_names(value)
    elif isinstance(obj, list):
        for value in obj:
            found |= _ref_names(value)
    return found


def _match_reachable_schemas(spec: Dict[str, Any]) -> Set[str]:
    """Every component schema transitively referenced by the match operation.

    Scoping to this closure is what keeps the D4 scan honest: it excludes the
    unrelated pre-existing ``FusionResponse.fusion_interpretation`` field,
    which is NOT reachable from the match operation.
    """
    op = spec["paths"][_MATCH_PATH]["post"]
    schemas = spec["components"]["schemas"]
    seen: Set[str] = set()
    stack = list(_ref_names(op))
    while stack:
        name = stack.pop()
        if name in seen:
            continue
        seen.add(name)
        stack.extend(_ref_names(schemas.get(name, {})))
    return seen


def _iter_strings(obj: Any) -> Any:
    """Yield every string value nested anywhere in ``obj``."""
    if isinstance(obj, dict):
        for value in obj.values():
            yield from _iter_strings(value)
    elif isinstance(obj, list):
        for value in obj:
            yield from _iter_strings(value)
    elif isinstance(obj, str):
        yield obj


def _openapi() -> Dict[str, Any]:
    """Return a freshly-built OpenAPI schema (idiom of test_openapi_contract)."""
    app.openapi_schema = None
    return app.openapi()


def test_v1_match_route_exists_and_answers() -> None:
    """T-001-01 / AC-001a — the /v1 route exists on the assembled app."""
    resp = client.post(_MATCH_PATH, json=VALID_MATCH_REQUEST)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert isinstance(body, dict)


def test_openapi_contains_match_path_with_schemas() -> None:
    """T-001-02 / AC-001a, EV-001 — path published with resolvable refs."""
    spec = _openapi()
    assert _MATCH_PATH in spec["paths"], "match path missing from OpenAPI"
    post = spec["paths"][_MATCH_PATH]["post"]

    request_schema = post["requestBody"]["content"]["application/json"]["schema"]
    assert "$ref" in request_schema
    request_ref = request_schema["$ref"].split("/")[-1]
    assert request_ref in spec["components"]["schemas"]

    response_schema = post["responses"]["200"]["content"]["application/json"][
        "schema"
    ]
    assert "$ref" in response_schema
    response_ref = response_schema["$ref"].split("/")[-1]
    assert response_ref in spec["components"]["schemas"]


def test_legacy_unversioned_match_route_is_404_error_envelope() -> None:
    """T-001-03 / AC-001c — DECISION-001 negative test (kills chain D).

    The legacy unversioned path must NOT be mounted; hitting it yields a
    404 whose body is a stable ErrorEnvelope, never a raw traceback/HTML.
    """
    resp = client.post(_LEGACY_MATCH_PATH, json=VALID_MATCH_REQUEST)
    assert resp.status_code == 404, resp.text
    body = resp.json()
    # Body validates against the canonical ErrorEnvelope schema.
    Draft7Validator(_ERROR_ENVELOPE_SCHEMA).validate(body)
    for key in ("error", "message", "request_id"):
        assert key in body


def test_match_operation_tag_is_hehun_mapping_key() -> None:
    """T-001-05 / AC-001d, AC-010c — the match op is tagged exactly ``Hehun``."""
    spec = _openapi()
    tags = spec["paths"][_MATCH_PATH]["post"].get("tags", [])
    assert _HEHUN_TAG in tags, f"expected {_HEHUN_TAG!r} tag, got {tags!r}"


def test_nonexistent_v1_match_paths_return_stable_envelope() -> None:
    """T-001-04 / AC-001b — unknown /v1/match/* paths give a stable envelope.

    An unmatched path (404) or a wrong method on the real endpoint (405) must
    always return the canonical ErrorEnvelope shape, never a raw traceback or
    an HTML error page.
    """
    cases = [
        ("POST", "/v1/match/does-not-exist"),
        ("GET", "/v1/match/does-not-exist"),
        ("GET", _MATCH_PATH),  # wrong method on the real endpoint ⇒ 405
    ]
    for method, path in cases:
        resp = client.request(
            method,
            path,
            json=VALID_MATCH_REQUEST if method == "POST" else None,
        )
        assert resp.status_code in (404, 405), (method, path, resp.status_code)
        body = resp.json()
        Draft7Validator(_ERROR_ENVELOPE_SCHEMA).validate(body)
        for key in ("error", "message", "request_id"):
            assert key in body, (method, path, body)
        assert "Traceback" not in resp.text, (method, path)
        assert "<html" not in resp.text.lower(), (method, path)


# ── T15: committed-spec / drift / example / D4 / D2 contract ──────────────────
def test_committed_openapi_json_is_valid_and_contains_match_path() -> None:
    """T-010-01 / AC-010a, EV-001 — the on-disk exported spec is authoritative.

    Pin the committed artifact itself (not just the in-memory schema): it must
    parse as JSON and publish ``paths["/v1/match/bazi-hehun"]``.
    """
    spec = json.loads(_SPEC_PATH.read_text(encoding="utf-8"))
    assert _MATCH_PATH in spec["paths"], "match path missing from committed spec"
    assert "post" in spec["paths"][_MATCH_PATH]


def test_export_openapi_check_passes() -> None:
    """T-010-02 / AC-010a — the committed spec is not drifted from the app.

    Runs the ACTUAL CI drift command as a subprocess (exit 0 ⇒ no drift). This
    is the same gate CI runs; a stale hand-edited spec fails here.
    """
    result = subprocess.run(
        [sys.executable, "scripts/export_openapi.py", "--check"],
        cwd=str(_REPO_ROOT),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"export --check failed (drift):\n{result.stdout}\n{result.stderr}"
    )


def test_match_operation_example_is_valid_and_not_confabulated() -> None:
    """T-010-03 / AC-010d — the request example is real and request-only.

    (a) POSTing the committed example to the assembled app returns 200;
    (b) it carries ONLY request-schema fields — no response/computed values
        (pillars, day_master, hashes, scores) are confabulated into it;
    (c) it confirms consent (``second_person_consent_confirmed: true``).
    """
    spec = json.loads(_SPEC_PATH.read_text(encoding="utf-8"))
    example = spec["components"]["schemas"]["MatchRequest"]["example"]

    # (a) the example is a live, accepted request.
    resp = client.post(_MATCH_PATH, json=example)
    assert resp.status_code == 200, resp.text

    # (b) request-only: the request model forbids unknown keys, so validating
    # the example proves it contains no computed/response field. A recursive
    # key scan makes the "not confabulated" intent explicit.
    from bazi_engine.routers.match import MatchRequest

    MatchRequest.model_validate(example)

    confabulated = {
        "pillars",
        "four_pillars",
        "day_master",
        "day_branch",
        "wuxing_vector",
        "wuxing_ledger",
        "spouse_palace",
        "input_hash",
        "canonical_birth_context_hash",
        "provenance",
        "evidence_ledger",
        "meta",
        "score",
        "total_score",
    }

    def _keys(obj: Any) -> Set[str]:
        out: Set[str] = set()
        if isinstance(obj, dict):
            for key, value in obj.items():
                out.add(key)
                out |= _keys(value)
        elif isinstance(obj, list):
            for value in obj:
                out |= _keys(value)
        return out

    leaked = _keys(example) & confabulated
    assert not leaked, f"example contains computed/response keys: {leaked}"

    # (c) consent is affirmatively confirmed in the example.
    assert example["options"]["second_person_consent_confirmed"] is True


def test_no_canonical_bazi_chart_input_schema_published() -> None:
    """T-002-05 / AC-002d — raw-chart input is deferred (D2), not published.

    No component schema is named / contains ``CanonicalBaziChartInput`` and the
    match request ``mode`` admits ONLY ``birth_input``.
    """
    app.openapi_schema = None
    spec = app.openapi()

    offenders = [
        name
        for name in spec["components"]["schemas"]
        if "canonicalbazichartinput" in name.lower()
    ]
    assert offenders == [], f"deferred D2 component leaked: {offenders}"

    mode = spec["components"]["schemas"]["MatchRequest"]["properties"]["mode"]
    values = mode.get("enum") or ([mode["const"]] if "const" in mode else [])
    assert values == ["birth_input"], f"mode admits more than birth_input: {mode}"


def test_no_llm_readiness_claim_in_match_openapi_descriptions() -> None:
    """T-008-03 (OpenAPI lift) / AC-008b — no D4 readiness wording in the spec.

    Scans the match operation AND every schema transitively reachable from it
    (descriptions, titles, examples) for the readiness lexicon. Scoping to the
    match closure excludes the unrelated ``FusionResponse.fusion_interpretation``
    field, which is not part of this contract.
    """
    app.openapi_schema = None
    spec = app.openapi()

    op = spec["paths"][_MATCH_PATH]["post"]
    schemas = spec["components"]["schemas"]
    scan_targets = [op] + [
        schemas[name] for name in _match_reachable_schemas(spec) if name in schemas
    ]

    for target in scan_targets:
        for text in _iter_strings(target):
            lowered = text.lower()
            for token in _D4_READINESS_TOKENS:
                assert token not in lowered, (
                    f"D4 readiness token {token!r} in match OpenAPI: {text[:120]!r}"
                )
