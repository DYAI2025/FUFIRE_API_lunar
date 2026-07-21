"""
test_ephemeris_attestation.py — FQ-ATT-01 acceptance tests (Phase 1 / TESTER contract).

Feature:      fufire-premium-verification-ci (WS-A increment)
PRD:          docs/prd/fufire-premium-verification-ci.prd.md (FQ-ATT-01, §7)
Vision:       docs/vision/fufire-premium-verification-ci.vision.md (VCHK-01a, VCHK-01b, VCHK-03)
Traceability: docs/traceability.md § fufire-premium-verification-ci

THIS FILE IS WRITTEN BEFORE IMPLEMENTATION (Phase 1, TESTER role). Every test below is
expected to be RED against the current tree — that is correct, not a bug in the test.
Do not soften assertions or add xfail/skip markers to make it pass prematurely; T2/T4/T6
(planner + coder, Phase 2) must make these tests pass by migrating the call sites.

── The AC-01-4a / AC-01-4b split (do not collapse these back into one test) ─────────────
The PRD's own spec-audit found that a single "empty SE_EPHE_PATH directory" test is
VACUOUS for any call site that is protected by `SwissEphBackend.__post_init__`'s
construction-time `ensure_ephemeris_files()` guard PLUS a per-call return-flag check
(`assert_no_moseph_fallback`): the construction-time guard raises first, so the test
would pass identically whether or not the return-flag-checking wrapper is migrated
correctly, is broken, or is missing entirely. AC-01-4a exists specifically to reach and
exercise the return-flag-check code path (files present, flags mocked to MOSEPH).
AC-01-4b (empty-directory) is the *correct* methodology for call sites whose only
protection is construction-time (no per-call flag to check at all).

Evidence-based endpoint classification (verified by direct read, not assumed):
  AC-01-4a (flag-checkable class — mocked `swe.calc_ut` return flags):
    western  -> bazi_engine/western.py:64          (swe.calc_ut, checked inline)
    transit  -> bazi_engine/transit.py:131          (swe.calc_ut, checked inline)
    fusion   -> internally calls compute_western_chart() -> same western.py:64 path
    wuxing   -> internally calls compute_western_chart() -> same western.py:64 path
    daily    -> internally calls compute_western_chart() -> same western.py:64 path
  AC-01-4b (construction-time-guard / flag-less class — empty ephemeris directory):
    bazi     -> compute_bazi() only calls backend.solcross_ut()/delta_t_seconds(),
                neither of which checks return flags (solcross_ut returns a bare float,
                see ephemeris.py's own docstring) — its ONLY protection today is
                SwissEphBackend.__post_init__'s ensure_ephemeris_files() check.
    health   -> routers/info.py:90 `_check_ephemeris()` calls the bare global
                `swisseph.calc_ut` directly — no SwissEphBackend construction at all,
                no flags argument, no assertion. The one genuinely-unguarded site (PRD §3.1).

AC-01-3 (houses class) is tested separately below against the house-computing endpoints
(western, fusion) under the same empty-directory condition, because `swe.houses*` returns
no flag in any variant (PRD §3.3) — construction-time guard is its only possible line of
defense, and this must be demonstrated directly, not merely inferred from AC-01-4b.
"""
from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import pytest
import swisseph as swe
from fastapi.testclient import TestClient

