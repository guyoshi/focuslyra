from __future__ import annotations

import json
from typing import Any

from .db import recent_learning_evidence
from .language_service import load_languages
from .profile_service import load_profile
from .providers import AIProviderError, ollama_json
from .runtime import current_user_id


class ActivityEngineError(RuntimeError):
    pass


SUPPORTED_MODALITIES = {"speak", "listen", "write", "read", "pronounce"}


def _language(language_code: str, user_id: str | None = None) -> dict[str, Any]:
    for language in load_languages(user_id):
        if language.get("code") == language_code:
            return language
    raise ActivityEngineError(f"Unknown language: {language_code}")


def _fallback_activity(slot: dict[str, Any], language: dict[str, Any]) -> dict[str, Any]:
    modality = str(slot.get("modality") or "speak")
    name = str(language.get("name") or slot.get("language_code") or "language")
    variety = str(language.get("target_variety") or language.get("code") or "")
    target = (slot.get("hidden_targets") or [""])[0]

    if modality == "listen":
        return {
            "title": "Listen, understand, respond",
            "instructions": "Listen without reading a transcript. Say or write what you understood, then respond naturally.",
            "prompt": "What did the speaker mean, and how would you answer?",
            "audio_text": f"This is a short {name} listening practice for today.",
            "input_text": "",
            "reference_text": "",
            "target_feature": "natural listening",
            "placeholder": "Your answer…",
        }
    if modality == "write":
        return {
            "title": "Write from real life",
            "instructions": f"Write in {name}. Do not correct yourself before submitting.",
            "prompt": "Describe one thing that happened today and one thing you plan to do next.",
            "audio_text": "",
            "input_text": "",
            "reference_text": "",
            "target_feature": target or "active production",
            "placeholder": f"Write in {name}…",
        }
    if modality == "read":
        return {
            "title": "Read for meaning",
            "instructions": "Read once for meaning before analysing individual words.",
            "prompt": "Explain the main idea in your own words.",
            "audio_text": "",
            "input_text": f"A short adaptive {name} reading will appear here when the local model is available.",
            "reference_text": "",
            "target_feature": target or "reading comprehension",
            "placeholder": "Your explanation…",
        }
    if modality == "pronounce":
        return {
            "title": "Pronunciation reference",
            "instructions": f"Listen to the reference in {variety}, then record yourself saying the same sentence naturally.",
            "prompt": "Match the sounds, timing and sentence melody rather than spelling.",
            "audio_text": "",
            "input_text": "",
            "reference_text": "I would rather practise a short sentence carefully than rush through it.",
            "target_feature": target or "timing and prosody",
            "placeholder": "",
        }
    return {
        "title": "Speak without preparing",
        "instructions": f"Answer aloud in {name}. Keep going even if you have to describe a word you do not know.",
        "prompt": "Explain what you would do if tomorrow suddenly became completely free.",
        "audio_text": "",
        "input_text": "",
        "reference_text": "",
        "target_feature": target or "spontaneous speaking",
        "placeholder": "",
    }


