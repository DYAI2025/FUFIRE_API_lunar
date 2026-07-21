#!/usr/bin/env python3
"""
derive_affinity.py — Leite AFFINITY_MAP-Zeilen aus Quiz-Text ab.

Nutzt LeanDeep-annotator als semantischen Analysator.
Uebersetzt LeanDeep-VAD-Koordinaten in 12-Sektor-Gewichte.

Drei Modi:
  derive   — Text -> neue AFFINITY_MAP-Zeile
  validate — Bestehende Zeile gegen LeanDeep pruefen
  batch    — Quiz-JSON -> alle Zeilen auf einmal

Voraussetzung: LeanDeep-annotator laeuft auf localhost:8420
               (oder via --leandeep-url konfigurierbar)

Beispiele:
  python -m tools.derive_affinity derive \
    --keyword physical_touch \
    --text "Koerperliche Naehe, Beruehrung als Sprache der Liebe"

  python -m tools.derive_affinity validate \
    --keyword physical_touch \
    --text "Koerperliche Naehe, Beruehrung als Sprache der Liebe"

  python -m tools.derive_affinity batch \
    --quiz-json path/to/love-languages-quiz.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from tools.sector_vad import SECTOR_NAMES, VADProfile
from tools.affinity_math import compute_affinity_row, compare_rows, format_affinity_row_ts
from tools.leandeep_client import LeanDeepClient
from tools.load_existing_map import get_existing, EXISTING_AFFINITY_MAP


# ===============================================================================
# MODE: DERIVE
# ===============================================================================

def cmd_derive(args: argparse.Namespace) -> int:
    """Leite eine neue AFFINITY_MAP-Zeile ab."""
    client = LeanDeepClient(base_url=args.leandeep_url)

    if not client.health():
        print(f"ERROR: LeanDeep nicht erreichbar unter {args.leandeep_url}", file=sys.stderr)
        return 1

    print(f"\n{'='*60}")
    print(f"DERIVE: '{args.keyword}'")
    print(f"Text: {args.text[:100]}{'...' if len(args.text) > 100 else ''}")
    print(f"{'='*60}\n")

    # LeanDeep analysieren
    vad, debug = client.derive_vad(args.text)
    print(f"LeanDeep Detections: {debug['detection_count']}")
    print(f"VAD Sources: {debug.get('vad_sources', 0)}")
    if debug.get("warning"):
        print(f"WARNING: {debug['warning']}")

    print(f"\nAggregiertes VAD: V={vad.valence:+.3f}  A={vad.arousal:.3f}  D={vad.dominance:.3f}")

    if debug.get("markers"):
        print(f"\nTop-Marker:")
        for m in sorted(debug["markers"], key=lambda x: x.get("confidence", 0), reverse=True)[:5]:
            mv = m["vad"]
            print(f"  {m['id']:40s}  conf={m['confidence']:.2f}  V={mv['v']:+.2f} A={mv['a']:.2f} D={mv['d']:.2f}")

    # Affinitaet berechnen
    row = compute_affinity_row(vad)
    print(f"\nBerechnete Affinitaet:")
    for s in range(12):
        bar = "█" * int(row[s] * 40)
        print(f"  S{s:2d} {SECTOR_NAMES[s]:12s}  {row[s]:.2f}  {bar}")

    # Gegen bestehende Map vergleichen
    existing = get_existing(args.keyword)
    if existing:
        print(f"\nVergleich mit bestehender Map:")
        result = compare_rows(row, existing, threshold=args.threshold)
        if result["coherent"]:
            print(f"  Status: KOHAERENT (max delta: {result['max_delta']:.3f})")
        else:
            print(f"  Status: ABWEICHUNG (max delta: {result['max_delta']:.3f})")
            for w in result["warnings"]:
                print(f"  ! {w}")
    else:
        domain = args.keyword.split("_")[0] if "_" in args.keyword else None
        if domain and domain in EXISTING_AFFINITY_MAP:
            print(f"\nKein Keyword-Eintrag. Domain-Fallback waere '{domain}':")
            fallback = EXISTING_AFFINITY_MAP[domain]
            result = compare_rows(row, fallback, threshold=args.threshold)
            if not result["coherent"]:
                print(f"  ! Fallback zu unscharf (max delta: {result['max_delta']:.3f})")
                print(f"  -> EMPFEHLUNG: Keyword-Zeile anlegen")
            else:
                print(f"  Fallback ausreichend (max delta: {result['max_delta']:.3f})")
        else:
            print(f"\nKein bestehender Eintrag. Neue Zeile:")

    # TypeScript Output
    print(f"\n{'─'*60}")
    print(f"TypeScript (copy-paste in AFFINITY_MAP):\n")
    print(format_affinity_row_ts(args.keyword, row))
    print()

    return 0


# ===============================================================================
# MODE: VALIDATE
# ===============================================================================

def cmd_validate(args: argparse.Namespace) -> int:
    """Validiere eine bestehende AFFINITY_MAP-Zeile."""
    client = LeanDeepClient(base_url=args.leandeep_url)

    if not client.health():
        print(f"ERROR: LeanDeep nicht erreichbar", file=sys.stderr)
        return 1

    existing = get_existing(args.keyword)
    if not existing:
        print(f"ERROR: Keyword '{args.keyword}' nicht in bestehender Map", file=sys.stderr)
        return 1

    vad, debug = client.derive_vad(args.text)
    row = compute_affinity_row(vad)
    result = compare_rows(row, existing, threshold=args.threshold)

    print(f"\nVALIDATE: '{args.keyword}'")
    print(f"VAD: V={vad.valence:+.3f}  A={vad.arousal:.3f}  D={vad.dominance:.3f}")
    print(f"Detections: {debug['detection_count']}")

    print(f"\n{'Sektor':<20s} {'Computed':>9s} {'Existing':>9s} {'Delta':>7s}")
    print(f"{'─'*48}")
    for s in range(12):
        delta = abs(row[s] - existing[s])
        flag = " !" if delta >= args.threshold else ""
        print(f"  S{s:2d} {SECTOR_NAMES[s]:<12s} {row[s]:>7.2f}   {existing[s]:>7.2f}   {delta:>5.3f}{flag}")

    print(f"\n{'─'*48}")
    if result["coherent"]:
        print(f"ERGEBNIS: KOHAERENT  (max delta = {result['max_delta']:.3f} < {args.threshold})")
    else:
        print(f"ERGEBNIS: MISMATCH  (max delta = {result['max_delta']:.3f} >= {args.threshold})")
        print(f"\nVorgeschlagene Korrektur:")
        print(format_affinity_row_ts(args.keyword, row))

    return 0 if result["coherent"] else 2


# ===============================================================================
# MODE: BATCH
# ===============================================================================

def cmd_batch(args: argparse.Namespace) -> int:
    """Batch-Verarbeitung eines Quiz-JSON.

    Erwartet JSON mit 'profiles' Array. Jedes Profil hat:
      - id: string (wird als keyword genutzt)
      - title: string
      - description: string (wird an LeanDeep gesendet)
    """
    client = LeanDeepClient(base_url=args.leandeep_url)

    if not client.health():
        print(f"ERROR: LeanDeep nicht erreichbar", file=sys.stderr)
        return 1

    quiz_path = Path(args.quiz_json)
    if not quiz_path.exists():
        print(f"ERROR: {quiz_path} nicht gefunden", file=sys.stderr)
        return 1

    quiz = json.loads(quiz_path.read_text(encoding="utf-8"))
    profiles = quiz.get("profiles", [])
    if not profiles:
        print(f"ERROR: Keine 'profiles' in {quiz_path}", file=sys.stderr)
        return 1

    quiz_title = quiz.get("meta", {}).get("title", quiz_path.stem)
    print(f"\nBATCH: {quiz_title}")
    print(f"Profile: {len(profiles)}")
    print(f"{'='*60}\n")

    results = []
    all_coherent = True

    for profile in profiles:
        pid = profile.get("id", "unknown")
        desc = profile.get("description", profile.get("tagline", profile.get("title", "")))
        if not desc:
            print(f"  SKIP: {pid} — keine Beschreibung")
            continue

        vad, debug = client.derive_vad(desc)
        row = compute_affinity_row(vad)

        existing = get_existing(pid)
        status = "NEW"
        coherent = True
        if existing:
            comp = compare_rows(row, existing, threshold=args.threshold)
            coherent = comp["coherent"]
            status = "OK" if coherent else "MISMATCH"
            if not coherent:
                all_coherent = False

        # Peak-Sektoren
        peaks = sorted(range(12), key=lambda s: row[s], reverse=True)[:3]
        peak_str = ", ".join(f"S{s}({SECTOR_NAMES[s]})" for s in peaks)

        print(f"  {pid:25s}  V={vad.valence:+.2f} A={vad.arousal:.2f} D={vad.dominance:.2f}  "
              f"Peaks: {peak_str}  [{status}]")

        results.append({
            "keyword": pid,
            "vad": {"v": vad.valence, "a": vad.arousal, "d": vad.dominance},
            "row": row,
            "status": status,
            "peaks": peaks,
        })

    # Summary
    print(f"\n{'='*60}")
    print(f"Ergebnis: {'ALLE KOHAERENT' if all_coherent else 'MISMATCHES GEFUNDEN'}\n")

    # TypeScript Output fuer neue/korrigierte Zeilen
    new_lines = [r for r in results if "NEW" in r["status"] or "MISMATCH" in r["status"]]
    if new_lines:
        print(f"Neue/korrigierte AFFINITY_MAP Zeilen:\n")
        for r in new_lines:
            print(format_affinity_row_ts(r["keyword"], r["row"]))
        print()

    # JSON Output fuer maschinelle Weiterverarbeitung
    if args.output:
        out_path = Path(args.output)
        out_path.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"JSON Output: {out_path}")

    return 0 if all_coherent else 2


# ===============================================================================
# BONUS: VALIDATE-ALL
# ===============================================================================

def cmd_validate_all(args: argparse.Namespace) -> int:
    """Validiere ALLE bestehenden AFFINITY_MAP-Eintraege.

    Braucht eine Mapping-Datei die Keywords auf Beschreibungstexte mappt.
    Format: JSON { "keyword": "Beschreibungstext", ... }
    """
    client = LeanDeepClient(base_url=args.leandeep_url)

    if not client.health():
        print(f"ERROR: LeanDeep nicht erreichbar", file=sys.stderr)
        return 1

    desc_path = Path(args.descriptions)
    if not desc_path.exists():
        print(f"ERROR: {desc_path} nicht gefunden", file=sys.stderr)
        return 1

    descriptions: dict[str, str] = json.loads(desc_path.read_text(encoding="utf-8"))

    print(f"\nVALIDATE-ALL: {len(descriptions)} Keywords")
    print(f"{'='*60}\n")

    mismatches = 0
    for keyword, text in descriptions.items():
        existing = get_existing(keyword)
        if not existing:
            print(f"  {keyword:25s}  SKIP (nicht in Map)")
            continue

        vad, _ = client.derive_vad(text)
        row = compute_affinity_row(vad)
        result = compare_rows(row, existing, threshold=args.threshold)

        status = "OK" if result["coherent"] else f"delta={result['max_delta']:.3f} MISMATCH"
        if not result["coherent"]:
            mismatches += 1
        print(f"  {keyword:25s}  {status}")

    print(f"\n{'='*60}")
    print(f"Ergebnis: {len(descriptions) - mismatches}/{len(descriptions)} kohaerent")
    if mismatches:
        print(f"          {mismatches} Mismatches — mit 'derive' Modus einzeln pruefen")

    return 0 if mismatches == 0 else 2


# ===============================================================================
# CLI ENTRY POINT
# ===============================================================================

def main() -> int:
    parser = argparse.ArgumentParser(
        description="LeanDeep Affinity Derivation Tool — leite AFFINITY_MAP-Zeilen aus Text ab",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--leandeep-url",
        default="http://localhost:8420",
        help="LeanDeep-annotator URL (default: http://localhost:8420)",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.15,
        help="Max delta fuer Kohaerenz-Check (default: 0.15)",
    )

    sub = parser.add_subparsers(dest="command", required=True)

    # derive
    p_derive = sub.add_parser("derive", help="Text -> neue AFFINITY_MAP-Zeile")
    p_derive.add_argument("--keyword", required=True, help="Marker-Keyword (z.B. physical_touch)")
    p_derive.add_argument("--text", required=True, help="Beschreibungstext fuer semantische Analyse")

    # validate
    p_validate = sub.add_parser("validate", help="Bestehende Zeile gegen LeanDeep pruefen")
    p_validate.add_argument("--keyword", required=True)
    p_validate.add_argument("--text", required=True)

    # batch
    p_batch = sub.add_parser("batch", help="Quiz-JSON -> alle Keyword-Zeilen")
    p_batch.add_argument("--quiz-json", required=True, help="Pfad zur Quiz-JSON Datei")
    p_batch.add_argument("--output", help="Optional: JSON Output-Pfad")

    # validate-all
    p_all = sub.add_parser("validate-all", help="Alle bestehenden Map-Eintraege pruefen")
    p_all.add_argument("--descriptions", required=True, help="JSON: { keyword: beschreibung, ... }")

    args = parser.parse_args()

    commands = {
        "derive": cmd_derive,
        "validate": cmd_validate,
        "batch": cmd_batch,
        "validate-all": cmd_validate_all,
    }

    return commands[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