from bazi_engine.app import app
from bazi_engine.ephemeris import (
    EPHEMERIS_FILES_REQUIRED,
    SwissEphBackend,
    ensure_ephemeris_files,
)
from bazi_engine.exc import EphemerisUnavailableError

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _no_api_key_enforcement(monkeypatch):
    """Match the repo-wide test convention (see tests/test_endpoints.py,
    tests/test_daily_chart_type_quality_surfaced.py): these tests exercise
    calculation correctness, not auth, so API keys are not required."""
    monkeypatch.setenv("FUFIRE_REQUIRE_API_KEYS", "false")
    monkeypatch.delenv("FUFIRE_API_KEYS", raising=False)
    # Must be unset so SwissEphBackend(mode="SWIEPH") is not silently overridden
    # to MOSEPH by conftest.py's environment default when real SE1 files are
    # absent in the CI/dev sandbox — these tests supply their OWN dummy/empty
    # ephemeris directories per-test and must control the mode explicitly.
    monkeypatch.delenv("EPHEMERIS_MODE", raising=False)


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def _dummy_ephe_dir(tmp_path: Path) -> Path:
    """A directory with all 4 required .se1 files present (empty content is
    fine — construction only checks existence; the calc_ut return-flags in
    the AC-01-4a tests are separately mocked, so no real ephemeris math runs)."""
    d = tmp_path / "dummy_ephe"
    d.mkdir()
    for name in EPHEMERIS_FILES_REQUIRED:
        (d / name).touch()
    return d


def _empty_ephe_dir(tmp_path: Path) -> Path:
    d = tmp_path / "empty_ephe"
    d.mkdir()
    return d


def _moseph_calc_ut_result(*_args, **_kwargs):
    """Stand-in for swe.calc_ut that pretends SWIEPH was requested but MOSEPH
    was actually used — the exact silent-fallback shape assert_no_moseph_fallback
    exists to catch."""
    return ((100.0, 0.0, 1.0, 0.0, 0.0, 0.0), swe.FLG_MOSEPH)


def _benign_solcross_ut(*_args, **_kwargs) -> float:
    """Stand-in for swe.solcross_ut (used by compute_bazi()'s LiChun boundary
    detection via SwissEphBackend.solcross_ut). solcross_ut returns a bare
    float with NO return-flags to check (ephemeris.py's own docstring: 'we
    cannot detect MOSEPH fallback here at runtime') — real production files
    would let this succeed; our test's dummy `.touch()`-created (zero-byte)
    files would make the REAL swisseph C call read a damaged file and raise,
    which is a test-fixture artifact wholly unrelated to the calc_ut
    MOSEPH-detection this test targets. Stubbing it keeps the test focused on
    what AC-01-4a actually claims."""
    return 2460345.5


# ---------------------------------------------------------------------------
# Endpoint request builders (T1 inventory: western/bazi/wuxing/fusion/transit/daily/health)
# ---------------------------------------------------------------------------

_WESTERN_BODY = {"date": "1990-06-15T14:30:00", "tz": "Europe/Berlin", "lon": 13.405, "lat": 52.52}
_BAZI_BODY = {"date": "1990-06-15T14:30:00", "tz": "Europe/Berlin", "lon": 13.405, "lat": 52.52}
_FUSION_BODY = {"date": "1990-06-15T14:30:00", "tz": "Europe/Berlin", "lon": 13.405, "lat": 52.52}
_WUXING_BODY = {"date": "1990-06-15T14:30:00", "tz": "Europe/Berlin", "lon": 13.405, "lat": 52.52}
_DAILY_BODY = {
    "birth": {
        "date": "1990-06-15", "time": "14:30:00", "tz": "Europe/Berlin",
        "lat": 52.52, "lon": 13.405,
    },
    "soulprint_sectors": [0.08, 0.09, 0.08, 0.09, 0.08, 0.08, 0.09, 0.08, 0.09, 0.08, 0.08, 0.08],
    "quiz_sectors": [0.08, 0.09, 0.08, 0.09, 0.08, 0.08, 0.09, 0.08, 0.09, 0.08, 0.08, 0.08],
    "target_date": "2026-04-13",
}


def _call_western(client: TestClient):
    return client.post("/calculate/western", json=_WESTERN_BODY)


def _call_bazi(client: TestClient):
    return client.post("/calculate/bazi", json=_BAZI_BODY)


def _call_fusion(client: TestClient):
    return client.post("/calculate/fusion", json=_FUSION_BODY)


def _call_wuxing(client: TestClient):
    return client.post("/calculate/wuxing", json=_WUXING_BODY)


def _call_transit(client: TestClient):
    return client.get("/transit/now")


def _call_daily(client: TestClient):
    return client.post("/experience/daily", json=_DAILY_BODY)


