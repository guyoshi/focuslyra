from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .db import recent_learning_evidence, save_learning_feedback, save_session
from .providers import AIProviderError, ollama_json

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"


class LearningEngineError(RuntimeError):
    pass


def _load_json(name: str) -> Any:
    path = DATA_DIR / name
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _language_profile(language_code: str) -> dict[str, Any]:
    languages = _load_json("languages.json")
    for language in languages:
        if language.get("code") == language_code:
            return language
    return {"code": language_code, "name": language_code, "target_variety": language_code}


def _learner_context(language_code: str) -> dict[str, Any]:
    profile = _load_json("profile.json")
    language = _language_profile(language_code)
    evidence = recent_learning_evidence(language_code, limit=16)
    return {
        "learner": {
            "name": profile.get("learner_name", "learner"),
            "native_language": profile.get("native_language", "pt-BR"),
            "learning_focus": profile.get("learning_focus", ["speaking", "listening"]),
            "accent_importance": profile.get("accent_importance", "high"),
            "attention_strategy": profile.get("attention_strategy"),
        },
        "language": language,
        "recent_evidence": evidence,
    }


def _validate_analysis(value: dict[str, Any]) -> dict[str, Any]:
    value.setdefault("summary", "Analysis completed.")
    value.setdefault("strengths", [])
    value.setdefault("corrections", [])
    value.setdefault("scores", {})
    value.setdefault("patterns_to_revisit", [])
    value.setdefault(
        "next_activity",
        {
            "type": "speak",
            "prompt": "Use the corrected language in one new sentence.",
            "target": "retrieval",
            "audio_text": "",
        },
    )

    scores = value.get("scores")
    if not isinstance(scores, dict):
        value["scores"] = {}
    else:
        clean_scores: dict[str, int] = {}
        for key, raw in scores.items():
            try:
                clean_scores[str(key)] = max(0, min(100, int(float(raw))))
            except (TypeError, ValueError):
                continue
        value["scores"] = clean_scores

    for list_key in ("strengths", "corrections", "patterns_to_revisit"):
        if not isinstance(value.get(list_key), list):
            value[list_key] = []
    if not isinstance(value.get("next_activity"), dict):
        value["next_activity"] = {"type": "speak", "prompt": "Try again naturally.", "target": "retrieval", "audio_text": ""}
    value["next_activity"].setdefault("audio_text", "")
    return value


def analyse_submission(
    *,
    language_code: str,
    modality: str,
    learner_text: str,
    exercise_prompt: str | None = None,
    transcript_source: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    text = learner_text.strip()
    if not text:
        raise LearningEngineError("There is no learner response to analyse.")

    context = _learner_context(language_code)
    language = context["language"]
    target_name = language.get("name", language_code)
    target_variety = language.get("target_variety") or language_code

    system_prompt = f"""
You are the local assessment engine inside Focuslyra, a speaking/listening-first language-learning system.
You are analysing {target_name} ({target_variety}) for one learner.
The learner's native language is Brazilian Portuguese.

Principles:
- Judge communication and automatic usable language, not school-test perfection.
- Correct only mistakes that are useful enough to change future learning.
- Do not punish harmless stylistic variation.
- Separate what the learner can understand from what they can actively produce when evidence allows it.
- Prefer natural chunks/collocations and reusable sentence patterns over isolated grammar lectures.
- If a regional variety is specified, prefer that variety.
- Never invent pronunciation conclusions from text alone. If modality is speech-transcript, comment only on language evidenced by the transcript; acoustic pronunciation is analysed separately.
- The next activity must test retrieval without simply giving the learner the answer first.
- Keep feedback concise enough to be useful during a study session.
- Feedback/explanations may be in clear English, but any audio_text must be natural {target_name} in the requested regional variety.

Return ONLY one JSON object with this exact high-level shape:
{{
  "summary": "short learner-facing summary",
  "strengths": ["..."],
  "corrections": [
    {{"original": "...", "natural": "...", "reason": "...", "category": "grammar|vocabulary|naturalness|word_order|register"}}
  ],
  "scores": {{"communication": 0, "grammar_automaticity": 0, "active_vocabulary": 0, "naturalness": 0}},
  "patterns_to_revisit": [{{"item": "short reusable target", "reason": "why it needs another encounter"}}],
  "next_activity": {{
    "type": "speak|write|listen|read|review",
    "prompt": "one concrete next task",
    "target": "hidden/retrieval target",
    "audio_text": "a short natural target-language utterance useful for listening/repetition; empty string when audio would reveal the retrieval answer"
  }}
}}
Scores are integers from 0 to 100 and are session evidence, not CEFR claims.
""".strip()

    user_payload = {
        "exercise_prompt": exercise_prompt,
        "modality": modality,
        "transcript_source": transcript_source,
        "learner_response": text,
        "learner_context": context,
    }
    try:
        analysis = ollama_json(system_prompt, json.dumps(user_payload, ensure_ascii=False))
    except AIProviderError as exc:
        raise LearningEngineError(str(exc)) from exc

    analysis = _validate_analysis(analysis)
    session_payload = {
        "language_code": language_code,
        "mode": modality,
        "writing": text if modality == "writing" else None,
        "metadata": {
            **(metadata or {}),
            "exercise_prompt": exercise_prompt,
            "transcript_source": transcript_source,
            "analysed_by": analysis.get("provider"),
            "model": analysis.get("model"),
        },
    }
    session_id = save_session(session_payload)
    save_learning_feedback(session_id, language_code, modality, analysis)

    return {
        "session_id": session_id,
        "language_code": language_code,
        "modality": modality,
        "analysis": analysis,
    }
