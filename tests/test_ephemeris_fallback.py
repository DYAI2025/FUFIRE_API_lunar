"""
test_ephemeris_fallback.py — Verify no silent MOSEPH fallback.

Tests that:
1. assert_no_moseph_fallback raises when MOSEPH is returned but not requested.
2. SwissEphBackend refuses to silently downgrade (no AUTO mode).
3. Missing SE1 files raise EphemerisUnavailableError at init time.
4. The runtime calc_ut check catches MOSEPH fallback even if init passed.
5. MOSEPH mode works when explicitly requested.
"""
from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import pytest
import swisseph as swe

from bazi_engine.ephemeris import (
    EPHEMERIS_FILES_REQUIRED,
    SwissEphBackend,
    assert_no_moseph_fallback,
    ensure_ephemeris_files,
)
from bazi_engine.exc import EphemerisUnavailableError


# Helper: remove EPHEMERIS_MODE from env so it doesn't override mode= param.
def _clean_env():
    """Return env dict with EPHEMERIS_MODE removed."""
    return {k: v for k, v in os.environ.items() if k != "EPHEMERIS_MODE"}


def _make_swieph_backend(tmp_path: Path) -> SwissEphBackend:
    """Create a SWIEPH backend with dummy SE1 files (no frozen-dataclass mutation)."""
    from bazi_engine.ephemeris import EPHEMERIS_FILES_REQUIRED
    for f in EPHEMERIS_FILES_REQUIRED:
        (tmp_path / f).touch()
    ensure_ephemeris_files.cache_clear()
    try:
        with patch.dict(os.environ, _clean_env(), clear=True):
            return SwissEphBackend(mode="SWIEPH", ephe_path=str(tmp_path))
    finally:
        ensure_ephemeris_files.cache_clear()


# ---------------------------------------------------------------------------
# Unit tests for assert_no_moseph_fallback
# ---------------------------------------------------------------------------


class TestAssertNoMosephFallback:
    """Direct tests for the guard function."""

    def test_swieph_requested_swieph_returned_ok(self):
        """No error when SWIEPH is requested and returned."""
        assert_no_moseph_fallback(swe.FLG_SWIEPH, swe.FLG_SWIEPH)

    def test_moseph_requested_moseph_returned_ok(self):
        """No error when MOSEPH is explicitly requested and returned."""
        assert_no_moseph_fallback(swe.FLG_MOSEPH, swe.FLG_MOSEPH)

    def test_swieph_requested_moseph_returned_raises(self):
        """Error when SWIEPH requested but MOSEPH was actually used."""
        with pytest.raises(EphemerisUnavailableError, match="silently fell back"):
            assert_no_moseph_fallback(swe.FLG_SWIEPH, swe.FLG_MOSEPH)

    def test_swieph_with_speed_moseph_returned_raises(self):
        """Error when SWIEPH|SPEED requested but MOSEPH|SPEED returned."""
        requested = swe.FLG_SWIEPH | swe.FLG_SPEED
        returned = swe.FLG_MOSEPH | swe.FLG_SPEED
        with pytest.raises(EphemerisUnavailableError):
            assert_no_moseph_fallback(requested, returned)

    def test_zero_flags_moseph_returned_raises(self):
        """Zero flags (default) should still catch MOSEPH fallback."""
        with pytest.raises(EphemerisUnavailableError):
            assert_no_moseph_fallback(0, swe.FLG_MOSEPH)


# ---------------------------------------------------------------------------
# T6 — FUFIRE_MOSEPH_ATTESTATION_ENFORCE rollout toggle (NFR-ATT-1)
# ---------------------------------------------------------------------------


