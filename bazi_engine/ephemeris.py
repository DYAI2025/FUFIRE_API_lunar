from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional, Protocol, Tuple

import swisseph as swe

from .exc import EphemerisUnavailableError

logger = logging.getLogger(__name__)


def norm360(deg: float) -> float:
    x = deg % 360.0
    if x < 0:
        x += 360.0
    return x


def wrap180(deg: float) -> float:
    return (deg + 180.0) % 360.0 - 180.0


def moseph_attestation_enforced() -> bool:
    """FQ-ATT-01 / T6 rollout toggle (NFR-ATT-1).

    ``FUFIRE_MOSEPH_ATTESTATION_ENFORCE`` -- default (unset, or any value other
    than the literal string ``"false"``, case-insensitive) is HARD-FAIL, per
    this repo's "fail visibly, no masking" principle (``CLAUDE.md``) and the
    PRD's §6.3 "hard-on by default" non-negotiable constraint. Setting it
    explicitly to ``"false"`` is a **staging-only rollback escape hatch**
    (see ``docs/runbooks/fq-att-01-rollout.md``): it degrades a detected
    silent-MOSEPH-fallback / unattested-houses-call condition to a logged
    warning instead of raising. It must never be the default in production;
    rollback is a per-environment toggle flip, not a code revert (PRD §12).
    """
    return os.environ.get("FUFIRE_MOSEPH_ATTESTATION_ENFORCE", "true").strip().lower() != "false"


def assert_no_moseph_fallback(requested_flags: int, returned_flags: int) -> None:
    """Raise EphemerisUnavailableError if Swiss Ephemeris silently fell back to Moshier.

    pyswisseph does NOT raise an error when SE1 files are missing -- it silently
    downgrades to the lower-precision Moshier analytical ephemeris and sets the
    FLG_MOSEPH bit in the returned flags.  For a B2B paid API this silent
    precision downgrade is unacceptable.

    Args:
        requested_flags: The flags passed TO swe.calc_ut / swe.calc / swe.fixstar*.
        returned_flags:  The flags returned FROM swe.calc_ut / swe.calc / swe.fixstar*.

    Raises:
        EphemerisUnavailableError: when MOSEPH was used but not requested and
            enforcement is on (default). If
            ``FUFIRE_MOSEPH_ATTESTATION_ENFORCE=false`` (staging escape hatch
            only, T6/NFR-ATT-1), logs a warning and returns instead of raising.
    """
    requested_moseph = bool(requested_flags & swe.FLG_MOSEPH)
    used_moseph = bool(returned_flags & swe.FLG_MOSEPH)
    if used_moseph and not requested_moseph:
        if not moseph_attestation_enforced():
            logger.warning(
                "Swiss Ephemeris silently fell back to Moshier (lower precision) "
                "but FUFIRE_MOSEPH_ATTESTATION_ENFORCE=false; degrading instead of "
                "raising (staging rollback escape hatch only -- not a production-"
                "recommended state). requested_flags=%s returned_flags=%s",
                requested_flags, returned_flags,
            )
            return
        raise EphemerisUnavailableError(
            "Swiss Ephemeris silently fell back to Moshier (lower precision). "
            "SE1 data files are missing or unreadable. "
            "Set SE_EPHE_PATH to a directory containing the required .se1 files.",
            detail={
                "requested_flags": requested_flags,
                "returned_flags": returned_flags,
            },
        )


class EphemerisBackend(Protocol):
    def delta_t_seconds(self, jd_ut: float) -> float: ...
    def jd_tt_from_jd_ut(self, jd_ut: float) -> float: ...
    def sun_lon_deg_ut(self, jd_ut: float) -> float: ...
    def solcross_ut(self, target_lon_deg: float, jd_start_ut: float) -> Optional[float]: ...


