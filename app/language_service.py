from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .profile_service import load_profile, save_profile

ROOT = Path(__file__).resolve().parents[1]
LANGUAGES_PATH = ROOT / "data" / "languages.json"

VALID_STATUSES = {"active", "maintenance", "parked"}


class LanguageServiceError(RuntimeError):
    pass


def _catalogue() -> list[dict[str, Any]]:
    try:
        value = json.loads(LANGUAGES_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise LanguageServiceError("The language catalogue could not be loaded.") from exc
    if not isinstance(value, list):
        raise LanguageServiceError("The language catalogue must be a JSON array.")
    return value


def _settings_from_profile(profile: dict[str, Any]) -> dict[str, dict[str, Any]]:
    raw = profile.get("language_settings")
    if isinstance(raw, dict):
        return {str(code): dict(settings) for code, settings in raw.items() if isinstance(settings, dict)}
    return {}


def load_languages(user_id: str | None = None) -> list[dict[str, Any]]:
    """Return the global language catalogue merged with learner-owned settings.

    Catalogue fields describe the language itself. Priority/status/current state/goals
    belong to the learner and are stored in that learner's profile. Legacy catalogue
    fields are accepted only as migration/default fallbacks so older installs keep
    working without leaking one learner's priorities into another account.
    """
    profile = load_profile(user_id)
    settings = _settings_from_profile(profile)
    result: list[dict[str, Any]] = []

    for base in _catalogue():
        code = str(base.get("code") or "").strip()
        if not code:
            continue
        merged = dict(base)
        learner = settings.get(code, {})

        merged["priority"] = int(learner.get("priority", base.get("default_priority", base.get("priority", 5))))
        merged["status"] = str(learner.get("status", base.get("default_status", base.get("status", "parked"))))
        merged["current_state"] = str(
            learner.get("current_state", base.get("default_current_state", base.get("current_state", "Not assessed yet.")))
        )
        goals = learner.get("goals", base.get("default_goals", base.get("goals", [])))
        merged["goals"] = list(goals) if isinstance(goals, list) else []

        # Never expose legacy learner-specific defaults as writable catalogue fields.
        for key in ("default_priority", "default_status", "default_current_state", "default_goals"):
            merged.pop(key, None)
        result.append(merged)
    return result


def save_language_settings(updates: dict[str, dict[str, Any]], user_id: str | None = None) -> list[dict[str, Any]]:
    if not isinstance(updates, dict):
        raise LanguageServiceError("Language updates must be an object keyed by language code.")

    catalogue_codes = {str(language.get("code")) for language in _catalogue() if language.get("code")}
    profile = load_profile(user_id)
    stored = _settings_from_profile(profile)

    for code, changes in updates.items():
        code = str(code)
        if code not in catalogue_codes or not isinstance(changes, dict):
            continue
        current = dict(stored.get(code, {}))

        if "status" in changes and changes["status"] is not None:
            status = str(changes["status"]).strip().lower()
            if status not in VALID_STATUSES:
                raise LanguageServiceError(f"Unsupported language status: {status}")
            current["status"] = status

        if "priority" in changes and changes["priority"] is not None:
            try:
                priority = int(changes["priority"])
            except (TypeError, ValueError) as exc:
                raise LanguageServiceError("Language priority must be a whole number.") from exc
            current["priority"] = max(1, min(9, priority))

        if "current_state" in changes and changes["current_state"] is not None:
            current["current_state"] = str(changes["current_state"]).strip()[:1000]

        if "goals" in changes and isinstance(changes["goals"], list):
            current["goals"] = [str(goal).strip()[:160] for goal in changes["goals"] if str(goal).strip()][:20]

        stored[code] = current

    profile["language_settings"] = stored
    save_profile(profile, user_id)
    return load_languages(user_id)


def top_priority_active_language(user_id: str | None = None) -> dict[str, Any] | None:
    active = [language for language in load_languages(user_id) if language.get("status") == "active"]
    if not active:
        return None
    active.sort(key=lambda language: (int(language.get("priority", 99)), str(language.get("code", ""))))
    return active[0]
