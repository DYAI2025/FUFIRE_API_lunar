# Corrected Zi Wei Dou Shu Formula Specification for FuFirE

## 1. Release status

**Core calculation seed: COMPUTATIONALLY_COHERENT.**  
**Historically complete/original ruleset: SOURCE_NEEDED.**

The user-provided guide is a useful formula seed, not a complete traditional specification. It defines the 12-palace frame, Ming/Shen, palace stems, Five-Elements Bureau, Zi Wei/Tian Fu, 14 major stars, four auxiliary stars, one Four-Transformations table, San Fang Si Zheng and a basic decadal rule. It does not define a complete school-specific star catalog, brightness tables, all dynamic layers or authoritative source editions.

## 2. Variable contract

All transport inputs must be resolved into an internal `ResolvedZwdsSeed` before star placement:

| Variable | Domain | Meaning | Source status |
|---|---:|---|---|
| `m` | 1..12 | effective lunar month after the selected leap-month policy | ruleset-dependent |
| `d` | 1..30 | chart lunar day after complete date rollover handling | ruleset-dependent |
| `h` | 1..12 | double-hour ordinal, Zi = 1 | computed |
| `y_s` | 0..9 | year stem index, Jia = 0 | year-cycle policy |
| `y_b` | 0..11 | year branch index, Zi = 0 | year-cycle policy |

`y_s` and `y_b` are independent typed variables. The guide's row `庚 / 午` is invalid: `庚` is a stem and `午` is a branch. Never permit a union string or use the zodiac animal as the branch value.

The seed must also carry `calendar_policy_id`, `time_policy_id`, `late_zi_policy_id`, `leap_month_policy_id`, `year_cycle_policy_id` and source provenance.

## 3. Canonical coordinate system

- Branches: `ZI=0, CHOU=1, YIN=2, ..., HAI=11`.
- Stems: `JIA=0, YI=1, ..., GUI=9`.
- `mod12(x) = ((x % 12) + 12) % 12`.
- `mod10(x) = ((x % 10) + 10) % 10`.

Never rely on language-specific negative remainder behavior.

## 4. Calendar/time pipeline — corrected

The previous design was too loose about operation order. Use this explicit pipeline:

1. Parse local civil time and resolve DST ambiguity/nonexistence.
2. Apply the ruleset time standard (`CIVIL`, `LMT` or `TLST`) to obtain the chart-local time.
3. Derive the hour branch and detect late Zi on the chart-local time.
4. Apply the late-Zi chart-date policy.
5. Convert the resulting chart date to the Chinese lunisolar date.
6. Apply the leap-month interpretation policy to derive `m`.
7. Resolve the year stem/branch using the ruleset's year-cycle policy.

**Critical correction:** never implement late Zi as a bare `d += 1`. Advancing the chart date can cross a lunar month or lunar year and must be handled by the calendar engine.

Coordinates are required by the proposed API for reproducibility and LMT/TLST compatibility. This is an API contract choice, not proof that every ZWDS school universally requires true solar time.

## 5. Ming and Shen palaces

With `YIN = 2`:

- `ming_b = mod12(2 + (m - 1) - (h - 1))`
- `shen_b = mod12(2 + (m - 1) + (h - 1))`

For `m=1, h=1`, both equal `YIN`.

## 6. Twelve palace roles

Use the source-order IDs:

`MING, XIONG_DI, FU_QI, ZI_NU, CAI_BO, JI_E, QIAN_YI, JIAO_YOU, GUAN_LU, TIAN_ZHAI, FU_DE, FU_MU`.

For `i=0..11`:

- `palace_branch(i) = mod12(ming_b - i)`.

Do not store English interpretations as the primary identifier.

## 7. Palace stems — Five Tigers

- `yin_stem = mod10(2*y_s + 2)`.
- `palace_stem(branch_b) = mod10(yin_stem + mod12(branch_b - YIN))`.

