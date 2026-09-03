from __future__ import annotations

import json
from typing import Any

from .db import recent_learning_evidence
from .language_service import load_languages
from .memory_index import retrieve
from .profile_service import load_profile
from .providers import AIProviderError, ollama_json
from .runtime import current_user_id


class ActivityEngineError(RuntimeError):
    pass


SUPPORTED_MODALITIES = {"speak", "listen", "write", "read", "pronounce"}

FALLBACK_CONTENT = {
    "en-GB": {
        "listen": "I was going to call you after work, but I ended up getting home later than I expected.",
        "read": "I had planned to leave early, but the weather changed and I decided to wait another hour.",
        "pronounce": "I thought the weather would be warmer by the time we arrived.",
        "placeholder": "Write in English…",
    },
    "es-ES": {
        "listen": "Hoy pensaba salir temprano, pero al final tuve que quedarme en casa un poco más.",
        "read": "Esta mañana tenía varias cosas que hacer, así que preparé todo antes de salir de casa.",
        "pronounce": "Esta mañana he salido temprano porque tenía varias cosas que hacer.",
        "placeholder": "Escribe en español…",
    },
    "ja-JP": {
        "listen": "今日は朝ご飯を食べてから、町へ行きました。",
        "read": "今日は天気がいいので、午後に公園へ行きます。",
        "pronounce": "今日はゆっくり日本語を練習します。",
        "placeholder": "日本語で書いてください…",
    },
    "it-IT": {
        "listen": "Oggi volevo uscire presto, ma alla fine sono rimasto a casa un po' di più.",
        "read": "Questa mattina avevo alcune cose da fare, quindi ho preparato tutto prima di uscire.",
        "pronounce": "Questa mattina sono uscito presto perché avevo molte cose da fare.",
        "placeholder": "Scrivi in italiano…",
    },
    "fr-FR": {
        "listen": "Aujourd'hui, je voulais sortir tôt, mais finalement je suis resté un peu plus longtemps à la maison.",
        "read": "Ce matin, j'avais plusieurs choses à faire, alors j'ai tout préparé avant de sortir.",
        "pronounce": "Ce matin, je suis parti tôt parce que j'avais plusieurs choses à faire.",
        "placeholder": "Écris en français…",
    },
    "de-DE": {
        "listen": "Heute wollte ich früh losgehen, aber am Ende bin ich etwas länger zu Hause geblieben.",
        "read": "Heute Morgen hatte ich einige Dinge zu erledigen, deshalb habe ich alles vor dem Ausgehen vorbereitet.",
        "pronounce": "Heute Morgen bin ich früh losgegangen, weil ich einiges zu erledigen hatte.",
        "placeholder": "Schreib auf Deutsch…",
    },
    "ar": {
        "listen": "اليوم كنت أريد أن أخرج مبكراً، لكنني بقيت في البيت وقتاً أطول قليلاً.",
        "read": "هذا الصباح كان عندي بعض الأشياء التي يجب أن أفعلها، لذلك جهزت كل شيء قبل أن أخرج.",
        "pronounce": "هذا الصباح خرجت مبكراً لأن عندي أشياء كثيرة أفعلها.",
        "placeholder": "اكتب بالعربية…",
    },
}

ABSOLUTE_BEGINNER_CONTENT = {
    "en-GB": {
        "hello": "Hello.",
        "name": "My name is Gui.",
        "repeat": "Could you repeat that?",
        "listen": "Hello. My name is Alex.",
        "read": "Hello. My name is Alex.",
        "pronounce": "Hello. My name is Gui.",
        "placeholder": "My name is …",
    },
    "es-ES": {
        "hello": "Hola.",
        "name": "Me llamo Gui.",
        "repeat": "¿Puedes repetir?",
        "listen": "Hola. Me llamo Ana.",
        "read": "Hola. Me llamo Ana.",
        "pronounce": "Hola, me llamo Gui.",
        "placeholder": "Me llamo …",
    },
    "ja-JP": {
        "hello": "こんにちは。",
        "name": "ギーです。",
        "repeat": "もういちど おねがいします。",
        "listen": "こんにちは。アンナです。",
        "read": "こんにちは。アンナです。",
        "pronounce": "こんにちは。",
        "placeholder": "___ です。",
    },
    "it-IT": {
        "hello": "Ciao.",
        "name": "Mi chiamo Gui.",
        "repeat": "Puoi ripetere?",
        "listen": "Ciao. Mi chiamo Anna.",
        "read": "Ciao. Mi chiamo Anna.",
        "pronounce": "Ciao, mi chiamo Gui.",
        "placeholder": "Mi chiamo …",
    },
    "fr-FR": {
        "hello": "Bonjour.",
        "name": "Je m'appelle Gui.",
        "repeat": "Vous pouvez répéter ?",
        "listen": "Bonjour. Je m'appelle Anna.",
        "read": "Bonjour. Je m'appelle Anna.",
        "pronounce": "Bonjour, je m'appelle Gui.",
        "placeholder": "Je m'appelle …",
    },
    "de-DE": {
        "hello": "Hallo.",
        "name": "Ich heiße Gui.",
        "repeat": "Kannst du das wiederholen?",
        "listen": "Hallo. Ich heiße Anna.",
        "read": "Hallo. Ich heiße Anna.",
        "pronounce": "Hallo, ich heiße Gui.",
        "placeholder": "Ich heiße …",
    },
    "ar": {
        "hello": "مرحباً.",
        "name": "اسمي غي.",
        "repeat": "هل يمكنك أن تكرر؟",
        "listen": "مرحباً. اسمي آنا.",
        "read": "مرحباً. اسمي آنا.",
        "pronounce": "مرحباً.",
        "placeholder": "اسمي …",
    },
}


