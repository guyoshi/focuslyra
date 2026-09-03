from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any

from .db import connection
from .language_service import load_languages
from .runtime import current_user_id


class ReviewServiceError(RuntimeError):
    pass


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


def _ensure_schema() -> None:
    with connection() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS review_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                language_code TEXT NOT NULL,
                item_key TEXT NOT NULL,
                modality TEXT NOT NULL,
                prompt TEXT NOT NULL,
                answer TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                ease REAL NOT NULL DEFAULT 2.3,
                interval_days REAL NOT NULL DEFAULT 0,
                repetitions INTEGER NOT NULL DEFAULT 0,
                due_at TEXT NOT NULL,
                last_rating TEXT,
                last_reviewed_at TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(user_id, language_code, item_key, modality)
            );
            CREATE INDEX IF NOT EXISTS idx_review_due
                ON review_items(user_id, due_at, language_code);
            """
        )
        conn.commit()


def materialise_review_targets(user_id: str | None = None) -> int:
    _ensure_schema()
    uid = user_id or current_user_id()
    now = _iso(_now())
    inserted = 0
    with connection() as conn:
        rows = conn.execute(
            """
            SELECT language_code, item_id, modality, payload_json, created_at
            FROM evidence_events
            WHERE user_id = ? AND event_type = 'review_target' AND item_id IS NOT NULL
            ORDER BY id DESC LIMIT 500
            """,
            (uid,),
        ).fetchall()
        for row in rows:
            item = str(row['item_id'] or '').strip()
            if not item:
                continue
            try:
                payload = json.loads(row['payload_json'] or '{}')
            except json.JSONDecodeError:
                payload = {}
            reason = str(payload.get('reason') or '').strip()
            prompt = reason or 'Recall and use this naturally without looking at the answer first.'
            cursor = conn.execute(
                """
                INSERT OR IGNORE INTO review_items(
                    user_id, language_code, item_key, modality, prompt, answer,
                    payload_json, due_at, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    uid,
                    row['language_code'],
                    item,
                    row['modality'] or 'production',
                    prompt,
                    item,
                    json.dumps(payload, ensure_ascii=False),
                    now,
                    row['created_at'] or now,
                    now,
                ),
            )
            inserted += int(cursor.rowcount or 0)
        conn.commit()
    return inserted


def _row_to_item(row) -> dict[str, Any]:
    try:
        payload = json.loads(row['payload_json'] or '{}')
    except json.JSONDecodeError:
        payload = {}
    return {
        'id': int(row['id']),
        'language_code': row['language_code'],
        'item_key': row['item_key'],
        'modality': row['modality'],
        'prompt': row['prompt'],
        'answer': row['answer'],
        'payload': payload,
        'ease': round(float(row['ease']), 2),
        'interval_days': round(float(row['interval_days']), 2),
        'repetitions': int(row['repetitions']),
        'due_at': row['due_at'],
        'last_rating': row['last_rating'],
    }


def due_reviews(limit: int = 20, language_code: str | None = None, user_id: str | None = None) -> dict[str, Any]:
    materialise_review_targets(user_id)
    uid = user_id or current_user_id()
    now = _iso(_now())
    params: list[Any] = [uid, now]
    language_filter = ''
    if language_code:
        language_filter = ' AND language_code = ?'
        params.append(language_code)
    params.append(max(1, min(int(limit), 100)))
    with connection() as conn:
        rows = conn.execute(
            f"""
            SELECT * FROM review_items
            WHERE user_id = ? AND due_at <= ? {language_filter}
            ORDER BY due_at ASC, repetitions ASC, id ASC
            LIMIT ?
            """,
            params,
        ).fetchall()
        total = conn.execute(
            f"SELECT COUNT(*) AS n FROM review_items WHERE user_id = ? AND due_at <= ? {language_filter}",
            params[:-1],
        ).fetchone()['n']
    languages = {item['code']: item for item in load_languages(uid)}
    items = []
    for row in rows:
        item = _row_to_item(row)
        language = languages.get(item['language_code'], {})
        item['language_name'] = language.get('name', item['language_code'])
        item['flag'] = language.get('flag', '')
        items.append(item)
    return {'due_count': int(total), 'items': items}


def grade_review(item_id: int, rating: str, user_id: str | None = None) -> dict[str, Any]:
    _ensure_schema()
    uid = user_id or current_user_id()
    rating = str(rating).strip().lower()
    if rating not in {'again', 'hard', 'good', 'easy'}:
        raise ReviewServiceError('Rating must be again, hard, good or easy.')

    with connection() as conn:
        row = conn.execute('SELECT * FROM review_items WHERE id = ? AND user_id = ?', (item_id, uid)).fetchone()
        if row is None:
            raise ReviewServiceError('Review item not found.')

        ease = float(row['ease'])
        interval = float(row['interval_days'])
        reps = int(row['repetitions'])
        now = _now()

        if rating == 'again':
            reps = 0
            ease = max(1.3, ease - 0.20)
            interval = 0.02
        elif rating == 'hard':
            reps += 1
            ease = max(1.3, ease - 0.10)
            interval = max(0.5, 1.0 if interval <= 0 else interval * 1.25)
        elif rating == 'good':
            reps += 1
            interval = 1.0 if reps <= 1 else (3.0 if reps == 2 else max(2.0, interval * ease))
        else:
            reps += 1
            ease = min(3.2, ease + 0.12)
            interval = 3.0 if reps <= 1 else max(4.0, interval * ease * 1.35)

        due = now + timedelta(days=interval)
        conn.execute(
            """
            UPDATE review_items
            SET ease = ?, interval_days = ?, repetitions = ?, due_at = ?,
                last_rating = ?, last_reviewed_at = ?, updated_at = ?
            WHERE id = ? AND user_id = ?
            """,
            (ease, interval, reps, _iso(due), rating, _iso(now), _iso(now), item_id, uid),
        )
        score = {'again': 20, 'hard': 50, 'good': 80, 'easy': 95}[rating]
        conn.execute(
            """
            INSERT INTO evidence_events(user_id, session_id, language_code, item_id, modality, event_type, score, payload_json, created_at)
            VALUES (?, NULL, ?, ?, ?, 'review_result', ?, ?, ?)
            """,
            (
                uid,
                row['language_code'],
                row['item_key'],
                row['modality'],
                score,
                json.dumps({'rating': rating, 'next_interval_days': interval}, ensure_ascii=False),
                _iso(now),
            ),
        )
        conn.commit()
        updated = conn.execute('SELECT * FROM review_items WHERE id = ?', (item_id,)).fetchone()
    return _row_to_item(updated)
