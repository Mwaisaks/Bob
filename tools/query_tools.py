"""
query_tools.py — the 6 financial analysis functions Bob calls as tools.

Each function:
  - Accepts simple typed arguments (persona name + optional filters)
  - Queries the ledger via raw SQL
  - Returns a plain dict (JSON-serialisable, ready to send back to Gemma)

QUERY_TOOLS at the bottom is the list of Ollama-format tool schemas. Pass it
directly to ollama.chat(tools=QUERY_TOOLS) in the agent loop.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from agent.ledger import Ledger

_ledger = Ledger()   # module-level singleton — one connection for the agent


# ---------------------------------------------------------------------------
# Tool 1: spending summary by transaction type
# ---------------------------------------------------------------------------

def get_spending_summary(persona: str, days: int = 30) -> dict:
    """
    Total KES spent per transaction type for the last N days.
    'Spent' means money leaving the account (excludes receives).
    Fees are included in the per-type total.
    """
    rows = _ledger.query(
        """SELECT type,
                  COUNT(*)        AS count,
                  SUM(amount)     AS total_amount,
                  SUM(fee)        AS total_fees,
                  SUM(amount+fee) AS total_out
           FROM transactions
           WHERE persona = ?
             AND type NOT IN ('receive', 'fuliza_repay')
             AND timestamp >= datetime('now', ? || ' days')
           GROUP BY type
           ORDER BY total_out DESC""",
        (persona, f"-{days}"),
    )
    return {
        "persona": persona,
        "period_days": days,
        "breakdown": rows,
        "grand_total_out": round(sum(r["total_out"] for r in rows), 2),
    }


# ---------------------------------------------------------------------------
# Tool 2: running balance over time
# ---------------------------------------------------------------------------

def get_balance_trend(persona: str, days: int = 30) -> dict:
    """
    The running balance at each transaction for the last N days.
    Useful for spotting boom-bust cycles, Fuliza dependency periods, etc.
    """
    rows = _ledger.query(
        """SELECT timestamp, type, amount, balance_after
           FROM transactions
           WHERE persona = ?
             AND timestamp >= datetime('now', ? || ' days')
           ORDER BY timestamp ASC""",
        (persona, f"-{days}"),
    )
    balances = [{"timestamp": r["timestamp"], "balance": r["balance_after"]} for r in rows]
    low = min((r["balance_after"] for r in rows), default=0)
    high = max((r["balance_after"] for r in rows), default=0)
    return {
        "persona": persona,
        "period_days": days,
        "data_points": len(balances),
        "lowest_balance": round(low, 2),
        "highest_balance": round(high, 2),
        "trend": balances,
    }


# ---------------------------------------------------------------------------
# Tool 3: top counterparties (merchants / recipients / senders)
# ---------------------------------------------------------------------------

def get_top_counterparties(persona: str, tx_type: str = "buy_goods", limit: int = 5) -> dict:
    """
    Top counterparties by total KES transacted for a given transaction type.
    tx_type can be any valid type: buy_goods, send_money, receive, paybill, etc.
    """
    rows = _ledger.query(
        """SELECT counterparty,
                  COUNT(*)    AS count,
                  SUM(amount) AS total_amount
           FROM transactions
           WHERE persona = ?
             AND type = ?
           GROUP BY counterparty
           ORDER BY total_amount DESC
           LIMIT ?""",
        (persona, tx_type, limit),
    )
    return {
        "persona": persona,
        "type": tx_type,
        "top": rows,
    }


# ---------------------------------------------------------------------------
# Tool 4: fee analysis
# ---------------------------------------------------------------------------

def get_fee_analysis(persona: str, days: int = 30) -> dict:
    """
    Total fees paid per transaction type for the last N days.
    Highlights the hidden cost of frequent small transactions (Wanjiku's story).
    """
    rows = _ledger.query(
        """SELECT type,
                  COUNT(*)  AS count,
                  SUM(fee)  AS total_fees,
                  AVG(fee)  AS avg_fee
           FROM transactions
           WHERE persona = ?
             AND fee > 0
             AND timestamp >= datetime('now', ? || ' days')
           GROUP BY type
           ORDER BY total_fees DESC""",
        (persona, f"-{days}"),
    )
    grand_total = round(sum(r["total_fees"] for r in rows), 2)
    return {
        "persona": persona,
        "period_days": days,
        "total_fees_paid": grand_total,
        "by_type": rows,
    }


# ---------------------------------------------------------------------------
# Tool 5: Fuliza usage summary
# ---------------------------------------------------------------------------

def get_fuliza_summary(persona: str) -> dict:
    """
    Fuliza borrow/repay overview across the full history.
    Shows how dependent the user is on Fuliza and the effective cost.
    """
    borrows = _ledger.query(
        """SELECT COUNT(*) AS count, SUM(amount) AS total, SUM(fee) AS total_fees
           FROM transactions WHERE persona = ? AND type = 'fuliza_borrow'""",
        (persona,),
    )[0]

    repays = _ledger.query(
        """SELECT COUNT(*) AS count, SUM(amount) AS total
           FROM transactions WHERE persona = ? AND type = 'fuliza_repay'""",
        (persona,),
    )[0]

    first_borrow = _ledger.query(
        """SELECT timestamp FROM transactions
           WHERE persona = ? AND type = 'fuliza_borrow'
           ORDER BY timestamp ASC LIMIT 1""",
        (persona,),
    )

    return {
        "persona": persona,
        "borrow_count": borrows["count"] or 0,
        "total_borrowed": round(borrows["total"] or 0, 2),
        "total_daily_charges": round(borrows["total_fees"] or 0, 2),
        "repay_count": repays["count"] or 0,
        "total_repaid": round(repays["total"] or 0, 2),
        "first_fuliza_date": first_borrow[0]["timestamp"] if first_borrow else None,
    }


# ---------------------------------------------------------------------------
# Tool 6: income vs spending
# ---------------------------------------------------------------------------

def get_income_vs_spending(persona: str, days: int = 30) -> dict:
    """
    Total money received vs total money spent (including fees) for the last N days.
    The gap tells you whether someone is net positive or negative.
    """
    income = _ledger.query(
        """SELECT SUM(amount) AS total
           FROM transactions
           WHERE persona = ? AND type = 'receive'
             AND timestamp >= datetime('now', ? || ' days')""",
        (persona, f"-{days}"),
    )[0]

    spending = _ledger.query(
        """SELECT SUM(amount + fee) AS total
           FROM transactions
           WHERE persona = ? AND type NOT IN ('receive', 'fuliza_borrow', 'fuliza_repay')
             AND timestamp >= datetime('now', ? || ' days')""",
        (persona, f"-{days}"),
    )[0]

    inc = round(income["total"] or 0, 2)
    spent = round(spending["total"] or 0, 2)
    return {
        "persona": persona,
        "period_days": days,
        "total_income": inc,
        "total_spending": spent,
        "net": round(inc - spent, 2),
        "verdict": "net positive" if inc >= spent else "net negative",
    }


# ---------------------------------------------------------------------------
# Tool dispatch registry — maps function names to callables
# ---------------------------------------------------------------------------

TOOL_REGISTRY = {
    "get_spending_summary":    get_spending_summary,
    "get_balance_trend":       get_balance_trend,
    "get_top_counterparties":  get_top_counterparties,
    "get_fee_analysis":        get_fee_analysis,
    "get_fuliza_summary":      get_fuliza_summary,
    "get_income_vs_spending":  get_income_vs_spending,
}


# ---------------------------------------------------------------------------
# Ollama tool schemas — passed to ollama.chat(tools=QUERY_TOOLS)
# ---------------------------------------------------------------------------

QUERY_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_spending_summary",
            "description": "Total KES spent per category (send, buy_goods, paybill, airtime, etc.) for the last N days. Use this when the user asks about their overall spending or spending breakdown.",
            "parameters": {
                "type": "object",
                "properties": {
                    "persona": {"type": "string", "description": "The persona name: brian, wanjiku, or athman"},
                    "days":    {"type": "integer", "description": "Number of past days to analyse (default 30)"},
                },
                "required": ["persona"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_balance_trend",
            "description": "Running M-Pesa balance over time. Use when the user asks how their balance has changed, or if they want to see spending patterns over time.",
            "parameters": {
                "type": "object",
                "properties": {
                    "persona": {"type": "string", "description": "The persona name"},
                    "days":    {"type": "integer", "description": "Number of past days to include"},
                },
                "required": ["persona"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_top_counterparties",
            "description": "Top merchants, recipients, or senders by KES amount for a given transaction type. Use when the user asks who they send money to most, or which shops they spend most at.",
            "parameters": {
                "type": "object",
                "properties": {
                    "persona": {"type": "string", "description": "The persona name"},
                    "tx_type": {"type": "string", "description": "Transaction type: buy_goods, send_money, receive, paybill, airtime_saf, airtime_other"},
                    "limit":   {"type": "integer", "description": "How many results to return (default 5)"},
                },
                "required": ["persona", "tx_type"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_fee_analysis",
            "description": "Total M-Pesa transaction fees paid, broken down by type. Use when the user asks how much they are losing to fees.",
            "parameters": {
                "type": "object",
                "properties": {
                    "persona": {"type": "string", "description": "The persona name"},
                    "days":    {"type": "integer", "description": "Number of past days to analyse"},
                },
                "required": ["persona"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_fuliza_summary",
            "description": "Fuliza borrow and repayment history with total charges. Use when the user asks about their Fuliza usage or debt.",
            "parameters": {
                "type": "object",
                "properties": {
                    "persona": {"type": "string", "description": "The persona name"},
                },
                "required": ["persona"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_income_vs_spending",
            "description": "Compares total money received against total money spent to show if the user is net positive or negative. Use for questions about saving, budgeting, or financial health.",
            "parameters": {
                "type": "object",
                "properties": {
                    "persona": {"type": "string", "description": "The persona name"},
                    "days":    {"type": "integer", "description": "Number of past days to analyse"},
                },
                "required": ["persona"],
            },
        },
    },
]
