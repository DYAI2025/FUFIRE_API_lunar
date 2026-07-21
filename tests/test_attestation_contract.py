"""
test_attestation_contract.py — FQ-ATT-02 per-endpoint attestation contract.

Feature:      fufire-premium-verification-ci (WS-A increment)
PRD:          docs/prd/fufire-premium-verification-ci.prd.md (FQ-ATT-02, AC-02-2..AC-02-6)
Vision:       docs/vision/fufire-premium-verification-ci.vision.md (VCHK-02, VCHK-06)

Run via: `pytest -k attestation_contract` (PRD AC-02-5's own invocation) or this file
directly. Every test name below contains "attestation_contract" so the `-k` selector
finds them regardless of which module they end up in.

Two tiers, deliberately separated (do not merge them):

  Tier 1 — SCHEMA-LEVEL (always runs, no ephemeris files needed). Introspects the
  Pydantic response models directly (`Model.model_fields`) to check field PRESENCE per
  the OQ-1-confirmed scope: `house_system_fallback` only on house-computing endpoints
  (western/fusion/chart/experience-daily); `bazi`/`wuxing` must carry the minimal
  attestation fields (AC-02-3) but never `house_system_fallback`. `tst` is a deliberate
  exemption (2026-07-01, see `_TST_MODEL`/`TestAttestationContractTstExemption` below) —
  it keeps `provenance` but carries no `quality_flags` at all, since its computation
  (`time_context.py`) touches no Swiss Ephemeris call and attesting an ephemeris_mode
  with zero causal bearing on the response would itself be a fake-attested value. This
  tier requires no real Swiss Ephemeris data and therefore has no excuse to be skipped
  anywhere, and covers `chart`/`transit` (which had NEITHER `quality_flags` NOR
  `provenance` at all — a gap this test file surfaces beyond what PRD §3.5's table had
  already audited; `chart`/`transit` were marked "not yet audited" there).

  Tier 2 — VALUE-LEVEL (`@pytest.mark.swieph`, needs real `.se1` files; skipped
  automatically per tests/conftest.py when absent, exactly like
  tests/test_daily_chart_type_quality_surfaced.py). Fires a real HTTP request and checks
  that the attestation field VALUES are real and never the literal string `"unknown"` —
  this is what AC-02-2 and VCHK-02 actually require ("a real, successful (2xx) request
  ... not a mocked/monkeypatched environment"). Only `swe.set_ephe_path`/backend
  construction may depend on real files here; `_detect_tzdb_version()` itself is never
  mocked in this tier, by design (VCHK-02: "not a hardcoded literal that merely
  satisfies a contract-shape test").

A standalone, non-swieph-gated unit check for `_detect_tzdb_version()` is included so
that the `tzdata`-pinning gap (PRD §3.4) is provably RED in every environment, including
this repo's local dev sandbox which currently has no `tzdata` package installed at all
(verified: `importlib.metadata.version("tzdata")` raises `PackageNotFoundError` here).
"""
from __future__ import annotations

import importlib.metadata
from typing import Any, Dict, Optional

import pytest
from fastapi.testclient import TestClient

from bazi_engine.app import app
from bazi_engine.exc import EphemerisUnavailableError
from bazi_engine.provenance import _detect_tzdb_version

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _no_api_key_enforcement(monkeypatch):
    monkeypatch.setenv("FUFIRE_REQUIRE_API_KEYS", "false")
    monkeypatch.delenv("FUFIRE_API_KEYS", raising=False)


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


# ---------------------------------------------------------------------------
# Tier 1 — schema-level field presence (no ephemeris files required)
# ---------------------------------------------------------------------------

# OQ-1 (CONFIRMED, user, 2026-07-01; PRD §5.2, §9): house_system_fallback is scoped to
# house-computing endpoints only.
_HOUSE_COMPUTING_RESPONSE_MODELS = {
    "western": ("bazi_engine.routers.western", "WesternResponse"),
    "fusion": ("bazi_engine.routers.fusion", "FusionResponse"),
    "chart": ("bazi_engine.routers.chart", "ChartResponse"),
    "daily": ("bazi_engine.routers.experience", "DailyResponse"),
}

