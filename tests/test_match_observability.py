"""Tests for the bazi-hehun evidence ledger (REQ-013 / AC-013a).

T6 (contract T-013-01, docs/testing/bazi-hehun.acceptance-tests.md): the
binding test name ``test_evidence_ledger_covers_every_block_and_warning``
is implemented here at the pure-engine boundary
(``bazi_engine.match.evidence``) — the highest boundary that EXISTS in
Milestone A (same idiom as ``test_match_raw_blocks.py``). The contract's
evidence class for this is integration-fake (assembled app); Milestone B
(T9/T12) lifts the same test name onto ``POST /v1/match/bazi-hehun`` once
the route exists. Engine-level projection:

- "``evidence_ledger`` has ≥1 entry for every emitted analysis block AND
  every warning" ⇒ the ledger materialized by
  ``build_evidence_ledger`` from the canonical sentinel pair covers every
  ``evidence_id`` referenced by ``build_text_blocks`` and every warning
  ``warning_evidence_id`` — no dangling refs, no orphan entries, exactly
  one entry per distinct evidence id.
- "no ledger entry mentions score contributions (D1)" ⇒ no forbidden
  score key in the entry fields/values and no score/blocked language in
  any emitted string (reuses the ``textblocks`` lexical scan).

Note (test-name reconciliation): the plan §5 T6 row and the T5
forward-reference in ``test_match_raw_blocks.py`` both name this
``test_evidence_ledger_complete``; the frozen contract (T-013-01) names it
``test_evidence_ledger_covers_every_block_and_warning``. Both names are
aliased below to the SAME assertions so the plan pointer and the binding
contract name resolve identically.
"""
from __future__ import annotations

import dataclasses
import logging
import re
import uuid as uuid_mod
from typing import Any, List, Tuple

# D1 / REQ-007 — forbidden score keys (contract §0.4), recursive/exact scan.
FORBIDDEN_SCORE_KEYS = {
    "total_score",
    "sub_scores",
    "score_class",
    "awarded_points",
    "score_confidence",
}

EVIDENCE_ENTRY_FIELDS = ["id", "kind", "source_ref", "description"]


def _individual(payload: dict, subject: str, *, birth_time_known: bool = True):
    from bazi_engine.bazi import compute_bazi
    from bazi_engine.match.individual import analyze_individual
    from bazi_engine.match.normalize import normalize_chart
    from bazi_engine.types import BaziInput

    result = compute_bazi(
        BaziInput(
            birth_local=payload["date"],
            timezone=payload["tz"],
            longitude_deg=payload["lon"],
            latitude_deg=payload["lat"],
        )
    )
    chart = normalize_chart(
        result, subject=subject, birth_time_known=birth_time_known
    )
    return analyze_individual(chart, subject=subject)


def _engine_output(
    birth_time_known: bool = True,
) -> Tuple[Any, Tuple[Any, ...], Tuple[Any, ...], Tuple[Any, ...]]:
    """Return (pair, warnings, blocks, ledger) for the sentinel pair."""
    from bazi_engine.match.evidence import build_evidence_ledger
    from bazi_engine.match.pair import analyze_pair
    from bazi_engine.match.textblocks import build_text_blocks
    from tests.fixtures.match_payloads import SENTINEL_A, SENTINEL_B

    person_a = _individual(
        SENTINEL_A, "person_a", birth_time_known=birth_time_known
    )
    person_b = _individual(
        SENTINEL_B, "person_b", birth_time_known=birth_time_known
    )
    pair = analyze_pair(person_a, person_b)
    warnings = person_a.warnings + person_b.warnings
    blocks = build_text_blocks(pair, warnings=warnings)
    ledger = build_evidence_ledger(pair, warnings)
    return pair, warnings, blocks, ledger


