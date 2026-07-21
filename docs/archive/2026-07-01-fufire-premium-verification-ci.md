# Concilium challenge-gate report — fufire-premium-verification-ci (WS-A increment)

Mode: `--mode=challenge` (thin, 3-role), /agileteam Phase 0.16, run against user-confirmed
canvas `docs/canvas/fufire-premium-verification-ci.canvas.md`.

## Framed subject
- Idea: harden FuFirE's attestation layer (WS-A only) so a paid response can never
  silently come from MOSEPH fallback, and every response exposes real (non-`"unknown"`)
  `ephemeris_mode`/`ephemeris_id`/`tzdb_version_id`/`house_system_fallback`.
- Underlying user goal: paying API customers get a provable guarantee that what they paid
  for (high-precision calculation) is what they received.
- Team: standard /agileteam roster, no domain additions proposed.

## Diversity disclosure
Attempted to route the Critic role through `mcp__plugin_second-opinion_codex__codex` for
real cross-model diversity (2 attempts, incl. a trivial smoke prompt) — both returned empty
output with no error, integration appears broken/misconfigured in this environment.
Fell back to a Claude subagent for Critic. **All three round-1 positions ran on Claude;
correlated blind spots are NOT covered — treat this as a structured single-model critique,
not true cognitive diversity.**

## Round 1 positions
- **Challenger** (concilium-skeptic, requirement lens): pull-go/sharpen. Requirement is
  legitimate but customer-harm framing is asserted, not evidenced — no ticket/SLA/churn
  signal cited for any customer beyond the originating BFF. WS-A alone is not inert: it
  converts an unknown risk into a bounded, provable one.
- **Advisor** (concilium-tech-arbiter, build+distribution lens): pull-pivot on mechanism.
  `assert_no_moseph_fallback` already exists and is centralizable. Proposed alternative:
  wrap `swe.calc_ut`/`houses`/`fixstar` once at the `pyswisseph` import boundary in
  `ephemeris.py`'s init instead of per-call-site rewrite + AST lint (one control point vs.
  N wrapped sites + a fragile static check). Flagged as unverified whether any downstream
  consumer actually reads `quality_flags` today — do-not-claim until checked.
- **Critic** (concilium-skeptic, concept+market lens): pull-pivot on process weight.
  Correctness fix should ship, but load-bearing assumption "attestation is a premium-tier
  feature" is unexamined and likely false (correctness bugs aren't tier differentiators).
  Proposed alternative: ship as a lean fix (1 coder + 1 reviewer), skip the heavyweight
  10-role process.

## Orchestrator fact-check (settles the live disagreement with evidence, not more debate)
Ran `grep -rn "swe\.\(calc_ut\|calc\|houses\|fixstar\)" bazi_engine/` excluding
`ephemeris.py`: **4 unguarded call sites bypass the wrapper across 3 files** —
`western.py:64` (`calc_ut`), `western.py:93` (`houses`, no comparable flag mechanism —
confirms FQ-A1's two-class distinction is real, not theoretical), `transit.py:131`
(`calc_ut`), `routers/info.py:90` (`calc_ut`, health-check). Small and bounded (supports
Critic's "not sprawling"), but real, multi-file, and touches a live customer-facing
endpoint (`western.py`) plus the health-check path — not zero-risk busywork, and the
`houses()` no-flag gap is a genuine design problem the wrapper-vs-monkeypatch choice must
resolve either way.

## Trajectory
- **Resonance:** all three agree the underlying mechanism (`assert_no_moseph_fallback`)
  already exists and this is coverage-completion, not new capability.
- **Repulsion:** Critic wants to downgrade process weight; Challenger's "not inert" finding
  and the confirmed multi-file, response-contract-changing scope argue the opposite.
- **Instability (now resolved by evidence):** Critic's "lean bugfix" framing depended on
  the gap being trivial-and-contained; the real count (4 sites / 3 files / 1 no-flag class)
  is small but not trivial — response-contract tightening (Optional→required) plus a
  design decision on the flag-less `houses()` path is exactly what code-reviewer +
  production-validator + the OpenAPI-drift check exist to catch.

## Recommendation: SHARPEN
The requirement and team survive the challenge. Concrete changes adopted going into the
PRD:
1. **Drop "premium tier" framing for WS-A.** This is a baseline correctness/reliability
   guarantee for all paying customers, not a tier differentiator — reserve "premium"
   language for the later accuracy-threshold work (WS-C/FQ-030), where it means a real
   numeric tier.
2. **Evaluate Advisor's import-boundary-wrap alternative** alongside the source doc's
   per-call-site `calc_checked()` + AST-lint approach during PRD/planner architecture —
   not pre-decided.
3. **Use the fact-checked scope, not speculation:** FQ-A1 touches exactly
   `western.py` (calc_ut + houses), `transit.py` (calc_ut), `routers/info.py` (calc_ut) —
   plus whatever `bazi_rules.py`/other modules the same grep needs to be re-run against
   during actual implementation (this was a scoping check, not the full pre-implementation
   discovery FQ-A1 itself still requires).
4. **Do not claim downstream consumers read `quality_flags`** without verification — kept
   as an evidence-needed / open item into the PRD.
5. Team stays as the standard /agileteam roster (no downgrade to a lean 2-role fix) — the
   response-contract change and the flag-less `houses()` design decision are exactly what
   the review/validation gates exist for.

No round 2 collision run: the remaining tension (process proportionality) was resolved by
direct evidence (the grep above) rather than needing more argument between the same three
Claude-only positions — consistent with "stop when positions stabilise."

**User steer:** presented to user; user said "proceed" — adopting the sharpen points above
into the PRD without further amendment rounds.
