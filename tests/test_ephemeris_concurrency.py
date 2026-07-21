"""
test_ephemeris_concurrency.py — NFR-ATT-4 / VCHK-07 concurrent-request skeleton.

Feature:      fufire-premium-verification-ci (WS-A increment)
PRD:          docs/prd/fufire-premium-verification-ci.prd.md (NFR-ATT-4, §3.7, §6.1)
Vision:       docs/vision/fufire-premium-verification-ci.vision.md (VCHK-07)

PRD §3.7 (verified, belegt): `railway.toml`/`Dockerfile` run a single uvicorn process with
no `--workers` override; all calculation path-operation functions are `def` (sync), so
FastAPI runs them in a shared thread pool. `western.py`'s `_SWE_LOCK` (module-level
`threading.Lock`) wraps ONLY the sidereal `swe.set_sid_mode()` / `swe.get_ayanamsa_ut()` /
reset sequence — NOT the `swe.calc_ut`/`swe.houses` calls themselves. NFR-ATT-4 requires
whichever FQ-ATT-01 mechanism (§6.1, Option A vs. B — not yet chosen, T2) is proven
thread-safe by a real concurrent-request test, not merely assumed from `pytest -q`'s
default single-threaded execution.

This file follows the "guarding concurrency fixes" lesson: a bare probabilistic
"spawn threads and hope the race happens" test is a weak regression guard on its own.
`TestExistingLockedPathConcurrencyInvariant` below instead asserts a DETERMINISTIC
invariant (each zodiac_mode's result must exactly match its own single-threaded baseline,
computed BEFORE any concurrent load starts) under real concurrent execution (a
ThreadPoolExecutor driving many overlapping HTTP requests through the actual, unmocked
`_SWE_LOCK` / `swe.set_sid_mode` / `swe.get_ayanamsa_ut` code path) — if cross-thread
ayanamsha contamination ever occurs, a tropical or sidereal response's longitude would
silently drift from its baseline. `swe.calc_ut` itself is mocked to a fixed deterministic
value (this test targets the LOCKING/shared-state code path, not ephemeris numerics, and
must run in every environment, not just ones with real .se1 files) — `swe.houses` and
`swe.get_ayanamsa_ut` are left REAL and unmocked, since neither requires ephemeris data
files (verified empirically: both succeed with no SE_EPHE_PATH configured at all) and
both are exactly the code this test needs to exercise for real.

`TestFutureMechanismConcurrencySkeleton` is the explicitly-skipped placeholder for the
part of NFR-ATT-4/VCHK-07 that genuinely cannot be tested yet: whichever mechanism T2/T4
choose (§6.1, Option A per-call-site wrapper vs. Option B import-boundary monkeypatch) is
not yet implemented, so there is nothing to concurrency-test for it. This must be
un-skipped and filled in during Phase 2 once the mechanism ADR lands — it is not
forgotten, it is explicitly parked.
"""
from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import patch

import pytest
import swisseph as swe
from fastapi.testclient import TestClient

from bazi_engine.app import app
from bazi_engine.ephemeris import EPHEMERIS_FILES_REQUIRED, ensure_ephemeris_files


# A fixed, deterministic (non-MOSEPH) calc_ut stand-in. Longitude is derived from the
# planet id only, so every call for the same body returns the exact same value
# regardless of which thread/request made it -- any cross-request drift the test
# observes must come from the (real, unmocked) ayanamsha/lock code path, not from
# calc_ut's own determinism.
def _fixed_calc_ut(jd_ut, planet_id, flags):
    return ((float(planet_id) * 7.0 % 360.0, 0.0, 1.0, 0.0, 0.0, 0.0), swe.FLG_SWIEPH)


_ZODIAC_MODES = ["tropical", "sidereal_lahiri", "sidereal_fagan_bradley"]


@pytest.fixture(autouse=True)
def _no_api_key_enforcement(monkeypatch):
    monkeypatch.setenv("FUFIRE_REQUIRE_API_KEYS", "false")
    monkeypatch.delenv("FUFIRE_API_KEYS", raising=False)
    monkeypatch.delenv("EPHEMERIS_MODE", raising=False)


def _dummy_ephe_dir(tmp_path: Path) -> Path:
    d = tmp_path / "dummy_ephe"
    d.mkdir()
    for name in EPHEMERIS_FILES_REQUIRED:
        (d / name).touch()
    return d


def _request_sun_longitude(client: TestClient, zodiac_mode: str) -> float:
    resp = client.post(
        "/calculate/western",
        json={
            "date": "1990-06-15T14:30:00",
            "tz": "Europe/Berlin",
            "lon": 13.405,
            "lat": 52.52,
            "zodiac_mode": zodiac_mode,
        },
    )
    assert resp.status_code == 200, f"{zodiac_mode}: expected 200, got {resp.status_code}: {resp.text}"
    return resp.json()["bodies"]["Sun"]["longitude"]