def test_evidence_ledger_covers_every_block_and_warning() -> None:
    """T-013-01 / AC-013a (engine projection): the evidence ledger has
    exactly one entry per distinct evidence id, covers every emitted block
    and every warning with no dangling refs and no orphan entries, and
    carries no score contribution (D1)."""
    from bazi_engine.match import (
        PAIR_LAYER_NAMES,
        EvidenceEntry,
        EvidenceKind,
    )
    from bazi_engine.match.textblocks import (
        find_blocked_language,
        warning_evidence_id,
    )

    # birth_time_unknown surfaces the most warnings (anchor + per-person).
    pair, warnings, blocks, ledger = _engine_output(birth_time_known=False)

    # --- ledger shape (AC-013a structural) -------------------------------
    assert isinstance(ledger, tuple) and len(ledger) > 0
    for entry in ledger:
        assert isinstance(entry, EvidenceEntry)
        assert [f.name for f in dataclasses.fields(entry)] == EVIDENCE_ENTRY_FIELDS
        assert isinstance(entry.id, str) and entry.id
        assert isinstance(entry.kind, EvidenceKind)
        assert isinstance(entry.source_ref, str) and entry.source_ref
        assert isinstance(entry.description, str) and entry.description

    # --- exactly one entry per distinct evidence id ----------------------
    ledger_ids = [entry.id for entry in ledger]
    assert len(ledger_ids) == len(set(ledger_ids)), (
        f"duplicate ledger ids: {ledger_ids!r}"
    )
    ledger_id_set = set(ledger_ids)

    # --- forward coverage: every block evidence id resolves (no dangling) -
    for block in blocks:
        for evidence_id in block.evidence_ids:
            assert evidence_id in ledger_id_set, (
                f"block {block.id!r} references unmaterialized "
                f"evidence id {evidence_id!r}"
            )

    # --- every emitted analysis block is covered by >=1 ledger entry -----
    for block in blocks:
        covering = [entry for entry in ledger if entry.id in block.evidence_ids]
        assert covering, f"block {block.id!r} has no covering ledger entry"

    # --- every warning is covered ----------------------------------------
    warning_ids = {warning_evidence_id(entry) for entry in warnings}
    assert warning_ids, "the birth-time-unknown input must surface warnings"
    for warning_id in warning_ids:
        assert warning_id in ledger_id_set

    # --- no orphan entries: ledger == exactly the referenced id set ------
    referenced = {eid for block in blocks for eid in block.evidence_ids}
    referenced |= warning_ids
    assert ledger_id_set == referenced, (
        f"ledger/reference mismatch: only-in-ledger="
        f"{ledger_id_set - referenced!r}, only-referenced="
        f"{referenced - ledger_id_set!r}"
    )

    # --- exactly one entry per pair layer (the three MVP layers) ---------
    pair_ids = {
        eid
        for layer in pair.layers().values()
        for eid in layer.evidence_ids
    }
    assert pair_ids <= ledger_id_set
    assert len(pair_ids) == len(PAIR_LAYER_NAMES)

    # --- kind classification: warnings are WARNING, layers are not -------
    for entry in ledger:
        if entry.id in warning_ids:
            assert entry.kind is EvidenceKind.WARNING
        elif entry.id in pair_ids:
            assert entry.kind is not EvidenceKind.WARNING

    # --- no score contributions (D1) -------------------------------------
    for entry in ledger:
        field_names = {f.name for f in dataclasses.fields(entry)}
        assert not FORBIDDEN_SCORE_KEYS & field_names
        for text in (
            entry.id,
            entry.kind.value,
            entry.source_ref,
            entry.description,
        ):
            assert find_blocked_language(text) is None, (
                f"blocked/score language in ledger string {text!r}"
            )
            for key in FORBIDDEN_SCORE_KEYS:
                assert key not in text, (
                    f"forbidden score key {key!r} in ledger string {text!r}"
                )

    # --- determinism (REQ-014 discipline) --------------------------------
    from bazi_engine.match.evidence import build_evidence_ledger

    assert build_evidence_ledger(pair, warnings) == ledger


def test_evidence_ledger_clean_input_covers_layers_and_anchor_warning() -> None:
    """AC-013a: even a fully-known birth input yields a complete ledger —
    one entry per pair layer plus the always-present unverified-anchor
    warning; no orphan entries, no score contribution."""
    from bazi_engine.match import PAIR_LAYER_NAMES
    from bazi_engine.match.textblocks import warning_evidence_id

    pair, warnings, blocks, ledger = _engine_output(birth_time_known=True)

    ledger_id_set = {entry.id for entry in ledger}
    referenced = {eid for block in blocks for eid in block.evidence_ids}
    referenced |= {warning_evidence_id(entry) for entry in warnings}
    assert ledger_id_set == referenced

    pair_ids = {
        eid
        for layer in pair.layers().values()
        for eid in layer.evidence_ids
    }
    assert len(pair_ids) == len(PAIR_LAYER_NAMES)
    assert pair_ids <= ledger_id_set

    # The shipped ruleset anchor is unverified ⇒ at least one warning entry.
    assert len(ledger) > len(PAIR_LAYER_NAMES)


