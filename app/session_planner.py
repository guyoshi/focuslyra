from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from .db import connection, recent_learning_evidence
from .language_service import load_languages
from .profile_service import load_profile
from .runtime import current_user_id


@dataclass
class LanguageStats:
    last_session_at: str | None
    sessions_7d: int
    sessions_30d: int
    review_targets: int
    average_skill_score: float | None


def _language_stats(language_code: str, user_id: str | None = None) -> LanguageStats:
    uid = user_id or current_user_id()
    now = datetime.now(timezone.utc)
    seven = (now - timedelta(days=7)).isoformat()
    thirty = (now - timedelta(days=30)).isoformat()
    with connection() as conn:
        latest = conn.execute(
            "SELECT MAX(completed_at) AS last_at FROM sessions WHERE user_id = ? AND language_code = ?",
            (uid, language_code),
        ).fetchone()
        seven_row = conn.execute(
            "SELECT COUNT(*) AS n FROM sessions WHERE user_id = ? AND language_code = ? AND completed_at >= ?",
            (uid, language_code, seven),
        ).fetchone()
        thirty_row = conn.execute(
            "SELECT COUNT(*) AS n FROM sessions WHERE user_id = ? AND language_code = ? AND completed_at >= ?",
            (uid, language_code, thirty),
        ).fetchone()
        score_row = conn.execute(
            """
            SELECT AVG(score) AS avg_score
            FROM (
                SELECT score FROM evidence_events
                WHERE user_id = ? AND language_code = ? AND event_type = 'skill_score' AND score IS NOT NULL
                ORDER BY id DESC LIMIT 24
            )
            """,
            (uid, language_code),
        ).fetchone()

    evidence = recent_learning_evidence(language_code, limit=40, user_id=uid)
    review_targets = sum(1 for event in evidence if event.get("event_type") == "review_target")
    return LanguageStats(
        last_session_at=latest["last_at"] if latest else None,
        sessions_7d=int(seven_row["n"] if seven_row else 0),
        sessions_30d=int(thirty_row["n"] if thirty_row else 0),
        review_targets=review_targets,
        average_skill_score=float(score_row["avg_score"]) if score_row and score_row["avg_score"] is not None else None,
    )


def _days_since(value: str | None) -> float:
    if not value:
        return 30.0
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return max(0.0, (datetime.now(timezone.utc) - dt.astimezone(timezone.utc)).total_seconds() / 86400.0)
    except ValueError:
        return 7.0


def _priority_score(language: dict[str, Any], stats: LanguageStats) -> float:
    priority = max(1, min(9, int(language.get("priority", 5))))
    status = str(language.get("status", "parked"))
    status_weight = {"active": 100.0, "maintenance": 38.0, "parked": -1000.0}.get(status, 0.0)
    stale = min(18.0, _days_since(stats.last_session_at) * 2.2)
    review = min(16.0, stats.review_targets * 2.0)
    scarcity = max(0.0, 7.0 - stats.sessions_7d) * 1.5
    difficulty = 0.0 if stats.average_skill_score is None else max(0.0, (70.0 - stats.average_skill_score) / 8.0)
    return status_weight + (12.0 - priority * 2.4) + stale + review + scarcity + difficulty


def _mode_candidates(language: dict[str, Any], stats: LanguageStats) -> list[str]:
    goals = " ".join(str(goal).lower() for goal in language.get("goals", []))
    code = str(language.get("code", ""))
    modes: list[str] = []

    if stats.review_targets:
        modes.append("review")
    if "pronunciation" in goals or "accent" in goals or "rp" in goals:
        modes.extend(["pronounce", "listen"])
    if "listening" in goals:
        modes.append("listen")
    if any(token in goals for token in ("speaking", "conversation", "fluency", "reactivate")):
        modes.append("speak")
    if any(token in goals for token in ("kana", "kanji", "reading", "alphabet")) or code == "ja-JP":
        modes.append("read")
    if "writing" in goals:
        modes.append("write")

    # Speaking/listening-first global fallback.
    modes.extend(["speak", "listen", "write"])
    unique: list[str] = []
    for mode in modes:
        if mode not in unique:
            unique.append(mode)
    return unique


