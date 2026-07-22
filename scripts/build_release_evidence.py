"""Build a non-secret, hash-addressed release evidence manifest."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

INPUTS = (
    "pyproject.toml",
    "uv.lock",
    "requirements.lock",
    "package.json",
    "package-lock.json",
    "ephemeris.lock.json",
    "spec/openapi/openapi.json",
    "Dockerfile",
)
SHA40 = re.compile(r"^[0-9a-f]{40}$")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _git(root: Path, *args: str) -> str:
    return subprocess.check_output(
        ["git", *args], cwd=root, text=True, stderr=subprocess.DEVNULL
    ).strip()


def build_manifest(
    root: Path,
    *,
    commit_sha: str,
    generated_at: str,
    sbom_path: Path,
) -> dict[str, object]:
    if not SHA40.fullmatch(commit_sha):
        raise ValueError("commit SHA must be 40 lowercase hexadecimal characters")
    missing = [relative for relative in INPUTS if not (root / relative).is_file()]
    if missing:
        raise FileNotFoundError(f"missing release inputs: {', '.join(missing)}")
    if not sbom_path.is_file():
        raise FileNotFoundError(f"missing SBOM: {sbom_path}")

    ephemeris = json.loads((root / "ephemeris.lock.json").read_text(encoding="utf-8"))
    github_server = os.environ.get("GITHUB_SERVER_URL")
    github_repository = os.environ.get("GITHUB_REPOSITORY")
    github_run_id = os.environ.get("GITHUB_RUN_ID")
    run_url = (
        f"{github_server}/{github_repository}/actions/runs/{github_run_id}"
        if github_server and github_repository and github_run_id
        else None
    )
    try:
        dirty = bool(_git(root, "status", "--porcelain", "--untracked-files=no"))
    except (OSError, subprocess.CalledProcessError):
        dirty = None

    return {
        "schema_version": 1,
        "generated_at": generated_at,
        "release_decision": "BLOCKED",
        "commit_sha": commit_sha,
        "github_run_url": run_url,
        "workspace_dirty": dirty,
        "inputs": {
            relative: {"sha256": _sha256(root / relative)}
            for relative in INPUTS
        },
        "sbom": {
            "path": sbom_path.name,
            "sha256": _sha256(sbom_path),
            "format": "CycloneDX JSON",
        },
        "ephemeris": {
            "lock_id": ephemeris["lock_id"],
            "source_commit": ephemeris["source"]["commit"],
        },
        "external_gates": {
            "branch_protection": "MISSING",
            "release_please_identity_proof": "MISSING",
            "swiss_ephemeris_license": "MISSING",
            "staging": "MISSING",
            "production_promotion": "MISSING",
            "rollback": "MISSING",
        },
        "signature": {"status": "MISSING", "reason": "signing identity is not provisioned"},
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--sbom", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--commit-sha")
    args = parser.parse_args()
    root = args.root.resolve()
    commit_sha = args.commit_sha or os.environ.get("GITHUB_SHA") or _git(root, "rev-parse", "HEAD")
    generated_at = datetime.now(timezone.utc).isoformat()
    manifest = build_manifest(
        root,
        commit_sha=commit_sha,
        generated_at=generated_at,
        sbom_path=args.sbom.resolve(),
    )
    args.output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"OK: wrote blocked release evidence manifest to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
