"""Fail-closed access to files shipped inside the Python distribution.

Runtime code must not depend on a repository checkout.  This module is the
single boundary for package resources and deliberately reports missing or
malformed required data instead of substituting fabricated defaults.
"""

from __future__ import annotations

import json
import sys
from importlib.resources import files
from typing import Any

if sys.version_info >= (3, 11):
    from importlib.resources.abc import Traversable
else:  # pragma: no cover - exercised by the Python 3.10 distribution job
    from importlib.resources import Traversable  # type: ignore[attr-defined]


class PackageResourceError(RuntimeError):
    """Base error for an unusable required package resource."""


class PackageResourceNotFoundError(FileNotFoundError):
    """A required resource is absent from the installed distribution."""


class PackageResourceIntegrityError(PackageResourceError):
    """A required resource exists but cannot be decoded or validated."""


def package_resource(package: str, *parts: str) -> Traversable:
    """Return a safe ``Traversable`` below ``package``.

    Each path component must be a literal child name.  Rejecting separators
    and dot-segments keeps callers from accidentally reintroducing a
    repository-relative or traversal-based resource lookup.
    """

    if not parts:
        raise ValueError("at least one package-resource component is required")
    for part in parts:
        if not part or part in {".", ".."} or "/" in part or "\\" in part:
            raise ValueError(f"unsafe package-resource component: {part!r}")

    resource = files(package)
    for part in parts:
        resource = resource.joinpath(part)
    return resource


def read_package_bytes(package: str, *parts: str) -> bytes:
    """Read a required resource or raise a stable, package-relative error."""

    resource_id = f"{package}:{'/'.join(parts)}"
    resource = package_resource(package, *parts)
    if not resource.is_file():
        raise PackageResourceNotFoundError(
            f"required package resource is missing: {resource_id}"
        )
    try:
        return resource.read_bytes()
    except OSError as exc:
        raise PackageResourceIntegrityError(
            f"required package resource is unreadable: {resource_id}"
        ) from exc


def load_json_resource(package: str, *parts: str) -> Any:
    """Decode a required UTF-8 JSON resource without a silent fallback."""

    resource_id = f"{package}:{'/'.join(parts)}"
    raw = read_package_bytes(package, *parts)
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PackageResourceIntegrityError(
            f"required package resource is not valid UTF-8 JSON: {resource_id}"
        ) from exc


def load_json_object_resource(package: str, *parts: str) -> dict[str, Any]:
    """Load a required JSON object, rejecting arrays and scalar documents."""

    resource_id = f"{package}:{'/'.join(parts)}"
    value = load_json_resource(package, *parts)
    if not isinstance(value, dict):
        raise PackageResourceIntegrityError(
            f"required package resource is not a JSON object: {resource_id}"
        )
    return value
