from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .runtime import current_user_id, user_private_dir

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PROFILE_PATH = ROOT / "data" / "profile.json"


class ProfileServiceError(RuntimeError):
    pass


def _profile_path(user_id: str | None = None) -> Path:
    return user_private_dir(user_id) / "learner" / "profile.json"


def _read_profile(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ProfileServiceError("Learner profile could not be loaded.") from exc
    if not isinstance(value, dict):
        raise ProfileServiceError("Learner profile must be a JSON object.")
    return value


def _merge_defaults(defaults: dict[str, Any], stored: dict[str, Any]) -> dict[str, Any]:
    """Merge missing schema/default fields without overwriting learner choices."""
    result = dict(defaults)
    for key, value in stored.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            nested = dict(result[key])
            nested.update(value)
            result[key] = nested
        else:
            result[key] = value
    return result


def load_profile(user_id: str | None = None) -> dict[str, Any]:
    defaults = _read_profile(DEFAULT_PROFILE_PATH)
    path = _profile_path(user_id)
    stored = _read_profile(path) if path.exists() else {}
    result = _merge_defaults(defaults, stored)
    result["user_id"] = user_id or current_user_id()
    return result


def save_profile(payload: dict[str, Any], user_id: str | None = None) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ProfileServiceError("Learner profile must be an object.")
    clean = dict(payload)
    clean.pop("user_id", None)
    path = _profile_path(user_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(clean, ensure_ascii=False, indent=2), encoding="utf-8")
    return load_profile(user_id)
