from __future__ import annotations

import pytest
from bazi_engine.ephemeris import ensure_ephemeris_files
from bazi_engine.exc import EphemerisUnavailableError

try:
    ensure_ephemeris_files(None)
except (FileNotFoundError, EphemerisUnavailableError):
    pytest.skip("Legacy golden/vector tests require Swiss Ephemeris files (no implicit downloads). Set SE_EPHE_PATH to run.", allow_module_level=True)

import pytest

from bazi_engine.types import BaziInput
from bazi_engine.bazi import compute_bazi
from tests.golden_reference_cases import EXTENDED_GOLDEN_CASES

# --- Original 4 golden cases (Berlin + Madrid) ---

GOLDEN_CASES = [
    (
        "Berlin_2024-02-10",
        BaziInput(
            birth_local="2024-02-10T14:30:00",
            timezone="Europe/Berlin",
            longitude_deg=13.4050,
            latitude_deg=52.52,
        ),
        ("JiaChen", "BingYin", "JiaChen", "XinWei"),
    ),
    (
        "Berlin_just_before_LiChun",
        BaziInput(
            birth_local="2024-02-04T09:26:00",
            timezone="Europe/Berlin",
            longitude_deg=13.4050,
            latitude_deg=52.52,
        ),
        ("GuiMao", "YiChou", "WuXu", "DingSi"),
    ),
    (
        "Berlin_just_after_LiChun",
        BaziInput(
            birth_local="2024-02-04T09:28:00",
            timezone="Europe/Berlin",
            longitude_deg=13.4050,
            latitude_deg=52.52,
        ),
        ("JiaChen", "BingYin", "WuXu", "DingSi"),
    ),
    (
        "Madrid_zi_LMT",
        BaziInput(
            birth_local="2024-02-04T23:30:00",
            timezone="Europe/Madrid",
            longitude_deg=-3.7038,
            latitude_deg=40.4168,
            time_standard="LMT",
            day_boundary="zi",
        ),
        ("JiaChen", "BingYin", "WuXu", "GuiHai"),
    ),
]

@pytest.mark.parametrize("name, inp, exp", GOLDEN_CASES, ids=[c[0] for c in GOLDEN_CASES])
def test_golden(name, inp, exp):
    res = compute_bazi(inp)
    got = (str(res.pillars.year), str(res.pillars.month), str(res.pillars.day), str(res.pillars.hour))
    assert got == exp


# --- Extended golden cases (12+ additional: geographic, LiChun, zi-hour, historical) ---
#
# BAZI-PRECISION-V2 (FBP-00-005): cases now carry a `source_type` flag.
# Tests are split into three suites that treat failures differently:
#
#   * EXTERNAL_ORACLE        → strict assertion. Failure is a blocker:
#                              it means the engine disagrees with a
#                              domain-authoritative reference.
#   * ENGINE_BASELINE        → strict assertion at the test-runner
#                              level (so CI catches regressions), but
#                              the failure message states explicitly
#                              that the expected value is engine-derived
#                              and is not "truth". A failure here is a
#                              precision-drift signal, not a defect
#                              against an external oracle.
#   * DOMAIN_REVIEW_REQUIRED → xfail; expected values are not yet
#                              verified. Tracked in
#                              `docs/precision/deviations.md`.
#
# See `docs/audits/fufire_bazi_precision_pre_audit.md` §6
# and `spec/golden/bazi_case.schema.json`.

from tests.golden_reference_cases import split_by_source_type


def _to_param(case):
    case_id, birth_local, tz, lon, lat, expected, _source_note, _source_type = case
    return (
        case_id,
        BaziInput(
            birth_local=birth_local,
            timezone=tz,
            longitude_deg=lon,
            latitude_deg=lat,
        ),
        expected,
    )


_BY_SOURCE_TYPE = split_by_source_type(EXTENDED_GOLDEN_CASES)
_ENGINE_BASELINE_PARAMS = [_to_param(c) for c in _BY_SOURCE_TYPE["ENGINE_BASELINE"]]
_EXTERNAL_ORACLE_PARAMS = [_to_param(c) for c in _BY_SOURCE_TYPE["EXTERNAL_ORACLE"]]
_DOMAIN_REVIEW_PARAMS = [_to_param(c) for c in _BY_SOURCE_TYPE["DOMAIN_REVIEW_REQUIRED"]]


@pytest.mark.skipif(
    not _ENGINE_BASELINE_PARAMS,
    reason="No ENGINE_BASELINE golden cases present.",
)
@pytest.mark.parametrize(
    "name, inp, exp",
    _ENGINE_BASELINE_PARAMS,
    ids=[c[0] for c in _ENGINE_BASELINE_PARAMS],
)
def test_golden_extended_engine_baseline(name, inp, exp):
    """ENGINE_BASELINE: detects regression vs prior engine output.

    Failure here means the engine's *own* output changed. It does NOT
    prove the new value is wrong; it proves the value changed.
    Investigate before either fixing the engine or updating the
    baseline. See FBP-00-005 / FBP-04-006.
    """
    res = compute_bazi(inp)
    got = (str(res.pillars.year), str(res.pillars.month), str(res.pillars.day), str(res.pillars.hour))
    assert got == exp, (
        f"ENGINE_BASELINE drift on case {name!r}. Expected {exp}, got {got}. "
        "This is regression-vs-prior-engine, not regression-vs-external-oracle."
    )


@pytest.mark.skipif(
    not _EXTERNAL_ORACLE_PARAMS,
    reason=(
        "No EXTERNAL_ORACLE cases present yet. FBP-02-007 will add "
        "LiChun / Jieqi boundary cases with citations."
    ),
)
@pytest.mark.parametrize(
    "name, inp, exp",
    _EXTERNAL_ORACLE_PARAMS,
    ids=[c[0] for c in _EXTERNAL_ORACLE_PARAMS],
)
def test_golden_extended_external_oracle(name, inp, exp):
    """EXTERNAL_ORACLE: blocker. Engine must match the verified source."""
    res = compute_bazi(inp)
    got = (str(res.pillars.year), str(res.pillars.month), str(res.pillars.day), str(res.pillars.hour))
    assert got == exp, (
        f"EXTERNAL_ORACLE precision defect on case {name!r}. "
        f"Expected {exp}, got {got}. This is a blocker — engine "
        "output disagrees with the verified domain source."
    )


@pytest.mark.skipif(
    not _DOMAIN_REVIEW_PARAMS,
    reason="No DOMAIN_REVIEW_REQUIRED cases present.",
)
@pytest.mark.xfail(
    reason="DOMAIN_REVIEW_REQUIRED: expected pillars not yet verified.",
    strict=False,
)
@pytest.mark.parametrize(
    "name, inp, exp",
    _DOMAIN_REVIEW_PARAMS,
    ids=[c[0] for c in _DOMAIN_REVIEW_PARAMS],
)
def test_golden_extended_domain_review_required(name, inp, exp):
    """DOMAIN_REVIEW_REQUIRED: case included but expected values not verified."""
    res = compute_bazi(inp)
    got = (str(res.pillars.year), str(res.pillars.month), str(res.pillars.day), str(res.pillars.hour))
    assert got == exp
