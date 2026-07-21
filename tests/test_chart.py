"""Integration tests for POST /chart endpoint."""

from __future__ import annotations

from fastapi.testclient import TestClient

from bazi_engine.app import app

client = TestClient(app)

BERLIN_PAYLOAD = {
    "local_datetime": "2024-02-10T14:30:00",
    "tz_id": "Europe/Berlin",
    "geo_lon_deg": 13.405,
    "geo_lat_deg": 52.52,
}

ZODIAC_SIGNS_EN = [
    "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
    "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces",
]


class TestChartHappyPath:
    """POST /chart basic functionality."""

    def test_returns_200(self):
        r = client.post("/chart", json=BERLIN_PAYLOAD)
        assert r.status_code == 200

    def test_response_has_engine_version(self):
        data = client.post("/chart", json=BERLIN_PAYLOAD).json()
        assert "engine_version" in data
        assert isinstance(data["engine_version"], str)

    def test_response_has_parameter_set_id(self):
        data = client.post("/chart", json=BERLIN_PAYLOAD).json()
        assert "parameter_set_id" in data

    def test_response_has_time_scales(self):
        data = client.post("/chart", json=BERLIN_PAYLOAD).json()
        ts = data["time_scales"]
        assert "utc" in ts
        assert "civil_local" in ts
        assert "jd_ut" in ts
        assert "tlst_hours" in ts
        assert "eot_min" in ts
        assert "quality" in ts
        assert 0 <= ts["tlst_hours"] < 24

    def test_response_has_positions_list(self):
        data = client.post("/chart", json=BERLIN_PAYLOAD).json()
        positions = data["positions"]
        assert isinstance(positions, list)
        assert len(positions) > 0

    def test_sun_and_moon_in_positions(self):
        data = client.post("/chart", json=BERLIN_PAYLOAD).json()
        names = [p["name"] for p in data["positions"]]
        assert "Sun" in names
        assert "Moon" in names

    def test_position_structure(self):
        data = client.post("/chart", json=BERLIN_PAYLOAD).json()
        sun = next(p for p in data["positions"] if p["name"] == "Sun")
        assert "longitude_deg" in sun
        assert "sign_index" in sun
        assert "sign_name" in sun
        assert "sign_name_de" in sun
        assert "degree_in_sign" in sun
        assert "is_retrograde" in sun
        assert 0 <= sun["sign_index"] <= 11
        assert sun["sign_name"] in ZODIAC_SIGNS_EN
        assert 0 <= sun["degree_in_sign"] < 30

    def test_bazi_section_present(self):
        data = client.post("/chart", json=BERLIN_PAYLOAD).json()
        bazi = data["bazi"]
        assert "pillars" in bazi
        assert "ruleset_id" in bazi
        assert "day_master" in bazi
        assert "dates" in bazi

    def test_bazi_pillars_structure(self):
        data = client.post("/chart", json=BERLIN_PAYLOAD).json()
        for name in ["year", "month", "day", "hour"]:
            pillar = data["bazi"]["pillars"][name]
            assert "stem_index" in pillar
            assert "branch_index" in pillar
            assert "stem" in pillar
            assert "branch" in pillar
            assert "animal" in pillar
            assert "element" in pillar
            assert 0 <= pillar["stem_index"] <= 9
            assert 0 <= pillar["branch_index"] <= 11

    def test_houses_and_angles_present(self):
        data = client.post("/chart", json=BERLIN_PAYLOAD).json()
        assert "houses" in data
        assert "angles" in data

    def test_feb_10_2024_sun_is_aquarius(self):
        """Feb 10 2024 sun should be in Aquarius (index 10)."""
        data = client.post("/chart", json=BERLIN_PAYLOAD).json()
        sun = next(p for p in data["positions"] if p["name"] == "Sun")
        assert sun["sign_index"] == 10  # Aquarius
        assert sun["sign_name"] == "Aquarius"
        assert sun["sign_name_de"] == "Wassermann"


class TestChartBodyFilter:
    """Test the bodies filter parameter."""

    def test_filter_sun_moon_only(self):
        payload = {**BERLIN_PAYLOAD, "bodies": ["Sun", "Moon"]}
        data = client.post("/chart", json=payload).json()
        names = {p["name"] for p in data["positions"]}
        assert names == {"Sun", "Moon"}

    def test_no_filter_returns_all(self):
        data = client.post("/chart", json=BERLIN_PAYLOAD).json()
        names = {p["name"] for p in data["positions"]}
        assert "Sun" in names
        assert "Moon" in names
        assert "Mars" in names