@dataclass
class SwissEphBackend:
    flags: int = swe.FLG_SWIEPH
    ephe_path: Optional[str] = None
    mode: str = "SWIEPH"
    # ADR: docs/architecture/adr-fq-att-01-houses-class.md -- set True the
    # instant an attested (non-silently-MOSEPH) calc_ut() call succeeds on
    # THIS backend instance. houses() below refuses to run until this is
    # True, since swe.houses*() returns no retflag to check itself (§3.3).
    # Per-instance (not module-level) so concurrent requests/threads never
    # observe each other's attestation state (each call site constructs its
    # own backend -- see western.py:54, transit.py:124).
    _attested: bool = field(default=False, init=False, repr=False)

    def __post_init__(self) -> None:
        mode = self.mode.upper()
        env_mode = os.environ.get("EPHEMERIS_MODE")
        if env_mode:
            mode = env_mode.upper()

        if mode not in {"SWIEPH", "MOSEPH"}:
            raise ValueError(
                f"Unsupported ephemeris mode: {mode!r}. "
                "Use 'SWIEPH' (default, high precision) or 'MOSEPH' (analytical fallback)."
            )

        if mode == "MOSEPH":
            self.flags = swe.FLG_MOSEPH
            self.mode = "MOSEPH"
            return

        # SWIEPH: require SE1 files -- never silently degrade.
        path = ensure_ephemeris_files(self.ephe_path)
        swe.set_ephe_path(path)
        self.flags = swe.FLG_SWIEPH
        self.mode = "SWIEPH"

    def delta_t_seconds(self, jd_ut: float) -> float:
        return swe.deltat(jd_ut) * 86400.0

    def jd_tt_from_jd_ut(self, jd_ut: float) -> float:
        return jd_ut + swe.deltat(jd_ut)

    def sun_lon_deg_ut(self, jd_ut: float) -> float:
        (lon, _lat, _dist, *_), _ret = self.calc_ut(jd_ut, swe.SUN)
        return norm360(lon)

    def solcross_ut(self, target_lon_deg: float, jd_start_ut: float) -> Optional[float]:
        # swe.solcross_ut returns a plain float (no return-flags tuple),
        # so we cannot detect MOSEPH fallback here at runtime.
        # Protection is at __post_init__: SWIEPH mode refuses to start
        # without SE1 files, so solcross_ut will always use the correct backend.
        return swe.solcross_ut(target_lon_deg, jd_start_ut, self.flags)

    def calc_ut(
        self, jd_ut: float, planet_id: int, extra_flags: int = 0,
    ) -> Tuple[Tuple[float, ...], int]:
        """Thin wrapper around swe.calc_ut with fallback detection (ADR-1, FQ-ATT-01).

        Returns the (result_tuple, flags) pair, raising
        EphemerisUnavailableError if MOSEPH was used unexpectedly. This is the
        single centralized call point for the flag-checkable class -- every
        `bazi_engine/` call site that needs a body position must go through
        this method (or the free-function `calc_checked()` below) rather than
        calling `swe.calc_ut`/`swe.calc` directly (AC-01-2/AC-01-5).

        On success, marks this backend instance as attested -- `houses()`
        below refuses to run until at least one `calc_ut()` call has passed
        this check (ADR-2, precondition-gate for the flag-less houses class).
        """
        combined = self.flags | extra_flags
        result, ret = swe.calc_ut(jd_ut, planet_id, combined)
        assert_no_moseph_fallback(combined, ret)
        self._attested = True
        return result, ret

    def houses(
        self, jd_ut: float, lat: float, lon: float, sys_char: bytes,
    ) -> Tuple[Tuple[float, ...], Tuple[float, ...]]:
        """Thin wrapper around swe.houses with a precondition-gate (ADR-2, FQ-ATT-01).

        `swe.houses`/`houses_ex`/`houses_ex2`/`houses_armc`/`houses_armc_ex2`
        return NO retflag in any variant (PRD §3.3) -- there is no return-value
        signal to check the way `calc_ut()`/`fixstar_checked()` can. Instead,
        this method requires that at least one attested `calc_ut()` call has
        already succeeded on THIS SAME backend instance before it will run
        (`self._attested`). This converts what was previously *incidental*
        call-order safety (the one live call site, `western.py`, always calls
        `calc_ut()` in its planet loop before reaching the houses loop) into a
        *causally enforced* guarantee -- closing the gap named in
        `docs/architecture/adr-fq-att-01-houses-class.md`: a future call site
        could otherwise call `houses()` without ever attesting the backend.

        Construction-time file presence (SWIEPH mode) is independently
        guaranteed by `__post_init__` before any instance even exists; this
        method adds the causal, per-call guarantee on top of that.
        """
        if not self._attested:
            if not moseph_attestation_enforced():
                logger.warning(
                    "SwissEphBackend.houses() called without a prior attested "
                    "calc_ut() call on this backend instance, but "
                    "FUFIRE_MOSEPH_ATTESTATION_ENFORCE=false; degrading instead "
                    "of raising (staging rollback escape hatch only -- see "
                    "docs/runbooks/fq-att-01-rollout.md)."
                )
            else:
                raise EphemerisUnavailableError(
                    "SwissEphBackend.houses() was called before an attested "
                    "calc_ut() call succeeded on this backend instance. House "
                    "cusps cannot be computed against an unattested ephemeris "
                    "state (see docs/architecture/adr-fq-att-01-houses-class.md).",
                    detail={"mode": self.mode, "attested": self._attested},
                )
        return swe.houses(jd_ut, lat, lon, sys_char)


