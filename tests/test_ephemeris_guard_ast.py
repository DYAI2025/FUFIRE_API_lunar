"""
test_ephemeris_guard_ast.py — AC-01-5 static guard (FQ-ATT-01) + VCHK-04 self-test.

Feature:      fufire-premium-verification-ci (WS-A increment)
PRD:          docs/prd/fufire-premium-verification-ci.prd.md (FQ-ATT-01, AC-01-5, §6.3)
Vision:       docs/vision/fufire-premium-verification-ci.vision.md (VCHK-04)

AC-01-5: an AST/grep guard scanning `bazi_engine/` (excluding `ephemeris.py`) must find
zero direct calls to `swe.calc*`, `swe.houses*`, or `swe.fixstar*`, and fail the build if
any exist.

VCHK-04 (the spec-auditor's own remediation instruction, carried into this PRD/Vision):
"The AST/grep static guard is proven to actually catch violations: run it against a
deliberately, temporarily reintroduced direct call ... and confirm it fails the build —
not just confirmed green against the current already-clean tree." A guard that has never
been proven to catch anything is exactly the "partial-coverage-disguised-as-complete" risk
this Vision names first. This file therefore has TWO independent concerns, tested
separately so neither can hide behind the other:

  1. `TestGuardDetectorCorrectness` — the detector logic itself, run against small
     synthetic fixtures (never the real tree). These tests do NOT depend on the current
     state of `bazi_engine/` and must ALWAYS pass, today and after implementation — they
     are what proves the guard is not vacuous.
  2. `TestGuardAgainstRealTree` — the guard run against the actual repo. This is EXPECTED
     TO FAIL today (western.py:64,93; transit.py:131; routers/info.py:90 are real,
     confirmed, currently-uncentralized direct calls per PRD §3.1) and is expected to turn
     green only once T4 (migration) is complete. Do not weaken this assertion or add an
     exclude-list entry for these files to make it pass early — that would defeat the
     guard's entire purpose.
"""
from __future__ import annotations

import ast
import textwrap
from pathlib import Path
from typing import List, NamedTuple, Set

REPO_ROOT = Path(__file__).resolve().parents[1]
ENGINE_ROOT = REPO_ROOT / "bazi_engine"

# The one file allowed to hold direct swe.calc*/houses*/fixstar* calls once
# FQ-ATT-01 is implemented (PRD §6.3: "Zero direct ... calls outside
# bazi_engine/ephemeris.py"). Matched by filename, not by the alias used to
# import swisseph in it -- ephemeris.py IS the centralization boundary itself.
GUARDED_MODULE_NAME = "ephemeris.py"

# Attribute-name prefixes that count as a guarded family. `swe.SUN`/`swe.FLG_SWIEPH`
# (plain attribute access, not a call) must NOT be flagged -- only ast.Call nodes
# whose func resolves to one of these families are violations.
_GUARDED_PREFIXES = ("calc", "houses", "fixstar")


class Violation(NamedTuple):
    file: str
    lineno: int
    call: str


def _swisseph_aliases(tree: ast.Module) -> Set[str]:
    """Collect every local name bound to the `swisseph` module in this file,
    at ANY scope (module-level `import swisseph as swe`, or a local import
    inside a function body such as routers/info.py's `_check_ephemeris()`)."""
    aliases: Set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "swisseph":
                    aliases.add(alias.asname or alias.name)
    return aliases


def _find_violations_in_source(source: str, filename: str) -> List[Violation]:
    """Parse `source` and return every direct call to `<swisseph-alias>.<calc|houses|fixstar>*`.

    This is the reusable detector under test by both test classes below.
    """
    tree = ast.parse(source, filename=filename)
    aliases = _swisseph_aliases(tree)
    if not aliases:
        return []

    violations: List[Violation] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not isinstance(func, ast.Attribute):
            continue
        if not isinstance(func.value, ast.Name):
            continue
        if func.value.id not in aliases:
            continue
        if any(func.attr.startswith(prefix) for prefix in _GUARDED_PREFIXES):
            violations.append(Violation(file=filename, lineno=node.lineno, call=f"{func.value.id}.{func.attr}"))
    return violations


def _scan_tree(root: Path, *, exclude_filenames: Set[str]) -> List[Violation]:
    violations: List[Violation] = []
    for path in sorted(root.rglob("*.py")):
        if path.name in exclude_filenames:
            continue
        if "__pycache__" in path.parts:
            continue
        source = path.read_text(encoding="utf-8")
        try:
            rel = str(path.relative_to(REPO_ROOT))
        except ValueError:
            rel = str(path.relative_to(root))
        violations.extend(_find_violations_in_source(source, rel))
    return violations


# ---------------------------------------------------------------------------
# 1. Detector correctness — synthetic fixtures only (VCHK-04)
# ---------------------------------------------------------------------------


