# Source and Evidence Ledger

| ID | Source | Class | What it supports | Limits |
|---|---|---|---|---|
| `S-01` | User guide `Eingefügter Text.txt` | user-provided synthesis | Formula seed, stated conventions, terminology, claims under audit | Not an identified primary edition; contains at least one token error and unsupported completeness claims |
| `S-02` | FuFirE `bazi_engine/time_utils.py`, lines 39–40 and 63–76 | inspected project code | Supported DST enums: `earlier/later`, `error/shift_forward` | Does not supply a Chinese lunisolar calendar |
| `S-03` | FuFirE `bazi_engine/dayun/direction.py`, lines 5–10 and 21–25 | inspected project code | Existing explicit/traditional flow-direction semantics | BaZi Da-Yun reuse must be named and tested for the selected ZWDS ruleset |
| `S-04` | Chinese Wikipedia article on 紫微斗數, history and calculation sections | secondary, caution | Describes Chen Tuan as traditional attribution; documents 14 major stars, calculation sequence, Four-Transformation variants, and late-Zi alternatives | Article itself flags source-quality issues; use only to prove that competing conventions exist, not as final authority |
| `S-05` | `SylarLong/iztro` commit `2dfe3ec...`, `palace.ts`, `location.ts`, `majorStar.ts` | implementation comparator | Corroborates core formula structure and exposes configurable conventions | Software agreement is not historical proof |
| `S-06` | `SylarLong/iztro` tests `star.test.ts`, `palace.test.ts` | implementation test corpus | Concrete comparator vectors for palace, bureau and star placement | Not an independent practitioner-approved FuFirE golden corpus |
| `S-07` | Unicode/typed ID policy in project skill | technical symbol control | Separating Heavenly Stem, Earthly Branch and animal tokens | Not an authority for ZWDS school selection |

## Claim-language rule

- `COMPUTATIONALLY_COHERENT`: finite-domain or invariant checks passed.
- `IMPLEMENTATION_CORROBORATED`: another implementation follows the same rule.
- `SOURCE_REVIEWED`: a selected ruleset source has been reviewed and recorded.
- `SOURCE_NEEDED`: insufficient authority for a final rule or historical claim.
- `BLOCKED`: must not be presented as fact or universal behavior.

No combination of schema validation, finite-domain testing and implementation comparison is labeled “historically verified.”