def calc_checked(
    jd_ut: float, planet_id: int, flags: int,
) -> Tuple[Tuple[float, ...], int]:
    """Free-function equivalent of `SwissEphBackend.calc_ut()` (ADR-1, FQ-ATT-01).

    For call sites that need a flag-checked `swe.calc_ut` call without
    already holding (or wanting to construct) a `SwissEphBackend` instance.
    Prefer `SwissEphBackend.calc_ut()` when a backend instance is already in
    scope, since it also updates that instance's attestation state for
    `houses()`'s precondition-gate; use this free function only when no
    backend instance is appropriate for the call site.
    """
    result, ret = swe.calc_ut(jd_ut, planet_id, flags)
    assert_no_moseph_fallback(flags, ret)
    return result, ret


def fixstar_checked(
    star_name: str, jd_ut: float, flags: int = swe.FLG_SWIEPH,
) -> Tuple[Tuple[float, ...], str, int]:
    """Flag-checked wrapper for `swe.fixstar_ut` (ADR-1, FQ-ATT-01).

    Preventive: no live `swe.fixstar*` call site exists in `bazi_engine/`
    today (PRD §3.1, confirmed by repo-wide grep). `swe.fixstar_ut` belongs
    in the same flag-checkable class as `swe.calc`/`swe.calc_ut` (PRD §3.3,
    verified via `help(swe.fixstar_ut)`: it accepts a `flags` argument and
    returns a `(xx, stnam, retflags)` 3-tuple, unlike `calc_ut`'s 2-tuple) --
    if/when a fixstar call site is ever added, it must call this function
    instead of `swe.fixstar*` directly, to stay inside the FQ-ATT-01
    guarantee and the AST/grep static guard's clean-tree invariant.
    """
    xx, stnam, ret = swe.fixstar_ut(star_name, jd_ut, flags)
    assert_no_moseph_fallback(flags, ret)
    return xx, stnam, ret


def datetime_utc_to_jd_ut(dt_utc: datetime) -> float:
    if dt_utc.tzinfo is None or dt_utc.utcoffset() != timedelta(0):
        raise ValueError("Expected aware UTC datetime")
    h = dt_utc.hour + dt_utc.minute / 60.0 + (dt_utc.second + dt_utc.microsecond / 1e6) / 3600.0
    return swe.julday(dt_utc.year, dt_utc.month, dt_utc.day, h)


