from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from .db import connection
from .providers import AIProviderError, ollama_json
from .runtime import current_user_id


class DiagnosticServiceError(RuntimeError):
    pass


ENGLISH_TASKS = [
    {
        'id': 'spontaneous_speech',
        'kind': 'speech',
        'title': 'Spontaneous speaking',
        'prompt': 'Speak for 2–3 minutes: If you never needed to work for someone else again, what would you do over the next five years, and how would it change you as a person?',
    },
    {
        'id': 'circumlocution',
        'kind': 'speech',
        'title': 'Lexical retrieval',
        'prompt': 'Explain these ideas without using the target word itself: deadline, screwdriver, stubborn, coincidence, homesick. Keep speaking rather than switching to Portuguese.',
    },
    {
        'id': 'grammar_automaticity',
        'kind': 'text',
        'title': 'Grammar automaticity',
        'prompt': "Complete naturally and quickly, without researching: If I'd known… / I wish I… / By the time… / I'd rather… / I was supposed to… / I might have… / What I find most difficult… / It's not that… / Had I realised… / I ended up…",
    },
    {
        'id': 'writing',
        'kind': 'text',
        'title': 'Spontaneous writing',
        'prompt': 'Write 150–250 words: Is technology making ordinary people more independent, or more dependent on systems they do not control? Give your own view and reasons.',
    },
    {
        'id': 'rp_listening',
        'kind': 'listening',
        'title': 'Blind RP listening',
        'prompt': 'Listen without seeing the transcript. Summarise what happened, then write the details you are least certain about.',
        'audio_text': "I was going to meet Sarah near Victoria just after half past six, but by the time I got there she'd already left a message saying the train had been cancelled. Rather than wait around, I walked towards the river and rang her on the way. She sounded tired, but said she'd try another route and meet me outside the theatre before the doors opened.",
    },
    {
        'id': 'rp_pronunciation',
        'kind': 'pronunciation',
        'title': 'RP pronunciation baseline',
        'prompt': 'Listen once, then read this naturally. Do not imitate word by word. Aim for connected speech and sentence rhythm.',
        'reference_text': "After a rather long morning, Sarah asked whether I could bring her a glass of water before we left for the theatre. I was certain we'd arrive early, but the traffic around Victoria was far worse than I'd imagined.",
        'target_feature': 'contemporary RP timing, weak forms and connected speech',
    },
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure_schema() -> None:
    with connection() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS diagnostic_attempts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                language_code TEXT NOT NULL,
                status TEXT NOT NULL,
                parts_json TEXT NOT NULL DEFAULT '{}',
                summary_json TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                completed_at TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_diagnostic_user ON diagnostic_attempts(user_id, language_code, id);
            """
        )
        conn.commit()


def start_english_diagnostic(user_id: str | None = None) -> dict[str, Any]:
    _ensure_schema()
    uid = user_id or current_user_id()
    now = _now()
    with connection() as conn:
        cursor = conn.execute(
            "INSERT INTO diagnostic_attempts(user_id, language_code, status, parts_json, created_at, updated_at) VALUES (?, 'en-GB', 'in_progress', '{}', ?, ?)",
            (uid, now, now),
        )
        attempt_id = int(cursor.lastrowid)
        conn.commit()
    return {'id': attempt_id, 'language_code': 'en-GB', 'status': 'in_progress', 'tasks': ENGLISH_TASKS, 'parts': {}}


def get_attempt(attempt_id: int, user_id: str | None = None) -> dict[str, Any]:
    _ensure_schema()
    uid = user_id or current_user_id()
    with connection() as conn:
        row = conn.execute('SELECT * FROM diagnostic_attempts WHERE id = ? AND user_id = ?', (attempt_id, uid)).fetchone()
    if row is None:
        raise DiagnosticServiceError('Diagnostic attempt not found.')
    try:
        parts = json.loads(row['parts_json'] or '{}')
    except json.JSONDecodeError:
        parts = {}
    try:
        summary = json.loads(row['summary_json']) if row['summary_json'] else None
    except json.JSONDecodeError:
        summary = None
    return {
        'id': int(row['id']), 'language_code': row['language_code'], 'status': row['status'],
        'tasks': ENGLISH_TASKS, 'parts': parts, 'summary': summary,
        'created_at': row['created_at'], 'completed_at': row['completed_at'],
    }


def save_part(attempt_id: int, part_id: str, result: dict[str, Any], user_id: str | None = None) -> dict[str, Any]:
    attempt = get_attempt(attempt_id, user_id)
    if part_id not in {task['id'] for task in ENGLISH_TASKS}:
        raise DiagnosticServiceError('Unknown diagnostic part.')
    parts = dict(attempt['parts'])
    parts[part_id] = result
    now = _now()
    uid = user_id or current_user_id()
    with connection() as conn:
        conn.execute(
            'UPDATE diagnostic_attempts SET parts_json = ?, updated_at = ? WHERE id = ? AND user_id = ?',
            (json.dumps(parts, ensure_ascii=False), now, attempt_id, uid),
        )
        conn.commit()
    return get_attempt(attempt_id, uid)


def _scores_from_parts(parts: dict[str, Any]) -> dict[str, list[float]]:
    values: dict[str, list[float]] = {}
    for result in parts.values():
        analysis = result.get('analysis') if isinstance(result, dict) else None
        scores = analysis.get('scores') if isinstance(analysis, dict) else None
        if not isinstance(scores, dict) and isinstance(result, dict):
            assessment = result.get('assessment')
            scores = assessment.get('scores') if isinstance(assessment, dict) else None
        if not isinstance(scores, dict):
            continue
        for key, raw in scores.items():
            try:
                score = float(raw)
            except (TypeError, ValueError):
                continue
            values.setdefault(str(key), []).append(score)
    return values


def finalise(attempt_id: int, user_id: str | None = None) -> dict[str, Any]:
    attempt = get_attempt(attempt_id, user_id)
    parts = attempt['parts']
    if len(parts) < 4:
        raise DiagnosticServiceError('Complete at least four diagnostic sections before finalising.')
    raw_scores = _scores_from_parts(parts)
    averages = {key: round(sum(values) / len(values)) for key, values in raw_scores.items() if values}
    system = """
You are Focuslyra's English diagnostic synthesiser. Build a practical ability map, not a school grade.
Return ONLY JSON with: overall_summary, dimensions, strongest_areas, priority_gaps, first_30_days.
dimensions must be an object whose values are integer 0-100 or null. Use these exact keys:
spontaneous_fluency, grammar_automaticity, active_vocabulary, lexical_retrieval, native_speed_listening, rp_sound_perception, rp_pronunciation_prosody, writing_control.
Do not invent precision unsupported by the submitted evidence. Pronunciation data may be broad prosody/intelligibility rather than phoneme accuracy.
Do not claim a certified CEFR level. You may include a cautious CEFR-like range in overall_summary only if the evidence strongly supports it.
""".strip()
    payload = {'parts': parts, 'raw_evidence_averages': averages}
    try:
        summary = ollama_json(system, json.dumps(payload, ensure_ascii=False), timeout=120.0)
    except AIProviderError:
        base = round(sum(averages.values()) / len(averages)) if averages else None
        summary = {
            'overall_summary': 'Diagnostic evidence saved. A richer synthesis will be available when the local model is running.',
            'dimensions': {
                'spontaneous_fluency': averages.get('communication', base),
                'grammar_automaticity': averages.get('grammar_automaticity', base),
                'active_vocabulary': averages.get('active_vocabulary', base),
                'lexical_retrieval': averages.get('active_vocabulary', base),
                'native_speed_listening': averages.get('communication', base),
                'rp_sound_perception': None,
                'rp_pronunciation_prosody': averages.get('practice_similarity'),
                'writing_control': averages.get('naturalness', base),
            },
            'strongest_areas': [], 'priority_gaps': [], 'first_30_days': [],
        }
    now = _now()
    uid = user_id or current_user_id()
    with connection() as conn:
        conn.execute(
            "UPDATE diagnostic_attempts SET status='completed', summary_json=?, updated_at=?, completed_at=? WHERE id=? AND user_id=?",
            (json.dumps(summary, ensure_ascii=False), now, now, attempt_id, uid),
        )
        conn.commit()
    return get_attempt(attempt_id, uid)


def latest_completed(user_id: str | None = None) -> dict[str, Any] | None:
    _ensure_schema()
    uid = user_id or current_user_id()
    with connection() as conn:
        row = conn.execute("SELECT id FROM diagnostic_attempts WHERE user_id=? AND language_code='en-GB' AND status='completed' ORDER BY id DESC LIMIT 1", (uid,)).fetchone()
    return get_attempt(int(row['id']), uid) if row else None
