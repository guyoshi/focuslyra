from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .activity_engine import ActivityEngineError, generate_activity
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
from .language_service import LanguageServiceError, load_languages, save_language_settings
from .learning_engine import LearningEngineError, analyse_submission
from .profile_service import ProfileServiceError, load_profile, save_profile
from .pronunciation_service import (
    PronunciationServiceError,
    analyse_acoustics,
    assess_pronunciation,
    pronunciation_status,
)
from .providers import get_provider_statuses, paid_ai_allowed
from .runtime import from_storable_path, runtime_config, to_storable_path, user_media_dir
from .session_planner import build_daily_plan
from .source_manager import SourceSyncError, sync_git_source
from .tts_service import (
    TTSServiceError,
    cached_audio_path,
    calibration_prompts,
    synthesise,
    tts_status,
)
from .voice_router import router as voice_router

ROOT = Path(__file__).resolve().parents[1]
STATIC_DIR = ROOT / "static"
DATA_DIR = ROOT / "data"
MAX_RECORDING_BYTES = int(os.getenv("FOCUSLYRA_MAX_RECORDING_MB", "25") or "25") * 1024 * 1024

load_dotenv(ROOT / ".env")
runtime_config().media_root.mkdir(parents=True, exist_ok=True)
initialise_database()

app = FastAPI(title="Focuslyra", version="0.6.0")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
app.include_router(voice_router)


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


class TTSPayload(BaseModel):
    text: str
    language_code: str = "en-GB"
    voice: str | None = None
    speed: float | None = None
    purpose: str = "default"


class StudyActivityPayload(BaseModel):
    id: str = "activity"
    order: int = 1
    language_code: str
    language_name: str | None = None
    flag: str | None = None
    target_variety: str | None = None
    modality: str
    minutes: int = 5
    hidden_targets: list[str] = Field(default_factory=list)
    reason: str | None = None
    stats: dict[str, Any] = Field(default_factory=dict)


class PronunciationAssessmentPayload(BaseModel):
    reference_text: str
    language_code: str
    target_feature: str | None = None


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


def _activity_with_audio(activity: dict[str, Any]) -> dict[str, Any]:
    """Attach persistent local audio when available, without making TTS mandatory."""
    result = dict(activity)
    modality = str(result.get("modality") or "")
    text = ""
    purpose = "default"
    if modality == "listen":
        text = str(result.get("audio_text") or "").strip()
        purpose = "listening"
    elif modality == "pronounce":
        text = str(result.get("reference_text") or "").strip()
        purpose = "reference"

    if not text:
        return result
    try:
        audio = synthesise(text, language_code=str(result.get("language_code") or "en-GB"), purpose=purpose)
        result["audio"] = {"id": audio["id"], "url": f"/api/tts/audio/{audio['id']}", "engine": audio.get("engine")}
    except TTSServiceError as exc:
        result["audio"] = {"id": None, "url": None, "engine": "browser-fallback", "note": str(exc)}
    return result


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
    try:
        return load_profile()
    except ProfileServiceError as exc:
        raise learning_error(exc) from exc


@app.put("/api/profile")
def update_profile(payload: dict[str, Any]) -> Any:
    try:
        return save_profile(payload)
    except ProfileServiceError as exc:
        raise learning_error(exc) from exc


@app.get("/api/languages")
def languages() -> Any:
    try:
        return load_languages()
    except (LanguageServiceError, ProfileServiceError) as exc:
        raise learning_error(exc) from exc


class LanguageSettingsPayload(BaseModel):
    languages: dict[str, dict[str, Any]] = Field(default_factory=dict)


@app.put("/api/languages")
def update_languages(payload: LanguageSettingsPayload) -> Any:
    try:
        return save_language_settings(payload.languages)
    except (LanguageServiceError, ProfileServiceError) as exc:
        raise learning_error(exc) from exc


@app.get("/api/study/today")
def study_today(mode: str = "normal") -> dict[str, Any]:
    mode = "minimum" if mode == "minimum" else "normal"
    try:
        plan = build_daily_plan(mode)
        if not plan.get("activities"):
            raise HTTPException(status_code=404, detail=plan.get("reason") or "No study activity is available.")
        first_slot = plan["activities"][0]
        activity = _activity_with_audio(generate_activity(first_slot))
        language = next((item for item in load_languages() if item.get("code") == first_slot.get("language_code")), None)
        return {
            "plan": plan,
            "activity": activity,
            # Compatibility fields used by older clients while 0.6 rolls out.
            "language": language or first_slot,
            "normal_session_minutes": load_profile().get("normal_session_minutes", 45),
            "minimum_session_minutes": load_profile().get("minimum_session_minutes", 12),
        }
    except (ActivityEngineError, LanguageServiceError, ProfileServiceError) as exc:
        raise learning_error(exc) from exc


