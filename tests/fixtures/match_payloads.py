"""Canonical bazi-hehun fixtures — binding names per the acceptance-test
contract (docs/testing/bazi-hehun.acceptance-tests.md §0.2), shared by all
``tests/test_match_*.py``.

The sentinel values are deliberately distinctive (Chatham/Caracas, odd
minutes, 4-decimal coords) so that log-scan and echo tests (T-012-*,
T-009-04) are lexically falsifiable: if any of these strings appears in
logs or error bodies, the test fails.

Consent-location pin (contract §3 WATCH item, frozen here per plan §4.3):
``second_person_consent_confirmed`` lives inside the REQUIRED ``options``
object. Every ancestor on its path must be ``required`` in the published
OpenAPI schema so omission always yields 422 (T-012-01/02).
"""
from __future__ import annotations

from typing import Any, Dict, Tuple

SENTINEL_A: Dict[str, Any] = {
    "date": "1988-06-04T07:31:00",
    "tz": "Pacific/Chatham",
    "lon": 173.9391,
    "lat": -43.9502,
}
SENTINEL_B: Dict[str, Any] = {
    "date": "1979-11-23T22:04:00",
    "tz": "America/Caracas",
    "lon": -66.9036,
    "lat": 10.4806,
}

VALID_MATCH_REQUEST: Dict[str, Any] = {
    "mode": "birth_input",
    "person_a": SENTINEL_A,
    "person_b": SENTINEL_B,
    "options": {
        "second_person_consent_confirmed": True,
    },
}

# Golden pairs for the determinism snapshot (T7 / contract T-014-03 /
# AC-014b). Each entry pins the two birth payloads AND the per-person
# ``birth_time_known`` flag: the second pair flips person_b's flag to
# ``False`` so the deterministic ``BIRTH_TIME_UNKNOWN`` warning path
# (AC-004c) — and its downstream text block + evidence entry — is
# exercised and snapshotted. ``birth_time_known`` is kept OUT of the
# person payloads (which stay pure birth fields for the request schema)
# and carried as a sibling flag, since the engine takes it as a separate
# ``normalize_chart(birth_time_known=...)`` argument, not a chart field.
GOLDEN_MATCH_PAIRS: Tuple[Dict[str, Any], ...] = (
    {
        "id": "sentinel_ab_known",
        "person_a": SENTINEL_A,
        "person_b": SENTINEL_B,
        "birth_time_known_a": True,
        "birth_time_known_b": True,
    },
    {
        "id": "sentinel_ab_b_hour_unknown",
        "person_a": SENTINEL_A,
        "person_b": SENTINEL_B,
        "birth_time_known_a": True,
        "birth_time_known_b": False,
    },
)
