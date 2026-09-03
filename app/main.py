from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .audio_service import AudioServiceError, audio_status, transcribe_recording
from .calendar_service import (
    CalendarIntegrationError,
    connect_google_calendar,
    create_study_event,
    disconnect_google_calendar,
    find_free_slots,
    get_calendar_status,
    list_calendars,
    save_client_credentials,
    set_availability_calendars,
    smart_schedule,
    upcoming_focuslyra_events,
)
from .db import initialise_database, save_session
from .learning_engine import LearningEngineError, analyse_submission
from .providers import get_provider_statuses, paid_ai_allowed
from .source_manager import SourceSyncError, sync_git_source

ROOT = Path(__file__).resolve().parents[1]
STATIC_DIR = ROOT / "static"
DATA_DIR = ROOT / "data"
MEDIA_DIR = ROOT / "media"
RECORDINGS_DIR = MEDIA_DIR / "recordings"

load_dotenv(ROOT / ".env")
RECORDINGS_DIR.mkdir(parents=True, exist_ok=True)
initialise_database()

app = FastAPI(title="Focuslyra", version="0.3.0")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


class SessionPayload(BaseModel):
    language_code: str | None = None
    mode: str = "study"
    started_at: str | None = None
    writing: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class LearningTextPayload(BaseModel):
    language_code: str
    modality: str = "writing"
    text: str
    exercise_prompt: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class CalendarSelectionPayload(BaseModel):
    calendar_ids: list[str] = Field(default_factory=list)


class CalendarStudyEventPayload(BaseModel):
    start: str
    duration_minutes: int = 45
    summary: str = "🌍 Focuslyra — Language study"
    description: str = "Adaptive language-study session scheduled by Focuslyra."


class CalendarSmartSchedulePayload(BaseModel):
    target_date: str
    duration_minutes: int = 45
    window_start: str = "08:00"
    window_end: str = "19:00"
    summary: str = "🌍 Focuslyra — Language study"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_json(name: str) -> Any:
    path = DATA_DIR / name
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Missing data file: {name}")
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def calendar_error(exc: CalendarIntegrationError) -> HTTPException:
    return HTTPException(status_code=400, detail=str(exc))


def learning_error(exc: Exception) -> HTTPException:
    return HTTPException(status_code=400, detail=str(exc))


@app.get("/", response_class=HTMLResponse)
def index() -> HTMLResponse:
    html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
    learning_script = '<script src="/static/learning.js" defer></script>'
    if learning_script not in html:
        html = html.replace("</body>", f"  {learning_script}\n</body>")
    return HTMLResponse(html)


@app.get("/api/health")
def health() -> dict[str, Any]:
    return {
        "ok": True,
        "name": "Focuslyra",
        "version": app.version,
        "paid_ai_allowed": paid_ai_allowed(),
        "host": os.getenv("FOCUSLYRA_HOST", "127.0.0.1"),
    }


@app.get("/api/profile")
def profile() -> Any:
    return load_json("profile.json")


@app.get("/api/languages")
def languages() -> Any:
    return load_json("languages.json")


@app.get("/api/sources")
def sources() -> Any:
    return load_json("sources.json")


@app.post("/api/sources/{source_id}/sync")
def sync_source(source_id: str) -> dict[str, Any]:
    try:
        result = sync_git_source(source_id)
    except SourceSyncError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "source": result}


@app.get("/api/providers")
def providers() -> list[dict]:
    return get_provider_statuses()


@app.post("/api/sessions")
def create_session(payload: SessionPayload) -> dict[str, Any]:
    session_id = save_session(payload.model_dump())
    return {"ok": True, "session_id": session_id}


@app.post("/api/learning/analyse-text")
def learning_analyse_text(payload: LearningTextPayload) -> dict[str, Any]:
    try:
        return {
            "ok": True,
            **analyse_submission(
                language_code=payload.language_code,
                modality=payload.modality,
                learner_text=payload.text,
                exercise_prompt=payload.exercise_prompt,
                metadata=payload.metadata,
            ),
        }
    except LearningEngineError as exc:
        raise learning_error(exc) from exc


@app.get("/api/audio/status")
def get_audio_status() -> dict[str, Any]:
    return audio_status()


