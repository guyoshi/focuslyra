from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
RECORDINGS_DIR = ROOT / "media" / "recordings"


class AudioServiceError(RuntimeError):
    pass


_WHISPER_MODEL: Any = None
_WHISPER_MODEL_NAME: str | None = None


def _load_whisper_model():
    global _WHISPER_MODEL, _WHISPER_MODEL_NAME
    model_name = os.getenv("WHISPER_MODEL", "small").strip() or "small"
    if _WHISPER_MODEL is not None and _WHISPER_MODEL_NAME == model_name:
        return _WHISPER_MODEL

    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise AudioServiceError(
            "Free local speech transcription is not configured yet. Run configure_free_audio.bat once."
        ) from exc

    device = os.getenv("WHISPER_DEVICE", "cpu").strip() or "cpu"
    compute_type = os.getenv("WHISPER_COMPUTE_TYPE", "int8").strip() or "int8"
    try:
        _WHISPER_MODEL = WhisperModel(model_name, device=device, compute_type=compute_type)
    except Exception as exc:
        raise AudioServiceError(f"Could not load the local Whisper model '{model_name}': {exc}") from exc
    _WHISPER_MODEL_NAME = model_name
    return _WHISPER_MODEL


def audio_status() -> dict[str, Any]:
    try:
        import faster_whisper  # noqa: F401
        package_ready = True
    except ImportError:
        package_ready = False
    return {
        "local_stt_configured": package_ready,
        "model": os.getenv("WHISPER_MODEL", "small").strip() or "small",
        "device": os.getenv("WHISPER_DEVICE", "cpu").strip() or "cpu",
        "cost": "free/local",
        "note": (
            "Local Whisper transcription is available."
            if package_ready
            else "Run configure_free_audio.bat once to enable local transcription."
        ),
    }


def _find_recording(recording_id: str) -> tuple[Path, dict[str, Any]]:
    if not recording_id or any(char not in "0123456789abcdef" for char in recording_id.lower()):
        raise AudioServiceError("Invalid recording id.")

    for metadata_path in RECORDINGS_DIR.glob(f"*/{recording_id}.json"):
        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise AudioServiceError("The recording metadata is damaged.") from exc
        relative = str(metadata.get("relative_audio_path") or "")
        audio_path = ROOT / relative
        if not audio_path.exists():
            raise AudioServiceError("The recording audio file no longer exists.")
        return audio_path, metadata
    raise AudioServiceError("Recording not found.")


def transcribe_recording(recording_id: str, language_hint: str | None = None) -> dict[str, Any]:
    audio_path, metadata = _find_recording(recording_id)
    model = _load_whisper_model()

    # Whisper's language parameter expects a short language code. Leaving it
    # unset is safer for variants such as en-GB/es-ES and lets Whisper detect it.
    hint = None
    if language_hint:
        short = language_hint.split("-")[0].lower()
        if len(short) == 2:
            hint = short

    try:
        segments, info = model.transcribe(
            str(audio_path),
            language=hint,
            beam_size=5,
            vad_filter=True,
            word_timestamps=True,
        )
        segment_list = []
        text_parts = []
        for segment in segments:
            text = (segment.text or "").strip()
            if text:
                text_parts.append(text)
            words = []
            for word in getattr(segment, "words", None) or []:
                words.append(
                    {
                        "word": (word.word or "").strip(),
                        "start": word.start,
                        "end": word.end,
                        "probability": getattr(word, "probability", None),
                    }
                )
            segment_list.append(
                {
                    "start": segment.start,
                    "end": segment.end,
                    "text": text,
                    "words": words,
                }
            )
    except Exception as exc:
        raise AudioServiceError(f"Local transcription failed: {exc}") from exc

    transcript = " ".join(text_parts).strip()
    result = {
        "recording_id": recording_id,
        "language_detected": getattr(info, "language", None),
        "language_probability": getattr(info, "language_probability", None),
        "duration": getattr(info, "duration", None),
        "text": transcript,
        "segments": segment_list,
        "engine": "faster-whisper/local",
        "model": os.getenv("WHISPER_MODEL", "small").strip() or "small",
        "original_metadata": metadata,
    }

    transcript_path = audio_path.with_suffix(".transcript.json")
    transcript_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result
