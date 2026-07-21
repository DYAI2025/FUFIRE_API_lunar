# Western Validation Report

## Scope
- Reference charts: 176 (real birth records from notable-person datasets).
- Compared fields: Sun sign, Moon sign, Ascendant sign.
- Reference engine in dataset: kerykeion.
- Target engine: FuFirE `compute_western_chart` (tropical mode).

## Accuracy
- Sun: 100.00%
- Moon: 100.00%
- Ascendant: 97.16%
- Full chart exact (Sun+Moon+Asc): 97.16%

## Reproducibility
- Rounds: 12
- Stable mismatch signature: True

## Deviation Pattern
- All deviations are Ascendant-only mismatches (Sun/Moon remain identical).
- Mismatch set is deterministic and repeatable across shuffled runs.
- In all mismatch cases, the kerykeion UTC offset derived from `utc_time` differs from Python zoneinfo historical offset.
- This indicates reference-side time normalization drift (historical offset model), not FuFirE planetary calculation drift.

## Mismatches
- Amelia Earhart: ref Asc=Ari, FuFirE Asc=Tau, delta=3.45°, tz=America/Chicago, offset(zoneinfo)=360m, offset(kerykeion)=351m
- Winston Churchill: ref Asc=Lib, FuFirE Asc=Vir, delta=-0.18°, tz=Europe/London, offset(zoneinfo)=0m, offset(kerykeion)=1m
- Paramahansa Yogananda: ref Asc=Leo, FuFirE Asc=Vir, delta=6.98°, tz=Asia/Kolkata, offset(zoneinfo)=-321m, offset(kerykeion)=-353m
- Nikola Tesla: ref Asc=Ari, FuFirE Asc=Tau, delta=7.86°, tz=Europe/Zagreb, offset(zoneinfo)=-63m, offset(kerykeion)=-82m
- Carl Jung: ref Asc=Cap, FuFirE Asc=Aqu, delta=1.42°, tz=Europe/Zurich, offset(zoneinfo)=-29m, offset(kerykeion)=-34m

## Proposed Fix
- Keep FuFirE western core unchanged (no deterministic mismatch in Sun/Moon and only reference-offset-driven Asc drift).
- For external validation pipelines, pin one shared timezone normalization policy (IANA zoneinfo + explicit historical offsets).
- Reject or flag references where derived UTC offset disagrees with policy by >2 minutes.
