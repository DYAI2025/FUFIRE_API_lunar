# release-please identity gate (RB-004)

Status: **repository wiring complete; external credential and bot-PR proof missing**  
Owner: Platform / Security

The workflow passes `secrets.RELEASE_PLEASE_TOKEN` explicitly. This avoids the
known `GITHUB_TOKEN` recursion boundary in which a pull request created by the
workflow token does not start the normal pull-request workflows. A missing
secret makes release automation fail closed.

Provision one of these identities for this repository only:

1. Preferred: a GitHub App installation/user token with repository contents
   write and pull-request write permissions; or
2. A fine-grained, expiring PAT with the same minimum repository scope, a named
   owner, and a recorded rotation date.

The secret value must never be printed, committed, added to an artifact, or
placed in a Railway variable. GitHub's documented workflow-trigger boundary is
the governing behavior: [Triggering a workflow from a workflow](https://docs.github.com/en/actions/how-tos/writing-workflows/choosing-when-your-workflow-runs/triggering-a-workflow#triggering-a-workflow-from-a-workflow).

RB-004 closes only after a test release-please PR has recorded check-run IDs
for `pr-title-lint` and the complete `release-gate`, with no bypass or manual
re-run under a different commit.
