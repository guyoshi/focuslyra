from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .runtime import from_storable_path, legacy_media_root, user_media_dir

ROOT = Path(__file__).resolve().parents[1]


def _recording_dirs() -> list[Path]:
    """User-scoped recordings first, then the pre-multiuser flat layout."""
    return [user_media_dir() / "recordings", legacy_media_root() / "recordings"]


class PronunciationServiceError(RuntimeError):
    pass


def pronunciation_status() -> dict[str, Any]:
    try:
        import parselmouth  # noqa: F401
        ready = True
    except ImportError:
        ready = False
    return {
        "configured": ready,
        "engine": "praat-parselmouth/local",
        "cost": "free/local",
        "scope": "acoustic-baseline",
        "note": (
            "Acoustic pronunciation baseline is ready. Phoneme alignment/calibration is a separate layer."
            if ready
            else "Run configure_pronunciation.bat once to enable local acoustic measurements."
        ),
    }


def _find_recording(recording_id: str) -> tuple[Path, dict[str, Any]]:
    if not recording_id or any(ch not in "0123456789abcdef" for ch in recording_id.lower()):
        raise PronunciationServiceError("Invalid recording id.")
    for recordings_dir in _recording_dirs():
        for metadata_path in recordings_dir.glob(f"*/{recording_id}.json"):
            try:
                metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise PronunciationServiceError("Recording metadata is damaged.") from exc
            audio_path = from_storable_path(str(metadata.get("relative_audio_path") or ""))
            if not audio_path.exists():
                raise PronunciationServiceError("Recording audio file is missing.")
            return audio_path, metadata
    raise PronunciationServiceError("Recording not found.")


def _to_analysis_wav(audio_path: Path) -> Path:
    target = audio_path.with_suffix(".acoustic.wav")
    if target.exists():
        return target
    try:
        import av
        import numpy as np
        import soundfile as sf
    except ImportError as exc:
        raise PronunciationServiceError("Pronunciation dependencies are missing. Run configure_pronunciation.bat once.") from exc

    chunks = []
    try:
        container = av.open(str(audio_path))
        stream = next((s for s in container.streams if s.type == "audio"), None)
        if stream is None:
            raise PronunciationServiceError("No audio stream was found in the recording.")
        resampler = av.audio.resampler.AudioResampler(format="fltp", layout="mono", rate=16000)
        for frame in container.decode(stream):
            converted = resampler.resample(frame)
            if not isinstance(converted, list):
                converted = [converted]
            for out in converted:
                if out is None:
                    continue
                arr = out.to_ndarray()
                chunks.append(arr.reshape(-1))
        container.close()
    except PronunciationServiceError:
        raise
    except Exception as exc:
        raise PronunciationServiceError(f"Could not decode recording for acoustic analysis: {exc}") from exc

    if not chunks:
        raise PronunciationServiceError("The recording contained no decodable speech samples.")
    audio = np.concatenate(chunks).astype("float32", copy=False)
    sf.write(str(target), audio, 16000, subtype="PCM_16")
    return target


def analyse_acoustics(recording_id: str) -> dict[str, Any]:
    audio_path, metadata = _find_recording(recording_id)
    wav_path = _to_analysis_wav(audio_path)
    try:
        import numpy as np
        import parselmouth
    except ImportError as exc:
        raise PronunciationServiceError("Pronunciation dependencies are missing. Run configure_pronunciation.bat once.") from exc

    try:
        sound = parselmouth.Sound(str(wav_path))
        duration = float(sound.get_total_duration())
        pitch = sound.to_pitch(time_step=0.01, pitch_floor=60.0, pitch_ceiling=500.0)
        frequencies = pitch.selected_array["frequency"]
        voiced = frequencies[frequencies > 0]
        intensity = sound.to_intensity(time_step=0.01)
        intensity_values = intensity.values.reshape(-1)
        finite_intensity = intensity_values[np.isfinite(intensity_values)]

        result = {
            "recording_id": recording_id,
            "engine": "praat-parselmouth/local",
            "scope": "acoustic-baseline",
            "duration_seconds": round(duration, 3),
            "pitch": {
                "voiced_frame_ratio": round(float(len(voiced) / max(1, len(frequencies))), 4),
                "mean_hz": round(float(np.mean(voiced)), 2) if len(voiced) else None,
                "min_hz": round(float(np.min(voiced)), 2) if len(voiced) else None,
                "max_hz": round(float(np.max(voiced)), 2) if len(voiced) else None,
            },
            "intensity": {
                "mean_db": round(float(np.mean(finite_intensity)), 2) if len(finite_intensity) else None,
                "min_db": round(float(np.min(finite_intensity)), 2) if len(finite_intensity) else None,
                "max_db": round(float(np.max(finite_intensity)), 2) if len(finite_intensity) else None,
            },
            "language_code": metadata.get("language_code"),
            "warning": (
                "These are real acoustic measurements, but they are not yet a phoneme-accuracy or accent score. "
                "Focuslyra will add target-specific alignment/calibration before judging individual sounds."
            ),
        }
    except Exception as exc:
        raise PronunciationServiceError(f"Acoustic analysis failed: {exc}") from exc

    output = audio_path.with_suffix(".acoustic.json")
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result
