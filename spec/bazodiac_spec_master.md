# BaZodiac Spec Master (SSOT)

spec_version: 1.0.0-rc0
status: FROZEN (contract-first)

This file is the Single Source of Truth (SSOT) for the BaZodiac Engine normative text.
JSON Schemas and rulesets live under spec/schemas and spec/rulesets.

---

## Base Specification (F1)

BaZodiac Engine Specification (Ready for Iteration Planning)

engine_spec_id: bazodiac-engine-spec
spec_version: 1.0.0-draft
ascii_only: true
deterministic: true

This specification defines a deterministic, reproducible engine that fuses:

BaZi as discrete cyclic algebra (Z10 stems, Z12 branches, Z60 sexagenary),

Western astrology as continuous ecliptic geometry (0..360 deg),
into a single, testable model with explicit conventions, versioned rulesets, and verifiable reference data packs.

1) Normative language

The key words MUST, MUST NOT, SHOULD, SHOULD NOT, MAY are to be interpreted as requirements.

1) Executive summary

The BaZodiac Engine is a modular computation pipeline that normalizes time/space inputs, computes western ephemeris positions and BaZi pillars, extracts typed features, applies formal bridge operators (hard segments, soft kernels, harmonic phasors), and generates optional deterministic interpretations derived strictly from those features. The engine enforces quadrant-safe angle arithmetic (atan2), explicit epoch/precession inputs, and a rigorous reference-data integrity subsystem (ephemeris, leap seconds, EOP, tzdb) enabling offline reproducibility. Ambiguities such as "Ingress vs Apex" are resolved via explicit configuration flags and validation checks that forbid mixed conventions.

1) Scope and non-goals
In scope

Deterministic computation of:

time scales (UTC/UT1/TT), TLST (true local solar time),

western body longitudes (and optional lat/RA/Dec),

BaZi pillars (at minimum branches; stems via ruleset),

fusion features via defined operators,

validation reports with failure modes and uncertainty diagnostics,

optional deterministic interpretation outputs.

Non-goals

No claims of scientific truth for metaphysical assertions.

No invented ephemerides, historical anchors, or school-specific constants without explicit ruleset data.

No implicit downloads at runtime in offline modes.

No hidden transformation steps.

1) High-level pipeline (PS+)

Inputs -> Normalization -> Transform chain -> Feature extraction -> Fusion operators -> Interpretation -> Output + Validation

Modules (replaceable components)

InputValidator

RefDataManager (resolve + verify data packs)

TimeModel (UTC/UT1/TT/TLST)

EphemerisProvider (positions)

CoordTransform (eq <-> ecl, atan2-safe)

BaZiCalculator (ruleset-driven)

WestCalculator (derived western features)

FeatureExtractor (typed, reproducible)

BridgeOperators (hard/soft mapping)

Harmonics (phasor embedding)

FusionComposer (merge fusion features)

InterpretationEngine (strictly feature-derived)

Validator (/validate invariants, property tests, failure modes)

1) Core definitions and conventions
4.1 Angles and time domains

Angles in degrees unless stated.

lambda_deg in [0, 360) : ecliptic longitude

alpha_deg in [0, 360) : right ascension

delta_deg in [-90, 90] : declination

TLST_hours in [0, 24)

4.2 Safe angle operators (MUST be used everywhere)

wrap360(x) := x mod 360 -> [0, 360)

wrap180(x) := wrap360(x + 180) - 180 -> (-180, 180]

delta_deg(a,b) := abs(wrap180(a - b)) -> [0, 180]

atan2(y,x) MUST be used for quadrant safety; arctan(y/x) MUST NOT be used.

4.3 Interval convention (branch/sign segmentation)

Default: half-open intervals [a, b).
Example: Zi sector [255, 285) means:

284.999 -> Zi

285.000 -> Chou

This convention MUST be explicitly stated in config: interval_convention="HALF_OPEN".

