# Contradictions: fufire-premium-verification-ci (WS-A increment)

Recorded by: plumbline-watcher, per-increment True-Line check (T12 gate)
Date: 2026-07-01

---

## CONTRA-1 — AC-01-6 / VCHK-05 ("/health still the blind spot") is claimed closed but is empirically false

**Status:** RESOLVED (2026-07-01). Root cause was two-fold: (1) the acceptance test's own
simulation method was stale — written against a pre-migration `_check_ephemeris()` that
never constructed a backend, so forcing failure via a direct `swe.set_ephe_path()` call no
longer matched how the migrated code actually behaves; (2) `ensure_ephemeris_files()`
carried an `@lru_cache` that masked a live environment change for the rest of the process's
lifetime. Fixed: corrected the test to use the same `SE_EPHE_PATH` + cache-clear pattern as
its `bazi` sibling; removed the caching. Re-verified independently by the orchestrator (not
trusted from the fixing agent's own claim): `SE_EPHE_PATH=~/.cache/bazi_engine/swisseph
pytest tests/test_ephemeris_attestation.py -q` → 11 passed, 0 failed. Full suite:
2618 passed, 0 failed, 58 skipped, 1 xfailed. `docs/runbooks/fq-att-01-rollout.md` carries
its own "CONTRA-1 resolution note" explaining this, dated 2026-07-01.

**What was claimed:** `bazi_engine/routers/info.py`'s `_check_ephemeris()` docstring
states this "closes the one call site that previously bypassed both the
construction-time `ensure_ephemeris_files()` guard and the `calc_ut()` return-flag
attestation check." `docs/runbooks/fq-att-01-rollout.md` (lines ~29-32, per code-reviewer)
asserts the same. The coder's own summary and the plan's T4 acceptance-evidence line both
name this as "the fix for AC-01-6 / site 4 / VCHK-05."

**What is actually true (independently reproduced by the Watcher, not merely trusted from
the code-reviewer's report):**
```
$ SE_EPHE_PATH=~/.cache/bazi_engine/swisseph pytest tests/test_ephemeris_attestation.py -q
...
FAILED tests/test_ephemeris_attestation.py::TestConstructionGuardClassEmptyDirectory::test_health_reports_unavailable_under_missing_se1_files
AssertionError: /health must report dependencies.ephemeris.status == 'unavailable' when
the ephemeris path is empty, got: {'ephemeris': {'status': 'ok', 'detail': None}, ...}
```
Root cause confirmed by direct code read: `_check_ephemeris()`
(`bazi_engine/routers/info.py:96-103`) constructs a fresh `SwissEphBackend()`, whose
`__post_init__` (`bazi_engine/ephemeris.py:107-128`) independently re-derives its own
ephemeris path via `ensure_ephemeris_files(self.ephe_path)` and then calls
`swe.set_ephe_path(path)` — unconditionally re-pointing the process-global swisseph path
back to the real, present `.se1` files, clobbering whatever the test (or an operator
simulating a real outage) forced via `swe.set_ephe_path()` directly. The health check
therefore always reports `"ok"` regardless of the actual forced-unavailable condition —
this reproduces with and without real ephemeris files present in the environment, i.e. it
is not a sandbox artifact.

**Why this is a contradiction, not a "known limitation":** this is exactly the Vision's
own named "Risk if Misbuilt": *"`/health` still the blind spot... If it is migrated on
paper (code changed) but not actually exercised under a forced-MOSEPH condition in a real
test, the single clearest safety signal in the whole system stays silently broken
(VCHK-05)."* That is precisely what has happened here — the code was changed, a test was
written, and the test **fails**, yet the shipped runbook and the code's own docstring
assert the gap is closed. The coder's own summary disclosed this as "a cross-track
blocker... traced but not fixed" but did not treat it as blocking sign-off, and did not
correct the runbook's false claim. Per the escalation-asymmetry / no-laundering rule, this
finding may not be self-downgraded to "known limitation" or "fix in a follow-up" — only
the user may accept that reframing.

**Forbidden shortcut to flag if proposed:** shipping this increment with the runbook/
docstring claim left as-is (asserting a guarantee that demonstrably does not hold), or
converting this into a "residual risk" paragraph without actually fixing `_check_ephemeris()`
or the test methodology.

**Required user decision:** either (a) fix `_check_ephemeris()`/`ensure_ephemeris_files()`
so the live `/health` probe genuinely detects a forced-unavailable ephemeris condition
(the test's own adjacent sibling, `test_bazi_fails_closed_under_missing_se1_files`, uses
the correct pattern — `SE_EPHE_PATH` env var + `ensure_ephemeris_files.cache_clear()` —
and could inform the fix), or (b) explicitly accept AC-01-6/VCHK-05 as not met in this
increment and correct the runbook/docstring to stop claiming otherwise, deferring the real
fix. Silence is not an allowed resolution.

---

## CONTRA-2 — VCHK-07 / NFR-ATT-4 concurrency guarantee for the new mechanism was never demonstrated, but the plan's own acceptance-evidence line claims it is

**Status:** RESOLVED (2026-07-01). Orchestrator judged this re-alignment-reachable (a
correction that completes already-agreed work, not a Vision-goal question) and directed
implementation rather than accepting the downgrade option. `TestFutureMechanismConcurrencySkeleton`
was un-skipped and implemented for real: concurrent `ThreadPoolExecutor` HTTP requests mix
legitimate-SWIEPH and forced-MOSEPH bodies against the real `calc_ut()`/`houses()`/`_attested`
mechanism, asserting both no false-negative (legitimate requests never wrongly 503) and no
false-positive (MOSEPH requests never wrongly succeed via cross-request `_attested` leakage).
Re-verified independently: `pytest tests/test_ephemeris_concurrency.py -q` → 2 passed.

**What was claimed:** the plan's T5 acceptance-evidence line (`docs/plans/2026-07-01-fufire-premium-verification-ci.md`,
T5 section) lists "VCHK-07" among the items T5 satisfies. `docs/traceability.md`'s
`value-check-id` row for `FQ-ATT-01` lists VCHK-07 as one of the checks this increment
must close.

**What is actually true (independently reproduced):**
```
$ SE_EPHE_PATH=~/.cache/bazi_engine/swisseph pytest tests/test_ephemeris_concurrency.py -q -v
tests/test_ephemeris_concurrency.py .s   [100%]
1 passed, 1 skipped in 0.92s
```
The one test that runs (`TestExistingLockedPathConcurrencyInvariant`) exercises the
pre-existing, unrelated `_SWE_LOCK` sidereal-reset path — not the new
`calc_ut()`/`houses()`/`_attested` mechanism this feature introduces.
`TestFutureMechanismConcurrencySkeleton::test_chosen_mechanism_is_thread_safe_under_shared_threadpool`
(`tests/test_ephemeris_concurrency.py:159-178`) remains `@pytest.mark.skip` with a body
that `raise NotImplementedError(...)` — its own file header states it "must be un-skipped
and filled in during Phase 2 once the mechanism ADR lands," and T2/T4 have both landed.

**Why this is a contradiction, not a "known limitation":** this is exactly the Vision's
own named "Risk if Misbuilt": *"Concurrency-blind guard... a guard proven correct under
`pytest -q`'s default single-threaded execution is not the same claim as one proven safe
under real concurrent traffic (VCHK-07)."* Thread-safety of the new mechanism is currently
argued only in the ADR's prose (per-instance `_attested` state, no shared mutable state) —
plausible, but not the "demonstrated, not just documented" bar VCHK-07 itself sets, and not
disclosed as an open gap in the coder's own summary.

**Required user decision:** either (a) write and run the concurrent-request test against
the real `calc_ut()`/`houses()` mechanism before this increment is considered done, or (b)
explicitly accept the prose-only ADR argument as sufficient for this increment and update
the traceability matrix to reflect that VCHK-07 was downgraded from "demonstrated" to
"argued," with the user's explicit sign-off recorded. Silence is not an allowed resolution.

---

## Finding 5 (code-reviewer, T12) — RESOLVED 2026-07-01: `/calculate/tst` new ephemeris coupling

**What was found:** `/calculate/tst` (`time_context.py`, pure civil-time/equation-of-time
math, zero Swiss Ephemeris dependency — confirmed via grep, no `ephemeris`/`swisseph`/
`calc_ut` references anywhere in its path) gained a new, unreviewed coupling: T9 wired
`quality_flags.ephemeris_mode` via `current_ephemeris_mode()`, which constructs a
throwaway `SwissEphBackend()` purely to populate that field. Unlike `bazi`/`wuxing`,
which already construct a real backend as part of their own computation (making the
same helper function's use there a redundant re-check of an already-enforced
guarantee), `tst` had no such guarantee to piggyback on — this was a genuinely new
failure mode: a previously ephemeris-file-independent endpoint could now 503 for a
reason wholly unrelated to what it computes.

**User decision (2026-07-01):** decouple `tst` from the backend check entirely. `tst`
no longer declares `quality_flags` at all — attesting an `ephemeris_mode` with zero
causal bearing on the response would itself have been a form of the "fake-attested
value" risk FQ-ATT-02 exists to close. `provenance` (ephemeris_id/tzdb_version_id)
stays, since `build_provenance()` touches no Swiss Ephemeris call and remains safe.

**Verification:** `tests/test_attestation_contract.py::TestAttestationContractTstExemption`
proves both halves (no `quality_flags` field; `provenance.ephemeris_id`/`tzdb_version_id`
still present). Full suite re-run: 2618 passed, 0 failed. `ruff`/`mypy`/OpenAPI `--check`
all clean.

---

## Non-blocking findings — all three resolved 2026-07-01

- VCHK-02 weak anchor: `tests/test_attestation_contract.py` now asserts
  `tzdb_version_id == importlib.metadata.version("tzdata")`, not merely `!= "unknown"`.
- ADR-2 mode-check deviation: **RESOLVED (2026-07-08, explicit user sign-off at the merge
  gate — user ratified the shipped `_attested`-only gate and the amended ADR text).**
  `docs/architecture/adr-fq-att-01-houses-class.md` was amended (agent-authored, 2026-07-01)
  with an "Implementation deviation from this ADR" section explaining why `_attested`-only
  gating (not a literal `self.mode == "SWIEPH"` check) is correct — the code was not changed
  to match the ADR; the ADR was corrected to match reality. Behaviorally sound (a literal
  mode check would 503 the legitimate explicit `EPHEMERIS_MODE=MOSEPH` path; VCHK-03 proves
  houses() fails closed). History: the earlier "resolved" marking was an agent
  self-downgrade of a finding that itself declared "needs explicit sign-off, not silent
  acceptance"; corrected per Watcher 2026-07-08, routed to the user, user ratified.
- Security Finding 1 (resolved_path disclosure): fixed at the source
  (`ensure_ephemeris_files()` in `bazi_engine/ephemeris.py` no longer puts `resolved_path`
  into the client-facing detail/message at all — server-log-only). Proven by
  `tests/test_security_findings.py::test_ephemeris_unavailable_503_does_not_leak_resolved_path`.

## Non-blocking findings carried forward for the user's awareness (review-required, not separately gated as CONTRA) — historical, superseded by the section above

- **VCHK-02 weak anchor** — mutation-tested independently by the Watcher: forcing
  `_detect_tzdb_version()` to return a fabricated literal (`"9999.99-FAKE-MUTATION-PROBE"`)
  left 21/22 `tests/test_attestation_contract.py` tests green, including the value-level
  "never unknown" check across every endpoint. The contract test only rules out the
  specific placeholder string `"unknown"`, not an arbitrary wrong-but-plausible value —
  the Vision's "fake-attested values" risk is not fully closed by the current test, even
  though the underlying detection code is real (not stubbed). Mutation reverted; `git
  status`/`git diff` confirm no leftover artifact from this probe.
- **ADR-2 mode-check deviation** — `SwissEphBackend.houses()` (`bazi_engine/ephemeris.py:169-207`)
  gates only on `self._attested`, not `self.mode == "SWIEPH"` as ADR-2's literal text
  states. Confirmed by direct code read. The coder's own reasoning for the deviation is
  sound (a literal mode check would 503 every house-computing endpoint under the
  already-legitimate, already-tested `EPHEMERIS_MODE=MOSEPH` explicit mode), but the
  "Accepted" ADR document itself was not amended to reflect this, so the shipped code and
  the ADR silently diverge. Needs explicit sign-off to amend the ADR text, not silent
  acceptance.
- **Security review Finding 1 (info disclosure) unresolved** — confirmed by direct code
  read: `bazi_engine/ephemeris.py:305` still puts `resolved_path` (a server-local
  filesystem path) into the client-facing `EphemerisUnavailableError` detail, and
  `bazi_engine/app.py:201-211`'s exception handler still serializes it verbatim into the
  503 body on any endpoint reachable from `SwissEphBackend` construction — now more call
  sites than before this increment (`/health`, `houses()`'s new gate). PRD §10 explicitly
  required the security-reviewer gate to make an explicit redact-or-accept call; the
  security reviewer recommended "redact" but no code change or explicit "accept as-is"
  sign-off followed. Not self-resolved.

---

## Resume cycle 2026-07-08 — post-review-diff findings (review chain re-run on Opus over 518b556..HEAD)

Context: 4 commits landed after the last recorded review gate (e4775dc, b474f3b, 3c77f94,
e5d4207). Per resume protocol they were treated as unreviewed increments; the full chain
(code-reviewer + security-reviewer + tester, all independent) re-ran and converged.

### CONTRA-1-REOPENED — b474f3b memoization re-introduced the resolved masking

**Status:** RESOLVED (2026-07-08, user decision — full revert, commit `aef4969`).
`current_ephemeris_mode()` memoization re-added the "cached files-present result masks a
live outage for the process's life" behavior one level above the deliberately removed
`ensure_ephemeris_files` lru_cache; the cache key also omitted `SE_EPHE_PATH`, and the
transit TTL-cache path performed no live re-verification on cache hits (stale `SWIEPH`
attestation after mid-process file loss — over-optimistic attestation, not silent MOSEPH;
a fresh backend raises rather than falling back). Docstring falsely cited the removed
lru_cache as precedent. User chose revert over fix-forward: marginal perf gain does not
justify re-opening a resolved contradiction. `tests/test_ephemeris_mode_cache.py` removed
with the revert (it tested the cache, which no longer exists).

### FINDING-PII-2 — e5d4207's "product-wide" DST-PII scrub was function-scoped, not product-wide

**Status:** RESOLVED (2026-07-08, commit `506adb5`). `parse_local_iso()`'s strict
round-trip raise still leaked the raw birth instant, tz name, and normalized instant into
client-facing 422 bodies — empirically reproduced via real TestClient on
`/v1/impact/active`, `/v1/experience/bootstrap`, `/v1/calculate/bazi/dayun` (the
`compute_bazi` callers that never pre-resolve). Root cause of the earlier miss: the
regression tests were fake-only (asserted on the exception object's `str()`, never the
HTTP boundary). Fixed at the source function (product-wide), guarded by new
HTTP-boundary tests (`tests/test_dst_pii_http.py`, failing-first confirmed on the
unfixed code).

### FINDING-TST-GUARD — tst attestation exemption rested on an untested invariant

**Status:** RESOLVED (2026-07-08, commit `cd978c7`). The "no Swiss-Ephemeris work on the
tst path" premise (basis of the user-approved Finding-5 exemption) had no regression
guard. Added `TestAttestationContractTstNoSwissEph`: construction spy asserts zero
`SwissEphBackend.__init__` during a real `/v1/calculate/tst` request; companion test
proves the spy is non-tautological (counts >0 on `/v1/calculate/bazi`).

### FINDING-ECHO — pre-existing format/unknown-tz 422 messages echo caller input

**Status:** RESOLVED (2026-07-08, commit `4ade317`). `time_utils.py` format-error /
unknown-timezone raises reflected the (injection-sanitized) raw
`birth_local_iso`/`tz_name` back to the client. Pre-existing, not from the reviewed diff;
user opted to scrub for consistency with the product-wide PII bar. All four echo sites
(both functions) scrubbed; HTTP-boundary + unit tests failing-first confirmed (8 failed
pre-fix → 16 passed post-fix); full suite 2636 passed.

### PRD-SYNC — AC-02-2/AC-02-3/§5.2 contradicted the shipped, user-approved tst exemption

**Status:** RESOLVED (2026-07-08, user decision — PRD amended + re-confirmed). The PRD
still literally required `quality_flags.ephemeris_mode` on `/calculate/tst` although the
exemption was formally user-decided 2026-07-01 (Finding 5). PRD text now records the
exemption explicitly; not a new decision, a text sync.