# PRD §3.5 / AC-02-3: these currently have NO quality_flags field at all — additive
# field is required, but must NOT include house_system_fallback (OQ-1).
_NON_HOUSE_RESPONSE_MODELS = {
    "bazi": ("bazi_engine.routers.bazi", "BaziResponse"),
    "wuxing": ("bazi_engine.routers.fusion", "WxResponse"),
}

# Refined 2026-07-01 (user decision, post-review): `tst` is intentionally exempt from
# the ephemeris_mode requirement above, unlike bazi/wuxing. `time_context.py` (which
# /calculate/tst delegates to) touches no Swiss Ephemeris call at all -- bazi/wuxing
# already construct a real SwissEphBackend as part of their own computation, so reading
# its attested mode is a redundant re-check; tst had no such guarantee to piggyback on,
# so populating ephemeris_mode there required a brand-new throwaway backend
# construction purely for attestation cosmetics -- a new failure mode, not a redundant
# one, and attesting a mode with zero causal bearing on the response is itself a form
# of the "fake-attested value" risk FQ-ATT-02 exists to close. See
# bazi_engine/routers/shared.py::current_ephemeris_mode()'s docstring.
_TST_MODEL = ("bazi_engine.routers.fusion", "TSTResponse")

# Discovery finding beyond PRD §3.5's own table (which marked these "not yet audited"):
# `transit` carries NEITHER quality_flags NOR provenance at all (verified via direct
# `TransitNowResponse.model_fields` introspection). Treated as non-house (transit
# computes no house cusps) for the purposes of this contract.
_UNAUDITED_NON_HOUSE_RESPONSE_MODELS = {
    "transit": ("bazi_engine.routers.transit", "TransitNowResponse"),
}


def _import_model(module_path: str, name: str):
    import importlib
    return getattr(importlib.import_module(module_path), name)


class TestAttestationContractSchemaHouseComputing:
    """AC-02-2/AC-02-6, house-computing subset: quality_flags.house_system_fallback
    must be a declared field on these response models."""

    @pytest.mark.parametrize("endpoint", sorted(_HOUSE_COMPUTING_RESPONSE_MODELS))
    def test_attestation_contract_house_system_fallback_present(self, endpoint):
        module_path, model_name = _HOUSE_COMPUTING_RESPONSE_MODELS[endpoint]
        model = _import_model(module_path, model_name)
        fields = set(model.model_fields)
        assert "quality_flags" in fields, (
            f"{endpoint}: {model_name} must declare a quality_flags field "
            f"(house-computing endpoint per OQ-1), has: {sorted(fields)}"
        )
        qf_model = model.model_fields["quality_flags"].annotation
        qf_field_names = set(getattr(qf_model, "model_fields", {}))
        assert "house_system_fallback" in qf_field_names, (
            f"{endpoint}: quality_flags model must declare house_system_fallback "
            f"for a house-computing endpoint, has: {sorted(qf_field_names)}"
        )


