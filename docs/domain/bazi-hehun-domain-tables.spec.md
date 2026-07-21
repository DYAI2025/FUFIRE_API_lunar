# Domain mapping-table format — bazi-hehun (unblocks MISSING-001..003 + day_cycle_anchor)

**Status update 2026-07-04** (see CONTRA-DOMAIN-TABLES-002 in
`docs/governance/bazi-hehun.missing-assumption-blocker-ledger.md`): the user
supplied two reference documents. Cross-checked against every table below:

- **§4 (ten_gods + spouse_star): DELIVERED.** Both the 10x10 Shi Shen matrix
  and the spouse-star convention were explicit and citable in
  `systematisches_handbuch_der_bazi_hehun_kompatibili.md` (Tabelle 8, Tabelle
  10). Shipped in `spec/rulesets/standard_bazi_2026.json` (`ten_gods`,
  `spouse_star_convention`) and `bazi_engine/match/ten_gods.py`, validated in
  `tests/test_match_ten_gods.py` (full 100-cell matrix + cross-check against
  the other doc's two worked example charts via the live engine).
  MISSING-002 is RESOLVED. `spouse_star` itself stays `PENDING_TABLES` —
  the remaining blocker is MISSING-007 (no gender field in `MatchRequest`),
  not a table gap.
- **§1 (day_cycle_anchor), §2/§3 (day_master_strength, yong_shen): STILL
  OPEN.** Neither document contains a JD→sexagenary citation, a seasonal
  Wang-Xiang-Xiu-Qiu-Si weight table, a DMS score formula/band cutoffs, or a
  Yong-Shen selection rule — these tables genuinely were not in the supplied
  material (checked exhaustively, not assumed absent). A different, more
  technical/tabular source is still needed for these three. (Non-citation-
  grade corroboration for the day-cycle anchor specifically was found —
  see CONTRA-DOMAIN-TABLES-002 — but does not meet the citation bar below.)

The honest path to flip the deferred flags to `CALCULATED`/`verified`: deliver the
domain data below in these exact shapes, they get merged into
`spec/rulesets/standard_bazi_2026.json` (or a new `domain_tables` block loaded by
`bazi_engine/bafe/ruleset_loader.py`), the engine computes the fields, and each flag
flips **because the source now exists** — never by editing the flag directly.

## Canonical vocabulary (all tables key on these exact tokens)

- **Stems (天干, 10):** `Jia, Yi, Bing, Ding, Wu, Ji, Geng, Xin, Ren, Gui`
- **Branches (地支, 12):** `Zi, Chou, Yin, Mao, Chen, Si, Wu, Wei, Shen, You, Xu, Hai`
- **Elements (五行, 5):** `wood, fire, earth, metal, water`
- **Polarity:** `yang, yin` (Jia/Bing/Wu/Geng/Ren = yang; Yi/Ding/Ji/Xin/Gui = yin)

Every table carries `source_provenance` (citation + reviewer) so provenance is auditable —
that citation is what makes the flip legitimate rather than fabricated.

---

## 1. `day_cycle_anchor` calibration → flips `DAY_ANCHOR_UNVERIFIED` (MISSING-006)

The anchor already exists; it only lacks a sourced reference. To verify, give ONE
authoritative known-sexagenary-day reference; the engine checks that
`(reference_jdn + anchor_offset) % 60` reproduces the cited index, then sets
`anchor_verification: "verified"`.

```json
"day_cycle_anchor": {
  "anchor_type": "JDN",
  "anchor_jdn": 2419451,
  "anchor_sexagenary_index_0based": 0,
  "anchor_label": "JiaZi day",
  "anchor_verification": "verified",
  "verification_source": {
    "reference_gregorian_date": "YYYY-MM-DD",
    "reference_sexagenary_day": "Jia-Zi",            // stem-branch of that day
    "reference_sexagenary_index_0based": 0,          // 0..59
    "citation": "<authoritative ephemeris/almanac, page/edition>",
    "reviewed_by": "<domain reviewer + date>"
  }
}
```

What I need from you: **one** trustworthy (gregorian date → sexagenary day) pair + the
source. The engine validates the existing `anchor_jdn`/index against it; if consistent,
the flag flips. If it disagrees, that's a real correction (and I surface it, not hide it).

---

## 2. `day_master_strength` (DMS) → flips the DMS field to `CALCULATED` (MISSING-003)

DMS = how supported the day-master element is, given season (month command) + the chart's
Wu-Xing vector. Give the classification of each element's role relative to the day master,
the seasonal weighting per month branch, and the band thresholds.

```json
"day_master_strength": {
  "mode": "supported_vs_draining_bands",
  "role_of_element_vs_day_master": {
    // for a day master of element X, each of the 5 elements plays one role
    "same":       "supports",     // 比劫  (same element)
    "resource":   "supports",     // 印    (element that produces X)
    "output":     "drains",       // 食伤  (element X produces)
    "wealth":     "drains",       // 财    (element X controls)
    "officer":    "drains"        // 官杀  (element that controls X)
  },
  "seasonal_weight_by_month_branch": {
    // multiplier applied to the day-master element's support when born in that month
    // (prosperous/旺 season high, imprisoned/囚死 season low). One entry per branch.
    "Zi": {"wood": 1.0, "fire": 0.3, "earth": 0.5, "metal": 0.7, "water": 1.3},
    "Chou": { "...": "..." }
    // ... all 12 branches × 5 elements
  },
  "score_formula": "weighted_support_sum_minus_drain_sum",   // or your exact formula
  "bands": [
    {"label": "weak",     "min": 0.0, "max": 0.40},
    {"label": "balanced", "min": 0.40, "max": 0.60},
    {"label": "strong",   "min": 0.60, "max": 1.0}
  ],
  "confidence_when_sourced": 1.0,
  "source_provenance": {"citation": "...", "reviewed_by": "..."}
}
```

What I need: the **role map** (same/resource/output/wealth/officer → supports/drains), the
**12×5 seasonal weight** table, the **score formula**, and the **band cutoffs**. Then DMS
computes from the existing Wu-Xing ledger + month command — no new astronomy.

---

## 3. `yong_shen` (useful god) → flips Yong-Shen to `CALCULATED` (MISSING-003, depends on §2)

Selection rule keyed by (day-master element, DMS band) → favorable element(s). Optionally a
climate/调候 adjustment by month branch.

```json
"yong_shen": {
  "mode": "strength_band_to_favorable_elements",
  "rule_by_daymaster_element_and_band": {
    "wood":  {"weak": ["water", "wood"], "balanced": ["fire"], "strong": ["metal", "fire", "earth"]},
    "fire":  {"weak": ["wood", "fire"],  "balanced": ["earth"], "strong": ["water", "earth", "metal"]},
    "earth": {"...": "..."},
    "metal": {"...": "..."},
    "water": {"...": "..."}
  },
  "climate_adjustment_by_month_branch": {           // OPTIONAL (调候); omit if not used
    "Zi": {"prefer": ["fire"], "reason": "cold winter needs warmth"},
    "...": "..."
  },
  "confidence_when_sourced": 1.0,
  "source_provenance": {"citation": "...", "reviewed_by": "..."}
}
```

What I need: the **5 × 3 (element × band)** favorable-element map. `yong_shen` then follows
deterministically from DMS (§2).

---

## 4. `ten_gods` + `spouse_star` → flips spouse-star to `CALCULATED` (MISSING-002)

The Ten Gods derive from (day-master stem → target stem) via element-relation + polarity.
Either give the closed rule (preferred — 10×10 is generated) or the explicit 10×10 table.

```json
"ten_gods": {
  "mode": "element_relation_plus_polarity_rule",
  "relation_to_god": {
    // relation of TARGET element to DAY-MASTER element, split by same/different polarity
    "same_element":       {"same_polarity": "Friend",        "diff_polarity": "RobWealth"},   // 比肩/劫财
    "resource_element":   {"same_polarity": "IndirectRes",   "diff_polarity": "DirectRes"},   // 偏印/正印
    "output_element":     {"same_polarity": "EatingGod",     "diff_polarity": "HurtingOfficer"}, // 食神/伤官
    "wealth_element":     {"same_polarity": "IndirectWealth","diff_polarity": "DirectWealth"}, // 偏财/正财
    "officer_element":    {"same_polarity": "SevenKilling",  "diff_polarity": "DirectOfficer"} // 七杀/正官
  },
  "spouse_star": {
    // which Ten-God is the spouse star, by the convention you approve
    "by_convention": "classical",
    "male":   ["DirectWealth", "IndirectWealth"],   // 财 = wife
    "female": ["DirectOfficer", "SevenKilling"],    // 官杀 = husband
    "neutral_or_unspecified_gender": "report_both_and_mark_convention"
  },
  "confidence_when_sourced": 1.0,
  "source_provenance": {"citation": "...", "reviewed_by": "..."}
}
```

What I need: confirm the **relation→god polarity map** above matches your source (this is the
standard mapping, but I won't assume — cite it), and the **spouse-star convention**
(male=wealth / female=officer, or your variant). Element-producing/controlling cycles the
engine already has (`wuxing/`), so no new element math — just the god labels + spouse rule.

---

## How the flip happens (no shortcut)

1. You deliver the JSONs above (partial is fine — each table unblocks its own field).
2. They merge into the ruleset under a `domain_tables` block (or the existing keys for the
   anchor); `ruleset_loader.py` gains typed accessors.
3. New engine code computes each field from the tables + the existing chart facts, TDD with
   golden fixtures you (or the source) can confirm.
4. The field's `source_status` flips to `CALCULATED` **because the computation now has an
   approved source** — the `DerivedFieldStatus` fabrication guard is updated to accept
   CALCULATED only for fields whose backing table is present + provenance-cited.
5. `ruleset_version` bumps; OpenAPI regenerates; the live contract shows the real values.

The `NEEDS_DOMAIN_REVIEW`/`PENDING_TABLES` markers stay until step 4 for each field — so at
every moment the system is honest about exactly what is and isn't sourced.
