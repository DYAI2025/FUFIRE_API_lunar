from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient

from bazi_engine.app import app
from bazi_engine.routers import info

ROOT = Path(__file__).resolve().parents[1]


def test_liveness_stays_200_while_missing_ephemeris_makes_ready_503(monkeypatch) -> None:
    monkeypatch.setattr(
        info,
        "_check_ephemeris",
        lambda: info.DependencyStatus(status="unavailable", required=True, detail="test outage"),
    )
    monkeypatch.setattr(
        info,
        "_check_rate_limiter",
        lambda: info.DependencyStatus(status="ok", required=False, detail="type=memory"),
    )
    client = TestClient(app)

    health = client.get("/health")
    ready = client.get("/ready")

    assert health.status_code == 200
    assert health.json()["status"] == "degraded"
    assert ready.status_code == 503
    assert ready.json()["dependencies"]["ephemeris"]["status"] == "unavailable"


def test_configured_degraded_redis_makes_ready_503(monkeypatch) -> None:
    monkeypatch.setattr(info, "_check_ephemeris", lambda: info.DependencyStatus(status="ok", required=True))
    monkeypatch.setattr(
        info,
        "_check_rate_limiter",
        lambda: info.DependencyStatus(status="degraded", required=True, detail="type=redis"),
    )

    response = TestClient(app).get("/ready")

    assert response.status_code == 503
    assert response.json()["dependencies"]["rate_limiter"]["status"] == "degraded"


def test_optional_single_replica_memory_limiter_does_not_block_readiness(monkeypatch) -> None:
    monkeypatch.setattr(info, "_check_ephemeris", lambda: info.DependencyStatus(status="ok", required=True))
    monkeypatch.setattr(
        info,
        "_check_rate_limiter",
        lambda: info.DependencyStatus(status="ok", required=False, detail="type=memory"),
    )

    assert TestClient(app).get("/ready").status_code == 200


def test_rate_limiter_status_never_exposes_configured_redis_uri(monkeypatch) -> None:
    from bazi_engine import limiter as limiter_module

    secret_uri = "redis://user:secret@example.invalid:6379/0"
    monkeypatch.setattr(limiter_module, "_storage_uri", secret_uri)
    monkeypatch.setattr(limiter_module, "_redis_is_required", True)
    monkeypatch.setattr(limiter_module, "limiter", SimpleNamespace(_storage=SimpleNamespace(check=lambda: False)))

    status = limiter_module.get_storage_status()

    assert status == {"type": "redis", "status": "degraded", "required": True, "configured": True}
    assert secret_uri not in repr(status)


def test_railway_uses_readiness_not_liveness() -> None:
    railway = (ROOT / "railway.toml").read_text(encoding="utf-8")

    assert 'healthcheckPath = "/ready"' in railway