class TestAttestationContractSchemaNonHouse:
    """AC-02-3, non-house subset (bazi/wuxing/tst): must gain minimal attestation
    fields (ephemeris_mode at least) but must NEVER carry house_system_fallback
    (OQ-1 confirmed scope). Expected RED today: none of the three has a
    quality_flags field at all yet (verified by direct model introspection)."""

    @pytest.mark.parametrize("endpoint", sorted(_NON_HOUSE_RESPONSE_MODELS) + sorted(_UNAUDITED_NON_HOUSE_RESPONSE_MODELS))
    def test_attestation_contract_ephemeris_mode_present_no_house_fallback(self, endpoint):
        specs = {**_NON_HOUSE_RESPONSE_MODELS, **_UNAUDITED_NON_HOUSE_RESPONSE_MODELS}
        module_path, model_name = specs[endpoint]
        model = _import_model(module_path, model_name)
        fields = set(model.model_fields)

        # Minimal bar (AC-02-3): ephemeris_mode must be reachable, either as its
        # own top-level field or nested under quality_flags.
        ephemeris_mode_reachable = "ephemeris_mode" in fields
        if not ephemeris_mode_reachable and "quality_flags" in fields:
            qf_model = model.model_fields["quality_flags"].annotation
            ephemeris_mode_reachable = "ephemeris_mode" in set(getattr(qf_model, "model_fields", {}))
        assert ephemeris_mode_reachable, (
            f"{endpoint}: {model_name} must expose ephemeris_mode (top-level or via "
            f"quality_flags) per AC-02-3 — currently has fields: {sorted(fields)}"
        )

        # OQ-1: never house_system_fallback on a non-house endpoint, even after
        # the field is added.
        house_fallback_present = "house_system_fallback" in fields
        if not house_fallback_present and "quality_flags" in fields:
            qf_model = model.model_fields["quality_flags"].annotation
            house_fallback_present = "house_system_fallback" in set(getattr(qf_model, "model_fields", {}))
        assert not house_fallback_present, (
            f"{endpoint}: house_system_fallback must be ABSENT (OQ-1 confirmed scope: "
            f"non-house endpoints only carry ephemeris_mode/ephemeris_id/tzdb_version_id)"
        )

    @pytest.mark.parametrize("endpoint", sorted(_NON_HOUSE_RESPONSE_MODELS) + sorted(_UNAUDITED_NON_HOUSE_RESPONSE_MODELS))
    def test_attestation_contract_provenance_ephemeris_and_tzdb_id_present(self, endpoint):
        specs = {**_NON_HOUSE_RESPONSE_MODELS, **_UNAUDITED_NON_HOUSE_RESPONSE_MODELS}
        module_path, model_name = specs[endpoint]
        model = _import_model(module_path, model_name)
        fields = set(model.model_fields)

        ephemeris_id_reachable = "ephemeris_id" in fields
        tzdb_reachable = "tzdb_version_id" in fields
        if "provenance" in fields:
            prov_model = model.model_fields["provenance"].annotation
            prov_field_names = set(getattr(prov_model, "model_fields", {}))
            ephemeris_id_reachable = ephemeris_id_reachable or "ephemeris_id" in prov_field_names
            tzdb_reachable = tzdb_reachable or "tzdb_version_id" in prov_field_names

        assert ephemeris_id_reachable, (
            f"{endpoint}: {model_name} must expose provenance.ephemeris_id "
            f"(AC-02-3), fields: {sorted(fields)}"
        )
        assert tzdb_reachable, (
            f"{endpoint}: {model_name} must expose provenance.tzdb_version_id "
            f"(AC-02-3), fields: {sorted(fields)}"
        )


class TestAttestationContractTstExemption:
    """tst is a positive, deliberate exemption (2026-07-01 user decision), not a
    silent gap — this proves both halves: no quality_flags at all, but provenance
    (ephemeris_id/tzdb_version_id) still present, since build_provenance() itself
    touches no Swiss Ephemeris call and stays cheap/safe to keep."""

    def test_tst_response_has_no_quality_flags_field(self):
        model = _import_model(*_TST_MODEL)
        fields = set(model.model_fields)
        assert "quality_flags" not in fields, (
            f"TSTResponse must NOT declare quality_flags (2026-07-01 exemption) — "
            f"if this now fails, tst grew a quality_flags field again and the "
            f"exemption/rationale above needs re-review, not a silent test update. "
            f"fields: {sorted(fields)}"
        )

    def test_tst_response_still_has_provenance_ephemeris_and_tzdb_id(self):
        model = _import_model(*_TST_MODEL)
        fields = set(model.model_fields)
        assert "provenance" in fields, f"TSTResponse must keep provenance, has: {sorted(fields)}"
        prov_field_names = set(getattr(model.model_fields["provenance"].annotation, "model_fields", {}))
        assert "ephemeris_id" in prov_field_names and "tzdb_version_id" in prov_field_names, (
            f"TSTResponse.provenance must still expose ephemeris_id/tzdb_version_id "
            f"(build_provenance() touches no Swiss Ephemeris call, so this stays safe "
            f"and cheap to keep even though quality_flags.ephemeris_mode was removed), "
            f"provenance fields: {sorted(prov_field_names)}"
        )


# ---------------------------------------------------------------------------
# Tier 2 — value-level, real successful (2xx) request, real ephemeris files
# ---------------------------------------------------------------------------

