from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_ci_and_docker_share_the_canonical_ephemeris_lock() -> None:
    ci = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    docker = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    ephe_base = (ROOT / "Dockerfile.ephe-base").read_text(encoding="utf-8")

    assert "hashFiles('ephemeris.lock.json')" in ci
    assert "scripts/fetch_ephemeris.py" in ci
    assert "COPY ephemeris.lock.json" in docker
    assert "COPY scripts/fetch_ephemeris.py" in docker
    assert "COPY ephemeris.lock.json" in ephe_base
    assert "COPY scripts/fetch_ephemeris.py" in ephe_base


def test_release_inputs_have_no_mutable_ephemeris_fallback() -> None:
    consumers = "\n".join(
        (ROOT / path).read_text(encoding="utf-8")
        for path in (".github/workflows/ci.yml", "Dockerfile", "Dockerfile.ephe-base")
    )

    assert "aloistr/swisseph/master" not in consumers
    assert "SWISSEPH_REF=master" not in consumers
    assert 'refs="${SWISSEPH_REF} master"' not in consumers


def test_release_ci_never_generates_expected_snapshots() -> None:
    ci = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")

    assert "UPDATE_SNAPSHOTS=1" not in ci
    assert "Generate SWIEPH snapshots if missing" not in ci


def test_snapshot_updates_are_manual_lock_bound_and_review_only() -> None:
    workflow = (ROOT / ".github/workflows/update-swieph-snapshots.yml").read_text(encoding="utf-8")

    assert "workflow_dispatch:" in workflow
    assert "scripts/fetch_ephemeris.py" in workflow
    assert 'UPDATE_SNAPSHOTS: "1"' in workflow
    assert "contents: read" in workflow
    assert "snapshot-update.patch" in workflow
    assert "git push" not in workflow


def test_ephemeris_base_is_not_published_as_latest_release_input() -> None:
    workflow = (ROOT / ".github/workflows/build-ephe-base.yml").read_text(encoding="utf-8")

    assert "ephe-base:latest" not in workflow
    assert "ephe-base:${{ github.sha }}" in workflow
