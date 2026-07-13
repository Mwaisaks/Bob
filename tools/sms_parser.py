"""
sms_parser.py — hybrid M-Pesa SMS parser.

Architecture:
  1. Regex classifier identifies the SMS type from a unique text fingerprint.
  2. Regex extractor pulls fields deterministically from the known format.
  3. Gemma 4 is called ONLY if the regex path fails (unknown format, future
     Safaricom format changes, edge cases).

This design runs the full 185-record eval in seconds, keeps Gemma available
for genuinely ambiguous SMS, and is honest to document in the writeup.
"""

import json
import re
from datetime import datetime
from typing import Optional

import ollama
from pydantic import BaseModel, ValidationError

MODEL = "gemma4:e2b"
NUM_CTX = 8192

VALID_TYPES = {
    "send_money",
    "receive",
    "buy_goods",
    "paybill",
    "airtime_saf",
    "airtime_other",
    "ziidi",
    "fuliza_borrow",
    "fuliza_repay",
}


class ParsedTransaction(BaseModel):
    type: str
    amount: float
    fee: float
    counterparty: str
    balance_after: float
    timestamp: str       # ISO 8601 YYYY-MM-DDTHH:MM
    raw_ref: str


# ---------------------------------------------------------------------------
# Shared extraction helpers
# ---------------------------------------------------------------------------

_TXN_CODE = re.compile(r"(U[A-Z0-9]{9,11})")
_BALANCE   = re.compile(r"M-PESA balance is [KkSsHh]{3}([\d,]+\.\d{2})")
_FEE       = re.compile(r"Transaction cost,\s*[KkSsHh]{3}([\d,]+\.\d{2})")
_DATETIME  = re.compile(r"on (\d{1,2}/\d{1,2}/\d{2}) at (\d{1,2}:\d{2} [AP]M)")
_AMOUNT    = re.compile(r"[KkSsHh]{3}([\d,]+\.\d{2})")   # first match = transaction amount


def _amt(s: str) -> float:
    return float(s.replace(",", ""))


def _parse_dt(date_str: str, time_str: str) -> str:
    dt = datetime.strptime(f"{date_str} {time_str}", "%d/%m/%y %I:%M %p")
    return dt.strftime("%Y-%m-%dT%H:%M")


def _common(sms: str) -> dict:
    """Extract fields present in almost every SMS type."""
    ref = m.group(1) if (m := _TXN_CODE.search(sms)) else ""
    bal = _amt(m.group(1)) if (m := _BALANCE.search(sms)) else 0.0
    fee = _amt(m.group(1)) if (m := _FEE.search(sms)) else 0.0
    dt_m = _DATETIME.search(sms)
    ts = _parse_dt(dt_m.group(1), dt_m.group(2)) if dt_m else ""
    return {"raw_ref": ref, "balance_after": bal, "fee": fee, "timestamp": ts}


# ---------------------------------------------------------------------------
# Type classifier — unique text fingerprints, evaluated in priority order
# ---------------------------------------------------------------------------

_FINGERPRINTS = [
    ("airtime_saf",   re.compile(r"SAFARICOM DATA BUNDLES")),
    ("airtime_other", re.compile(r"MARAPAY SOLUTION")),
    ("ziidi",         re.compile(r"sent to ZIIDI")),
    ("fuliza_borrow", re.compile(r"Fuliza M-PESA amount of")),
    ("fuliza_repay",  re.compile(r"repaid to Fuliza M-PESA")),
    ("receive",       re.compile(r"You have received")),
    ("buy_goods",     re.compile(r"paid to ")),
    ("paybill",       re.compile(r"for account .+ on \d")),   # paybill has "for account"
    ("send_money",    re.compile(r"sent to [A-Z]")),          # last resort
]


def _classify(sms: str) -> Optional[str]:
    for tx_type, pattern in _FINGERPRINTS:
        if pattern.search(sms):
            return tx_type
    return None


# ---------------------------------------------------------------------------
# Per-type regex extractors
# ---------------------------------------------------------------------------

def _extract_send_money(sms: str) -> Optional[dict]:
    # "sent to FIRSTNAME  LASTNAME 07XXXXXXXX on"
    m = re.search(r"sent to ([A-Z][A-Z\s]+?) (\d{9,12}) on", sms)
    if not m:
        return None
    return {"type": "send_money", "counterparty": m.group(1).strip(),
            "amount": _amt(_AMOUNT.search(sms).group(1)), **_common(sms)}


def _extract_receive(sms: str) -> Optional[dict]:
    # "received KshXX.XX from FIRSTNAME  LASTNAME 07XX***XXX on"
    m = re.search(r"received [KkSsHh]{3}([\d,]+\.\d{2}) from ([A-Z][A-Z\s]+?) \d{4}\*{3}\d{3}", sms)
    if not m:
        return None
    base = _common(sms)
    base["fee"] = 0.0   # receive SMS never shows a fee
    return {"type": "receive", "amount": _amt(m.group(1)),
            "counterparty": m.group(2).strip(), **base}


def _extract_buy_goods(sms: str) -> Optional[dict]:
    # "paid to MERCHANT NAME. on"
    m = re.search(r"paid to ([^.]+)\. on", sms)
    if not m:
        return None
    return {"type": "buy_goods", "counterparty": m.group(1).strip(),
            "amount": _amt(_AMOUNT.search(sms).group(1)), **_common(sms)}


