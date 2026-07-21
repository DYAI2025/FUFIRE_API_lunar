"""Tests for the request-shaped Da-Yun direction bridge (TASK-DY-006)."""

from types import SimpleNamespace

import pytest

from bazi_engine.dayun.direction import (
    DirectionBasisMissingError,
    resolve_direction_for_request,
)


def _year_pillar(stem_index: int):
    """Minimal Pillar-like stub; the bridge only needs ``.stem_index``."""
    return SimpleNamespace(stem_index=stem_index)


# ── Explicit mode pass-through ────────────────────────────────────────────

def test_explicit_forward_passes_through():
    req = {"direction_method": "explicit", "flow_direction": "forward"}
    assert resolve_direction_for_request(req, year_pillar=None) == "forward"


def test_explicit_backward_passes_through():
    req = {"direction_method": "explicit", "flow_direction": "backward"}
    assert resolve_direction_for_request(req, year_pillar=None) == "backward"


# ── Traditional mode derives polarity from year_pillar ────────────────────

def test_traditional_yang_year_male_is_forward():
    # stem_index=0 (Jia) → yang
    req = {"direction_method": "year_stem_yinyang_and_sex", "sex_at_birth": "male"}
    assert resolve_direction_for_request(req, year_pillar=_year_pillar(0)) == "forward"


def test_traditional_yang_year_female_is_backward():
    req = {"direction_method": "year_stem_yinyang_and_sex", "sex_at_birth": "female"}
    assert resolve_direction_for_request(req, year_pillar=_year_pillar(0)) == "backward"


def test_traditional_yin_year_male_is_backward():
    # stem_index=1 (Yi) → yin
    req = {"direction_method": "year_stem_yinyang_and_sex", "sex_at_birth": "male"}
    assert resolve_direction_for_request(req, year_pillar=_year_pillar(1)) == "backward"


def test_traditional_yin_year_female_is_forward():
    req = {"direction_method": "year_stem_yinyang_and_sex", "sex_at_birth": "female"}
    assert resolve_direction_for_request(req, year_pillar=_year_pillar(1)) == "forward"


# ── Article-example sanity: 1987 = Ding Mao year → stem_index 3 (Ding) → yin
def test_article_example_1987_explicit_forward_returns_forward():
    req = {"direction_method": "explicit", "flow_direction": "forward", "sex_at_birth": None}
    assert resolve_direction_for_request(req, year_pillar=_year_pillar(3)) == "forward"


# ── Traditional mode without year_pillar raises ───────────────────────────

def test_traditional_without_year_pillar_raises():
    req = {"direction_method": "year_stem_yinyang_and_sex", "sex_at_birth": "male"}
    with pytest.raises(DirectionBasisMissingError, match="direction_basis_missing"):
        resolve_direction_for_request(req, year_pillar=None)


# ── Underlying-resolver guards still fire ─────────────────────────────────

def test_explicit_without_flow_direction_raises():
    req = {"direction_method": "explicit"}
    with pytest.raises(DirectionBasisMissingError, match="direction_basis_missing"):
        resolve_direction_for_request(req, year_pillar=None)


def test_traditional_without_sex_at_birth_raises():
    req = {"direction_method": "year_stem_yinyang_and_sex"}
    with pytest.raises(DirectionBasisMissingError, match="direction_basis_missing"):
        resolve_direction_for_request(req, year_pillar=_year_pillar(0))


def test_missing_direction_method_raises():
    req = {}
    with pytest.raises(DirectionBasisMissingError, match="direction_basis_missing"):
        resolve_direction_for_request(req, year_pillar=None)
