"""
validate_synthetic.py — sanity-checks the generated SMS data before Phase 2.

Not a full parser (that's Gemma's job in Phase 2). Just confirms:
  1. Every SMS looks like a real M-Pesa message (transaction code, amount, balance line)
  2. Every ground_truth record has all the fields the Phase 2 parser is expected to produce

Exit code 0 = all clear. Exit code 1 = something is broken, fix the generator.
"""

import json
import re
import sys
from pathlib import Path

SYNTHETIC_DIR = Path(__file__).parent / "synthetic"

# Patterns that must appear in every valid M-Pesa SMS
SMS_CHECKS = {
    "transaction_code": re.compile(r"U[A-Z0-9]{9}"),
    "amount":           re.compile(r"[Kk][Ss][Hh][\d,]+\.\d{2}"),
    "balance_line":     re.compile(r"M-PESA balance is"),
}

# Fields that every ground_truth dict must contain
REQUIRED_GT_FIELDS = {"type", "amount", "fee", "counterparty", "balance_after", "timestamp"}


def check_record(record: dict) -> list[str]:
    """
    Returns a list of failure reasons. Empty list = record is clean.
    """
    failures = []
    sms = record.get("sms", "")
    gt = record.get("ground_truth", {})

    for label, pattern in SMS_CHECKS.items():
        if not pattern.search(sms):
            failures.append(f"SMS missing {label}")

    missing_fields = REQUIRED_GT_FIELDS - gt.keys()
    if missing_fields:
        failures.append(f"ground_truth missing fields: {missing_fields}")

    return failures


def validate_file(path: Path) -> tuple[int, int]:
    """
    Validates one .jsonl file. Returns (pass_count, fail_count).
    Prints details for any failures.
    """
    passed = 0
    failed = 0

    with open(path, encoding="utf-8") as f:
        for line_num, line in enumerate(f, start=1):
            record = json.loads(line)
            issues = check_record(record)

            if issues:
                failed += 1
                print(f"  [FAIL] line {line_num}: {'; '.join(issues)}")
                print(f"         SMS: {record.get('sms', '')[:80]}...")
            else:
                passed += 1

    return passed, failed


def main() -> int:
    jsonl_files = sorted(SYNTHETIC_DIR.glob("*.jsonl"))

    if not jsonl_files:
        print(f"No .jsonl files found in {SYNTHETIC_DIR}. Run generate_synthetic.py first.")
        return 1

    overall_failed = 0

    for path in jsonl_files:
        passed, failed = validate_file(path)
        total = passed + failed
        status = "✅" if failed == 0 else "❌"
        print(f"{status}  {path.name:<20} — {total} records: {passed} pass, {failed} fail")
        overall_failed += failed

    if overall_failed > 0:
        print(f"\n{overall_failed} record(s) failed. Fix generate_synthetic.py and re-run.")
        return 1

    print("\nAll records valid.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
