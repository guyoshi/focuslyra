from __future__ import annotations

import os
import re
from contextvars import ContextVar
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

_SAFE_ID = re.compile(r"[^A-Za-z0-9_.-]+")


def _safe_id(value: str) -> str:
    clean = _SAFE_ID.sub("-", (value or "").strip()).strip("-.")
    return clean[:96] or "local-owner"


@dataclass(frozen=True)
class RuntimeConfig:
    """Small deployment seam kept stable as Focuslyra grows.

    Today the app is single-user/local. A future authenticated server can set
    the request user context without rewriting learning/storage services.
    """

    mode: str
    default_user_id: str
    data_root: Path
    private_root: Path
    media_root: Path


def runtime_config() -> RuntimeConfig:
    mode = (os.getenv("FOCUSLYRA_MODE", "personal") or "personal").strip().lower()
    return RuntimeConfig(
        mode=mode,
        default_user_id=_safe_id(os.getenv("FOCUSLYRA_USER_ID", "local-owner")),
        data_root=Path(os.getenv("FOCUSLYRA_DATA_ROOT", str(ROOT / "data"))).resolve(),
        private_root=Path(os.getenv("FOCUSLYRA_PRIVATE_ROOT", str(ROOT / "private"))).resolve(),
        media_root=Path(os.getenv("FOCUSLYRA_MEDIA_ROOT", str(ROOT / "media"))).resolve(),
    )


_USER_CONTEXT: ContextVar[str | None] = ContextVar("focuslyra_user_id", default=None)


def current_user_id() -> str:
    value = _USER_CONTEXT.get()
    return _safe_id(value) if value else runtime_config().default_user_id


def set_current_user_id(user_id: str):
    """Reserved for future authentication middleware/request context."""
    return _USER_CONTEXT.set(_safe_id(user_id))


def reset_current_user_id(token) -> None:
    _USER_CONTEXT.reset(token)


def user_private_dir(user_id: str | None = None) -> Path:
    uid = _safe_id(user_id or current_user_id())
    return runtime_config().private_root / "users" / uid


def user_media_dir(user_id: str | None = None) -> Path:
    uid = _safe_id(user_id or current_user_id())
    return runtime_config().media_root / "users" / uid


def legacy_media_root() -> Path:
    """Flat media layout used before per-user folders existed.

    Kept only so recordings/generated audio created by earlier Focuslyra
    versions are still found. New files are always written under
    ``user_media_dir()``.
    """
    return runtime_config().media_root


def to_storable_path(path: Path) -> str:
    """Serialise a filesystem path for JSON metadata.

    Prefers a path relative to the project root (portable across machines
    for the common default install). Falls back to an absolute path when a
    custom ``FOCUSLYRA_*_ROOT`` points outside the project, which a plain
    relative-to-ROOT path could not represent.
    """
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(resolved)


def from_storable_path(value: str) -> Path:
    """Inverse of :func:`to_storable_path`."""
    candidate = Path(value)
    return candidate if candidate.is_absolute() else (ROOT / candidate)
