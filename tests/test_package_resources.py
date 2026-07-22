from __future__ import annotations

import json
from pathlib import Path

import pytest

from bazi_engine import resource_loader
from bazi_engine.resource_loader import (
    PackageResourceIntegrityError,
    PackageResourceNotFoundError,
    load_json_object_resource,
    package_resource,
)

ROOT = Path(__file__).resolve().parents[1]
MIRRORS = {
    ROOT / "ephemeris.lock.json": package_resource(
        "bazi_engine.resources", "ephemeris.lock.json"
    ),
    ROOT / "spec/schemas/ErrorEnvelope.schema.json": package_resource(
        "bazi_engine.resources", "schemas", "ErrorEnvelope.schema.json"
    ),
    ROOT / "spec/schemas/ValidateRequest.schema.json": package_resource(
        "bazi_engine.resources", "schemas", "ValidateRequest.schema.json"
    ),
    ROOT / "spec/schemas/ValidateResponse.schema.json": package_resource(
        "bazi_engine.resources", "schemas", "ValidateResponse.schema.json"
    ),
    ROOT / "spec/schemas/zwds/ZwdsRequest.schema.json": package_resource(
        "bazi_engine.resources", "schemas", "zwds", "ZwdsRequest.schema.json"
    ),
    ROOT / "spec/schemas/zwds/ZwdsRawResponse.schema.json": package_resource(
        "bazi_engine.resources",
        "schemas",
        "zwds",
        "ZwdsRawResponse.schema.json",
    ),
    ROOT / "spec/rulesets/standard_bazi_2026.json": package_resource(
        "bazi_engine.resources", "rulesets", "standard_bazi_2026.json"
    ),
}


@pytest.mark.parametrize(("source", "resource"), MIRRORS.items())
def test_runtime_resource_mirror_is_semantically_identical(source, resource):
    assert json.loads(resource.read_bytes()) == json.loads(source.read_bytes())


@pytest.mark.parametrize("part", ["", ".", "..", "../secret", "a/b", "a\\b"])
def test_package_resource_rejects_unsafe_components(part):
    with pytest.raises(ValueError):
        package_resource("bazi_engine.resources", part)


def test_missing_required_resource_fails_closed(tmp_path, monkeypatch):
    monkeypatch.setattr(resource_loader, "files", lambda _package: tmp_path)
    with pytest.raises(PackageResourceNotFoundError, match="required package resource"):
        load_json_object_resource("example.package", "missing.json")


def test_corrupt_required_resource_fails_closed(tmp_path, monkeypatch):
    (tmp_path / "broken.json").write_text("{not-json", encoding="utf-8")
    monkeypatch.setattr(resource_loader, "files", lambda _package: tmp_path)
    with pytest.raises(PackageResourceIntegrityError, match="not valid UTF-8 JSON"):
        load_json_object_resource("example.package", "broken.json")


def test_non_object_required_resource_fails_closed(tmp_path, monkeypatch):
    (tmp_path / "array.json").write_text("[]", encoding="utf-8")
    monkeypatch.setattr(resource_loader, "files", lambda _package: tmp_path)
    with pytest.raises(PackageResourceIntegrityError, match="not a JSON object"):
        load_json_object_resource("example.package", "array.json")
