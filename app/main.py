from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .db import initialise_database, save_session
from .providers import get_provider_statuses, paid_ai_allowed

ROOT = Path(__file__).resolve().parents[1]
STATIC_DIR = ROOT / "static"
DATA_DIR = ROOT / "data"
MEDIA_DIR = ROOT / "media"
RECORDINGS_DIR = MEDIA_DIR / "recordings"

load_dotenv(ROOT / ".env")
RECORDINGS_DIR.mkdir(parents=True, exist_ok=True)
initialise_database()

app = FastAPI(title="Focuslyra", version="0.1.0")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


class SessionPayload(BaseModel):
    language_code: str | None = None
    mode: str = "study"
    started_at: str | None = None
    writing: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_json(name: str) -> Any:
    path = DATA_DIR / name
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Missing data file: {name}")
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/health")
def health() -> dict[str, Any]:
    return {
        "ok": True,
        "name": "Focuslyra",
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


@app.get("/api/providers")
def providers() -> list[dict]:
    return get_provider_statuses()


@app.post("/api/sessions")
def create_session(payload: SessionPayload) -> dict[str, Any]:
    session_id = save_session(payload.model_dump())
    return {"ok": True, "session_id": session_id}


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