@app.post("/api/study/activity")
def study_activity(payload: StudyActivityPayload) -> dict[str, Any]:
    try:
        activity = generate_activity(payload.model_dump())
        return {"ok": True, "activity": _activity_with_audio(activity)}
    except ActivityEngineError as exc:
        raise learning_error(exc) from exc


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


@app.get("/api/tts/status")
def get_tts_status() -> dict[str, Any]:
    return tts_status()


@app.post("/api/tts/generate")
def generate_tts(payload: TTSPayload) -> dict[str, Any]:
    try:
        result = synthesise(
            payload.text,
            language_code=payload.language_code,
            voice=payload.voice,
            speed=payload.speed,
            purpose=payload.purpose,
        )
    except TTSServiceError as exc:
        raise learning_error(exc) from exc
    return {"ok": True, "audio": result, "url": f"/api/tts/audio/{result['id']}"}


@app.get("/api/tts/audio/{audio_id}")
def serve_generated_audio(audio_id: str) -> FileResponse:
    try:
        path = cached_audio_path(audio_id)
    except TTSServiceError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return FileResponse(path, media_type="audio/wav", filename=path.name)


@app.get("/api/tts/calibration-prompts")
def get_tts_calibration_prompts() -> dict[str, Any]:
    status = tts_status()
    return {
        "voices": status.get("british_calibration_voices", []),
        "prompts": calibration_prompts(),
        "warning": "British voice does not automatically mean perfect contemporary RP. Audition before selecting the reference voice.",
    }


@app.get("/api/pronunciation/status")
def get_pronunciation_status() -> dict[str, Any]:
    return pronunciation_status()


@app.post("/api/recordings")
async def save_recording(
    file: UploadFile = File(...),
    language_code: str = Form("unknown"),
    activity: str = Form("speaking"),
    activity_id: str = Form(""),
    reference_text: str = Form(""),
    target_feature: str = Form(""),
) -> dict[str, Any]:
    suffix = Path(file.filename or "recording.webm").suffix.lower()
    if suffix not in {".webm", ".wav", ".mp3", ".m4a", ".ogg"}:
        suffix = ".webm"

    contents = await file.read()
    if len(contents) > MAX_RECORDING_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"Recording is larger than the {MAX_RECORDING_BYTES // (1024 * 1024)}MB limit for a single upload.",
        )

    day_dir = user_media_dir() / "recordings" / datetime.now().strftime("%Y-%m-%d")
    day_dir.mkdir(parents=True, exist_ok=True)

    recording_id = uuid4().hex
    audio_path = day_dir / f"{recording_id}{suffix}"
    metadata_path = day_dir / f"{recording_id}.json"
    audio_path.write_bytes(contents)

    metadata = {
        "id": recording_id,
        "language_code": language_code,
        "activity": activity,
        "activity_id": activity_id or None,
        "reference_text": reference_text or None,
        "target_feature": target_feature or None,
        "created_at": utc_now(),
        "mime_type": file.content_type,
        "original_filename": file.filename,
        "relative_audio_path": to_storable_path(audio_path),
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
            metadata={
                "recording_id": recording_id,
                "activity_id": metadata.get("activity_id"),
                "transcription": {"engine": transcript.get("engine"), "model": transcript.get("model")},
            },
        )

        relative = str(metadata.get("relative_audio_path") or "")
        if relative:
            audio_path = from_storable_path(relative)
            analysis_path = audio_path.with_suffix(".analysis.json")
            analysis_path.write_text(
                json.dumps({"transcript": transcript, "learning": result}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        return {"ok": True, "transcript": transcript, **result}
    except (AudioServiceError, LearningEngineError) as exc:
        raise learning_error(exc) from exc


@app.post("/api/pronunciation/analyse-recording/{recording_id}")
def pronunciation_analyse_recording(recording_id: str) -> dict[str, Any]:
    try:
        return {"ok": True, "acoustics": analyse_acoustics(recording_id)}
    except PronunciationServiceError as exc:
        raise learning_error(exc) from exc


@app.post("/api/pronunciation/assess/{recording_id}")
def pronunciation_assess(recording_id: str, payload: PronunciationAssessmentPayload) -> dict[str, Any]:
    try:
        return {
            "ok": True,
            "assessment": assess_pronunciation(
                recording_id,
                payload.reference_text,
                payload.language_code,
                payload.target_feature,
            ),
        }
    except PronunciationServiceError as exc:
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
