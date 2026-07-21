"""Tests for bazi-hehun score absence (REQ-007 / D1).

T5 (this file's first increment): ``test_lexical_guard`` — unit-fake guard
cases for the lexical blocked-language guard in
``bazi_engine.match.textblocks`` (AC-007e), binding per the plan's T5 row
(docs/plans/2026-07-02-bazi-hehun.md §5).

T14 (this file's second increment): the EV-004 score-absence proof —
contract tests ``test_schema_graph_contains_no_score_fields`` (T-007-01),
``test_response_contains_no_score_keys_recursively`` (T-007-02),
``test_no_numeric_compatibility_value_or_blocked_language`` (T-007-03) and
``test_source_completeness_confidence_if_present_is_documented_metadata``
(T-007-04), per docs/testing/bazi-hehun.acceptance-tests.md §1 REQ-007 and
docs/plans/2026-07-02-bazi-hehun.md §5 T14 (AC-007a–e). These scan BOTH
the exported response schema (the assembled app's ``app.openapi()`` graph
transitively reachable from ``/v1/match/bazi-hehun``) AND live
assembled-app responses (≥3 person pairs, incl. same-person). Class:
integration-fake — the real composition path, never a hand-built router.

This task is a PURE TEST increment: it must pass against the T8–T13
output with ZERO production-code change. A genuine failure here would mean
a real score-leak / naming defect, to be reported as a DEFECT and sent
back through the loop — never patched away by editing the contract to fit.
"""
from __future__ import annotations

import re
from typing import Any, Dict, Iterator, List, Set

from fastapi.testclient import TestClient

from bazi_engine.app import app
from tests.fixtures.match_payloads import SENTINEL_A, SENTINEL_B

# Contract §0.4 — spec-mandated EN phrases + QA-added DE hardening.
# Case-insensitive substring over every emitted string value.
SPEC_BLOCKED_PHRASES = (
    "perfect match",
    "marriage guarantee",
    "breakup prediction",
    "fate certainty",
)
QA_DE_BLOCKED_PHRASES = (
    "perfekte übereinstimmung",
    "ehegarantie",
    "trennungsvorhersage",
    "schicksals",
)

# Blocked-language guard cases: every string here MUST be detected.
# Mixed casing and mid-sentence embedding make the scan falsifiable.
BLOCKED_SAMPLES = (
    "You two are a PERFECT MATCH overall.",
    "This pairing comes with a Marriage Guarantee.",
    "Our breakup prediction is reliable.",
    "Fate Certainty: high.",
    "Eine perfekte Übereinstimmung!",
    "Das ist keine EHEGARANTIE.",
    "Trennungsvorhersage aktiviert.",
    "Das Schicksalsrad dreht sich.",
    # Score language (task T5: "score language" is part of the guard) —
    # word-level tokens and the T-007-03 numeric-compatibility pattern.
    "Your compatibility score is high.",
    "Score: excellent.",
    "The pair SCORES well.",
    "You get 87 points.",
    "1 point awarded.",
    "Compatibility: 75%.",
    "Compatibility: 75 %.",
    "Rated 88/100 overall.",
    "Rated 8 / 100 overall.",
)

# Clean factual strings: none may trip the guard (no false positives on
# the engine's actual emission vocabulary).
CLEAN_SAMPLES = (
    "Day master of person_a is Jia (Holz); day master of person_b is "
    "Gui (Wasser).",
    "Wu-Xing day-master relation per the canonical Sheng/Ke cycle: "
    "a_generates_b.",
    "Spouse-palace host pillar: day. Same day branch: no.",
    "Wu-Xing vectors in element order Holz, Feuer, Erde, Metall, Wasser "
    "— person_a: 1.20, 0.50, 2.30, 1.00, 3.00.",
    "The day-branch to spouse-palace designation has no domain-approved "
    "ruleset table; this layer is marked NEEDS_DOMAIN_REVIEW.",
    "DAY_ANCHOR_UNVERIFIED: Day-cycle anchor is not verified "
    "(day_cycle_anchor.anchor_verification='unverified').",
    "Birth date 1988-06-04T07:31:00 at 173.9391, -43.9502.",
    # Word-boundary discipline: substrings of longer words never match.
    "pointer arithmetic and underscores are fine",
    "ev:pair:day_master_comparison",
)