1) Configuration and versioning
5.1 EngineConfig (MUST be echoed in outputs)
{
  "engine_version": "1.0.0",
  "parameter_set_id": "pz_YYYY_MM_core",
  "deterministic": true,

  "epoch_id": "ofDate|J2000|custom",
  "zodiac_mode": "tropical|sidereal",
  "ayanamsa_id": "MISSING_if_sidereal",
  "precession_model_id": "MISSING_or_explicit",
  "obliquity_model_id": "MISSING_or_explicit",

  "time_standard": "CIVIL|LMT|TLST",
  "dst_policy": "error|earlier|later",

  "interval_convention": "HALF_OPEN",

  "branch_coordinate_convention": "SHIFT_BOUNDARIES|SHIFT_LONGITUDES",
  "phi_apex_offset_deg": 15.0,
  "zi_apex_deg": 270.0,
  "branch_width_deg": 30.0,

  "month_boundary_mode": "JIEQI_CROSSING|APEX_SEGMENTS",
  "month_start_solar_longitude_deg": 315.0,

  "fusion_mode": "hard_segment|soft_kernel|harmonic_phasor",
  "kernel": { "type": "von_mises", "kappa": 4.0 },
  "harmonics_k": [2,3,4,6,12],
  "pillar_weights": { "year": 1.0, "month": 1.0, "day": 1.0, "hour": 1.0 },
  "planet_weights": { "Sun": 1.0, "Moon": 1.0 },

  "bazi_ruleset_id": "standard_bazi_v1",
  "interpretation_ruleset_id": "interp_core_v1",

  "refdata": {
    "refdata_pack_id": "refpack-YYYY-MM-DDTHHMMZ",
    "refdata_mode": "BUNDLED_OFFLINE|LOCAL_MIRROR|PROVIDER_BACKED",
    "refdata_root_path": "/path/to/refdata/live",
    "allow_network": false,
    "ephemeris_id": "JPL_DE440|JPL_DE441|JPL_DE442|SwissEph_x.y",
    "tzdb_version_id": "tzdataYYYYx",
    "leaps_source_id": "IERS_leap-seconds.list|tzdb_leapseconds",
    "eop_source_id": "IERS_finals2000A|null",
    "verification_policy": {
      "tzdb_gpg_required": true,
      "ephemeris_hash_required": true,
      "eop_redundancy_required": false,
      "leaps_expiry_enforced": true
    }
  }
}

1) Rulesets (BaZi definitions, including hidden stems)
6.1 BaZiRuleset object (MUST be versioned, no implicit constants)
{
  "ruleset_id": "standard_bazi_v1",
  "ruleset_version": "1.0.0",

  "stem_order": ["Jia","Yi","Bing","Ding","Wu","Ji","Geng","Xin","Ren","Gui"],
  "branch_order": ["Zi","Chou","Yin","Mao","Chen","Si","Wu","Wei","Shen","You","Xu","Hai"],

  "day_cycle_anchor": {
    "anchor_type": "JDN|DATE_ISO",
    "anchor_jdn": "MISSING_if_not_JDN",
    "anchor_date_iso": "MISSING_if_not_DATE_ISO",
    "anchor_sexagenary_index": "MISSING_0_to_59"
  },

  "day_change_policy": "midnight|zi_hour_start",

  "year_boundary": {
    "mode": "solar_longitude_crossing",
    "solar_longitude_deg": 315.0
  },

  "month_boundary": {
    "mode": "JIEQI_CROSSING|APEX_SEGMENTS",
    "month_start_solar_longitude_deg": 315.0,
    "step_deg": 30.0
  },

  "month_stem_rule": { "mode": "five_tigers|table" },
  "hour_stem_rule": { "mode": "five_rats|table" },

  "hidden_stems": {
    "mode": "table",
    "ordering": "principal_central_residual",
    "branch_to_hidden": {
      "Zi":   ["Gui"],
      "Chou": ["Ji","Gui","Xin"],
      "Yin":  ["Jia","Bing","Wu"],
      "Mao":  ["Yi"],
      "Chen": ["Wu","Yi","Gui"],
      "Si":   ["Bing","Geng","Wu"],
      "Wu":   ["Ding","Ji"],
      "Wei":  ["Ji","Yi","Ding"],
      "Shen": ["Geng","Ren","Wu"],
      "You":  ["Xin"],
      "Xu":   ["Wu","Xin","Ding"],
      "Hai":  ["Ren","Jia"]
    }
  },

  "hidden_stems_weighting": {
    "mode": "none|role_weights|percent_table",
    "role_weights": { "principal": 1.0, "central": 0.5, "residual": 0.3 },
    "percent_table": {
      "default_1": [1.0],
      "default_2": [0.7, 0.3],
      "default_3": [0.6, 0.3, 0.1]
    }
  }
}

