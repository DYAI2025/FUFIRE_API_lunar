# Gap Report: BC Engine V2 vs BaZodiac Spec (1.0.0-rc0)

Scope:
- Compare current BC Engine V2 codebase against SSOT under ./spec (contract-first).
- Status tags: DONE / PARTIAL / MISSING / CONFLICTS_SPEC

## Inventory Matrix

| Area | Spec requirement | V2 implementation | Status | Priority | Evidence |
|---|---|---|---|---|---|
| /validate endpoint | Contract-bound /validate with Draft-07 schemas, error codes, evidence | No /validate endpoint exists | MISSING | P0 | bazi_engine/app.py |
| Contract schemas in repo | spec/schemas/*.schema.json are SSOT | No spec/ folder (pre-change) | MISSING | P0 | (created in this iteration under spec/) |
| Ruleset standard_bazi_2026 | Canonical ruleset loaded/validated | No ruleset loader; hardcoded logic | MISSING | P0 | bazi_engine/bazi.py (hardcoded year/month/hour rules) |
| Anchor gating | anchor_verification != verified => policy-gated behavior via /validate | No anchor verification concept | MISSING | P0 | n/a |
| Determinism knobs | now_utc_override for expiry tests; no time defaults | No now_utc_override; runtime uses datetime.now in app | MISSING | P0 | bazi_engine/app.py uses datetime.now/time.time |
| No implicit network calls | Offline modes forbid downloads; network guard strict | Ephemeris auto-download on startup via urllib | CONFLICTS_SPEC | P0 | bazi_engine/ephemeris.py ensure_ephemeris_files() |
| RefData manifest + provenance | Explicit refdata_manifest + verification policy | No refdata manifest subsystem | MISSING | P0 | n/a |
| DST fold/gap error codes | Distinguish ambiguous vs nonexistent local time | parse_local_iso does strict round-trip, but no codes | PARTIAL | P1 | bazi_engine/time_utils.py parse_local_iso |
| TimeModel chain UTC->UT1->TT + TLST | Evidence of time scales + quality flags | Uses SwissEph deltat; no UT1/EOP model; no TLST | PARTIAL | P1 | bazi_engine/bazi.py (delta_t), fusion.py (approx TST) |
| Branch coordinate convention | SHIFT_BOUNDARIES canonical; forbid mixing | No explicit convention; implicit logic differs | MISSING | P0 | bazi_engine/bazi.py hour_branch_index (civil) |
| TLST hour boundary rule | Hour branch derived from TLST (half-open intervals) | Uses civil local hour rounding | CONFLICTS_SPEC | P0 | bazi_engine/bazi.py hour_branch_index |
| Soft kernel weights | sum(weights)=1, symmetric; config-driven kernel | No branch kernel weights | MISSING | P1 | n/a |
| Harmonics/phasors | harmonic_phasor features with degeneracy handling | No harmonic features | MISSING | P2 | n/a |
| Forbidden convention mixing detector | Error INCONSISTENT_BRANCH_ORIGIN_FOR_SHIFTED_LONGITUDES | No detector | MISSING | P0 | n/a |
| Error catalog | ErrorCode enum per contract | No error catalog | MISSING | P0 | n/a |

## Stop-the-line Conflicts (P0)

1. Implicit network downloads in ephemeris bootstrap (must be removed or guarded).
2. Hour pillar computed from civil clock, not TLST (spec conflict).
3. No /validate contract endpoint (core deliverable missing).

## Follow-up: Epics mapping (from spec/addenda + patch-values)

- E0: /validate skeleton + error catalog + evidence structure
- E1-mini: RefData contract + network guard
- E2: TimeModel + TLST + DST fold/gap codes
- E4: Branch mapping canonical + forbidden mixing detection
- E3-lite: Ruleset loader standard_bazi_2026 + hidden stems
- E5a/E5b: FeatureExtractor + kernel + harmonics