def test_lexical_guard() -> None:
    """AC-007e / AC-006d: the lexical guard detects every §0.4 phrase
    (case-insensitive) and every score-language form, rejects them loudly,
    passes clean factual strings through, and is applied to EVERY string
    the textblocks engine emits."""
    import pytest

    from bazi_engine.exc import BaziEngineError
    from bazi_engine.match.textblocks import (
        BLOCKED_PHRASES,
        BlockedLanguageError,
        find_blocked_language,
        guard_text,
    )

    # The shipped lexicon IS the §0.4 binding list (EN + DE hardening).
    for phrase in SPEC_BLOCKED_PHRASES + QA_DE_BLOCKED_PHRASES:
        assert phrase in BLOCKED_PHRASES, f"§0.4 phrase missing: {phrase!r}"

    # Detection: every blocked sample is found and rejected.
    for sample in BLOCKED_SAMPLES:
        found = find_blocked_language(sample)
        assert found is not None, f"guard missed blocked sample {sample!r}"
        with pytest.raises(BlockedLanguageError):
            guard_text(sample)

    # The guard error is part of the domain exception hierarchy, so the
    # app-level handlers map it — it can never escape as a bare exception.
    assert issubclass(BlockedLanguageError, BaziEngineError)

    # No false positives on the factual emission vocabulary.
    for sample in CLEAN_SAMPLES:
        found = find_blocked_language(sample)
        assert found is None, (
            f"false positive {found!r} on clean sample {sample!r}"
        )
        assert guard_text(sample) == sample

    # AC-007e is applied to EVERY emitted string: build the full block set
    # for the canonical sentinel pair (both birth-time variants) and scan
    # every string field, enum value and evidence id.
    from tests.test_match_raw_blocks import _block_strings, _build

    for birth_time_known in (True, False):
        _, _, blocks = _build(birth_time_known=birth_time_known)
        assert blocks
        for block in blocks:
            for text in _block_strings(block):
                assert find_blocked_language(text) is None, (
                    f"blocked language {find_blocked_language(text)!r} "
                    f"in emitted string {text!r}"
                )


# ─────────────────────────────────────────────────────────────────────────────
# T14 — EV-004 score-absence proof (contract T-007-01..04, AC-007a–e)
#
# Both surfaces are scanned: the exported schema (``app.openapi()`` graph
# reachable from the match path) AND live assembled-app responses. Every
# assertion below must hold against the UNCHANGED T8–T13 output; a failure is a
# production DEFECT (score-leak / mis-naming), not a signal to edit these tests.
# ─────────────────────────────────────────────────────────────────────────────

_client = TestClient(app)
_MATCH_PATH = "/v1/match/bazi-hehun"

# §0.4 — the five forbidden score keys (EXACT key match, recursive; D1: the
# keys must be OMITTED, never present-as-null). Plus the REQ-016 QA-hardening
# key: a registered-user matching opt-in must not leak into the MVP contract
# ("add this key to T-007-01's forbidden-key scan" — acceptance-tests §1
# REQ-016).
FORBIDDEN_SCORE_KEYS: Set[str] = {
    "total_score",
    "sub_scores",
    "score_class",
    "awarded_points",
    "score_confidence",
}
QA_HARDENING_KEYS: Set[str] = {"allow_match_by_other_users"}
FORBIDDEN_KEYS: Set[str] = FORBIDDEN_SCORE_KEYS | QA_HARDENING_KEYS

# §0.4 blocked-language lexicon reused for the response string scan (T-007-03).
BLOCKED_PHRASES = SPEC_BLOCKED_PHRASES + QA_DE_BLOCKED_PHRASES

# T-007-03 — a numeric compatibility value presented as a rating: N% / N/100 /
# N point(s). The engine emits only source-labelled facts, so this pattern must
# be ABSENT from every string value (a smuggled heuristic score would trip it).
_NUMERIC_COMPAT_RE = re.compile(r"\b\d{1,3}\s*(?:%|/\s*100|points?)\b", re.IGNORECASE)

# ≥3 distinct person pairs (incl. same-person) so absence is not pair-specific.
_PAIRS = (
    ("A_B", SENTINEL_A, SENTINEL_B),
    ("B_A", SENTINEL_B, SENTINEL_A),
    ("A_A", SENTINEL_A, SENTINEL_A),
)

_SCC_FIELD = "source_completeness_confidence"


def _openapi() -> Dict[str, Any]:
    """Freshly-built OpenAPI schema (idiom of tests/test_openapi_contract.py)."""
    app.openapi_schema = None
    return app.openapi()


