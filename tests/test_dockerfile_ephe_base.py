from __future__ import annotations

from pathlib import Path


def test_dockerfile_builds_ephemeris_internally_with_integrity_checks() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    dockerfile = (repo_root / "Dockerfile").read_text(encoding="utf-8")

    assert "FROM debian:bookworm-slim AS ephe" in dockerfile
    assert "COPY --from=ephe /usr/local/share/swisseph /usr/local/share/swisseph" in dockerfile

    # Ensure we keep checksum verification to preserve deterministic, trusted ephemeris data.
    assert "sha256sum -c -" in dockerfile

    for filename in ("sepl_18.se1", "semo_18.se1", "seas_18.se1", "seplm06.se1"):
        assert filename in dockerfile
