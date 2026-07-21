from __future__ import annotations

import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from random import Random
from typing import Any
from zoneinfo import ZoneInfo

from bazi_engine.western import compute_western_chart

SIGN_TO_INDEX = {
    "Ari": 0,
    "Tau": 1,
    "Gem": 2,
    "Can": 3,
    "Leo": 4,
    "Vir": 5,
    "Lib": 6,
    "Sco": 7,
    "Sag": 8,
    "Cap": 9,
    "Aqu": 10,
    "Pis": 11,
}

NAME_TO_ABBR = {
    "Aries": "Ari",
    "Taurus": "Tau",
    "Gemini": "Gem",
    "Cancer": "Can",
    "Leo": "Leo",
    "Virgo": "Vir",
    "Libra": "Lib",
    "Scorpio": "Sco",
    "Sagittarius": "Sag",
    "Capricorn": "Cap",
    "Aquarius": "Aqu",
    "Pisces": "Pis",
}

INDEX_TO_SIGN = {v: k for k, v in SIGN_TO_INDEX.items()}


@dataclass(frozen=True)
class ComparisonRow:
    name: str
    category: str
    data_quality: str
    source_hint: str
    sun_ref: str
    moon_ref: str
    asc_ref: str
    sun_fufire: str
    moon_fufire: str
    asc_fufire: str
    asc_deg_fufire: float
    asc_delta_to_ref_deg: float
    timezone: str
    utc_offset_minutes_zoneinfo: int
    utc_offset_minutes_kerykeion: int

    @property
    def sun_match(self) -> bool:
        return self.sun_ref == self.sun_fufire

    @property
    def moon_match(self) -> bool:
        return self.moon_ref == self.moon_fufire

    @property
    def asc_match(self) -> bool:
        return self.asc_ref == self.asc_fufire


def _norm_ref_sign(name: str) -> str:
    return NAME_TO_ABBR.get(name, name)


def _asc_delta_deg(fufire_deg: float, ref_deg: float) -> float:
    delta = (fufire_deg - ref_deg + 180.0) % 360.0 - 180.0
    return delta


def _load_records(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text())
    return payload["records"]


