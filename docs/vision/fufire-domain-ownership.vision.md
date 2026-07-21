# Product Vision — FuFire Domain Ownership

> Quelle: SRC-001 (Operator-Intake-Spec). Slug: `fufire-domain-ownership`.

## VIS-001 — Vision Statement (EXPLICIT)
FuFire wird der **Owner des Metaphysik-Domänenvertrags** (BaZi / Wuxing / Zodiac
inkl. Geocoding). Domänen-Interpretation und Ortsauflösung liegen dort, wo das
Domänenwissen sitzt — in FuFire — statt in konsumierenden Middlewares.

## VIS-002 — Zielnutzer / Consumer (EXPLICIT)
Primärer Consumer: **Sizhu-Middleware** (POD-Chain). Sie wird vom Domänen-Interpreter
zum **dünnen Consumer** eines stabilen `/v1/`-Vertrags. Sekundär: jeder künftige
Consumer, der personalisierte Prompt-Vars ohne eigene Pillar-Interpretation braucht.

## VIS-003 — Value Proposition (EXPLICIT)
- Ein `/v1/personalize`-Call statt 2–3 (bazi + wuxing + fusion).
- Kein `NO_GEOCODER_CONFIGURED` mehr — 0 manuelle Koordinateneingaben.
- Single Source of Truth für Metaphysik-Semantik → kein Interpreter-Drift über Repos.

## VIS-004 — Success Signal (EXPLICIT)
Eine POD-Chain läuft End-to-End gegen ECHTE FuFire-Endpunkte bis QA Gate 2,
mit 0 manuellen Koordinateneingaben (siehe REQ-004 / AC-004).

## VIS-005 — Scope-Grenze (EXPLICIT)
In: Geocoding-, Aggregat-Endpunkt, Migration deferred-Mappings, E2E-Nachweis.
Aus: echte Etsy-Prod-Integration, POD-Dispatch/Gelato, Middleware-UI-Redesign
(außer Entfernen des manuellen lat/lon-Felds).
