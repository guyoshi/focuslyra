from __future__ import annotations

import json
import math
import re
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from .audio_service import transcribe_recording
from .db import save_learning_feedback, save_session
from .runtime import from_storable_path, legacy_media_root, user_media_dir
from .tts_service import cached_audio_path, synthesise

ROOT = Path(__file__).resolve().parents[1]


def _recording_dirs() -> list[Path]:
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
        "scope": "controlled-reference-v1" if ready else "not-configured",
        "capabilities": [
            "real acoustic measurements",
            "controlled sentence intelligibility",
            "timing comparison",
            "pitch-contour/prosody comparison",
            "rhythm/voicing comparison",
        ] if ready else [],
        "phoneme_alignment": False,
        "note": (
            "Controlled pronunciation assessment is ready. Exact phoneme-by-phoneme scoring still requires alignment/calibration."
            if ready
            else "Run configure_pronunciation.bat once to enable local pronunciation measurements."
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
    if audio_path.suffix.lower() == ".wav":
        return audio_path
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
                chunks.append(out.to_ndarray().reshape(-1))
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


def _contour(values, points: int = 64):
    import numpy as np

    arr = np.asarray(values, dtype=float)
    good = np.isfinite(arr) & (arr > 0)
    if int(good.sum()) < 4:
        return None
    x = np.arange(len(arr), dtype=float)
    filled = np.interp(x, x[good], arr[good])
    sample_x = np.linspace(0, len(filled) - 1, points)
    sampled = np.interp(sample_x, x, filled)
    std = float(np.std(sampled))
    if std < 1e-6:
        return None
    return (sampled - float(np.mean(sampled))) / std


def _measure_path(audio_path: Path) -> dict[str, Any]:
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
        contour = _contour(frequencies)

        if len(finite_intensity):
            mean_db = float(np.mean(finite_intensity))
            silence_threshold = mean_db - 14.0
            quiet_ratio = float(np.mean(finite_intensity < silence_threshold))
        else:
            mean_db = None
            quiet_ratio = 0.0

        if len(voiced) >= 4:
            p10, p90 = np.percentile(voiced, [10, 90])
            pitch_range_st = 12.0 * math.log2(float(p90) / float(p10)) if p10 > 0 else None
        else:
            pitch_range_st = None

        return {
            "duration_seconds": round(duration, 3),
            "voiced_frame_ratio": round(float(len(voiced) / max(1, len(frequencies))), 4),
            "quiet_frame_ratio": round(quiet_ratio, 4),
            "pitch_mean_hz": round(float(np.mean(voiced)), 2) if len(voiced) else None,
            "pitch_min_hz": round(float(np.min(voiced)), 2) if len(voiced) else None,
            "pitch_max_hz": round(float(np.max(voiced)), 2) if len(voiced) else None,
            "pitch_range_semitones": round(float(pitch_range_st), 2) if pitch_range_st is not None else None,
            "intensity_mean_db": round(mean_db, 2) if mean_db is not None else None,
            "pitch_contour": contour.tolist() if contour is not None else None,
        }
    except Exception as exc:
        raise PronunciationServiceError(f"Acoustic analysis failed: {exc}") from exc


def analyse_acoustics(recording_id: str) -> dict[str, Any]:
    audio_path, metadata = _find_recording(recording_id)
    features = _measure_path(audio_path)
    result = {
        "recording_id": recording_id,
        "engine": "praat-parselmouth/local",
        "scope": "acoustic-baseline",
        "language_code": metadata.get("language_code"),
        **{key: value for key, value in features.items() if key != "pitch_contour"},
        "warning": "These are real acoustic measurements, not an exact phoneme or accent score.",
    }
    output = audio_path.with_suffix(".acoustic.json")
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def _normalised_words(text: str) -> list[str]:
    return re.findall(r"[^\W_]+(?:['’][^\W_]+)?", text.lower(), flags=re.UNICODE)


def _similarity(expected: str, heard: str) -> float:
    a = _normalised_words(expected)
    b = _normalised_words(heard)
    if not a:
        return 0.0
    return SequenceMatcher(None, a, b).ratio() * 100.0


def _ratio_score(a: float, b: float) -> float:
    if a <= 0 or b <= 0:
        return 0.0
    ratio = a / b
    return max(0.0, min(100.0, 100.0 * math.exp(-abs(math.log(ratio)) * 1.45)))


def _contour_score(a: list[float] | None, b: list[float] | None) -> float | None:
    if not a or not b:
        return None
    try:
        import numpy as np
        aa = np.asarray(a, dtype=float)
        bb = np.asarray(b, dtype=float)
        if len(aa) != len(bb) or len(aa) < 4:
            return None
        corr = float(np.corrcoef(aa, bb)[0, 1])
        if not math.isfinite(corr):
            return None
        # Shape similarity only. Different speaker pitch ranges are normal.
        return max(0.0, min(100.0, (corr + 1.0) * 50.0))
    except Exception:
        return None


def assess_pronunciation(
    recording_id: str,
    reference_text: str,
    language_code: str,
    target_feature: str | None = None,
) -> dict[str, Any]:
    """Assess controlled production against a known reference sentence.

    V1 deliberately scores intelligibility, timing, rhythm and broad prosody.
    It does NOT pretend to know exact phoneme accuracy until a forced-alignment
    layer and language-specific calibration data are added.
    """
    clean_reference = reference_text.strip()
    if not clean_reference:
        raise PronunciationServiceError("A known reference sentence is required for pronunciation assessment.")

    learner_path, metadata = _find_recording(recording_id)
    learner_features = _measure_path(learner_path)

    try:
        transcript = transcribe_recording(recording_id, language_hint=language_code)
    except Exception as exc:
        raise PronunciationServiceError(f"Could not transcribe the controlled pronunciation attempt: {exc}") from exc

    try:
        reference_audio = synthesise(clean_reference, language_code=language_code, purpose="reference")
        reference_path = cached_audio_path(str(reference_audio["id"]))
        reference_features = _measure_path(reference_path)
    except Exception as exc:
        raise PronunciationServiceError(
            "A local reference voice is required for controlled pronunciation comparison. "
            f"Configure local TTS first. Details: {exc}"
        ) from exc

    intelligibility = _similarity(clean_reference, str(transcript.get("text") or ""))
    timing = _ratio_score(float(learner_features["duration_seconds"]), float(reference_features["duration_seconds"]))
    prosody = _contour_score(learner_features.get("pitch_contour"), reference_features.get("pitch_contour"))
    voiced = 100.0 - min(100.0, abs(float(learner_features["voiced_frame_ratio"]) - float(reference_features["voiced_frame_ratio"])) * 180.0)
    quiet = 100.0 - min(100.0, abs(float(learner_features["quiet_frame_ratio"]) - float(reference_features["quiet_frame_ratio"])) * 220.0)
    rhythm = max(0.0, (voiced + quiet) / 2.0)

    components = [(intelligibility, 0.55), (timing, 0.20), (rhythm, 0.10)]
    if prosody is not None:
        components.append((prosody, 0.15))
    total_weight = sum(weight for _, weight in components)
    overall = sum(score * weight for score, weight in components) / total_weight

    notes: list[str] = []
    if intelligibility >= 90:
        notes.append("The controlled sentence was recognised very clearly.")
    elif intelligibility >= 70:
        notes.append("Most of the sentence was intelligible, but some words need a cleaner second attempt.")
    else:
        notes.append("Several words were not reliably recognised; slow down and stabilise the target sounds before increasing speed.")
    if timing < 72:
        notes.append("Your overall timing differs noticeably from the reference. Listen once more and imitate phrase length and pauses.")
    if prosody is not None and prosody < 58:
        notes.append("The sentence melody differs from the reference. Shadow the whole phrase rather than individual words.")
    if rhythm < 65:
        notes.append("Voicing/pausing pattern differs from the reference; keep the phrase flowing instead of giving every word equal weight.")
    if target_feature:
        notes.append(f"Target feature: {target_feature}. This V1 does not yet assign a phoneme-specific score to that feature.")

    result = {
        "recording_id": recording_id,
        "language_code": language_code,
        "reference_text": clean_reference,
        "heard_text": str(transcript.get("text") or ""),
        "target_feature": target_feature or "general controlled pronunciation",
        "engine": "focuslyra-pronunciation-v1/local",
        "scores": {
            "controlled_intelligibility": round(intelligibility),
            "timing_similarity": round(timing),
            "rhythm_similarity": round(rhythm),
            "prosody_shape_similarity": round(prosody) if prosody is not None else None,
            "practice_similarity": round(overall),
        },
        "feedback": notes,
        "learner_acoustics": {key: value for key, value in learner_features.items() if key != "pitch_contour"},
        "reference_acoustics": {key: value for key, value in reference_features.items() if key != "pitch_contour"},
        "phoneme_accuracy": None,
        "warning": (
            "Practice similarity is not a native-accent percentage. Exact sound-by-sound scoring remains disabled until "
            "forced alignment and target-language calibration are implemented."
        ),
    }

    session_id = save_session(
        {
            "language_code": language_code,
            "mode": "pronunciation",
            "metadata": {
                "recording_id": recording_id,
                "reference_text": clean_reference,
                "target_feature": target_feature,
                "reference_audio_id": reference_audio.get("id"),
            },
        }
    )
    evidence_analysis = {
        "provider": "local-acoustic",
        "model": "focuslyra-pronunciation-v1",
        "scores": {key: value for key, value in result["scores"].items() if value is not None},
        "patterns_to_revisit": ([{"item": target_feature, "reason": "controlled pronunciation practice"}] if target_feature else []),
    }
    save_learning_feedback(session_id, language_code, "pronunciation", evidence_analysis)
    result["session_id"] = session_id

    output = learner_path.with_suffix(".pronunciation.json")
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result