def _language(language_code: str, user_id: str | None = None) -> dict[str, Any]:
    for language in load_languages(user_id):
        if language.get("code") == language_code:
            return language
    raise ActivityEngineError(f"Unknown language: {language_code}")


def _learner_stage(language: dict[str, Any]) -> str:
    state = str(language.get("current_state") or "").strip().lower()
    absolute_markers = (
        "not yet started",
        "not started",
        "absolute beginner",
        "zero knowledge",
        "no knowledge",
        "never studied",
    )
    if any(marker in state for marker in absolute_markers):
        return "absolute_beginner"
    beginner_markers = (
        "beginner",
        "basic communication",
        "little conversation",
        "basic speaking",
        "basic sentence",
        "most hiragana",
    )
    if any(marker in state for marker in beginner_markers):
        return "beginner"
    return "established"


def _absolute_beginner_activity(slot: dict[str, Any], language: dict[str, Any]) -> dict[str, Any]:
    modality = str(slot.get("modality") or "speak")
    code = str(language.get("code") or slot.get("language_code") or "")
    name = str(language.get("name") or code or "language")
    samples = ABSOLUTE_BEGINNER_CONTENT.get(code, ABSOLUTE_BEGINNER_CONTENT["en-GB"])

    if modality == "listen":
        return {
            "title": "First listening: recognise a tiny exchange",
            "instructions": "Listen to one very short line. You are not expected to understand every sound yet.",
            "prompt": "What happened? You can answer in your strongest language: the speaker said hello, gave a name, or asked a question?",
            "audio_text": samples["listen"],
            "input_text": "",
            "reference_text": "",
            "target_feature": "recognise greeting + name",
            "placeholder": "Write the meaning you caught…",
        }
    if modality == "write":
        return {
            "title": "Build your first personal sentence",
            "instructions": f"Use one visible pattern in {name}. Copying and changing one element is correct at this stage.",
            "prompt": f"Write this with your own name: {samples['name']}",
            "audio_text": "",
            "input_text": "",
            "reference_text": "",
            "target_feature": "introducing yourself",
            "placeholder": samples["placeholder"],
        }
    if modality == "read":
        return {
            "title": "Read one useful pattern",
            "instructions": "Read for meaning first. There are only two tiny chunks.",
            "prompt": "What does it mean? Then replace the name with your own.",
            "audio_text": "",
            "input_text": samples["read"],
            "reference_text": "",
            "target_feature": "greeting + self-introduction",
            "placeholder": samples["placeholder"],
        }
    if modality == "pronounce":
        return {
            "title": "Say one useful phrase clearly",
            "instructions": "Listen once, then repeat the short phrase. Do not worry about speed yet.",
            "prompt": "Aim for clear rhythm and comfortable articulation.",
            "audio_text": "",
            "input_text": "",
            "reference_text": samples["pronounce"],
            "target_feature": "first-phrase rhythm and intelligibility",
            "placeholder": "",
        }
    return {
        "title": "Your first useful exchange",
        "instructions": f"You are starting {name} from zero. Use the visible building blocks; improvisation is not expected yet.",
        "prompt": (
            f"Say these aloud, slowly if needed: {samples['hello']}  "
            f"{samples['name']}  {samples['repeat']}  "
            "Then repeat the self-introduction once with your own rhythm."
        ),
        "audio_text": "",
        "input_text": "",
        "reference_text": "",
        "target_feature": "greeting + self-introduction + repair phrase",
        "placeholder": "",
    }