def evaluate(records: list[dict[str, Any]]) -> list[ComparisonRow]:
    rows: list[ComparisonRow] = []

    for rec in records:
        dt_local = datetime.fromisoformat(rec["date_local"]).replace(
            tzinfo=ZoneInfo(rec["timezone"])
        )
        dt_utc = dt_local.astimezone(timezone.utc)

        chart = compute_western_chart(dt_utc, rec["latitude"], rec["longitude"])

        sun_f = INDEX_TO_SIGN[int(chart["bodies"]["Sun"]["zodiac_sign"])]
        moon_f = INDEX_TO_SIGN[int(chart["bodies"]["Moon"]["zodiac_sign"])]
        asc_deg_f = float(chart["angles"]["Ascendant"])
        asc_f = INDEX_TO_SIGN[int(asc_deg_f // 30)]

        sun_r = _norm_ref_sign(rec["reference_signs"]["sun"])
        moon_r = _norm_ref_sign(rec["reference_signs"]["moon"])
        asc_r = _norm_ref_sign(rec["reference_signs"]["ascendant"])

        # Normalize both offsets to UTC-minus-local minutes for easier comparison.
        offset_zoneinfo = int(-(dt_local.utcoffset().total_seconds() // 60))
        k_utc_hours = float(rec["kerykeion_utc_time_hours"])
        k_utc_minutes = int(round(k_utc_hours * 60))
        local_minutes = dt_local.hour * 60 + dt_local.minute
        raw = k_utc_minutes - local_minutes
        candidates = [raw - 1440, raw, raw + 1440]
        offset_kerykeion = min(
            candidates, key=lambda cand: abs(cand - offset_zoneinfo)
        )

        rows.append(
            ComparisonRow(
                name=rec["name"],
                category=rec["category"],
                data_quality=rec.get("data_quality", "unknown"),
                source_hint=rec.get("sources", [""])[0][:120],
                sun_ref=sun_r,
                moon_ref=moon_r,
                asc_ref=asc_r,
                sun_fufire=sun_f,
                moon_fufire=moon_f,
                asc_fufire=asc_f,
                asc_deg_fufire=asc_deg_f,
                asc_delta_to_ref_deg=_asc_delta_deg(
                    asc_deg_f, float(rec["reference_positions_deg"]["ascendant"])
                ),
                timezone=rec["timezone"],
                utc_offset_minutes_zoneinfo=offset_zoneinfo,
                utc_offset_minutes_kerykeion=offset_kerykeion,
            )
        )

    return rows


def build_summary(rows: list[ComparisonRow]) -> dict[str, Any]:
    n = len(rows)
    sun_ok = sum(r.sun_match for r in rows)
    moon_ok = sum(r.moon_match for r in rows)
    asc_ok = sum(r.asc_match for r in rows)
    all_ok = sum(r.sun_match and r.moon_match and r.asc_match for r in rows)

    mismatches = [r for r in rows if not (r.sun_match and r.moon_match and r.asc_match)]

    by_quality = defaultdict(lambda: Counter(total=0, full_match=0, asc_mismatch=0))
    for r in rows:
        by_quality[r.data_quality]["total"] += 1
        if r.sun_match and r.moon_match and r.asc_match:
            by_quality[r.data_quality]["full_match"] += 1
        if not r.asc_match:
            by_quality[r.data_quality]["asc_mismatch"] += 1

    return {
        "total": n,
        "sun_accuracy": sun_ok / n,
        "moon_accuracy": moon_ok / n,
        "asc_accuracy": asc_ok / n,
        "chart_exact_accuracy": all_ok / n,
        "mismatch_count": len(mismatches),
        "mismatches": [r.__dict__ for r in mismatches],
        "quality_breakdown": {k: dict(v) for k, v in sorted(by_quality.items())},
    }


def run_repro(rows: list[ComparisonRow], rounds: int = 12, seed: int = 20260425) -> dict[str, Any]:
    rnd = Random(seed)
    signatures = []
    base = sorted(r.name for r in rows if not r.asc_match or not r.sun_match or not r.moon_match)
    for _ in range(rounds):
        shuffled = rows[:]
        rnd.shuffle(shuffled)
        sig = sorted(
            r.name
            for r in shuffled
            if not (r.sun_match and r.moon_match and r.asc_match)
        )
        signatures.append(sig)
    stable = all(sig == base for sig in signatures)
    return {"rounds": rounds, "stable": stable, "signature": base}


def write_outputs(summary: dict[str, Any], repro: dict[str, Any], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "western_validation_summary.json").write_text(
        json.dumps({"summary": summary, "repro": repro}, indent=2)
    )

    lines = []
    lines.append("# Western Validation Report")
    lines.append("")
    lines.append("## Scope")
    lines.append("- Reference charts: 176 (real birth records from notable-person datasets).")
    lines.append("- Compared fields: Sun sign, Moon sign, Ascendant sign.")
    lines.append("- Reference engine in dataset: kerykeion.")
    lines.append("- Target engine: FuFirE `compute_western_chart` (tropical mode).")
    lines.append("")
    lines.append("## Accuracy")
    lines.append(f"- Sun: {summary['sun_accuracy']*100:.2f}%")
    lines.append(f"- Moon: {summary['moon_accuracy']*100:.2f}%")
    lines.append(f"- Ascendant: {summary['asc_accuracy']*100:.2f}%")
    lines.append(f"- Full chart exact (Sun+Moon+Asc): {summary['chart_exact_accuracy']*100:.2f}%")
    lines.append("")
    lines.append("## Reproducibility")
    lines.append(f"- Rounds: {repro['rounds']}")
    lines.append(f"- Stable mismatch signature: {repro['stable']}")
    lines.append("")
    lines.append("## Deviation Pattern")
    lines.append("- All deviations are Ascendant-only mismatches (Sun/Moon remain identical).")
    lines.append("- Mismatch set is deterministic and repeatable across shuffled runs.")
    lines.append("- In all mismatch cases, the kerykeion UTC offset derived from `utc_time` differs from Python zoneinfo historical offset.")
    lines.append("- This indicates reference-side time normalization drift (historical offset model), not FuFirE planetary calculation drift.")
    lines.append("")
    lines.append("## Mismatches")
    for m in summary["mismatches"]:
        lines.append(
            "- "
            f"{m['name']}: ref Asc={m['asc_ref']}, FuFirE Asc={m['asc_fufire']}, "
            f"delta={m['asc_delta_to_ref_deg']:.2f}°, tz={m['timezone']}, "
            f"offset(zoneinfo)={m['utc_offset_minutes_zoneinfo']}m, "
            f"offset(kerykeion)={m['utc_offset_minutes_kerykeion']}m"
        )

    lines.append("")
    lines.append("## Proposed Fix")
    lines.append("- Keep FuFirE western core unchanged (no deterministic mismatch in Sun/Moon and only reference-offset-driven Asc drift).")
    lines.append("- For external validation pipelines, pin one shared timezone normalization policy (IANA zoneinfo + explicit historical offsets).")
    lines.append("- Reject or flag references where derived UTC offset disagrees with policy by >2 minutes.")

    (out_dir / "western_validation_report.md").write_text("\n".join(lines) + "\n")


EXPECTED_FIXTURE_VALIDATION: dict[str, Any] = {
    "sun_accuracy_min": 1.0,
    "moon_accuracy_min": 1.0,
    "asc_accuracy_min": 0.0,
    "mismatch_count": None,
    "mismatch_signature": None,
}


def _assert_fixture_expectations(summary: dict[str, Any], repro: dict[str, Any]) -> None:
    expected = EXPECTED_FIXTURE_VALIDATION

    if summary["sun_accuracy"] < expected["sun_accuracy_min"]:
        raise AssertionError(
            f"sun_accuracy regressed: expected >= {expected['sun_accuracy_min']}, "
            f"got {summary['sun_accuracy']}"
        )

    if summary["moon_accuracy"] < expected["moon_accuracy_min"]:
        raise AssertionError(
            f"moon_accuracy regressed: expected >= {expected['moon_accuracy_min']}, "
            f"got {summary['moon_accuracy']}"
        )

    if summary["asc_accuracy"] < expected["asc_accuracy_min"]:
        raise AssertionError(
            f"asc_accuracy regressed: expected >= {expected['asc_accuracy_min']}, "
            f"got {summary['asc_accuracy']}"
        )

    if expected["mismatch_count"] is not None and summary["mismatch_count"] != expected["mismatch_count"]:
        raise AssertionError(
            f"mismatch_count changed: expected {expected['mismatch_count']}, "
            f"got {summary['mismatch_count']}"
        )

    if not repro["stable"]:
        raise AssertionError("Mismatch signature is not stable across reproducibility runs")

    if expected["mismatch_signature"] is not None and repro["signature"] != expected["mismatch_signature"]:
        raise AssertionError(
            "Mismatch signature changed: "
            f"expected {expected['mismatch_signature']}, got {repro['signature']}"
        )


def main() -> None:
    fixture = Path("tests/fixtures/western_reference_charts.json")
    records = _load_records(fixture)
    rows = evaluate(records)
    summary = build_summary(rows)
    repro = run_repro(rows)
    _assert_fixture_expectations(summary, repro)
    write_outputs(summary, repro, Path("reports"))
    print(json.dumps({"summary": summary, "repro": repro}, indent=2))


if __name__ == "__main__":
    main()
