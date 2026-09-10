from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from typing import Any

from .db import connection
from .runtime import current_user_id


TRACKED_CATEGORIES = {
    "typo",
    "spelling",
    "romaji",
    "kana",
    "kanji",
    "grammar",
    "vocabulary",
    "vocabulary_naturalness",
    "naturalness",
    "word_order",
    "register",
    "pronunciation",
    "pronunciation_control",
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


def _ensure_schema() -> None:
    with connection() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS learning_mistakes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                language_code TEXT NOT NULL,
                memory_key TEXT NOT NULL,
                category TEXT NOT NULL,
                modality TEXT NOT NULL,
                learning_target TEXT NOT NULL,
                original_text TEXT,
                corrected_text TEXT,
                meaning_pt TEXT,
                explanation_pt TEXT,
                example_text TEXT,
                severity TEXT NOT NULL DEFAULT 'medium',
                occurrences INTEGER NOT NULL DEFAULT 1,
                successful_retests INTEGER NOT NULL DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'active',
                first_seen_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL,
                next_due_at TEXT NOT NULL,
                last_retested_at TEXT,
                payload_json TEXT NOT NULL,
                UNIQUE(user_id, language_code, memory_key)
            );
            CREATE INDEX IF NOT EXISTS idx_learning_mistakes_due
                ON learning_mistakes(user_id, language_code, status, next_due_at);
            CREATE INDEX IF NOT EXISTS idx_learning_mistakes_recent
                ON learning_mistakes(user_id, language_code, last_seen_at);
            """
        )
        conn.commit()


def _slug(value: str) -> str:
    text = re.sub(r"\s+", " ", str(value or "").strip().lower())
    text = re.sub(r"[^\w\-\u3040-\u30ff\u3400-\u9fff ]+", "", text, flags=re.UNICODE)
    return text[:140].strip().replace(" ", "_")


def normalise_memory_key(item: dict[str, Any]) -> str:
    explicit = str(item.get("memory_key") or item.get("mistake_key") or "").strip()
    if explicit:
        return explicit[:180]
    category = str(item.get("category") or "pattern").strip().lower().replace(" ", "_")
    target = str(
        item.get("learning_target")
        or item.get("item")
        or item.get("natural")
        or item.get("corrected")
        or item.get("original")
        or ""
    ).strip()
    slug = _slug(target) or "general"
    return f"{category}:{slug}"[:180]


def _row_to_memory(row) -> dict[str, Any]:
    try:
        payload = json.loads(row["payload_json"] or "{}")
    except (TypeError, json.JSONDecodeError):
        payload = {}
    return {
        "id": int(row["id"]),
        "language_code": row["language_code"],
        "memory_key": row["memory_key"],
        "category": row["category"],
        "modality": row["modality"],
        "learning_target": row["learning_target"],
        "original": row["original_text"] or "",
        "corrected": row["corrected_text"] or "",
        "meaning_pt": row["meaning_pt"] or "",
        "explanation_pt": row["explanation_pt"] or "",
        "example": row["example_text"] or "",
        "severity": row["severity"],
        "occurrences": int(row["occurrences"]),
        "successful_retests": int(row["successful_retests"]),
        "status": row["status"],
        "first_seen_at": row["first_seen_at"],
        "last_seen_at": row["last_seen_at"],
        "next_due_at": row["next_due_at"],
        "last_retested_at": row["last_retested_at"],
        "payload": payload,
    }


def mistake_memory(
    language_code: str,
    limit: int = 12,
    *,
    include_resolved: bool = False,
    user_id: str | None = None,
) -> list[dict[str, Any]]:
    _ensure_schema()
    uid = user_id or current_user_id()
    status_clause = "" if include_resolved else "AND status != 'resolved'"
    with connection() as conn:
        rows = conn.execute(
            f"""
            SELECT * FROM learning_mistakes
            WHERE user_id = ? AND language_code = ? {status_clause}
            ORDER BY
                CASE WHEN next_due_at <= ? THEN 0 ELSE 1 END,
                occurrences DESC,
                last_seen_at DESC
            LIMIT ?
            """,
            (uid, language_code, _iso(_now()), max(1, min(int(limit), 100))),
        ).fetchall()
    return [_row_to_memory(row) for row in rows]


def due_mistake_targets(
    language_code: str,
    limit: int = 6,
    *,
    user_id: str | None = None,
) -> list[dict[str, Any]]:
    _ensure_schema()
    uid = user_id or current_user_id()
    now = _iso(_now())
    with connection() as conn:
        rows = conn.execute(
            """
            SELECT * FROM learning_mistakes
            WHERE user_id = ? AND language_code = ?
              AND status != 'resolved' AND next_due_at <= ?
            ORDER BY occurrences DESC, next_due_at ASC, last_seen_at DESC
            LIMIT ?
            """,
            (uid, language_code, now, max(1, min(int(limit), 50))),
        ).fetchall()
    return [_row_to_memory(row) for row in rows]


def mistake_stats(language_code: str, *, user_id: str | None = None) -> dict[str, int]:
    _ensure_schema()
    uid = user_id or current_user_id()
    now = _iso(_now())
    with connection() as conn:
        row = conn.execute(
            """
            SELECT
                SUM(CASE WHEN status != 'resolved' THEN 1 ELSE 0 END) AS active,
                SUM(CASE WHEN status != 'resolved' AND next_due_at <= ? THEN 1 ELSE 0 END) AS due,
                SUM(CASE WHEN status != 'resolved' AND occurrences >= 2 THEN 1 ELSE 0 END) AS recurring
            FROM learning_mistakes
            WHERE user_id = ? AND language_code = ?
            """,
            (now, uid, language_code),
        ).fetchone()
    return {
        "active": int((row["active"] if row else 0) or 0),
        "due": int((row["due"] if row else 0) or 0),
        "recurring": int((row["recurring"] if row else 0) or 0),
    }


def annotate_analysis_with_mistake_history(
    language_code: str,
    analysis: dict[str, Any],
    *,
    user_id: str | None = None,
) -> dict[str, Any]:
    """Attach recurrence facts using local state, never model guesswork."""
    memories = {item["memory_key"]: item for item in mistake_memory(language_code, limit=40, user_id=user_id)}
    corrections = analysis.get("corrections") if isinstance(analysis.get("corrections"), list) else []
    recurring: list[dict[str, Any]] = []
    for correction in corrections:
        if not isinstance(correction, dict):
            continue
        key = normalise_memory_key(correction)
        correction["memory_key"] = key
        previous = memories.get(key)
        if previous:
            before = int(previous.get("occurrences") or 0)
            correction["recurring"] = True
            correction["occurrences_before"] = before
            correction["occurrences"] = before + 1
            note = f"Este padrão já apareceu {before} vez{'es' if before != 1 else ''} antes. Vou voltar a testá-lo em outros dias."
            correction["recurrence_note"] = note
            reason = str(correction.get("reason") or correction.get("explanation_pt") or "").strip()
            if note not in reason:
                correction["reason"] = f"{reason} {note}".strip()
            recurring.append({"memory_key": key, "occurrences": before + 1, "note": note})
        else:
            correction.setdefault("recurring", False)
            correction.setdefault("occurrences", 1)

    patterns = analysis.get("patterns_to_revisit") if isinstance(analysis.get("patterns_to_revisit"), list) else []
    for pattern in patterns:
        if not isinstance(pattern, dict):
            continue
        key = normalise_memory_key(pattern)
        pattern["memory_key"] = key
        previous = memories.get(key)
        if previous:
            pattern["recurring"] = True
            pattern["occurrences_before"] = int(previous.get("occurrences") or 0)
    analysis["recurring_mistakes"] = recurring[:6]
    return analysis


def _schedule_after_error(occurrences: int, severity: str) -> datetime:
    severity = str(severity or "medium").lower()
    if occurrences >= 2 or severity == "high":
        days = 1
    elif severity == "low":
        days = 3
    else:
        days = 2
    return _now() + timedelta(days=days)


def _schedule_after_success(successful_retests: int) -> datetime:
    return _now() + timedelta(days=4 if successful_retests <= 1 else 10)


def _trackable(item: dict[str, Any]) -> bool:
    category = str(item.get("category") or "").strip().lower().replace("-", "_").replace("/", "_")
    needs_retest = item.get("needs_retest")
    if needs_retest is False:
        return False
    if category == "typo" and needs_retest is not True and not item.get("recurring"):
        return False
    return category in TRACKED_CATEGORIES or bool(item.get("memory_key") or item.get("mistake_key"))


def _upsert_error(
    conn,
    *,
    uid: str,
    session_id: int | None,
    language_code: str,
    modality: str,
    item: dict[str, Any],
    source: str,
) -> dict[str, Any] | None:
    if not _trackable(item):
        return None
    key = normalise_memory_key(item)
    category = str(item.get("category") or "pattern").strip().lower().replace("/", "_")[:60]
    target = str(item.get("learning_target") or item.get("item") or item.get("natural") or item.get("corrected") or key).strip()[:400]
    severity = str(item.get("severity") or "medium").strip().lower()
    if severity not in {"low", "medium", "high"}:
        severity = "medium"
    now = _now()

    existing = conn.execute(
        "SELECT * FROM learning_mistakes WHERE user_id = ? AND language_code = ? AND memory_key = ?",
        (uid, language_code, key),
    ).fetchone()
    occurrences = int(existing["occurrences"]) + 1 if existing else 1
    due = _schedule_after_error(occurrences, severity)
    payload = dict(item)
    payload["source"] = source
    payload["session_id"] = session_id

    if existing:
        conn.execute(
            """
            UPDATE learning_mistakes
            SET category = ?, modality = ?, learning_target = ?, original_text = ?, corrected_text = ?,
                meaning_pt = ?, explanation_pt = ?, example_text = ?, severity = ?, occurrences = ?,
                successful_retests = 0, status = 'active', last_seen_at = ?, next_due_at = ?, payload_json = ?
            WHERE id = ?
            """,
            (
                category,
                modality,
                target,
                str(item.get("original") or existing["original_text"] or "")[:1200],
                str(item.get("natural") or item.get("corrected") or existing["corrected_text"] or "")[:1200],
                str(item.get("meaning_pt") or existing["meaning_pt"] or "")[:1200],
                str(item.get("explanation_pt") or item.get("reason") or existing["explanation_pt"] or "")[:1600],
                str(item.get("example") or existing["example_text"] or "")[:1200],
                severity,
                occurrences,
                _iso(now),
                _iso(due),
                json.dumps(payload, ensure_ascii=False),
                int(existing["id"]),
            ),
        )
        mistake_id = int(existing["id"])
    else:
        cursor = conn.execute(
            """
            INSERT INTO learning_mistakes(
                user_id, language_code, memory_key, category, modality, learning_target,
                original_text, corrected_text, meaning_pt, explanation_pt, example_text,
                severity, occurrences, successful_retests, status, first_seen_at, last_seen_at,
                next_due_at, last_retested_at, payload_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 0, 'active', ?, ?, ?, NULL, ?)
            """,
            (
                uid,
                language_code,
                key,
                category,
                modality,
                target,
                str(item.get("original") or "")[:1200],
                str(item.get("natural") or item.get("corrected") or "")[:1200],
                str(item.get("meaning_pt") or "")[:1200],
                str(item.get("explanation_pt") or item.get("reason") or "")[:1600],
                str(item.get("example") or "")[:1200],
                severity,
                _iso(now),
                _iso(now),
                _iso(due),
                json.dumps(payload, ensure_ascii=False),
            ),
        )
        mistake_id = int(cursor.lastrowid)

    conn.execute(
        """
        INSERT INTO evidence_events(user_id, session_id, language_code, item_id, modality, event_type, score, payload_json, created_at)
        VALUES (?, ?, ?, ?, ?, 'mistake_observed', NULL, ?, ?)
        """,
        (
            uid,
            session_id,
            language_code,
            key,
            modality,
            json.dumps({"memory_key": key, "category": category, "occurrences": occurrences, "learning_target": target}, ensure_ascii=False),
            _iso(now),
        ),
    )

    review_exists = conn.execute(
        """
        SELECT 1 FROM evidence_events
        WHERE user_id = ? AND session_id IS ? AND language_code = ?
          AND item_id = ? AND modality = ? AND event_type = 'review_target'
        LIMIT 1
        """,
        (uid, session_id, language_code, target, modality),
    ).fetchone()
    if not review_exists:
        conn.execute(
            """
            INSERT INTO evidence_events(user_id, session_id, language_code, item_id, modality, event_type, score, payload_json, created_at)
            VALUES (?, ?, ?, ?, ?, 'review_target', NULL, ?, ?)
            """,
            (
                uid,
                session_id,
                language_code,
                target,
                modality,
                json.dumps(
                    {
                        "memory_key": key,
                        "category": category,
                        "reason": str(item.get("reason") or item.get("explanation_pt") or "Meaningful learner error")[:800],
                        "review_prompt": str(item.get("review_prompt") or f"Use this correctly in a new context: {target}")[:1000],
                        "review_answer": str(item.get("review_answer") or item.get("natural") or item.get("corrected") or target)[:1000],
                    },
                    ensure_ascii=False,
                ),
                _iso(now),
            ),
        )

    return {
        "id": mistake_id,
        "memory_key": key,
        "category": category,
        "learning_target": target,
        "occurrences": occurrences,
        "recurring": occurrences >= 2,
        "next_due_at": _iso(due),
        "status": "active",
    }


def _apply_success(conn, *, uid: str, language_code: str, key: str, modality: str, session_id: int | None) -> dict[str, Any] | None:
    row = conn.execute(
        "SELECT * FROM learning_mistakes WHERE user_id = ? AND language_code = ? AND memory_key = ?",
        (uid, language_code, key),
    ).fetchone()
    if row is None:
        return None
    successes = int(row["successful_retests"]) + 1
    status = "resolved" if successes >= 2 else "monitoring"
    due = _schedule_after_success(successes)
    now = _now()
    conn.execute(
        """
        UPDATE learning_mistakes
        SET successful_retests = ?, status = ?, last_retested_at = ?, next_due_at = ?
        WHERE id = ?
        """,
        (successes, status, _iso(now), _iso(due), int(row["id"])),
    )
    conn.execute(
        """
        INSERT INTO evidence_events(user_id, session_id, language_code, item_id, modality, event_type, score, payload_json, created_at)
        VALUES (?, ?, ?, ?, ?, 'mistake_retest_success', 90, ?, ?)
        """,
        (
            uid,
            session_id,
            language_code,
            key,
            modality,
            json.dumps({"memory_key": key, "successful_retests": successes, "status": status}, ensure_ascii=False),
            _iso(now),
        ),
    )
    return {"memory_key": key, "successful_retests": successes, "status": status, "next_due_at": _iso(due)}


def record_analysis_mistakes(
    session_id: int | None,
    language_code: str,
    modality: str,
    analysis: dict[str, Any],
    *,
    user_id: str | None = None,
) -> list[dict[str, Any]]:
    """Persist only meaningful errors and explicit retest outcomes."""
    _ensure_schema()
    uid = user_id or current_user_id()
    updates: list[dict[str, Any]] = []
    seen_keys: set[str] = set()

    with connection() as conn:
        outcomes = analysis.get("mistake_outcomes") if isinstance(analysis.get("mistake_outcomes"), list) else []
        for outcome in outcomes[:12]:
            if not isinstance(outcome, dict):
                continue
            key = str(outcome.get("memory_key") or "").strip()
            result = str(outcome.get("outcome") or "").strip().lower()
            if key and result == "correct_use":
                updated = _apply_success(conn, uid=uid, language_code=language_code, key=key, modality=modality, session_id=session_id)
                if updated:
                    updates.append({"type": "retest_success", **updated})

        corrections = analysis.get("corrections") if isinstance(analysis.get("corrections"), list) else []
        for correction in corrections[:10]:
            if not isinstance(correction, dict) or not _trackable(correction):
                continue
            key = normalise_memory_key(correction)
            if key in seen_keys:
                continue
            seen_keys.add(key)
            updated = _upsert_error(
                conn,
                uid=uid,
                session_id=session_id,
                language_code=language_code,
                modality=modality,
                item=correction,
                source="correction",
            )
            if updated:
                updates.append({"type": "error", **updated})

        patterns = analysis.get("patterns_to_revisit") if isinstance(analysis.get("patterns_to_revisit"), list) else []
        for pattern in patterns[:10]:
            if not isinstance(pattern, dict) or not _trackable(pattern):
                continue
            key = normalise_memory_key(pattern)
            if key in seen_keys:
                continue
            seen_keys.add(key)
            updated = _upsert_error(
                conn,
                uid=uid,
                session_id=session_id,
                language_code=language_code,
                modality=modality,
                item=pattern,
                source="pattern",
            )
            if updated:
                updates.append({"type": "error", **updated})
        conn.commit()

    analysis["mistake_memory_updates"] = updates
    return updates


def apply_review_rating(
    memory_key: str,
    rating: str,
    language_code: str,
    modality: str,
    *,
    user_id: str | None = None,
) -> None:
    """Let Review v1 feed the same learner-error memory."""
    key = str(memory_key or "").strip()
    if not key:
        return
    _ensure_schema()
    uid = user_id or current_user_id()
    with connection() as conn:
        if str(rating).lower() in {"good", "easy"}:
            _apply_success(conn, uid=uid, language_code=language_code, key=key, modality=modality, session_id=None)
        elif str(rating).lower() in {"again", "hard"}:
            row = conn.execute(
                "SELECT * FROM learning_mistakes WHERE user_id = ? AND language_code = ? AND memory_key = ?",
                (uid, language_code, key),
            ).fetchone()
            if row:
                now = _now()
                occurrences = int(row["occurrences"]) + (1 if str(rating).lower() == "again" else 0)
                conn.execute(
                    """
                    UPDATE learning_mistakes
                    SET occurrences = ?, successful_retests = 0, status = 'active',
                        last_retested_at = ?, next_due_at = ?
                    WHERE id = ?
                    """,
                    (occurrences, _iso(now), _iso(now + timedelta(days=1)), int(row["id"])),
                )
        conn.commit()
