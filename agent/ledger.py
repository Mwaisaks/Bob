"""
ledger.py — SQLite transaction store for Bob.

All parsed M-Pesa transactions live here. The schema mirrors ParsedTransaction
from tools/sms_parser.py so ingestion is a straight dict → row insert.
Query tools in tools/query_tools.py read from this database.
"""

import sqlite3
from pathlib import Path
from typing import Optional

DEFAULT_DB = Path(__file__).parent.parent / "data" / "bob.db"

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS transactions (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    persona       TEXT    NOT NULL,
    type          TEXT    NOT NULL,
    amount        REAL    NOT NULL,
    fee           REAL    NOT NULL DEFAULT 0.0,
    counterparty  TEXT    NOT NULL,
    balance_after REAL    NOT NULL,
    timestamp     TEXT    NOT NULL,
    raw_ref       TEXT,
    is_fuliza     INTEGER NOT NULL DEFAULT 0,
    fuliza_amount REAL    NOT NULL DEFAULT 0.0,
    raw_sms       TEXT
);
"""

_CREATE_INDEX = """
CREATE INDEX IF NOT EXISTS idx_persona_ts ON transactions (persona, timestamp);
"""


class Ledger:
    def __init__(self, db_path: Path = DEFAULT_DB):
        self.db_path = db_path
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        with self._conn:
            self._conn.execute(_CREATE_TABLE)
            self._conn.execute(_CREATE_INDEX)

    def insert(self, persona: str, tx: dict, raw_sms: str = "") -> int:
        """Insert one parsed transaction. Returns the new row id."""
        with self._conn:
            cur = self._conn.execute(
                """INSERT INTO transactions
                       (persona, type, amount, fee, counterparty, balance_after,
                        timestamp, raw_ref, is_fuliza, fuliza_amount, raw_sms)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    persona,
                    tx["type"],
                    tx["amount"],
                    tx["fee"],
                    tx["counterparty"],
                    tx["balance_after"],
                    tx["timestamp"],
                    tx.get("raw_ref", ""),
                    int(tx.get("is_fuliza", False)),
                    tx.get("fuliza_amount", 0.0),
                    raw_sms,
                ),
            )
            return cur.lastrowid

    def query(self, sql: str, params: tuple = ()) -> list[dict]:
        """Run an arbitrary SELECT and return rows as plain dicts."""
        cur = self._conn.execute(sql, params)
        return [dict(row) for row in cur.fetchall()]

    def count(self, persona: Optional[str] = None) -> int:
        if persona:
            return self._conn.execute(
                "SELECT COUNT(*) FROM transactions WHERE persona = ?", (persona,)
            ).fetchone()[0]
        return self._conn.execute("SELECT COUNT(*) FROM transactions").fetchone()[0]

    def clear(self, persona: Optional[str] = None):
        """Delete records — all personas or just one."""
        with self._conn:
            if persona:
                self._conn.execute(
                    "DELETE FROM transactions WHERE persona = ?", (persona,)
                )
            else:
                self._conn.execute("DELETE FROM transactions")

    def close(self):
        self._conn.close()
