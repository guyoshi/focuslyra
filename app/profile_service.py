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


def load_profile(user_id: str | None = None) -> dict[str, Any]:
    path = _profile_path(user_id)
    source = path if path.exists() else DEFAULT_PROFILE_PATH
    try:
        value = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ProfileServiceError("Learner profile could not be loaded.") from exc
    if not isinstance(value, dict):
        raise ProfileServiceError("Learner profile must be a JSON object.")
    result = dict(value)
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
