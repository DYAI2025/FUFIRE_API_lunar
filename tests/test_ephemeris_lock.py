from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "fetch_ephemeris.py"
SPEC = importlib.util.spec_from_file_location("fetch_ephemeris", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
fetch_ephemeris = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(fetch_ephemeris)


def _lock_for(name: str, data: bytes) -> dict[str, object]:
    lock: dict[str, object] = {
        "schema_version": 1,
        "source": {
            "repository": "aloistr/swisseph",
            "commit": "2f18c14c37ecf96264e87b2b6ed67b2028ae0c96",
            "subdirectory": "ephe",
        },
        "files": [{"name": name, "size": len(data), "sha256": hashlib.sha256(data).hexdigest()}],
        "policy": {"network_fallback": False},
    }
    lock["lock_id"] = fetch_ephemeris.compute_lock_id(lock)
    return lock


def test_committed_lock_is_self_consistent() -> None:
    lock = fetch_ephemeris.load_lock(ROOT / "ephemeris.lock.json")

    assert lock["source"]["commit"] == "2f18c14c37ecf96264e87b2b6ed67b2028ae0c96"
    assert len(lock["files"]) == 4
    assert lock["policy"]["network_fallback"] is False


def test_lock_rejects_mutable_or_short_commit() -> None:
    lock = _lock_for("test.se1", b"binary")
    lock["source"]["commit"] = "master"
    lock["lock_id"] = fetch_ephemeris.compute_lock_id(lock)

    with pytest.raises(fetch_ephemeris.EphemerisLockError, match="full immutable SHA"):
        fetch_ephemeris.validate_lock(lock)


def test_verify_rejects_missing_file(tmp_path: Path) -> None:
    lock = _lock_for("missing.se1", b"binary")

    with pytest.raises(fetch_ephemeris.EphemerisLockError, match="missing locked"):
        fetch_ephemeris.verify_directory(tmp_path, lock)


@pytest.mark.parametrize("payload", [b"wrong-size", b"<html>not ephemeris</html>"])
def test_verify_rejects_size_hash_or_markup(tmp_path: Path, payload: bytes) -> None:
    expected = b"trusted-binary-payload"
    lock = _lock_for("test.se1", expected)
    (tmp_path / "test.se1").write_bytes(payload)

    with pytest.raises(fetch_ephemeris.EphemerisLockError):
        fetch_ephemeris.verify_directory(tmp_path, lock)


def test_load_rejects_tampered_lock_id(tmp_path: Path) -> None:
    lock = _lock_for("test.se1", b"trusted-binary-payload")
    lock["files"][0]["size"] += 1
    path = tmp_path / "lock.json"
    path.write_text(json.dumps(lock), encoding="utf-8")

    with pytest.raises(fetch_ephemeris.EphemerisLockError, match="lock_id mismatch"):
        fetch_ephemeris.load_lock(path)


def test_verify_accepts_exact_locked_bytes(tmp_path: Path) -> None:
    data = b"trusted-binary-payload"
    lock = _lock_for("test.se1", data)
    (tmp_path / "test.se1").write_bytes(data)

    fetch_ephemeris.verify_directory(tmp_path, lock)