def _match_operation(spec: Dict[str, Any]) -> Dict[str, Any]:
    assert _MATCH_PATH in spec["paths"], "match path missing from OpenAPI"
    return spec["paths"][_MATCH_PATH]["post"]


def _reachable_schema_names(spec: Dict[str, Any], start: Any) -> Set[str]:
    """Component-schema names transitively reachable from ``start`` via ``$ref``.

    Follows ``#/components/schemas/<name>`` refs through the whole graph
    (request body + every response, incl. the 422 ErrorEnvelope), guarding
    against cycles.
    """
    schemas = spec.get("components", {}).get("schemas", {})
    reached: Set[str] = set()
    stack: List[Any] = [start]
    while stack:
        node = stack.pop()
        if isinstance(node, dict):
            ref = node.get("$ref")
            if isinstance(ref, str) and ref.startswith("#/components/schemas/"):
                name = ref.rsplit("/", 1)[-1]
                if name not in reached and name in schemas:
                    reached.add(name)
                    stack.append(schemas[name])
            stack.extend(node.values())
        elif isinstance(node, list):
            stack.extend(node)
    return reached


def _all_dict_keys(node: Any) -> Iterator[str]:
    """Yield every dict key at every depth (used to scan example payloads)."""
    if isinstance(node, dict):
        for key, value in node.items():
            if isinstance(key, str):
                yield key
            yield from _all_dict_keys(value)
    elif isinstance(node, list):
        for item in node:
            yield from _all_dict_keys(item)


def _schema_tokens(node: Any) -> Iterator[str]:
    """Yield property names, ``required`` entries, ``enum`` values and example
    keys — the schema-graph analog of "any place a score key could hide"."""
    if isinstance(node, dict):
        props = node.get("properties")
        if isinstance(props, dict):
            for name in props:
                if isinstance(name, str):
                    yield name
        required = node.get("required")
        if isinstance(required, list):
            for entry in required:
                if isinstance(entry, str):
                    yield entry
        enum = node.get("enum")
        if isinstance(enum, list):
            for value in enum:
                if isinstance(value, str):
                    yield value
        for ex_key in ("example", "examples", "default"):
            if ex_key in node:
                yield from _all_dict_keys(node[ex_key])
        for value in node.values():
            yield from _schema_tokens(value)
    elif isinstance(node, list):
        for item in node:
            yield from _schema_tokens(item)


def _match_schema_nodes(spec: Dict[str, Any]) -> List[Any]:
    """The operation + every component schema reachable from the match path."""
    operation = _match_operation(spec)
    schemas = spec["components"]["schemas"]
    reached = _reachable_schema_names(spec, operation)
    return [operation] + [schemas[name] for name in reached]


def _walk_keys(node: Any) -> Iterator[str]:
    """Yield every dict key at every depth of a live response body."""
    if isinstance(node, dict):
        for key, value in node.items():
            if isinstance(key, str):
                yield key
            yield from _walk_keys(value)
    elif isinstance(node, list):
        for item in node:
            yield from _walk_keys(item)


def _walk_string_values(node: Any) -> Iterator[str]:
    """Yield every leaf STRING VALUE (not keys) of a live response body."""
    if isinstance(node, str):
        yield node
    elif isinstance(node, dict):
        for value in node.values():
            yield from _walk_string_values(value)
    elif isinstance(node, list):
        for item in node:
            yield from _walk_string_values(item)


def _post_match(person_a: Dict[str, Any], person_b: Dict[str, Any]) -> Dict[str, Any]:
    """POST a consenting valid request to the ASSEMBLED app; assert 200."""
    payload = {
        "mode": "birth_input",
        "person_a": person_a,
        "person_b": person_b,
        "options": {"second_person_consent_confirmed": True},
    }
    resp = _client.post(_MATCH_PATH, json=payload)
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_schema_graph_contains_no_score_fields() -> None:
    """T-007-01 / AC-007a/b/c, EV-004 — resolve ALL schemas transitively
    reachable from ``POST /v1/match/bazi-hehun`` (request + every response,
    through ``$ref``); then no property name, no ``required`` entry, no
    ``enum`` value and no example key equals any of the five forbidden score
    keys (nor the REQ-016 QA-hardening key). D1: the keys are OMITTED — the
    contract cannot even advertise a score. Kills chain C at the schema level."""
    spec = _openapi()
    tokens: Set[str] = set()
    for node in _match_schema_nodes(spec):
        tokens.update(_schema_tokens(node))
    leaked = tokens & FORBIDDEN_KEYS
    assert not leaked, f"forbidden score keys leaked in match schema graph: {leaked}"


