"""
test_geocode_endpoint.py — Acceptance spec for REQ-001 POST /geocode (+ /v1/geocode).

These are BLACK-BOX acceptance tests for an endpoint that does NOT exist yet, so
the whole module is RED until the coder lands routers/geocode.py and mounts it in
app.py. Failure now is expected and correct.

Contract (docs/plans/2026-06-18-req-001-geocode-endpoint.md):
- POST /geocode and POST /v1/geocode, protected by require_api_key.
- Body {"place": str, "language"?: str}.
- 200 on unambiguous match → {lat, lon, resolved_name, confidence, timezone, country_code}.
- OQ-001 fail-loud: confidence < 0.6 → HTTP 422
      {"error":"ambiguous_place","candidates":[...],"confidence":float}.
- 404 when no place found → {"error":"place_not_found"}.
- 401 when no/invalid API key (require_api_key returns 401 — see bazi_engine/auth.py).

Confidence v1 heuristic (deterministic, drives the mock payloads):
    confidence = pop_top / (pop_top + pop_second) over ranked candidates;
    1 candidate → 1.0; missing population → 0.5.

Determinism: Open-Meteo HTTP is mocked the SAME way as tests/test_services_geocoding.py
— patching ``bazi_engine.services.geocoding.httpx.AsyncClient`` with a fake async
context manager. No network in the default suite.

The single live-boundary smoke (EV-001) hits the REAL Open-Meteo API and is SKIPPED
by default; it runs only when ``RUN_LIVE=1`` is set in the environment (the repo had
no pre-existing network/live marker, so this env-gate is introduced here and
documented inline).
"""
from __future__ import annotations

import os
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from fastapi.testclient import TestClient

from bazi_engine.app import app
from bazi_engine.services.geocoding import clear_geocode_cache

client = TestClient(app)

GEOCODE_MODULE = "bazi_engine.services.geocoding.httpx.AsyncClient"


# ── Cache isolation (I1) ───────────────────────────────────────────────────────
# The geocode service now keeps an in-memory TTL cache (avoid hammering
# Open-Meteo). Without resetting it between tests, a "Berlin" cached by an early
# happy-path test would let later tests (e.g. the 503 raising-mock test) hit the
# cache and never exercise their mock → false greens. Reset before EVERY test.

@pytest.fixture(autouse=True)
def _reset_geocode_cache():
    clear_geocode_cache()
    yield
    clear_geocode_cache()


# ── Mock helper (mirrors tests/test_services_geocoding.py::_mock_httpx_client) ──

def _mock_httpx_client(results: list) -> MagicMock:
    """Build a mock httpx.AsyncClient context manager returning given results.

    Identical seam to the existing service unit tests so the mock covers whatever
    geocode_candidates/geocode_place the coder builds inside that module.
    """
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"results": results}
    mock_resp.raise_for_status = MagicMock()

    mock_client = MagicMock()
    mock_client.get = AsyncMock(return_value=mock_resp)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    return mock_client


def _mock_httpx_client_raising(exc: Exception) -> MagicMock:
    """Build a mock httpx.AsyncClient whose ``resp.raise_for_status()`` raises ``exc``.

    Same seam as ``_mock_httpx_client`` (patching
    ``bazi_engine.services.geocoding.httpx.AsyncClient``), but simulates an
    upstream failure (timeout / 5xx) surfacing at ``resp.raise_for_status()``.
    """
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"results": []}
    mock_resp.raise_for_status = MagicMock(side_effect=exc)

    mock_client = MagicMock()
    mock_client.get = AsyncMock(return_value=mock_resp)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    return mock_client


# ── Deterministic Open-Meteo candidate payloads ───────────────────────────────
# Real Open-Meteo geocoding results carry a "population" field (used by the v1
# confidence heuristic). Field names match the live API (latitude/longitude/
# timezone/country_code/name/population).

PARIS_FR = {
    "name": "Paris",
    "latitude": 48.8534,
    "longitude": 2.3488,
    "timezone": "Europe/Paris",
    "country_code": "FR",
    "population": 2138551,
}
PARIS_TX = {
    "name": "Paris",
    "latitude": 33.6609,
    "longitude": -95.5555,
    "timezone": "America/Chicago",
    "country_code": "US",
    "population": 24839,
}

# Dominant top (FR pop >> TX pop): confidence = 2138551/(2138551+24839) ≈ 0.989 → 200.
DOMINANT_PARIS = [PARIS_FR, PARIS_TX]

