from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .db import initialise_database, save_session
from .providers import get_provider_statuses, paid_ai_allowed

ROOT = Path(__file__).resolve().parents[1]
STATIC_DIR = ROOT / "static"
DATA_DIR = ROOT / "data"

load_dotenv(ROOT / ".env")
initialise_database()

app = FastAPI(title="Focuslyra", version="0.1.0")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


class SessionPayload(BaseModel):
    language_code: str | None = None
    mode: str = "study"
    started_at: str | None = None
    writing: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


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
