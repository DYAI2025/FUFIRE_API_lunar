"""
Integration-Tests: brauchen laufende LeanDeep-Instanz.

Markiert als 'integration' — mit pytest -m integration ausfuehren.
Uebersprungen wenn LeanDeep nicht erreichbar.
"""

import pytest

from tools.affinity_math import compute_affinity_row
from tools.leandeep_client import LeanDeepClient
from tools.sector_vad import SECTOR_NAMES

client = LeanDeepClient()

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def skip_if_no_leandeep():
    if not client.health():
        pytest.skip("LeanDeep nicht erreichbar")
    if not client.has_vad_support():
        pytest.skip("LeanDeep-Marker liefern keine VAD-Daten")


class TestPhysicalTouchDerivation:
    def test_derives_scorpio_peak(self):
        vad, _ = client.derive_vad(
            "Koerperliche Beruehrung, physische Naehe, Umarmung, "
            "taktile Liebessprache, Hautkontakt, sinnliche Verbindung"
        )
        row = compute_affinity_row(vad)
        # S7 (Skorpion) oder S1 (Stier) muss Top-3 sein
        top3 = sorted(range(12), key=lambda s: row[s], reverse=True)[:3]
        assert 7 in top3 or 1 in top3, (
            f"Physical Touch sollte S7 oder S1 treffen: "
            f"{[(s, SECTOR_NAMES[s], row[s]) for s in top3]}"
        )


class TestAnalyticalDerivation:
    def test_derives_virgo_or_gemini_peak(self):
        vad, _ = client.derive_vad(
            "Analytisches Denken, logische Zerlegung, Praezision, "
            "systematische Analyse, Detailarbeit, wissenschaftliche Methode"
        )
        row = compute_affinity_row(vad)
        top3 = sorted(range(12), key=lambda s: row[s], reverse=True)[:3]
        # S5 (Jungfrau/Analyse) oder S2 (Zwillinge/Kognition)
        assert 5 in top3 or 2 in top3, (
            f"Analytical sollte S5 oder S2 treffen: "
            f"{[(s, SECTOR_NAMES[s], row[s]) for s in top3]}"
        )


class TestProtectiveDerivation:
    def test_derives_cancer_or_capricorn(self):
        vad, _ = client.derive_vad(
            "Beschuetzerinstinkt, Verteidigung der Schwachen, "
            "Fuersorge, Schutzverhalten, Aufopferung fuer die Familie"
        )
        row = compute_affinity_row(vad)
        top3 = sorted(range(12), key=lambda s: row[s], reverse=True)[:3]
        # S3 (Krebs/Fuersorge) oder S9 (Steinbock/Verantwortung)
        assert 3 in top3 or 9 in top3, (
            f"Protective sollte S3 oder S9 treffen: "
            f"{[(s, SECTOR_NAMES[s], row[s]) for s in top3]}"
        )
