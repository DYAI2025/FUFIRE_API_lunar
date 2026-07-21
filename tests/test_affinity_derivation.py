"""Tests fuer das Affinity Derivation Tool."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from tools.affinity_math import (
    compare_rows,
    compute_affinity_row,
    cosine_similarity,
    format_affinity_row_ts,
)
from tools.leandeep_client import LeanDeepClient
from tools.load_existing_map import EXISTING_AFFINITY_MAP, get_existing
from tools.sector_vad import SECTOR_NAMES, SECTOR_SIGNS_EN, SECTOR_VAD, VADProfile


class TestCosineSimilarity:
    def test_identical_profiles(self):
        a = VADProfile(0.5, 0.8, 0.3)
        assert cosine_similarity(a, a) == pytest.approx(1.0, abs=0.001)

    def test_orthogonal_profiles(self):
        a = VADProfile(1.0, 0.0, 0.0)
        b = VADProfile(0.0, 1.0, 0.0)
        assert cosine_similarity(a, b) == pytest.approx(0.0, abs=0.001)

    def test_opposite_valence(self):
        a = VADProfile(+0.8, 0.5, 0.5)
        b = VADProfile(-0.8, 0.5, 0.5)
        # Nicht perfekt gegensaetzlich wegen A und D Ueberlapp
        sim = cosine_similarity(a, b)
        assert sim < 0.5  # Aber niedrig

    def test_zero_vector(self):
        a = VADProfile(0.0, 0.0, 0.0)
        b = VADProfile(0.5, 0.5, 0.5)
        assert cosine_similarity(a, b) == 0.0


class TestComputeAffinityRow:
    def test_sum_approximately_one(self):
        vad = VADProfile(0.3, 0.7, 0.5)
        row = compute_affinity_row(vad)
        assert sum(row) == pytest.approx(1.0, abs=0.05)

    def test_all_non_negative(self):
        vad = VADProfile(-0.5, 0.9, 0.8)
        row = compute_affinity_row(vad)
        assert all(v >= 0 for v in row)

    def test_twelve_elements(self):
        vad = VADProfile(0.1, 0.5, 0.5)
        row = compute_affinity_row(vad)
        assert len(row) == 12

    def test_scorpio_affinity_for_dark_intense(self):
        """Negativ, hoch-aktiviert, dominant -> muss S7 (Skorpion) treffen."""
        vad = VADProfile(valence=-0.4, arousal=0.85, dominance=0.8)
        row = compute_affinity_row(vad)
        # S7 (Skorpion) hat exakt dieses Profil
        assert row[7] == max(row), f"S7 sollte Peak sein, ist aber {row}"

    def test_pisces_affinity_for_soft_submissive(self):
        """Mild positiv, niedrig-aktiviert, sehr submissiv -> S11 (Fische)."""
        vad = VADProfile(valence=+0.1, arousal=0.2, dominance=0.1)
        row = compute_affinity_row(vad)
        assert row[11] == max(row), f"S11 sollte Peak sein, ist aber {row}"

    def test_aries_affinity_for_impulsive_dominant(self):
        """Positiv, hoch-aktiviert, sehr dominant -> S0 (Widder) oder S4 (Loewe)."""
        vad = VADProfile(valence=+0.3, arousal=0.9, dominance=0.9)
        row = compute_affinity_row(vad)
        # S0 und S4 haben aehnliches Profil, einer muss Top-2 sein
        top2 = sorted(range(12), key=lambda s: row[s], reverse=True)[:2]
        assert 0 in top2 or 4 in top2, f"S0 oder S4 sollte Top-2 sein: {row}"


class TestCompareRows:
    def test_identical_is_coherent(self):
        a = [0.1] * 12
        result = compare_rows(a, a)
        assert result["coherent"] is True
        assert result["max_delta"] == 0.0

    def test_large_delta_is_mismatch(self):
        a = [0.5] + [0.05] * 11
        b = [0.0] + [0.05] * 11
        result = compare_rows(a, b, threshold=0.15)
        assert result["coherent"] is False
        assert result["max_delta_sector"] == 0


class TestSectorVADConsistency:
    def test_all_twelve_sectors_defined(self):
        assert len(SECTOR_VAD) == 12

    def test_valence_range(self):
        for s, vad in SECTOR_VAD.items():
            assert -1.0 <= vad.valence <= 1.0, f"S{s} valence out of range"

    def test_arousal_range(self):
        for s, vad in SECTOR_VAD.items():
            assert 0.0 <= vad.arousal <= 1.0, f"S{s} arousal out of range"

    def test_dominance_range(self):
        for s, vad in SECTOR_VAD.items():
            assert 0.0 <= vad.dominance <= 1.0, f"S{s} dominance out of range"

    def test_scorpio_is_negative_valence(self):
        assert SECTOR_VAD[7].valence < 0, "Skorpion muss negativ-valence sein"

    def test_pisces_is_low_dominance(self):
        assert SECTOR_VAD[11].dominance <= 0.2, "Fische muss niedrig-dominant sein"

    def test_aries_is_high_arousal(self):
        assert SECTOR_VAD[0].arousal >= 0.8, "Widder muss hoch-aktiviert sein"

    def test_sector_names_length(self):
        assert len(SECTOR_NAMES) == 12

    def test_sector_signs_en_length(self):
        assert len(SECTOR_SIGNS_EN) == 12


# =========================================================================
# format_affinity_row_ts — was buggy (int truncation), verify fix
# =========================================================================

class TestFormatAffinityRowTs:
    def test_zero_values(self):
        row = [0.0] * 12
        result = format_affinity_row_ts("test", row)
        assert "'test'" in result
        assert "0  " in result

    def test_one_value(self):
        row = [1.0] + [0.0] * 11
        result = format_affinity_row_ts("peak", row)
        assert "1  " in result

    def test_small_value_formatting(self):
        """Regression: int(0.05*100)=5 produced '.5 ' instead of '.05'."""
        row = [0.05] + [0.0] * 11
        result = format_affinity_row_ts("small", row)
        assert ".05" in result

    def test_medium_value_formatting(self):
        row = [0.25] + [0.0] * 11
        result = format_affinity_row_ts("med", row)
        assert ".25" in result

    def test_output_is_valid_ts_syntax(self):
        row = [0.1, 0.2, 0.0, 0.3, 0.0, 0.0, 0.15, 0.0, 0.0, 0.1, 0.1, 0.05]
        result = format_affinity_row_ts("mixed", row)
        assert result.startswith("  'mixed': [")
        assert result.endswith("],")


# =========================================================================
# compute_affinity_row — edge cases
# =========================================================================

class TestComputeAffinityRowEdgeCases:
    def test_zero_vad_returns_uniform(self):
        """Zero VAD vector should produce uniform distribution."""
        vad = VADProfile(0.0, 0.0, 0.0)
        row = compute_affinity_row(vad)
        assert len(row) == 12
        assert all(v == row[0] for v in row), "Should be uniform"
        assert sum(row) == pytest.approx(1.0, abs=0.05)

    def test_noise_filter_removes_tiny_values(self):
        """Values < 0.03 after normalization should become 0."""
        # Use a VAD that creates at least one tiny sector weight
        vad = VADProfile(valence=-0.4, arousal=0.85, dominance=0.8)
        row = compute_affinity_row(vad)
        for v in row:
            assert v == 0.0 or v >= 0.03, f"Non-zero value {v} below noise threshold"

    def test_scorpio_has_highest_self_similarity(self):
        """Scorpio (only negative-valence sector) should strongly self-peak."""
        vad = SECTOR_VAD[7]  # Scorpio: V=-0.4, A=0.85, D=0.8
        row = compute_affinity_row(vad)
        # S7 is the only sector with negative valence, so it must peak
        assert row[7] == max(row)


# =========================================================================
# compare_rows — additional coverage
# =========================================================================

class TestCompareRowsExtended:
    def test_warnings_contain_sector_names(self):
        a = [0.5] + [0.05] * 11
        b = [0.0] + [0.05] * 11
        result = compare_rows(a, b, threshold=0.15)
        assert len(result["warnings"]) >= 1
        assert "S0" in result["warnings"][0]
        assert "Widder" in result["warnings"][0]

    def test_threshold_edge_exact(self):
        """Delta exactly at threshold should be incoherent (>= check)."""
        a = [0.25] + [0.0] * 11
        b = [0.10] + [0.0] * 11
        result = compare_rows(a, b, threshold=0.15)
        assert result["coherent"] is False

    def test_threshold_edge_just_below(self):
        a = [0.24] + [0.0] * 11
        b = [0.10] + [0.0] * 11
        result = compare_rows(a, b, threshold=0.15)
        assert result["coherent"] is True

    def test_deltas_list_length(self):
        a = [0.1] * 12
        b = [0.2] * 12
        result = compare_rows(a, b)
        assert len(result["deltas"]) == 12


# =========================================================================
# EXISTING_AFFINITY_MAP — data integrity
# =========================================================================

class TestExistingAffinityMapIntegrity:
    def test_all_rows_have_12_elements(self):
        for kw, row in EXISTING_AFFINITY_MAP.items():
            assert len(row) == 12, f"'{kw}' has {len(row)} elements, expected 12"

    def test_all_values_non_negative(self):
        for kw, row in EXISTING_AFFINITY_MAP.items():
            assert all(v >= 0 for v in row), f"'{kw}' has negative values"

    def test_rows_sum_approximately_one(self):
        for kw, row in EXISTING_AFFINITY_MAP.items():
            # Handcrafted weights — some rows sum to 0.9 (acceptable)
            assert 0.85 <= sum(row) <= 1.05, (
                f"'{kw}' sum={sum(row):.3f} out of range"
            )

    def test_expected_keyword_count(self):
        assert len(EXISTING_AFFINITY_MAP) == 27

    def test_get_existing_returns_known(self):
        assert get_existing("love") is not None
        assert len(get_existing("love")) == 12

    def test_get_existing_returns_none_for_unknown(self):
        assert get_existing("nonexistent_keyword_xyz") is None


# =========================================================================
# LeanDeepClient.derive_vad — mocked unit tests
# =========================================================================

class TestLeanDeepClientDeriveVad:
    def _make_client(self):
        return LeanDeepClient(base_url="http://fake:8420")

    @patch.object(LeanDeepClient, "analyze")
    def test_empty_detections_returns_zero_vad(self, mock_analyze):
        mock_analyze.return_value = {"detections": []}
        client = self._make_client()
        vad, debug = client.derive_vad("test text")
        assert vad.valence == 0.0
        assert vad.arousal == 0.0
        assert vad.dominance == 0.0
        assert debug["detection_count"] == 0
        assert "warning" in debug

    @patch.object(LeanDeepClient, "analyze")
    def test_detections_without_vad_returns_zero(self, mock_analyze):
        mock_analyze.return_value = {"detections": [
            {"id": "marker1", "confidence": 0.9},
            {"id": "marker2", "confidence": 0.8},
        ]}
        client = self._make_client()
        vad, debug = client.derive_vad("test text")
        assert vad.valence == 0.0
        assert debug["detection_count"] == 2
        assert "warning" in debug

    @patch.object(LeanDeepClient, "analyze")
    def test_normal_detections_aggregate_vad(self, mock_analyze):
        mock_analyze.return_value = {"detections": [
            {"id": "m1", "confidence": 1.0, "vad": {"valence": 0.5, "arousal": 0.8, "dominance": 0.6}},
            {"id": "m2", "confidence": 1.0, "vad": {"valence": -0.3, "arousal": 0.4, "dominance": 0.2}},
        ]}
        client = self._make_client()
        vad, debug = client.derive_vad("test text")
        # Equal weights -> simple average
        assert vad.valence == pytest.approx(0.1, abs=0.01)
        assert vad.arousal == pytest.approx(0.6, abs=0.01)
        assert vad.dominance == pytest.approx(0.4, abs=0.01)
        assert debug["vad_sources"] == 2

    @patch.object(LeanDeepClient, "analyze")
    def test_weighted_aggregation(self, mock_analyze):
        mock_analyze.return_value = {"detections": [
            {"id": "m1", "confidence": 0.9, "vad": {"valence": 1.0, "arousal": 0.0, "dominance": 0.0}},
            {"id": "m2", "confidence": 0.1, "vad": {"valence": 0.0, "arousal": 1.0, "dominance": 0.0}},
        ]}
        client = self._make_client()
        vad, _ = client.derive_vad("test")
        # m1 has 9x the weight of m2
        assert vad.valence > 0.8
        assert vad.arousal < 0.2

    @patch.object(LeanDeepClient, "analyze")
    def test_vad_estimate_fallback_key(self, mock_analyze):
        """LeanDeep may use 'vad_estimate' instead of 'vad'."""
        mock_analyze.return_value = {"detections": [
            {"id": "m1", "confidence": 1.0, "vad_estimate": {"valence": 0.3, "arousal": 0.5, "dominance": 0.7}},
        ]}
        client = self._make_client()
        vad, debug = client.derive_vad("test")
        assert vad.valence == pytest.approx(0.3, abs=0.01)
        assert debug["vad_sources"] == 1


# =========================================================================
# LeanDeepClient — text truncation
# =========================================================================

class TestLeanDeepClientTruncation:
    def test_max_text_length_constant(self):
        assert LeanDeepClient.MAX_TEXT_LENGTH == 10_000

    @patch("httpx.Client")
    def test_long_text_gets_truncated(self, mock_client_cls):
        """Verify analyze() truncates text before sending HTTP request."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"detections": []}
        mock_resp.raise_for_status = MagicMock()

        mock_http = MagicMock()
        mock_http.post.return_value = mock_resp
        mock_http.__enter__ = MagicMock(return_value=mock_http)
        mock_http.__exit__ = MagicMock(return_value=False)
        mock_client_cls.return_value = mock_http

        client = LeanDeepClient(base_url="http://fake:8420")
        long_text = "x" * 20_000
        client.analyze(long_text)

        # Verify the JSON payload has truncated text
        call_kwargs = mock_http.post.call_args
        sent_text = call_kwargs[1]["json"]["text"] if "json" in call_kwargs[1] else call_kwargs.kwargs["json"]["text"]
        assert len(sent_text) == 10_000


# =========================================================================
# affinity_descriptions.json — integrity
# =========================================================================

class TestAffinityDescriptionsJson:
    @pytest.fixture
    def descriptions(self):
        path = Path(__file__).parent.parent / "tools" / "affinity_descriptions.json"
        return json.loads(path.read_text(encoding="utf-8"))

    def test_all_map_keywords_have_descriptions(self, descriptions):
        for kw in EXISTING_AFFINITY_MAP:
            assert kw in descriptions, f"Missing description for '{kw}'"

    def test_no_empty_descriptions(self, descriptions):
        for kw, desc in descriptions.items():
            assert len(desc.strip()) > 5, f"'{kw}' has empty/short description"

    def test_descriptions_count_matches_map(self, descriptions):
        assert len(descriptions) == len(EXISTING_AFFINITY_MAP)
