from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
DB_PATH = DATA_DIR / "focuslyra.db"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def initialise_database() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                language_code TEXT,
                mode TEXT NOT NULL,
                started_at TEXT,
                completed_at TEXT NOT NULL,
                payload_json TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS writings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER,
                language_code TEXT,
                original_text TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(session_id) REFERENCES sessions(id)
            );

            CREATE TABLE IF NOT EXISTS evidence_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER,
                language_code TEXT NOT NULL,
                item_id TEXT,
                modality TEXT NOT NULL,
                event_type TEXT NOT NULL,
                score REAL,
                payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(session_id) REFERENCES sessions(id)
            );
            """
        )
        conn.commit()


@contextmanager
def connection() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def save_session(payload: dict[str, Any]) -> int:
    completed_at = utc_now()
    with connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO sessions(language_code, mode, started_at, completed_at, payload_json)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                payload.get("language_code"),
                payload.get("mode", "unknown"),
                payload.get("started_at"),
                completed_at,
                json.dumps(payload, ensure_ascii=False),
            ),
        )
        session_id = int(cursor.lastrowid)
        if payload.get("writing"):
            conn.execute(
                """
                INSERT INTO writings(session_id, language_code, original_text, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (session_id, payload.get("language_code"), payload["writing"], completed_at),
            )
        conn.commit()
    return session_id
