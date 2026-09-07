from __future__ import annotations

import json
from typing import Any

from .db import recent_learning_evidence, save_learning_feedback, save_session
from .language_service import load_languages
from .mistake_service import annotate_analysis_with_mistake_history, due_mistake_targets, mistake_memory
from .profile_service import load_profile
from .providers import AIProviderError, ollama_json
from .runtime import current_user_id


class LearningEngineError(RuntimeError):
    pass


def _language_profile(language_code: str, user_id: str | None = None) -> dict[str, Any]:
    for language in load_languages(user_id):
        if language.get("code") == language_code:
            return language
    return {"code": language_code, "name": language_code, "target_variety": language_code, "goals": []}


def _learner_stage(current_state: str) -> str:
    state = str(current_state or "").strip().lower()
    if any(marker in state for marker in ("pre-a1", "absolute beginner", "zero knowledge", "no knowledge", "not yet started", "not started", "never studied")):
        return "absolute_beginner"
    if "a1" in state or any(marker in state for marker in ("beginner", "most hiragana", "basic sentence")):
        return "beginner"
    if "a2" in state:
        return "elementary"
    if "b1" in state:
        return "independent"
    if "b2" in state:
        return "upper_intermediate"
    if "c1" in state or "c2" in state:
        return "advanced"
    return "unknown"


def _compact_evidence(language_code: str, user_id: str | None = None) -> list[dict[str, Any]]:
    evidence = recent_learning_evidence(language_code, limit=10, user_id=user_id)
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
                "memory_key": str(payload.get("memory_key") or "")[:180],
            }
        )
    return compact


def _compact_mistakes(language_code: str, user_id: str | None = None) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for item in mistake_memory(language_code, limit=10, user_id=user_id):
        result.append(
            {
                "memory_key": item.get("memory_key"),
                "category": item.get("category"),
                "learning_target": item.get("learning_target"),
                "corrected": str(item.get("corrected") or "")[:300],
                "explanation_pt": str(item.get("explanation_pt") or "")[:360],
                "occurrences": item.get("occurrences"),
                "successful_retests": item.get("successful_retests"),
                "status": item.get("status"),
                "next_due_at": item.get("next_due_at"),
            }
        )
    return result


def _learner_context(language_code: str, user_id: str | None = None) -> dict[str, Any]:
    uid = user_id or current_user_id()
    profile = load_profile(uid)
    language = _language_profile(language_code, uid)
    current_state = str(language.get("current_state") or "not assessed")
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
            "current_state": current_state,
            "learner_stage": _learner_stage(current_state),
            "goals": (language.get("goals") or [])[:6],
        },
        "recent_evidence": _compact_evidence(language_code, uid),
        "mistake_memory": _compact_mistakes(language_code, uid),
        "due_mistakes": [
            {
                "memory_key": item.get("memory_key"),
                "category": item.get("category"),
                "learning_target": item.get("learning_target"),
                "occurrences": item.get("occurrences"),
            }
            for item in due_mistake_targets(language_code, limit=6, user_id=uid)
        ],
    }


