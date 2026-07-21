"""Tests for the bazi-hehun performance boundary (REQ-015).

T13 (contract T-015-01/02, docs/testing/bazi-hehun.acceptance-tests.md §1
REQ-015 / §5). Milestone B, Iteration 2. TEST-ONLY: the production code this
exercises is already shipped (the pure ``bazi_engine.match`` engine from
Milestone A and the T12 latency/observability wiring in
``routers/match.py``); this task adds no production code.

The Gegenthese the tester pinned for REQ-015 is that a hard local latency
assertion ("overhead < 250ms") proves nothing about the deployed p95 and
rots into a skipped, flaky gate while NO metric is actually emitted. So the
acceptance tests deliberately do NOT assert a wall-clock budget. They assert
the two properties that ARE locally falsifiable:

* **T-015-01 / AC-015a — purity.** After the two charts are computed
  (``compute_bazi`` — the only step that may touch the ephemeris on disk),
  the entire match computation is pure and in-memory: no disk, no network.
  We prove it by running the real ``bazi_engine.match`` engine chain
  (normalize → individual → pair → text blocks → evidence ledger → canonical
  serialization) with ``builtins.open`` / ``io.open`` / ``os.open`` and
  ``socket.socket`` / ``socket.create_connection`` all monkeypatched to
  raise. A positive control confirms the tripwire is genuinely armed (a real
  ``open`` / ``socket`` call under the guard DOES raise), so the test is a
  real falsifier — it fails the moment any ``match/*`` code touches disk or
  the network — not a tautology. Determinism is re-checked here too:
  twice-same-input ⇒ byte-identical canonical output.

* **T-015-02 / AC-015b — the measurement wiring exists.** One valid request
  through the ASSEMBLED app emits a numeric ``match.request_ms`` latency for
  the match COMPUTATION, distinct from the middleware's total request time
  (``X-Response-Time-ms``): the compute window is a strict sub-interval of
  the whole-request window, so ``match.request_ms <= X-Response-Time-ms``.

AC-015c — DEFERRAL NOTE (binding, not a test here). The live full-request
p95 latency baseline and the revision of the 250ms overhead target are a
DEPLOYED-SYSTEM fact and are NOT automatable in this repo: they are named
real-boundary item RB-3 in docs/testing/bazi-hehun.acceptance-tests.md §3
and are carried out in plan task T22 (Milestone E — requires a Railway
deploy, MISSING-005). No local test can stand in for it; asserting a dev-box
timing here would be exactly the false gate the Gegenthese warns against.
Per the test-contract §6 count, this file carries EXACTLY the two functions
below; AC-015c stays a documented deferral, never a green-looking stub.
"""
from __future__ import annotations

import builtins
import io
import logging
import os
import re
import socket
from typing import Any, Dict

import pytest

from bazi_engine.bazi import compute_bazi
from bazi_engine.bazi_rules import load_default_ruleset
from bazi_engine.match import (
    MATCH_SCHEMA_VERSION,
    analyze_individual,
    analyze_pair,
    build_evidence_ledger,
    build_text_blocks,
    normalize_chart,
)
from bazi_engine.match.canonical import canonical_dumps
from bazi_engine.match.observability import LATENCY_METRIC
from bazi_engine.types import BaziInput
from tests.fixtures.match_payloads import (
    SENTINEL_A,
    SENTINEL_B,
    VALID_MATCH_REQUEST,
)

_OBS_LOGGER = "bazi_engine.match.observability"
_MATCH_PATH = "/v1/match/bazi-hehun"


class _ForbiddenIOError(RuntimeError):
    """Raised by the tripwire when guarded code performs real disk/network I/O.

    A dedicated exception type so the purity assertion is unambiguous and no
    accidental broad ``except`` inside engine code could swallow it as benign.
    """


def _install_io_tripwire(monkeypatch: pytest.MonkeyPatch) -> None:
    """Monkeypatch every real disk/network primitive to raise.

    Covers file opens through all three funnels the engine could plausibly
    reach — ``builtins.open`` (and ``io.open`` / ``os.open``; ``Path.read_text``
    and ``json`` ruleset loads route through these) — and socket creation
    (``socket.socket`` / ``socket.create_connection``). ``monkeypatch``
    auto-reverts at teardown. Under this guard, ANY disk or network access
    raises :class:`_ForbiddenIOError` instead of silently doing I/O.
    """

    def _blocked(what: str) -> Any:
        def _raise(*args: Any, **kwargs: Any) -> Any:
            raise _ForbiddenIOError(
                f"forbidden {what} inside the pure match computation"
            )

        return _raise

    monkeypatch.setattr(builtins, "open", _blocked("disk open (builtins.open)"))
    monkeypatch.setattr(io, "open", _blocked("disk open (io.open)"))
    monkeypatch.setattr(os, "open", _blocked("disk open (os.open)"))
    monkeypatch.setattr(socket, "socket", _blocked("socket creation"))
    monkeypatch.setattr(
        socket, "create_connection", _blocked("socket connect")
    )


def _bazi_input(payload: Dict[str, Any]) -> BaziInput:
    """Build a ``BaziInput`` from a birth payload (same idiom as the router)."""
    return BaziInput(
        birth_local=payload["date"],
        timezone=payload["tz"],
        longitude_deg=payload["lon"],
        latitude_deg=payload["lat"],
    )