# Test-name reconciliation (see module docstring): the plan §5 T6 pointer
# and the committed T5 forward-reference both name this
# ``test_evidence_ledger_complete``; alias it to the binding contract test.
test_evidence_ledger_complete = test_evidence_ledger_covers_every_block_and_warning


# ── T12 (Milestone B): observability mechanism — EV-007 / AC-013b-d, AC-015b ──
#
# The EV-007 demand-attribution mechanism (plan §5 T12, contract §1 REQ-013).
# These three run against the ASSEMBLED app (class: integration-fake). The
# core (T-013-03) is the chain-G killer: it drives one allowlisted and one
# non-allowlisted key through the real route with auth enforced and asserts
# the two calls land in DIFFERENT buckets — a test that fails if
# classification is unwired or one-bucketed, so the demand falsifier can
# never silently become unfalsifiable again. Counts + key-tier ONLY: no key
# string, no birth PII, request-id in every record.

_OBS_LOGGER = "bazi_engine.match.observability"
_MATCH_PATH = "/v1/match/bazi-hehun"

# Distinctive sentinel birth tokens (contract §0.2) — a lexically falsifiable
# PII guard: none of these may appear in any observability record.
_SENTINEL_TOKENS: Tuple[str, ...] = (
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


def _obs_blob(records: List[logging.LogRecord]) -> str:
    """Flatten observability records (message + args) into one scan blob."""
    chunks: List[str] = []
    for rec in records:
        chunks.append(rec.getMessage())
        chunks.append(str(rec.args))
    return "\n".join(chunks)


def test_metrics_and_observability_records_contain_no_pii(caplog: Any) -> None:
    """T-013-02 / AC-013b, AC-013c, AC-015b (integration-fake).

    One valid call; the observability record carries request_id, endpoint,
    ruleset id/version, warning classes, caller class + key-tier and a
    numeric ``match.request_ms`` latency measurement — and NO sentinel birth
    value and NO raw API key material (tier only).
    """
    from fastapi.testclient import TestClient

    from bazi_engine.app import app
    from bazi_engine.match.observability import caller_counts, reset_caller_counts
    from tests.fixtures.match_payloads import VALID_MATCH_REQUEST

    reset_caller_counts()
    client = TestClient(app)
    with caplog.at_level(logging.INFO, logger=_OBS_LOGGER):
        resp = client.post(
            _MATCH_PATH,
            json=VALID_MATCH_REQUEST,
            headers={"X-Request-ID": "qa-obs-nopii"},
        )
    assert resp.status_code == 200, resp.text
    request_id = resp.json()["meta"]["request_id"]

    obs_records = [r for r in caplog.records if r.name == _OBS_LOGGER]
    assert obs_records, "no observability record emitted for the match request"
    mine = [r for r in obs_records if request_id in r.getMessage()]
    assert mine, "observability record missing the request_id (AC-013c)"
    blob = _obs_blob(mine)

    # AC-015b — a numeric latency measurement for the match computation.
    assert "match.request_ms" in blob
    latency = re.search(r"match\.request_ms=([0-9]+(?:\.[0-9]+)?)", blob)
    assert latency is not None and float(latency.group(1)) >= 0.0, blob

    # T-013-02 — endpoint, ruleset id/version, warning classes, tier surfaced.
    assert _MATCH_PATH in blob
    assert "ruleset_id=" in blob and "ruleset_version=" in blob
    assert "caller_class=" in blob and "key_tier=" in blob
    assert "warning_codes=" in blob

    # AC-013b — no birth PII anywhere in the observability surface.
    for token in _SENTINEL_TOKENS:
        assert token not in blob, f"birth value {token!r} leaked into observability"

    # The demand-attribution counter advanced (unattributed dev key => external).
    assert caller_counts()["external"] >= 1


def test_team_vs_external_classification_via_key_allowlist(
    monkeypatch: Any, caplog: Any
) -> None:
    """T-013-03 / AC-013d / EV-007-mechanism (integration-fake).

    Given auth enforced and an allowlist holding K_team but not K_ext; when
    one valid call is made with each key; then the observability output
    classifies K_team's call ``team`` and K_ext's call ``external`` — two
    DIFFERENT buckets — exposing counts + key-tier ONLY (no key string, no
    PII). Kills chain G's mechanism half.
    """
    from fastapi.testclient import TestClient

    from bazi_engine.app import app
    from bazi_engine.auth import _load_keys, _load_tier_overrides
    from bazi_engine.match.observability import caller_counts, reset_caller_counts
    from tests.fixtures.match_payloads import VALID_MATCH_REQUEST

    k_team = "ff_pro_teamkey0001"
    k_ext = "ff_pro_extkey0002"
    monkeypatch.setenv("FUFIRE_REQUIRE_API_KEYS", "true")
    monkeypatch.setenv("FUFIRE_API_KEYS", f"{k_team},{k_ext}")
    monkeypatch.setenv("FUFIRE_TEAM_KEY_ALLOWLIST", k_team)
    _load_keys.cache_clear()
    _load_tier_overrides.cache_clear()
    reset_caller_counts()

    # FUFIRE-009: X-Request-ID must be a UUID (contract format:uuid) —
    # non-UUID ids are replaced by the middleware, so use real UUIDs.
    rid_team = str(uuid_mod.uuid4())
    rid_ext = str(uuid_mod.uuid4())
    client = TestClient(app)
    try:
        with caplog.at_level(logging.INFO, logger=_OBS_LOGGER):
            r_team = client.post(
                _MATCH_PATH,
                json=VALID_MATCH_REQUEST,
                headers={"X-API-Key": k_team, "X-Request-ID": rid_team},
            )
            r_ext = client.post(
                _MATCH_PATH,
                json=VALID_MATCH_REQUEST,
                headers={"X-API-Key": k_ext, "X-Request-ID": rid_ext},
            )
        assert r_team.status_code == 200, r_team.text
        assert r_ext.status_code == 200, r_ext.text

        obs = [r for r in caplog.records if r.name == _OBS_LOGGER]
        team_rec = [r for r in obs if rid_team in r.getMessage()]
        ext_rec = [r for r in obs if rid_ext in r.getMessage()]
        assert team_rec, "no observability record for the team call"
        assert ext_rec, "no observability record for the external call"

        team_msg = team_rec[-1].getMessage()
        ext_msg = ext_rec[-1].getMessage()
        # Two DIFFERENT buckets — the chain-G killer.
        assert "caller_class=team" in team_msg, team_msg
        assert "caller_class=external" in ext_msg, ext_msg

        # The EV-007 counters advanced in both buckets.
        counts = caller_counts()
        assert counts["team"] >= 1 and counts["external"] >= 1, counts

        # Counts + key-tier ONLY: raw key strings never appear; no birth PII.
        blob = _obs_blob(obs)
        assert k_team not in blob and k_ext not in blob, "raw API key leaked"
        assert "key_tier=pro" in team_msg and "key_tier=pro" in ext_msg
        for token in _SENTINEL_TOKENS:
            assert token not in blob, f"birth value {token!r} leaked"
    finally:
        _load_keys.cache_clear()
        _load_tier_overrides.cache_clear()


def test_request_id_propagates_into_match_logs_and_response(caplog: Any) -> None:
    """T-013-04 / AC-013c (integration-fake).

    A fixed ``X-Request-ID`` reaches the response header AND the response
    envelope AND every captured observability record (RequestIdMiddleware
    parity through the new route).
    """
    from fastapi.testclient import TestClient

    from bazi_engine.app import app
    from bazi_engine.match.observability import reset_caller_counts
    from tests.fixtures.match_payloads import VALID_MATCH_REQUEST

    reset_caller_counts()
    # FUFIRE-009: must be a valid UUID — the middleware replaces anything
    # else with a fresh id (OpenAPI contract declares format:uuid).
    fixed = str(uuid_mod.uuid4())
    client = TestClient(app)
    with caplog.at_level(logging.INFO, logger=_OBS_LOGGER):
        resp = client.post(
            _MATCH_PATH,
            json=VALID_MATCH_REQUEST,
            headers={"X-Request-ID": fixed},
        )
    assert resp.status_code == 200, resp.text
    assert resp.headers.get("X-Request-ID") == fixed
    assert resp.json()["meta"]["request_id"] == fixed

    obs = [r for r in caplog.records if r.name == _OBS_LOGGER]
    mine = [r for r in obs if fixed in r.getMessage()]
    assert mine, "observability record missing the propagated request_id"
    for rec in mine:
        assert fixed in rec.getMessage()
