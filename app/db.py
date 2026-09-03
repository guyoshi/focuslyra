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

            CREATE TABLE IF NOT EXISTS ai_feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
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


def save_learning_feedback(
    session_id: int,
    language_code: str,
    modality: str,
    analysis: dict[str, Any],
) -> None:
    """Persist AI feedback plus compact evidence events used by later sessions."""
    created_at = utc_now()
    provider = str(analysis.get("provider") or "")
    model = str(analysis.get("model") or "")
    with connection() as conn:
        conn.execute(
            """
            INSERT INTO ai_feedback(session_id, language_code, modality, provider, model, feedback_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
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
                    INSERT INTO evidence_events(session_id, language_code, item_id, modality, event_type, score, payload_json, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
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
                INSERT INTO evidence_events(session_id, language_code, item_id, modality, event_type, score, payload_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
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


def recent_learning_evidence(language_code: str, limit: int = 20) -> list[dict[str, Any]]:
    with connection() as conn:
        rows = conn.execute(
            """
            SELECT item_id, modality, event_type, score, payload_json, created_at
            FROM evidence_events
            WHERE language_code = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (language_code, max(1, min(limit, 100))),
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
