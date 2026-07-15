"""
statement_parser.py — parses a real Safaricom M-Pesa PDF statement (the
*334# → My Account → M-PESA Statement journey) into the same transaction
shape the ledger expects.

Same hybrid philosophy as sms_parser.py: a regex classifier handles every
Details phrase seen in a real statement, and Gemma 4 is called only for the
rows the classifier doesn't recognise. Unlike SMS parsing, amount/fee/
balance/timestamp are already reliable (they come from fixed PDF columns,
not freetext) — the only "soft" step is classifying the type and pulling
out a clean counterparty name, so a classification miss degrades to a
labelled "other" row instead of dropping the transaction outright.

No PDF library dependency: the password-protected PDF is decrypted and
its text extracted in one step via poppler's `pdftotext` binary, already
present on most Linux/macOS systems (`apt install poppler-utils` /
`brew install poppler`).
"""

import json
import re
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional

import ollama

MODEL = "gemma4:e2b"
NUM_CTX = 4096

# ---------------------------------------------------------------------------
# PDF -> text
# ---------------------------------------------------------------------------


def extract_statement_text(pdf_path: Path, password: str) -> str:
    """Decrypt + extract the statement as text via pdftotext -layout."""
    try:
        result = subprocess.run(
            ["pdftotext", "-layout", "-upw", password, str(pdf_path), "-"],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except FileNotFoundError:
        raise RuntimeError(
            "pdftotext not found. Install poppler-utils (Linux: "
            "`apt install poppler-utils`, macOS: `brew install poppler`)."
        )
    if result.returncode != 0 or not result.stdout.strip():
        raise RuntimeError(
            f"Could not read the PDF (wrong password, or not a Safaricom "
            f"statement): {result.stderr.strip()}"
        )
    return result.stdout


# ---------------------------------------------------------------------------
# Text -> raw table rows (handles multi-line Details, page headers/footers)
# ---------------------------------------------------------------------------

_ROW_START = re.compile(
    r"^([A-Z0-9]{10})\s+(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\s+(.*)$"
)
_ROW_TAIL = re.compile(
    r"^(?P<details>.*?)\s+(?P<status>Completed|Failed|Reversed)\s+"
    r"(?:(?P<paid_in>[\d,]+\.\d{2})\s+)?"
    r"(?:-(?P<withdrawn>[\d,]+\.\d{2})\s+)?"
    r"(?P<balance>[\d,]+\.\d{2})\s*$"
)

_NOISE_MARKERS = (
    "Disclaimer:", "Statement Verification Code", "For self-help dial",
    "M-PESA STATEMENT", "Customer Name:", "Mobile Number:", "Email Address:",
    "Statement Period:", "Request Date:", "SUMMARY", "TRANSACTION TYPE",
    "DETAILED STATEMENT", "Receipt No.", "TOTAL:",
)


def _amt(s: Optional[str]) -> float:
    return float(s.replace(",", "")) if s else 0.0


def _split_rows(text: str) -> list[dict]:
    """Turn the raw pdftotext output into one dict per physical table row."""
    rows: list[dict] = []
    current: Optional[dict] = None

    for line in text.split("\n"):
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("Page ") and " of " in stripped:
            if current:
                rows.append(current)
            current = None
            continue
        if any(marker in stripped for marker in _NOISE_MARKERS):
            if current:
                rows.append(current)
            current = None
            continue

        m = _ROW_START.match(line)
        if m:
            if current:
                rows.append(current)
            receipt, ts_str, tail = m.group(1), m.group(2), m.group(3)
            tail_m = _ROW_TAIL.match(tail)
            if not tail_m:
                # Status/amount columns not on this line yet — treat the
                # whole tail as the start of Details and keep reading.
                current = {
                    "receipt": receipt, "timestamp": ts_str, "details": tail,
                    "status": None, "paid_in": None, "withdrawn": None,
                    "balance": None,
                }
            else:
                current = {
                    "receipt": receipt,
                    "timestamp": ts_str,
                    "details": tail_m.group("details").strip(),
                    "status": tail_m.group("status"),
                    "paid_in": _amt(tail_m.group("paid_in")),
                    "withdrawn": _amt(tail_m.group("withdrawn")),
                    "balance": _amt(tail_m.group("balance")),
                }
        elif current is not None:
            current["details"] = f"{current['details']} {stripped}".strip()

    if current:
        rows.append(current)

    return [r for r in rows if r.get("status") == "Completed"]


def _group_by_receipt(rows: list[dict]) -> list[dict]:
    """Merge paired '<X> Charge' rows into their sibling's fee."""
    by_receipt: dict[str, list[dict]] = {}
    for r in rows:
        by_receipt.setdefault(r["receipt"], []).append(r)

    merged = []
    for receipt, group in by_receipt.items():
        charges = [r for r in group if "Charge" in r["details"]]
        mains = [r for r in group if "Charge" not in r["details"]]

        if not mains:
            # A lone charge row with no sibling — keep it, it's still real money.
            mains = charges
            charges = []

        main = mains[0]
        fee = sum(c["withdrawn"] for c in charges)
        balance_after = min(
            [main["balance"]] + [c["balance"] for c in charges]
        )
        merged.append({
            "receipt": receipt,
            "timestamp": main["timestamp"],
            "details": main["details"],
            "paid_in": main["paid_in"],
            "withdrawn": main["withdrawn"],
            "fee": fee,
            "balance": balance_after,
        })

    merged.sort(key=lambda r: r["timestamp"])
    return merged


# ---------------------------------------------------------------------------
# Classification — ordered fingerprints, most specific first
# ---------------------------------------------------------------------------

_FINGERPRINTS = [
    ("receive",        re.compile(r"Funds received from")),
    ("receive",        re.compile(r"Offnet B2C Transfer")),
    ("receive",        re.compile(r"Deposit of Funds at Agent Till")),
    ("receive",        re.compile(r"M-Shwari Withdraw")),
    ("receive",        re.compile(r"Business Payment from")),
    ("m_shwari",       re.compile(r"M-Shwari Deposit")),
    ("ziidi",          re.compile(r"Unit Trust Invest To.*ZIIDI", re.I)),
    ("airtime_other",  re.compile(r"MARAPAY SOLUTION")),
    ("airtime_saf",    re.compile(r"Customer Bundle Purchase|Recharge for Customer")),
    ("fuliza_borrow",  re.compile(r"Fuliza M-PESA.*(Advance|Borrow)", re.I)),
    ("fuliza_repay",   re.compile(r"(Repayment|repaid).*Fuliza", re.I)),
    ("paybill",        re.compile(r"Pay ?Bill( Online)? to")),
    ("buy_goods",      re.compile(r"Merchant Payment( Online)? to")),
    ("send_money",     re.compile(r"Customer Transfer to")),
]

_COUNTERPARTY_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("receive",        re.compile(r"from\s*-?\s*[\d\*]+\s*(.+)$")),
    ("receive",        re.compile(r"Business Payment from \d+\s*-\s*([^.]+?)(?:\s+via|$)")),
    ("receive",        re.compile(r"Agent Till\s*\d+\s*-\s*(.+)$")),
    ("receive",        re.compile(r"Offnet B2C Transfer by \d*([A-Z][A-Z\s]+?)\s+via")),
    ("send_money",     re.compile(r"to\s*-?\s*[\d\*]+\s*(.+)$")),
    ("buy_goods",      re.compile(r"to\s*\d+\s*-\s*(.+)$")),
    ("paybill",        re.compile(r"to\s*\d+\s*-\s*([^.]+?)(?:\s+Acc\.|\.|$)")),
]


