from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from .runtime import current_user_id, runtime_config

DATA_DIR = runtime_config().data_root
DB_PATH = DATA_DIR / "focuslyra.db"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _has_column(conn: sqlite3.Connection, table: str, column: str) -> bool:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return any(str(row[1]) == column for row in rows)


def _ensure_user_column(conn: sqlite3.Connection, table: str) -> None:
    # Existing personal MVP databases are migrated in place. Old records belong
    # to the original local owner; future auth middleware can provide user ids.
    if not _has_column(conn, table, "user_id"):
        conn.execute(
            f"ALTER TABLE {table} ADD COLUMN user_id TEXT NOT NULL DEFAULT 'local-owner'"
        )


def initialise_database() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL DEFAULT 'local-owner',
                language_code TEXT,
                mode TEXT NOT NULL,
                started_at TEXT,
                completed_at TEXT NOT NULL,
                payload_json TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS writings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL DEFAULT 'local-owner',
                session_id INTEGER,
                language_code TEXT,
                original_text TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(session_id) REFERENCES sessions(id)
            );

            CREATE TABLE IF NOT EXISTS evidence_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL DEFAULT 'local-owner',
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

            CREATE TABLE IF NOT EXISTS ai_feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL DEFAULT 'local-owner',
                session_id INTEGER,
                language_code TEXT NOT NULL,
                modality TEXT NOT NULL,
                provider TEXT,
                model TEXT,
                feedback_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(session_id) REFERENCES sessions(id)
            );
            """
        )

        # Safe in-place migration for databases created before user scoping.
        for table in ("sessions", "writings", "evidence_events", "ai_feedback"):
            _ensure_user_column(conn, table)

        conn.executescript(
            """
            CREATE INDEX IF NOT EXISTS idx_sessions_user_language
                ON sessions(user_id, language_code, id);
            CREATE INDEX IF NOT EXISTS idx_evidence_user_language
                ON evidence_events(user_id, language_code, id);
            CREATE INDEX IF NOT EXISTS idx_feedback_user_language
                ON ai_feedback(user_id, language_code, id);
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


def save_session(payload: dict[str, Any], user_id: str | None = None) -> int:
    uid = user_id or current_user_id()
    completed_at = utc_now()
    with connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO sessions(user_id, language_code, mode, started_at, completed_at, payload_json)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                uid,
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
                INSERT INTO writings(user_id, session_id, language_code, original_text, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (uid, session_id, payload.get("language_code"), payload["writing"], completed_at),
            )
        conn.commit()
    return session_id


def save_learning_feedback(
    session_id: int,
    language_code: str,
    modality: str,
    analysis: dict[str, Any],
    user_id: str | None = None,
) -> None:
    """Persist AI feedback plus compact evidence events used by later sessions."""
    uid = user_id or current_user_id()
    created_at = utc_now()
    provider = str(analysis.get("provider") or "")
    model = str(analysis.get("model") or "")
    with connection() as conn:
        conn.execute(
            """
            INSERT INTO ai_feedback(user_id, session_id, language_code, modality, provider, model, feedback_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                uid,
                session_id,
                language_code,
                modality,
                provider,
                model,
                json.dumps(analysis, ensure_ascii=False),
                created_at,
            ),
        )

        scores = analysis.get("scores") or {}
        if isinstance(scores, dict):
            for skill, value in scores.items():
                try:
                    score = float(value)
                except (TypeError, ValueError):
                    continue
                conn.execute(
                    """
                    INSERT INTO evidence_events(user_id, session_id, language_code, item_id, modality, event_type, score, payload_json, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        uid,
                        session_id,
                        language_code,
                        str(skill),
                        modality,
                        "skill_score",
                        score,
                        json.dumps({"skill": skill}, ensure_ascii=False),
                        created_at,
                    ),
                )

        for pattern in (analysis.get("patterns_to_revisit") or [])[:10]:
            if isinstance(pattern, dict):
                item = str(pattern.get("item") or pattern.get("pattern") or "").strip()
                payload = pattern
            else:
                item = str(pattern).strip()
                payload = {"pattern": item}
            if not item:
                continue
            conn.execute(
                """
                INSERT INTO evidence_events(user_id, session_id, language_code, item_id, modality, event_type, score, payload_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    uid,
                    session_id,
                    language_code,
                    item,
                    modality,
                    "review_target",
                    None,
                    json.dumps(payload, ensure_ascii=False),
                    created_at,
                ),
            )
        conn.commit()


def recent_learning_evidence(
    language_code: str,
    limit: int = 20,
    user_id: str | None = None,
) -> list[dict[str, Any]]:
    uid = user_id or current_user_id()
    with connection() as conn:
        rows = conn.execute(
            """
            SELECT item_id, modality, event_type, score, payload_json, created_at
            FROM evidence_events
            WHERE user_id = ? AND language_code = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (uid, language_code, max(1, min(limit, 100))),
        ).fetchall()
    result: list[dict[str, Any]] = []
    for row in rows:
        try:
            payload = json.loads(row["payload_json"])
        except (TypeError, json.JSONDecodeError):
            payload = {}
        result.append(
            {
                "item_id": row["item_id"],
                "modality": row["modality"],
                "event_type": row["event_type"],
                "score": row["score"],
                "payload": payload,
                "created_at": row["created_at"],
            }
        )
    return result
