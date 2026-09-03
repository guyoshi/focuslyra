from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any

from .db import connection
from .language_service import load_languages
from .providers import AIProviderError, ollama_json
from .runtime import current_user_id


class ConceptServiceError(RuntimeError):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure_schema() -> None:
    with connection() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS concepts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                concept_key TEXT NOT NULL,
                label TEXT NOT NULL,
                visual TEXT,
                visual_kind TEXT NOT NULL DEFAULT 'emoji',
                senses_json TEXT NOT NULL DEFAULT '[]',
                expressions_json TEXT NOT NULL DEFAULT '{}',
                notes TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(user_id, concept_key)
            );
            CREATE INDEX IF NOT EXISTS idx_concepts_user_label ON concepts(user_id, label);
            """
        )
        conn.commit()


def _key(label: str) -> str:
    clean = re.sub(r'[^\w]+', '-', label.strip().lower(), flags=re.UNICODE).strip('-')
    return clean[:120] or 'concept'


def _decode(row) -> dict[str, Any]:
    try:
        senses = json.loads(row['senses_json'] or '[]')
    except json.JSONDecodeError:
        senses = []
    try:
        expressions = json.loads(row['expressions_json'] or '{}')
    except json.JSONDecodeError:
        expressions = {}
    return {
        'id': int(row['id']),
        'concept_key': row['concept_key'],
        'label': row['label'],
        'visual': row['visual'],
        'visual_kind': row['visual_kind'],
        'senses': senses,
        'expressions': expressions,
        'notes': row['notes'] or '',
        'created_at': row['created_at'],
        'updated_at': row['updated_at'],
    }


def list_concepts(limit: int = 200, user_id: str | None = None) -> list[dict[str, Any]]:
    _ensure_schema()
    uid = user_id or current_user_id()
    with connection() as conn:
        rows = conn.execute(
            'SELECT * FROM concepts WHERE user_id = ? ORDER BY updated_at DESC LIMIT ?',
            (uid, max(1, min(int(limit), 1000))),
        ).fetchall()
    return [_decode(row) for row in rows]


def save_concept(payload: dict[str, Any], user_id: str | None = None) -> dict[str, Any]:
    _ensure_schema()
    uid = user_id or current_user_id()
    label = str(payload.get('label') or '').strip()
    if not label:
        raise ConceptServiceError('Concept label is required.')
    concept_key = str(payload.get('concept_key') or _key(label)).strip()[:120]
    visual = str(payload.get('visual') or '').strip()[:80]
    visual_kind = str(payload.get('visual_kind') or ('emoji' if visual else 'none')).strip()[:30]
    senses = payload.get('senses') if isinstance(payload.get('senses'), list) else []
    expressions = payload.get('expressions') if isinstance(payload.get('expressions'), dict) else {}
    notes = str(payload.get('notes') or '').strip()[:4000]
    now = _now()

    with connection() as conn:
        conn.execute(
            """
            INSERT INTO concepts(user_id, concept_key, label, visual, visual_kind, senses_json, expressions_json, notes, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id, concept_key) DO UPDATE SET
                label=excluded.label,
                visual=excluded.visual,
                visual_kind=excluded.visual_kind,
                senses_json=excluded.senses_json,
                expressions_json=excluded.expressions_json,
                notes=excluded.notes,
                updated_at=excluded.updated_at
            """,
            (
                uid,
                concept_key,
                label,
                visual or None,
                visual_kind,
                json.dumps(senses, ensure_ascii=False),
                json.dumps(expressions, ensure_ascii=False),
                notes or None,
                now,
                now,
            ),
        )
        conn.commit()
        row = conn.execute('SELECT * FROM concepts WHERE user_id = ? AND concept_key = ?', (uid, concept_key)).fetchone()
    return _decode(row)


def enrich_concept(concept_id: int, user_id: str | None = None) -> dict[str, Any]:
    _ensure_schema()
    uid = user_id or current_user_id()
    with connection() as conn:
        row = conn.execute('SELECT * FROM concepts WHERE id = ? AND user_id = ?', (concept_id, uid)).fetchone()
    if row is None:
        raise ConceptServiceError('Concept not found.')
    concept = _decode(row)
    languages = load_languages(uid)
    target_codes = [item['code'] for item in languages]
    system = """
You enrich one multilingual Focuslyra concept. A concept represents meaning, not merely a translated word.
Return ONLY JSON with keys: label, senses, expressions, suggested_emoji.
- senses is a short list of distinct meanings when needed.
- expressions is an object keyed by the exact language codes requested.
- Each expression value is an object with text and optional reading/transliteration.
- Prefer the most ordinary contemporary expression for the intended meaning.
- Do not force one-to-one equivalence where a language needs a phrase or has multiple senses.
- suggested_emoji must be one existing Unicode emoji when a clear one exists, otherwise empty string.
""".strip()
    user = {
        'concept': concept,
        'language_codes': target_codes,
        'language_targets': {item['code']: item.get('target_variety') for item in languages},
    }
    try:
        result = ollama_json(system, json.dumps(user, ensure_ascii=False), timeout=90.0)
    except AIProviderError as exc:
        raise ConceptServiceError(str(exc)) from exc

    expressions = result.get('expressions') if isinstance(result.get('expressions'), dict) else concept['expressions']
    senses = result.get('senses') if isinstance(result.get('senses'), list) else concept['senses']
    visual = concept['visual'] or str(result.get('suggested_emoji') or '').strip()
    return save_concept(
        {
            **concept,
            'label': str(result.get('label') or concept['label']),
            'senses': senses,
            'expressions': expressions,
            'visual': visual,
            'visual_kind': 'emoji' if visual else concept['visual_kind'],
        },
        uid,
    )