def test_response_contains_no_score_keys_recursively() -> None:
    """T-007-02 / AC-007a/b/d — deep-walk every dict key at every depth of a
    live response; none of the five forbidden score keys occurs. Run against
    ≥3 distinct person pairs (incl. same-person) so absence is not
    pair-specific (D1: omitted, never null)."""
    for label, person_a, person_b in _PAIRS:
        body = _post_match(person_a, person_b)
        keys = set(_walk_keys(body))
        leaked = keys & FORBIDDEN_KEYS
        assert not leaked, f"[{label}] forbidden score keys in response: {leaked}"


def test_no_numeric_compatibility_value_or_blocked_language() -> None:
    """T-007-03 / AC-007d/e, AC-008c — deep-walk every string VALUE of a live
    response; no §0.4 blocked-language phrase (EN + DE, case-insensitive
    substring) occurs, no numeric compatibility rating (``N%`` / ``N/100`` /
    ``N point(s)``) is presented, and no value labelled ``PROPOSED_HEURISTIC``
    exists anywhere (keys or values). Run across the ≥3 pairs."""
    for label, person_a, person_b in _PAIRS:
        body = _post_match(person_a, person_b)
        for text in _walk_string_values(body):
            lowered = text.lower()
            for phrase in BLOCKED_PHRASES:
                assert phrase not in lowered, (
                    f"[{label}] blocked phrase {phrase!r} in string value {text!r}"
                )
            assert "proposed_heuristic" not in lowered, (
                f"[{label}] PROPOSED_HEURISTIC value present: {text!r}"
            )
            match = _NUMERIC_COMPAT_RE.search(text)
            assert match is None, (
                f"[{label}] numeric compatibility pattern {match.group()!r} "
                f"in string value {text!r}"
            )
        # PROPOSED_HEURISTIC must not appear as a KEY either ("anywhere").
        for key in _walk_keys(body):
            assert "proposed_heuristic" not in key.lower(), (
                f"[{label}] PROPOSED_HEURISTIC key present: {key!r}"
            )


def test_source_completeness_confidence_if_present_is_documented_metadata() -> None:
    """T-007-04 / AC-007c — if any field named ``source_completeness_confidence``
    exists in the schema graph, its schema ``description`` MUST document it as
    source-status metadata and MUST NOT claim ``compatibility`` or ``score``;
    if it is emitted in a live response it must be documented in the schema.
    Absent field ⇒ vacuous pass (it is not a compatibility value in disguise)."""
    spec = _openapi()

    descriptions: List[str] = []
    for node in _match_schema_nodes(spec):
        for sub in _iter_named_property_schemas(node, _SCC_FIELD):
            descriptions.append(sub.get("description", "") or "")

    for desc in descriptions:
        lowered = desc.lower()
        assert "source" in lowered and (
            "status" in lowered or "completeness" in lowered or "metadata" in lowered
        ), (
            f"{_SCC_FIELD} must be documented as source-status metadata, "
            f"got description: {desc!r}"
        )
        assert "compatibility" not in lowered, (
            f"{_SCC_FIELD} description makes a compatibility claim: {desc!r}"
        )
        assert "score" not in lowered, (
            f"{_SCC_FIELD} description makes a score claim: {desc!r}"
        )

    # Response side: if emitted, it must be backed by the schema documentation
    # checked above (never a bare, undocumented number).
    body = _post_match(SENTINEL_A, SENTINEL_B)
    if _SCC_FIELD in set(_walk_keys(body)):
        assert descriptions, (
            f"{_SCC_FIELD} is emitted in the response but undocumented in the "
            f"schema graph"
        )


def _iter_named_property_schemas(node: Any, field_name: str) -> Iterator[Dict[str, Any]]:
    """Yield every property schema named ``field_name`` in the schema graph."""
    if isinstance(node, dict):
        props = node.get("properties")
        if isinstance(props, dict):
            sub = props.get(field_name)
            if isinstance(sub, dict):
                yield sub
        for value in node.values():
            yield from _iter_named_property_schemas(value, field_name)
    elif isinstance(node, list):
        for item in node:
            yield from _iter_named_property_schemas(item, field_name)