def _call_health(client: TestClient):
    return client.get("/health")


# ---------------------------------------------------------------------------
# AC-01-4a — flag-checkable class: files present, calc_ut return flags forced to MOSEPH
# ---------------------------------------------------------------------------

_FLAG_CHECKABLE_ENDPOINTS = {
    # name: (request_fn, patch_target — module-qualified `swe` reference actually
    #        invoked by that endpoint's call chain, per the evidence above,
    #        needs_solcross_stub — True if this endpoint's call chain reaches
    #        compute_bazi() BEFORE compute_western_chart(), which would
    #        otherwise hit the unrelated solcross_ut file-damage artifact
    #        described on _benign_solcross_ut above)
    "western": (_call_western, "bazi_engine.western.swe.calc_ut", False),
    "transit": (_call_transit, "bazi_engine.transit.swe.calc_ut", False),
    "fusion": (_call_fusion, "bazi_engine.western.swe.calc_ut", False),  # compute_western_chart() runs before compute_bazi() here
    "wuxing": (_call_wuxing, "bazi_engine.western.swe.calc_ut", False),
    "daily": (_call_daily, "bazi_engine.western.swe.calc_ut", True),  # compute_bazi() runs FIRST in _compute_astro_profile()
}


class TestFlagCheckableClassMockedReturnFlag:
    """AC-01-4a. Extends — does not replace — the existing precedent in
    tests/test_ephemeris_fallback.py::TestWesternFallbackDetection /
    TestTransitFallbackDetection, up to the full HTTP endpoint level, across every
    endpoint whose call chain reaches swe.calc_ut via western.py/transit.py."""

    @pytest.mark.parametrize("endpoint", sorted(_FLAG_CHECKABLE_ENDPOINTS))
    def test_endpoint_hard_fails_on_moseph_return_flag(self, client, tmp_path, endpoint):
        request_fn, patch_target, needs_solcross_stub = _FLAG_CHECKABLE_ENDPOINTS[endpoint]
        ephe_dir = _dummy_ephe_dir(tmp_path)  # construction-time guard PASSES
        ensure_ephemeris_files.cache_clear()
        with patch.dict(os.environ, {"SE_EPHE_PATH": str(ephe_dir)}):
            with patch(patch_target, side_effect=_moseph_calc_ut_result):
                if needs_solcross_stub:
                    with patch("bazi_engine.ephemeris.swe.solcross_ut", side_effect=_benign_solcross_ut):
                        resp = request_fn(client)
                else:
                    resp = request_fn(client)
        ensure_ephemeris_files.cache_clear()
        # NOTE (discovery finding, currently RED for "daily"): routers/experience.py's
        # _compute_astro_profile() wraps the western-chart step in a bare
        # `except Exception as exc: raise HTTPException(500, ...)`, unlike the
        # compute_bazi() step right above it which explicitly does
        # `except BaziEngineError: raise`. This flattens EphemerisUnavailableError
        # (a BaziEngineError subclass) into a generic 500 "computation_error"
        # instead of letting it reach the global handler for a 503. This is a
        # genuine pre-existing gap this test surfaces, not a test-fixture
        # artifact — Phase 2 (T4/T9) must make daily's western step re-raise
        # BaziEngineError the same way its bazi step already does.
        assert resp.status_code == 503, (
            f"{endpoint}: expected 503 EphemerisUnavailableError when swe.calc_ut "
            f"silently returns MOSEPH, got {resp.status_code}: {resp.text}"
        )
        body = resp.json()
        assert body.get("error") == "ephemeris_unavailable", (
            f"{endpoint}: 503 body must identify the ephemeris_unavailable error, got {body}"
        )


# ---------------------------------------------------------------------------
# AC-01-4b — construction-time-guard / flag-less class: empty ephemeris directory
# ---------------------------------------------------------------------------