@app.post("/api/recordings")
async def save_recording(
    file: UploadFile = File(...),
    language_code: str = Form("unknown"),
    activity: str = Form("speaking"),
) -> dict[str, Any]:
    suffix = Path(file.filename or "recording.webm").suffix.lower()
    if suffix not in {".webm", ".wav", ".mp3", ".m4a", ".ogg"}:
        suffix = ".webm"

    day_dir = RECORDINGS_DIR / datetime.now().strftime("%Y-%m-%d")
    day_dir.mkdir(parents=True, exist_ok=True)

    recording_id = uuid4().hex
    audio_path = day_dir / f"{recording_id}{suffix}"
    metadata_path = day_dir / f"{recording_id}.json"

    contents = await file.read()
    audio_path.write_bytes(contents)

    metadata = {
        "id": recording_id,
        "language_code": language_code,
        "activity": activity,
        "created_at": utc_now(),
        "mime_type": file.content_type,
        "original_filename": file.filename,
        "relative_audio_path": str(audio_path.relative_to(ROOT)).replace("\\", "/"),
    }
    metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")

    return {"ok": True, "recording": metadata}


@app.post("/api/learning/analyse-recording/{recording_id}")
def learning_analyse_recording(recording_id: str) -> dict[str, Any]:
    try:
        transcript = transcribe_recording(recording_id)
        metadata = transcript.get("original_metadata") or {}
        language_code = str(metadata.get("language_code") or "unknown")
        activity = str(metadata.get("activity") or "speaking")
        result = analyse_submission(
            language_code=language_code,
            modality="speech-transcript",
            learner_text=str(transcript.get("text") or ""),
            exercise_prompt=activity,
            transcript_source="local-whisper",
            metadata={"recording_id": recording_id, "transcription": {"engine": transcript.get("engine"), "model": transcript.get("model")}},
        )

        relative = str(metadata.get("relative_audio_path") or "")
        if relative:
            audio_path = ROOT / relative
            analysis_path = audio_path.with_suffix(".analysis.json")
            analysis_path.write_text(
                json.dumps({"transcript": transcript, "learning": result}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        return {"ok": True, "transcript": transcript, **result}
    except (AudioServiceError, LearningEngineError) as exc:
        raise learning_error(exc) from exc


@app.get("/api/calendar/status")
def calendar_status() -> dict[str, Any]:
    return get_calendar_status()


@app.post("/api/calendar/credentials")
async def calendar_credentials(file: UploadFile = File(...)) -> dict[str, Any]:
    try:
        result = save_client_credentials(await file.read())
    except CalendarIntegrationError as exc:
        raise calendar_error(exc) from exc
    return {"ok": True, **result}


@app.post("/api/calendar/connect")
def calendar_connect() -> dict[str, Any]:
    try:
        result = connect_google_calendar()
    except CalendarIntegrationError as exc:
        raise calendar_error(exc) from exc
    return {"ok": True, **result}


@app.post("/api/calendar/disconnect")
def calendar_disconnect() -> dict[str, Any]:
    disconnect_google_calendar()
    return {"ok": True, "connected": False}


@app.get("/api/calendar/calendars")
def calendar_list() -> list[dict[str, Any]]:
    try:
        return list_calendars()
    except CalendarIntegrationError as exc:
        raise calendar_error(exc) from exc


@app.post("/api/calendar/availability-calendars")
def calendar_availability_calendars(payload: CalendarSelectionPayload) -> dict[str, Any]:
    try:
        selected = set_availability_calendars(payload.calendar_ids)
    except CalendarIntegrationError as exc:
        raise calendar_error(exc) from exc
    return {"ok": True, "calendar_ids": selected}


@app.get("/api/calendar/free-slots")
def calendar_free_slots(
    target_date: str,
    duration_minutes: int = 45,
    window_start: str = "08:00",
    window_end: str = "19:00",
) -> dict[str, Any]:
    try:
        return find_free_slots(target_date, duration_minutes, window_start, window_end)
    except CalendarIntegrationError as exc:
        raise calendar_error(exc) from exc


@app.post("/api/calendar/study-events")
def calendar_create_study_event(payload: CalendarStudyEventPayload) -> dict[str, Any]:
    try:
        event = create_study_event(
            payload.start,
            duration_minutes=payload.duration_minutes,
            summary=payload.summary,
            description=payload.description,
        )
    except CalendarIntegrationError as exc:
        raise calendar_error(exc) from exc
    return {"ok": True, "event": event}


@app.post("/api/calendar/study-events/smart")
def calendar_smart_schedule(payload: CalendarSmartSchedulePayload) -> dict[str, Any]:
    try:
        result = smart_schedule(
            payload.target_date,
            duration_minutes=payload.duration_minutes,
            window_start=payload.window_start,
            window_end=payload.window_end,
            summary=payload.summary,
        )
    except CalendarIntegrationError as exc:
        raise calendar_error(exc) from exc
    return {"ok": True, **result}


@app.get("/api/calendar/upcoming")
def calendar_upcoming(max_results: int = 10) -> list[dict[str, Any]]:
    try:
        return upcoming_focuslyra_events(max_results=max_results)
    except CalendarIntegrationError as exc:
        raise calendar_error(exc) from exc