_ENDPOINT_2XX_REQUESTS = {
    "western": ("POST", "/calculate/western", {
        "date": "1990-06-15T14:30:00", "tz": "Europe/Berlin", "lon": 13.405, "lat": 52.52,
    }, True),
    "fusion": ("POST", "/calculate/fusion", {
        "date": "1990-06-15T14:30:00", "tz": "Europe/Berlin", "lon": 13.405, "lat": 52.52,
    }, True),
    "bazi": ("POST", "/calculate/bazi", {
        "date": "1990-06-15T14:30:00", "tz": "Europe/Berlin", "lon": 13.405, "lat": 52.52,
    }, False),
    "wuxing": ("POST", "/calculate/wuxing", {
        "date": "1990-06-15T14:30:00", "tz": "Europe/Berlin", "lon": 13.405, "lat": 52.52,
    }, False),
    "tst": ("POST", "/calculate/tst", {
        "date": "1990-06-15T14:30:00", "tz": "Europe/Berlin", "lon": 13.405,
    }, False),
    "daily": ("POST", "/experience/daily", {
        "birth": {"date": "1990-06-15", "time": "14:30:00", "tz": "Europe/Berlin", "lat": 52.52, "lon": 13.405},
        "soulprint_sectors": [0.08, 0.09, 0.08, 0.09, 0.08, 0.08, 0.09, 0.08, 0.09, 0.08, 0.08, 0.08],
        "quiz_sectors": [0.08, 0.09, 0.08, 0.09, 0.08, 0.08, 0.09, 0.08, 0.09, 0.08, 0.08, 0.08],
        "target_date": "2026-04-13",
    }, True),
    # T9 scope addition (orchestrator, post-Phase-1 spot-check): `chart` and
    # `transit/now` were confirmed gaps beyond PRD §3.5's initial audit
    # table (both previously had ZERO quality_flags/provenance fields at
    # all) -- added to this contract test's Tier 2 alongside the Tier 1
    # schema checks above, which already covered them.
    "chart": ("POST", "/chart", {
        "local_datetime": "1990-06-15T14:30:00", "tz_id": "Europe/Berlin",
        "geo_lon_deg": 13.405, "geo_lat_deg": 52.52,
    }, True),
    "transit": ("GET", "/transit/now", {}, False),
}


def _dig(payload: Dict[str, Any], *path: str) -> Optional[Any]:
    cur: Any = payload
    for key in path:
        if not isinstance(cur, dict) or key not in cur:
            return None
        cur = cur[key]
    return cur


