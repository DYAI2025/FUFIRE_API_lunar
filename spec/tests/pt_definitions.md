# Property Tests (PT*)

PT1 wrap360/wrap180 periodicity
- wrap360(x + 360*n) == wrap360(x)
- wrap180(x + 360*n) == wrap180(x)
- wrap360 in [0,360), wrap180 in (-180,180]

PT2 kernel sum(weights)=1
- soft kernel branch weights are >=0 and sum to 1 (within tolerance)
- symmetric cases: at exact midpoints between two centers, the two adjacent weights are equal

PT3 harmonic degeneracy/periodicity
- phasor features are 360-periodic in longitude
- degeneracy flags are raised when norms are ~0

PT4 canonical JSON determinism (fingerprint stable)
- config_fingerprint is stable under key reordering
- config_fingerprint is stable across repeated computations in deterministic mode