def _classify(details: str) -> Optional[str]:
    for tx_type, pattern in _FINGERPRINTS:
        if pattern.search(details):
            return tx_type
    return None


def _counterparty(tx_type: str, details: str) -> str:
    if tx_type == "airtime_saf":
        return "SAFARICOM DATA BUNDLES"
    if tx_type == "airtime_other":
        return "MARAPAY SOLUTION"
    if tx_type == "ziidi":
        return "ZIIDI"
    if tx_type == "m_shwari":
        return "M-SHWARI"

    for pattern_type, pattern in _COUNTERPARTY_PATTERNS:
        if pattern_type != tx_type:
            continue
        m = pattern.search(details)
        if m:
            name = re.sub(r"\s+", " ", m.group(1)).strip(" -.")
            if name:
                return name

    # Soft fallback — never drop a transaction over a naming miss.
    return re.sub(r"\s+", " ", details)[:60].strip(" -.")


def _parse_dt(ts: str) -> str:
    dt = datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")
    return dt.strftime("%Y-%m-%dT%H:%M")


# ---------------------------------------------------------------------------
# Gemma fallback — only for rows the regex classifier couldn't identify
# ---------------------------------------------------------------------------

_GEMMA_SYSTEM = """You are parsing a row from a Kenyan M-Pesa statement.
Given the "Details" text, return ONLY valid JSON: {"type": one of
["send_money","receive","buy_goods","paybill","airtime_saf","airtime_other",
"ziidi","m_shwari","fuliza_borrow","fuliza_repay","other"],
"counterparty": short string}. No markdown fences."""


