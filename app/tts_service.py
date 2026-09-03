from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
MODEL_DIR = ROOT / "models" / "tts" / "kokoro"
GENERATED_DIR = ROOT / "media" / "generated"
MODEL_PATH = MODEL_DIR / "kokoro-v1.0.onnx"
VOICES_PATH = MODEL_DIR / "voices-v1.0.bin"


class TTSServiceError(RuntimeError):
    pass


_KOKORO: Any = None

# First calibration set. We deliberately do not call these "RP" until Gui
# auditions them. British Kokoro voices are candidates, not automatically a
# perfect contemporary-RP reference.
BRITISH_CALIBRATION_VOICES = ["bf_emma", "bf_isabella", "bm_george", "bm_lewis"]

DEFAULT_VOICES = {
    "en-GB": "bm_george",
}

LANG_MAP = {
    "en-GB": "en-gb",
}


def _load_engine():
    global _KOKORO
    if _KOKORO is not None:
        return _KOKORO
    if not MODEL_PATH.exists() or not VOICES_PATH.exists():
        raise TTSServiceError("Local Kokoro files are missing. Run configure_local_tts.bat once.")
    try:
        from kokoro_onnx import Kokoro
    except ImportError as exc:
        raise TTSServiceError("Local Kokoro TTS is not installed. Run configure_local_tts.bat once.") from exc
    try:
        _KOKORO = Kokoro(str(MODEL_PATH), str(VOICES_PATH))
    except Exception as exc:
        raise TTSServiceError(f"Could not load local Kokoro TTS: {exc}") from exc
    return _KOKORO


def tts_status() -> dict[str, Any]:
    try:
        import kokoro_onnx  # noqa: F401
        package_ready = True
    except ImportError:
        package_ready = False
    files_ready = MODEL_PATH.exists() and VOICES_PATH.exists()
    return {
        "configured": package_ready and files_ready,
        "engine": "kokoro-onnx/local",
        "cost": "free/local",
        "model_ready": MODEL_PATH.exists(),
        "voices_ready": VOICES_PATH.exists(),
        "british_calibration_voices": BRITISH_CALIBRATION_VOICES,
        "note": (
            "Kokoro local TTS is ready."
            if package_ready and files_ready
            else "Run configure_local_tts.bat once to enable persistent local WAV generation."
        ),
    }


def _cache_id(text: str, language_code: str, voice: str, speed: float) -> str:
    payload = json.dumps(
        {"text": text, "language_code": language_code, "voice": voice, "speed": round(speed, 3), "engine": "kokoro-v1.0"},
        ensure_ascii=False,
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]


def synthesise(text: str, language_code: str = "en-GB", voice: str | None = None, speed: float = 1.0) -> dict[str, Any]:
    clean = text.strip()
    if not clean:
        raise TTSServiceError("There is no text to speak.")
    if len(clean) > 1500:
        raise TTSServiceError("This local TTS endpoint currently accepts up to 1500 characters at a time.")

    selected_voice = (voice or DEFAULT_VOICES.get(language_code) or "bm_george").strip()
    lang = LANG_MAP.get(language_code)
    if not lang:
        raise TTSServiceError(
            f"Persistent Kokoro generation is not calibrated for {language_code} yet. Browser TTS remains the fallback."
        )
    speed = max(0.65, min(1.35, float(speed)))
    cache_id = _cache_id(clean, language_code, selected_voice, speed)
    out_dir = GENERATED_DIR / language_code
    out_dir.mkdir(parents=True, exist_ok=True)
    wav_path = out_dir / f"{cache_id}.wav"
    metadata_path = out_dir / f"{cache_id}.json"

    if not wav_path.exists():
        engine = _load_engine()
        try:
            samples, sample_rate = engine.create(clean, voice=selected_voice, speed=speed, lang=lang)
            import soundfile as sf
            sf.write(str(wav_path), samples, sample_rate)
        except Exception as exc:
            raise TTSServiceError(f"Local speech generation failed: {exc}") from exc

    metadata = {
        "id": cache_id,
        "text": clean,
        "language_code": language_code,
        "voice": selected_voice,
        "speed": speed,
        "engine": "kokoro-onnx/local",
        "relative_audio_path": str(wav_path.relative_to(ROOT)).replace("\\", "/"),
        "cached": True,
    }
    metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    return metadata


def cached_audio_path(cache_id: str) -> Path:
    if not cache_id or any(ch not in "0123456789abcdef" for ch in cache_id.lower()):
        raise TTSServiceError("Invalid generated-audio id.")
    for path in GENERATED_DIR.glob(f"*/{cache_id}.wav"):
        return path
    raise TTSServiceError("Generated audio was not found in the local cache.")


def calibration_prompts() -> list[dict[str, str]]:
    return [
        {"id": "bath", "text": "After class, I asked Sarah to pass me the glass by the bath."},
        {"id": "nonrhotic", "text": "The car was parked near the theatre before four."},
        {"id": "weakforms", "text": "I could have gone to the shop, but I was waiting for a friend."},
        {"id": "linking", "text": "The idea is easier after another example."},
        {"id": "thought", "text": "I thought the water ought to be warmer this morning."},
        {"id": "connected", "text": "Would you have told her if you'd known what was going to happen?"},
    ]
