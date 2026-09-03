from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
LANGUAGES_PATH = ROOT / "data" / "languages.json"

VALID_STATUSES = {"active", "maintenance", "parked"}


class LanguageServiceError(RuntimeError):
    pass


def load_languages() -> list[dict[str, Any]]:
    try:
        value = json.loads(LANGUAGES_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise LanguageServiceError("The language list could not be loaded.") from exc
    if not isinstance(value, list):
        raise LanguageServiceError("The language list must be a JSON array.")
    return value


def save_language_settings(updates: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    """Update priority/status for existing languages, keyed by language code.

    This intentionally never adds or removes a language — that stays a
    data/config change, per ARCHITECTURE.md — it only edits the fields the
    learner is expected to tune from day to day.
    """
    if not isinstance(updates, dict):
        raise LanguageServiceError("Language updates must be an object keyed by language code.")

    languages = load_languages()
    by_code = {str(language.get("code")): language for language in languages if language.get("code")}

    for code, changes in updates.items():
        language = by_code.get(str(code))
        if language is None or not isinstance(changes, dict):
            continue

        if "status" in changes and changes["status"] is not None:
            status = str(changes["status"]).strip().lower()
            if status not in VALID_STATUSES:
                raise LanguageServiceError(f"Unsupported language status: {status}")
            language["status"] = status

        if "priority" in changes and changes["priority"] is not None:
            try:
                priority = int(changes["priority"])
            except (TypeError, ValueError) as exc:
                raise LanguageServiceError("Language priority must be a whole number.") from exc
            language["priority"] = max(1, min(9, priority))

    LANGUAGES_PATH.write_text(json.dumps(languages, ensure_ascii=False, indent=2), encoding="utf-8")
    return languages


def top_priority_active_language() -> dict[str, Any] | None:
    """Pick the active language Study should default to.

    This is a small, honest stand-in for the real daily session planner in
    ROADMAP.md Phase 2 — it only picks *which* language, using data that
    already exists (languages.json), rather than pretending to plan a full
    adaptive session.
    """
    active = [language for language in load_languages() if language.get("status") == "active"]
    if not active:
        return None
    active.sort(key=lambda language: (language.get("priority", 99), str(language.get("code", ""))))
    return active[0]