def _gemma_classify(details: str) -> tuple[str, str]:
    try:
        resp = ollama.chat(
            model=MODEL,
            messages=[
                {"role": "system", "content": _GEMMA_SYSTEM},
                {"role": "user", "content": details},
            ],
            options={"num_ctx": NUM_CTX},
        )
        raw = re.sub(r"```(?:json)?\s*", "", resp.message.content).strip()
        data = json.loads(raw)
        return data.get("type", "other"), data.get("counterparty", details[:60])
    except Exception:
        return "other", details[:60]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse_statement(pdf_path: Path, password: str) -> tuple[list[dict], dict]:
    """
    Parse a Safaricom M-Pesa PDF statement into ledger-ready transaction dicts.

    Returns:
        (transactions, stats) where stats = {rows_total, via_regex, via_gemma}
    """
    text = extract_statement_text(pdf_path, password)
    detail_start = text.find("DETAILED STATEMENT")
    detail_text = text[detail_start:] if detail_start != -1 else text

    rows = _group_by_receipt(_split_rows(detail_text))

    transactions = []
    via_regex = via_gemma = 0

    for row in rows:
        tx_type = _classify(row["details"])
        if tx_type:
            via_regex += 1
            counterparty = _counterparty(tx_type, row["details"])
        else:
            tx_type, counterparty = _gemma_classify(row["details"])
            via_gemma += 1

        amount = row["paid_in"] if row["paid_in"] else row["withdrawn"]

        transactions.append({
            "type": tx_type,
            "amount": round(amount, 2),
            "fee": round(row["fee"], 2),
            "counterparty": counterparty,
            "balance_after": round(row["balance"], 2),
            "timestamp": _parse_dt(row["timestamp"]),
            "raw_ref": row["receipt"],
        })

    stats = {
        "rows_total": len(transactions),
        "via_regex": via_regex,
        "via_gemma": via_gemma,
    }
    return transactions, stats


# ---------------------------------------------------------------------------
# Reconciliation — verify against the statement's own printed SUMMARY totals
# (there's no external ground truth for real data, so this is the honest
# verification method: does our parse sum to what Safaricom itself printed)
# ---------------------------------------------------------------------------

_TOTAL_LINE = re.compile(r"TOTAL:\s+([\d,]+\.\d{2})\s+([\d,]+\.\d{2})")


def reconcile(transactions: list[dict], statement_text: str) -> dict:
    m = _TOTAL_LINE.search(statement_text)
    stated_paid_in = _amt(m.group(1)) if m else None
    stated_withdrawn = _amt(m.group(2)) if m else None

    parsed_paid_in = sum(
        t["amount"] for t in transactions if t["type"] == "receive"
    )
    parsed_withdrawn = sum(
        t["amount"] + t["fee"] for t in transactions if t["type"] != "receive"
    )

    return {
        "stated_paid_in": stated_paid_in,
        "parsed_paid_in": round(parsed_paid_in, 2),
        "paid_in_delta": round(parsed_paid_in - (stated_paid_in or 0), 2),
        "stated_withdrawn": stated_withdrawn,
        "parsed_withdrawn": round(parsed_withdrawn, 2),
        "withdrawn_delta": round(parsed_withdrawn - (stated_withdrawn or 0), 2),
    }