class TestConstructionGuardClassEmptyDirectory:
    """AC-01-4b. Correct methodology for the class whose ONLY existing protection
    is SwissEphBackend.__post_init__'s ensure_ephemeris_files() check (bazi) or —
    for /health — has no protection at all today (AC-01-6 closes this)."""

    def test_bazi_fails_closed_under_missing_se1_files(self, client, tmp_path):
        empty_dir = _empty_ephe_dir(tmp_path)
        ensure_ephemeris_files.cache_clear()
        with patch.dict(os.environ, {"SE_EPHE_PATH": str(empty_dir)}):
            resp = _call_bazi(client)
        ensure_ephemeris_files.cache_clear()
        assert resp.status_code == 503, (
            f"bazi: expected 503 EphemerisUnavailableError under missing .se1 "
            f"files, got {resp.status_code}: {resp.text}"
        )
        assert resp.json().get("error") == "ephemeris_unavailable"

    def test_health_reports_unavailable_under_missing_se1_files(self, client, tmp_path):
        """AC-01-6 / VCHK-05.

        CONTRA-1 correction (plumbline-watcher, per-increment True-Line check,
        2026-07-01): this test previously forced the failure via a direct
        `swe.set_ephe_path()` call, reasoning that "`_check_ephemeris()` does
        NOT read SE_EPHE_PATH at all" — that was true of the OLD, pre-AC-01-6
        implementation (a bare `swisseph.calc_ut` call with no backend, no
        guard). `_check_ephemeris()` has SINCE been migrated (T4) to construct
        a real `SwissEphBackend()`, which DOES read `SE_EPHE_PATH` on every
        construction (`_resolve_ephe_path()` inside `ensure_ephemeris_files()`).
        The old `swe.set_ephe_path()` methodology is therefore now WRONG for
        this call site, for the same reason it was never used for the `bazi`
        test above: `SwissEphBackend.__post_init__` unconditionally re-derives
        its own path from `SE_EPHE_PATH`/default and re-points
        `swe.set_ephe_path()` to whatever that resolves to — silently
        overwriting (clobbering) any direct low-level manipulation performed
        before the request, producing a false "ok" regardless of what this
        test forced beforehand. This is independently reproducible: direct
        code read + a manual repro both confirm `SwissEphBackend()`
        construction overwrites the forced path before `calc_ut()` ever runs.

        The correct, deterministic simulation of a real "SE_EPHE_PATH points at
        an empty/missing directory" outage for this (or any) `SwissEphBackend`
        construction-time-guarded call site is the SAME pattern the sibling
        `test_bazi_fails_closed_under_missing_se1_files` test already uses:
        set `SE_EPHE_PATH` to a genuinely empty directory and clear
        `ensure_ephemeris_files`'s cache (kept as a no-op shim after CONTRA-1's
        `@lru_cache` removal — see `ephemeris.py`) so no stale resolution from
        an earlier test leaks in.
        """
        empty_dir = _empty_ephe_dir(tmp_path)
        ensure_ephemeris_files.cache_clear()
        with patch.dict(os.environ, {"SE_EPHE_PATH": str(empty_dir)}):
            resp = _call_health(client)
        ensure_ephemeris_files.cache_clear()

        # AC-01-6: /health must REPORT unavailable, not return a 5xx to a
        # monitoring probe.
        assert resp.status_code == 200, f"/health should still respond 200: {resp.text}"
        deps = resp.json().get("dependencies", {})
        assert deps.get("ephemeris", {}).get("status") == "unavailable", (
            "/health must report dependencies.ephemeris.status == 'unavailable' "
            f"when the ephemeris path is empty, got: {deps}"
        )


# ---------------------------------------------------------------------------
# AC-01-3 — houses class fails closed under missing .se1 files
# ---------------------------------------------------------------------------

_HOUSE_COMPUTING_ENDPOINTS = {
    "western": _call_western,
    "fusion": _call_fusion,
}


