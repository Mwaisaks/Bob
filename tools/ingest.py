"""
ingest.py — loads M-Pesa data into the ledger via the parser pipeline.

Three sources:
  - Synthetic demo data: reads .jsonl from data/synthetic/ and passes each
    raw SMS through parse_sms() — the same path real SMS would follow.
    Ground truth is ignored at ingest time; it only exists for
    eval/parser_eval.py.
  - A real M-Pesa statement PDF (the *334# journey): parsed via
    tools/statement_parser.py and ingested under a persona label of your
    choice (default "me").
  - Your own real SMS, exported as text: either messages you've copy/pasted
    (one per paragraph, blank-line separated), or JSON from
    `termux-sms-list` (Termux:API on Android — see README). Both go through
    the same parse_sms() as the synthetic path.

Usage:
    python tools/ingest.py                              # ingest all synthetic personas
    python tools/ingest.py --persona brian               # ingest one persona
    python tools/ingest.py --reset                       # clear ledger first, then ingest
    python tools/ingest.py --statement path/to/statement.pdf
                                                           # ingest a real statement (prompts for password)
    python tools/ingest.py --sms-file path/to/messages.txt
                                                           # ingest pasted/exported SMS text
"""

import argparse
import getpass
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from agent.ledger import Ledger
from tools.sms_parser import parse_sms
from tools.statement_parser import parse_statement, extract_statement_text, reconcile

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


def _read_sms_messages(path: Path) -> list[str]:
    """
    Accepts two formats:
      - JSON array (e.g. `termux-sms-list` output): pulls the "body" (or
        "text") field from each object.
      - Plain text: messages separated by one or more blank lines, e.g. a
        user pasting several forwarded SMS into a .txt file.
    """
    raw = path.read_text(encoding="utf-8").strip()
    if raw.startswith("["):
        records = json.loads(raw)
        return [r.get("body") or r.get("text") or "" for r in records]

    blocks = re.split(r"\n\s*\n", raw)
    return [" ".join(b.split()) for b in blocks if b.strip()]


def ingest_sms_text(path: Path, persona: str, ledger: Ledger) -> tuple[int, int]:
    """
    Parse and insert every SMS found in a pasted-text or termux-sms-list
    JSON export. Returns (ingested_count, failed_count).
    """
    ingested = 0
    failed = 0

    for sms in _read_sms_messages(path):
        if not sms.strip():
            continue
        tx, status = parse_sms(sms)
        if tx is None:
            failed += 1
            continue
        ledger.insert(persona, tx.model_dump(), raw_sms=sms)
        ingested += 1

    return ingested, failed


def ingest_statement(pdf_path: Path, password: str, persona: str, ledger: Ledger) -> tuple[int, int]:
    """
    Parse a real M-Pesa statement PDF and insert every transaction.
    Returns (ingested_count, stats) — stats includes the regex/gemma split
    and a reconciliation against the statement's own printed SUMMARY totals.
    """
    transactions, parse_stats = parse_statement(pdf_path, password)
    for tx in transactions:
        ledger.insert(persona, tx, raw_sms="")

    text = extract_statement_text(pdf_path, password)
    parse_stats["reconciliation"] = reconcile(transactions, text)
    return len(transactions), parse_stats


def main():
    parser = argparse.ArgumentParser(description="Ingest M-Pesa data into the ledger")
    parser.add_argument("--persona", choices=["brian", "wanjiku", "athman"],
                        help="Ingest a single synthetic persona only")
    parser.add_argument("--reset", action="store_true",
                        help="Clear existing records before ingesting")
    parser.add_argument("--statement", type=Path,
                        help="Path to a real M-Pesa statement PDF (from *334#)")
    parser.add_argument("--password",
                        help="Statement PDF password (prompted securely if omitted)")
    parser.add_argument("--sms-file", type=Path,
                        help="Path to pasted SMS text or termux-sms-list JSON export")
    parser.add_argument("--persona-label", default="me",
                        help="Persona name to store real data under (default: me)")
    args = parser.parse_args()

    if args.statement and args.sms_file:
        parser.error("--statement and --sms-file are mutually exclusive")

    ledger = Ledger()

    if args.statement:
        password = args.password or getpass.getpass("Statement PDF password: ")
        ledger.clear(persona=args.persona_label)
        count, stats = ingest_statement(args.statement, password, args.persona_label, ledger)
        print(f"✅ {args.persona_label:<10} {count} transactions ingested "
              f"({stats['via_regex']} via regex, {stats['via_gemma']} via Gemma)")
        recon = stats["reconciliation"]
        print(f"   Reconciliation vs statement totals: "
              f"Paid In delta {recon['paid_in_delta']:+.2f}, "
              f"Withdrawn delta {recon['withdrawn_delta']:+.2f}")
        print(f"\nLedger now holds {ledger.count()} total transactions.")
        return

    if args.sms_file:
        ledger.clear(persona=args.persona_label)
        ingested, failed = ingest_sms_text(args.sms_file, args.persona_label, ledger)
        status = "✅" if failed == 0 else "⚠️ "
        print(f"{status} {args.persona_label:<10} {ingested} ingested, {failed} failed")
        print(f"\nLedger now holds {ledger.count()} total transactions.")
        return

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
