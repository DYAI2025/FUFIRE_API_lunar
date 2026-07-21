# Plan — REQ-002 `/v1/personalize` (+ REQ-003 domain_extras)

Feature `fufire-domain-ownership` · Branch `feat/req-002-personalize` (off main, has REQ-001 geocode).
Contract decision: **Option A** (Operator-confirmed 2026-06-18) — 4 flat prompt-vars + domain_extras.
Parity source (authoritative semantics): `/Users/benjaminpoersch/Projects/SaaS/Sizhu/Sizhu_middleware/server/services/fufireResponseInterpreter.ts` + its tests.

## Endpoint
POST `/personalize` (+ `/v1/personalize`), `dependencies=_protected`, `@limiter.limit(tier_limit)`,
global OpenAPI tag "Personalize". Aggregates internal compute (NOT HTTP self-calls): geocoding (REQ-001)
+ bazi + wuxing + bazi/trace + chronometry. **No fusion** (eastern_dominant is not in the consumer contract).

## Request (PersonalizeRequest)
- `birth_datetime`: str (ISO 8601 local) — passed as bazi/wuxing `date`.
- Location oneOf (OQ-003): EITHER `place`: str (→ internal geocode via REQ-001 geocode_candidates → lat/lon/timezone)
  OR explicit `lat`+`lon`+`tz`. Validation: exactly one of {place} / {lat,lon,tz}; else 422.
- `birth_time_known`: bool = true (pass-through to bazi).
- `locale`: "de"|"en" = "en" (selects animal source, see mapping).
- If `place` geocoding is ambiguous (REQ-001 conf<0.6) → 422 ambiguous_place (reuse REQ-001 behavior); not-found → 404.

## Output (PersonalizeResponse) — 4 flat vars + provenance + extras
```json
{
  "animal": "Horse|Pferd|null",
  "element": "Metall|null",
  "birth_year": 1990,
  "dominant_element": "Holz|null",
  "sources": { "animal": "bazi.chinese.year.animal", ... },
  "issues": ["PROMPT_VARIABLE_SOURCE_MISSING: ..."],
  "caveats": ["day-pillar anchor_verification: unverified"],
  "domain_extras": { "bazi_trace": { ... }, "chronometry": { ... } }
}
```

## Parity mapping (EXACT — from the interpreter, RISK-002 / EV-002-Parität)
- `animal` ← locale: de→`bazi.pillars.year.tier`, en→`bazi.chinese.year.animal` (paired, never mixed).
- `element` ← `bazi.pillars.year.element`.
- `birth_year` ← `bazi.transition.solar_year` (finite number).
- `dominant_element` ← `wuxing.dominant_element` (location-invariant western dominance; bound unguarded).
- **No invented data:** an absent/empty/wrong-type source → var ABSENT (null) + push
  `PROMPT_VARIABLE_SOURCE_MISSING: <var> (no source at <path>)`. Never default/guess.
- **Day-anchor caveat (no laundering):** read `bazi.derivation_trace.day.day_anchor_evidence.anchor_verification`;
  surface verbatim as `caveats: ["day-pillar anchor_verification: <value>"]`. If absent → an issue, never imply verified.
- Provenance: record matched source path per resolved var in `sources`.

## domain_extras (REQ-003 migration)
- `bazi_trace` ← internal `/calculate/bazi/trace` compute (real now; the old interpreter render-blocked it as
  "no real sample" — this endpoint provides the REAL data, that IS the migration).
- `chronometry` ← internal `/chronometry/resolve` compute.
- These are REAL engine outputs → no PROMPT_VARIABLE_SOURCE_MISSING for them.

## Internal wiring (coder)
Read how the existing routers compute and reuse the underlying compute functions/modules directly
(bazi_engine/* modules, not HTTP). Files: routers/{bazi,fusion(wuxing),bazi(trace),chronometry}.py and the
bazi_engine/{bazi or shared, fusion, chronometry}.py compute modules. geocode: reuse
bazi_engine/services/geocoding.geocode_candidates + the REQ-001 confidence rule.

## Parity test strategy (EV-002-Parität)
The old interpreter is TS; this is Python. Port its test cases: read the middleware's
`server/tests/fufire.responseInterpreter.test.ts` + captured samples
(`docs/contracts/fufire-samples/*.json` if present) and replicate the SAME input→output cases in pytest —
same bazi/wuxing sample → same 4 vars, same PROMPT_VARIABLE_SOURCE_MISSING issues, same day-anchor caveat.
That is the concrete parity proof.

## Tasks
- T2 tester: black-box endpoint tests, internal compute mocked deterministically; parity cases ported from TS;
  oneOf input (place→geocode vs coords); missing-source→issue+null; day-anchor caveat verbatim; domain_extras present;
  mount-reality anchor; auth 401; + RUN_LIVE EV-004-ish live smoke (real birth input end-to-end).
- T3 coder: PersonalizeRequest/Response, internal aggregation, parity mapping, domain_extras, dual-mount + tag.
- T4 review (clean-code + parity correctness + no-invented-data + injection/SSRF via place).
- T5 Gate A + Gate C reality (live personalize smoke against real engine post-deploy).
- T6 commit + PR.

## Non-Goals
No fusion/eastern_dominant. No caching beyond REQ-001's geocode cache. No new metaphysics math (reuse engine).
