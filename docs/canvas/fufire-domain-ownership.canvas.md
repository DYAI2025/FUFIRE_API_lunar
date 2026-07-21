# Product Canvas — FuFire Domain Ownership

> Quelle: SRC-001. Slug: `fufire-domain-ownership`.

## CAN-001 — Problem (EXPLICIT)
Middleware interpretiert rohe FuFire-Pillar-Shapes selbst (`fufireResponseInterpreter.ts`)
und hat keinen Geocoder → Operator muss lat/lon manuell eingeben. Domänenlogik
dupliziert/verlagert, Drift-Risiko, manuelle Schritte.

## CAN-002 — Zielnutzer (EXPLICIT)
Sizhu-Middleware als Consumer; Operator der POD-Chain.

## CAN-003 — Value Proposition (EXPLICIT)
Siehe VIS-003: 1 Call, kein Geocoder-Gap, eine Domänen-Wahrheit.

## CAN-004 — Lösung / Deliverables (EXPLICIT)
1. REQ-001 Geocoding-Endpunkt (Ortsname → lat/lon).
2. REQ-002 Aggregat-Endpunkt `/v1/personalize` (Geburtsdaten → Prompt-Vars).
3. REQ-003 Migration deferred-unverified Mappings (bazi/trace, chronometry) zu FuFire.

## CAN-005 — Key Metrics / Erfolg (EXPLICIT)
- 0 manuelle Koordinateneingaben.
- 1 Aggregat-Call statt 2–3.
- Paritäts-Diff alt vs. neu: 0 Abweichungen.
- E2E-Chain bis Gate 2 grün.

## CAN-006 — Constraints / Consumer-Vertrag (EXPLICIT)
- Prompt-Var-Feldnamen + Typen aus REQ-002 = bindender Vertrag (kein Shape-Drift).
- Vertrag versioniert/stabil unter `/v1/`.
- Auth via API-Key; Key niemals in Response/Log (Secret-Hygiene).

## CAN-007 — Risiken (EXPLICIT)
RISK-001 Cross-Repo-Drift · RISK-002 Semantik-Bruch bei Verlagerung ·
RISK-003 Geocoding-Ambiguität. (Mitigations → PRD.)

## CAN-008 — Non-Goals (EXPLICIT)
Etsy-Prod-Integration · POD-Dispatch/Gelato · Middleware-UI-Redesign.
