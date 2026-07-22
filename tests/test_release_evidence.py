from __future__ import annotations

import importlib.util
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "build_release_evidence.py"
SPEC = importlib.util.spec_from_file_location("build_release_evidence", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
builder = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(builder)


def test_release_evidence_is_hash_addressed_and_blocked(tmp_path: Path) -> None:
    for relative in builder.INPUTS:
        destination = tmp_path / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, destination)
    sbom = tmp_path / "sbom.cdx.json"
    sbom.write_text(
        json.dumps({"bomFormat": "CycloneDX", "specVersion": "1.6", "components": []}),
        encoding="utf-8",
    )

    manifest = builder.build_manifest(
        tmp_path,
        commit_sha="a" * 40,
        generated_at="2026-07-21T23:00:00+00:00",
        sbom_path=sbom,
    )

    assert manifest["release_decision"] == "BLOCKED"
    assert manifest["ephemeris"]["lock_id"] == json.loads(
        (ROOT / "ephemeris.lock.json").read_text(encoding="utf-8")
    )["lock_id"]
    assert len(manifest["inputs"]["uv.lock"]["sha256"]) == 64
    assert set(manifest["external_gates"].values()) == {"MISSING"}
    assert manifest["signature"]["status"] == "MISSING"


def test_release_evidence_rejects_non_commit_identifier(tmp_path: Path) -> None:
    try:
        builder.build_manifest(
            tmp_path,
            commit_sha="main",
            generated_at="2026-07-21T23:00:00+00:00",
            sbom_path=tmp_path / "missing.json",
        )
    except ValueError as exc:
        assert "commit SHA" in str(exc)
    else:  # pragma: no cover - explicit failure is clearer than pytest.raises here
        raise AssertionError("expected invalid commit identifier to fail")
