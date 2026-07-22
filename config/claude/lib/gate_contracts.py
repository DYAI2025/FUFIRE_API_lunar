"""Helpers for loading Claude gate contract fixture manifests.

The roster fallback parser in this module is intentionally tiny so the gate
contracts can be checked in environments that do not have PyYAML installed.
It is only intended for known roster fixture manifests with top-level role
lists; install PyYAML for general YAML support.
"""
from __future__ import annotations

import importlib
import importlib.util
from pathlib import Path
from typing import Any

yaml = importlib.import_module("yaml") if importlib.util.find_spec("yaml") else None


def _strip_unquoted_comment(line: str) -> str:
    """Remove a trailing comment marker only when it is outside quotes."""
    comment_index = None
    in_single = False
    in_double = False
    escape = False
    for idx, ch in enumerate(line):
        if escape:
            escape = False
            continue
        if ch == "\\":
            escape = True
            continue
        if ch == "'" and not in_double:
            in_single = not in_single
            continue
        if ch == '"' and not in_single:
            in_double = not in_double
            continue
        if ch == "#" and not in_single and not in_double:
            comment_index = idx
            break
    if comment_index is not None:
        line = line[:comment_index]
    return line.rstrip()


def _strip_single_enclosing_quote_pair(value: str) -> str:
    """Remove one matching quote pair; preserve literal boundary quotes."""
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def _load_simple_roster_manifest(path: Path) -> dict[str, list[str]]:
    """Load the restricted roster YAML subset used by known fixtures.

    Supported shape::

        role_group:
          - role-name
          - "role # with literal hash"

    This fallback deliberately rejects richer YAML so unsupported syntax does
    not get misparsed when PyYAML is unavailable.
    """
    data: dict[str, list[str]] = {}
    current: str | None = None
    for lineno, original in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = _strip_unquoted_comment(original)
        if not line.strip():
            continue
        if not line.startswith(" ") and line.endswith(":"):
            current = line[:-1].strip()
            if not current:
                raise ValueError(f"empty roster section on line {lineno}")
            data[current] = []
            continue
        stripped = line.strip()
        if stripped.startswith("- ") and current is not None:
            role = _strip_single_enclosing_quote_pair(stripped[2:].strip())
            if not role:
                raise ValueError(f"empty roster role on line {lineno}")
            data[current].append(role)
            continue
        raise ValueError(
            f"unsupported roster YAML on line {lineno}: {original} "
            "(the built-in simple parser only supports a limited subset of roster YAML; "
            "install PyYAML to use full YAML syntax)"
        )
    return data


def _load_manifest(path: Path) -> dict[str, Any]:
    """Load a manifest, falling back to a restricted roster fixture parser.

    The fallback is intentionally scoped to known roster fixture manifests.
    Maintainers expanding the roster format should add PyYAML to the execution
    environment or update the parser and its tests together.
    """
    if yaml is None:
        return _load_simple_roster_manifest(path)
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise ValueError(f"manifest must be a mapping: {path}")
    return loaded