# Several comparable same-name candidates → low confidence (<0.6) → 422.
# pop_top/(pop_top+pop_second) = 16000/(16000+15800) ≈ 0.503 < 0.6 → ambiguous.
SPRINGFIELD_A = {
    "name": "Springfield",
    "latitude": 39.7817,
    "longitude": -89.6501,
    "timezone": "America/Chicago",
    "country_code": "US",
    "population": 16000,
}
SPRINGFIELD_B = {
    "name": "Springfield",
    "latitude": 37.2153,
    "longitude": -93.2982,
    "timezone": "America/Chicago",
    "country_code": "US",
    "population": 15800,
}
SPRINGFIELD_C = {
    "name": "Springfield",
    "latitude": 42.1015,
    "longitude": -72.5898,
    "timezone": "America/New_York",
    "country_code": "US",
    "population": 15300,
}
AMBIGUOUS_SPRINGFIELD = [SPRINGFIELD_A, SPRINGFIELD_B, SPRINGFIELD_C]

# Single unambiguous candidate → confidence 1.0 → 200.
BERLIN_ONLY = [
    {
        "name": "Berlin",
        "latitude": 52.52,
        "longitude": 13.405,
        "timezone": "Europe/Berlin",
        "country_code": "DE",
        "population": 3426354,
    }
]


def _post(body: dict, path: str = "/geocode", headers: dict | None = None):
    return client.post(path, json=body, headers=headers or {})


# ── 200: unambiguous match → full shape ────────────────────────────────────────

def test_unambiguous_match_returns_200_full_shape():
    """Dominant top candidate → 200 with the full contract body and typed fields."""
    with patch(GEOCODE_MODULE, return_value=_mock_httpx_client(DOMINANT_PARIS)):
        r = _post({"place": "Paris"})
    assert r.status_code == 200, r.text
    data = r.json()
    for key in ("lat", "lon", "resolved_name", "confidence", "timezone", "country_code"):
        assert key in data, f"missing contract key: {key} in {data}"
    assert isinstance(data["lat"], float)
    assert isinstance(data["lon"], float)
    assert isinstance(data["resolved_name"], str)
    assert isinstance(data["confidence"], float)
    assert isinstance(data["timezone"], str)
    assert isinstance(data["country_code"], str)


def test_unambiguous_match_resolves_dominant_candidate():
    """Paris FR (huge pop) must win over Paris TX (small pop); confidence high."""
    with patch(GEOCODE_MODULE, return_value=_mock_httpx_client(DOMINANT_PARIS)):
        r = _post({"place": "Paris"})
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["country_code"] == "FR"
    assert data["lat"] == pytest.approx(48.8534)
    assert data["lon"] == pytest.approx(2.3488)
    assert data["timezone"] == "Europe/Paris"
    assert data["confidence"] >= 0.6, "dominant top must be above the ambiguity threshold"


def test_single_candidate_confidence_is_one():
    """Exactly one candidate → confidence 1.0 → 200."""
    with patch(GEOCODE_MODULE, return_value=_mock_httpx_client(BERLIN_ONLY)):
        r = _post({"place": "Berlin"})
    assert r.status_code == 200, r.text
    assert r.json()["confidence"] == pytest.approx(1.0)


def test_v1_route_also_registered():
    """POST /v1/geocode must resolve to the same handler (mounted unprefixed + /v1)."""
    with patch(GEOCODE_MODULE, return_value=_mock_httpx_client(BERLIN_ONLY)):
        r = _post({"place": "Berlin"}, path="/v1/geocode")
    assert r.status_code == 200, r.text
    assert r.json()["country_code"] == "DE"


# ── 422: OQ-001 fail-loud on ambiguity (confidence < 0.6) ──────────────────────

