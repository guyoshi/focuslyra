from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .audio_service import AudioServiceError, transcribe_recording
from .placement_service import PlacementServiceError, assess_level, placement_prompts
from .runtime import current_user_id
from .user_service import UserServiceError, find_user, list_users, select_user

router = APIRouter(tags=["learners"])


class UserSelectionPayload(BaseModel):
    user_id: str


class PlacementTextPayload(BaseModel):
    text: str


@router.get("/users")
def users() -> dict[str, Any]:
    uid = current_user_id()
    try:
        current = find_user(uid)
    except UserServiceError:
        current = {"id": uid, "display_name": uid}
    return {
        "current_user_id": uid,
        "current_display_name": str(current.get("display_name") or uid),
        "users": list_users(),
    }


@router.post("/users/select")
def users_select(payload: UserSelectionPayload) -> dict[str, Any]:
    try:
        selected = select_user(payload.user_id)
    except UserServiceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "user": selected}


@router.get("/placement/{language_code}")
def placement_get(language_code: str) -> dict[str, Any]:
    try:
        return placement_prompts(language_code)
    except PlacementServiceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/placement/{language_code}/text")
def placement_text(language_code: str, payload: PlacementTextPayload) -> dict[str, Any]:
    try:
        return {
            "ok": True,
            "placement": assess_level(language_code, payload.text, "writing"),
        }
    except PlacementServiceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/placement/{language_code}/recording/{recording_id}")
def placement_recording(language_code: str, recording_id: str) -> dict[str, Any]:
    try:
        transcript = transcribe_recording(recording_id)
        placement = assess_level(
            language_code,
            str(transcript.get("text") or ""),
            "speaking",
            transcript_source=str(transcript.get("engine") or "local-whisper"),
        )
        return {"ok": True, "transcript": transcript, "placement": placement}
    except (AudioServiceError, PlacementServiceError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