This reproduces the five start pairs described by the guide and the implementation comparator.

## 8. Five-Elements Bureau

Reject invalid stem/branch parity pairs before lookup:

- valid pair invariant: `(stem_index_0 - branch_index_0) mod 2 = 0`.

For a valid Ming-palace pair:

- `stem_group = floor(stem_index_0 / 2) + 1`
- `branch_group = floor((branch_index_0 mod 6) / 2) + 1`
- `v = ((stem_group + branch_group - 1) mod 5) + 1`

Mapping:

| `v` | Bureau |
|---:|---|
| 1 | `WOOD_3` |
| 2 | `METAL_4` |
| 3 | `WATER_2` |
| 4 | `FIRE_6` |
| 5 | `EARTH_5` |

Ship an immutable 60-pair table generated from this rule and hash it in the ruleset.

## 9. Zi Wei and Tian Fu

Let `B` be the bureau number in `{2,3,4,5,6}`:

- `k = ceil(d / B)`
- `delta = k*B - d`
- `step_ordinal = k + delta` when `delta` is even
- `step_ordinal = k - delta` when `delta` is odd
- `ziwei_b = mod12(YIN + step_ordinal - 1)`
- `tianfu_b = mod12(4 - ziwei_b)`

The finite-domain test verifies algebraic equivalence between the guide's 1-based expression and this 0-based expression for all `30 × 5 = 150` day/bureau cases. This is **not** independent historical validation.

## 10. Fourteen major stars

Offsets from `ziwei_b`:

| Star ID | Offset |
|---|---:|
| `ZI_WEI` | 0 |
| `TIAN_JI` | -1 |
| `TAI_YANG` | -3 |
| `WU_QU` | -4 |
| `TIAN_TONG` | -5 |
| `LIAN_ZHEN` | -8 |

Offsets from `tianfu_b`:

| Star ID | Offset |
|---|---:|
| `TIAN_FU` | 0 |
| `TAI_YIN` | +1 |
| `TAN_LANG` | +2 |
| `JU_MEN` | +3 |
| `TIAN_XIANG` | +4 |
| `TIAN_LIANG` | +5 |
| `QI_SHA` | +6 |
| `PO_JUN` | +10 |

Each position is `mod12(base + offset)`.

## 11. Four guide-defined auxiliary stars

- `ZUO_FU = mod12(CHEN + (m-1))`
- `YOU_BI = mod12(XU - (m-1))`
- `WEN_QU = mod12(CHEN + (h-1))`
- `WEN_CHANG = mod12(XU - (h-1))`

These four are a seed subset, not a complete auxiliary-star catalog.

## 12. Four Transformations

The guide table must be a versioned data file, not universal code. At least two documented tabulations differ in the Geng and Ren rows. Therefore every response must disclose `transformation_table_id` and `transformation_table_sha256`.

## 13. San Fang Si Zheng

For focus branch `p`:

- `harmony_1 = mod12(p + 4)`
- `harmony_2 = mod12(p + 8)`
- `opposition = mod12(p + 6)`

Return relations only. Beneficial/harmful interpretation belongs in a separately sourced interpretation layer.

## 14. Decadal limits

Guide-seed rule:

- first start age = bureau number;
- each next range begins 10 years later;
- first range is assigned to Ming palace;
- direction is selected by explicit direction or the year-stem-yin/yang plus sex rule.

Every response must state inclusive/exclusive range semantics and `age_reckoning_id`. This rule is releaseable only as part of a named ruleset.

## 15. Completeness gate

The word `complete` is allowed only as `complete for ruleset <id>`, when:

- the ruleset enumerates every included star/rule family;
- all policies and tables have source pointers and immutable hashes;
- calendar boundary tests pass;
- golden charts are practitioner-reviewed;
- missing family count is zero for the requested scope.

Do not use an unsourced universal number such as “108 stars” as a completeness criterion.