@pytest.mark.swieph
class TestAttestationContractValueLevel:
    """AC-02-2 / VCHK-02. Requires real .se1 ephemeris files (skipped otherwise,
    see tests/conftest.py). Never mocks _detect_tzdb_version() or the ephemeris
    backend — this is the real, wired path, not a contract-shape stub."""

    @pytest.mark.parametrize("endpoint", sorted(_ENDPOINT_2XX_REQUESTS))
    def test_attestation_contract_2xx_never_unknown(self, client, endpoint):
        method, path, body, house_computing = _ENDPOINT_2XX_REQUESTS[endpoint]
        resp = client.post(path, json=body) if method == "POST" else client.get(path)
        assert resp.status_code == 200, f"{endpoint}: expected 2xx, got {resp.status_code}: {resp.text}"
        payload = resp.json()

        ephemeris_mode = _dig(payload, "ephemeris_mode") or _dig(payload, "quality_flags", "ephemeris_mode")
        ephemeris_id = _dig(payload, "ephemeris_id") or _dig(payload, "provenance", "ephemeris_id")
        tzdb_version_id = _dig(payload, "tzdb_version_id") or _dig(payload, "provenance", "tzdb_version_id")

        if endpoint == "tst":
            # 2026-07-01 exemption (see _TST_MODEL comment above): tst deliberately
            # omits quality_flags/ephemeris_mode entirely, so this is the one endpoint
            # where "not present" is the correct, tested outcome, not a gap.
            assert ephemeris_mode is None, (
                f"tst: quality_flags/ephemeris_mode was re-added ({ephemeris_mode!r}) — "
                f"this endpoint is deliberately exempt (2026-07-01), review before "
                f"updating this assertion"
            )
        else:
            assert ephemeris_mode == "SWIEPH", f"{endpoint}: quality_flags.ephemeris_mode must be 'SWIEPH', got {ephemeris_mode!r}"
        assert ephemeris_id not in (None, "", "unknown"), f"{endpoint}: provenance.ephemeris_id must be real, got {ephemeris_id!r}"
        # VCHK-02 (tightened per plumbline-watcher mutation-test finding,
        # fufire-premium-verification-ci): a mere `!= "unknown"` check only
        # rejects the ONE literal placeholder string — it was empirically
        # shown to still pass when `_detect_tzdb_version()` was mutated to
        # return an arbitrary wrong-but-plausible fabricated version string
        # (e.g. "9999.99-FAKE-MUTATION-PROBE"). Assert equality against the
        # ACTUALLY-pinned `tzdata` package version instead, closing that gap.
        expected_tzdb_version_id = importlib.metadata.version("tzdata")
        assert tzdb_version_id == expected_tzdb_version_id, (
            f"{endpoint}: provenance.tzdb_version_id must equal the actually-pinned "
            f"tzdata package version ({expected_tzdb_version_id!r}), got "
            f"{tzdb_version_id!r} — a `!= 'unknown'` check alone does not rule out an "
            f"arbitrary fake-but-plausible value (PRD §3.4, VCHK-02)."
        )

        if house_computing:
            house_system_fallback = _dig(payload, "house_system_fallback") or _dig(payload, "quality_flags", "house_system_fallback")
            assert isinstance(house_system_fallback, bool), (
                f"{endpoint}: house_system_fallback must be a real bool on a "
                f"house-computing endpoint, got {house_system_fallback!r}"
            )


# ---------------------------------------------------------------------------
# tzdb_version_id root-cause unit check (PRD §3.4) — no ephemeris files needed
# ---------------------------------------------------------------------------


class TestAttestationContractTzdbPinning:
    def test_attestation_contract_detect_tzdb_version_never_unknown(self):
        """AC-02-1. Runs everywhere (no .se1 files needed — this is a pure
        importlib/package-metadata probe). `tzdata` is now a pinned, declared
        dependency (T7, pyproject.toml `tzdata>=2026.2`).

        VCHK-02 (tightened per plumbline-watcher mutation-test finding): assert
        equality against the actually-pinned `importlib.metadata.version("tzdata")`
        value, not merely inequality with the literal placeholder "unknown" — the
        weaker check does not rule out an arbitrary wrong-but-plausible value.
        """
        expected = importlib.metadata.version("tzdata")
        assert _detect_tzdb_version() == expected, (
            f"_detect_tzdb_version() must return the actually-pinned tzdata package "
            f"version ({expected!r}); a fabricated-but-plausible value would pass a "
            f"mere '!= \"unknown\"' check (PRD §3.4, AC-02-1, VCHK-02)."
        )

    def test_attestation_contract_detect_tzdb_version_raises_when_undetectable(self, monkeypatch):
        """T8 / OQ-7 (decided): if BOTH detection probes fail even with tzdata
        pinned (e.g. corrupted/uninstalled at runtime), _detect_tzdb_version()
        must RAISE EphemerisUnavailableError instead of silently returning the
        literal placeholder string "unknown" -- a deliberate failure-mode
        semantics change (previously: degraded-200 with a bad string; now:
        503 on an edge case that should not occur once tzdata is correctly
        pinned and locked). Forces both the importlib.metadata probe and the
        importlib.resources fallback to fail, exactly the "still fails"
        scenario OQ-7 describes."""
        import importlib.metadata

        def _raise_not_found(name):
            raise importlib.metadata.PackageNotFoundError(name)

        monkeypatch.setattr(importlib.metadata, "version", _raise_not_found)

        import importlib.resources

        def _raise_module_not_found(name):
            raise ModuleNotFoundError(name)

        monkeypatch.setattr(importlib.resources, "files", _raise_module_not_found)

        with pytest.raises(EphemerisUnavailableError):
            _detect_tzdb_version()


