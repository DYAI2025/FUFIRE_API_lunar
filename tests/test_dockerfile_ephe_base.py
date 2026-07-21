from __future__ import annotations

from pathlib import Path


def test_dockerfile_builds_ephemeris_internally_with_integrity_checks() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    dockerfile = (repo_root / "Dockerfile").read_text(encoding="utf-8")

    assert (
        "FROM python:3.12-slim@sha256:"
        "57cd7c3a7a273101a6485ba99423ee568157882804b1124b4dd04266317710de AS ephe"
    ) in dockerfile
    assert "COPY --from=ephe /usr/local/share/swisseph /usr/local/share/swisseph" in dockerfile

    # The lock-aware fetcher owns the filename, size, and SHA-256 checks.
    assert "scripts/fetch_ephemeris.py" in dockerfile
    assert "--verify-only" in dockerfile


def test_runtime_installs_verified_wheel_without_source_tree() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    dockerfile = (repo_root / "Dockerfile").read_text(encoding="utf-8")

    assert "python -m build --wheel --no-isolation" in dockerfile
    assert "scripts/verify_distribution.py" in dockerfile
    assert "COPY --from=builder /install /usr/local" in dockerfile
    assert "COPY spec/" not in dockerfile
    assert "COPY bazi_engine/ ./bazi_engine/" in dockerfile  # builder only
    assert "USER 10001:10001" in dockerfile
    assert "uv export" in dockerfile
    assert "--frozen" in dockerfile
    assert "--require-hashes" in dockerfile
    assert "--ignore-installed" in dockerfile
    assert "pip install --no-cache-dir --no-deps" in dockerfile
    assert "packaging==26.0" in dockerfile
    assert "pyproject-hooks==1.2.0" in dockerfile
    assert "pyswisseph does not publish a CPython 3.12 Linux wheel" in dockerfile
