# ADR-004: `/ready` returns dependency-rich `HealthResponse` on 503

- Status: accepted for the Engine contract; generated OpenAPI closure pending
- Date: 2026-07-22
- Owners: Engine Maintainer, Platform
- Related gate: LR-010

## Context

`GET /health` is a liveness signal and remains HTTP 200 while reporting dependency degradation. `GET /ready` is the orchestration/load-balancer signal and returns HTTP 503 when a required dependency is unavailable. The current runtime response on 503 is the same dependency-rich `HealthResponse` used on 200, while generic protected-operation failures normally use the shared error envelope.

Returning only a generic error envelope from `/ready` would remove the dependency state needed to distinguish ephemeris and required rate-limiter failures during deployment and rollback. Returning a dependency-rich response without declaring it in OpenAPI would leave clients and operators with an undocumented exception.

## Decision

1. `/ready` keeps `HealthResponse` for both 200 and 503.
2. The 503 response is an explicit, narrow exception to the generic error-envelope convention because readiness is an operational state resource, not a business-operation failure.
3. The response may expose dependency names, status, whether a dependency is required, and non-secret diagnostic classification such as limiter type.
4. The response must not expose Redis URIs, credentials, API keys, filesystem secrets, stack traces, or raw exception internals that reveal sensitive configuration.
5. The next contract-changing RC patch must declare the 503 `HealthResponse` in the generated OpenAPI and add a regression test asserting the schema reference.
6. Railway readiness probes must use `/ready`; `/health` must not be substituted as a deployment-readiness check.

## Consequences

- Existing runtime behavior and current readiness tests remain compatible.
- Platform tooling can use dependency state during failure injection and rollback verification.
- LR-010 remains `PARTIAL` until the generated OpenAPI contains the explicit 503 schema and the same contract is proven on Railway Staging.
- No production promotion is authorized by this ADR alone.

## Verification required for closure

- Focused runtime tests for ephemeris unavailable, required Redis degraded, and optional in-memory limiter healthy.
- OpenAPI test asserting `paths./ready.get.responses.503` references `HealthResponse`.
- Generated OpenAPI drift check.
- Railway probe test showing 503 prevents routing and 200 restores readiness.