class TestExistingLockedPathConcurrencyInvariant:
    """Exercises the CURRENT code's `_SWE_LOCK`-guarded sidereal path under real
    concurrent load. This is a regression baseline for NFR-ATT-4/VCHK-07 against
    the code that exists TODAY -- it is deliberately independent of the not-yet-
    chosen §6.1 mechanism (see TestFutureMechanismConcurrencySkeleton below)."""

    def test_concurrent_mixed_zodiac_requests_match_sequential_baseline(self, tmp_path):
        ephe_dir = _dummy_ephe_dir(tmp_path)
        ensure_ephemeris_files.cache_clear()
        client = TestClient(app)

        with patch.dict(os.environ, {"SE_EPHE_PATH": str(ephe_dir)}):
            with patch("bazi_engine.western.swe.calc_ut", side_effect=_fixed_calc_ut):
                # 1. Sequential baseline per zodiac_mode, BEFORE any concurrent load.
                baseline: Dict[str, float] = {
                    mode: _request_sun_longitude(client, mode) for mode in _ZODIAC_MODES
                }
                assert baseline["tropical"] != baseline["sidereal_lahiri"], (
                    "sanity check: tropical and sidereal_lahiri must differ (ayanamsha "
                    "correction must actually be applied) or this invariant is vacuous"
                )
                assert baseline["sidereal_lahiri"] != baseline["sidereal_fagan_bradley"], (
                    "sanity check: the two sidereal systems must use different ayanamsha "
                    "values or this invariant cannot detect cross-system contamination"
                )

                # 2. Real concurrent load: many overlapping requests, mixed zodiac_mode,
                #    driven across a real thread pool (not a single-threaded loop) so the
                #    unmocked `_SWE_LOCK` / swe.set_sid_mode / swe.get_ayanamsa_ut path is
                #    genuinely exercised under contention.
                n_workers = 16
                n_requests = 160
                jobs = [_ZODIAC_MODES[i % len(_ZODIAC_MODES)] for i in range(n_requests)]

                results: List[float] = [None] * n_requests  # type: ignore[list-item]

                def _run(i: int) -> None:
                    results[i] = _request_sun_longitude(client, jobs[i])

                with ThreadPoolExecutor(max_workers=n_workers) as pool:
                    list(pool.map(_run, range(n_requests)))

        ensure_ephemeris_files.cache_clear()

        # 3. Deterministic invariant: every concurrent result must exactly match its
        #    OWN zodiac_mode's sequential baseline. Any cross-thread ayanamsha
        #    contamination (e.g. a tropical request observing a residual sidereal
        #    sid_mode, or one sidereal system observing another's ayanamsha value)
        #    would show up here as a value mismatch, not as an exception -- this is
        #    exactly the "false pass under a single-threaded test run" failure mode
        #    NFR-ATT-4/VCHK-07 exists to rule out.
        mismatches = [
            (i, jobs[i], results[i], baseline[jobs[i]])
            for i in range(n_requests)
            if results[i] != baseline[jobs[i]]
        ]
        assert not mismatches, (
            f"{len(mismatches)}/{n_requests} concurrent requests diverged from their "
            f"zodiac_mode's sequential baseline (cross-request ephemeris-state "
            f"corruption under concurrency) -- first few: {mismatches[:5]}"
        )


_LEGIT_BODY = {
    "date": "1990-06-15T14:30:00", "tz": "Europe/Berlin", "lon": 13.405, "lat": 52.52,
}
_MOSEPH_BODY = {
    # A date ~15 years away from _LEGIT_BODY's -- Julian day difference is
    # ~5500 days, trivially distinguishable by the mock below from any
    # possible ambiguity/rounding, so each concurrent request's logical
    # population (legit vs. forced-MOSEPH) is unambiguous from jd_ut alone.
    "date": "2005-03-10T09:15:00", "tz": "Europe/Berlin", "lon": 13.405, "lat": 52.52,
}

# Approximate (UTC-naive) Julian days for the two dates above -- only used to
# bucket which logical population a given swe.calc_ut call belongs to, so
# exact precision (down to the TZ-conversion) is not required, just that the
# two buckets are far enough apart to never be ambiguous (they are, by ~5500
# days, against an hours-scale error tolerance).
_LEGIT_JD_APPROX = swe.julday(1990, 6, 15, 14.5)
_MOSEPH_JD_APPROX = swe.julday(2005, 3, 10, 9.25)


