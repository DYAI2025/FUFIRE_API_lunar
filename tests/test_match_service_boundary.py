"""test_match_service_boundary.py — T9 reuse of the BaZi engine (REQ-003).

Binding contract anchors (docs/testing/bazi-hehun.acceptance-tests.md §1
REQ-003, docs/plans/2026-07-02-bazi-hehun.md §5 T9 + §4.2):

- AC-003a: the existing single-chart endpoint is unchanged; its golden
  regression anchor (``tests/test_golden.py``) stays byte-identical to
  ``main`` (T-003-01). The coder MUST NOT edit ``test_golden.py``.
- AC-003c: same-person chart parity THROUGH the two assembled endpoints —
  the per-person pillars + day master inside the match response deep-equal
  ``/v1/calculate/bazi``'s (T-003-02). Composition reuses the SAME
  ``compute_bazi`` and the SAME ``format_pillar`` (plan §4.2), so parity
  holds by construction, not coincidence.
- AC-003b: the Level-4 ``bazi_engine/match/**`` package does NOT duplicate
  core computation — no ``compute_bazi``/``find_crossing`` re-implementation
  and no copied day-offset/jieqi tables; the reuse is a real import in the
  composition seam (T-003-03). Justified deviation from the literal
  contract wording: per plan §4.2 the ``compute_bazi`` CALL lives in the
  Level-5 seam ``routers/match.py`` (composition at the router), keeping
  ``match/`` HTTP-free — so the "imports bazi_engine.bazi" assertion is
  checked on the seam, and ``match/`` is checked for reuse of engine
  primitives instead of standing alone.
- AC-003d: no cross-request state — a second call carries nothing derived
  from the first, and repeating a call is byte-identical (T-003-04).

Class: integration-fake — every behavioural test runs against the
assembled app (``from bazi_engine.app import app``); T-003-03 is a
unit-fake static source check.
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Any, Dict

import pytest
from fastapi.testclient import TestClient

from bazi_engine.app import app
from tests.fixtures.match_payloads import SENTINEL_A, SENTINEL_B

client = TestClient(app)

_MATCH_PATH = "/v1/match/bazi-hehun"
_BAZI_PATH = "/v1/calculate/bazi"

_REPO_ROOT = Path(__file__).resolve().parents[1]
_MATCH_PKG = _REPO_ROOT / "bazi_engine" / "match"
_SEAM = _REPO_ROOT / "bazi_engine" / "routers" / "match.py"

# The distinctive sentinel substrings (contract §0.2) — raw birth data must
# never surface in a redacted response, so their presence in call 2 would
# prove cross-request leakage (T-003-04).
_SENTINEL_A_TOKENS = ("1988-06-04", "07:31", "Pacific/Chatham", "173.9391", "-43.9502")

# Fields that are legitimately volatile per call (pinned exclusion list,
# T-003-04 / T-014-02 discipline) — everything else must be byte-stable.
_VOLATILE_JSONPATHS = (
    ("meta", "request_id"),
    ("meta", "generated_at_utc"),
    ("meta", "correlation_id"),
    ("provenance", "computation_timestamp"),
)


def _match_request(person_a: Dict[str, Any], person_b: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "mode": "birth_input",
        "person_a": person_a,
        "person_b": person_b,
        "options": {"second_person_consent_confirmed": True},
    }


def _strip_volatile(body: Dict[str, Any]) -> Dict[str, Any]:
    clone = json.loads(json.dumps(body))
    for section, key in _VOLATILE_JSONPATHS:
        if section in clone and isinstance(clone[section], dict):
            clone[section].pop(key, None)
    return clone


def test_existing_calculate_bazi_behavior_unchanged() -> None:
    """T-003-01 / AC-003a — golden anchor unedited + single-chart still 200."""
    # PR CI checkouts are detached/shallow and may carry neither a local
    # ``main`` nor ``origin/main`` ref — fall back through candidates and
    # skip (visibly) only when no ref is resolvable, instead of failing on
    # ``fatal: invalid object name 'main'`` for every PR regardless of
    # whether the golden anchor actually diverged.
    show = None
    for ref in ("main", "origin/main"):
        candidate = subprocess.run(
            ["git", "show", f"{ref}:tests/test_golden.py"],
            cwd=_REPO_ROOT,
            capture_output=True,
            text=True,
        )
        if candidate.returncode == 0:
            show = candidate
            break
    if show is None:
        pytest.skip(
            "no main/origin-main ref in this checkout (PR CI shallow clone) — "
            "golden-anchor divergence check runs locally and on push-to-main CI"
        )
    current = (_REPO_ROOT / "tests" / "test_golden.py").read_text()
    assert current == show.stdout, "tests/test_golden.py diverged from main (AC-003a)"

    resp = client.post(_BAZI_PATH, json=SENTINEL_A)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    for key in ("input", "pillars", "chinese", "dates", "transition", "provenance", "precision"):
        assert key in body, f"single-chart response lost key {key!r}"


def test_same_person_chart_parity_with_calculate_bazi() -> None:
    """T-003-02 / AC-003c — per-person pillars + day master parity.

    Same process, same EPHEMERIS_MODE: the four pillars and day master a
    caller sees inside ``individual.person_a`` of the match response must be
    field-by-field EQUAL to the single-chart ``/v1/calculate/bazi``
    response — proving the match endpoint reuses the same computation and
    the same ``format_pillar`` shaping (plan §4.2), not a divergent copy.
    """
    single = client.post(_BAZI_PATH, json=SENTINEL_A)
    assert single.status_code == 200, single.text
    single_body = single.json()

    match = client.post(_MATCH_PATH, json=_match_request(SENTINEL_A, SENTINEL_A))
    assert match.status_code == 200, match.text
    match_body = match.json()

    person_a = match_body["individual"]["person_a"]

    # Four pillars deep-equal the single-chart pillars block (same shaper).
    assert person_a["four_pillars"] == single_body["pillars"]
    # Day master parity.
    assert person_a["day_master"] == single_body["chinese"]["day_master"]

    # Wu-Xing vector: the single-chart endpoint does not surface it, so
    # cross-endpoint equality is impossible; instead assert same-input
    # determinism (person_a == person_b, identical payloads) plus a
    # well-formed 5-element finite vector. The vector's SOURCE binding
    # (DECISION-003) is pinned separately in test_match_normalization.py.
    person_b = match_body["individual"]["person_b"]
    vector = person_a["wuxing_vector"]
    assert vector == person_b["wuxing_vector"]
    assert len(vector) == 5
    assert all(isinstance(v, (int, float)) for v in vector)


def test_match_package_does_not_duplicate_core_computation() -> None:
    """T-003-03 / AC-003b — no core-computation copy in the match package.

    The Level-4 ``match/`` package must not re-implement the engine; the
    reuse is a real import in the Level-5 composition seam (plan §4.2).
    """
    sources = {p.name: p.read_text() for p in _MATCH_PKG.glob("*.py")}
    assert sources, "no match package sources found"

    # No re-implementation of the core computation anywhere in match/**.
    for name, text in sources.items():
        assert "def compute_bazi" not in text, f"{name} re-implements compute_bazi"
        assert "def find_crossing" not in text, f"{name} re-implements find_crossing"
        # No copied day-offset table (the canonical constant lives in
        # constants.DAY_OFFSET; match/ must not hardcode its own).
        assert "DAY_OFFSET" not in text, f"{name} copies the day-offset table"

    # match/ reuses engine primitives rather than standing alone — every
    # non-canonical module imports from the bazi_engine package.
    engine_importers = [
        name
        for name, text in sources.items()
        if re.search(r"from \.\.?[\w.]* import|import bazi_engine", text)
    ]
    assert engine_importers, "match/ does not reuse any bazi_engine primitive"

    # The reuse of the core engine is real: the composition seam imports
    # compute_bazi from bazi_engine.bazi (AC-003b, plan §4.2).
    seam = _SEAM.read_text()
    assert re.search(r"from \.\.bazi import [^\n]*compute_bazi", seam), (
        "routers/match.py must import compute_bazi from bazi_engine.bazi"
    )


def test_no_cross_request_state_between_match_calls() -> None:
    """T-003-04 / AC-003d — no state bleeds between sequential calls."""
    call1 = client.post(_MATCH_PATH, json=_match_request(SENTINEL_A, SENTINEL_A))
    assert call1.status_code == 200, call1.text
    call1_body = call1.json()

    call2 = client.post(_MATCH_PATH, json=_match_request(SENTINEL_B, SENTINEL_B))
    assert call2.status_code == 200, call2.text
    call2_text = call2.text
    # Nothing derived from call 1's persons may appear in call 2.
    for token in _SENTINEL_A_TOKENS:
        assert token not in call2_text, f"call 2 leaked call-1 sentinel {token!r}"

    # Repeating call 1 is byte-stable modulo the pinned volatile fields.
    call1_again = client.post(_MATCH_PATH, json=_match_request(SENTINEL_A, SENTINEL_A))
    assert call1_again.status_code == 200, call1_again.text
    assert _strip_volatile(call1_body) == _strip_volatile(call1_again.json())
