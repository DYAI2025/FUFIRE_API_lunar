#!/usr/bin/env python3
"""Verify the approved runtime-resource inventory in a wheel or sdist."""

from __future__ import annotations

import argparse
import json
import tarfile
import zipfile
from pathlib import Path, PurePosixPath

SCHEMA_RESOURCES = {
    "bazi_engine/resources/ephemeris.lock.json",
    "bazi_engine/resources/schemas/ErrorEnvelope.schema.json",
    "bazi_engine/resources/schemas/ValidateRequest.schema.json",
    "bazi_engine/resources/schemas/ValidateResponse.schema.json",
    "bazi_engine/resources/schemas/zwds/ZwdsRawResponse.schema.json",
    "bazi_engine/resources/schemas/zwds/ZwdsRequest.schema.json",
    "bazi_engine/resources/rulesets/standard_bazi_2026.json",
}
ZWDS_DATA_FILES = {
    "bureau_table.json",
    "calendar_policy.json",
    "manifest.json",
    "palace_roles.json",
    "placement_rules.json",
    "sources.json",
    "star_catalog.json",
    "time_policy.json",
    "transformations.json",
}
ZWDS_PREFIX = (
    "bazi_engine/data/zwds/rulesets/"
    "zwds.fufire.core-seed.v1/"
)
DATA_RESOURCES = {"bazi_engine/data/affinity_map.json"} | {
    f"{ZWDS_PREFIX}{name}" for name in ZWDS_DATA_FILES
}
EXPECTED_JSON_RESOURCES = SCHEMA_RESOURCES | DATA_RESOURCES
RESOURCE_PREFIXES = ("bazi_engine/resources/", "bazi_engine/data/")


def _archive_names(artifact: Path) -> set[str]:
    if artifact.suffix == ".whl":
        with zipfile.ZipFile(artifact) as archive:
            return set(archive.namelist())
    if artifact.name.endswith(".tar.gz"):
        with tarfile.open(artifact, "r:gz") as archive:
            names = set(archive.getnames())
        roots = {PurePosixPath(name).parts[0] for name in names if name}
        if len(roots) != 1:
            raise SystemExit(f"sdist must have one root directory, found: {roots}")
        return {
            PurePosixPath(*PurePosixPath(name).parts[1:]).as_posix()
            for name in names
            if len(PurePosixPath(name).parts) > 1
        }
    raise SystemExit(f"unsupported distribution artifact: {artifact}")


def verify_artifact(artifact: Path) -> dict[str, object]:
    names = _archive_names(artifact)
    actual = {
        name
        for name in names
        if name.endswith(".json") and name.startswith(RESOURCE_PREFIXES)
    }
    missing = sorted(EXPECTED_JSON_RESOURCES - actual)
    unexpected = sorted(actual - EXPECTED_JSON_RESOURCES)
    root_spec = sorted(name for name in names if name.startswith("spec/"))
    if missing or unexpected or root_spec:
        raise SystemExit(
            json.dumps(
                {
                    "artifact": artifact.name,
                    "missing": missing,
                    "unexpected": unexpected,
                    "forbidden_root_spec": root_spec,
                },
                indent=2,
            )
        )
    return {
        "artifact": artifact.name,
        "approved_json_resources": len(actual),
        "status": "ok",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("artifacts", nargs="+", type=Path)
    args = parser.parse_args()
    reports = [verify_artifact(path) for path in args.artifacts]
    print(json.dumps(reports, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
