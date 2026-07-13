"""
ingest.py — loads M-Pesa SMS into the ledger via the parser pipeline.

For synthetic data: reads .jsonl from data/synthetic/ and passes each raw SMS
through parse_sms() — the same path real SMS would follow. Ground truth is
ignored at ingest time; it only exists for eval/parser_eval.py.

Usage:
    python tools/ingest.py                  # ingest all personas
    python tools/ingest.py --persona brian  # ingest one persona
    python tools/ingest.py --reset          # clear ledger first, then ingest
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from agent.ledger import Ledger
from tools.sms_parser import parse_sms

SYNTHETIC_DIR = Path(__file__).parent.parent / "data" / "synthetic"


def ingest_file(path: Path, persona: str, ledger: Ledger) -> tuple[int, int]:
    """
    Parse and insert every SMS in a .jsonl file.
    Returns (ingested_count, failed_count).
    """
    ingested = 0
    failed = 0

    with open(path, encoding="utf-8") as f:
        for line in f:
            record = json.loads(line)
            sms = record["sms"]

            tx, status = parse_sms(sms)

            if tx is None:
                failed += 1
                continue

            ledger.insert(persona, tx.model_dump(), raw_sms=sms)
            ingested += 1

    return ingested, failed


def main():
    parser = argparse.ArgumentParser(description="Ingest synthetic SMS into the ledger")
    parser.add_argument("--persona", choices=["brian", "wanjiku", "athman"],
                        help="Ingest a single persona only")
    parser.add_argument("--reset", action="store_true",
                        help="Clear existing records before ingesting")
    args = parser.parse_args()

    ledger = Ledger()

    if args.reset:
        target = args.persona if args.persona else None
        ledger.clear(persona=target)
        cleared = f"persona={target}" if target else "all personas"
        print(f"Cleared ledger ({cleared})")

    files = sorted(SYNTHETIC_DIR.glob("*.jsonl"))
    if args.persona:
        files = [f for f in files if f.stem == args.persona]

    if not files:
        print("No .jsonl files found. Run data/generate_synthetic.py first.")
        sys.exit(1)

    total_in = total_fail = 0

    for path in files:
        persona = path.stem
        ingested, failed = ingest_file(path, persona, ledger)
        total_in += ingested
        total_fail += failed
        status = "✅" if failed == 0 else "⚠️ "
        print(f"{status} {persona:<10} {ingested} ingested, {failed} failed")

    print(f"\nLedger now holds {ledger.count()} total transactions.")

    if total_fail > 0:
        print(f"⚠️  {total_fail} record(s) failed to parse.")
        sys.exit(1)


if __name__ == "__main__":
    main()