def _validate_analysis(value: dict[str, Any]) -> dict[str, Any]:
    value.setdefault("summary", "Analysis completed.")
    value.setdefault("strengths", [])
    value.setdefault("corrections", [])
    value.setdefault("scores", {})
    value.setdefault("patterns_to_revisit", [])
    value.setdefault("mistake_outcomes", [])
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

    for list_key in ("strengths", "corrections", "patterns_to_revisit", "mistake_outcomes"):
        if not isinstance(value.get(list_key), list):
            value[list_key] = []

    clean_corrections: list[dict[str, Any]] = []
    for raw in value.get("corrections", [])[:6]:
        if not isinstance(raw, dict):
            continue
        correction = dict(raw)
        correction["original"] = str(correction.get("original") or "")[:1000]
        correction["natural"] = str(correction.get("natural") or correction.get("corrected") or "")[:1000]
        correction["category"] = str(correction.get("category") or "grammar")[:80]
        correction["meaning_pt"] = str(correction.get("meaning_pt") or "")[:1000]
        correction["explanation_pt"] = str(correction.get("explanation_pt") or correction.get("reason") or "")[:1200]
        correction["example"] = str(correction.get("example") or "")[:1000]
        correction["learning_target"] = str(correction.get("learning_target") or correction.get("natural") or "")[:400]
        correction["memory_key"] = str(correction.get("memory_key") or "")[:180]
        correction["knowledge_state"] = str(correction.get("knowledge_state") or "uncertain")[:40]
        correction["teaching_action"] = str(correction.get("teaching_action") or "correct_then_retest")[:60]
        correction["severity"] = str(correction.get("severity") or "medium")[:20]
        correction["needs_retest"] = bool(correction.get("needs_retest", True))
        parts = [correction["explanation_pt"]]
        if correction["meaning_pt"]:
            parts.append(f"Significado: {correction['meaning_pt']}")
        if correction["example"]:
            parts.append(f"Exemplo: {correction['example']}")
        correction["reason"] = " ".join(part.strip() for part in parts if part.strip())[:1800]
        clean_corrections.append(correction)
    value["corrections"] = clean_corrections

    clean_patterns: list[dict[str, Any]] = []
    for raw in value.get("patterns_to_revisit", [])[:8]:
        if isinstance(raw, dict):
            pattern = dict(raw)
        else:
            pattern = {"item": str(raw)}
        item = str(pattern.get("item") or pattern.get("learning_target") or "").strip()
        if not item:
            continue
        pattern["item"] = item[:400]
        pattern["learning_target"] = str(pattern.get("learning_target") or item)[:400]
        pattern["reason"] = str(pattern.get("reason") or "Meaningful learning target")[:1000]
        pattern["category"] = str(pattern.get("category") or "")[:80]
        pattern["memory_key"] = str(pattern.get("memory_key") or "")[:180]
        pattern["severity"] = str(pattern.get("severity") or "medium")[:20]
        pattern["needs_retest"] = bool(pattern.get("needs_retest", True))
        pattern["review_prompt"] = str(pattern.get("review_prompt") or "")[:1000]
        pattern["review_answer"] = str(pattern.get("review_answer") or "")[:1000]
        clean_patterns.append(pattern)
    value["patterns_to_revisit"] = clean_patterns

    clean_outcomes: list[dict[str, Any]] = []
    for raw in value.get("mistake_outcomes", [])[:10]:
        if not isinstance(raw, dict):
            continue
        outcome = str(raw.get("outcome") or "not_tested").strip().lower()
        if outcome not in {"correct_use", "repeated_error", "not_tested"}:
            outcome = "not_tested"
        key = str(raw.get("memory_key") or "").strip()[:180]
        if key:
            clean_outcomes.append({"memory_key": key, "outcome": outcome, "evidence": str(raw.get("evidence") or "")[:500]})
    value["mistake_outcomes"] = clean_outcomes

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

    uid = current_user_id()
    context = _learner_context(language_code, uid)
    language = context["language"]
    target_name = language.get("name", language_code)
    target_variety = language.get("target_variety") or language_code
    native_language = context["learner"].get("native_language") or "pt-BR"
    learner_stage = language.get("learner_stage") or "unknown"
    japanese_rules = """
Japanese-specific correction taxonomy:
- Use category typo for an accidental surface slip that does not reveal a Japanese knowledge gap.
- Use romaji only when the submitted evidence actually contains a romaji/input-method error. Never invent unseen keystrokes after automatic kana conversion.
- Use kana for wrong/missing hiragana or katakana knowledge, spelling or script choice.
- Use kanji for wrong kanji, reading-linked orthography, or choosing/recognising the wrong character.
- Use grammar for particles, conjugation, syntax or grammatical form.
- Use vocabulary_naturalness for wrong lexical choice, collocation or unnatural Japanese.
""".strip() if language_code == "ja-JP" else ""

    system_prompt = f"""
You are the fast local assessment AND teaching engine inside Focuslyra.
Analyse {target_name} ({target_variety}) for a learner whose native language is {native_language}.
Modality: {modality}.
Learner stage: {learner_stage}.
Current state/placement memory: {language.get('current_state')}.

Focuslyra controls the learner's progression. A correction is not just feedback for this turn: meaningful gaps can become future teaching/retrieval targets.

Rules:
- Judge usable communication, not school-test perfection.
- Let the learner's completed thought stand, then correct only mistakes worth learning from.
- Do not punish harmless stylistic variation.
- Listening/reading responses: prioritise comprehension first.
- Prefer natural chunks and reusable sentence patterns.
- Never infer pronunciation from text/transcripts; acoustics are separate.
- Use the learner stage and placement memory. Do not demand knowledge the learner has never been taught as though it were a careless failure.
- For absolute_beginner/beginner learners, when a mistake exposes a concept, sound, script rule or pattern they probably do not know yet, TEACH it briefly first: corrected form, Brazilian-Portuguese meaning, a plain explanation, and one tiny example. Mark knowledge_state=not_yet_taught or emerging and teaching_action=teach_then_guided_practice.
- For established learners, keep explanations shorter and prefer retrieval/contrast practice.
- A one-off harmless typo normally gets needs_retest=false. A recurring error, meaning-blocking error, current learning target, likely fossilisation risk, or important production gap gets needs_retest=true.
- mistake_memory contains durable past learner errors. If the same memory_key appears again, treat it as recurring and prioritise it. Do not guess recurrence from prose; use the supplied memory.
- due_mistakes are errors scheduled for a later check. If this task genuinely tested one, report a mistake_outcome with exactly that memory_key: correct_use, repeated_error, or not_tested. Never claim success when the task did not elicit the target.
- Repeated errors must be explicitly pointed out to the learner, but without scolding.
- For every meaningful correction, create a stable semantic memory_key such as grammar:past-tense-went or ja:particle-wa-vs-ga. Reuse a supplied memory_key when it is clearly the same target.
- If needs_retest=true, include a matching patterns_to_revisit entry with the same memory_key, category and learning_target.
- The next task should either teach/scaffold a not-yet-taught target or test retrieval without giving away a known target's answer.
- Keep the response concise enough for a live study session: maximum 3 strengths, 4 useful corrections and 4 revisit patterns.
{japanese_rules}

Return ONLY JSON:
{{
  "summary":"1-2 short sentences in Brazilian Portuguese",
  "strengths":["..."],
  "corrections":[{{
    "original":"exact learner fragment",
    "natural":"correct/natural target-language form",
    "meaning_pt":"meaning of corrected form in Brazilian Portuguese",
    "explanation_pt":"brief teaching explanation in Brazilian Portuguese",
    "example":"one short target-language example if useful",
    "category":"typo|spelling|romaji|kana|kanji|grammar|vocabulary|vocabulary_naturalness|naturalness|word_order|register",
    "learning_target":"short reusable target",
    "memory_key":"stable semantic key",
    "knowledge_state":"not_yet_taught|emerging|known|uncertain",
    "teaching_action":"teach_then_guided_practice|correct_then_retest|note_only",
    "severity":"low|medium|high",
    "needs_retest":true
  }}],
  "scores":{{"communication":0,"grammar_automaticity":0,"active_vocabulary":0,"naturalness":0}},
  "patterns_to_revisit":[{{
    "item":"short reusable target",
    "learning_target":"same target",
    "reason":"brief reason",
    "category":"same category",
    "memory_key":"same key as correction",
    "severity":"low|medium|high",
    "needs_retest":true,
    "review_prompt":"a later prompt that does not give away the answer",
    "review_answer":"short expected answer or model"
  }}],
  "mistake_outcomes":[{{"memory_key":"exact key from due_mistakes","outcome":"correct_use|repeated_error|not_tested","evidence":"brief evidence"}}],
  "next_activity":{{"type":"speak|write|listen|read|review","prompt":"one short task","target":"hidden retrieval/teaching target","audio_text":""}}
}}
Scores are 0-100 session evidence, not CEFR.
""".strip()

    user_payload = {
        "exercise": (exercise_prompt or "")[:1800],
        "response": text[:4000],
        "metadata": metadata or {},
        "context": context,
    }
    try:
        analysis = ollama_json(system_prompt, json.dumps(user_payload, ensure_ascii=False), timeout=60.0)
    except AIProviderError as exc:
        raise LearningEngineError(str(exc)) from exc

    analysis = _validate_analysis(analysis)
    analysis = annotate_analysis_with_mistake_history(language_code, analysis, user_id=uid)
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
            "learner_stage": learner_stage,
        },
    }
    session_id = save_session(session_payload, user_id=uid)
    save_learning_feedback(session_id, language_code, modality, analysis, user_id=uid)

    return {"session_id": session_id, "language_code": language_code, "modality": modality, "analysis": analysis}
