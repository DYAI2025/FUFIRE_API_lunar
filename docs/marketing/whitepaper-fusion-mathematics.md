# Fusion Astrology in Five-Dimensional Element Space: A Calibrated Coherence Metric for Cross-Traditional Chart Comparison

**FuFirE Technical Whitepaper TWP-001**
Version 1.0 | March 2026

Authors: FuFirE Engineering Team

---

## Abstract

FuFirE (Fusion Firmament Engine) solves a long-standing interoperability problem between Western astrology and Chinese BaZi (Four Pillars of Destiny) by projecting both systems into a shared five-dimensional vector space defined by the Wu-Xing (Five Elements). Each tradition's chart produces a non-negative vector in R^5; L2-normalization maps both onto the positive orthant of the unit 4-sphere S^4. The cosine similarity between these unit vectors yields a raw Coherence Index H. Because non-negative unit vectors in R^5 exhibit a baseline expected similarity of 0.45--0.80 depending on input density, raw H is misleading without correction. We introduce a calibrated metric H_calibrated that measures structural congruence above an empirically derived Monte Carlo baseline. The engine is deterministic, fully auditable via a per-contribution ledger, and validated against 1500+ regression tests with 200 bit-stable snapshot vectors.

---

## 1. Introduction

Western astrology and Chinese BaZi are independently developed astronomical interpretation systems. Western astrology encodes planetary positions along the ecliptic; BaZi encodes the sexagenary cycle derived from solar-term boundaries. Despite sharing an astronomical substrate (the Sun's apparent motion), they produce structurally different outputs: ecliptic longitudes and zodiac signs on one side, Heavenly Stems and Earthly Branches on the other.

Any meaningful comparison requires a shared representation space. Ad hoc textual mappings ("Jupiter is like Wood") lack rigor and cannot be quantified. FuFirE addresses this by defining a precise projection from each system into R^5, equipped with a well-defined similarity metric and empirical calibration.

The contribution of this paper is threefold: (1) a formal vector-space construction for cross-traditional comparison, (2) identification and correction of the positive-orthant bias that inflates naive similarity scores, and (3) a fully auditable implementation with deterministic guarantees.

---

## 2. Background

### 2.1 Western Astrology: Planetary Positions

A Western chart computes geocentric ecliptic longitudes for celestial bodies at a given UTC instant. FuFirE uses the Swiss Ephemeris (pyswisseph) for sub-arcsecond precision. The engine evaluates up to 13 bodies: the seven classical planets (Sun, Moon, Mercury, Venus, Mars, Jupiter, Saturn), three modern planets (Uranus, Neptune, Pluto), and three auxiliary points (Chiron, Lilith, North Node). Retrograde status is derived from the sign of daily motion.

### 2.2 Chinese BaZi: Four Pillars

BaZi assigns four pillar pairs (Year, Month, Day, Hour), each consisting of a Heavenly Stem (one of 10) and an Earthly Branch (one of 12). The Year pillar changes at LiChun (solar longitude 315 degrees, approximately February 3--5), not January 1. The Month pillar follows solar-term boundaries. The Day pillar is computed from the Julian Day Number with a calibrated offset (JDN + 49) mod 60. The Hour pillar depends on True Solar Time, not civil clock time.

Each Heavenly Stem maps directly to one of the Five Elements. Each Earthly Branch contains one to three "hidden stems" with traditional Qi weights: Main Qi (1.0), Middle Qi (0.5), Residual Qi (0.3). For example, Branch Chen contains Earth (1.0), Wood (0.5), and Water (0.3).

### 2.3 Wu-Xing: The Five Elements

The Wu-Xing system (Wood, Fire, Earth, Metal, Water) is the natural shared vocabulary. Both traditions already use it internally: Western planets have classical elemental associations; BaZi stems are explicitly elemental. The generative cycle (Wood -> Fire -> Earth -> Metal -> Water -> Wood) provides the canonical ordering.

---

## 3. Method

### 3.1 The Vector Space

We define Wu-Xing space as R^5 with ordered basis:

```
e = [Wood, Fire, Earth, Metal, Water]
```

All vectors have non-negative components (weights are always >= 0), restricting us to the positive orthant R^5_+.

### 3.2 Western Projection

Each planetary body contributes a weight to its assigned element:

| Planet | Element | Weight | Category |
|--------|---------|--------|----------|
| Sun | Fire | 1.0 (1.3 if retrograde) | Traditional |
| Moon | Water | 1.0 (1.3 if retrograde) | Traditional |
| Mercury | Earth (day) / Metal (night) | 1.0 (1.3 if retrograde) | Traditional |
| Venus | Metal | 1.0 (1.3 if retrograde) | Traditional |
| Mars | Fire | 1.0 (1.3 if retrograde) | Traditional |
| Jupiter | Wood | 1.0 (1.3 if retrograde) | Traditional |
| Saturn | Earth | 1.0 (1.3 if retrograde) | Traditional |
| Uranus | Wood | 1.0 (1.3 if retrograde) | Modern heuristic |
| Neptune | Water | 1.0 (1.3 if retrograde) | Modern heuristic |
| Pluto | Fire | 1.0 (1.3 if retrograde) | Modern heuristic |

Mercury's dual assignment depends on sect: Earth in day charts, Metal in night charts. Day/night determination uses the Sun-Ascendant geometric relationship.

The raw Western vector v_W is the component-wise sum of all planet contributions.

### 3.3 BaZi Projection

Each of four pillars contributes through its Heavenly Stem (weight 1.0) and Earthly Branch hidden stems (Main: 1.0, Middle: 0.5, Residual: 0.3). For example, pillar Jia-Chen contributes:

```
Stem Jia:            Wood  += 1.0
Branch Chen Main:    Earth += 1.0
Branch Chen Middle:  Wood  += 0.5
Branch Chen Residual: Water += 0.3
```

A full four-pillar chart produces 12--16 individual contributions, yielding raw BaZi vector v_B.

### 3.4 Normalization

Both raw vectors are L2-normalized:

```
v_hat = v / ||v||_2
```

This maps each vector onto the intersection of S^4 (the unit 4-sphere) with the positive orthant R^5_+. Normalization ensures that the number of contributing bodies does not bias the comparison -- a chart with 13 planets is compared on equal footing with one that has 7.

### 3.5 Coherence Index

The raw Coherence Index is the dot product of the two unit vectors:

```
H_raw = v_hat_W . v_hat_B = cos(theta)
```

Since both vectors lie in the positive orthant, theta is in [0, pi/2] and H_raw is in [0, 1]. A value of 1.0 means identical elemental profiles; 0.0 means orthogonal (maximally different) profiles.

---

## 4. The Calibration Problem

### 4.1 Positive Orthant Bias

The raw Coherence Index has a critical flaw: it is systematically inflated. Two random non-negative unit vectors in R^5 are not expected to be orthogonal. Their expected cosine similarity depends on the number of non-zero components (input density) and is substantially greater than zero.

Consider the geometry: random points on the positive orthant of S^4 are confined to 1/32 of the full sphere. They cluster around the direction (1,1,1,1,1)/sqrt(5), producing high expected dot products.

### 4.2 Empirical Baselines

We estimated the null distribution via 5000 Monte Carlo trials per density cell (seed=42), reproducible via `python scripts/calibrate_baselines.py --trials 5000 --seed 42`. Results are archived in `docs/calibration-results.json`. Input density is bucketed as follows:

- **Western density**: sparse (1--3 planets), medium (4--8), dense (9+)
- **BaZi density**: sparse (1--8 Qi contributions), medium (9--16), dense (17+)

Each trial generates two random R^5 vectors by distributing n contributions uniformly across 5 element bins, then computes their cosine similarity. The full 3x3 baseline table:

| Western | BaZi | H_baseline | sigma |
|---------|------|------------|-------|
| sparse | sparse | 0.449 | 0.267 |
| sparse | medium | 0.524 | 0.208 |
| sparse | dense | 0.546 | 0.176 |
| medium | sparse | 0.609 | 0.215 |
| medium | medium | 0.690 | 0.176 |
| medium | dense | 0.727 | 0.150 |
| dense | sparse | 0.665 | 0.187 |
| dense | medium | 0.761 | 0.145 |
| dense | dense | 0.796 | 0.122 |

A dense/dense chart pair (the typical case with all planets available) has a baseline expected H of 0.796. Without calibration, a raw score of 0.84 would be reported as "strong coherence" when it is barely above chance.

### 4.3 Calibrated Metric

The calibrated Coherence Index measures how much structural congruence exceeds the density-matched baseline:

```
H_calibrated = max(0, (H_raw - H_baseline) / (1 - H_baseline))
```

This is a contrast ratio: H_calibrated = 0.0 means "exactly as similar as random charts of this density," and H_calibrated = 1.0 means "maximum possible congruence." Values below zero (less similar than random) are clamped to zero.

We also report a z-score:

```
sigma_above = (H_raw - H_baseline) / sigma
```

This enables statistical interpretation: sigma_above > 2.0 indicates the congruence is unlikely to arise by chance.

---

## 5. Implementation

### 5.1 True Solar Time

BaZi hour pillar calculation requires True Solar Time (TST), not civil clock time. Civil time deviates from solar time due to timezone rounding, longitude offset from the standard meridian, and the Equation of Time (EoT).

```
TST = civil_time + 4 * (standard_meridian - longitude) / 60 + EoT / 60
```

The EoT is computed from the NOAA reference formula:

```
gamma = 2 * pi * (day_of_year - 1) / 365
EoT = 229.18 * (0.000075 + 0.001868*cos(gamma) - 0.032077*sin(gamma)
       - 0.014615*cos(2*gamma) - 0.040849*sin(2*gamma))
```

This yields values in the range of approximately -14.2 to +16.4 minutes. For Berlin (longitude 13.405, standard meridian 15), the longitude correction alone shifts the hour by about 6.4 minutes.

### 5.2 Contribution Ledger

Every weight contribution is logged as a structured record containing: source identity (planet name or stem/branch), target element, numeric weight, retrograde status (for planets), Qi category (for branches), and a rationale string. This ledger enables full mathematical reproducibility -- any third party can reconstruct the exact vector from the ledger entries.

### 5.3 Provenance and Determinism

Each API response includes a provenance block specifying: engine version, ephemeris backend identifier, parameter set (stem weight, hidden stem weights, retrograde multiplier, Mercury dual rule, coherence method), ruleset ID, and house system. Identical inputs with identical provenance parameters produce bit-identical outputs.

### 5.4 Quality Assurance

The engine maintains 1500+ regression tests across 12 test modules, including 200 bit-stable snapshot vectors that detect any numerical drift. CI enforces type checking (mypy), linting (ruff), and complexity gates. The test suite covers golden vectors (known-correct pillar results), LiChun boundary cases, DST edge cases, high-latitude locations, and cross-timezone True Solar Time consistency.

---

## 6. Worked Example

**Input:** 2024-02-10 14:30 CET, Berlin (52.52N, 13.405E).

**BaZi pillars:** Jia-Chen (Year), Bing-Yin (Month), Jia-Chen (Day), Xin-Wei (Hour). This yields 16 Qi contributions. Raw BaZi vector (before normalization):

```
Wood=4.3  Fire=2.0  Earth=3.3  Metal=1.0  Water=0.6
```

**Western planets:** 13 bodies computed, night chart detected (Mercury -> Metal). North Node and TrueNorthNode both retrograde (weight 1.3 each). Raw Western vector:

```
Wood=4.6  Fire=3.0  Earth=1.0  Metal=2.0  Water=3.0
```

**Normalized unit vectors:**

| Element | Western | BaZi | Difference |
|---------|---------|------|------------|
| Wood | 0.692 | 0.730 | -0.037 |
| Fire | 0.451 | 0.339 | +0.112 |
| Earth | 0.150 | 0.560 | -0.409 |
| Metal | 0.301 | 0.170 | +0.131 |
| Water | 0.451 | 0.102 | +0.350 |

**Raw Coherence Index:** H_raw = 0.8395

**Calibration** (dense/medium, baseline 0.791, sigma 0.127):

```
H_calibrated = (0.8395 - 0.791) / (1 - 0.791) = 0.2321
sigma_above = (0.8395 - 0.791) / 0.127 = 0.382
```

**Interpretation:** H_calibrated = 0.23, below-average congruence. Despite a seemingly high raw score of 0.84, the calibrated metric reveals that this chart pair is only marginally more aligned than random charts of similar density. The dominant element (Wood) agrees across both systems, but the large Earth discrepancy (0.56 BaZi vs. 0.15 Western) and Water discrepancy (0.10 BaZi vs. 0.45 Western) dilute the overall alignment. The z-score of 0.38 confirms this is well within the normal range.

---

## 7. Discussion

### 7.1 What H_calibrated Measures

H_calibrated quantifies the degree to which the elemental profile derived from planetary positions structurally mirrors the profile derived from the sexagenary cycle, beyond what would be expected from the input structure alone. It is a measure of mathematical congruence between two projections of the same birth moment into element space.

### 7.2 What It Does Not Measure

H_calibrated is not a quality score for either chart individually. It does not assess whether a chart is "good" or "bad." It does not incorporate interpretive traditions such as the Ten Gods, Luck Pillars, planetary dignities, or aspect patterns. It does not claim astrological validity -- it provides a rigorous mathematical framework for those who wish to explore cross-traditional correlations.

### 7.3 Limitations

**Planet-element mapping.** The assignment of modern planets (Uranus, Neptune, Pluto) to elements follows heuristic correspondences, not classical doctrine. These are categorized separately in the contribution ledger. Users can assess their impact by examining the ledger.

**Equal planet weighting.** All planets contribute weight 1.0 (or 1.3 retrograde). A luminaries-weighted scheme (higher weight for Sun/Moon) might better reflect traditional importance hierarchies but would introduce additional free parameters.

**Hidden stem model.** The Main/Middle/Residual Qi weights (1.0/0.5/0.3) follow the most common traditional convention but are not universally agreed upon across all BaZi schools.

**Calibration granularity.** The current baseline table uses three density buckets per system (sparse/medium/dense). A continuous regression model could provide finer calibration but would require a larger simulation corpus.

---

## 8. Conclusion

FuFirE demonstrates that a principled mathematical comparison between Western and Chinese astrological systems is achievable by projecting both into a shared Wu-Xing vector space. The critical insight is that naive cosine similarity in the positive orthant of R^5 is misleading without density-aware calibration. The calibrated Coherence Index H_calibrated provides an interpretable metric grounded in an empirical null hypothesis.

The implementation prioritizes transparency (contribution ledger), reproducibility (deterministic computation with provenance tracking), and correctness (1500+ regression tests, bit-stable snapshots). The full API is available as a REST service with JSON Schema validation.

Whether H_calibrated captures something meaningful about the relationship between these two astronomical traditions is an empirical question that this engine makes possible to investigate at scale.

---

## References

1. Swiss Ephemeris documentation. Astrodienst AG, Zurich.
2. NOAA Solar Calculator. National Oceanic and Atmospheric Administration.
3. Shao, W. (2008). *The Complete Guide to BaZi Four Pillars of Destiny.*
4. Hand, R. (1976). *Planets in Composite.* Para Research.

---

## Cite As

```
FuFirE Engineering Team. "Fusion Astrology in Five-Dimensional Element Space:
A Calibrated Coherence Metric for Cross-Traditional Chart Comparison."
FuFirE Technical Whitepaper TWP-001, v1.0, March 2026.
URL: https://github.com/DYAI2025/BAFE
```