class TestAttestationEnforcementToggle:
    """Default (unset, or any value other than the literal string "false") is
    hard-fail. Explicit "false" is a staging-only rollback escape hatch that
    degrades to a logged warning instead of raising -- see
    docs/runbooks/fq-att-01-rollout.md."""

    def test_default_unset_hard_fails_on_moseph(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("FUFIRE_MOSEPH_ATTESTATION_ENFORCE", None)
            with pytest.raises(EphemerisUnavailableError, match="silently fell back"):
                assert_no_moseph_fallback(swe.FLG_SWIEPH, swe.FLG_MOSEPH)

    def test_explicit_true_hard_fails_on_moseph(self):
        with patch.dict(os.environ, {"FUFIRE_MOSEPH_ATTESTATION_ENFORCE": "true"}):
            with pytest.raises(EphemerisUnavailableError, match="silently fell back"):
                assert_no_moseph_fallback(swe.FLG_SWIEPH, swe.FLG_MOSEPH)

    def test_explicit_false_degrades_without_raising(self, caplog):
        """Staging escape hatch: FUFIRE_MOSEPH_ATTESTATION_ENFORCE=false must
        NOT raise on a detected silent MOSEPH fallback -- it must log a
        warning instead. This is documented as a staging-only rollback
        mechanism, never a production-recommended state (T6/NFR-ATT-1)."""
        with patch.dict(os.environ, {"FUFIRE_MOSEPH_ATTESTATION_ENFORCE": "false"}):
            with caplog.at_level("WARNING", logger="bazi_engine.ephemeris"):
                assert_no_moseph_fallback(swe.FLG_SWIEPH, swe.FLG_MOSEPH)  # must not raise
        assert any("degrading instead of raising" in rec.message for rec in caplog.records)

    def test_explicit_false_case_insensitive(self):
        with patch.dict(os.environ, {"FUFIRE_MOSEPH_ATTESTATION_ENFORCE": "FALSE"}):
            assert_no_moseph_fallback(swe.FLG_SWIEPH, swe.FLG_MOSEPH)  # must not raise

    def test_toggle_does_not_mask_legitimate_moseph_request(self):
        """Sanity: the toggle only affects the SILENT-fallback path -- an
        explicitly-requested MOSEPH call must still succeed with no warning
        regardless of the toggle's value."""
        with patch.dict(os.environ, {"FUFIRE_MOSEPH_ATTESTATION_ENFORCE": "false"}):
            assert_no_moseph_fallback(swe.FLG_MOSEPH, swe.FLG_MOSEPH)  # no raise, no warning needed

    def test_houses_precondition_gate_respects_toggle(self, tmp_path):
        """The toggle also gates the NEW houses() precondition-gate (ADR-2) --
        a consistent rollback lever for both halves of FQ-ATT-01's hardening
        (calc-checkable class + houses class), per NFR-ATT-1's framing of
        "hardening enforcement" broadly, not just the calc_ut path."""
        for f in EPHEMERIS_FILES_REQUIRED:
            (tmp_path / f).touch()
        ensure_ephemeris_files.cache_clear()
        try:
            with patch.dict(os.environ, _clean_env(), clear=True):
                with patch.dict(os.environ, {"FUFIRE_MOSEPH_ATTESTATION_ENFORCE": "false"}):
                    backend = SwissEphBackend(ephe_path=str(tmp_path))
                    assert not backend._attested
                    # Must NOT raise -- degraded instead, per the toggle.
                    backend.houses(2460000.0, 52.52, 13.405, b"P")
        finally:
            ensure_ephemeris_files.cache_clear()


# ---------------------------------------------------------------------------
# SwissEphBackend initialization
# ---------------------------------------------------------------------------


class TestSwissEphBackendInit:
    """Backend construction with various modes."""

    def test_auto_mode_rejected(self):
        """AUTO mode is no longer supported — must be explicit."""
        with patch.dict(os.environ, _clean_env(), clear=True):
            with pytest.raises(ValueError, match="Unsupported ephemeris mode"):
                SwissEphBackend(mode="AUTO")

    def test_auto_mode_via_env_rejected(self):
        """AUTO via EPHEMERIS_MODE env is also rejected."""
        with patch.dict(os.environ, {"EPHEMERIS_MODE": "AUTO"}):
            with pytest.raises(ValueError, match="Unsupported ephemeris mode"):
                SwissEphBackend()

    def test_invalid_mode_rejected(self):
        """Random mode string raises ValueError."""
        with patch.dict(os.environ, _clean_env(), clear=True):
            with pytest.raises(ValueError, match="Unsupported ephemeris mode"):
                SwissEphBackend(mode="JPLEPH")

    def test_moseph_mode_explicit(self):
        """MOSEPH mode works when explicitly requested."""
        backend = SwissEphBackend(mode="MOSEPH")
        assert backend.mode == "MOSEPH"
        assert backend.flags == swe.FLG_MOSEPH

    def test_moseph_via_env(self):
        """MOSEPH via EPHEMERIS_MODE env works."""
        with patch.dict(os.environ, {"EPHEMERIS_MODE": "MOSEPH"}):
            backend = SwissEphBackend()
            assert backend.mode == "MOSEPH"

    def test_swieph_missing_files_raises(self, tmp_path):
        """SWIEPH mode with missing SE1 files raises at init."""
        ensure_ephemeris_files.cache_clear()
        with patch.dict(os.environ, _clean_env(), clear=True):
            with pytest.raises(EphemerisUnavailableError, match="missing"):
                SwissEphBackend(mode="SWIEPH", ephe_path=str(tmp_path))
        ensure_ephemeris_files.cache_clear()

    @pytest.mark.swieph
    def test_swieph_with_files_ok(self, tmp_path):
        """SWIEPH mode succeeds when all required files exist."""
        backend = _make_swieph_backend(tmp_path)
        assert backend.mode == "SWIEPH"
        assert backend.flags == swe.FLG_SWIEPH

    def test_default_mode_is_swieph(self):
        """Default mode should be SWIEPH, not AUTO."""
        assert SwissEphBackend.__dataclass_fields__["mode"].default == "SWIEPH"


# ---------------------------------------------------------------------------
# Runtime fallback detection
# ---------------------------------------------------------------------------


class TestRuntimeFallbackDetection:
    """Verify calc_ut checks catch runtime MOSEPH fallback."""

    def test_sun_lon_deg_ut_catches_fallback(self, tmp_path):
        """sun_lon_deg_ut raises if swe.calc_ut returns MOSEPH flags."""
        backend = _make_swieph_backend(tmp_path)
        assert backend.flags == swe.FLG_SWIEPH

        mock_result = ((100.0, 0.0, 1.0, 0.0, 0.0, 0.0), swe.FLG_MOSEPH)
        with patch("bazi_engine.ephemeris.swe.calc_ut", return_value=mock_result):
            with pytest.raises(EphemerisUnavailableError, match="silently fell back"):
                backend.sun_lon_deg_ut(2460000.0)

    def test_sun_lon_deg_ut_ok_when_swieph_returned(self, tmp_path):
        """sun_lon_deg_ut succeeds when swe.calc_ut returns SWIEPH flags."""
        backend = _make_swieph_backend(tmp_path)

        mock_result = ((100.0, 0.0, 1.0, 0.0, 0.0, 0.0), swe.FLG_SWIEPH)
        with patch("bazi_engine.ephemeris.swe.calc_ut", return_value=mock_result):
            lon = backend.sun_lon_deg_ut(2460000.0)
            assert lon == 100.0

    def test_calc_ut_wrapper_catches_fallback(self, tmp_path):
        """The calc_ut wrapper method raises on MOSEPH fallback."""
        backend = _make_swieph_backend(tmp_path)

        mock_result = ((100.0, 0.0, 1.0, 0.0, 0.0, 0.0), swe.FLG_MOSEPH)
        with patch("bazi_engine.ephemeris.swe.calc_ut", return_value=mock_result):
            with pytest.raises(EphemerisUnavailableError):
                backend.calc_ut(2460000.0, swe.SUN)

    def test_solcross_ut_uses_backend_flags(self, tmp_path):
        """solcross_ut passes self.flags to swe.solcross_ut."""
        backend = _make_swieph_backend(tmp_path)

        with patch("bazi_engine.ephemeris.swe.solcross_ut", return_value=2460000.5) as mock:
            result = backend.solcross_ut(315.0, 2460000.0)
            assert result == 2460000.5
            mock.assert_called_once_with(315.0, 2460000.0, swe.FLG_SWIEPH)

    def test_moseph_mode_no_false_alarm(self):
        """MOSEPH mode should NOT raise even though MOSEPH flags returned."""
        backend = SwissEphBackend(mode="MOSEPH")
        assert backend.flags == swe.FLG_MOSEPH

        mock_result = ((100.0, 0.0, 1.0, 0.0, 0.0, 0.0), swe.FLG_MOSEPH)
        with patch("bazi_engine.ephemeris.swe.calc_ut", return_value=mock_result):
            lon = backend.sun_lon_deg_ut(2460000.0)
            assert lon == 100.0


# ---------------------------------------------------------------------------
# Western chart fallback detection
# ---------------------------------------------------------------------------


class TestWesternFallbackDetection:
    """western.py must also catch MOSEPH fallback.

    NOTE (T4, FQ-ATT-01 migration): `compute_western_chart()` now calls
    `backend.calc_ut(...)` (a real `SwissEphBackend` method,
    `ephemeris.py:147-167`) instead of the bare module-level `swe.calc_ut`
    that `western.py` used to call directly. Mocking the entire
    `SwissEphBackend` class (as this test previously did) would replace
    `calc_ut()` itself with an unrelated `MagicMock` and never reach the real
    fallback-detection code at all -- so this test now constructs a REAL
    backend (dummy `.se1` files present so construction succeeds) and patches
    only `bazi_engine.ephemeris.swe.calc_ut`, the one physical location the
    wrapped call now resolves to (ADR:
    docs/architecture/adr-fq-att-01-mechanism.md). The assertion itself
    (`pytest.raises(EphemerisUnavailableError, match="silently fell back")`)
    is unchanged.
    """

    def test_western_catches_moseph_fallback(self, tmp_path):
        """compute_western_chart raises on MOSEPH fallback."""
        from datetime import datetime, timezone

        from bazi_engine.western import compute_western_chart

        dt = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

        for f in EPHEMERIS_FILES_REQUIRED:
            (tmp_path / f).touch()
        ensure_ephemeris_files.cache_clear()

        mock_result = ((100.0, 0.0, 1.0, 1.0, 0.0, 0.0), swe.FLG_MOSEPH)
        try:
            with patch.dict(os.environ, _clean_env(), clear=True):
                with patch("bazi_engine.ephemeris.swe.calc_ut", return_value=mock_result):
                    with pytest.raises(EphemerisUnavailableError, match="silently fell back"):
                        compute_western_chart(dt, lat=52.52, lon=13.405, ephe_path=str(tmp_path))
        finally:
            ensure_ephemeris_files.cache_clear()


# ---------------------------------------------------------------------------
# Transit fallback detection
# ---------------------------------------------------------------------------


class TestTransitFallbackDetection:
    """transit.py must also catch MOSEPH fallback.

    NOTE (T4, FQ-ATT-01 migration): same rationale as
    `TestWesternFallbackDetection` above -- `compute_transit_now()` now calls
    `backend.calc_ut(...)`, so mocking the whole `SwissEphBackend` class
    would bypass the real fallback-detection logic entirely. This test
    constructs a real backend and patches only
    `bazi_engine.ephemeris.swe.calc_ut`.
    """

    def test_transit_catches_moseph_fallback(self, tmp_path):
        """compute_transit_now raises on MOSEPH fallback."""
        from datetime import datetime, timezone

        from bazi_engine.transit import compute_transit_now

        dt = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

        for f in EPHEMERIS_FILES_REQUIRED:
            (tmp_path / f).touch()
        ensure_ephemeris_files.cache_clear()

        mock_result = ((100.0, 0.0, 1.0, 1.0, 0.0, 0.0), swe.FLG_MOSEPH)
        try:
            with patch.dict(os.environ, _clean_env(), clear=True):
                with patch("bazi_engine.ephemeris.swe.calc_ut", return_value=mock_result):
                    with pytest.raises(EphemerisUnavailableError, match="silently fell back"):
                        compute_transit_now(dt_utc=dt, ephe_path=str(tmp_path))
        finally:
            ensure_ephemeris_files.cache_clear()


# ---------------------------------------------------------------------------
# ensure_ephemeris_files
# ---------------------------------------------------------------------------


class TestEnsureEphemerisFiles:
    """File existence checks for SE1 data."""

    def test_missing_files_raises(self, tmp_path):
        """Missing SE1 files raise EphemerisUnavailableError."""
        ensure_ephemeris_files.cache_clear()
        with pytest.raises(EphemerisUnavailableError, match="missing"):
            ensure_ephemeris_files(str(tmp_path))
        ensure_ephemeris_files.cache_clear()

    def test_partial_files_raises(self, tmp_path):
        """Some but not all SE1 files raises with details of missing ones."""
        ensure_ephemeris_files.cache_clear()
        (tmp_path / "sepl_18.se1").touch()
        with pytest.raises(EphemerisUnavailableError) as exc_info:
            ensure_ephemeris_files(str(tmp_path))
        assert "semo_18.se1" in str(exc_info.value)
        ensure_ephemeris_files.cache_clear()

    def test_all_files_present_ok(self, tmp_path):
        """All SE1 files present returns path string."""
        ensure_ephemeris_files.cache_clear()
        from bazi_engine.ephemeris import EPHEMERIS_FILES_REQUIRED
        for fname in EPHEMERIS_FILES_REQUIRED:
            (tmp_path / fname).touch()
        result = ensure_ephemeris_files(str(tmp_path))
        assert result == str(tmp_path)
        ensure_ephemeris_files.cache_clear()

    def test_not_cached_across_calls_with_same_argument(self, tmp_path):
        """CONTRA-1 regression guard (fufire-premium-verification-ci).

        `ensure_ephemeris_files()` used to be `@lru_cache(maxsize=1)`'d. Since
        the common call pattern always passes the SAME argument (`None`, or a
        fixed `ephe_path`), that cache -- once a call with a given argument
        succeeded -- would return the STALE "files present" answer forever for
        that argument, even if the files were deleted afterward (a live
        SE_EPHE_PATH/filesystem change). This directly threatened `bazi.py`'s
        `solcross_ut()`/`delta_t_seconds()` call chain, whose ONLY protection
        against a silent MOSEPH fallback is this construction-time check (no
        return-flag to inspect for those calls). This test proves the function
        re-validates the filesystem live on every call, without requiring
        `cache_clear()` in between -- i.e. that it is not cached at all.
        """
        from bazi_engine.ephemeris import EPHEMERIS_FILES_REQUIRED
        for fname in EPHEMERIS_FILES_REQUIRED:
            (tmp_path / fname).touch()

        # First call succeeds (files present).
        result = ensure_ephemeris_files(str(tmp_path))
        assert result == str(tmp_path)

        # Simulate an outage: delete the files WITHOUT calling cache_clear().
        # A stale-cached implementation would still (wrongly) return success.
        for fname in EPHEMERIS_FILES_REQUIRED:
            (tmp_path / fname).unlink()

        with pytest.raises(EphemerisUnavailableError, match="missing"):
            ensure_ephemeris_files(str(tmp_path))


# ---------------------------------------------------------------------------
# jd_ut_to_datetime_utc edge cases
# ---------------------------------------------------------------------------


class TestJdUtToDatetimeUtc:
    """Edge cases for Julian Day to datetime conversion."""

    def test_microsecond_overflow_at_boundary(self):
        """Microsecond rounding near 999999.5 should not crash."""
        from datetime import datetime, timezone

        from bazi_engine.ephemeris import datetime_utc_to_jd_ut, jd_ut_to_datetime_utc
        dt = datetime(2024, 1, 1, 23, 59, 59, 999999, tzinfo=timezone.utc)
        jd = datetime_utc_to_jd_ut(dt)
        result = jd_ut_to_datetime_utc(jd)
        assert result.year == 2024
        assert result.month == 1
        assert result.day in (1, 2)

    def test_roundtrip_preserves_date(self):
        """datetime -> JD -> datetime should preserve the date (within 1 second)."""
        from datetime import datetime, timezone

        from bazi_engine.ephemeris import datetime_utc_to_jd_ut, jd_ut_to_datetime_utc
        original = datetime(2024, 6, 15, 14, 30, 45, tzinfo=timezone.utc)
        jd = datetime_utc_to_jd_ut(original)
        result = jd_ut_to_datetime_utc(jd)
        diff = abs((result - original).total_seconds())
        assert diff < 1.0, f"Roundtrip drift: {diff}s"
