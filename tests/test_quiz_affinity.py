import json
from pathlib import Path


def test_affinity_map_loads():
    path = Path(__file__).parent.parent / "bazi_engine" / "data" / "affinity_map.json"
    data = json.loads(path.read_text())
    assert "keywords" in data
    assert len(data["keywords"]) >= 69
    for key, weights in data["keywords"].items():
        assert len(weights) == 12, f"{key} must have 12 sectors"
        assert abs(sum(weights) - 1.0) < 0.15, f"{key} sum={sum(weights)} should be ~1.0"


def test_affinity_map_has_tags():
    path = Path(__file__).parent.parent / "bazi_engine" / "data" / "affinity_map.json"
    data = json.loads(path.read_text())
    assert "tags" in data
    for key, weights in data["tags"].items():
        assert len(weights) == 12


def test_resolve_quiz_sectors_known():
    from bazi_engine.services.quiz_affinity import resolve_quiz_sectors
    result = resolve_quiz_sectors("expression")
    assert len(result) == 12
    assert result[4] == 0.5  # expression has highest weight in sector 4


def test_resolve_quiz_sectors_unknown():
    from bazi_engine.services.quiz_affinity import resolve_quiz_sectors
    result = resolve_quiz_sectors("nonexistent_keyword_xyz")
    assert len(result) == 12
    assert abs(sum(result) - 1.0) < 0.01  # uniform fallback