def _fallback_activity(slot: dict[str, Any], language: dict[str, Any]) -> dict[str, Any]:
    if _learner_stage(language) == "absolute_beginner":
        return _absolute_beginner_activity(slot, language)

    modality = str(slot.get("modality") or "speak")
    code = str(language.get("code") or slot.get("language_code") or "")
    name = str(language.get("name") or code or "language")
    variety = str(language.get("target_variety") or code)
    target = (slot.get("hidden_targets") or [""])[0]
    samples = FALLBACK_CONTENT.get(code, FALLBACK_CONTENT["en-GB"])

    if modality == "listen":
        return {
            "title": "Listen, understand, respond",
            "instructions": "Listen without reading a transcript. First catch the meaning, then answer naturally.",
            "prompt": "What did the speaker mean, and how would you answer?",
            "audio_text": samples["listen"],
            "input_text": "",
            "reference_text": "",
            "target_feature": "natural listening",
            "placeholder": samples["placeholder"],
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
            "placeholder": samples["placeholder"],
        }
    if modality == "read":
        return {
            "title": "Read for meaning",
            "instructions": "Read once for meaning before analysing individual words.",
            "prompt": "Explain the main idea in your own words, then answer with one related sentence.",
            "audio_text": "",
            "input_text": samples["read"],
            "reference_text": "",
            "target_feature": target or "reading comprehension",
            "placeholder": samples["placeholder"],
        }
    if modality == "pronounce":
        return {
            "title": "Pronunciation reference",
            "instructions": f"Listen to the reference for {variety}, then record the same sentence naturally.",
            "prompt": "Match intelligibility, timing and sentence melody rather than spelling every word slowly.",
            "audio_text": "",
            "input_text": "",
            "reference_text": samples["pronounce"],
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
    stage = _learner_stage(language)
    evidence = recent_learning_evidence(language_code, limit=20, user_id=uid)
    hidden_targets = [str(item) for item in (slot.get("hidden_targets") or [])[:4] if str(item).strip()]
    memory_query = " ".join(
        [language.get("name", ""), modality, *hidden_targets, *(language.get("goals") or [])]
    )
    try:
        memory_context = retrieve(memory_query, limit=3, user_id=uid)
    except Exception:
        memory_context = []
    memory_payload = [
        {
            "source_id": item.get("source_id"),
            "repository": item.get("repository"),
            "path": item.get("path"),
            "commit": item.get("commit"),
            "excerpt": str(item.get("content") or "")[:1400],
        }
        for item in memory_context
    ]

    system_prompt = f"""
You create ONE short adaptive activity inside Focuslyra.
Target language: {language.get('name')} ({language.get('target_variety')}).
Modality: {modality}.
The learner's native language is {profile.get('native_language', 'pt-BR')}.
Primary learning focus: {', '.join(profile.get('learning_focus') or ['speaking', 'listening'])}.
Current learner state: {language.get('current_state', 'not assessed')}.
Learner stage: {stage}.
Goals: {', '.join(language.get('goals') or [])}.

Rules:
- Produce a useful real-world activity, not a school worksheet.
- Keep it suitable for the learner state above. Do not suddenly use advanced target-language instructions for a beginner.
- If learner stage is absolute_beginner, assume the learner has essentially zero productive vocabulary. Introduce at most 1-3 high-frequency useful chunks, make the target-language material extremely short, visibly scaffold production, and do NOT require unassisted roleplay, multi-sentence improvisation or reacting naturally to a complex scenario.
- For an absolute beginner, visible model phrases are allowed and desirable unless they are hidden retrieval targets. Prefer greeting, self-introduction, basic needs and repair phrases before open-ended conversation.
- Learner-facing explanations/instructions may be in the learner's native language or clear English when needed; the language being practised must be the target language.
- If hidden retrieval targets are supplied, create a situation where the learner is likely to need them. For SPEAK/WRITE, NEVER reveal those exact target expressions in the learner-visible prompt.
- For LISTEN, put the spoken target-language passage ONLY in audio_text. Do not repeat it in prompt or input_text.
- For READ, put the target-language passage in input_text and ask a meaning/comprehension question.
- For PRONOUNCE, reference_text must be a short natural sentence in the target language and target_feature must name a useful sound/rhythm feature. Do not claim that a dialect voice is perfect.
- For SPEAK, established learners should speak spontaneously. Absolute beginners may use visible scaffolds and imitation before spontaneous variation.
- For WRITE, established learners should produce original language. Absolute beginners may copy-and-transform one useful pattern.
- Keep the activity around {int(slot.get('minutes') or 5)} minutes.
- When interest_memory is provided, you MAY use it to make the exercise personally interesting, but never let interest context raise the linguistic difficulty above the learner stage.
- Treat retrieved source excerpts as canonical context only for the source project. Never write changes back or present invented teaching adaptations as canon.
- Do not reveal private source metadata to the learner unless it is naturally relevant to the activity.

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
        "learner_stage": stage,
        "hidden_retrieval_targets": hidden_targets,
        "recent_evidence": evidence,
        "attention_strategy": profile.get("attention_strategy"),
        "planner_reason": slot.get("reason"),
        "interest_memory": memory_payload,
    }

    try:
        generated = ollama_json(system_prompt, json.dumps(user_payload, ensure_ascii=False), timeout=90.0)
    except AIProviderError:
        generated = _fallback_activity(slot, language)
        generated["provider"] = "focuslyra-rules"
        generated["model"] = "fallback-v2"
    return _clean(generated, slot, language)