6.2 Ruleset requirements

If day_cycle_anchor is missing and no bazi_pillars_override is provided, /validate MUST return error MISSING_DAY_CYCLE_ANCHOR.

Hidden stems MUST contain 1..3 stems per branch, ordered according to ordering.

Weighting MUST NOT be assumed unless hidden_stems_weighting.mode != "none".

1) Reference data packs (offline integrity subsystem)
7.1 RefDataPack manifest (single source of truth)

refdata_root_path/live/manifest.json MUST exist in offline modes.

{
  "pack_id": "refpack-YYYY-MM-DDTHHMMZ",
  "created_at_utc": "YYYY-MM-DDTHH:MM:SSZ",
  "manifest_hash_sha256": "sha256_of_manifest_contents",
  "artifacts": [
    {
      "name": "ephemeris/deXXX.bsp",
      "logical_id": "JPL_DE442",
      "source_url": "https://...",
      "hashes": { "sha256": "..." },
      "aux_verification": { "vendor_md5_ok": true }
    },
    {
      "name": "eop/finals2000A.all",
      "logical_id": "IERS_finals2000A",
      "hashes": { "sha256": "..." },
      "sanity_checks": { "ranges_ok": true, "contains_predictions": true }
    },
    {
      "name": "timescales/leap-seconds.list",
      "logical_id": "IERS_leap-seconds.list",
      "hashes": { "sha256": "..." },
      "metadata": { "expires_utc": "YYYY-MM-DDTHH:MM:SSZ" }
    },
    {
      "name": "tzdb/tzdataYYYYx.tar.gz",
      "logical_id": "tzdataYYYYx",
      "gpg": { "signature_ok": true, "signing_key_fingerprint": "..." }
    }
  ]
}

7.2 RefDataManager behavior

In refdata_mode in {BUNDLED_OFFLINE, LOCAL_MIRROR}:

allow_network MUST be false.

Any network access attempt MUST fail with REFDATA_NETWORK_FORBIDDEN.

Verification:

tzdb: GPG signature MUST verify if tzdb_gpg_required=true.

ephemeris: sha256 MUST match manifest if ephemeris_hash_required=true.

leap seconds: expires_utc MUST be in the future if leaps_expiry_enforced=true.

EOP: MUST run sanity-range checks; if redundancy is required, compare at least two sources during pack build (sidecar), not at runtime.

7.3 Sidecar pattern (LOCAL_MIRROR)

Sidecar downloads into staging/, verifies, then atomic swap staging -> live.

Engine runtime reads only live/.

1) Mapping functions (formal math)
8.1 f_time (Local -> UTC -> UT1/TT -> LMST/TLST)

Inputs:

local_datetime, tz_id or tz_offset_sec, geo_lon_deg, dst_policy

refdata: tzdb + leap seconds + optional EOP

optional overrides: DUT1_sec, DeltaT_sec, EoT_min

Outputs:

utc_dt, ut1_dt (optional), tt_dt, jd_ut, jd_tt

LMST_hours, TLST_hours (if requested or diagnostics enabled)

provenance + staleness flags

Algorithm (deterministic):

Resolve local -> UTC using tzdb and dst_policy.

UT1:

If DUT1 override provided: UT1 = UTC + DUT1.

Else if EOP available: DUT1 = interpolate(UT1-UTC from finals2000A).

Else UT1 missing (flag).

TT:

If leap seconds file valid: TT = UTC + (TAI-UTC) + 32.184s

Else if DeltaT override provided and UT1 exists: TT = UT1 + DeltaT

Else TT missing (error in strict mode).

LMST:

If UT1 exists: LMST = (UT1_hours + geo_lon_deg/15) mod 24

Else LMST missing.

TLST:

If EoT_min override provided: use it.

Else compute EoT by chosen method (approx_noaa or ephemeris-based) and mark provenance.

TLST = (LMST + EoT/60) mod 24

Provide distance_to_hour_boundary_minutes for hour classification.

8.2 f_coord (equatorial <-> ecliptic)

Given obliquity epsilon_deg from obliquity_model_id at epoch_id.

Equatorial -> ecliptic:

beta = asin( sin(delta)*cos(eps) - cos(delta)*sin(eps)*sin(alpha) )

