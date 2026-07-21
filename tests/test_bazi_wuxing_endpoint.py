"""Tests for POST /calculate/bazi/wuxing — the canonical BaZi Wu-Xing endpoint,
and the western-planetary `basis` label added to POST /calculate/wuxing.

The BaZi Wu-Xing endpoint exposes the Four-Pillar-derived Five-Element vector
(previously only reachable embedded in /chart's `wuxing.from_bazi`). Consumers
were mistaking the planetary /calculate/wuxing for the BaZi one; these lock the
distinction: a BaZi `basis`, parity with /chart.from_bazi, and a
`western_planetary` `basis` on the planetary endpoint.
"""
from fastapi.testclient import TestClient

from bazi_engine.app import app

client = TestClient(app)

# Elke-Christina fixture (Hannover); pillars Xin Mao / Ding You / Gui Chou / Bing Chen.
BODY = {
    "date": "1951-09-10T08:20:00", "tz": "Europe/Berlin", "lon": 9.732, "lat": 52.3759,
    "standard": "CIVIL", "boundary": "midnight", "ambiguousTime": "earlier",
    "nonexistentTime": "error", "birth_time_known": True,
}
CHART_BODY = {
    "local_datetime": "1951-09-10T08:20:00", "tz_id": "Europe/Berlin",
    "geo_lon_deg": 9.732, "geo_lat_deg": 52.3759,
    "time_standard": "CIVIL", "day_boundary": "midnight", "dst_policy": "earlier",
}


def test_bazi_wuxing_shape_and_basis():
    r = client.post("/v1/calculate/bazi/wuxing", json=BODY)
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["basis"] == "bazi_four_pillars"
    assert set(j["wu_xing_vector"]) == {"Holz", "Feuer", "Erde", "Metall", "Wasser"}
    # dominant is the actual argmax of the returned vector
    assert j["dominant_element"] == max(j["wu_xing_vector"], key=j["wu_xing_vector"].get)
    # ledger present and attributed to the bazi basis
    assert j["contribution_ledger"]["bazi"], "bazi contribution ledger must be non-empty"
    # the four pillars it was built from are echoed
    assert set(j["pillars"]) == {"year", "month", "day", "hour"}


def test_bazi_wuxing_equals_chart_from_bazi():
    """The new endpoint must be byte-identical to /chart's `wuxing.from_bazi`
    (it reuses the same resolve_local_iso -> BaziInput -> compute_bazi chain),
    so no consumer sees a second, diverging 'BaZi' number."""
    r = client.post("/v1/calculate/bazi/wuxing", json=BODY)
    chart = client.post("/chart", json=CHART_BODY)
    assert r.status_code == 200 and chart.status_code == 200, (r.text, chart.text)
    assert r.json()["wu_xing_vector"] == chart.json()["wuxing"]["from_bazi"]
    assert r.json()["dominant_element"] == chart.json()["wuxing"]["dominant_bazi"]


def test_planetary_wuxing_carries_western_basis():
    """The existing planetary endpoint now self-labels its provenance so a BaZi
    consumer cannot mistake it for the Four-Pillar vector."""
    r = client.post("/v1/calculate/wuxing", json={
        "date": "1951-09-10T08:20:00", "tz": "Europe/Berlin", "lon": 9.732, "lat": 52.3759,
    })
    assert r.status_code == 200, r.text
    assert r.json()["basis"] == "western_planetary"