def _clean(value: dict[str, Any], slot: dict[str, Any], language: dict[str, Any]) -> dict[str, Any]:
    fallback = _fallback_activity(slot, language)
    modality = str(slot.get("modality") or "speak")
    if modality not in SUPPORTED_MODALITIES:
        modality = "speak"

    clean = {
        "activity_id": str(slot.get("id") or "activity"),
        "language_code": str(language.get("code") or slot.get("language_code") or ""),
        "language_name": str(language.get("name") or ""),
        "flag": str(language.get("flag") or ""),
        "target_variety": str(language.get("target_variety") or ""),
        "modality": modality,
        "minutes": int(slot.get("minutes") or 5),
        "title": str(value.get("title") or fallback["title"])[:180],
        "instructions": str(value.get("instructions") or fallback["instructions"])[:1200],
        "prompt": str(value.get("prompt") or fallback["prompt"])[:1800],
        "audio_text": str(value.get("audio_text") or fallback["audio_text"])[:1800],
        "input_text": str(value.get("input_text") or fallback["input_text"])[:3000],
        "reference_text": str(value.get("reference_text") or fallback["reference_text"])[:1000],
        "target_feature": str(value.get("target_feature") or fallback["target_feature"])[:240],
        "placeholder": str(value.get("placeholder") or fallback["placeholder"])[:240],
        "hidden_targets": [str(item)[:180] for item in (slot.get("hidden_targets") or [])[:4]],
        "reason": str(slot.get("reason") or "adaptive study"),
        "provider": str(value.get("provider") or "fallback"),
        "model": str(value.get("model") or "rules"),
    }

    # Listening must have something to play. Pronunciation must have a known
    # reference so acoustic comparison is meaningful.
    if modality == "listen" and not clean["audio_text"]:
        clean["audio_text"] = fallback["audio_text"]
    if modality == "pronounce" and not clean["reference_text"]:
        clean["reference_text"] = fallback["reference_text"]
    return clean


def generate_activity(slot: dict[str, Any], user_id: str | None = None) -> dict[str, Any]:
    uid = user_id or current_user_id()
    language_code = str(slot.get("language_code") or "").strip()
    modality = str(slot.get("modality") or "speak").strip().lower()
    if modality not in SUPPORTED_MODALITIES:
        raise ActivityEngineError(f"Unsupported study modality: {modality}")

    language = _language(language_code, uid)
    profile = load_profile(uid)
    evidence = recent_learning_evidence(language_code, limit=20, user_id=uid)
    hidden_targets = [str(item) for item in (slot.get("hidden_targets") or [])[:4] if str(item).strip()]

    system_prompt = f"""
You create ONE short adaptive activity inside Focuslyra.
Target language: {language.get('name')} ({language.get('target_variety')}).
Modality: {modality}.
The learner's native language is {profile.get('native_language', 'pt-BR')}.
Primary learning focus: {', '.join(profile.get('learning_focus') or ['speaking', 'listening'])}.
Current learner state: {language.get('current_state', 'not assessed')}.
Goals: {', '.join(language.get('goals') or [])}.

Rules:
- Produce a useful real-world activity, not a school worksheet.
- Keep it suitable for the learner state above. Do not suddenly use advanced target-language instructions for a beginner.
- Learner-facing explanations/instructions may be in clear English when needed; the language being practised must be the target language.
- If hidden retrieval targets are supplied, create a situation where the learner is likely to need them. For SPEAK/WRITE, NEVER reveal those exact target expressions in the learner-visible prompt.
- For LISTEN, put the spoken target-language passage ONLY in audio_text. Do not repeat it in prompt or input_text.
- For READ, put the target-language passage in input_text and ask a meaning/comprehension question.
- For PRONOUNCE, reference_text must be a short natural sentence in the target language and target_feature must name a useful sound/rhythm feature. Do not claim that a dialect voice is perfect.
- For SPEAK, prompt must require spontaneous speech and no reference answer.
- For WRITE, prompt must require original production and placeholder should match the target language.
- Keep the activity around {int(slot.get('minutes') or 5)} minutes.

Return ONLY JSON:
{{
  "title": "...",
  "instructions": "...",
  "prompt": "...",
  "audio_text": "...",
  "input_text": "...",
  "reference_text": "...",
  "target_feature": "...",
  "placeholder": "..."
}}
Use empty strings for fields the modality does not need.
""".strip()

    user_payload = {
        "hidden_retrieval_targets": hidden_targets,
        "recent_evidence": evidence,
        "attention_strategy": profile.get("attention_strategy"),
        "planner_reason": slot.get("reason"),
    }

    try:
        generated = ollama_json(system_prompt, json.dumps(user_payload, ensure_ascii=False), timeout=90.0)
    except AIProviderError:
        generated = _fallback_activity(slot, language)
        generated["provider"] = "focuslyra-rules"
        generated["model"] = "fallback-v1"
    return _clean(generated, slot, language)
