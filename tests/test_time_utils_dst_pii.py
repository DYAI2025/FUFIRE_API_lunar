"""Standalone product-wide security fix (surfaced by the bazi-hehun match feature,
CONTRA-T9-SCOPE-001; NOT part of a specific /agileteam feature increment).

`resolve_local_iso()` is on every birth-input endpoint's path (bazi, western, fusion,
chart, chronometry, webhooks, personalize). Its DST-nonexistent error messages used to
interpolate the raw `birth_local_iso` + `tz_name`, and those messages surface to API
clients as the error body — leaking a subject's exact birth instant and timezone (PII).

These tests pin that the client-facing DST error text carries no such raw values. A
spring-forward gap (Europe/Berlin 2024-03-31 02:30, the 02:00->03:00 jump) is a real
nonexistent local time.
"""
from __future__ import annotations

import pytest

from bazi_engine.time_utils import LocalTimeError, parse_local_iso, resolve_local_iso

_SENTINEL_ISO = "2024-03-31T02:30:00"
_SENTINEL_TZ = "Europe/Berlin"
# The strict round-trip normalizes the nonexistent 02:30 to 03:30; that
# derived instant is just as PII-sensitive as the raw input and must not leak.
_SENTINEL_ROUNDTRIP_ISO = "2024-03-31T03:30:00"


def test_dst_nonexistent_error_message_omits_raw_instant_and_tz():
    with pytest.raises(LocalTimeError) as excinfo:
        resolve_local_iso(_SENTINEL_ISO, _SENTINEL_TZ, nonexistent="error")
    msg = str(excinfo.value)
    assert _SENTINEL_ISO not in msg, f"raw birth instant leaked in DST error: {msg!r}"
    assert _SENTINEL_TZ not in msg, f"raw timezone leaked in DST error: {msg!r}"
    # The message must still be informative (name the cause + the remedy).
    assert "DST" in msg


def test_dst_shift_forward_still_resolves():
    # The scrub touches only the error strings, not resolution behavior.
    dt, resolution = resolve_local_iso(
        _SENTINEL_ISO, _SENTINEL_TZ, nonexistent="shift_forward"
    )
    assert resolution.status == "nonexistent_shifted"
    assert resolution.adjusted_minutes >= 1


def test_parse_local_iso_strict_dst_error_omits_raw_instant_tz_and_roundtrip():
    """parse_local_iso's strict round-trip raise is the sibling leak site of
    resolve_local_iso (reached on every route that builds BaziInput with the
    default strict_local_time=True and no pre-resolution). Its client-facing
    message must carry neither the raw instant/tz nor the normalized round-trip
    instant."""
    with pytest.raises(LocalTimeError) as excinfo:
        parse_local_iso(_SENTINEL_ISO, _SENTINEL_TZ, strict=True, fold=0)
    msg = str(excinfo.value)
    assert _SENTINEL_ISO not in msg, f"raw birth instant leaked in strict DST error: {msg!r}"
    assert _SENTINEL_TZ not in msg, f"raw timezone leaked in strict DST error: {msg!r}"
    assert _SENTINEL_ROUNDTRIP_ISO not in msg, (
        f"normalized round-trip instant leaked in strict DST error: {msg!r}"
    )
    # Still informative: names the failure mode + a remedy.
    assert "DST" in msg


def test_parse_local_iso_strict_dst_error_preserves_type_and_empty_detail():
    """The scrub changes only the message text — LocalTimeError type and its
    (empty) structured detail dict must be preserved so downstream consumers
    (routers/chart.py, routers/webhooks.py) keep mapping it to a 422."""
    with pytest.raises(LocalTimeError) as excinfo:
        parse_local_iso(_SENTINEL_ISO, _SENTINEL_TZ, strict=True, fold=0)
    assert excinfo.value.http_status == 422
    assert excinfo.value.detail == {}


# ── FIX-3: format-error / unknown-tz raises must not echo caller input ────────
# A malformed birth string is still a birth instant, and the tz name is
# location PII. Both time_utils functions raise the same message pair; pin all
# four sites. Sentinels deliberately survive the char-whitelist sanitizer, so
# these fail on any echoing message regardless of sanitization.

_MALFORMED_DATE = "31.03.2024 02:30"
_BOGUS_TZ = "Mars/Olympus"


@pytest.mark.parametrize(
    "raise_format_error",
    [
        pytest.param(
            lambda: resolve_local_iso(_MALFORMED_DATE, _SENTINEL_TZ),
            id="resolve_local_iso",
        ),
        pytest.param(
            lambda: parse_local_iso(_MALFORMED_DATE, _SENTINEL_TZ, strict=True, fold=0),
            id="parse_local_iso",
        ),
    ],
)
def test_format_error_message_omits_raw_birth_string(raise_format_error):
    with pytest.raises(LocalTimeError) as excinfo:
        raise_format_error()
    msg = str(excinfo.value)
    assert _MALFORMED_DATE not in msg, (
        f"raw (malformed) birth string echoed in format error: {msg!r}"
    )
    # Still informative: names the expected format.
    assert "ISO 8601" in msg


@pytest.mark.parametrize(
    "raise_tz_error",
    [
        pytest.param(
            lambda: resolve_local_iso("2024-02-10T14:30:00", _BOGUS_TZ),
            id="resolve_local_iso",
        ),
        pytest.param(
            lambda: parse_local_iso("2024-02-10T14:30:00", _BOGUS_TZ, strict=True, fold=0),
            id="parse_local_iso",
        ),
    ],
)
def test_unknown_tz_error_message_omits_raw_tz_name(raise_tz_error):
    with pytest.raises(LocalTimeError) as excinfo:
        raise_tz_error()
    msg = str(excinfo.value)
    assert _BOGUS_TZ not in msg, f"raw timezone name echoed in unknown-tz error: {msg!r}"
    # Still informative: names the failure class.
    assert "IANA" in msg
