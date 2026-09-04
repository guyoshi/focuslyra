from __future__ import annotations

import json
from typing import Any

from .db import recent_learning_evidence, save_learning_feedback, save_session
from .language_service import load_languages
from .profile_service import load_profile
from .providers import AIProviderError, ollama_json


class LearningEngineError(RuntimeError):
    pass


def _language_profile(language_code: str) -> dict[str, Any]:
    for language in load_languages():
        if language.get("code") == language_code:
            return language
    return {"code": language_code, "name": language_code, "target_variety": language_code, "goals": []}


def _compact_evidence(language_code: str) -> list[dict[str, Any]]:
    """Keep only the evidence needed for one live assessment.

    The full evidence history remains in SQLite. Sending a large history back to
    a small local model on every click wastes prompt-processing time and does not
    improve the immediate correction enough to justify the latency.
    """
    evidence = recent_learning_evidence(language_code, limit=8)
    compact: list[dict[str, Any]] = []
    for item in evidence:
        payload = item.get("payload") if isinstance(item.get("payload"), dict) else {}
        compact.append(
            {
                "item": str(item.get("item_id") or "")[:180],
                "modality": item.get("modality"),
                "event": item.get("event_type"),
                "score": item.get("score"),
                "reason": str(payload.get("reason") or "")[:220],
            }
        )
    return compact


def _learner_context(language_code: str) -> dict[str, Any]:
    profile = load_profile()
    language = _language_profile(language_code)
    return {
        "learner": {
            "native_language": profile.get("native_language", "pt-BR"),
            "learning_focus": profile.get("learning_focus", ["speaking", "listening"]),
            "accent_importance": profile.get("accent_importance", "high"),
        },
        "language": {
            "code": language.get("code", language_code),
            "name": language.get("name", language_code),
            "target_variety": language.get("target_variety", language_code),
            "current_state": language.get("current_state", "not assessed"),
            "goals": (language.get("goals") or [])[:6],
        },
        "recent_evidence": _compact_evidence(language_code),
    }


def _validate_analysis(value: dict[str, Any]) -> dict[str, Any]:
    value.setdefault("summary", "Analysis completed.")
    value.setdefault("strengths", [])
    value.setdefault("corrections", [])
    value.setdefault("scores", {})
    value.setdefault("patterns_to_revisit", [])
    value.setdefault(
        "next_activity",
        {"type": "speak", "prompt": "Use the corrected language in one new sentence.", "target": "retrieval", "audio_text": ""},
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
    native_language = context["learner"].get("native_language") or "pt-BR"

    system_prompt = f"""
You are the fast local assessment engine inside Focuslyra.
Analyse {target_name} ({target_variety}) for a learner whose native language is {native_language}.
Modality: {modality}.

Rules:
- Judge usable communication, not school-test perfection.
- Correct only mistakes worth revisiting.
- Do not punish harmless stylistic variation.
- Listening/reading responses: prioritise comprehension first.
- Prefer natural chunks and reusable sentence patterns.
- Never infer pronunciation from text/transcripts; acoustics are separate.
- Keep the response VERY concise for a live study session.
- Maximum 3 strengths, 3 corrections and 3 revisit patterns.
- The next task must test retrieval without giving away the answer.

Return ONLY JSON:
{{
  "summary":"1-2 short sentences",
  "strengths":["..."],
  "corrections":[{{"original":"...","natural":"...","reason":"brief reason","category":"grammar|vocabulary|naturalness|word_order|register"}}],
  "scores":{{"communication":0,"grammar_automaticity":0,"active_vocabulary":0,"naturalness":0}},
  "patterns_to_revisit":[{{"item":"short reusable target","reason":"brief reason"}}],
  "next_activity":{{"type":"speak|write|listen|read|review","prompt":"one short task","target":"hidden retrieval target","audio_text":""}}
}}
Scores are 0-100 session evidence, not CEFR.
""".strip()

    user_payload = {
        "exercise": (exercise_prompt or "")[:1800],
        "response": text[:4000],
        "context": context,
    }
    try:
        analysis = ollama_json(system_prompt, json.dumps(user_payload, ensure_ascii=False), timeout=60.0)
    except AIProviderError as exc:
        raise LearningEngineError(str(exc)) from exc

    analysis = _validate_analysis(analysis)
    session_payload = {
        "language_code": language_code,
        "mode": modality,
        "writing": text if modality in {"writing", "listening-response", "reading-response"} else None,
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

    return {"session_id": session_id, "language_code": language_code, "modality": modality, "analysis": analysis}
