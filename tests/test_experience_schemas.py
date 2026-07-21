"""Tests for experience router Pydantic schemas (M1.2)."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from bazi_engine.routers.experience import (
    BootstrapRequest,
    DailyRequest,
    QuizAnswer,
    SignatureBlueprint,
    SignatureDeltaRequest,
)

# ── Fixtures ─────────────────────────────────────────────────────────────────

VALID_BIRTH = {
    "date": "1990-06-15",
    "time": "14:30:00",
    "tz": "Europe/Berlin",
    "lat": 52.52,
    "lon": 13.405,
}

VALID_SECTORS_12 = [0.5] * 12
VALID_SECTORS_11 = [0.5] * 11


# ── BootstrapRequest ────────────────────────────────────────────────────────

class TestBootstrapRequest:
    def test_accepts_valid_birth(self) -> None:
        req = BootstrapRequest(birth=VALID_BIRTH)
        assert req.birth.lat == 52.52
        assert req.locale == "de-DE"

    def test_rejects_lat_above_90(self) -> None:
        bad = {**VALID_BIRTH, "lat": 91.0}
        with pytest.raises(ValidationError, match="less than or equal to 90"):
            BootstrapRequest(birth=bad)

    def test_rejects_lat_below_neg90(self) -> None:
        bad = {**VALID_BIRTH, "lat": -91.0}
        with pytest.raises(ValidationError, match="greater than or equal to -90"):
            BootstrapRequest(birth=bad)

    def test_rejects_invalid_date_format(self) -> None:
        bad = {**VALID_BIRTH, "date": "15-06-1990"}
        with pytest.raises(ValidationError):
            BootstrapRequest(birth=bad)

    def test_rejects_invalid_time_format(self) -> None:
        bad = {**VALID_BIRTH, "time": "2:30 PM"}
        with pytest.raises(ValidationError):
            BootstrapRequest(birth=bad)

    def test_place_label_optional(self) -> None:
        req = BootstrapRequest(birth={**VALID_BIRTH, "place_label": "Berlin"})
        assert req.birth.place_label == "Berlin"


# ── SignatureDeltaRequest ───────────────────────────────────────────────────

class TestSignatureDeltaRequest:
    def test_accepts_valid_input(self) -> None:
        req = SignatureDeltaRequest(
            soulprint_sectors=VALID_SECTORS_12,
            signature_blueprint=SignatureBlueprint(seed="abc123"),
            quiz_answer=QuizAnswer(keyword="fire"),
        )
        assert len(req.soulprint_sectors) == 12

    def test_rejects_11_sectors(self) -> None:
        with pytest.raises(ValidationError, match="too_short"):
            SignatureDeltaRequest(
                soulprint_sectors=VALID_SECTORS_11,
                signature_blueprint=SignatureBlueprint(seed="abc123"),
                quiz_answer=QuizAnswer(keyword="fire"),
            )

    def test_rejects_sector_value_above_1(self) -> None:
        bad_sectors = [0.5] * 11 + [1.5]
        with pytest.raises(ValidationError, match="not in range"):
            SignatureDeltaRequest(
                soulprint_sectors=bad_sectors,
                signature_blueprint=SignatureBlueprint(seed="abc123"),
                quiz_answer=QuizAnswer(keyword="fire"),
            )


# ── DailyRequest ────────────────────────────────────────────────────────────

class TestDailyRequest:
    def test_accepts_valid_input(self) -> None:
        req = DailyRequest(
            birth=VALID_BIRTH,
            soulprint_sectors=VALID_SECTORS_12,
            quiz_sectors=VALID_SECTORS_12,
            target_date="2026-03-16",
        )
        assert req.target_date == "2026-03-16"
        assert req.locale == "de-DE"

    def test_rejects_soulprint_with_11_elements(self) -> None:
        with pytest.raises(ValidationError, match="too_short"):
            DailyRequest(
                birth=VALID_BIRTH,
                soulprint_sectors=VALID_SECTORS_11,
                quiz_sectors=VALID_SECTORS_12,
                target_date="2026-03-16",
            )

    def test_rejects_quiz_sectors_with_11_elements(self) -> None:
        with pytest.raises(ValidationError, match="too_short"):
            DailyRequest(
                birth=VALID_BIRTH,
                soulprint_sectors=VALID_SECTORS_12,
                quiz_sectors=VALID_SECTORS_11,
                target_date="2026-03-16",
            )

    def test_rejects_invalid_target_date(self) -> None:
        with pytest.raises(ValidationError):
            DailyRequest(
                birth=VALID_BIRTH,
                soulprint_sectors=VALID_SECTORS_12,
                quiz_sectors=VALID_SECTORS_12,
                target_date="March 16, 2026",
            )