def test_ambiguous_place_returns_422_with_candidates():
    """Comparable same-name candidates → confidence < 0.6 → 422 ambiguous_place.

    I2: candidates must be projected to the TYPED GeocodeCandidate subset
    {name, lat, lon, country_code, population} — NOT the raw Open-Meteo dict
    (which carries latitude/longitude/timezone/elevation etc.). This stops raw
    upstream shape drift from leaking into our 422 contract.
    """
    with patch(GEOCODE_MODULE, return_value=_mock_httpx_client(AMBIGUOUS_SPRINGFIELD)):
        r = _post({"place": "Springfield"})
    assert r.status_code == 422, r.text
    data = r.json()
    assert data["error"] == "ambiguous_place"
    assert isinstance(data["candidates"], list)
    assert len(data["candidates"]) >= 2, "fail-loud must hand back candidates to disambiguate"
    assert isinstance(data["confidence"], float)
    assert data["confidence"] < 0.6

    expected_keys = {"name", "lat", "lon", "country_code", "population"}
    for cand in data["candidates"]:
        assert set(cand.keys()) == expected_keys, (
            f"candidate must be the typed subset {expected_keys}, got {set(cand.keys())}"
        )
        # Raw upstream keys must NOT leak through.
        for raw_key in ("latitude", "longitude", "timezone", "elevation", "id"):
            assert raw_key not in cand, f"raw upstream key {raw_key!r} leaked into 422 candidate"
        # latitude→lat / longitude→lon projection is correct.
        assert isinstance(cand["lat"], float)
        assert isinstance(cand["lon"], float)
        assert isinstance(cand["name"], str)
        assert isinstance(cand["country_code"], str)

    # The lat/lon must match the projected source (Springfield A).
    first = data["candidates"][0]
    assert first["lat"] == pytest.approx(SPRINGFIELD_A["latitude"])
    assert first["lon"] == pytest.approx(SPRINGFIELD_A["longitude"])
    assert first["population"] == SPRINGFIELD_A["population"]


def test_missing_population_is_ambiguous_422():
    """Heuristic: missing population → 0.5 < 0.6 → 422 (fail loud, do not silently pick)."""
    a = {k: v for k, v in SPRINGFIELD_A.items() if k != "population"}
    b = {k: v for k, v in SPRINGFIELD_B.items() if k != "population"}
    with patch(GEOCODE_MODULE, return_value=_mock_httpx_client([a, b])):
        r = _post({"place": "Springfield"})
    assert r.status_code == 422, r.text
    assert r.json()["error"] == "ambiguous_place"


# ── 404: no place found ────────────────────────────────────────────────────────

def test_place_not_found_returns_404():
    """Empty Open-Meteo results (service ValueError) → 404 place_not_found."""
    with patch(GEOCODE_MODULE, return_value=_mock_httpx_client([])):
        r = _post({"place": "NoSuchPlace_ZZZ_999"})
    assert r.status_code == 404, r.text
    assert r.json()["error"] == "place_not_found"


# ── 401: auth enforced (require_api_key) ───────────────────────────────────────
# Default test env has no FUFIRE_API_KEYS and no store → dev-mode bypass, so the
# happy-path tests above need no key. To prove the route IS protected we must turn
# auth ON by setting FUFIRE_API_KEYS (mirrors tests/test_error_response_headers.py).

def test_no_api_key_returns_401_when_auth_enabled():
    """With auth configured, a request without X-API-Key → 401 (require_api_key)."""
    from bazi_engine.auth import _load_keys

    os.environ["FUFIRE_REQUIRE_API_KEYS"] = "true"
    os.environ["FUFIRE_API_KEYS"] = "ff_pro_testsecret"
    _load_keys.cache_clear()
    try:
        # No upstream call should even happen (auth rejects first), but mock anyway
        # so a regression that calls upstream before auth is still deterministic.
        with patch(GEOCODE_MODULE, return_value=_mock_httpx_client(BERLIN_ONLY)):
            r = _post({"place": "Berlin"})
    finally:
        os.environ.pop("FUFIRE_REQUIRE_API_KEYS", None)
        os.environ.pop("FUFIRE_API_KEYS", None)
        _load_keys.cache_clear()

    assert r.status_code == 401, f"expected 401 without API key, got {r.status_code}: {r.text}"


def test_valid_api_key_passes_auth():
    """A valid X-API-Key passes the gate (proves it's the auth, not the route, that 401s)."""
    from bazi_engine.auth import _load_keys

    os.environ["FUFIRE_REQUIRE_API_KEYS"] = "true"
    os.environ["FUFIRE_API_KEYS"] = "ff_pro_testsecret"
    _load_keys.cache_clear()
    try:
        with patch(GEOCODE_MODULE, return_value=_mock_httpx_client(BERLIN_ONLY)):
            r = _post({"place": "Berlin"}, headers={"X-API-Key": "ff_pro_testsecret"})
    finally:
        os.environ.pop("FUFIRE_REQUIRE_API_KEYS", None)
        os.environ.pop("FUFIRE_API_KEYS", None)
        _load_keys.cache_clear()

    assert r.status_code != 401, f"valid key was rejected: {r.status_code} {r.text}"
    assert r.status_code == 200, r.text


# ── Reality anchor: route is actually mounted in the assembled production app ───
# Kritische semantische Glättung / Gegenthese: every mocked test above can be green
# while the router is built but never include_router'd into `app`. This test fails
# loudly in that case — an unmounted route returns 404 for BOTH verbs, whereas a
# mounted route with a bad body returns 422 (validation) — never the generic
# "Not Found" of an absent path.