lambda = atan2( sin(alpha)*cos(eps) + tan(delta)*sin(eps), cos(alpha) )

lambda = wrap360(rad2deg(lambda))

Ecliptic -> equatorial:

delta = asin( sin(beta)*cos(eps) + cos(beta)*sin(eps)*sin(lambda) )

alpha = atan2( sin(lambda)*cos(eps) - tan(beta)*sin(eps), cos(lambda) )

alpha = wrap360(rad2deg(alpha))

8.3 f_branch (Ingress vs Apex ambiguity resolved)

Define:

width = branch_width_deg

half = width / 2

B0 = zi_apex_deg - half

Two conventions (MUST NOT be mixed):

K1 SHIFT_BOUNDARIES (recommended default):

branch(lambda) = floor( wrap360(lambda - B0) / width )

K2 SHIFT_LONGITUDES:

lambda_apex = wrap360(lambda - phi_apex_offset_deg)

B0_apex = wrap360(B0 - phi_apex_offset_deg)

branch(lambda) = floor( wrap360(lambda_apex - B0_apex) / width )

Validator MUST error if SHIFT_LONGITUDES is configured but B0_apex is not used.

8.4 f_bazi (pillars)

Inputs:

time outputs (UTC/TT/TLST), sun longitude lambda_sun_deg

BaZiRuleset or ruleset_id

month_boundary_mode, day_change_policy, time_standard

Outputs:

pillars: year/month/day/hour with stem_index, branch_index, sexagenary_index (when available)

hidden stems per pillar branch

boundary diagnostics: distance to boundary, unstable flags

Rules:

Year branch/stem via year boundary mode (solar longitude crossing) or ruleset-provided method.

Month branch:

JIEQI_CROSSING: compute crossing instants for month_start_solar_longitude_deg + 30*k, find interval containing birth instant.

APEX_SEGMENTS: month_branch = f_branch(lambda_sun_deg); note stems may require explicit mapping (MISSING unless ruleset defines month index mapping).

Day pillar:

sexagenary_index = (JDN_effective - anchor_jdn + anchor_index) mod 60

effective day depends on day_change_policy:

midnight: civil midnight in chosen time standard reference

zi_hour_start: day rolls at start of Zi hour (23:00 in effective time standard)

Hour branch:

Use T_hours from chosen time_standard:

CIVIL: local civil hours

LMT: longitude mean time hours

TLST: TLST hours (recommended)

hour_branch = floor( ((T_hours + 1) mod 24) / 2 )

Month stem rule:

five_tigers (formula form): month_stem = (year_stem*2 + 2 + month_index) mod 10

or table mode

Hour stem rule:

five_rats (formula form): hour_stem = (day_stem*2 + hour_branch) mod 10

or table mode

Hidden stems:

list from ruleset mapping

optional weights applied per ruleset weighting mode

8.5 f_west (western positions)

Inputs:

TT, ephemeris_id, epoch_id, zodiac_mode
Outputs:

for each body: lambda_deg (+ optional beta, speed, retro)

derived: sign_index, degree_in_sign, half_sign_flag

provenance: ephemeris_id, file hash, verified

8.6 Bridge operators

Hard segment mapping:

planet_branch[p] = f_branch(lambda_p)

Soft kernel weighting (circular):

centers_b = wrap360(zi_apex_deg + width*b) for b in 0..11

weights_b(lambda) proportional to K(delta_deg(lambda, centers_b))

von Mises: K(delta) = exp(kappa * cos(delta_rad))

normalize sum(weights)=1

8.7 Harmonic phasor fusion (optional but recommended)

Choose harmonics set H = harmonics_k.

theta_branch_center(b) = wrap360(zi_apex_deg + width*b)

BaZi phasor:

R_k = sum_{pillars i} w_i *exp(i* k * deg2rad(theta_i))

West phasor:

O_k = sum_{planets p} v_p *exp(i* k * deg2rad(lambda_phase_p))
Where lambda_phase_p MUST be explicitly chosen:

either raw lambda_p, or apex-shifted lambda_apex_p, but MUST be declared in config: harmonic_phase_convention.

Fusion features:

I_k = |R_k + O_k|^2

X_k = Re(conj(R_k) * O_k)

A_k = X_k / (|R_k|*|O_k| + eps_norm) in [-1,1]

