"""ZWDS-P1-23 — natal golden corpus regression lock.

Locks the ZWDS core-seed engine's current deterministic natal output. For every
committed golden under ``tests/zwds/goldens/`` this test:

1. re-runs :func:`bazi_engine.zwds.engine.compute_zwds_raw` on the stored
   ``request`` with the stored ``request_id`` / ``generated_at``, and asserts
   **full-dict equality** with the stored ``response`` — the engine is a pure,
   deterministic function of those three inputs (with a fixed ephemeris), so the
   whole response including ``chart_fingerprint`` is byte-stable; and
2. asserts the stored ``response`` validates against
   ``spec/schemas/zwds/ZwdsRawResponse.schema.json`` (Draft 2020-12).

The goldens are engine-deterministic-TRUTH, not historically validated charts;
practitioner review (GATE-1) is PENDING — see ``docs/zwds/golden-review.md``.
Regenerate with ``scripts/zwds/gen_natal_goldens.py`` (SWIEPH / SE1 required).

Marked ``swieph`` because the calendar half converts the civil chart date onto
the Chinese lunisolar calendar via Swiss-Ephemeris; the committed goldens are
SWIEPH-mode truth, so the byte-equality assertion only holds where the SE1 data
is present (conftest auto-skips otherwise).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

import pytest
from jsonschema import Draft202012Validator

from bazi_engine.zwds.engine import compute_zwds_raw

pytestmark = pytest.mark.swieph


def _repo_root() -> Path:
    """Walk up until the repo root (the dir carrying ``pyproject.toml``)."""
    for parent in Path(__file__).resolve().parents:
        if (parent / "pyproject.toml").is_file():
            return parent
    raise RuntimeError("could not locate repo root (no pyproject.toml found)")


ROOT = _repo_root()
GOLDENS_DIR = ROOT / "tests" / "zwds" / "goldens"
RAW_RESPONSE_SCHEMA = ROOT / "spec" / "schemas" / "zwds" / "ZwdsRawResponse.schema.json"

#: Every committed golden file, sorted for stable parametrization order.
GOLDEN_FILES: List[Path] = sorted(GOLDENS_DIR.glob("*.json"))


def _load(path: Path) -> Dict[str, Any]:
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def test_golden_corpus_is_present() -> None:
    """Guard against an empty glob silently making this a no-op suite."""
    assert GOLDEN_FILES, f"no golden files found under {GOLDENS_DIR}"


@pytest.fixture(scope="module")
def raw_response_validator() -> Draft202012Validator:
    schema = _load(RAW_RESPONSE_SCHEMA)
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


@pytest.mark.parametrize(
    "golden_path", GOLDEN_FILES, ids=[p.stem for p in GOLDEN_FILES]
)
def test_golden_recomputes_byte_stable(golden_path: Path) -> None:
    """Re-running the engine reproduces the stored response exactly."""
    golden = _load(golden_path)
    recomputed = compute_zwds_raw(
        golden["request"],
        request_id=golden["request_id"],
        generated_at=golden["generated_at"],
    )
    assert recomputed == golden["response"], (
        f"engine output drifted from golden {golden_path.name}; "
        "regenerate with scripts/zwds/gen_natal_goldens.py if intentional"
    )


@pytest.mark.parametrize(
    "golden_path", GOLDEN_FILES, ids=[p.stem for p in GOLDEN_FILES]
)
def test_golden_response_is_schema_valid(
    golden_path: Path, raw_response_validator: Draft202012Validator
) -> None:
    """Each stored response validates against ZwdsRawResponse.schema.json."""
    golden = _load(golden_path)
    errors = sorted(
        raw_response_validator.iter_errors(golden["response"]),
        key=lambda err: list(err.path),
    )
    assert errors == [], (
        f"golden {golden_path.name} failed ZwdsRawResponse schema: "
        + "; ".join(f"{list(e.path)}: {e.message}" for e in errors)
    )