def test_route_is_mounted_not_unmapped_404():
    """An empty body on a mounted /geocode → 422 validation, NOT an unmapped-route 404."""
    r_bare = _post({})            # missing required "place"
    r_v1 = _post({}, path="/v1/geocode")
    for label, resp in (("/geocode", r_bare), ("/v1/geocode", r_v1)):
        assert resp.status_code != 404 or resp.json().get("error") != "not_found", (
            f"{label} appears UNMOUNTED (generic 404), the router was not wired into app: "
            f"{resp.status_code} {resp.text}"
        )
        assert resp.status_code == 422, (
            f"{label} with empty body should be a validation 422, got "
            f"{resp.status_code} {resp.text}"
        )


# ── FIX 1 (REQ-001 review, MAJOR): place input cap (max_length=200) ────────────
# Independent-review defect: GeocodeRequest.place had only min_length=1, so an
# unbounded place string flowed into the Open-Meteo query. A 201-char place must
# be rejected by Pydantic validation (422) before any upstream call.

def test_place_over_200_chars_returns_422_validation():
    """A 201-char place → HTTP 422 (Pydantic max_length=200), no upstream call."""
    long_place = "a" * 201
    # Mock upstream anyway: validation must reject BEFORE any network call,
    # so a regression that calls upstream first is still deterministic.
    with patch(GEOCODE_MODULE, return_value=_mock_httpx_client(BERLIN_ONLY)):
        r = _post({"place": long_place})
    assert r.status_code == 422, r.text


def test_place_at_200_chars_still_accepted():
    """Boundary: exactly 200 chars is within the cap → not a validation 422."""
    place_200 = "a" * 200
    with patch(GEOCODE_MODULE, return_value=_mock_httpx_client(BERLIN_ONLY)):
        r = _post({"place": place_200})
    assert r.status_code == 200, r.text


# ── FIX 2 (REQ-001 review, MAJOR): upstream failure → 503, not 500 ─────────────
# Independent-review defect: an Open-Meteo timeout / 5xx / non-JSON response
# propagated to the app's generic Exception handler → misleading 500
# internal_error. It must surface as a 503 geocoding_unavailable. The legitimate
# empty-result → 404 path (a normal [] return, not an exception) must NOT be
# swallowed by this handling.

def test_upstream_timeout_returns_503_geocoding_unavailable():
    """resp.raise_for_status() raising httpx.TimeoutException → 503, not 500."""
    exc = httpx.TimeoutException("upstream timed out")
    with patch(GEOCODE_MODULE, return_value=_mock_httpx_client_raising(exc)):
        r = _post({"place": "Berlin"})
    assert r.status_code == 503, r.text
    # The app wraps dict HTTPException details in its standard error envelope,
    # which preserves the "error" key (mirrors the 404/422 assertions above).
    assert r.json()["error"] == "geocoding_unavailable", r.text


def test_upstream_5xx_returns_503_geocoding_unavailable():
    """resp.raise_for_status() raising HTTPStatusError (5xx) → 503, not 500."""
    request = httpx.Request("GET", "https://geocoding-api.open-meteo.com/v1/search")
    response = httpx.Response(503, request=request)
    exc = httpx.HTTPStatusError("server error", request=request, response=response)
    with patch(GEOCODE_MODULE, return_value=_mock_httpx_client_raising(exc)):
        r = _post({"place": "Berlin"})
    assert r.status_code == 503, r.text
    assert r.json()["error"] == "geocoding_unavailable", r.text


def test_empty_results_still_404_not_swallowed_as_503():
    """The legitimate empty-result path must stay 404 place_not_found (not 503)."""
    with patch(GEOCODE_MODULE, return_value=_mock_httpx_client([])):
        r = _post({"place": "NoSuchPlace_ZZZ_999"})
    assert r.status_code == 404, r.text
    assert r.json()["error"] == "place_not_found"


# ── FIX 3 (REQ-001 review, MINOR): clamp confidence into the [0, 1] contract ───
# Independent-review defect: _compute_confidence could exceed 1.0 when a
# candidate carried a negative population (pop_top / (pop_top + pop_second) with a
# negative second pop → > 1). The contract states confidence ∈ [0, 1].