def _mixed_calc_ut(jd_ut, planet_id, flags):
    """Deterministic, thread-safe stand-in for swe.calc_ut used to simulate TWO
    concurrently-in-flight populations of requests against the SAME shared
    thread pool: a legitimate-SWIEPH population and a forced-MOSEPH population.

    Classifies each call by its jd_ut (a pure function of its arguments -- no
    shared mutable state, so this mock itself cannot be the source of any
    cross-request contamination the test observes) and returns the matching
    attested/unattested shape. This lets a single `patch()` context mix both
    scenarios across a real ThreadPoolExecutor without needing any thread-local
    state (which would not reliably propagate across FastAPI's own internal
    request-handling thread dispatch anyway).
    """
    if abs(jd_ut - _MOSEPH_JD_APPROX) < abs(jd_ut - _LEGIT_JD_APPROX):
        # Forced-MOSEPH logical request: SWIEPH was requested (western.py never
        # asks for MOSEPH explicitly) but MOSEPH was silently used -- the exact
        # shape assert_no_moseph_fallback exists to catch.
        return ((float(planet_id) * 3.0 % 360.0, 0.0, 1.0, 0.0, 0.0, 0.0), swe.FLG_MOSEPH)
    # Legitimate logical request: real, attested SWIEPH result.
    return ((float(planet_id) * 7.0 % 360.0, 0.0, 1.0, 0.0, 0.0, 0.0), swe.FLG_SWIEPH)


class TestFutureMechanismConcurrencySkeleton:
    """NFR-ATT-4/VCHK-07 (full scope). T2/T4 landed the chosen FQ-ATT-01
    mechanism -- `SwissEphBackend.calc_ut()`/`.houses()`/`_attested` (ADR-1,
    ADR-2) -- so this is no longer a skeleton: it empirically proves ADR-2's
    per-instance `_attested` design claim ("each call site constructs its own
    backend -- concurrent requests/threads never observe each other's
    attestation state") under REAL concurrent HTTP traffic against a
    house-computing endpoint (`/calculate/western`), mixing legitimate-SWIEPH
    and forced-MOSEPH requests IN THE SAME shared thread pool (mirroring
    FastAPI's sync-endpoint threadpool-dispatch model, PRD §3.7)."""

    def test_chosen_mechanism_is_thread_safe_under_shared_threadpool(self, tmp_path):
        ephe_dir = _dummy_ephe_dir(tmp_path)
        ensure_ephemeris_files.cache_clear()
        client = TestClient(app)

        n_workers = 16
        n_requests = 160
        # Interleave the two populations across worker submission order so
        # both are genuinely in flight on the shared thread pool at once, not
        # run as two sequential batches.
        jobs = [_LEGIT_BODY if i % 2 == 0 else _MOSEPH_BODY for i in range(n_requests)]
        responses: List[Any] = [None] * n_requests

        def _run(i: int) -> None:
            responses[i] = client.post("/calculate/western", json=jobs[i])

        with patch.dict(os.environ, {"SE_EPHE_PATH": str(ephe_dir)}):
            with patch("bazi_engine.western.swe.calc_ut", side_effect=_mixed_calc_ut):
                with ThreadPoolExecutor(max_workers=n_workers) as pool:
                    list(pool.map(_run, range(n_requests)))

        ensure_ephemeris_files.cache_clear()

        legit_results = [responses[i] for i in range(n_requests) if jobs[i] is _LEGIT_BODY]
        moseph_results = [responses[i] for i in range(n_requests) if jobs[i] is _MOSEPH_BODY]
        assert len(legit_results) == len(moseph_results) == n_requests // 2  # sanity check

        # No false negatives: every legitimate-SWIEPH request must succeed --
        # never wrongly 503 because it observed a concurrent forced-MOSEPH
        # request's lack of attestation (a shared/leaked `_attested` state
        # would manifest as spurious failures here).
        legit_failures = [r for r in legit_results if r.status_code != 200]
        assert not legit_failures, (
            f"{len(legit_failures)}/{len(legit_results)} legitimate-SWIEPH concurrent "
            f"requests wrongly failed under shared-threadpool contention -- possible "
            f"cross-request _attested contamination. First failure: "
            f"{legit_failures[0].status_code} {legit_failures[0].text}"
        )
        for r in legit_results:
            assert r.json()["quality_flags"]["ephemeris_mode"] == "SWIEPH"

        # No false positives: every forced-MOSEPH request must be hard-rejected
        # -- never wrongly 200 by "borrowing" a concurrent legitimate request's
        # attested calc_ut() success. This is exactly the cross-request
        # attestation leakage ADR-2's per-instance `_attested` design claims to
        # rule out -- empirically proven here, not just argued in the ADR's prose.
        moseph_successes = [r for r in moseph_results if r.status_code == 200]
        assert not moseph_successes, (
            f"{len(moseph_successes)}/{len(moseph_results)} forced-MOSEPH concurrent "
            f"requests wrongly succeeded under shared-threadpool contention -- this is "
            f"exactly the cross-request _attested leakage ADR-2's per-instance design "
            f"must rule out (VCHK-07: demonstrated, not just documented)."
        )
        for r in moseph_results:
            assert r.status_code == 503, (
                f"forced-MOSEPH concurrent request expected 503, got "
                f"{r.status_code}: {r.text}"
            )
            assert r.json().get("error") == "ephemeris_unavailable"
