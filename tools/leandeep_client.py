"""
HTTP Client fuer LeanDeep-annotator.

Analysiert Text und extrahiert aggregierte VAD-Profile
aus allen gefeuerten Markern.
"""

from __future__ import annotations

import httpx
from tools.sector_vad import VADProfile

DEFAULT_LEANDEEP_URL = "http://localhost:8420"


class LeanDeepClient:
    """Synchroner Client fuer LeanDeep /v1/analyze."""

    def __init__(self, base_url: str = DEFAULT_LEANDEEP_URL, timeout: float = 10.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    MAX_TEXT_LENGTH = 10_000

    def analyze(self, text: str) -> dict:
        """Sende Text an LeanDeep, gib vollen Response zurueck."""
        if len(text) > self.MAX_TEXT_LENGTH:
            text = text[:self.MAX_TEXT_LENGTH]
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.post(
                f"{self.base_url}/v1/analyze",
                json={"text": text},
            )
            resp.raise_for_status()
            return resp.json()

    def derive_vad(self, text: str) -> tuple[VADProfile, dict]:
        """Analysiere Text und aggregiere VAD aus allen Detections.

        Returns:
            Tuple von (aggregiertes VADProfile, Debug-Info dict)
        """
        result = self.analyze(text)
        detections = result.get("markers", []) or result.get("detections", [])

        if not detections:
            return VADProfile(0.0, 0.0, 0.0), {
                "detection_count": 0,
                "markers": [],
                "warning": "Keine LeanDeep-Marker gefeuert. Text zu kurz oder zu generisch?",
            }

        # VAD extrahieren — LeanDeep liefert vad_estimate pro Detection
        vads = []
        weights = []
        marker_info = []
        for det in detections:
            vad = det.get("vad") or det.get("vad_estimate")
            if not vad:
                continue
            v = vad.get("valence", 0)
            a = vad.get("arousal", 0)
            d = vad.get("dominance", 0)
            vads.append((v, a, d))
            weights.append(det.get("confidence", 1.0))
            marker_info.append({
                "id": det.get("marker_id") or det.get("id", "?"),
                "confidence": det.get("confidence", 0),
                "vad": {"v": v, "a": a, "d": d},
            })

        if not vads:
            return VADProfile(0.0, 0.0, 0.0), {
                "detection_count": len(detections),
                "markers": marker_info,
                "warning": "Detections vorhanden, aber keine VAD-Werte.",
            }

        # Gewichtetes Mittel (nach Confidence)
        total_w = sum(weights) or 1.0

        agg_v = sum(v * w for (v, _, _), w in zip(vads, weights)) / total_w
        agg_a = sum(a * w for (_, a, _), w in zip(vads, weights)) / total_w
        agg_d = sum(d * w for (_, _, d), w in zip(vads, weights)) / total_w

        profile = VADProfile(
            valence=round(agg_v, 3),
            arousal=round(agg_a, 3),
            dominance=round(agg_d, 3),
        )

        return profile, {
            "detection_count": len(detections),
            "vad_sources": len(vads),
            "markers": marker_info,
        }

    def health(self) -> bool:
        """Check ob LeanDeep erreichbar ist."""
        try:
            with httpx.Client(timeout=3.0) as client:
                resp = client.get(f"{self.base_url}/v1/health")
                return resp.status_code == 200
        except Exception:
            return False

    def has_vad_support(self) -> bool:
        """Check ob LeanDeep-Marker VAD-Daten liefern.

        Sendet einen Probe-Text und prueft ob mindestens ein Marker
        ein 'vad' oder 'vad_estimate' Feld enthaelt.
        """
        try:
            result = self.analyze("Love, passion, joy, desire")
            markers = result.get("markers", []) or result.get("detections", [])
            for m in markers:
                if m.get("vad") or m.get("vad_estimate"):
                    return True
            return False
        except Exception:
            return False
