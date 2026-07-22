from __future__ import annotations

import json
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - exercised by the Python 3.10 CI lane
    import tomli as tomllib

ROOT = Path(__file__).resolve().parents[1]
BASELINE_VERSION = "1.5.0"
BOOTSTRAP_SHA = "fe8f0198f6a4bda1568d986bf8aac06efe4e123c"


def test_package_and_release_manifest_share_reconstructed_baseline() -> None:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    manifest = json.loads((ROOT / ".release-please-manifest.json").read_text(encoding="utf-8"))

    assert pyproject["project"]["version"] == BASELINE_VERSION
    assert manifest["."] == BASELINE_VERSION


def test_release_please_bootstrap_is_reachable_lunar_baseline() -> None:
    config = json.loads((ROOT / "release-please-config.json").read_text(encoding="utf-8"))

    assert config["bootstrap-sha"] == BOOTSTRAP_SHA


def test_changelog_preserves_canonical_source_provenance() -> None:
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")

    assert "## [1.5.0]" in changelog
    assert "github.com/DYAI2025/FuFirE/compare/v1.4.0...v1.5.0" in changelog
    assert "no\ntags or commits have been fabricated" in changelog


def test_lunar_target_version_is_explicit_but_not_auto_approved() -> None:
    adr = (ROOT / "docs/adr/ADR-003-lunar-release-baseline.md").read_text(encoding="utf-8")

    assert "Target 1.6.0" in adr
    assert "Product-owner approval remains MISSING" in adr
