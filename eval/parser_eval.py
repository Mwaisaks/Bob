"""
parser_eval.py — measures how accurately Gemma parses the synthetic M-Pesa SMS.

Runs tools/sms_parser.py over every record in data/synthetic/*.jsonl and
compares the output against the generator's ground truth.

The accuracy numbers printed here go directly into the competition writeup.

Usage:
    python eval/parser_eval.py [--persona brian|wanjiku|athman] [--limit N]
"""

import argparse
import json
import sys
from typing import Optional
from pathlib import Path

# Project root on the path so we can import tools/
sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.sms_parser import parse_sms, VALID_TYPES

SYNTHETIC_DIR = Path(__file__).parent.parent / "data" / "synthetic"

# Fields we compare between parsed output and ground truth
# timestamp is excluded — minor formatting differences would unfairly penalise good parses
COMPARE_FIELDS = ["type", "amount", "fee", "counterparty", "balance_after"]

# How close floats need to be to count as a match (handles rounding differences)
FLOAT_TOLERANCE = 0.01


def floats_match(a: float, b: float) -> bool:
    return abs(a - b) <= FLOAT_TOLERANCE


def fields_match(parsed: dict, truth: dict) -> dict[str, bool]:
    """
    Returns per-field pass/fail for the comparable fields.
    counterparty: case-insensitive, strip whitespace
    floats: within tolerance
    type: exact
    """
    results = {}
    for field in COMPARE_FIELDS:
        p_val = parsed.get(field)
        t_val = truth.get(field)

        if field in ("amount", "fee", "balance_after"):
            results[field] = floats_match(float(p_val or 0), float(t_val or 0))
        elif field == "counterparty":
            results[field] = (str(p_val or "").strip().upper() ==
                              str(t_val or "").strip().upper())
        else:
            results[field] = str(p_val) == str(t_val)

    return results


def eval_file(path: Path, limit: Optional[int] = None) -> dict:
    records = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            records.append(json.loads(line))
    if limit:
        records = records[:limit]

    total = len(records)
    parse_failures = 0
    regex_path = 0
    gemma_path = 0
    field_totals = {f: 0 for f in COMPARE_FIELDS}
    field_correct = {f: 0 for f in COMPARE_FIELDS}
    fully_correct = 0

    for record in records:
        sms = record["sms"]
        truth = record["ground_truth"]

        tx, status = parse_sms(sms)

        if tx is None:
            parse_failures += 1
            continue

        if status == "regex":
            regex_path += 1
        else:
            gemma_path += 1

        parsed = tx.model_dump()
        match = fields_match(parsed, truth)

        if all(match.values()):
            fully_correct += 1

        for field, ok in match.items():
            field_totals[field] += 1
            if ok:
                field_correct[field] += 1

    return {
        "total": total,
        "parse_failures": parse_failures,
        "regex_path": regex_path,
        "gemma_path": gemma_path,
        "fully_correct": fully_correct,
        "field_totals": field_totals,
        "field_correct": field_correct,
    }


def print_results(persona: str, stats: dict):
    total = stats["total"]
    parseable = total - stats["parse_failures"]
    full_pct = 100 * stats["fully_correct"] / total if total else 0

    print(f"\n{'─' * 52}")
    print(f"  {persona.upper()}")
    print(f"{'─' * 52}")
    print(f"  Total records    : {total}")
    print(f"  Via regex        : {stats['regex_path']}")
    print(f"  Via Gemma        : {stats['gemma_path']}")
    print(f"  Parse failures   : {stats['parse_failures']}")
    print(f"  Fully correct    : {stats['fully_correct']}  ({full_pct:.1f}%)")
    print()
    print(f"  Per-field accuracy (of {parseable} parseable records):")
    for field in COMPARE_FIELDS:
        correct = stats["field_correct"][field]
        tot = stats["field_totals"][field]
        pct = 100 * correct / tot if tot else 0
        bar = "█" * int(pct / 5) + "░" * (20 - int(pct / 5))
        print(f"    {field:<16} {bar}  {correct}/{tot}  ({pct:.1f}%)")


def main():
    parser = argparse.ArgumentParser(description="Evaluate Gemma SMS parser accuracy")
    parser.add_argument("--persona", choices=["brian", "wanjiku", "athman"],
                        help="Run on a single persona only")
    parser.add_argument("--limit", type=int, default=None,
                        help="Cap records per file (useful for a quick test run)")
    args = parser.parse_args()

    files = sorted(SYNTHETIC_DIR.glob("*.jsonl"))
    if args.persona:
        files = [f for f in files if f.stem == args.persona]

    if not files:
        print("No files to evaluate. Run data/generate_synthetic.py first.")
        sys.exit(1)

    all_stats = {}
    for path in files:
        print(f"Parsing {path.name} ...", end=" ", flush=True)
        stats = eval_file(path, limit=args.limit)
        print("done")
        all_stats[path.stem] = stats

    for persona, stats in all_stats.items():
        print_results(persona, stats)

    # Summary row for the writeup
    total_all = sum(s["total"] for s in all_stats.values())
    correct_all = sum(s["fully_correct"] for s in all_stats.values())
    failures_all = sum(s["parse_failures"] for s in all_stats.values())
    overall_pct = 100 * correct_all / total_all if total_all else 0

    print(f"\n{'═' * 52}")
    print(f"  OVERALL: {correct_all}/{total_all} fully correct  ({overall_pct:.1f}%)")
    print(f"           {failures_all} parse failures (invalid JSON)")
    print(f"{'═' * 52}")
    print("\nCopy the overall line into your writeup accuracy table.")


if __name__ == "__main__":
    main()