def test_negative_population_confidence_not_above_one():
    """A candidate with a negative second population must not yield confidence > 1."""
    top = {**BERLIN_ONLY[0], "name": "Dupville", "population": 100}
    second = {**BERLIN_ONLY[0], "name": "Dupville", "population": -40}
    with patch(GEOCODE_MODULE, return_value=_mock_httpx_client([top, second])):
        r = _post({"place": "Dupville"})
    # 200 (clamped to 1.0, above threshold) or 422 (ambiguous) are both contract-
    # valid; the defect is a confidence value > 1.0 leaking out. Assert the bound.
    body = r.json()
    confidence = body.get("confidence")
    assert confidence is not None, body
    assert confidence <= 1.0, f"confidence must be clamped to <= 1.0, got {confidence}"
    assert 0.0 <= confidence <= 1.0


# ── M3 (REQ-001 follow-up): country-suffix disambiguation through the endpoint ─
# OQ-003: a ", XX" country suffix narrows the candidate set. With both Parises
# returned by upstream, "Paris, US" must filter to Paris TX only → 1 candidate →
# confidence 1.0 → 200 with country_code "US". Proves disambiguation works end to
# end (router + service), not just in the service unit tests.

def test_country_suffix_disambiguates_to_single_candidate_200():
    """POST {"place":"Paris, US"} over [Paris FR, Paris TX] → 1 candidate, US, conf 1.0."""
    with patch(GEOCODE_MODULE, return_value=_mock_httpx_client(DOMINANT_PARIS)):
        r = _post({"place": "Paris, US"})
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["country_code"] == "US"
    assert data["confidence"] == pytest.approx(1.0)
    assert data["lat"] == pytest.approx(PARIS_TX["latitude"])
    assert data["lon"] == pytest.approx(PARIS_TX["longitude"])
    assert data["timezone"] == PARIS_TX["timezone"]


# ── I1 (REQ-001 follow-up): geocode_candidates result is cached (no re-hammer) ─
# Review finding: every POST hit Open-Meteo, even for an identical (place,
# language). place→coords is stable, so the service now memoizes the candidate
# list with a TTL. A second identical POST must be served from cache — the mock
# httpx client's .get must be awaited exactly ONCE across two identical requests.

def test_repeat_request_served_from_cache_no_second_upstream_call():
    """Two identical POSTs → upstream .get awaited exactly once (second is cached)."""
    mock_client = _mock_httpx_client(DOMINANT_PARIS)
    with patch(GEOCODE_MODULE, return_value=mock_client):
        r1 = _post({"place": "Paris"})
        r2 = _post({"place": "Paris"})
    assert r1.status_code == 200, r1.text
    assert r2.status_code == 200, r2.text
    assert r1.json() == r2.json()
    assert mock_client.get.await_count == 1, (
        f"second identical request must be served from cache, "
        f"upstream .get was awaited {mock_client.get.await_count} times"
    )


def test_cached_list_copy_not_mutated_across_calls():
    """Cache must return a COPY: a 422 candidate-list mutation must not poison a refetch."""
    mock_client = _mock_httpx_client(AMBIGUOUS_SPRINGFIELD)
    with patch(GEOCODE_MODULE, return_value=mock_client):
        r1 = _post({"place": "Springfield"})
        # Mutating the response payload must not affect the cached service list.
        r1.json()["candidates"].clear()
        r2 = _post({"place": "Springfield"})
    assert r2.status_code == 422, r2.text
    assert len(r2.json()["candidates"]) >= 2
    assert mock_client.get.await_count == 1


# ── EV-001: live-boundary smoke against the REAL Open-Meteo API (skipped) ───────
# This is the only test that touches the real network. It is SKIPPED by default and
# runs only with RUN_LIVE=1 (no pre-existing live/network marker in this repo, so
# the env-gate is introduced and documented here). It proves the assembled path —
# real router + real geocode service + real Open-Meteo response shape — actually
# resolves a stable place, killing the "green against a fake, broken against reality"
# counter-thesis.

RUN_LIVE = os.environ.get("RUN_LIVE") == "1"


@pytest.mark.skipif(not RUN_LIVE, reason="live Open-Meteo smoke (EV-001) — set RUN_LIVE=1 to run")
def test_live_geocode_berlin_de_smoke():
    """EV-001: real Open-Meteo resolves 'Berlin, DE' through the assembled endpoint."""
    r = _post({"place": "Berlin, DE"})
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["country_code"] == "DE"
    # Berlin DE ≈ 52.52 / 13.405 — generous tolerance against minor catalog drift.
    assert data["lat"] == pytest.approx(52.52, abs=0.5)
    assert data["lon"] == pytest.approx(13.405, abs=0.5)
    assert data["timezone"] == "Europe/Berlin"
    assert isinstance(data["confidence"], float)