def _hidden_targets(language_code: str, user_id: str | None = None) -> list[str]:
    events = recent_learning_evidence(language_code, limit=30, user_id=user_id)
    targets: list[str] = []
    for event in events:
        if event.get("event_type") != "review_target":
            continue
        item = str(event.get("item_id") or "").strip()
        if item and item not in targets:
            targets.append(item)
        if len(targets) >= 4:
            break
    return targets


def _session_minutes(profile: dict[str, Any], mode: str) -> int:
    field = "minimum_session_minutes" if mode == "minimum" else "normal_session_minutes"
    default = 12 if mode == "minimum" else 45
    try:
        return max(5, min(180, int(profile.get(field, default))))
    except (TypeError, ValueError):
        return default


def build_daily_plan(mode: str = "normal", user_id: str | None = None) -> dict[str, Any]:
    """Build a deterministic plan from learner priorities, recency and evidence.

    The planner itself does not call an LLM. It decides *what needs practice*;
    the activity generator decides *how to present it*. This separation keeps
    scheduling reliable even when local AI is unavailable.
    """
    uid = user_id or current_user_id()
    profile = load_profile(uid)
    languages = load_languages(uid)
    total = _session_minutes(profile, mode)

    candidates: list[tuple[float, dict[str, Any], LanguageStats]] = []
    for language in languages:
        if language.get("status") == "parked":
            continue
        stats = _language_stats(str(language.get("code")), uid)
        candidates.append((_priority_score(language, stats), language, stats))
    candidates.sort(key=lambda item: item[0], reverse=True)

    if not candidates:
        return {"mode": mode, "total_minutes": total, "activities": [], "reason": "No active or maintenance language is configured."}

    if mode == "minimum" or total <= 15:
        chosen = candidates[:1]
        activity_count = 2 if total >= 10 else 1
    elif total <= 30:
        chosen = candidates[:2]
        activity_count = min(3, len(chosen) + 1)
    else:
        # Prefer active languages, but allow one stale maintenance language to
        # enter longer sessions when it has been neglected.
        active = [item for item in candidates if item[1].get("status") == "active"]
        maintenance = [item for item in candidates if item[1].get("status") == "maintenance"]
        chosen = active[:3]
        if total >= 55 and maintenance:
            chosen = (chosen[:2] + maintenance[:1]) if len(chosen) >= 2 else (chosen + maintenance[:1])
        chosen = chosen or candidates[:2]
        activity_count = min(6, max(3, round(total / 9)))

    # Allocate activity slots round-robin across chosen languages, then divide minutes.
    slots: list[tuple[dict[str, Any], LanguageStats, str]] = []
    mode_indexes: dict[str, int] = {}
    for index in range(activity_count):
        _, language, stats = chosen[index % len(chosen)]
        code = str(language.get("code"))
        choices = _mode_candidates(language, stats)
        pointer = mode_indexes.get(code, 0)
        modality = choices[pointer % len(choices)]
        mode_indexes[code] = pointer + 1
        slots.append((language, stats, modality))

    base = total // len(slots)
    remainder = total % len(slots)
    activities: list[dict[str, Any]] = []
    for index, (language, stats, modality) in enumerate(slots):
        minutes = max(4, base + (1 if index < remainder else 0))
        targets = _hidden_targets(str(language.get("code")), uid)
        activities.append(
            {
                "id": f"a{index + 1}",
                "order": index + 1,
                "language_code": language.get("code"),
                "language_name": language.get("name"),
                "flag": language.get("flag"),
                "target_variety": language.get("target_variety"),
                "modality": modality,
                "minutes": minutes,
                "hidden_targets": targets,
                "reason": (
                    "review evidence is due" if modality == "review" and targets
                    else "high priority + recent learning evidence"
                ),
                "stats": {
                    "days_since_last_session": round(_days_since(stats.last_session_at), 1),
                    "sessions_7d": stats.sessions_7d,
                    "review_targets": stats.review_targets,
                },
            }
        )

    return {
        "mode": mode,
        "total_minutes": total,
        "activities": activities,
        "languages": [item[1].get("code") for item in chosen],
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "planner": "focuslyra-rules-v1",
    }