class TestHousesClassFailsClosed:
    """AC-01-3. swe.houses*/houses_ex*/houses_armc* return NO flag in any variant
    (PRD §3.3, verified against the installed pyswisseph via help()) — there is no
    way to return-flag-check a houses call. The only possible guard is failing
    BEFORE the houses call is ever reached, i.e. at backend construction time.
    This pins that this safety net already exists today (regression guard) AND
    is the correct target behavior post-implementation — it is legitimate for
    this specific test to already be green; the gap this increment closes is
    that `swe.houses*` itself carries no per-call detection, not that
    construction-time protection is absent."""

    @pytest.mark.parametrize("endpoint", sorted(_HOUSE_COMPUTING_ENDPOINTS))
    def test_house_computing_endpoint_fails_closed_on_missing_files(self, client, tmp_path, endpoint):
        request_fn = _HOUSE_COMPUTING_ENDPOINTS[endpoint]
        empty_dir = _empty_ephe_dir(tmp_path)
        ensure_ephemeris_files.cache_clear()
        with patch.dict(os.environ, {"SE_EPHE_PATH": str(empty_dir)}):
            resp = request_fn(client)
        ensure_ephemeris_files.cache_clear()
        assert resp.status_code == 503, (
            f"{endpoint}: house-computing endpoint must fail closed (never return "
            f"geometrically-computed-but-unattested house cusps) when .se1 files "
            f"are missing, got {resp.status_code}: {resp.text}"
        )
        assert resp.json().get("error") == "ephemeris_unavailable"


# ---------------------------------------------------------------------------
# ADR-2 precondition-gate — SwissEphBackend.houses() unit test
# ---------------------------------------------------------------------------


class TestHousesPreconditionGate:
    """Direct unit test of the NEW mechanism ADR-2 introduces
    (docs/architecture/adr-fq-att-01-houses-class.md): `SwissEphBackend.houses()`
    must refuse to run unless an attested `calc_ut()` call has already succeeded
    on the SAME backend instance -- this is distinct from (and not re-proven by)
    `TestHousesClassFailsClosed` above, which only re-exercises the pre-existing
    construction-time guard. This test constructs a backend with `.se1` files
    PRESENT (construction succeeds) and calls `houses()` WITHOUT a prior
    `calc_ut()` call on that instance -- the only way to prove the precondition-
    gate itself is doing real work, as opposed to the construction-time check
    alone."""

    def test_houses_before_any_attested_calc_ut_raises(self, tmp_path):
        ephe_dir = _dummy_ephe_dir(tmp_path)
        ensure_ephemeris_files.cache_clear()
        try:
            with patch.dict(os.environ, {"SE_EPHE_PATH": str(ephe_dir)}):
                backend = SwissEphBackend()
                assert backend.mode == "SWIEPH"
                assert not backend._attested, (
                    "sanity check: a freshly constructed backend must start unattested"
                )
                with pytest.raises(EphemerisUnavailableError):
                    backend.houses(2460000.0, 52.52, 13.405, b"P")
        finally:
            ensure_ephemeris_files.cache_clear()

    def test_houses_after_attested_calc_ut_succeeds(self, tmp_path):
        """Positive control: once calc_ut() has succeeded on this instance,
        houses() must be allowed to proceed (no behavior change for the one
        live call site, western.py, whose planet loop always runs first)."""
        ephe_dir = _dummy_ephe_dir(tmp_path)
        ensure_ephemeris_files.cache_clear()
        try:
            with patch.dict(os.environ, {"SE_EPHE_PATH": str(ephe_dir)}):
                backend = SwissEphBackend()
                mock_result = ((100.0, 0.0, 1.0, 0.0, 0.0, 0.0), swe.FLG_SWIEPH)
                with patch("bazi_engine.ephemeris.swe.calc_ut", return_value=mock_result):
                    backend.calc_ut(2460000.0, swe.SUN)
                assert backend._attested
                with patch(
                    "bazi_engine.ephemeris.swe.houses",
                    return_value=((0.0,) * 12, (0.0, 0.0, 0.0, 0.0)),
                ) as mock_houses:
                    backend.houses(2460000.0, 52.52, 13.405, b"P")
                mock_houses.assert_called_once()
        finally:
            ensure_ephemeris_files.cache_clear()