class TestChartDSTHandling:
    """DST edge cases for /chart endpoint."""

    def test_nonexistent_time_error_policy_returns_422(self):
        """March 31 2024 02:30 CET does not exist (spring forward)."""
        payload = {
            "local_datetime": "2024-03-31T02:30:00",
            "tz_id": "Europe/Berlin",
            "geo_lon_deg": 13.405,
            "geo_lat_deg": 52.52,
            "dst_policy": "error",
        }
        r = client.post("/chart", json=payload)
        assert r.status_code == 422
        body = r.json()
        assert body.get("type") == "dst_error" or "DST" in str(body.get("error", ""))

    def test_nonexistent_time_earlier_policy_shifts_forward(self):
        """With dst_policy='earlier', nonexistent time should be shifted forward."""
        payload = {
            "local_datetime": "2024-03-31T02:30:00",
            "tz_id": "Europe/Berlin",
            "geo_lon_deg": 13.405,
            "geo_lat_deg": 52.52,
            "dst_policy": "earlier",
        }
        r = client.post("/chart", json=payload)
        assert r.status_code == 200
        data = r.json()
        assert data["time_scales"]["dst_status"] == "nonexistent_shifted"

    def test_ambiguous_time_earlier(self):
        """Oct 27 2024 02:30 CET is ambiguous (fall back). Test earlier fold."""
        payload = {
            "local_datetime": "2024-10-27T02:30:00",
            "tz_id": "Europe/Berlin",
            "geo_lon_deg": 13.405,
            "geo_lat_deg": 52.52,
            "dst_policy": "earlier",
        }
        r = client.post("/chart", json=payload)
        assert r.status_code == 200
        data = r.json()
        assert data["time_scales"]["dst_status"] == "ambiguous"
        assert data["time_scales"]["dst_fold"] == 0

    def test_ambiguous_time_later(self):
        """Oct 27 2024 02:30 CET, later fold."""
        payload = {
            "local_datetime": "2024-10-27T02:30:00",
            "tz_id": "Europe/Berlin",
            "geo_lon_deg": 13.405,
            "geo_lat_deg": 52.52,
            "dst_policy": "later",
        }
        r = client.post("/chart", json=payload)
        assert r.status_code == 200
        data = r.json()
        assert data["time_scales"]["dst_status"] == "ambiguous"
        assert data["time_scales"]["dst_fold"] == 1


class TestChartValidationEmbed:
    """Test include_validation flag."""

    def test_validation_null_by_default(self):
        data = client.post("/chart", json=BERLIN_PAYLOAD).json()
        assert data.get("validation") is None

    def test_validation_present_when_requested(self):
        payload = {**BERLIN_PAYLOAD, "include_validation": True}
        data = client.post("/chart", json=payload).json()
        assert "validation" in data
        # Should be a dict (validation response or error)
        assert isinstance(data["validation"], dict)


class TestChartWuXing:
    """Test Wu-Xing distribution in /chart response."""

    def test_wuxing_present(self):
        data = client.post("/chart", json=BERLIN_PAYLOAD).json()
        assert "wuxing" in data

    def test_wuxing_has_from_planets(self):
        wx = client.post("/chart", json=BERLIN_PAYLOAD).json()["wuxing"]
        fp = wx["from_planets"]
        for key in ["Holz", "Feuer", "Erde", "Metall", "Wasser"]:
            assert key in fp
            assert isinstance(fp[key], (int, float))

    def test_wuxing_has_from_bazi(self):
        wx = client.post("/chart", json=BERLIN_PAYLOAD).json()["wuxing"]
        fb = wx["from_bazi"]
        for key in ["Holz", "Feuer", "Erde", "Metall", "Wasser"]:
            assert key in fb
            assert isinstance(fb[key], (int, float))

    def test_wuxing_harmony_index_range(self):
        wx = client.post("/chart", json=BERLIN_PAYLOAD).json()["wuxing"]
        h = wx["harmony_index"]
        assert 0.0 <= h <= 1.0

    def test_wuxing_dominant_elements(self):
        wx = client.post("/chart", json=BERLIN_PAYLOAD).json()["wuxing"]
        valid = {"Holz", "Feuer", "Erde", "Metall", "Wasser"}
        assert wx["dominant_planet"] in valid
        assert wx["dominant_bazi"] in valid


class TestChartBaziOptions:
    """Test BaZi-specific options (time_standard, day_boundary)."""

    def test_lmt_standard(self):
        payload = {**BERLIN_PAYLOAD, "time_standard": "LMT"}
        r = client.post("/chart", json=payload)
        assert r.status_code == 200

    def test_zi_boundary(self):
        payload = {
            "local_datetime": "2024-02-10T23:30:00",
            "tz_id": "Europe/Berlin",
            "geo_lon_deg": 13.405,
            "geo_lat_deg": 52.52,
            "day_boundary": "zi",
        }
        r = client.post("/chart", json=payload)
        assert r.status_code == 200


class TestChartErrorHandling:
    """Error cases for /chart endpoint."""

    def test_invalid_datetime_returns_4xx(self):
        payload = {**BERLIN_PAYLOAD, "local_datetime": "not-a-date"}
        r = client.post("/chart", json=payload)
        assert r.status_code in (400, 422)

    def test_invalid_timezone_returns_422(self):
        payload = {**BERLIN_PAYLOAD, "tz_id": "Invalid/Zone"}
        r = client.post("/chart", json=payload)
        assert r.status_code in (400, 422)

    def test_missing_required_field_returns_422(self):
        r = client.post("/chart", json={"tz_id": "Europe/Berlin"})
        assert r.status_code == 422  # Pydantic validation error


class TestChartDeterminism:
    """Ensure /chart is deterministic (same input -> same output)."""

    def test_identical_calls_produce_identical_results(self):
        r1 = client.post("/chart", json=BERLIN_PAYLOAD).json()
        r2 = client.post("/chart", json=BERLIN_PAYLOAD).json()
        # FQ-ATT-02 (T9): /chart now carries a `provenance.computation_timestamp`
        # (wall-clock, by design) alongside the other attestation fields added
        # to close ChartResponse's previously-zero quality_flags/provenance
        # gap -- strip it before comparing, exactly like the established
        # volatile-key convention in tests/test_snapshot_stability.py's
        # _VOLATILE_KEYS. Every OTHER field (including the rest of
        # `provenance` and `quality_flags`) must still be identical.
        for r in (r1, r2):
            r["provenance"].pop("computation_timestamp", None)
        assert r1 == r2
