from __future__ import annotations

import fnmatch
import json
import math
import re
from collections import Counter
from pathlib import Path
from typing import Any

from .db import connection
from .runtime import current_user_id
from .source_manager import SOURCES_DIR, find_source, sync_git_source


class MemoryIndexError(RuntimeError):
    pass


TEXT_EXTENSIONS = {'.md', '.txt', '.json', '.yaml', '.yml', '.rst'}


def _ensure_schema() -> None:
    with connection() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS source_chunks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                source_id TEXT NOT NULL,
                repository TEXT,
                commit_sha TEXT,
                path TEXT NOT NULL,
                chunk_index INTEGER NOT NULL,
                content TEXT NOT NULL,
                tokens_json TEXT NOT NULL,
                UNIQUE(user_id, source_id, path, chunk_index)
            );
            CREATE INDEX IF NOT EXISTS idx_source_chunks_user_source ON source_chunks(user_id, source_id, id);
            """
        )
        conn.commit()


def _tokens(text: str) -> list[str]:
    return [token for token in re.findall(r"[^\W_]{2,}", text.lower(), flags=re.UNICODE) if not token.isdigit()]


def _allowed(path: Path, source: dict[str, Any], root: Path) -> bool:
    rel = path.relative_to(root).as_posix()
    includes = source.get('include') or ['**/*']
    excludes = source.get('exclude') or []
    included = any(fnmatch.fnmatch(rel, pattern) or Path(rel).match(pattern) for pattern in includes)
    excluded = any(fnmatch.fnmatch(rel, pattern) or Path(rel).match(pattern) for pattern in excludes)
    return included and not excluded and path.suffix.lower() in TEXT_EXTENSIONS


def _chunks(text: str, size: int = 1400, overlap: int = 180) -> list[str]:
    clean = text.replace('\r\n', '\n').strip()
    if not clean:
        return []
    paragraphs = [part.strip() for part in re.split(r'\n\s*\n', clean) if part.strip()]
    result: list[str] = []
    current = ''
    for paragraph in paragraphs:
        candidate = f'{current}\n\n{paragraph}'.strip() if current else paragraph
        if len(candidate) <= size:
            current = candidate
            continue
        if current:
            result.append(current)
        if len(paragraph) <= size:
            current = paragraph
            continue
        start = 0
        while start < len(paragraph):
            part = paragraph[start:start + size].strip()
            if part:
                result.append(part)
            start += max(1, size - overlap)
        current = ''
    if current:
        result.append(current)
    return result


def index_source(source_id: str, sync_first: bool = True, user_id: str | None = None) -> dict[str, Any]:
    _ensure_schema()
    uid = user_id or current_user_id()
    source = find_source(source_id)
    if not source.get('enabled', True):
        raise MemoryIndexError('This source is disabled.')
    sync_result = sync_git_source(source_id) if sync_first else None
    root = SOURCES_DIR / source_id
    if not root.exists():
        raise MemoryIndexError('Source is not available locally. Sync it first.')
    commit = (sync_result or {}).get('commit')
    if not commit and (root / '.git').exists():
        try:
            import subprocess
            commit = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=root, capture_output=True, text=True, check=True).stdout.strip()
        except Exception:
            commit = None

    records: list[tuple[Any, ...]] = []
    file_count = 0
    for path in root.rglob('*'):
        if not path.is_file() or '.git' in path.parts or not _allowed(path, source, root):
            continue
        try:
            if path.stat().st_size > 2_000_000:
                continue
            text = path.read_text(encoding='utf-8', errors='replace')
        except OSError:
            continue
        parts = _chunks(text)
        if not parts:
            continue
        file_count += 1
        rel = path.relative_to(root).as_posix()
        for index, chunk in enumerate(parts):
            token_counts = Counter(_tokens(chunk))
            records.append((uid, source_id, source.get('repository'), commit, rel, index, chunk, json.dumps(token_counts, ensure_ascii=False)))

    with connection() as conn:
        conn.execute('DELETE FROM source_chunks WHERE user_id = ? AND source_id = ?', (uid, source_id))
        conn.executemany(
            """
            INSERT INTO source_chunks(user_id, source_id, repository, commit_sha, path, chunk_index, content, tokens_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            records,
        )
        conn.commit()
    return {'source_id': source_id, 'commit': commit, 'files_indexed': file_count, 'chunks_indexed': len(records)}


def index_status(user_id: str | None = None) -> list[dict[str, Any]]:
    _ensure_schema()
    uid = user_id or current_user_id()
    with connection() as conn:
        rows = conn.execute(
            """
            SELECT source_id, repository, MAX(commit_sha) AS commit_sha, COUNT(*) AS chunks, COUNT(DISTINCT path) AS files
            FROM source_chunks WHERE user_id = ? GROUP BY source_id, repository ORDER BY source_id
            """,
            (uid,),
        ).fetchall()
    return [dict(row) for row in rows]


def retrieve(query: str, limit: int = 4, source_ids: list[str] | None = None, user_id: str | None = None) -> list[dict[str, Any]]:
    _ensure_schema()
    uid = user_id or current_user_id()
    query_tokens = Counter(_tokens(query))
    params: list[Any] = [uid]
    where = 'user_id = ?'
    if source_ids:
        placeholders = ','.join('?' for _ in source_ids)
        where += f' AND source_id IN ({placeholders})'
        params.extend(source_ids)
    with connection() as conn:
        rows = conn.execute(f'SELECT * FROM source_chunks WHERE {where}', params).fetchall()
    if not rows:
        return []

    doc_freq: Counter[str] = Counter()
    decoded = []
    for row in rows:
        try:
            counts = Counter(json.loads(row['tokens_json'] or '{}'))
        except json.JSONDecodeError:
            counts = Counter()
        decoded.append((row, counts))
        doc_freq.update(counts.keys())

    scored: list[tuple[float, Any]] = []
    n = len(decoded)
    for row, counts in decoded:
        score = 0.0
        for token, qcount in query_tokens.items():
            tf = counts.get(token, 0)
            if tf:
                idf = math.log((n + 1) / (doc_freq[token] + 1)) + 1.0
                score += (1.0 + math.log(tf)) * idf * qcount
        path_lower = str(row['path']).lower()
        for token in query_tokens:
            if token in path_lower:
                score += 2.0
        if score > 0:
            scored.append((score, row))

    if not scored:
        # A deterministic interest fallback is still useful for activity generation
        # when the learner's target phrase does not lexically overlap source canon.
        decoded_sorted = sorted(decoded, key=lambda pair: (pair[0]['source_id'], pair[0]['path'], pair[0]['chunk_index']))
        picked = decoded_sorted[:max(1, min(limit, 4))]
        return [
            {
                'source_id': row['source_id'], 'repository': row['repository'], 'commit': row['commit_sha'],
                'path': row['path'], 'content': row['content'], 'score': 0.0,
            }
            for row, _ in picked
        ]

    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [
        {
            'source_id': row['source_id'], 'repository': row['repository'], 'commit': row['commit_sha'],
            'path': row['path'], 'content': row['content'], 'score': round(score, 3),
        }
        for score, row in scored[:max(1, min(limit, 10))]
    ]
