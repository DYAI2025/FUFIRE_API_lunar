# Staging release gate runbook (TASK-018)

Status: **prepared; execution blocked on an immutable RC and Railway access**

## Preconditions

- `release-gate` succeeded for the exact RC commit.
- RB-004, RB-017, branch protection, and required domain approvals are closed.
- Staging is isolated from production data and secrets.
- Approved latency/error/resource thresholds are recorded in the report before
  load execution.

## Execution contract

1. Deploy the exact RC commit/build and record Railway project, service,
   environment, deployment, build, and commit IDs.
2. Assert `/build` matches the RC and `/ready` returns 200 while `/health`
   remains the liveness boundary.
3. Run no-key, invalid-key, valid-key, CORS allow/deny, request-ID, and redacted
   error tests without storing secret values.
4. Execute the approved Lunar SWIEPH reference requests over HTTP.
5. In a controlled staging window, make required Redis and SE1 data unavailable
   one at a time; `/ready` must return 503 and traffic must not be promoted.
6. Run the pre-approved load matrix and record p50/p95/p99 latency, error rate,
   CPU, memory, and Redis metrics.
7. Restore dependencies, require `/ready` 200, and attach sanitized logs and
   metric snapshots.

Use `evidence/release-readiness/staging-report.template.json`; do not replace
`null` thresholds or observations with estimates. Promotion remains blocked if
any required field is absent or any threshold is not approved and met.
