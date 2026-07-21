# Production promotion and rollback runbook (TASK-019)

Status: **prepared; no production action executed**

Promotion is authorized only when the release-please PR, tag candidate, CI
evidence, image digest, staging deployment, and approvals all identify the same
commit and RB-017 is closed.

## Promotion

1. Verify the release-please diff contains the approved SemVer and changelog.
2. Verify protected-branch approval and a successful `release-gate` on the PR
   head; record immutable check-run URLs.
3. Merge without bypass. Verify the created tag/release commit exactly matches
   the protected merge commit.
4. Promote the approved image digest/build identity. Do not rebuild from an
   unpinned branch.
5. Verify `/build`, `/ready`, no/invalid/valid auth, CORS, and a small Lunar
   reference smoke. Observe agreed metrics for the approved window.

## Rollback trigger and procedure

Trigger rollback on identity mismatch, readiness degradation, auth/CORS bypass,
material error-rate/latency breach, missing dependency/license evidence, or
incorrect astronomical reference output.

1. Stop further promotion and record incident time and current deployment ID.
2. Reactivate the previously recorded healthy deployment/image digest.
3. Verify its `/build`, `/ready`, auth, and smoke contract.
4. Revoke/rotate newly exposed credentials when the incident scope requires it.
5. Mark the release withdrawn; never delete tags or rewrite history to conceal
   the failed release.
6. Record recovery time, sanitized evidence, impact, and follow-up owner.

A rollback rehearsal in isolated production simulation is acceptable only when
the Release Manager records why a real production rollback was unsafe. Blank or
estimated evidence does not satisfy TASK-019.