Degeneracy:

if |R_k|==0 or |O_k|==0 then A_k=0 and flag harmonic_degenerate=true

1) Feature extraction (typed, deterministic)

FeatureVector MUST include:

engine_version, parameter_set_id, refdata_pack_id, ruleset_id, epoch_id, zodiac_mode

raw values:

time scales, TLST, EoT provenance, uncertainties

positions (selected bodies)

pillars indices + hidden stems

derived:

branch mapping (hard) and/or branch weights (soft)

harmonic features if enabled

boundary distances and unstable flags

1) Interpretation layer (strictly derived)
Principle

Every statement MUST reference concrete feature keys (feature_refs).

No additional constants without being in interpretation_ruleset.

InterpretationRuleset (outline)
{
  "interpretation_ruleset_id": "interp_core_v1",
  "version": "1.0.0",
  "thresholds": {
    "harmonic_pos": 0.6,
    "harmonic_neg": -0.6,
    "boundary_warn_deg": 0.1,
    "boundary_warn_min": 2.0
  },
  "rules": [
    {
      "id": "branch_unstable_warning",
      "if": { "feature": "month_branch_unstable", "equals": true },
      "then": { "template": "Month branch near boundary; classification unstable.", "refs": ["month_branch_unstable","month_branch_boundary_distance_deg"] }
    }
  ]
}

1) Validation and failure modes
11.1 Invariants (MUST)

Angle invariants:

wrap360 in [0,360), wrap180 in (-180,180], delta in [0,180]

Time invariants:

TLST_hours in [0,24)

if time_standard=TLST and EoT missing -> tlst_quality must be degraded

Branch convention invariants:

SHIFT_LONGITUDES MUST use B0_apex; mixing is forbidden:

error: INCONSISTENT_BRANCH_ORIGIN_FOR_SHIFTED_LONGITUDES

Ruleset invariants:

hidden stems 1..3 per branch, ordered, unique

if weighting enabled: weights positive, normalized per scheme

Refdata invariants:

allow_network false in offline modes

tzdb signature ok if required

ephemeris sha256 ok if required

leap seconds file not expired if enforced

11.2 Failure modes (MUST enumerate in validation report)

DST ambiguous local time (fold)

DST gap (non-existent local time)

tz_id invalid

leap seconds file expired

EOP missing or stale (if UT1 required)

predicted EOP region used (warning)

ephemeris file missing / hash mismatch

classification near boundary with uncertainty > distance

11.3 Error budget policy

Each stage must report typical/max uncertainty when known, else MISSING:

civil->UTC: up to 3600s risk around DST if policy not applied

UTC->TT: invalid if leap seconds missing/expired

UT1 and EOP: predicted region adds uncertainty (flag)

ephemeris: provider dependent; must surface uncertainty metadata if available

discretization: classification_unstable if sigma >= boundary distance

1) API specification
12.1 Endpoints (minimum set)

POST /chart

POST /features

POST /fusion

POST /interpretation

POST /validate

GET /refdata/status

POST /refdata/validate

POST /refdata/switch (admin, LOCAL_MIRROR only)

12.2 Common request schema (OpenAPI-like)
{
  "engine_config": { ...EngineConfig... },
  "birth_event": {
    "local_datetime": "YYYY-MM-DDTHH:MM:SS",
    "tz_id": "Europe/Berlin",
    "tz_offset_sec": null,
    "dst_policy": "earlier|later|error",
    "geo_lon_deg": 13.4050,
    "geo_lat_deg": 52.5200
  },
  "bodies": ["Sun","Moon","Mercury","Venus","Mars","Jupiter","Saturn"],
  "positions_override": null,
  "bazi_pillars_override": null,
  "include_interpretation": true,
  "include_validation": true
}

