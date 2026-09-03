from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any

from .db import connection
from .language_service import load_languages
from .runtime import current_user_id


def _since(days: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()


def learner_progress(user_id: str | None = None) -> dict[str, Any]:
    uid = user_id or current_user_id()
    languages = load_languages(uid)
    with connection() as conn:
        session_rows = conn.execute(
            """
            SELECT language_code,
                   COUNT(*) AS sessions_total,
                   SUM(CASE WHEN completed_at >= ? THEN 1 ELSE 0 END) AS sessions_7d,
                   SUM(CASE WHEN completed_at >= ? THEN 1 ELSE 0 END) AS sessions_30d,
                   MAX(completed_at) AS last_session_at
            FROM sessions
            WHERE user_id = ? AND language_code IS NOT NULL
            GROUP BY language_code
            """,
            (_since(7), _since(30), uid),
        ).fetchall()
        score_rows = conn.execute(
            """
            SELECT language_code, item_id, modality, score, created_at
            FROM evidence_events
            WHERE user_id = ? AND event_type = 'skill_score' AND score IS NOT NULL
            ORDER BY id DESC
            """,
            (uid,),
        ).fetchall()
        review_rows = conn.execute(
            """
            SELECT language_code, COUNT(*) AS n
            FROM evidence_events
            WHERE user_id = ? AND event_type = 'review_result'
            GROUP BY language_code
            """,
            (uid,),
        ).fetchall()

    session_by_code = {row['language_code']: dict(row) for row in session_rows}
    review_by_code = {row['language_code']: int(row['n']) for row in review_rows}
    grouped: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    modality_grouped: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    for row in score_rows:
        code = str(row['language_code'])
        skill = str(row['item_id'] or 'general')
        if len(grouped[code][skill]) < 12:
            grouped[code][skill].append(float(row['score']))
        modality = str(row['modality'] or 'unknown')
        if len(modality_grouped[code][modality]) < 20:
            modality_grouped[code][modality].append(float(row['score']))

    result = []
    for language in languages:
        code = language['code']
        sessions = session_by_code.get(code, {})
        skills = {
            skill: round(sum(values) / len(values))
            for skill, values in grouped.get(code, {}).items()
            if values
        }
        modalities = {
            modality: round(sum(values) / len(values))
            for modality, values in modality_grouped.get(code, {}).items()
            if values
        }
        all_scores = [score for values in grouped.get(code, {}).values() for score in values]
        overall = round(sum(all_scores) / len(all_scores)) if all_scores else None
        confidence = min(100, len(all_scores) * 4)
        result.append(
            {
                'code': code,
                'name': language.get('name'),
                'flag': language.get('flag'),
                'status': language.get('status'),
                'priority': language.get('priority'),
                'target_variety': language.get('target_variety'),
                'overall_evidence_score': overall,
                'evidence_confidence': confidence,
                'skills': skills,
                'modalities': modalities,
                'sessions_total': int(sessions.get('sessions_total') or 0),
                'sessions_7d': int(sessions.get('sessions_7d') or 0),
                'sessions_30d': int(sessions.get('sessions_30d') or 0),
                'last_session_at': sessions.get('last_session_at'),
                'review_responses': review_by_code.get(code, 0),
            }
        )

    with connection() as conn:
        total_sessions = conn.execute('SELECT COUNT(*) AS n FROM sessions WHERE user_id = ?', (uid,)).fetchone()['n']
        total_evidence = conn.execute('SELECT COUNT(*) AS n FROM evidence_events WHERE user_id = ?', (uid,)).fetchone()['n']
        try:
            due_reviews = conn.execute('SELECT COUNT(*) AS n FROM review_items WHERE user_id = ? AND due_at <= ?', (uid, datetime.now(timezone.utc).isoformat())).fetchone()['n']
        except Exception:
            due_reviews = 0
        try:
            concepts = conn.execute('SELECT COUNT(*) AS n FROM concepts WHERE user_id = ?', (uid,)).fetchone()['n']
        except Exception:
            concepts = 0
    return {
        'languages': result,
        'totals': {
            'sessions': int(total_sessions),
            'evidence_events': int(total_evidence),
            'reviews_due': int(due_reviews),
            'concepts': int(concepts),
        },
        'warning': 'Scores are evidence summaries from Focuslyra activities, not certified CEFR levels.',
    }