# ---------------------------------------------------------------------------
# tst "no Swiss-Ephemeris work" invariant (F3, dev-review loop) — no ephemeris
# files needed
# ---------------------------------------------------------------------------


class TestAttestationContractTstNoSwissEph:
    """The /calculate/tst attestation exemption (TSTResponse deliberately carries
    NO quality_flags/ephemeris_mode, 2026-07-01) rests entirely on the invariant
    that the tst path performs NO Swiss-Ephemeris work — attesting an
    ephemeris_mode with zero causal bearing on the response is itself the
    "fake-attested value" risk FQ-ATT-02 exists to close. That invariant was
    documented (see the _TST_MODEL comment above and
    routers/fusion.py::calculate_tst_endpoint) but never enforced. This spies on
    SwissEphBackend construction during a real /v1/calculate/tst request and
    asserts it stays zero, so a future refactor that reintroduces a backend on
    this path fails loudly here instead of silently invalidating the exemption's
    rationale.

    Needs no real .se1 files: the tst path is pure civil-time / equation-of-time
    math, so it must succeed (200) AND build zero backends everywhere.
    """

    _TST_REQUEST = {"date": "1990-06-15T14:30:00", "tz": "Europe/Berlin", "lon": 13.405}
    _BAZI_REQUEST = {
        "date": "1990-06-15T14:30:00", "tz": "Europe/Berlin", "lon": 13.405, "lat": 52.52,
    }

    @staticmethod
    def _install_backend_spy(monkeypatch) -> Dict[str, int]:
        """Count SwissEphBackend constructions without changing behavior — the
        wrapper still delegates to the real __init__ (so a route that legitimately
        needs a backend keeps working, and errors still surface normally)."""
        from bazi_engine import ephemeris

        counter = {"n": 0}
        orig_init = ephemeris.SwissEphBackend.__init__

        def counting_init(self, *args, **kwargs):
            counter["n"] += 1
            return orig_init(self, *args, **kwargs)

        monkeypatch.setattr(ephemeris.SwissEphBackend, "__init__", counting_init)
        return counter

    @staticmethod
    def _force_dev_mode():
        # /v1/* is behind require_api_key; the autouse _no_api_key_enforcement
        # fixture delenvs FUFIRE_API_KEYS, but _load_keys is lru_cached, so clear
        # it to guarantee the empty-key dev-mode bypass regardless of test order.
        from bazi_engine.auth import _load_keys

        _load_keys.cache_clear()

    def test_attestation_contract_tst_constructs_no_swisseph_backend(self, client, monkeypatch):
        self._force_dev_mode()
        counter = self._install_backend_spy(monkeypatch)
        resp = client.post("/v1/calculate/tst", json=self._TST_REQUEST)
        assert resp.status_code == 200, (
            f"tst: expected 200, got {resp.status_code}: {resp.text}"
        )
        assert counter["n"] == 0, (
            f"/calculate/tst constructed a SwissEphBackend ({counter['n']}x). The "
            f"tst attestation exemption requires this path to touch NO Swiss-"
            f"Ephemeris work; if this now fails, tst grew an ephemeris dependency "
            f"and the quality_flags/ephemeris_mode exemption (2026-07-01) must be "
            f"re-reviewed rather than this assertion loosened."
        )

    def test_attestation_contract_tst_spy_bites_on_bazi_backend(self, client, monkeypatch):
        """Non-tautology proof: the SAME spy must count >0 on /calculate/bazi,
        which constructs a real SwissEphBackend inside compute_bazi(). Without
        this, a broken/no-op spy would make the count==0 assertion above pass for
        the wrong reason. (The construction happens before any ephemeris-file
        check, so this holds even where .se1 files are absent — hence no status
        assertion.)"""
        self._force_dev_mode()
        counter = self._install_backend_spy(monkeypatch)
        resp = client.post("/v1/calculate/bazi", json=self._BAZI_REQUEST)
        assert counter["n"] > 0, (
            f"construction spy observed no SwissEphBackend build on "
            f"/calculate/bazi (status={resp.status_code}) — the spy is not wired "
            f"to the real constructor, so the tst count==0 guard proves nothing."
        )