12.3 /chart response schema (core)
{
  "engine_version": "1.0.0",
  "parameter_set_id": "pz_YYYY_MM_core",
  "refdata": { ...RefDataProvenance... },

  "time_scales": {
    "utc": "...Z",
    "ut1": "...Z|null",
    "tt":  "...Z|null",
    "jd_ut": 0.0,
    "jd_tt": 0.0,
    "lmst_hours": 0.0,
    "tlst_hours": 0.0,
    "eot_min": 0.0,
    "quality": { "ut1": "ok|missing", "tt": "ok|missing", "tlst": "ok|degraded|missing" },
    "staleness_flags": { "tzdb_stale": false, "leaps_expired": false, "eop_stale": false, "eop_predicted_region": false }
  },

  "positions": [ ...BodyPosition... ],
  "bazi": { "ruleset_id": "...", "pillars": [ ... ], "hidden_stems_by_pillar": { ... } },

  "features": { "features": { ... }, "provenance": { ... } },
  "fusion": { "mode": "soft_kernel", "features": { ... } },

  "interpretation": { "statements": [ ... ], "explain": { ... } },

  "validation": { "ok": true, "warnings": [ ... ], "errors": [ ... ], "assertions": [ ... ] }
}

1) Validation suite (test vectors + property tests)
13.1 Synthetic test vectors (MUST)

TV1 Branch boundary (zi_apex=270, width=30):

lambda=275 -> Zi (0)

lambda=285 -> Chou (1)

lambda=284.999 -> Zi

lambda=254.999 -> Hai (11)

TV2 Convention equivalence:

For random lambda:

branch_SHIFT_BOUNDARIES(lambda) == branch_SHIFT_LONGITUDES(lambda)
(only if SHIFT_LONGITUDES implemented correctly)

TV3 Forbidden mixing detector:

Configure SHIFT_LONGITUDES but do not shift B0 -> validate returns error INCONSISTENT_BRANCH_ORIGIN...

TV4 TLST hour branch:

TLST=22.999 -> Hai (11)

TLST=23.000 -> Zi (0)

TLST=0.999 -> Zi

TLST=1.000 -> Chou (1)

TV5 Soft kernel symmetry:

lambda exactly between Zi center 270 and Chou center 300 (lambda=285):

weights[Zi] == weights[Chou] for symmetric kernel

TV6 Hidden stems mapping correctness:

for each branch, assert mapping list equals ruleset list

TV7 Refdata policy:

offline mode + allow_network true -> error REFDATA_NETWORK_FORBIDDEN

tzdb_gpg_required true but signature false -> error

13.2 Property tests (MUST)

wrap invariants

periodicity (lambda + 360n)

kernel normalization sum(weights)=1

harmonic degeneracy flags

leap seconds expiry enforcement

1) Limitations and MISSING items (explicit)

MISSING unless provided by ruleset or provider:

day_cycle_anchor anchor_jdn/anchor_index for sexagenary day computation

sidereal ayanamsa definitions if zodiac_mode="sidereal"

precise UT1/EOP usage requirements (only needed for strict earth-fixed transforms/houses)

ephemeris uncertainty metadata unless provider supplies it

month stem derivation for APEX_SEGMENTS unless ruleset defines month_index mapping

1) Iteration planning backlog (ready-to-plan epics)
Epic E0: Spec compliance harness

Acceptance:

/validate exists and runs invariants + failure modes

All responses echo engine_version, parameter_set_id, refdata_pack_id, ruleset_id

Epic E1: RefData subsystem (offline packs)

Deliverables:

RefDataManager + manifest parsing

Verification: tzdb GPG (optional in dev), ephemeris sha256, leaps expiry

/refdata/status + /refdata/validate
Acceptance:

offline mode never performs network I/O

pack provenance in every /chart response

Epic E2: TimeModel with TLST

Deliverables:

CIVIL/LMT/TLST computation

EoT override + approx mode with provenance

boundary distance diagnostics for hour bins
Acceptance:

TV4 passes, dst ambiguity handled by dst_policy

Epic E3: BaZiRuleset integration (stems, branches, hidden stems)

Deliverables:

ruleset loader + validation

day_cycle_anchor required or override path

hidden stems output + optional weighting
Acceptance:

TV6 passes; missing anchor yields explicit error

Epic E4: Branch mapping conventions (offset dualism fixed)

Deliverables:

SHIFT_BOUNDARIES default + SHIFT_LONGITUDES optional

mixing detector in validator
Acceptance:

TV2 and TV3 pass

Epic E5: Bridge operators + Harmonics

Deliverables:

hard segment mapping, soft kernel, harmonic phasors

fusion feature outputs + degeneracy flags
Acceptance:

TV5 passes; harmonic features deterministic

Epic E6: Interpretation ruleset (optional)

Deliverables:

interpretation_ruleset loader

