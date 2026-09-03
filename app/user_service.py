from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .runtime import current_user_id, set_active_user_id

ROOT = Path(__file__).resolve().parents[1]
USERS_PATH = ROOT / "data" / "users.json"


class UserServiceError(RuntimeError):
    pass


def _load_registry() -> list[dict[str, Any]]:
    try:
        value = json.loads(USERS_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise UserServiceError("User registry could not be loaded.") from exc
    if not isinstance(value, list):
        raise UserServiceError("User registry must be a JSON array.")
    users = [dict(item) for item in value if isinstance(item, dict) and str(item.get("id") or "").strip()]
    if not users:
        raise UserServiceError("User registry is empty.")
    return users


def list_users() -> list[dict[str, Any]]:
    return [
        {
            "id": str(user.get("id")),
            "display_name": str(user.get("display_name") or user.get("id")),
            "default": bool(user.get("default", False)),
        }
        for user in _load_registry()
    ]


def find_user(user_id: str | None = None) -> dict[str, Any]:
    uid = str(user_id or current_user_id()).strip()
    for user in _load_registry():
        if str(user.get("id")) == uid:
            return user
    raise UserServiceError(f"Unknown Focuslyra user: {uid}")


def default_user_id() -> str:
    users = _load_registry()
    preferred = next((item for item in users if item.get("default")), users[0])
    return str(preferred.get("id"))


def profile_defaults(user_id: str | None = None) -> dict[str, Any]:
    user = find_user(user_id)
    value = user.get("profile")
    return dict(value) if isinstance(value, dict) else {}


def select_user(user_id: str) -> dict[str, Any]:
    user = find_user(user_id)
    set_active_user_id(str(user.get("id")))
    return {
        "id": str(user.get("id")),
        "display_name": str(user.get("display_name") or user.get("id")),
    }
