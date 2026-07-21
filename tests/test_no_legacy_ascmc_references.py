"""Guard: no consumer outside bazi_engine/western.py may read 'ascmc' from a
chart dict. The legacy field never existed in the producer's output; every
prior usage was the audit-confirmed P0 bug fixed in commit 370a870d. This
test fails CI if the bug is reintroduced.

Audit ref: technischer_audit_bericht_korrektur_fehlerhafter_.md
"""

import pathlib
import re

# Match either dict-get or subscript access on the literal "ascmc" key.
FORBIDDEN = re.compile(r"""\.get\(\s*['"]ascmc['"]\s*[,\)]|\[\s*['"]ascmc['"]\s*\]""")

# bazi_engine/western.py legitimately uses 'ascmc' as a local variable
# name for the Swiss Ephemeris return value -- exempt that one file.
WHITELIST = {"bazi_engine/western.py"}


def test_no_consumer_reads_ascmc_from_chart_dict():
    root = pathlib.Path(__file__).resolve().parents[1]
    bazi_dir = root / "bazi_engine"
    offenders = []
    for path in bazi_dir.rglob("*.py"):
        rel = path.relative_to(root).as_posix()
        if rel in WHITELIST:
            continue
        text = path.read_text(encoding="utf-8")
        for lineno, line in enumerate(text.splitlines(), 1):
            if FORBIDDEN.search(line):
                offenders.append(f"{rel}:{lineno}: {line.strip()}")
    assert not offenders, (
        "Legacy 'ascmc' chart-dict consumers detected (audit P0 bug class). "
        "The producer in bazi_engine/western.py returns angles under "
        "western['angles'], not 'ascmc'. Replace with western['angles'].get('Ascendant'):\n"
        + "\n".join(offenders)
    )
