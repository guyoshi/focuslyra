from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .tts_service import voice_catalog
from .voice_preferences import VoicePreferenceError, load_voice_preferences, save_voice_preferences

router = APIRouter(prefix="/api/voice", tags=["voice"])


class VoicePreferencesPayload(BaseModel):
    languages: dict[str, dict[str, Any]] = Field(default_factory=dict)


@router.get("/catalog")
def get_voice_catalog() -> dict[str, Any]:
    return voice_catalog()


@router.get("/preferences")
def get_voice_preferences() -> dict[str, Any]:
    return load_voice_preferences()


@router.put("/preferences")
def put_voice_preferences(payload: VoicePreferencesPayload) -> dict[str, Any]:
    try:
        return save_voice_preferences(payload.model_dump())
    except VoicePreferenceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
