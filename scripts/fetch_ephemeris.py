"""Fetch or verify the exact Swiss Ephemeris files in ephemeris.lock.json."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import tempfile
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LOCK = ROOT / "ephemeris.lock.json"
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
_REPOSITORY_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


class EphemerisLockError(RuntimeError):
    """Raised when the lock or a locked file cannot be trusted."""


def authority_payload(lock: dict[str, Any]) -> dict[str, Any]:
    """Return the immutable data covered by lock_id."""
    return {"source": lock.get("source"), "files": lock.get("files")}


def compute_lock_id(lock: dict[str, Any]) -> str:
    raw = json.dumps(authority_payload(lock), sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def validate_lock(lock: dict[str, Any]) -> None:
    if lock.get("schema_version") != 1:
        raise EphemerisLockError("unsupported ephemeris lock schema")
    source = lock.get("source")
    files = lock.get("files")
    if not isinstance(source, dict) or not isinstance(files, list) or not files:
        raise EphemerisLockError("lock must contain source and non-empty files")
    if not _REPOSITORY_RE.fullmatch(str(source.get("repository", ""))):
        raise EphemerisLockError("source repository must be owner/name")
    if not _COMMIT_RE.fullmatch(str(source.get("commit", ""))):
        raise EphemerisLockError("source commit must be a full immutable SHA")
    subdirectory = str(source.get("subdirectory", ""))
    if not subdirectory or subdirectory.startswith("/") or ".." in Path(subdirectory).parts:
        raise EphemerisLockError("source subdirectory is unsafe")

    names: set[str] = set()
    for entry in files:
        if not isinstance(entry, dict):
            raise EphemerisLockError("file entries must be objects")
        name = str(entry.get("name", ""))
        if not name or Path(name).name != name or name in names:
            raise EphemerisLockError(f"unsafe or duplicate file name: {name!r}")
        names.add(name)
        if not isinstance(entry.get("size"), int) or entry["size"] <= 0:
            raise EphemerisLockError(f"invalid size for {name}")
        if not _SHA256_RE.fullmatch(str(entry.get("sha256", ""))):
            raise EphemerisLockError(f"invalid sha256 for {name}")

    actual_id = compute_lock_id(lock)
    if lock.get("lock_id") != actual_id:
        raise EphemerisLockError(f"lock_id mismatch: expected {actual_id}")


def load_lock(path: Path = DEFAULT_LOCK) -> dict[str, Any]:
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise EphemerisLockError(f"cannot load lock {path}: {exc}") from exc
    if not isinstance(loaded, dict):
        raise EphemerisLockError("ephemeris lock root must be an object")
    validate_lock(loaded)
    return loaded


def _looks_like_markup(data: bytes) -> bool:
    prefix = data[:512].lstrip().lower()
    return prefix.startswith(b"<") or b"<html" in prefix or b"<!doctype" in prefix


def verify_bytes(data: bytes, entry: dict[str, Any]) -> None:
    name = entry["name"]
    if _looks_like_markup(data):
        raise EphemerisLockError(f"{name} contains an HTML/XML-like payload")
    if len(data) != entry["size"]:
        raise EphemerisLockError(f"{name} size mismatch: {len(data)} != {entry['size']}")
    digest = hashlib.sha256(data).hexdigest()
    if digest != entry["sha256"]:
        raise EphemerisLockError(f"{name} sha256 mismatch: {digest} != {entry['sha256']}")


def verify_directory(destination: Path, lock: dict[str, Any]) -> None:
    validate_lock(lock)
    for entry in lock["files"]:
        path = destination / entry["name"]
        try:
            data = path.read_bytes()
        except OSError as exc:
            raise EphemerisLockError(f"missing locked ephemeris file: {path}") from exc
        verify_bytes(data, entry)


def _source_url(lock: dict[str, Any], name: str) -> str:
    source = lock["source"]
    return (
        "https://raw.githubusercontent.com/"
        f"{source['repository']}/{source['commit']}/{source['subdirectory']}/{name}"
    )


def fetch_locked_files(destination: Path, lock: dict[str, Any], *, timeout: float = 60.0) -> None:
    """Download every locked file once, verify it, then atomically install it."""
    validate_lock(lock)
    destination.mkdir(parents=True, exist_ok=True)
    for entry in lock["files"]:
        url = _source_url(lock, entry["name"])
        request = urllib.request.Request(url, headers={"User-Agent": "fufire-ephemeris-lock/1"})
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310 - fixed HTTPS host
                data = response.read(entry["size"] + 1)
        except OSError as exc:
            raise EphemerisLockError(f"download failed for locked URL {url}: {exc}") from exc
        verify_bytes(data, entry)
        fd, temporary_name = tempfile.mkstemp(prefix=f".{entry['name']}.", dir=destination)
        temporary_path = Path(temporary_name)
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_path, destination / entry["name"])
        finally:
            temporary_path.unlink(missing_ok=True)
    verify_directory(destination, lock)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lock", type=Path, default=DEFAULT_LOCK)
    parser.add_argument("--destination", type=Path, default=Path("/usr/local/share/swisseph"))
    parser.add_argument("--verify-only", action="store_true")
    parser.add_argument("--print-lock-id", action="store_true")
    args = parser.parse_args()

    lock = load_lock(args.lock)
    if args.print_lock_id:
        print(lock["lock_id"])
    if args.verify_only:
        verify_directory(args.destination, lock)
    else:
        fetch_locked_files(args.destination, lock)
    print(f"OK: verified Swiss Ephemeris lock {lock['lock_id']} at {args.destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
