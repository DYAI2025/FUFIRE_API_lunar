# Plan — REQ-001 Geocode-Endpoint

Feature: `fufire-domain-ownership` · REQ-001 · Branch `feat/req-001-geocode-endpoint` (off main).
Quelle: `docs/prd/fufire-domain-ownership.prd.md`, OQ-001 entschieden.

## Kontext
`bazi_engine/services/geocoding.py::geocode_place()` existiert (Open-Meteo, kostenlos, kein Key),
liefert `{lat, lon, timezone, name, country_code}` — nimmt aber still `results[0]` und hat
**kein `confidence`**. Kein HTTP-Endpoint exponiert ihn. REQ-001 = exponieren + OQ-001-Ambiguität.

## Contract (Acceptance, black-box)
Neuer Router, FastAPI, gemountet unprefixed + `/v1`, `dependencies=_protected` (require_api_key).

- **POST `/geocode`** (+ `/v1/geocode`), body `{ "place": str, "language"?: str = "de" }`.
- **200** bei eindeutigem Treffer:
  `{ "lat": float, "lon": float, "resolved_name": str, "confidence": float, "timezone": str, "country_code": str }`
- **OQ-001 Ambiguität (fail loud):** `confidence < 0.6` → **422** `{ "error": "ambiguous_place", "candidates": [...], "confidence": float }`.
- **404** `{ "error": "place_not_found" }` wenn kein Treffer (Service `ValueError`).
- **401/403** ohne API-Key (wie alle `_protected` Routen).

## Confidence-Heuristik (⚠ ASSUMPTION v1 — Acceptance-Gate bestätigen)
Open-Meteo liefert KEINEN nativen Score. v1-Ableitung aus Kandidatenliste (deterministisch testbar):
- Service erweitern: `geocode_candidates(place, language) -> list[dict]` (bis 5 ranked Kandidaten);
  `geocode_place` darauf refactoren (Verhalten unverändert).
- 0 Kandidaten → not found (404).
- 1 Kandidat (nach optionalem Country-Filter) → `confidence = 1.0`.
- Country-Code gegeben und filtert auf genau 1 → `1.0`.
- ≥2 Kandidaten → `confidence = pop_top / (pop_top + pop_second)` (Population-Dominanz).
  Fehlt Population → `0.5` (ambig). „Paris" (FR≫TX) hoch; „Springfield" (viele gleich) niedrig → fail loud.
- Schwelle `< 0.6` → 422 mit Kandidatenliste, damit Consumer präzisieren kann.

Diese Heuristik ist eine vorgeschlagene v1, **sichtbar fürs Acceptance-Gate** — nur der User reklassifiziert.

## Tasks
- T2 (tester, independent): `tests/test_geocode_endpoint.py` — Open-Meteo gemockt (deterministisch):
  eindeutig→200+shape; ambig low-conf→422+candidates; unknown→404; ohne Key→401/403.
  Plus 1 `@live`/`network`-markierter Smoke gegen echtes Open-Meteo (default skipped) = EV-001.
- T3 (coder, fresh): `geocode_candidates` + confidence + `routers/geocode.py` + mount in `app.py`. Tests grün.
- T4 (code-reviewer): diff review (SSRF/Injection: place→externe URL bereits in geocode_place; clean-code).
- T5: Gate A (suite) + Gate C reality (Open-Meteo Live-Smoke EV-001).
- T6: commit + PR.

## Non-Goals
Kein `/v1/personalize` (REQ-002), keine Caching-Schicht, kein Timezone-Rework.
