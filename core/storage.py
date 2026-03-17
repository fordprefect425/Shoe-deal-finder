"""
core/storage.py
SQLite-backed storage for offer snapshots and alert logs.
"""

import sqlite3
import os
import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "prices.db")


def get_connection() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Create all tables if they don't exist."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.executescript("""
            CREATE TABLE IF NOT EXISTS offer_snapshots (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                shoe_id     TEXT NOT NULL,
                site_name   TEXT NOT NULL,
                product_url TEXT NOT NULL,
                title       TEXT,
                price       REAL,
                currency    TEXT DEFAULT 'INR',
                in_stock    INTEGER DEFAULT 0,
                size_available INTEGER DEFAULT -1,
                checked_at  TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS alert_log (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                shoe_id      TEXT NOT NULL,
                alert_type   TEXT NOT NULL,
                message_hash TEXT,
                sent_at      TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_snapshots_shoe_url
                ON offer_snapshots (shoe_id, product_url, checked_at);

            CREATE INDEX IF NOT EXISTS idx_alert_log_shoe
                ON alert_log (shoe_id, sent_at);
        """)
        conn.commit()
        logger.info("Database initialised at %s", DB_PATH)
    finally:
        conn.close()


def save_snapshot(snapshot: dict) -> None:
    """Persist a single offer snapshot returned by a scraper."""
    conn = get_connection()
    try:
        conn.execute(
            """
            INSERT INTO offer_snapshots
                (shoe_id, site_name, product_url, title, price, currency,
                 in_stock, size_available, checked_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                snapshot["shoe_id"],
                snapshot["site_name"],
                snapshot["product_url"],
                snapshot.get("title"),
                snapshot.get("price"),
                snapshot.get("currency", "INR"),
                1 if snapshot.get("in_stock") else 0,
                1 if snapshot.get("size_available") is True else
                (0 if snapshot.get("size_available") is False else -1),
                snapshot.get("checked_at", datetime.utcnow().isoformat()),
            ),
        )
        conn.commit()
    finally:
        conn.close()


def get_last_snapshot(shoe_id: str, product_url: str) -> Optional[dict]:
    """Return the most recent snapshot for a given shoe + URL, or None."""
    conn = get_connection()
    try:
        row = conn.execute(
            """
            SELECT * FROM offer_snapshots
            WHERE shoe_id = ? AND product_url = ?
            ORDER BY checked_at DESC
            LIMIT 1
            """,
            (shoe_id, product_url),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_last_snapshots_for_shoe(shoe_id: str) -> list[dict]:
    """Return the latest snapshot for every URL tracked for a shoe."""
    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT s.*
            FROM offer_snapshots s
            INNER JOIN (
                SELECT product_url, MAX(checked_at) AS max_checked
                FROM offer_snapshots
                WHERE shoe_id = ?
                GROUP BY product_url
            ) latest
            ON s.product_url = latest.product_url
            AND s.checked_at = latest.max_checked
            WHERE s.shoe_id = ?
            """,
            (shoe_id, shoe_id),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def log_alert(shoe_id: str, alert_type: str, message_hash: str) -> None:
    """Record that an alert was sent."""
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO alert_log (shoe_id, alert_type, message_hash, sent_at) VALUES (?, ?, ?, ?)",
            (shoe_id, alert_type, message_hash, datetime.utcnow().isoformat()),
        )
        conn.commit()
    finally:
        conn.close()


def was_alert_sent_today(shoe_id: str, alert_type: str, message_hash: str) -> bool:
    """True if an identical alert was already sent today for this shoe."""
    today = datetime.utcnow().date().isoformat()
    conn = get_connection()
    try:
        row = conn.execute(
            """
            SELECT 1 FROM alert_log
            WHERE shoe_id = ? AND alert_type = ? AND message_hash = ?
            AND DATE(sent_at) = ?
            LIMIT 1
            """,
            (shoe_id, alert_type, message_hash, today),
        ).fetchone()
        return row is not None
    finally:
        conn.close()
