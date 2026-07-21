"""Regression: routers/experience.py must read western['angles']['Ascendant'],
not the legacy western.get('ascmc'). Audit ref: technischer_audit_bericht_korrektur_fehlerhafter_.md

The bug: `_compute_astro_profile` looks up the ascendant via
`western.get("ascmc", [0])[0]` while `compute_western_chart()` exposes the
chart angles under the key ``angles`` (Ascendant/MC/Vertex). The lookup
silently returns ``None``, which then causes
``compute_fusion_analysis`` to mark
``contribution_ledger.chart_type_quality == "assumed_day"`` even though a
precise birth time was supplied. After the fix we expect ``"exact"``.
"""

from __future__ import annotations

import pytest

from bazi_engine.routers.experience import BirthInput, _compute_astro_profile

pytestmark = pytest.mark.swieph


def _berlin_birth() -> BirthInput:
    # Berlin midday, ephemeris-friendly latitude (Placidus works without issue).
    return BirthInput(
        date="1990-06-15",
        time="14:30:00",
        tz="Europe/Berlin",
        lat=52.52,
        lon=13.405,
    )


def test_compute_astro_profile_marks_chart_as_exact_when_birth_time_known():
    """If a precise birth time is supplied, the profile must NOT fall back
    to ``assumed_day``. This proves the angles->ascendant wiring."""
    profile = _compute_astro_profile(_berlin_birth())

    fusion = profile.get("fusion") or {}
    ledger = fusion.get("contribution_ledger") or {}
    chart_type_quality = ledger.get("chart_type_quality")

    assert chart_type_quality == "exact", (
        f"Expected 'exact' (Ascendant must be wired through from "
        f"western['angles']['Ascendant']), got {chart_type_quality!r}. "
        f"Symptom of the ascmc/angles naming mismatch in routers/experience.py."
    )


def test_compute_astro_profile_exposes_real_ascendant_sign_index():
    """asc_sign_idx must be derived from the real ascendant; the buggy
    code path collapses every chart's ascendant to sign index 0 (Aries)."""
    profile = _compute_astro_profile(_berlin_birth())
    asc_sign_idx = profile.get("asc_sign_idx")
    # Berlin, 1990-06-15 14:30 local — the ascendant is well away from 0°
    # Aries; with the bug it is forced to 0.
    assert isinstance(asc_sign_idx, int)
    assert 0 <= asc_sign_idx < 12
    assert asc_sign_idx != 0, (
        "asc_sign_idx == 0 implies ascendant fell back to None and was "
        "coerced to 0 — this is the ascmc/angles bug surfacing."
    )