def _pure_engine_bytes(
    result_a: Any, result_b: Any, ruleset: Dict[str, Any]
) -> str:
    """Run the match engine chain DOWNSTREAM of ``compute_bazi``, pre-HTTP.

    normalize → individual → pair → text blocks → evidence ledger → canonical
    serialization. The pre-loaded ``ruleset`` is passed explicitly to every
    ruleset-aware function so none of them reaches for disk. Every symbol used
    is imported at module top (before any tripwire is installed), so calling
    them here re-opens no source file. Returns the canonical-JSON bytes of the
    full deterministic engine core.
    """
    chart_a = normalize_chart(
        result_a, birth_time_known=True, subject="person_a", ruleset=ruleset
    )
    chart_b = normalize_chart(
        result_b, birth_time_known=True, subject="person_b", ruleset=ruleset
    )
    individual_a = analyze_individual(
        chart_a, subject="person_a", ruleset=ruleset
    )
    individual_b = analyze_individual(
        chart_b, subject="person_b", ruleset=ruleset
    )
    pair = analyze_pair(individual_a, individual_b)
    warnings = chart_a.warnings + chart_b.warnings
    text_blocks = build_text_blocks(pair, warnings=warnings)
    evidence_ledger = build_evidence_ledger(pair, warnings)

    output = {
        "schema_version": MATCH_SCHEMA_VERSION,
        "individual": {"person_a": individual_a, "person_b": individual_b},
        "pair": pair.layers(),
        "raw_analysis_text": list(text_blocks),
        "warnings": list(warnings),
        "evidence_ledger": list(evidence_ledger),
    }
    return canonical_dumps(output)


# ── T-015-01 / AC-015a — the match computation is pure after the two charts ──


def test_pair_analysis_is_pure_after_charts_available(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """T-015-01 / AC-015a (unit-fake).

    Given two precomputed chart objects; when the match engine chain runs
    with all filesystem and network primitives monkeypatched to raise; then
    it completes doing NO I/O, and twice-same-input yields identical output.
    """
    # Precompute phase — OUTSIDE the guard. ``compute_bazi`` is the only step
    # allowed to touch the ephemeris on disk (the "two charts"); warm the
    # ruleset cache here too so the guarded region never reaches for it.
    ruleset = load_default_ruleset()
    result_a = compute_bazi(_bazi_input(SENTINEL_A))
    result_b = compute_bazi(_bazi_input(SENTINEL_B))

    _install_io_tripwire(monkeypatch)

    # Positive control: the tripwire is genuinely armed — a real disk open and
    # a real socket DO raise under the guard. This makes the purity assertion
    # a true falsifier (it fails if match/* touches disk/network), not a no-op.
    with pytest.raises(_ForbiddenIOError):
        open(os.devnull)  # noqa: SIM115 — intentional guard probe, not real I/O
    with pytest.raises(_ForbiddenIOError):
        socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    # The real match engine runs entirely in-memory under the guard: if any
    # match/* code touched disk or the network it would raise here (AC-015a).
    out1 = _pure_engine_bytes(result_a, result_b, ruleset)
    out2 = _pure_engine_bytes(result_a, result_b, ruleset)

    # Completed with no I/O AND twice-same-input ⇒ byte-identical output.
    assert out1 == out2
    assert MATCH_SCHEMA_VERSION in out1


# ── T-015-02 / AC-015b — a compute-scoped latency metric is emitted ──────────


def test_latency_metric_emitted_per_match_request(caplog: Any) -> None:
    """T-015-02 / AC-015b (integration-fake).

    One valid request through the assembled app emits a numeric
    ``match.request_ms`` latency measurement for the match COMPUTATION,
    distinct from the middleware's total request time
    (``X-Response-Time-ms``) — the compute window is a strict sub-interval of
    the whole-request window, so ``match.request_ms <= X-Response-Time-ms``.
    """
    from fastapi.testclient import TestClient

    from bazi_engine.app import app
    from bazi_engine.match.observability import reset_caller_counts

    reset_caller_counts()
    client = TestClient(app)
    with caplog.at_level(logging.INFO, logger=_OBS_LOGGER):
        resp = client.post(
            _MATCH_PATH,
            json=VALID_MATCH_REQUEST,
            headers={"X-Request-ID": "qa-perf-latency"},
        )
    assert resp.status_code == 200, resp.text
    request_id = resp.json()["meta"]["request_id"]

    # The observability record for THIS request carries the latency metric.
    obs_records = [r for r in caplog.records if r.name == _OBS_LOGGER]
    mine = [r for r in obs_records if request_id in r.getMessage()]
    assert mine, "no observability record carried the request_id (AC-013c)"
    blob = "\n".join(r.getMessage() for r in mine)

    assert LATENCY_METRIC == "match.request_ms"
    match_hit = re.search(
        r"match\.request_ms=([0-9]+(?:\.[0-9]+)?)", blob
    )
    assert match_hit is not None, f"no {LATENCY_METRIC} metric emitted: {blob}"
    match_ms = float(match_hit.group(1))
    assert match_ms >= 0.0

    # Distinct from the total request time: the middleware measures the whole
    # request (same perf_counter clock) and exposes it as X-Response-Time-ms;
    # the match compute window is strictly inside it.
    total_header = resp.headers.get("X-Response-Time-ms")
    assert total_header is not None, "middleware total-time header missing"
    total_ms = float(total_header)
    assert total_ms >= 0.0
    # +1.0ms tolerates the header's 2-decimal rounding; the compute window is a
    # strict sub-interval, so the metric can never meaningfully exceed the total.
    assert match_ms <= total_ms + 1.0, (
        f"match.request_ms={match_ms} exceeds total X-Response-Time-ms="
        f"{total_ms} — the compute metric is not a sub-interval of the "
        "whole-request time"
    )
