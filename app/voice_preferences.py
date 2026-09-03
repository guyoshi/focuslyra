from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from .runtime import current_user_id, user_private_dir

ROOT = Path(__file__).resolve().parents[1]
LANGUAGES_PATH = ROOT / "data" / "languages.json"
LEGACY_VOICE_PREFERENCES_PATH = ROOT / "private" / "preferences" / "voice_profiles.json"

VALID_ENGINES = {"auto", "kokoro", "browser"}
VALID_PURPOSES = {"default", "reference", "conversation", "listening"}

DEFAULT_VOICES = {
    "en-GB": "bm_george",
}


class VoicePreferenceError(RuntimeError):
    pass


def _preference_path(user_id: str | None = None) -> Path:
    return user_private_dir(user_id) / "preferences" / "voice_profiles.json"


def _migrate_legacy_preferences(target: Path) -> None:
    if target.exists() or not LEGACY_VOICE_PREFERENCES_PATH.exists():
        return
    # The legacy single-user file belongs to the original local owner only.
    if current_user_id() != "local-owner":
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        shutil.copy2(LEGACY_VOICE_PREFERENCES_PATH, target)
    except OSError:
        pass


def _languages() -> list[dict[str, Any]]:
    if not LANGUAGES_PATH.exists():
        return []
    try:
        return json.loads(LANGUAGES_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []


def _default_profile(language_code: str) -> dict[str, Any]:
    default_voice = DEFAULT_VOICES.get(language_code)
    return {
        "engine": "auto",
        "default_voice": default_voice,
        "reference_voice": default_voice,
        "conversation_voice": None,
        "listening_voice": None,
        "speed": 1.0,
    }


def _defaults() -> dict[str, Any]:
    return {
        "version": 1,
        "user_id": current_user_id(),
        "languages": {
            str(language.get("code")): _default_profile(str(language.get("code")))
            for language in _languages()
            if language.get("code")
        },
    }


def load_voice_preferences() -> dict[str, Any]:
    defaults = _defaults()
    path = _preference_path()
    _migrate_legacy_preferences(path)
    if not path.exists():
        return defaults
    try:
        stored = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return defaults

    stored_languages = stored.get("languages") if isinstance(stored, dict) else None
    if not isinstance(stored_languages, dict):
        return defaults

    for code, default_profile in defaults["languages"].items():
        existing = stored_languages.get(code)
        if isinstance(existing, dict):
            default_profile.update({key: existing.get(key) for key in default_profile if key in existing})
    return defaults


def save_voice_preferences(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise VoicePreferenceError("Voice preferences must be an object.")
    incoming_languages = payload.get("languages")
    if not isinstance(incoming_languages, dict):
        raise VoicePreferenceError("Voice preferences must include a languages object.")

    result = load_voice_preferences()
    known_languages = result["languages"]

    for code, incoming in incoming_languages.items():
        if code not in known_languages or not isinstance(incoming, dict):
            continue
        current = known_languages[code]

        engine = str(incoming.get("engine", current.get("engine", "auto"))).strip().lower()
        if engine not in VALID_ENGINES:
            raise VoicePreferenceError(f"Unsupported voice engine: {engine}")
        current["engine"] = engine

        for field in ("default_voice", "reference_voice", "conversation_voice", "listening_voice"):
            value = incoming.get(field, current.get(field))
            if value is None or str(value).strip() == "":
                current[field] = None
            else:
                clean = str(value).strip()
                if len(clean) > 160 or any(char in clean for char in "\r\n\0"):
                    raise VoicePreferenceError("Invalid voice identifier.")
                current[field] = clean

        try:
            speed = float(incoming.get("speed", current.get("speed", 1.0)))
        except (TypeError, ValueError) as exc:
            raise VoicePreferenceError("Voice speed must be a number.") from exc
        current["speed"] = round(max(0.65, min(1.35, speed)), 2)

    path = _preference_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def resolve_voice_profile(language_code: str, purpose: str = "default") -> dict[str, Any]:
    purpose = purpose if purpose in VALID_PURPOSES else "default"
    profiles = load_voice_preferences().get("languages", {})
    profile = dict(profiles.get(language_code) or _default_profile(language_code))

    field = {
        "reference": "reference_voice",
        "conversation": "conversation_voice",
        "listening": "listening_voice",
        "default": "default_voice",
    }[purpose]
    selected = profile.get(field) or profile.get("default_voice")
    profile["selected_voice"] = selected
    profile["purpose"] = purpose
    return profile