statements with feature_refs
Acceptance:

every statement references concrete feature keys; no free text

If you want, I can also provide:

a canonical standard_bazi_v1.json with MISSING placeholders clearly marked,

a minimal refpack_manifest.json template,

and an /validate error code catalog (stable identifiers for clients).

---

## Normative Patch: PATCH-MATH-002 (Mapping Functions + Extensions)

PATCH: Mathematical Core Clarifications + Extensions

patch_id: PATCH-MATH-002
scope: master_spec.mapping_functions + bazi.ruleset_interfaces + tests
breaking_change: false (adds optional features + clarifies conventions)

1) Spec Text Patch (normativ) fuer spec/bazodiac_spec_master.md

## Mapping Functions (Normative)

### 1. Ingress vs Apex: Definitionen und Konventionen

We distinguish:

- Ingress convention: sector boundaries at multiples of 30 deg (0,30,60,...).
- Apex convention: sector centers at multiples of 30 deg, with boundaries +/- 15 deg.

The engine MUST declare a single branch coordinate convention:

- SHIFT_BOUNDARIES (recommended default): keep longitudes unchanged; shift the branch boundaries.
- SHIFT_LONGITUDES (optional): shift longitudes by phi_apex_offset_deg; boundaries stay at canonical boundaries.

Mixing these conventions in one computation graph is forbidden and MUST trigger
INCONSISTENT_BRANCH_ORIGIN_FOR_SHIFTED_LONGITUDES.

### 2. Month Branch from Solar Longitude (Apex/ZhongQi-consistent)

Parameters:

- zi_apex_deg = 270.0 (tropical, ofDate)  # default
- branch_width_deg = 30.0
- half_width_deg = 15.0
- interval_convention = HALF_OPEN

Definition (SHIFT_BOUNDARIES):
Let the Zi month be centered at zi_apex_deg.
Then Zi month boundaries are:
  [zi_apex_deg - half_width_deg, zi_apex_deg + half_width_deg)
i.e. [255, 285) when zi_apex_deg=270.

Month branch index b_month is:
  b_month = floor( wrap360(lambda_sun_deg - (zi_apex_deg - half_width_deg)) / branch_width_deg )
with b_month in {0..11} and b_month=0 meaning Zi.

This is equivalent to:

- Zi sector: [255, 285)
- Chou: [285, 315)
- ...
and resolves the ingress-vs-apex ambiguity deterministically.

Note:
If month_boundary_mode = JIEQI_CROSSING, the engine MUST use solar-term crossings
as boundaries and MUST still output the implied apex center and distances-to-boundary
for diagnostics (stability).

### 3. Hour Branch as Solar-Time Phase (TLST) and as Solar Hour Angle (H)

Hour branch classification MUST be based on TLST (True Local Solar Time) when available.
We define two equivalent views:

(A) TLST binning (canonical):
  hour_branch = floor( ((TLST_hours + 1) mod 24) / 2 )
with hour_branch=0 meaning Zi (23:00-01:00), HALF_OPEN intervals.

(B) Solar-time phase angle:
Define gamma_deg = wrap360( 15 * TLST_hours )
Interpret TLST midnight as gamma_deg = 0 deg.
Then Zi sector is:
  [345, 15) in circular sense, which is implemented as:
  hour_branch = floor( wrap360(gamma_deg - 345) / 30 )

The engine MUST expose (for explainability and debugging):

- TLST_hours
- gamma_deg
- distance_to_hour_boundary_minutes

Optional: solar hour angle H (astronomy convention):
  H_deg = wrap180( 15 * (TLST_hours - 12) )
This is equivalent information; using H_deg is allowed, but the implementation MUST
remain consistent with HALF_OPEN intervals and the Zi=23-01 bin definition.

### 4. Jupiter / Tai Sui: optional fusion feature channel (NOT a silent Year-Pillar change)

The BaZi Year Pillar remains solar-year ruleset-based (e.g., LiChun boundary).
Separately, the fusion layer MAY expose an additional "annual-cycle" feature channel:

annual_cycle_mode:

- NONE
- PHYSICAL_JUPITER_LONGITUDE
- VIRTUAL_TAI_SUI (requires explicit ruleset definition; may be MISSING)

If PHYSICAL_JUPITER_LONGITUDE:

