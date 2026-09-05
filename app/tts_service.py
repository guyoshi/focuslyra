from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .runtime import legacy_media_root, to_storable_path, user_media_dir
from .voice_preferences import resolve_voice_profile

ROOT = Path(__file__).resolve().parents[1]
MODEL_DIR = ROOT / "models" / "tts" / "kokoro"
MODEL_PATH = MODEL_DIR / "kokoro-v1.0.onnx"
VOICES_PATH = MODEL_DIR / "voices-v1.0.bin"


def _generated_dirs() -> list[Path]:
    """User-scoped generated audio first, then the pre-multiuser flat layout."""
    return [user_media_dir() / "generated", legacy_media_root() / "generated"]


class TTSServiceError(RuntimeError):
    pass


_KOKORO: Any = None
_JAPANESE_G2P: Any = None

BRITISH_CALIBRATION_VOICES = ["bf_emma", "bf_isabella", "bm_george", "bm_lewis"]

# Preferred starting points only. The settings screen can replace every one.
DEFAULT_VOICES = {
    "en-GB": "bm_george",
    "es-ES": "ef_dora",
    "fr-FR": "ff_siwis",
    "it-IT": "if_sara",
    "ja-JP": "jf_alpha",
}

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


def _load_japanese_g2p():
    """Use Misaki's Japanese G2P explicitly instead of letting a generic
    tokenizer guess how kanji/kana should be read.

    Kokoro's Japanese voices expect Japanese phonemes. Passing raw Japanese
    directly through a generic multilingual path can produce bizarre spoken
    labels or wrong kanji readings, so Japanese is phonemised before synthesis.
    """
    global _JAPANESE_G2P
    if _JAPANESE_G2P is not None:
        return _JAPANESE_G2P
    try:
        from misaki import ja
    except ImportError as exc:
        raise TTSServiceError(
            "Japanese Kokoro phonemisation is missing. Run configure_local_tts.bat again after updating Focuslyra."
        ) from exc
    try:
        _JAPANESE_G2P = ja.JAG2P()
    except Exception as exc:
        raise TTSServiceError(f"Could not initialise Japanese pronunciation support: {exc}") from exc
    return _JAPANESE_G2P


def _japanese_g2p_ready() -> bool:
    try:
        _load_japanese_g2p()
        return True
    except TTSServiceError:
        return False


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


def voices_for_language(language_code: str) -> list[str]:
    prefixes = VOICE_PREFIXES.get(language_code, ())
    if not prefixes:
        return []
    return [voice for voice in available_kokoro_voices() if voice.startswith(prefixes)]


def _automatic_voice(language_code: str) -> str | None:
    candidates = voices_for_language(language_code)
    preferred = DEFAULT_VOICES.get(language_code)
    if preferred and (not candidates or preferred in candidates):
        return preferred
    return candidates[0] if candidates else preferred


def voice_catalog() -> dict[str, Any]:
    languages: dict[str, Any] = {}
    for language_code in VOICE_PREFIXES:
        languages[language_code] = {
            "kokoro_supported": language_code in LANG_MAP,
            "kokoro_voices": voices_for_language(language_code),
            "browser_supported": True,
        }
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
        "japanese_g2p_ready": _japanese_g2p_ready() if ready else False,
        "supported_languages": sorted(LANG_MAP.keys()),
        "british_calibration_voices": BRITISH_CALIBRATION_VOICES,
        "note": (
            "Kokoro local TTS is ready."
            if ready
            else "Run configure_local_tts.bat once to enable persistent local WAV generation."
        ),
    }


def _cache_id(text: str, language_code: str, voice: str, speed: float) -> str:
    # Japanese cache version is deliberately distinct because Japanese now uses
    # explicit Misaki G2P. This prevents old incorrectly-pronounced WAV files
    # from surviving after the pronunciation fix.
    engine_variant = "kokoro-v1.0-ja-misaki-v1" if language_code == "ja-JP" else "kokoro-v1.0"
    payload = json.dumps(
        {"text": text, "language_code": language_code, "voice": voice, "speed": round(speed, 3), "engine": engine_variant},
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

    selected_voice = str(voice or profile.get("selected_voice") or _automatic_voice(language_code) or "").strip()
    if not selected_voice:
        raise TTSServiceError(f"No compatible local voice is installed for {language_code}.")

    lang = LANG_MAP.get(language_code)
    if not lang:
        raise TTSServiceError(
            f"Persistent Kokoro generation is not available for {language_code}. Browser/system TTS remains available."
        )

    if speed is None:
        speed = float(profile.get("speed") or 1.0)
    speed = max(0.65, min(1.35, float(speed)))

    known_for_language = voices_for_language(language_code)
    if known_for_language and selected_voice not in known_for_language:
        raise TTSServiceError(
            f"The selected voice '{selected_voice}' is not a compatible Kokoro voice for {language_code}."
        )

    cache_id = _cache_id(clean, language_code, selected_voice, speed)
    out_dir = user_media_dir() / "generated" / language_code
    out_dir.mkdir(parents=True, exist_ok=True)
    wav_path = out_dir / f"{cache_id}.wav"
    metadata_path = out_dir / f"{cache_id}.json"

    if not wav_path.exists():
        engine = _load_engine()
        try:
            if language_code == "ja-JP":
                phonemes, _ = _load_japanese_g2p()(clean)
                if not str(phonemes or "").strip():
                    raise TTSServiceError("Japanese phonemisation returned no readable sounds.")
                samples, sample_rate = engine.create(
                    phonemes,
                    voice=selected_voice,
                    speed=speed,
                    is_phonemes=True,
                )
            else:
                samples, sample_rate = engine.create(clean, voice=selected_voice, speed=speed, lang=lang)
            import soundfile as sf
            sf.write(str(wav_path), samples, sample_rate)
        except TTSServiceError:
            raise
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
        "relative_audio_path": to_storable_path(wav_path),
        "cached": True,
    }
    metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    return metadata


def cached_audio_path(cache_id: str) -> Path:
    if not cache_id or any(ch not in "0123456789abcdef" for ch in cache_id.lower()):
        raise TTSServiceError("Invalid generated-audio id.")
    for generated_dir in _generated_dirs():
        for path in generated_dir.glob(f"*/{cache_id}.wav"):
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
