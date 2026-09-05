from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .japanese_service import JapaneseServiceError, romanise_japanese
from .phase2_router import router as phase2_router
from .tts_service import voice_catalog
from .user_router import router as user_router
from .voice_preferences import VoicePreferenceError, load_voice_preferences, save_voice_preferences

# Main app already mounts this router once. Keep /api as the shared root so
# voice settings and the learning modules can evolve without bloating main.py.
router = APIRouter(prefix="/api", tags=["api"])
router.include_router(phase2_router)
router.include_router(user_router)


class VoicePreferencesPayload(BaseModel):
    languages: dict[str, dict[str, Any]] = Field(default_factory=dict)


class JapaneseRomajiPayload(BaseModel):
    texts: list[str] = Field(default_factory=list)


@router.get("/voice/catalog")
def get_voice_catalog() -> dict[str, Any]:
    return voice_catalog()


@router.get("/voice/preferences")
def get_voice_preferences() -> dict[str, Any]:
    return load_voice_preferences()


@router.put("/voice/preferences")
def put_voice_preferences(payload: VoicePreferencesPayload) -> dict[str, Any]:
    try:
        return save_voice_preferences(payload.model_dump())
    except VoicePreferenceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/japanese/romaji")
def japanese_romaji(payload: JapaneseRomajiPayload) -> dict[str, Any]:
    texts = [str(text)[:3000] for text in payload.texts[:12]]
    try:
        return {"ok": True, "romaji": [romanise_japanese(text) for text in texts]}
    except JapaneseServiceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
