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


def _enabled_codes(profile: dict[str, Any], catalogue_codes: list[str]) -> set[str]:
    """Return languages selected by the learner.

    Older personal profiles did not have enabled_languages. For backwards
    compatibility, absence of the field means every catalogue language is
    selected. New/explicit profiles store the selected list directly.
    """
    raw = profile.get("enabled_languages")
    if isinstance(raw, list):
        return {str(code) for code in raw if str(code) in catalogue_codes}
    return set(catalogue_codes)


def load_language_catalogue(user_id: str | None = None) -> list[dict[str, Any]]:
    """Return every supported language plus learner-owned settings.

    This is the Settings/onboarding view. ``selected`` controls whether the
    language belongs to this learner's study set; unselected languages remain
    visible here so they can be enabled later.
    """
    profile = load_profile(user_id)
    settings = _settings_from_profile(profile)
    catalogue = _catalogue()
    catalogue_codes = [str(item.get("code") or "") for item in catalogue if item.get("code")]
    enabled = _enabled_codes(profile, catalogue_codes)
    result: list[dict[str, Any]] = []

    for base in catalogue:
        code = str(base.get("code") or "").strip()
        if not code:
            continue
        merged = dict(base)
        learner = settings.get(code, {})
        merged["selected"] = code in enabled
        merged["priority"] = int(learner.get("priority", base.get("default_priority", base.get("priority", 3))))
        merged["status"] = str(learner.get("status", base.get("default_status", base.get("status", "active"))))
        merged["target_variety"] = str(
            learner.get("target_variety", base.get("default_target_variety", base.get("target_variety", code)))
        )
        merged["current_state"] = str(
            learner.get("current_state", base.get("default_current_state", base.get("current_state", "Not assessed yet.")))
        )
        goals = learner.get("goals", base.get("default_goals", base.get("goals", [])))
        merged["goals"] = list(goals) if isinstance(goals, list) else []

        for key in (
            "default_priority",
            "default_status",
            "default_target_variety",
            "default_current_state",
            "default_goals",
        ):
            merged.pop(key, None)
        result.append(merged)
    return result


def load_languages(user_id: str | None = None) -> list[dict[str, Any]]:
    """Return only languages selected for this learner.

    Daily planning, dashboard language cards, assessment and study generation
    use this filtered list. Settings uses :func:`load_language_catalogue` so
    every supported language is always available to every learner.
    """
    return [language for language in load_language_catalogue(user_id) if language.get("selected")]


def save_language_settings(updates: dict[str, dict[str, Any]], user_id: str | None = None) -> list[dict[str, Any]]:
    if not isinstance(updates, dict):
        raise LanguageServiceError("Language updates must be an object keyed by language code.")

    catalogue = _catalogue()
    catalogue_order = [str(language.get("code")) for language in catalogue if language.get("code")]
    catalogue_codes = set(catalogue_order)
    profile = load_profile(user_id)
    stored = _settings_from_profile(profile)
    enabled = _enabled_codes(profile, catalogue_order)

    for code, changes in updates.items():
        code = str(code)
        if code not in catalogue_codes or not isinstance(changes, dict):
            continue
        current = dict(stored.get(code, {}))

        if "selected" in changes and changes["selected"] is not None:
            if bool(changes["selected"]):
                enabled.add(code)
            else:
                enabled.discard(code)

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
            current["priority"] = max(1, min(4, priority))

        if "target_variety" in changes and changes["target_variety"] is not None:
            current["target_variety"] = str(changes["target_variety"]).strip()[:240]

        if "current_state" in changes and changes["current_state"] is not None:
            current["current_state"] = str(changes["current_state"]).strip()[:1000]

        if "goals" in changes and isinstance(changes["goals"], list):
            current["goals"] = [str(goal).strip()[:220] for goal in changes["goals"] if str(goal).strip()][:8]

        stored[code] = current

    profile["enabled_languages"] = [code for code in catalogue_order if code in enabled]
    profile["language_settings"] = stored
    save_profile(profile, user_id)
    return load_languages(user_id)


def top_priority_active_language(user_id: str | None = None) -> dict[str, Any] | None:
    active = [language for language in load_languages(user_id) if language.get("status") == "active"]
    if not active:
        return None
    active.sort(key=lambda language: (int(language.get("priority", 99)), str(language.get("code", ""))))
    return active[0]
