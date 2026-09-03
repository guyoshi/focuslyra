from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .voice_preferences import resolve_voice_profile

ROOT = Path(__file__).resolve().parents[1]
MODEL_DIR = ROOT / "models" / "tts" / "kokoro"
GENERATED_DIR = ROOT / "media" / "generated"
MODEL_PATH = MODEL_DIR / "kokoro-v1.0.onnx"
VOICES_PATH = MODEL_DIR / "voices-v1.0.bin"


class TTSServiceError(RuntimeError):
    pass


_KOKORO: Any = None

# British candidates for the first English calibration. They are deliberately
# not labelled as definitive RP until the learner auditions them.
BRITISH_CALIBRATION_VOICES = ["bf_emma", "bf_isabella", "bm_george", "bm_lewis"]

DEFAULT_VOICES = {
    "en-GB": "bm_george",
}

# Kokoro's language argument and voice prefixes. Unsupported languages stay
# fully usable through the browser/system voice fallback.
LANG_MAP = {
    "en-GB": "en-gb",
    "es-ES": "es",
    "fr-FR": "fr-fr",
    "it-IT": "it",
    "ja-JP": "ja",
}

VOICE_PREFIXES = {
    "en-GB": ("bf_", "bm_"),
    "es-ES": ("ef_", "em_"),
    "fr-FR": ("ff_", "fm_"),
    "it-IT": ("if_", "im_"),
    "ja-JP": ("jf_", "jm_"),
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


def _kokoro_ready() -> bool:
    try:
        import kokoro_onnx  # noqa: F401
        package_ready = True
    except ImportError:
        package_ready = False
    return package_ready and MODEL_PATH.exists() and VOICES_PATH.exists()


def available_kokoro_voices() -> list[str]:
    if not _kokoro_ready():
        return []
    try:
        return sorted(str(voice) for voice in _load_engine().get_voices())
    except Exception:
        return []


def voice_catalog() -> dict[str, Any]:
    all_voices = available_kokoro_voices()
    languages: dict[str, Any] = {}
    for language_code, prefixes in VOICE_PREFIXES.items():
        languages[language_code] = {
            "kokoro_supported": language_code in LANG_MAP,
            "kokoro_voices": [voice for voice in all_voices if voice.startswith(prefixes)],
            "browser_supported": True,
        }
    # Languages currently studied but not supported by Kokoro still appear so
    # the UI can offer browser/system voices now and future providers later.
    for language_code in ("ar", "de-DE"):
        languages.setdefault(
            language_code,
            {"kokoro_supported": False, "kokoro_voices": [], "browser_supported": True},
        )
    return {
        "engines": [
            {"id": "auto", "label": "Auto (best available)"},
            {"id": "kokoro", "label": "Kokoro local"},
            {"id": "browser", "label": "Browser / system voice"},
        ],
        "languages": languages,
    }


def tts_status() -> dict[str, Any]:
    ready = _kokoro_ready()
    return {
        "configured": ready,
        "engine": "kokoro-onnx/local",
        "cost": "free/local",
        "model_ready": MODEL_PATH.exists(),
        "voices_ready": VOICES_PATH.exists(),
        "supported_languages": sorted(LANG_MAP.keys()),
        "british_calibration_voices": BRITISH_CALIBRATION_VOICES,
        "note": (
            "Kokoro local TTS is ready."
            if ready
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


def synthesise(
    text: str,
    language_code: str = "en-GB",
    voice: str | None = None,
    speed: float | None = None,
    purpose: str = "default",
) -> dict[str, Any]:
    clean = text.strip()
    if not clean:
        raise TTSServiceError("There is no text to speak.")
    if len(clean) > 1500:
        raise TTSServiceError("This local TTS endpoint currently accepts up to 1500 characters at a time.")

    profile = resolve_voice_profile(language_code, purpose)
    if profile.get("engine") == "browser":
        raise TTSServiceError("This language is configured to use the browser/system voice.")

    selected_voice = (voice or profile.get("selected_voice") or DEFAULT_VOICES.get(language_code) or "bm_george").strip()
    lang = LANG_MAP.get(language_code)
    if not lang:
        raise TTSServiceError(
            f"Persistent Kokoro generation is not available for {language_code}. Browser/system TTS remains available."
        )

    if speed is None:
        speed = float(profile.get("speed") or 1.0)
    speed = max(0.65, min(1.35, float(speed)))

    known = available_kokoro_voices()
    if known and selected_voice not in known:
        raise TTSServiceError(f"The selected Kokoro voice '{selected_voice}' is not installed in this voice pack.")

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
        "purpose": purpose,
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