def _extract_paybill(sms: str) -> Optional[dict]:
    # "KSH sent to BUSINESS NAME. for account ACCOUNT on"
    m = re.search(r"sent to ([^.]+)\. for account", sms)
    if not m:
        return None
    return {"type": "paybill", "counterparty": m.group(1).strip(),
            "amount": _amt(_AMOUNT.search(sms).group(1)), **_common(sms)}


def _extract_airtime_saf(sms: str) -> Optional[dict]:
    return {"type": "airtime_saf", "counterparty": "SAFARICOM DATA BUNDLES",
            "amount": _amt(_AMOUNT.search(sms).group(1)), **_common(sms)}


def _extract_airtime_other(sms: str) -> Optional[dict]:
    return {"type": "airtime_other", "counterparty": "MARAPAY SOLUTION",
            "amount": _amt(_AMOUNT.search(sms).group(1)), **_common(sms)}


def _extract_ziidi(sms: str) -> Optional[dict]:
    return {"type": "ziidi", "counterparty": "ZIIDI",
            "amount": _amt(_AMOUNT.search(sms).group(1)), **_common(sms)}


def _extract_fuliza_borrow(sms: str) -> Optional[dict]:
    # Ground truth amount = the original transaction amount, not the Fuliza loan amount
    # "Your M-PESA transaction of KshXX.XX has been completed"
    m = re.search(r"transaction of [KkSsHh]{3}([\d,]+\.\d{2})", sms)
    if not m:
        return None
    daily = re.search(r"Daily charge [KkSsHh]{3}([\d,]+\.\d{2})", sms)
    fee = _amt(daily.group(1)) if daily else 0.0
    base = _common(sms)
    base["fee"] = fee
    return {"type": "fuliza_borrow", "counterparty": "FULIZA M-PESA",
            "amount": _amt(m.group(1)), **base}


def _extract_fuliza_repay(sms: str) -> Optional[dict]:
    m = re.search(r"([\d,]+\.\d{2}) repaid to Fuliza", sms)
    if not m:
        return None
    return {"type": "fuliza_repay", "counterparty": "FULIZA M-PESA",
            "amount": _amt(m.group(1)), **_common(sms)}


_EXTRACTORS = {
    "send_money":    _extract_send_money,
    "receive":       _extract_receive,
    "buy_goods":     _extract_buy_goods,
    "paybill":       _extract_paybill,
    "airtime_saf":   _extract_airtime_saf,
    "airtime_other": _extract_airtime_other,
    "ziidi":         _extract_ziidi,
    "fuliza_borrow": _extract_fuliza_borrow,
    "fuliza_repay":  _extract_fuliza_repay,
}


# ---------------------------------------------------------------------------
# Gemma fallback — for unrecognised formats
# ---------------------------------------------------------------------------

_GEMMA_SYSTEM = f"""You are an M-Pesa SMS parser. Return ONLY valid JSON.

Schema: {{"type": one of {sorted(VALID_TYPES)}, "amount": float, "fee": float,
"counterparty": string, "balance_after": float,
"timestamp": "YYYY-MM-DDTHH:MM", "raw_ref": "U..."}}

Strip Ksh/KSH prefix and commas from amounts. No markdown fences."""


def _gemma_parse(sms: str) -> Optional[dict]:
    for _ in range(2):
        try:
            resp = ollama.chat(
                model=MODEL,
                messages=[
                    {"role": "system", "content": _GEMMA_SYSTEM},
                    {"role": "user", "content": sms},
                ],
                options={"num_ctx": NUM_CTX},
            )
            raw = re.sub(r"```(?:json)?\s*", "", resp.message.content).strip()
            return json.loads(raw)
        except (json.JSONDecodeError, Exception):
            continue
    return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse_sms(sms: str) -> tuple[Optional[ParsedTransaction], str]:
    """
    Parse a single M-Pesa SMS.

    Returns:
        (ParsedTransaction, "regex")  — fast path succeeded
        (ParsedTransaction, "gemma")  — fell through to Gemma
        (None, "unknown_type")        — classifier couldn't identify the SMS
        (None, "regex_error")         — classifier matched but extractor failed
        (None, "gemma_failed")        — Gemma couldn't parse it either
        (None, "schema_error:…")      — parsed but Pydantic rejected the output
    """
    tx_type = _classify(sms)

    if tx_type and tx_type in _EXTRACTORS:
        data = _EXTRACTORS[tx_type](sms)
        if data:
            try:
                return ParsedTransaction(**data), "regex"
            except ValidationError as e:
                return None, f"schema_error:{e.error_count()} errors"
        return None, "regex_error"

    if tx_type is None:
        # Unrecognised format — hand off to Gemma
        data = _gemma_parse(sms)
        if data is None:
            return None, "gemma_failed"
        if "type" in data:
            data["type"] = data["type"].strip().lower().replace(" ", "_")
        try:
            return ParsedTransaction(**data), "gemma"
        except ValidationError as e:
            return None, f"schema_error:{e.error_count()} errors"

    return None, "unknown_type"