def jd_ut_to_datetime_utc(jd_ut: float) -> datetime:
    y, m, d, h = swe.revjul(jd_ut)
    hour = int(h)
    rem = (h - hour) * 3600.0
    minute = int(rem // 60.0)
    sec = rem - minute * 60.0
    second = int(sec)
    micro = int(round((sec - second) * 1_000_000))
    # Clamp microseconds (rounding can push to 1_000_000)
    if micro >= 1_000_000:
        micro = 0
        second += 1
    # Use timedelta to handle all overflow cascades (second->minute->hour->day)
    base = datetime(y, m, d, tzinfo=timezone.utc)
    return base + timedelta(hours=hour, minutes=minute, seconds=second, microseconds=micro)


EPHEMERIS_FILES_REQUIRED = [
    "sepl_18.se1",
    "semo_18.se1",
    "seas_18.se1",
    "seplm06.se1",
]


def _resolve_ephe_path(ephe_path: Optional[str]) -> Path:
    # Default to a user-writable cache path (no implicit downloads).
    if ephe_path:
        return Path(ephe_path)
    env = os.environ.get("SE_EPHE_PATH")
    if env:
        return Path(env)
    return Path.home() / ".cache" / "bazi_engine" / "swisseph"


def ensure_ephemeris_files(ephe_path: Optional[str] = None) -> str:
    """
    Ensure ephemeris files are present locally.

    Contract-first / offline-safe behavior:
    - NEVER downloads files.
    - Creates the directory if missing.
    - Raises EphemerisUnavailableError if required files are missing.

    Deliberately NOT ``@lru_cache``d (CONTRA-1 hardening, FQ-ATT-01 /
    fufire-premium-verification-ci): this is a safety-critical construction-time
    guard invoked on every ``SwissEphBackend()`` construction (i.e. on every
    single request, across every call site), and its entire purpose is to
    detect the CURRENT, live filesystem state -- not a state cached from
    whichever call happened first in this process's lifetime. A cached
    "files present" result would silently mask a real-world outage (SE_EPHE_PATH
    changing, or the .se1 files being deleted/corrupted after the first
    successful call) for the remainder of the process's life. This matters
    most for `bazi.py`'s `solcross_ut()`/`delta_t_seconds()` call chain, whose
    ONLY protection against a silent MOSEPH fallback is this construction-time
    check (neither function returns a return-flag `assert_no_moseph_fallback`
    can inspect) -- if this check were cached-stale, that call chain would have
    no live safety net at all. The file-existence check itself
    (``Path.exists()`` x4 + an idempotent ``mkdir``) is cheap enough that
    re-running it on every call is not a meaningful performance cost.
    """
    path = _resolve_ephe_path(ephe_path)
    path.mkdir(parents=True, exist_ok=True)
    missing = [name for name in EPHEMERIS_FILES_REQUIRED if not (path / name).exists()]
    if missing:
        # SECURITY (finding #3, fufire-premium-verification-ci): resolved_path is a
        # server-local filesystem path. Log it server-side for operator debugging,
        # but do NOT put it in the exception's client-facing message/detail -- both
        # are serialized verbatim into the 503 response body by
        # app.py's ephemeris_error_handler.
        logger.error(
            "Swiss Ephemeris files missing at resolved path %s. Missing: %s",
            path, missing,
        )
        raise EphemerisUnavailableError(
            "Swiss Ephemeris files missing. Provide them via SE_EPHE_PATH or ephe_path. "
            f"Missing: {missing}.",
            detail={"missing_files": missing},
        )
    return str(path)


# Backward-compatible no-op: many tests defensively call
# ensure_ephemeris_files.cache_clear() between cases (a hygiene habit from when
# this function was @lru_cache'd). Since it no longer caches anything, clearing
# is a no-op -- kept so those call sites don't need to change.
ensure_ephemeris_files.cache_clear = lambda: None  # type: ignore[attr-defined]
