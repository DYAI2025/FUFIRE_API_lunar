# FuFirE Customer Guide

This guide explains how product teams and agencies can use FuFirE API to build revenue-generating features.

## 1. What FuFirE Enables

FuFirE combines:
- BaZi calculations (`/calculate/bazi`)
- Western astrology (`/calculate/western`)
- Fusion scoring and interpretation (`/calculate/fusion`, `/calculate/wuxing`)
- Real-time and daily transit intelligence (`/transit/*`, `/experience/*`)
- Contract validation and compliance checks (`/validate`)

For production integrations, use `/v1/*` endpoints with `X-API-Key`.

## 2. Example Product Use Cases (with API Flows)

## Use Case A: Paid Personalized Birth Chart

**User flow**
1. User enters birth data.
2. Your app creates a premium chart.
3. You sell one-off reports or subscriptions.

**Endpoint flow**
1. `POST /v1/calculate/bazi`
2. `POST /v1/calculate/western`
3. `POST /v1/calculate/fusion`
4. Optional: `POST /chart` (legacy helper endpoint — **deprecated**, internal only)

**Monetization**
- One-time report fee (`$19-$149`)
- Upsell to monthly membership
- White-label report resale

## Use Case B: Daily Insight Subscription App

**User flow**
1. User completes onboarding once.
2. App computes profile and sends daily guidance.
3. Premium users unlock advanced daily narratives.

**Endpoint flow**
1. `POST /v1/experience/bootstrap` (once per user)
2. `POST /v1/experience/daily` (daily cron)
3. `POST /v1/transit/narrative` (premium personalization)

**Monetization**
- Monthly subscription (`$8-$39`)
- Annual plan discount for retention
- Premium tier for deeper analysis

## Use Case C: Engagement Engine for Existing Wellness App

**User flow**
1. Existing app injects “today’s energy” cards.
2. Users open app daily for personalized prompts.
3. Higher DAU improves conversion to paid plans.

**Endpoint flow**
1. `GET /v1/transit/now`
2. `POST /v1/transit/state`
3. `GET /v1/transit/timeline`

**Monetization**
- Indirect revenue via increased retention
- Better conversion from free to paid plans
- Higher LTV through habit loops

## Use Case D: Coach / Consultant Automation

**User flow**
1. Client books session and fills birth data.
2. Coach receives automated briefing pack.
3. Session prep time drops from hours to minutes.

**Endpoint flow**
1. `POST /v1/calculate/bazi`
2. `POST /v1/calculate/fusion`
3. `POST /v1/transit/timeline`

**Monetization**
- Higher margin per session
- Serve more clients per week
- Offer premium “deep dive” packages

## Use Case E: Lead Magnet Funnel

**User flow**
1. Visitor requests free mini-reading.
2. You capture email, return a teaser.
3. Upsell to paid full report or membership.

**Endpoint flow**
1. `POST /v1/calculate/wuxing`
2. `POST /v1/calculate/fusion`
3. Optional webhook pipeline via `/internal/api/webhooks/chart` (internal path — ElevenLabs integration only)

**Monetization**
- Lead generation for coaching/program sales
- CPA reduction for paid ads
- Email nurture to recurring offers

## 3. Business Models: How Customers Can Make Money

## Model 1: Subscription SaaS
- **Offer:** Daily/weekly astrology intelligence.
- **Revenue:** MRR/ARR.
- **Best endpoints:** `/v1/experience/*`, `/v1/transit/*`.
- **Typical KPI:** churn, DAU/MAU, trial-to-paid.

## Model 2: One-Time Premium Reports
- **Offer:** Detailed birth/fusion reports.
- **Revenue:** one-time checkout.
- **Best endpoints:** `/v1/calculate/bazi`, `/v1/calculate/western`, `/v1/calculate/fusion`.
- **Typical KPI:** conversion rate, AOV.

## Model 3: B2B API Reseller / White Label
- **Offer:** “Astrology intelligence API” for niche apps.
- **Revenue:** usage-based markup or seat licenses.
- **Best endpoints:** full `/v1` suite + `/v1/validate`.
- **Typical KPI:** gross margin, requests/customer, expansion revenue.

## Model 4: Agency Service Product
- **Offer:** Done-for-you funnels and reading systems for coaches.
- **Revenue:** setup fee + monthly retainer.
- **Best endpoints:** `/v1/calculate/*`, `/v1/experience/*`.
- **Typical KPI:** delivery cost per client, margin per project.

## Model 5: In-App Purchases (Consumer Apps)
- **Offer:** unlock advanced transit narratives or compatibility packs.
- **Revenue:** microtransactions + bundles.
- **Best endpoints:** `/v1/transit/narrative`, `/v1/experience/daily`.
- **Typical KPI:** ARPPU, purchase frequency.

## 4. Packaging Ideas Your Customers Can Sell

## Starter Plan (B2C)
- 1 birth chart
- Daily summary
- Basic element analysis

## Pro Plan (B2C/B2B creator)
- Full fusion report
- 30-day transit timeline
- Priority interpretation layer

## Team Plan (B2B)
- Multi-user dashboard
- API access for internal tools
- SLA + validated configuration workflows

## 5. Revenue Design Checklist for Your Customers

- Define one paid “core outcome” (for example: daily guidance that improves user consistency).
- Use free teaser + paid depth strategy.
- Gate high-frequency value behind subscription.
- Use `request_id` and error envelope in support workflows to reduce churn from integration issues.
- Track usage-to-revenue ratio by endpoint family.

## 6. Suggested Pricing Strategy (for Customers Using FuFirE)

- **Entry:** low-friction monthly tier (`$9-$19`)
- **Growth:** premium tier (`$29-$79`) with deeper narratives and timelines
- **B2B:** contract pricing (seat + usage + support SLA)

Simple pricing formula:

`Price floor >= (API cost per active user + support cost per active user + infra overhead) / target gross margin`

## 7. Risk and Compliance Notes

- Astrology outputs should be framed as guidance, not medical/legal/financial advice.
- Add transparent disclaimers in checkout and onboarding.
- For enterprise, use `/v1/validate` to enforce deterministic config policy.

## 8. Build-to-Revenue Launch Plan (30 Days)

1. Week 1: launch paid birth-chart endpoint flow.
2. Week 2: add daily notifications (`/v1/experience/daily`).
3. Week 3: add upsell wall for premium transit narratives.
4. Week 4: optimize funnel using conversion and retention data.

---

For exact endpoint schemas, use:
- [Developer API Reference](01_developer_api_reference.md)
- [OpenAPI Source of Truth](../../spec/openapi/openapi.json)