class TestGuardDetectorCorrectness:
    """Proves the guard can actually catch a violation, independent of the
    real tree's current (clean or dirty) state. These must always be green."""

    def test_detects_direct_calc_ut_call(self):
        source = textwrap.dedent(
            """
            import swisseph as swe

            def bad():
                return swe.calc_ut(2451545.0, swe.SUN, swe.FLG_SWIEPH)
            """
        )
        violations = _find_violations_in_source(source, "synthetic_violation.py")
        assert len(violations) == 1
        assert violations[0].call == "swe.calc_ut"

    def test_detects_direct_houses_call(self):
        source = textwrap.dedent(
            """
            import swisseph as swe

            def bad():
                return swe.houses(2451545.0, 52.52, 13.405, b'P')
            """
        )
        violations = _find_violations_in_source(source, "synthetic_violation.py")
        assert len(violations) == 1
        assert violations[0].call == "swe.houses"

    def test_detects_direct_fixstar_call(self):
        source = textwrap.dedent(
            """
            import swisseph as swe

            def bad():
                return swe.fixstar_ut("Aldebaran", 2451545.0)
            """
        )
        violations = _find_violations_in_source(source, "synthetic_violation.py")
        assert len(violations) == 1
        assert violations[0].call == "swe.fixstar_ut"

    def test_detects_violation_from_local_import_inside_function(self):
        """Mirrors the real routers/info.py:90 shape: `import swisseph as swe`
        INSIDE a function body, not at module level."""
        source = textwrap.dedent(
            """
            def _check_ephemeris():
                import swisseph as swe
                jd = swe.julday(2000, 1, 1, 12.0)
                swe.calc_ut(jd, swe.SUN)
            """
        )
        violations = _find_violations_in_source(source, "synthetic_local_import.py")
        assert len(violations) == 1
        assert violations[0].call == "swe.calc_ut"

    def test_does_not_flag_plain_attribute_access(self):
        """`swe.SUN`, `swe.FLG_SWIEPH` etc. are attribute reads, not calls —
        must never be flagged (a naive string-grep guard would over-fire here;
        this is why the guard is AST-based, not regex-based)."""
        source = textwrap.dedent(
            """
            import swisseph as swe

            PLANETS = {"Sun": swe.SUN, "Moon": swe.MOON}
            FLAGS = swe.FLG_SWIEPH | swe.FLG_SPEED
            """
        )
        violations = _find_violations_in_source(source, "synthetic_attrs_only.py")
        assert violations == []

    def test_does_not_flag_calc_family_calls_via_a_different_alias(self):
        """A call named `.calc_ut` on an object that is NOT bound to the
        `swisseph` import must not be flagged — proves the detector resolves
        the alias, it does not pattern-match on the method name alone."""
        source = textwrap.dedent(
            """
            class Unrelated:
                def calc_ut(self, *a, **kw):
                    return None

            def fine():
                obj = Unrelated()
                return obj.calc_ut(1, 2, 3)
            """
        )
        violations = _find_violations_in_source(source, "synthetic_unrelated_calc_ut.py")
        assert violations == []

    def test_scan_tree_excludes_only_the_named_guarded_file(self, tmp_path):
        """The directory-level exclude must be scoped to the exact guarded
        filename, not silently swallow any other file — proves the exclude
        list itself cannot be a blind spot (part of VCHK-04's intent)."""
        pkg = tmp_path / "pkg"
        pkg.mkdir()
        violation_src = "import swisseph as swe\nswe.calc_ut(1, 2, 3)\n"

        (pkg / "ephemeris.py").write_text(violation_src)  # excluded -- the real guard boundary
        (pkg / "not_ephemeris.py").write_text(violation_src)  # NOT excluded -- must be caught

        found = _scan_tree(pkg, exclude_filenames={"ephemeris.py"})
        found_files = {v.file for v in found}
        assert any(f.endswith("not_ephemeris.py") for f in found_files), (
            f"guard must catch a violation in a non-excluded file, found: {found}"
        )
        assert not any(f.endswith("pkg/ephemeris.py") or f == "ephemeris.py" for f in found_files), (
            f"guard must not flag the guarded ephemeris.py file itself, found: {found}"
        )


# ---------------------------------------------------------------------------
# 2. Guard applied to the real tree (AC-01-5) — expected RED until T4 lands
# ---------------------------------------------------------------------------


class TestGuardAgainstRealTree:
    def test_zero_direct_calls_outside_ephemeris_py(self):
        violations = _scan_tree(ENGINE_ROOT, exclude_filenames={GUARDED_MODULE_NAME})
        assert violations == [], (
            "Found direct swe.calc*/houses*/fixstar* calls outside "
            "bazi_engine/ephemeris.py (must be migrated per FQ-ATT-01/T4 before "
            "this passes):\n"
            + "\n".join(f"  {v.file}:{v.lineno} -> {v.call}" for v in violations)
        )
