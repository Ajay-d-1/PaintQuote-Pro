"""
database.py
───────────
SQLite persistence for PaintQuote Pro.
All tables are created on first run. The secure_token column is
added to approval_queue via ALTER TABLE if it doesn't exist yet
(safe migration for existing databases).
"""

import sqlite3
import json
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

DB_PATH = "paintquote.db"


def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS quotes (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            client_name   TEXT    NOT NULL,
            client_phone  TEXT,
            project_address TEXT,
            paint_grade   TEXT,
            total_area    REAL,
            paint_cost    REAL,
            labor_cost    REAL,
            extras_cost   REAL,
            gst_cost      REAL    DEFAULT 0,
            total_cost    REAL,
            breakdown     TEXT,
            rooms         TEXT,
            extras        TEXT,
            status        TEXT    DEFAULT 'pending',
            created_at    TEXT,
            pdf_path      TEXT
        );

        CREATE TABLE IF NOT EXISTS chat_messages (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            quote_id        INTEGER,
            role            TEXT,
            message         TEXT,
            suggested_price REAL,
            action          TEXT,
            approval_status TEXT    DEFAULT 'sent',
            timestamp       TEXT,
            FOREIGN KEY (quote_id) REFERENCES quotes(id)
        );

        CREATE TABLE IF NOT EXISTS approval_queue (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            quote_id          INTEGER,
            chat_message_id   INTEGER,
            client_message    TEXT,
            ai_suggested_reply TEXT,
            suggested_price   REAL,
            trade_off         TEXT,
            status            TEXT    DEFAULT 'pending',
            dad_response      TEXT,
            secure_token      TEXT    UNIQUE,
            created_at        TEXT,
            resolved_at       TEXT,
            FOREIGN KEY (quote_id)        REFERENCES quotes(id),
            FOREIGN KEY (chat_message_id) REFERENCES chat_messages(id)
        );
    """)
    conn.commit()

    # Safe migration: add secure_token if column didn't exist before
    try:
        conn.execute("ALTER TABLE approval_queue ADD COLUMN secure_token TEXT UNIQUE")
        conn.commit()
    except sqlite3.OperationalError:
        pass

    # Safe migration: add trade_off to approval_queue
    try:
        conn.execute("ALTER TABLE approval_queue ADD COLUMN trade_off TEXT")
        conn.commit()
    except sqlite3.OperationalError:
        pass

    # Safe migration: add action to chat_messages
    try:
        conn.execute("ALTER TABLE chat_messages ADD COLUMN action TEXT")
        conn.commit()
    except sqlite3.OperationalError:
        pass

    # Safe migration: add approval_status to chat_messages
    try:
        conn.execute("ALTER TABLE chat_messages ADD COLUMN approval_status TEXT DEFAULT 'sent'")
        conn.commit()
    except sqlite3.OperationalError:
        pass

    # Safe migration: add gst_cost if column didn't exist before
    try:
        conn.execute("ALTER TABLE quotes ADD COLUMN gst_cost REAL DEFAULT 0")
        conn.commit()
        logger.info("Migration: checked and applied necessary schema updates")
    except sqlite3.OperationalError:
        pass

    conn.close()


# ── Quotes ───────────────────────────────────────────────────────────────────

def create_quote(data: dict) -> int:
    conn = get_db()
    cursor = conn.execute("""
        INSERT INTO quotes (
            client_name, paint_grade, total_area, paint_cost,
            labor_cost, extras_cost, gst_cost, total_cost,
            breakdown, rooms, extras, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        data["client_name"], data["paint_grade"], data["total_area"],
        data["paint_cost"], data["labor_cost"], data["extras_cost"],
        data.get("gst_cost", 0), data["total_cost"],
        json.dumps(data["breakdown"]),
        json.dumps(data["rooms"]), json.dumps(data["extras"]),
        data["created_at"]
    ))
    quote_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return quote_id


def get_quote(quote_id: int) -> dict | None:
    conn = get_db()
    row = conn.execute("SELECT * FROM quotes WHERE id = ?", (quote_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_all_quotes() -> list[dict]:
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM quotes ORDER BY created_at DESC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── Chat Messages ─────────────────────────────────────────────────────────────

def add_chat_message(
    quote_id: int,
    role: str,
    message: str,
    suggested_price: float | None = None,
    action: str | None = None,
    approval_status: str = "sent"
) -> int:
    conn = get_db()
    cursor = conn.execute("""
        INSERT INTO chat_messages
            (quote_id, role, message, suggested_price, action, approval_status, timestamp)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        quote_id, role, message, suggested_price, action,
        approval_status, datetime.now().isoformat()
    ))
    msg_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return msg_id


def get_chat_history(quote_id: int) -> list[dict]:
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM chat_messages WHERE quote_id = ? ORDER BY timestamp",
        (quote_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update_chat_message_status(
    msg_id: int,
    approval_status: str,
    message: str | None = None
) -> None:
    conn = get_db()
    if message:
        conn.execute(
            "UPDATE chat_messages SET approval_status = ?, message = ? WHERE id = ?",
            (approval_status, message, msg_id)
        )
    else:
        conn.execute(
            "UPDATE chat_messages SET approval_status = ? WHERE id = ?",
            (approval_status, msg_id)
        )
    conn.commit()
    conn.close()


# ── Approval Queue ────────────────────────────────────────────────────────────

def add_to_approval_queue(
    quote_id: int,
    chat_message_id: int,
    client_message: str,
    ai_suggested_reply: str,
    suggested_price: float | None,
    trade_off: str,
    secure_token: str
) -> int:
    conn = get_db()
    cursor = conn.execute("""
        INSERT INTO approval_queue (
            quote_id, chat_message_id, client_message,
            ai_suggested_reply, suggested_price, trade_off,
            status, secure_token, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, 'pending', ?, ?)
    """, (
        quote_id, chat_message_id, client_message,
        ai_suggested_reply, suggested_price, trade_off,
        secure_token, datetime.now().isoformat()
    ))
    aq_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return aq_id


def get_pending_approvals() -> list[dict]:
    conn = get_db()
    rows = conn.execute("""
        SELECT aq.*, q.client_name, q.total_cost
        FROM approval_queue aq
        JOIN quotes q ON aq.quote_id = q.id
        WHERE aq.status = 'pending'
        ORDER BY aq.created_at DESC
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_all_approvals() -> list[dict]:
    conn = get_db()
    rows = conn.execute("""
        SELECT aq.*, q.client_name, q.total_cost
        FROM approval_queue aq
        JOIN quotes q ON aq.quote_id = q.id
        ORDER BY aq.created_at DESC
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def resolve_approval(aq_id: int, action: str, dad_response: str | None = None) -> None:
    conn = get_db()
    conn.execute("""
        UPDATE approval_queue
        SET status = ?, dad_response = ?, resolved_at = ?
        WHERE id = ?
    """, (action, dad_response, datetime.now().isoformat(), aq_id))
    conn.commit()
    conn.close()


def get_approval_by_id(aq_id: int) -> dict | None:
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM approval_queue WHERE id = ?", (aq_id,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def get_approval_by_token(token: str) -> dict | None:
    """Look up an approval queue item by its secure email token."""
    if not token:
        return None
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM approval_queue WHERE secure_token = ?", (token,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None
