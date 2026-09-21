"""
SQLite yordamchi funksiyalari: obunachilar, kurs tarixi va oxirgi
bildirilgan kurslar shu yerda saqlanadi.
"""

import os
import sqlite3
from datetime import datetime, timezone

DB_PATH = os.environ.get("DB_PATH", "valyutax.db")


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with get_conn() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS subscribers (
                chat_id INTEGER PRIMARY KEY,
                user_id INTEGER,
                username TEXT,
                subscribed_at TEXT
            );

            CREATE TABLE IF NOT EXISTS rate_history (
                date TEXT,
                currency_code TEXT,
                rate REAL,
                PRIMARY KEY (date, currency_code)
            );

            CREATE TABLE IF NOT EXISTS last_notified_rate (
                currency_code TEXT PRIMARY KEY,
                rate REAL,
                updated_at TEXT
            );

            CREATE TABLE IF NOT EXISTS usage_stats (
                currency_code TEXT PRIMARY KEY,
                request_count INTEGER NOT NULL DEFAULT 0
            );
            """
        )


def add_subscriber(chat_id: int, user_id: int, username: str | None) -> None:
    with get_conn() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO subscribers (chat_id, user_id, username, subscribed_at) "
            "VALUES (?, ?, ?, ?)",
            (chat_id, user_id, username, datetime.now(timezone.utc).isoformat()),
        )


def remove_subscriber(chat_id: int) -> None:
    with get_conn() as conn:
        conn.execute("DELETE FROM subscribers WHERE chat_id = ?", (chat_id,))


def is_subscribed(chat_id: int) -> bool:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT 1 FROM subscribers WHERE chat_id = ?", (chat_id,)
        ).fetchone()
        return row is not None


def list_subscribers() -> list[int]:
    with get_conn() as conn:
        rows = conn.execute("SELECT chat_id FROM subscribers").fetchall()
        return [row["chat_id"] for row in rows]


def save_rate_snapshot(date: str, currency_code: str, rate: float) -> None:
    with get_conn() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO rate_history (date, currency_code, rate) VALUES (?, ?, ?)",
            (date, currency_code, rate),
        )


def get_rate_history(currency_code: str, days: int) -> list[tuple[str, float]]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT date, rate FROM rate_history WHERE currency_code = ? "
            "ORDER BY date DESC LIMIT ?",
            (currency_code, days),
        ).fetchall()
        return [(row["date"], row["rate"]) for row in reversed(rows)]


def get_last_notified(currency_code: str) -> float | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT rate FROM last_notified_rate WHERE currency_code = ?",
            (currency_code,),
        ).fetchone()
        return row["rate"] if row else None


def set_last_notified(currency_code: str, rate: float) -> None:
    with get_conn() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO last_notified_rate (currency_code, rate, updated_at) "
            "VALUES (?, ?, ?)",
            (currency_code, rate, datetime.now(timezone.utc).isoformat()),
        )


def log_usage(currency_code: str) -> None:
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO usage_stats (currency_code, request_count) VALUES (?, 1) "
            "ON CONFLICT(currency_code) DO UPDATE SET request_count = request_count + 1",
            (currency_code,),
        )


def get_top_currencies(limit: int = 5) -> list[tuple[str, int]]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT currency_code, request_count FROM usage_stats "
            "ORDER BY request_count DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [(row["currency_code"], row["request_count"]) for row in rows]


def get_subscriber_count() -> int:
    with get_conn() as conn:
        row = conn.execute("SELECT COUNT(*) AS n FROM subscribers").fetchone()
        return row["n"] if row else 0
