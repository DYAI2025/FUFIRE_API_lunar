"""match/observability.py — REQ-013/015 latency + demand-attribution (T12).

Level 4 subpackage module (plan §4.1, docs/plans/2026-07-02-bazi-hehun.md):
pure stdlib, with NO ``routers/*`` / ``app`` / ``limiter`` / ``services/*``
imports — the "Level 4, no router imports" constraint, enforced by
``tests/test_import_hierarchy.py`` (``match.observability`` registered at
Level 4). It deliberately does NOT import ``bazi_engine.auth`` (that top-level
module sits at Level 5): the API-key metadata is consumed by DUCK TYPING
(``.tier`` / ``.key`` attributes), so this module stays free of any upward
dependency.

This is the EV-007 / AC-013d demand-attribution mechanism. Each match
request emits exactly ONE structured, PII-free observability record that:

* measures the match COMPUTATION latency as ``match.request_ms`` — distinct
  from the middleware's total request time (AC-015b);
* classifies the caller ``team`` vs ``external`` from
  ``request.state.key_info`` (the resolved API key) against the
  ``FUFIRE_TEAM_KEY_ALLOWLIST`` env allowlist — anyone NOT on the list is
  ``external`` (AC-013d). An empty/unwired allowlist therefore makes EVERY
  caller ``external``, which is the honest default: the demand falsifier
  cannot be silently satisfied by the team's own smoke traffic (chain G);
* advances per-bucket counters (the EV-007 evidence counters — the "counts"
  half of "counts + key-tier ONLY");
* carries the ``request_id`` in every line (AC-013c);
* emits the caller's key-TIER only, NEVER the key itself — mirroring
  ``KeyInfo.__repr__``'s last-4 discipline of never leaking the full key,
  taken here to its strictest form: no key material at all, tier only. No
  birth field (date/tz/lon/lat) is ever passed in or logged (AC-013b).
"""
from __future__ import annotations

import logging
import os
import threading
from typing import Any, Collection, Dict, Final, Optional

# Documented observability logger namespace (T-013-02/03/04 target it by name).
_log = logging.getLogger(__name__)

#: Caller classification buckets (AC-013d). ``team`` == allowlisted API key;
#: everything else (external key, dev-mode, missing key) == ``external``.
CALLER_TEAM: Final[str] = "team"
CALLER_EXTERNAL: Final[str] = "external"

#: Env var holding the comma-separated team API-key allowlist (AC-013d).
TEAM_ALLOWLIST_ENV: Final[str] = "FUFIRE_TEAM_KEY_ALLOWLIST"

#: Structured metric token for the match-computation latency (AC-015b).
LATENCY_METRIC: Final[str] = "match.request_ms"

# Per-process demand-attribution counters (the EV-007 evidence counters).
# Mutated under a lock: the record is emitted from request handlers that the
# ASGI server may run on multiple worker threads, so the increment must not
# race (a lost increment would under-report demand).
_counts_lock = threading.Lock()
_call_counts: Dict[str, int] = {CALLER_TEAM: 0, CALLER_EXTERNAL: 0}


def team_key_allowlist(
    allowlist: Optional[Collection[str]] = None,
) -> frozenset[str]:
    """Return the team API-key allowlist.

    Read fresh from ``FUFIRE_TEAM_KEY_ALLOWLIST`` (comma-separated) on every
    call when ``allowlist`` is not supplied — no caching, so a test or an
    operator env change takes effect immediately and never leaves a stale
    bucket wired. Blank entries are dropped. An explicit ``allowlist``
    argument (any iterable of key strings) overrides the env, for pure unit
    use.
    """
    if allowlist is not None:
        return frozenset(str(k).strip() for k in allowlist if str(k).strip())
    raw = os.environ.get(TEAM_ALLOWLIST_ENV, "")
    return frozenset(k.strip() for k in raw.split(",") if k.strip())


def classify_caller(
    key_info: Any,
    *,
    allowlist: Optional[Collection[str]] = None,
) -> str:
    """Classify a caller ``team`` vs ``external`` (AC-013d).

    ``team`` iff the caller's resolved API key (``key_info.key``) is on the
    allowlist; every other caller — a non-allowlisted key, a dev-mode key, or
    no ``key_info`` at all — is ``external`` ("outside list ⇒ external").
    Reads only the key for the membership test; never logs or returns it.
    """
    allow = team_key_allowlist(allowlist)
    key = getattr(key_info, "key", None)
    if key is not None and key in allow:
        return CALLER_TEAM
    return CALLER_EXTERNAL


def caller_counts() -> Dict[str, int]:
    """Return a snapshot copy of the per-bucket demand-attribution counters."""
    with _counts_lock:
        return dict(_call_counts)


def reset_caller_counts() -> None:
    """Reset the demand-attribution counters (test isolation helper)."""
    with _counts_lock:
        for bucket in _call_counts:
            _call_counts[bucket] = 0


def _increment(caller_class: str) -> Dict[str, int]:
    """Advance the counter for ``caller_class`` and return a fresh snapshot."""
    with _counts_lock:
        _call_counts[caller_class] = _call_counts.get(caller_class, 0) + 1
        return dict(_call_counts)


def record_match_request(
    *,
    request_id: str,
    key_info: Any,
    duration_ms: float,
    endpoint: str,
    ruleset_id: str,
    ruleset_version: str,
    warning_codes: Collection[str] = (),
    allowlist: Optional[Collection[str]] = None,
) -> Dict[str, Any]:
    """Emit the PII-free observability record for one match request.

    Classifies the caller, advances the demand-attribution counter, and logs
    exactly one structured line carrying the ``request_id`` (AC-013c), the
    ``match.request_ms`` latency (AC-015b), the endpoint, ruleset id/version,
    warning CLASSES (stable codes — never text/PII), the caller class and the
    caller's key-TIER only (AC-013d / AC-013b). The raw API key and every
    birth field are deliberately absent. Returns the emitted record so callers
    and tests can inspect it without re-parsing the log line.
    """
    caller_class = classify_caller(key_info, allowlist=allowlist)
    key_tier = str(getattr(key_info, "tier", "unknown"))
    codes = sorted({str(code) for code in warning_codes})
    counts = _increment(caller_class)

    record: Dict[str, Any] = {
        "event": "match.request",
        "request_id": request_id,
        "endpoint": endpoint,
        "caller_class": caller_class,
        "key_tier": key_tier,
        LATENCY_METRIC: round(float(duration_ms), 3),
        "ruleset_id": ruleset_id,
        "ruleset_version": ruleset_version,
        "warning_codes": codes,
        "warning_count": len(codes),
        "source_complete": len(codes) == 0,
        "counts": counts,
    }

    _log.info(
        "match.request request_id=%s endpoint=%s caller_class=%s key_tier=%s "
        "match.request_ms=%.3f ruleset_id=%s ruleset_version=%s "
        "warning_codes=%s warning_count=%d source_complete=%s "
        "team_count=%d external_count=%d",
        request_id,
        endpoint,
        caller_class,
        key_tier,
        record[LATENCY_METRIC],
        ruleset_id,
        ruleset_version,
        codes,
        record["warning_count"],
        record["source_complete"],
        counts[CALLER_TEAM],
        counts[CALLER_EXTERNAL],
    )
    return record
