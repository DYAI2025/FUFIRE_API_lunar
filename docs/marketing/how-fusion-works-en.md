# How FuFirE Fusion Works — The Math Behind the Coherence Index

## The Problem

Two ancient systems — Western astrology and Chinese BaZi — describe the same birth moment in completely different formats.

Western astrology gives you planetary positions on a 360-degree circle. BaZi gives you Heavenly Stems and Earthly Branches from a 60-unit sexagenary cycle. One speaks in degrees and zodiac signs. The other speaks in Wood, Fire, Earth, Metal, and Water.

These two systems evolved independently, thousands of miles apart, over thousands of years. They have no shared vocabulary. So how do you compare them in a way that is mathematically rigorous and not hand-wavy?

That is what FuFirE's fusion engine does. Here is exactly how.

## Step 1: A Shared Language — The Five Elements

Both systems can be mapped to Wu-Xing (Five Elements): Wood, Fire, Earth, Metal, Water. This is not a trick or a stretch — element correspondences are deeply embedded in both traditions.

### Western Planets to Five Elements

Each planet has a fixed element assignment based on classical correspondences that predate modern astrology:

| Planet  | Element         | Notes                                      |
|---------|-----------------|---------------------------------------------|
| Sun     | Fire            |                                             |
| Moon    | Water           |                                             |
| Mercury | Earth or Metal | Earth during the day, Metal at night (sect) |
| Venus   | Metal           |                                             |
| Mars    | Fire            |                                             |
| Jupiter | Wood            |                                             |
| Saturn  | Earth           |                                             |
| Uranus  | Wood            |                                             |
| Neptune | Water           |                                             |
| Pluto   | Fire            |                                             |

Each planet contributes a weight of **1.0** to its assigned element. If a planet is retrograde at the time of birth, the weight increases to **1.3x** — a convention reflecting the traditional view that retrograde planets carry intensified energy.

The result is a five-number vector. For example:

```
Western vector = [Wood: 3.3, Fire: 2.0, Earth: 1.3, Metal: 2.0, Water: 3.0]
```

### BaZi Pillars to Five Elements

A BaZi chart has four pillars (Year, Month, Day, Hour). Each pillar has two components:

- **Heavenly Stem** — maps directly to one element (weight **1.0**)
- **Earthly Branch** — contains hidden stems with traditional Qi weights:
  - Main hidden stem: **1.0**
  - Middle hidden stem: **0.5**
  - Residual hidden stem: **0.3**

These hidden stem weights are not arbitrary. They come from classical BaZi theory and represent the relative strength of Qi within each branch.

The result is another five-number vector:

```
BaZi vector = [Wood: 1.5, Fire: 2.8, Earth: 3.1, Metal: 1.3, Water: 2.0]
```

## Step 2: Comparing the Distributions

Now we have two vectors in R^5 (five-dimensional space). We do not care about the absolute magnitudes — a chart with 10 planets visible is not inherently "more" of anything than a chart with 7. What matters is the **shape**: the relative distribution across the five elements.

First, we normalize both vectors to unit length:

```
v_normalized = v / ||v||_2

where ||v||_2 = sqrt(v_1^2 + v_2^2 + v_3^2 + v_4^2 + v_5^2)
```

Then we measure the angle between them using **cosine similarity**:

```
H_raw = cos(theta) = (v_west . v_bazi) / (||v_west|| * ||v_bazi||)
```

- `H_raw = 1.0` means identical distribution (the two systems emphasize the same elements in exactly the same proportions)
- `H_raw = 0.0` means completely orthogonal emphasis (no overlap at all)

This is a standard measure from linear algebra. Nothing exotic.

## Step 3: The Calibration Problem (Why Raw Scores Lie)

Here is the critical insight that makes FuFirE different from naive approaches.

Since all five element values are positive — you cannot have negative Wood — two completely random vectors in the positive orthant of R^5 already point in roughly the same direction. Geometrically, they are confined to a small cone in the corner of five-dimensional space.

The expected cosine similarity of two random charts is somewhere between **0.45 and 0.80**, depending on how many planets and Qi contributions are in play.

Without correction, almost every chart would look "harmonious." Every reading would feel impressive. And that would be dishonest.

## Step 4: Monte Carlo Calibration

To establish what "random" looks like, we ran a large-scale simulation. The procedure:

1. Generate random Wu-Xing vectors by distributing `n` unit contributions uniformly across 5 element bins
2. Compute cosine similarity for each random pair
3. Repeat 5,000 times per density configuration
4. Record the mean (baseline) and standard deviation

The simulation is fully reproducible: `python scripts/calibrate_baselines.py --seed 42`

Results:

| Western density       | BaZi density       | Expected baseline | Std. deviation |
|-----------------------|--------------------|-------------------|----------------|
| sparse (1-3 planets)  | sparse (1-8 Qi)    | 0.449             | 0.267          |
| sparse                | medium (9-16 Qi)   | 0.524             | 0.208          |
| sparse                | dense (17+ Qi)     | 0.546             | 0.176          |
| medium (4-8 planets)  | sparse             | 0.609             | 0.215          |
| medium                | medium             | 0.690             | 0.176          |
| medium                | dense              | 0.727             | 0.150          |
| dense (9+ planets)    | sparse             | 0.665             | 0.187          |
| dense                 | medium             | 0.761             | 0.145          |
| dense                 | dense              | 0.796             | 0.122          |

The key takeaway: two dense random charts average a cosine similarity of **0.796**. If we reported that as "80% harmony," we would be misleading you. That is just the geometric baseline for positive vectors with many components.

## Step 5: The Calibrated Coherence Index

The final Coherence Index measures how much **your** chart's similarity exceeds the random baseline for its density class:

```
H_calibrated = max(0, (H_raw - H_baseline) / (1 - H_baseline))
```

This is a simple rescaling. The numerator is "how much better than random." The denominator is "the maximum possible improvement over random." The `max(0, ...)` ensures we never report a negative score — if your chart is at or below random, the score is zero.

Interpretation:

- **H_calibrated = 0.0** — Your chart's similarity is exactly what two random charts would produce. No meaningful structural alignment detected.
- **H_calibrated = 0.5** — Halfway between random and perfect alignment. A notable degree of congruence.
- **H_calibrated = 1.0** — Maximum possible structural congruence between your Western and BaZi charts.

### Worked Example

Birth data: Berlin, February 10, 2024, 14:30 CET.

```
H_raw       = 0.84   (looks impressive at first glance)
H_baseline  = 0.796  (but random dense charts average 0.80)

H_calibrated = (0.84 - 0.796) / (1 - 0.796)
             = 0.044 / 0.204
             = 0.22
```

Interpretation: **moderate alignment** — 22% above what chance alone would produce. Honest, specific, and not inflated.

## What This Measures (and What It Does Not)

**What it measures:** The degree to which your Western planetary chart and your Chinese BaZi chart emphasize the same elements, beyond what random chance would explain.

**What it does NOT claim:**

- It does not prove astrology "works"
- It does not predict your future
- It does not claim the two systems "should" agree
- It is a mathematical measurement, not a spiritual judgment

**What makes it honest:**

- Every calculation is deterministic — same input, same output, always
- Every contribution is logged in a ledger (see below)
- The calibration is reproducible — run the simulation yourself
- The source code is auditable

## The Contribution Ledger

Every API response includes a full audit trail. For each element in each vector, you can see:

- **Which** planet, stem, or branch contributed
- **How much** weight (1.0 standard, 1.3 retrograde, 0.5 middle Qi, 0.3 residual Qi)
- **Why** (classical rulership, sect-dependent Mercury dual rule, hidden stem tradition)

This means you never have to trust a black box. You can trace every number in the Coherence Index back to a specific astronomical or calendrical fact about your birth moment.

## True Solar Time Correction

One more detail that matters for accuracy.

BaZi hour pillars depend on when the Sun is actually overhead at your birth location — not what the clock says. Clock time is a political convention (time zones, daylight saving). The Sun does not care about time zones.

Consider someone born at 14:30 clock time in western Spain. Their timezone meridian is at 15 degrees East (Central European Time), but their actual location is at roughly 8 degrees West. That is a 23-degree difference. The Sun overhead is about 1.5 hours behind what the clock reads.

FuFirE corrects for this using two components:

1. **Longitude correction:** 4 minutes per degree of difference between the birth longitude and the timezone's reference meridian
2. **Equation of Time:** A seasonal correction (ranging from -14.2 to +16.4 minutes across the year) that accounts for Earth's elliptical orbit and axial tilt

The result is True Solar Time — the astronomically correct local time that determines which two-hour BaZi period the birth falls into. This ensures the BaZi side of the fusion uses the right hour pillar.

## Reproducibility

Everything described on this page can be independently verified:

- **Calibration simulation:** `python scripts/calibrate_baselines.py --trials 5000 --seed 42`
- **Calibration data:** `docs/calibration-results.json`
- **Source code:** open for inspection
- **API responses:** include provenance metadata (engine version, ephemeris backend, parameter set)

No hidden layers. No proprietary sauce. If you understand linear algebra and have Python installed, you can reproduce every number.

---

*FuFirE -- Fusion Firmament Engine. Transparent by design.*
