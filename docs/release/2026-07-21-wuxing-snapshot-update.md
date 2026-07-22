# Reviewed-diff request: Wu-Xing snapshot contract field

Status: **generated; maintainer review required before merge**  
Ephemeris lock ID: `c2185af9a436e8381bcf2e6584afd793a280ec0a70796c03b54ba9441fe27623`

Reason: the runtime and focused endpoint contract already require
`basis="western_planetary"` on `/calculate/wuxing`, while the 50 committed
SWIEPH Wu-Xing snapshots predated that response field. The release gate
correctly rejected the drift.

The update was executed explicitly with the locked SWIEPH data and limited to
the Wu-Xing selection of `tests/test_snapshot_stability.py`. A structural diff
check compared every updated JSON file against `HEAD` and proved:

- exactly 50 files changed;
- every file ends in `__wuxing.json`;
- the only semantic difference is the added top-level field
  `"basis": "western_planetary"`;
- no astronomical number, provenance value, timestamp, or other endpoint
  snapshot changed.

This is not an approval. Reviewers must inspect the PR diff; closing or
rejecting the change leaves the release blocked. Future updates continue to
use the read-only/manual snapshot workflow separation.
