"""Tests for bazi-hehun determinism (REQ-014).

T7 (contract T-014-01..03, docs/testing/bazi-hehun.acceptance-tests.md):
the binding test names are implemented at the highest boundary that EXISTS
in Milestone A — the pure match engine (canonical hash over the FULL engine
output, pre-HTTP). The contract's evidence class for T-014-02/03 is
integration-fake (assembled app); Milestone B (T9) lifts the same
byte-stability + hash-recomputability assertions onto
``POST /v1/match/bazi-hehun`` once the route exists (the router adds the
volatile ``request_id``/timestamp fields the contract excludes — pre-HTTP
there are none, so the whole engine output is stable).

The canonical-JSON function under test is ``bazi_engine.match.canonical``
(same discipline as ``bafe/canonical_json.py``: ``sort_keys`` +
``sha256``), kept in-package to avoid widening the Level-5 carve-out
(plan §4.4). Determinism is asserted WITHIN an ephemeris mode, never
ACROSS modes (contract §0.3); T-014-03 keys its snapshot by the active
``EPHEMERIS_MODE`` (``tests/snapshots/<mode>/match_*.json``), so SWIEPH
values are only ever asserted when SE1 files are present — the active mode
is SWIEPH only then (conftest forces MOSEPH without SE1). Snapshots
auto-generate on first run (``UPDATE_SNAPSHOTS=1`` regenerates), matching
the ``test_snapshot_stability.py`` idiom (which likewise commits both a
``moseph/`` and a ``swieph/`` golden per case).

Snapshot provenance (T7 review round 1): both the ``moseph/`` and the
``swieph/`` ``match_*.json`` golden are genuine backend output — each was
produced by running this test under its respective active backend and
confirmed byte-identical on regeneration. The ``swieph/`` golden were
regenerated and verified on an SE1-present host (``SwissEphBackend.mode ==
"SWIEPH"``, all four SE1 files resolvable); they equal the ``moseph/``
golden only because these two coarse sentinel pillar sets do not diverge
between backends — NOT because they were copied. On an SE1-less host the
active mode is MOSEPH, the ``swieph/`` golden are inert (never read), and
they re-verify on the next genuine SWIEPH run.
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Tuple

from tests.fixtures.match_payloads import (
    GOLDEN_MATCH_PAIRS,
    VALID_MATCH_REQUEST,
)

_SNAPSHOTS_BASE = Path(__file__).parent / "snapshots"
UPDATE_SNAPSHOTS = os.environ.get("UPDATE_SNAPSHOTS", "0") == "1"

FORBIDDEN_SCORE_KEYS = {
    "total_score",
    "sub_scores",
    "score_class",
    "awarded_points",
    "score_confidence",
}

# The frozen key set of the full pre-HTTP engine output. The router (T9)
# wraps this with provenance / quality_flags / precision / request_id;
# none of those belong to the deterministic engine core.
_ENGINE_OUTPUT_KEYS = {
    "schema_version",
    "individual",
    "pair",
    "raw_analysis_text",
    "warnings",
    "evidence_ledger",
}


def _ephemeris_tag() -> str:
    """Return ``'swieph'`` or ``'moseph'`` for the ACTIVE backend.

    Mirrors ``test_snapshot_stability._ephemeris_tag`` so determinism
    snapshots key off the same mode directory.
    """
    mode = os.environ.get("EPHEMERIS_MODE", "").upper()
    if mode == "MOSEPH":
        return "moseph"
    try:
        from bazi_engine.ephemeris import (
            EPHEMERIS_FILES_REQUIRED,
            _resolve_ephe_path,
        )

        path = _resolve_ephe_path(None)
        if all((path / name).exists() for name in EPHEMERIS_FILES_REQUIRED):
            return "swieph"
    except ImportError:
        pass
    return "moseph"


def _dedupe_warnings(warnings: Tuple[Any, ...]) -> List[Any]:
    """Distinct surfaced warnings, first-seen order, keyed by (code, subject).

    Matches the de-duplication discipline of ``build_text_blocks`` /
    ``build_evidence_ledger`` so the engine-output ``warnings`` list has
    exactly one entry per distinct warning the ledger covers.
    """
    seen: set = set()
    distinct: List[Any] = []
    for entry in warnings:
        key = (entry.code, entry.subject)
        if key in seen:
            continue
        seen.add(key)
        distinct.append(entry)
    return distinct


def _run_engine(
    person_a: Dict[str, Any],
    person_b: Dict[str, Any],
    *,
    birth_time_known_a: bool = True,
    birth_time_known_b: bool = True,
) -> Dict[str, Any]:
    """Compose the FULL pre-HTTP engine output for a person pair.

    The exact Level-4 pipeline the router (T9) will drive: ``compute_bazi``
    per person → ``normalize_chart`` → ``analyze_individual`` →
    ``analyze_pair`` → ``build_text_blocks`` / ``build_evidence_ledger``.
    No HTTP shaping, no request_id/timestamp — only the deterministic core.
    """
    from bazi_engine.bazi import compute_bazi
    from bazi_engine.match import (
        MATCH_SCHEMA_VERSION,
        analyze_individual,
        analyze_pair,
        build_evidence_ledger,
        build_text_blocks,
        normalize_chart,
    )
    from bazi_engine.types import BaziInput

    def _input(payload: Dict[str, Any]) -> "BaziInput":
        return BaziInput(
            birth_local=payload["date"],
            timezone=payload["tz"],
            longitude_deg=payload["lon"],
            latitude_deg=payload["lat"],
        )

    chart_a = normalize_chart(
        compute_bazi(_input(person_a)),
        birth_time_known=birth_time_known_a,
        subject="person_a",
    )
    chart_b = normalize_chart(
        compute_bazi(_input(person_b)),
        birth_time_known=birth_time_known_b,
        subject="person_b",
    )
    individual_a = analyze_individual(chart_a, subject="person_a")
    individual_b = analyze_individual(chart_b, subject="person_b")
    pair = analyze_pair(individual_a, individual_b)

    # Both persons' warnings concatenated (the router's T9 input); the
    # block/ledger builders de-duplicate internally, so pass the raw union.
    all_warnings = chart_a.warnings + chart_b.warnings
    text_blocks = build_text_blocks(pair, warnings=all_warnings)
    evidence_ledger = build_evidence_ledger(pair, warnings=all_warnings)

    return {
        "schema_version": MATCH_SCHEMA_VERSION,
        "individual": {"person_a": individual_a, "person_b": individual_b},
        "pair": pair.layers(),
        "raw_analysis_text": list(text_blocks),
        "warnings": _dedupe_warnings(all_warnings),
        "evidence_ledger": list(evidence_ledger),
    }


def _run_valid_request() -> Dict[str, Any]:
    """Full engine output for the canonical ``VALID_MATCH_REQUEST``."""
    return _run_engine(
        VALID_MATCH_REQUEST["person_a"], VALID_MATCH_REQUEST["person_b"]
    )


# ── T-014-01 / AC-014a — order-independent canonical hash (unit-fake) ────────


def _reorder_keys(obj: Any) -> Any:
    """Rebuild ``obj`` with every dict's keys in REVERSED insertion order.

    Semantically identical document, deliberately different key order at
    every object level — the falsifiable input for an order-independent
    canonicalization.
    """
    if isinstance(obj, dict):
        return {k: _reorder_keys(obj[k]) for k in reversed(list(obj))}
    if isinstance(obj, list):
        return [_reorder_keys(x) for x in obj]
    return obj


def test_canonical_hash_invariant_under_json_key_order() -> None:
    """T-014-01 / AC-014a: two semantically identical request docs with
    permuted key order canonicalize to the SAME bytes and the SAME hash;
    mutating a single value changes the hash."""
    from bazi_engine.match.canonical import canonical_dumps, canonical_hash

    doc = copy.deepcopy(VALID_MATCH_REQUEST)
    permuted = _reorder_keys(doc)

    # The inputs really are permuted (guards against a no-op reorder).
    assert list(doc) != list(permuted)

    # Order-independence: identical canonical bytes ⇒ identical hash.
    assert canonical_dumps(permuted) == canonical_dumps(doc)
    assert canonical_hash(permuted) == canonical_hash(doc)

    # Value-sensitivity: any changed value flips the hash.
    mutated = copy.deepcopy(doc)
    mutated["person_a"]["lon"] = doc["person_a"]["lon"] + 1.0
    assert canonical_hash(mutated) != canonical_hash(doc)

    consent_flip = copy.deepcopy(doc)
    consent_flip["options"]["second_person_consent_confirmed"] = False
    assert canonical_hash(consent_flip) != canonical_hash(doc)


# ── T-014-02 / AC-014a/b — byte-stable engine core across identical runs ─────


def test_repeated_identical_requests_yield_byte_stable_core() -> None:
    """T-014-02 / AC-014a/b (pre-HTTP boundary, see module docstring):
    running the full engine twice on the same request serializes to
    byte-identical canonical JSON, the canonical hash is identical across
    runs AND recomputable from the serialized body. Pre-HTTP the output
    carries NO volatile fields (request_id/timestamp are added only by the
    router, T9), so the whole core is stable — the exclusion list is empty
    and asserted so."""
    from bazi_engine.match.canonical import canonical_dumps, canonical_hash

    out1 = _run_valid_request()
    out2 = _run_valid_request()

    # The engine core has exactly the documented keys and no volatile field.
    assert set(out1) == _ENGINE_OUTPUT_KEYS
    dumped1 = canonical_dumps(out1)
    dumped2 = canonical_dumps(out2)
    assert "request_id" not in dumped1  # volatile fields are router-only (T9)
    assert "timestamp" not in dumped1
    assert not FORBIDDEN_SCORE_KEYS.intersection(json.loads(dumped1).keys())

    # Byte-stable core across identical runs.
    assert dumped1 == dumped2

    # Canonical hash: stable across runs AND recomputable from the body.
    assert canonical_hash(out1) == canonical_hash(out2)
    assert (
        canonical_hash(out1)
        == hashlib.sha256(dumped1.encode("utf-8")).hexdigest()
    )


# ── T-014-03 / AC-014b — per-ephemeris-mode fixture snapshot stability ───────


def _write_snapshot(path: Path, jsonable: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(jsonable, indent=2, ensure_ascii=False, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )


def test_fixture_snapshot_stability_per_ephemeris_mode() -> None:
    """T-014-03 / AC-014b: for ≥2 golden pairs (one with
    ``birth_time_known=false``), the full engine output equals the
    committed snapshot for the ACTIVE ephemeris mode
    (``tests/snapshots/<mode>/match_<id>.json``). Stability is asserted
    WITHIN a mode, never across modes; a missing baseline is generated on
    first run (``UPDATE_SNAPSHOTS=1`` regenerates)."""
    from bazi_engine.match.canonical import canonical_dumps, to_jsonable

    assert len(GOLDEN_MATCH_PAIRS) >= 2
    assert any(
        not pair["birth_time_known_b"] or not pair["birth_time_known_a"]
        for pair in GOLDEN_MATCH_PAIRS
    ), "at least one golden pair must exercise birth_time_known=false"

    snap_dir = _SNAPSHOTS_BASE / _ephemeris_tag()
    for pair in GOLDEN_MATCH_PAIRS:
        output = _run_engine(
            pair["person_a"],
            pair["person_b"],
            birth_time_known_a=pair["birth_time_known_a"],
            birth_time_known_b=pair["birth_time_known_b"],
        )
        jsonable = to_jsonable(output)
        path = snap_dir / f"match_{pair['id']}.json"

        if UPDATE_SNAPSHOTS or not path.exists():
            _write_snapshot(path, jsonable)
            # Freshly generated baseline: still assert self-consistency.
            assert canonical_dumps(json.loads(path.read_text())) == (
                canonical_dumps(output)
            )
            continue

        stored = json.loads(path.read_text(encoding="utf-8"))
        assert canonical_dumps(stored) == canonical_dumps(output), (
            f"determinism drift for golden pair {pair['id']!r} in "
            f"{_ephemeris_tag()} mode (set UPDATE_SNAPSHOTS=1 to rebaseline "
            "only if the change is intended)"
        )
