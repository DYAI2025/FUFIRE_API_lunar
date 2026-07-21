"""
test_openapi_schema.py — Spec truth: servers list and legacy deprecation.

These tests pin two facts about the served /openapi.json:
  - The servers list names ONLY live deployments (Railway); the old Fly.io
    and Cloud Run URLs are decommissioned and must never reappear.
  - Every legacy (non-/v1) operation carries deprecated:true; /v1 is the
    canonical surface and must never be deprecated.

The landingpage repo mirrors the deprecation rule fail-closed in
tests/unit/openapi-legacy-deprecated.test.ts — a regression here breaks
the sibling repo's gate after the next spec sync.
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from bazi_engine.app import app

client = TestClient(app)


def test_servers_list_names_only_live_deployments():
    """The spec must not advertise dead deployments (old Fly URL) — clients
    and the landingpage BFF take this list as authority."""
    schema = client.get("/openapi.json").json()
    urls = [s["url"] for s in schema["servers"]]
    assert "https://api.fufire.space" in urls
    assert not any("fly.dev" in u for u in urls), urls
    assert not any("run.app" in u for u in urls), urls


HTTP_METHODS = {"get", "put", "post", "delete", "options", "head", "patch", "trace"}


def test_legacy_unversioned_operations_are_deprecated():
    """The unversioned path family is legacy; /v1 is canonical. Every legacy
    operation must carry deprecated:true so generated clients and the docs
    portal steer to /v1. The landingpage repo has a fail-closed mirror
    (tests/unit/openapi-legacy-deprecated.test.ts)."""
    schema = client.get("/openapi.json").json()
    offenders = []
    for path, methods in schema["paths"].items():
        if path == "/" or path.startswith("/v1"):
            continue
        for method, op in methods.items():
            if method in HTTP_METHODS and isinstance(op, dict) and op.get("deprecated") is not True:
                offenders.append(f"{method.upper()} {path}")
    assert offenders == [], offenders


def test_v1_operations_are_not_deprecated():
    schema = client.get("/openapi.json").json()
    wrongly = []
    for path, methods in schema["paths"].items():
        if not path.startswith("/v1"):
            continue
        for method, op in methods.items():
            if method in HTTP_METHODS and isinstance(op, dict) and op.get("deprecated") is True:
                wrongly.append(f"{method.upper()} {path}")
    assert wrongly == [], wrongly
