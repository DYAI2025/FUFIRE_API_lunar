"""match/privacy.py — REQ-012 privacy logging helper (AC-012a / AC-012f).

Level 4 subpackage module (plan §4.1, docs/plans/2026-07-02-bazi-hehun.md):
pure stdlib, with NO ``routers/*`` / ``app`` / ``limiter`` / ``services/*``
imports — the "Level 4, no router imports" constraint of task T11, enforced
by ``tests/test_import_hierarchy.py`` (``match.privacy`` is registered at
Level 4).

This module owns the consent audit discipline for the match endpoint. It
emits exactly ONE PII-free record per consent decision that proves the
server evaluated consent — the ``request_id`` plus a one-way ``sha256:``
digest of the consent value — and NOTHING else. It never receives, formats
or logs any birth field (date/tz/lon/lat) or person payload, so the consent
side-effect log has no accidental PII path (AC-012a). The redaction is a
one-way hash: the raw consent value cannot be reconstructed from the log,
yet a specific request's decision stays auditable via its ``request_id``
(AC-012f / D5).
"""
from __future__ import annotations

import hashlib
import logging
from typing import Final

# Documented match-privacy logger namespace. Kept as the module logger so the
# consent audit record is greppable / redactable independently of the app
# loggers and so tests can target it by name (T-012-04).
_log = logging.getLogger(__name__)

#: Documented consent-hash form: ``sha256:`` + a lowercase 64-char hex digest.
CONSENT_HASH_PREFIX: Final[str] = "sha256:"


def consent_value_hash(consent_confirmed: bool) -> str:
    """Return a one-way ``sha256:<64hex>`` digest of the consent value.

    Deterministic and PII-free: the digest is taken over the canonical
    boolean token (``true`` / ``false``) only — never over any birth field.
    Returned as a documented, prefixed token so the audit log line is
    unambiguous and machine-greppable.
    """
    token = "true" if consent_confirmed else "false"
    digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
    return f"{CONSENT_HASH_PREFIX}{digest}"


def log_consent_decision(request_id: str, consent_confirmed: bool) -> str:
    """Emit the PII-free consent audit record; return the consent hash.

    The single consent side-effect log for a match request. It carries only
    the ``request_id`` and the ``sha256:`` consent hash — deliberately NO
    date/tz/lon/lat/name/person payload (AC-012a/f). Returns the hash so the
    caller can reuse it without recomputing.
    """
    consent_hash = consent_value_hash(consent_confirmed)
    _log.info(
        "match.consent request_id=%s consent_hash=%s",
        request_id,
        consent_hash,
    )
    return consent_hash
