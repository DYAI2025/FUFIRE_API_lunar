from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from bazi_engine.app import app
from bazi_engine.features import FEATURE_MATRIX, feature_enabled
from bazi_engine.openapi_ext import install_custom_openapi
from bazi_engine.routers.registry import mount_all


def _fresh_openapi() -> dict:
    candidate = FastAPI(title="feature-matrix-test", version="test")
    mount_all(candidate)
    install_custom_openapi(candidate)
    return candidate.openapi()


def test_conditional_features_are_disabled_by_default(monkeypatch) -> None:
    for decision in FEATURE_MATRIX.values():
        monkeypatch.delenv(decision.env_var, raising=False)
        assert decision.default_enabled is False
        assert feature_enabled(decision.feature_id) is False


def test_disabled_conditional_routes_are_hidden_and_return_404(monkeypatch) -> None:
    monkeypatch.delenv("FUFIRE_ENABLE_KEY_ISSUANCE", raising=False)
    monkeypatch.delenv("FUFIRE_ENABLE_ZWDS", raising=False)
    client = TestClient(app, raise_server_exceptions=False)

    issue = client.post(
        "/v1/admin/keys",
        json={"tier": "free", "label": "x", "jti": "disabled"},
    )
    metadata = client.get(
        "/v1/metadata/zwds/rulesets/zwds.fufire.core-seed.v1"
    )

    assert issue.status_code == 404
    assert issue.json()["error"] == "feature_disabled"
    assert metadata.status_code == 404
    assert metadata.json()["error"] == "feature_disabled"

    spec = _fresh_openapi()
    assert "/v1/admin/keys" not in spec["paths"]
    assert "/v1/calculate/zwds" not in spec["paths"]
    assert "/v1/metadata/zwds/rulesets/{ruleset_id}" not in spec["paths"]


def test_explicit_dev_flags_restore_routes_and_openapi(monkeypatch) -> None:
    monkeypatch.setenv("FUFIRE_ENABLE_KEY_ISSUANCE", "true")
    monkeypatch.setenv("FUFIRE_ENABLE_ZWDS", "true")
    monkeypatch.delenv("KEY_STORE_BACKEND", raising=False)
    monkeypatch.delenv("FUFIRE_ADMIN_TOKEN", raising=False)
    client = TestClient(app, raise_server_exceptions=False)

    issue = client.post(
        "/v1/admin/keys",
        json={"tier": "free", "label": "x", "jti": "enabled"},
    )
    metadata = client.get(
        "/v1/metadata/zwds/rulesets/zwds.fufire.core-seed.v1"
    )

    assert issue.status_code == 503  # feature passed; issuance config did not
    assert metadata.status_code == 200

    spec = _fresh_openapi()
    assert spec["paths"]["/v1/admin/keys"]["post"]["deprecated"] is True
    assert "/v1/calculate/zwds" in spec["paths"]
    assert "/v1/metadata/zwds/rulesets/{ruleset_id}" in spec["paths"]


def test_v2_lunar_contract_is_not_marked_legacy_deprecated(monkeypatch) -> None:
    monkeypatch.delenv("FUFIRE_ENABLE_KEY_ISSUANCE", raising=False)
    monkeypatch.delenv("FUFIRE_ENABLE_ZWDS", raising=False)
    operation = _fresh_openapi()["paths"]["/v2/astronomy/lunar-state"]["post"]

    assert operation.get("deprecated") is not True
