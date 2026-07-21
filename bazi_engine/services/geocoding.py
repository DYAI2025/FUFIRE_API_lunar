"""
services/geocoding.py — Place name → lat/lon/timezone resolution.

Uses Open-Meteo Geocoding API (free, no API key required).
Uses httpx.AsyncClient to avoid blocking the FastAPI event loop.
"""
from __future__ import annotations

import copy
import time
from typing import Any, Dict, List, Tuple
from urllib.parse import urlencode

import httpx

# ── Confidence heuristic + candidate projection (single source of truth, I1) ───
# The v1 confidence rule, the ambiguity threshold, and the typed-candidate
# projection used to live duplicated in both routers/geocode.py and
# routers/personalize.py (byte-identical logic). They are centralised here —
# PURE, no FastAPI coupling — so a future change touches exactly one place.
# Routers import these; the service never imports a router (no cycle).

# Below this score a resolved place is considered ambiguous (rejected with 422
# by the callers). Kept as the single source of the OQ-001 gate threshold.
AMBIGUITY_THRESHOLD = 0.6


def compute_confidence(candidates: List[Dict[str, Any]]) -> float:
    """Deterministic v1 confidence from the ranked candidate list.

    Rule (docs/plans/2026-06-18-req-001-geocode-endpoint.md):
      - exactly 1 candidate            → 1.0
      - >= 2 candidates                → ``pop_top / (pop_top + pop_second)``
        from the two top candidates' populations
      - a missing population on either of the top two → 0.5 (ambiguous)
      - total population <= 0          → 0.5
      - the ratio is clamped into the [0, 1] contract (a negative population on
        either top-2 candidate could otherwise push it outside the range).
    """
    if len(candidates) == 1:
        return 1.0

    pop_top = candidates[0].get("population")
    pop_second = candidates[1].get("population")
    if pop_top is None or pop_second is None:
        return 0.5

    total = pop_top + pop_second
    if total <= 0:
        return 0.5
    return max(0.0, min(1.0, pop_top / total))


def project_candidate(c: Dict[str, Any]) -> Dict[str, Any]:
    """Project a raw Open-Meteo candidate to the typed 422 subset.

    The subset is ``{name, lat, lon, country_code, population}`` with
    ``latitude``→``lat`` and ``longitude``→``lon`` renamed. Pinning the 422
    candidate shape to this explicit subset stops raw upstream drift
    (timezone/elevation/id/…) from leaking into the contract.
    """
    return {
        "name": str(c.get("name") or ""),
        "lat": float(c["latitude"]),
        "lon": float(c["longitude"]),
        "country_code": str(c.get("country_code") or ""),
        "population": c.get("population"),
    }


# ── In-memory TTL cache for geocode_candidates (I1) ────────────────────────────
# place→coords is stable, so we memoize the resolved candidate list (including
# empty results = negative cache) to avoid hammering Open-Meteo. Keyed by the
# normalized (place, language). Failures are NOT cached (the cache write only
# happens after a successful upstream call). Single-process, single-threaded
# FastAPI event loop, so a plain dict is safe without locking.
_CACHE_TTL_SECONDS = 24 * 60 * 60  # place→coords is stable; 24h is plenty.
_CACHE_MAX_ENTRIES = 1024
_geocode_cache: Dict[Tuple[str, str], Tuple[float, List[Dict[str, Any]]]] = {}


def _cache_key(place: str, language: str) -> Tuple[str, str]:
    """Normalize (place, language) into a stable cache key."""
    return (place.strip().casefold(), language.strip().casefold())


def clear_geocode_cache() -> None:
    """Reset the in-memory geocode cache.

    Wired into the test suite (autouse fixture) to prevent cross-test pollution,
    and useful operationally to force a refetch.
    """
    _geocode_cache.clear()


async def geocode_candidates(place: str, language: str = "de") -> List[Dict[str, Any]]:
    """Resolve a place name into up to 5 ranked Open-Meteo candidates.

    Accepts formats like "Berlin", "Berlin, DE", "Tokyo, JP". If a
    comma-separated 2-letter country code is present, candidates are filtered
    by it (the filter is dropped when it would eliminate every candidate, so
    behaviour matches ``geocode_place``).

    The returned candidates are the raw Open-Meteo result dicts, preserving at
    least ``latitude``, ``longitude``, ``timezone``, ``name``, ``country_code``
    and ``population`` when the upstream provides them. Candidate order is the
    upstream ranking (most relevant first), which the confidence heuristic
    relies on.

    Args:
        place:    Place name, optionally with country code suffix.
        language: Language code for result names (default: "de").

    Returns:
        List of candidate dicts (possibly empty when nothing matched).
    """
    key = _cache_key(place, language)
    cached = _geocode_cache.get(key)
    if cached is not None:
        ts, results = cached
        if (time.monotonic() - ts) < _CACHE_TTL_SECONDS:
            # Return a deep copy so callers can mutate freely without poisoning
            # the cached list (it holds nested dicts).
            return copy.deepcopy(results)
        # Expired entry — drop it and fall through to a fresh fetch.
        _geocode_cache.pop(key, None)

    parts = [p.strip() for p in place.split(",", maxsplit=1)]
    search_name = parts[0]
    country_filter = (
        parts[1].upper()
        if len(parts) > 1 and len(parts[1].strip()) == 2
        else None
    )

    url = "https://geocoding-api.open-meteo.com/v1/search?" + urlencode({
        "name": search_name, "count": 5, "language": language, "format": "json",
    })

    async with httpx.AsyncClient(
        headers={"User-Agent": "bafe-bazi-engine/1.0"},
        timeout=5.0,
    ) as client:
        resp = await client.get(url)
        # raise_for_status raising here propagates BEFORE the cache write below,
        # so upstream failures are never cached.
        resp.raise_for_status()
        data = resp.json()

    results = data.get("results") or []
    if country_filter:
        filtered = [
            r for r in results
            if r.get("country_code", "").upper() == country_filter
        ]
        if filtered:
            results = filtered

    results = list(results)

    # Bound the cache: a simple clear at the cap keeps it from growing unbounded
    # without the complexity of an LRU. Negative results ([]) are cached too.
    if len(_geocode_cache) >= _CACHE_MAX_ENTRIES:
        _geocode_cache.clear()
    _geocode_cache[key] = (time.monotonic(), copy.deepcopy(results))

    return results


async def geocode_place(place: str, language: str = "de") -> Dict[str, Any]:
    """Resolve place name to lat/lon/timezone via Open-Meteo Geocoding API.

    Accepts formats like "Berlin", "Berlin, DE", "Tokyo, JP".
    If a comma-separated 2-letter country code is present, results are
    filtered by it.

    Args:
        place:    Place name, optionally with country code suffix.
        language: Language code for result names (default: "de").

    Returns:
        Dict with keys: lat, lon, timezone, name, country_code.

    Raises:
        ValueError: If no matching place is found.
    """
    results = await geocode_candidates(place, language)

    if not results:
        raise ValueError(f"Could not geocode place: {place}")

    r = results[0]
    return {
        "lat": float(r["latitude"]),
        "lon": float(r["longitude"]),
        "timezone": str(r.get("timezone") or ""),
        "name": str(r.get("name") or place),
        "country_code": str(r.get("country_code") or ""),
    }
