"""Integration tests for /experience/* endpoints."""
from fastapi.testclient import TestClient

from bazi_engine.app import app

client = TestClient(app)

BIRTH = {
    "date": "1990-08-14",
    "time": "07:42:00",
    "tz": "Europe/Berlin",
    "lat": 53.5511,
    "lon": 9.9937,
    "place_label": "Hamburg, DE",
}


class TestBootstrap:
    def test_returns_200(self):
        resp = client.post("/experience/bootstrap", json={"birth": BIRTH, "locale": "de-DE"})
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert "profile" in data
        assert "soulprint_sectors" in data
        assert len(data["soulprint_sectors"]) == 12
        assert "signature_blueprint" in data
        assert data["signature_blueprint"]["seed"].startswith("sig_v1_")

    def test_profile_has_required_fields(self):
        resp = client.post("/experience/bootstrap", json={"birth": BIRTH})
        data = resp.json()
        profile = data["profile"]
        assert "sun_sign" in profile
        assert "moon_sign" in profile
        assert "ascendant_sign" in profile
        assert "day_master" in profile
        assert 0 <= profile["harmony_index"] <= 1

    def test_soulprint_sums_to_one(self):
        resp = client.post("/experience/bootstrap", json={"birth": BIRTH})
        sectors = resp.json()["soulprint_sectors"]
        assert abs(sum(sectors) - 1.0) < 0.01

    def test_blueprint_has_visual_params(self):
        resp = client.post("/experience/bootstrap", json={"birth": BIRTH})
        bp = resp.json()["signature_blueprint"]
        assert bp["visual"] is not None
        for key in ("symmetry", "curvature", "angularity", "density", "contrast"):
            assert 0 <= bp["visual"][key] <= 1
        assert 1 <= bp["visual"]["orbit_count"] <= 7

    def test_invalid_lat_returns_422(self):
        bad_birth = {**BIRTH, "lat": 999}
        resp = client.post("/experience/bootstrap", json={"birth": bad_birth})
        assert resp.status_code == 422

    def test_german_locale_returns_german_signs(self):
        resp = client.post("/experience/bootstrap", json={"birth": BIRTH, "locale": "de-DE"})
        profile = resp.json()["profile"]
        # Verify sign is in German (one of the German sign names)
        german_signs = {"Widder", "Stier", "Zwillinge", "Krebs", "Loewe", "Jungfrau",
                        "Waage", "Skorpion", "Schuetze", "Steinbock", "Wassermann", "Fische"}
        assert profile["sun_sign"] in german_signs
        assert profile["moon_sign"] in german_signs
        assert profile["ascendant_sign"] in german_signs


class TestSignatureDelta:
    def _bootstrap(self):
        return client.post("/experience/bootstrap", json={"birth": BIRTH}).json()

    def test_returns_200(self):
        boot = self._bootstrap()
        resp = client.post("/experience/signature-delta", json={
            "soulprint_sectors": boot["soulprint_sectors"],
            "signature_blueprint": boot["signature_blueprint"],
            "quiz_answer": {"keyword": "expression"},
        })
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert "quiz_sectors" in data
        assert len(data["quiz_sectors"]) == 12
        assert "signature_delta" in data
        assert "signature_blueprint" in data

    def test_different_keywords_different_deltas(self):
        boot = self._bootstrap()
        r1 = client.post("/experience/signature-delta", json={
            "soulprint_sectors": boot["soulprint_sectors"],
            "signature_blueprint": boot["signature_blueprint"],
            "quiz_answer": {"keyword": "expression"},
        }).json()
        r2 = client.post("/experience/signature-delta", json={
            "soulprint_sectors": boot["soulprint_sectors"],
            "signature_blueprint": boot["signature_blueprint"],
            "quiz_answer": {"keyword": "analytical"},
        }).json()
        assert r1["quiz_sectors"] != r2["quiz_sectors"]


class TestDaily:
    def _bootstrap(self):
        return client.post("/experience/bootstrap", json={"birth": BIRTH}).json()

    def test_returns_200(self):
        boot = self._bootstrap()
        resp = client.post("/experience/daily", json={
            "birth": BIRTH,
            "soulprint_sectors": boot["soulprint_sectors"],
            "quiz_sectors": [0.0] * 12,
            "target_date": "2026-03-16",
            "locale": "de-DE",
        })
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["date"] == "2026-03-16"
        assert "western" in data
        assert "eastern" in data
        assert "fusion" in data

    def test_western_section_structure(self):
        boot = self._bootstrap()
        resp = client.post("/experience/daily", json={
            "birth": BIRTH,
            "soulprint_sectors": boot["soulprint_sectors"],
            "quiz_sectors": [0.0] * 12,
            "target_date": "2026-03-16",
        })
        w = resp.json()["western"]
        assert "summary" in w
        assert "themes" in w
        assert len(w["themes"]) >= 1
        assert "evidence" in w

    def test_eastern_has_day_master(self):
        boot = self._bootstrap()
        resp = client.post("/experience/daily", json={
            "birth": BIRTH,
            "soulprint_sectors": boot["soulprint_sectors"],
            "quiz_sectors": [0.0] * 12,
            "target_date": "2026-03-16",
        })
        e = resp.json()["eastern"]
        assert e["evidence"]["day_master"] is not None
        assert e["evidence"]["daily_pillar"] is not None
        assert "stem" in e["evidence"]["daily_pillar"]
        assert e["evidence"]["relation_to_day_master"] is not None

    def test_fusion_has_synthesis(self):
        boot = self._bootstrap()
        resp = client.post("/experience/daily", json={
            "birth": BIRTH,
            "soulprint_sectors": boot["soulprint_sectors"],
            "quiz_sectors": [0.0] * 12,
            "target_date": "2026-03-16",
        })
        f = resp.json()["fusion"]
        assert "synthesis" in f
        assert len(f["synthesis"]) > 20  # substantive text
        assert "action" in f
        assert "pushworthy" in f

    def test_different_dates_different_results(self):
        boot = self._bootstrap()
        base = {"birth": BIRTH, "soulprint_sectors": boot["soulprint_sectors"], "quiz_sectors": [0.0]*12}
        r1 = client.post("/experience/daily", json={**base, "target_date": "2026-03-16"}).json()
        r2 = client.post("/experience/daily", json={**base, "target_date": "2026-06-21"}).json()
        # Eastern pillar must differ (different days)
        assert r1["eastern"]["evidence"]["daily_pillar"] != r2["eastern"]["evidence"]["daily_pillar"]