- compute lambda_jupiter_deg via ephemeris provider
- map to branches using the same branch mapping operator as other bodies
- record provenance: ephemeris_id, time_scale_used, zodiac_mode, epoch_id

If VIRTUAL_TAI_SUI:

- engine MUST require explicit ruleset definition of TaiSui mapping.
- if missing, /validate MUST emit MISSING_TAI_SUI_RULESET and disable this channel.

Rationale:
This preserves BaZi semantics while allowing a mathematically clean, optional
astronomical bridge for fusion experiments.

1) Ruleset Interface Patch (was muss im Ruleset stehen, damit es sauber bleibt?)

Ergaenzung zu rulesets/standard_bazi_2026.json (oder als Schema-Anforderung):

{
  "ruleset_extensions": {
    "month_apex_definition": {
      "zi_apex_deg": 270.0,
      "zodiac_mode": "tropical",
      "epoch_id": "ofDate",
      "interval_convention": "HALF_OPEN"
    },
    "year_boundary_definition": {
      "mode": "solar_longitude_crossing",
      "solar_longitude_deg": 315.0,
      "time_scale": "TT",
      "zodiac_mode": "tropical"
    },
    "optional_annual_cycle": {
      "tai_sui_mapping": "MISSING"
    }
  }
}

Normative Konsequenz:

Wenn month_branch_calc = jieqi_segments, muessen die tatsaechlichen crossing times aus der Ephemeris-/TimeChain berechenbar sein, sonst -> DEGRADED + MISSING_JIEQI_CROSSINGS.

1) /validate: neue Failure Modes und Codes (minimal)
3.1 Neue Error/Warn Codes (nur wenn ihr Tai Sui Channel aktiviert)

MISSING_TAI_SUI_RULESET (ERROR in STRICT, WARNING sonst)

3.2 Neue Evidence Felder (empfohlen)

evidence.time.distance_to_hour_boundary_minutes

evidence.discretization.hour_branch_boundary_distance_min

1) Testvektoren (synthetisch, deterministisch)
TV-MONTH-APEX-001 (SHIFT_BOUNDARIES, zi_apex=270)

lambda_sun=275 -> Zi (0)

lambda_sun=284.9999 -> Zi (0)

lambda_sun=285 -> Chou (1)

lambda_sun=255 -> Zi (0)

lambda_sun=254.9999 -> Hai (11)

TV-HOUR-TLST-001 (HALF_OPEN, Zi=23-01)

TLST=23.0000 -> Zi (0)

TLST=00.9999 -> Zi (0)

TLST=01.0000 -> Chou (1)

TLST=22.9999 -> Hai (11)

TV-HOUR-PHASE-001 (gamma equivalence)

TLST=23 -> gamma=345 -> Zi (0)

TLST=1 -> gamma=15 -> Chou (1)
Assert: hour_branch(TLST-binning) == hour_branch(gamma-mapping)

TV-ANNUAL-JUPITER-001 (optional channel)

if annual_cycle_mode=PHYSICAL_JUPITER_LONGITUDE:

engine returns feature annual_branch_from_jupiter with provenance

if annual_cycle_mode=VIRTUAL_TAI_SUI and mapping missing:

/validate emits MISSING_TAI_SUI_RULESET

1) Was wird dadurch praeziser/besser?

Zi-Sektor Formel ist komplett und implementierbar:

Zi = [255,285) (bei zi_apex=270), HALF_OPEN eindeutig.

Hour-Branch ist wirklich "dieselbe Formel" (nur anderer Winkelraum):

TLST-binning und solar-time phase gamma sind formal gleichwertig.

Optionaler Hour Angle H ist sauber eingebettet (ohne Branch-Def zu veraendern).

Jupiter/Tai Sui wird nicht zum semantischen Stolperdraht:

BaZi Year Pillar bleibt BaZi.

Jupiter/Tai Sui sind definierte, optionale Fusion-Features mit harter Provenance und MISSING-Regeln.

---

## Contract Reference: PATCH-VALUES (Schemas, error codes, acceptance tests)

See:
- spec/schemas/ValidateRequest.schema.json
- spec/schemas/ValidateResponse.schema.json
- spec/tests/tv_matrix.json
- spec/tests/pt_definitions.md

Patch source:
1) /validate Endpoint: JSON Schema (Draft-07)
