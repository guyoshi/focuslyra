from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from .db import save_learning_feedback, save_session
from .language_service import load_languages
from .profile_service import load_profile, save_profile
from .providers import AIProviderError, ollama_json
from .runtime import current_user_id


class PlacementServiceError(RuntimeError):
    pass


CEFR_ORDER = ["pre-A1", "A1", "A2", "B1", "B2", "C1", "C2"]
CEFR_SCORE = {"pre-A1": 10, "A1": 22, "A2": 38, "B1": 55, "B2": 72, "C1": 86, "C2": 96}


def _language(language_code: str, user_id: str | None = None) -> dict[str, Any]:
    for language in load_languages(user_id):
        if language.get("code") == language_code:
            return language
    raise PlacementServiceError("This language is not enabled for the current learner.")


def placement_prompts(language_code: str, user_id: str | None = None) -> dict[str, Any]:
    language = _language(language_code, user_id)
    name = str(language.get("name") or language_code)
    return {
        "language_code": language_code,
        "language_name": name,
        "target_variety": language.get("target_variety"),
        "writing_prompt": (
            f"Escreva em {name} sem usar tradutor. Diga quem você é, como é um dia normal seu, "
            "conte algo que aconteceu recentemente e fale de um plano para o futuro. Escreva somente "
            "o que conseguir naturalmente. Se souber pouco, algumas frases já bastam."
        ),
        "speaking_prompt": (
            f"Fale em {name} sem ler um texto pronto. Apresente-se, conte um pouco da sua rotina, "
            "diga algo que fez recentemente e algo que pretende fazer. Continue enquanto conseguir; "
            "não há problema em parar quando faltar vocabulário."
        ),
        "note": "Este é um nivelamento prático, não uma certificação oficial de CEFR.",
    }


def _clean_result(value: dict[str, Any]) -> dict[str, Any]:
    level = str(value.get("cefr_estimate") or "").strip()
    if level not in CEFR_ORDER:
        level = "pre-A1"
    confidence = str(value.get("confidence") or "low").strip().lower()
    if confidence not in {"low", "medium", "high"}:
        confidence = "low"
    return {
        "cefr_estimate": level,
        "confidence": confidence,
        "summary": str(value.get("summary") or "Amostra analisada.")[:1200],
        "strengths": [str(item)[:260] for item in (value.get("strengths") or [])[:6]],
        "gaps": [str(item)[:260] for item in (value.get("gaps") or [])[:6]],
        "next_step": str(value.get("next_step") or "Continue praticando com atividades adaptadas ao nível observado.")[:600],
        "evidence": [str(item)[:300] for item in (value.get("evidence") or [])[:6]],
    }


def _save_profile_level(language_code: str, result: dict[str, Any], modality: str, user_id: str) -> None:
    profile = load_profile(user_id)
    language_settings = dict(profile.get("language_settings") or {})
    current = dict(language_settings.get(language_code) or {})
    level = result["cefr_estimate"]
    current["current_state"] = (
        f"Placement estimate: {level} ({result['confidence']} confidence), based on a {modality} sample. "
        f"{result['summary']}"
    )[:1000]
    language_settings[language_code] = current
    profile["language_settings"] = language_settings

    history = dict(profile.get("placement_history") or {})
    entries = list(history.get(language_code) or [])
    entries.append(
        {
            "at": datetime.now(timezone.utc).isoformat(),
            "modality": modality,
            "cefr_estimate": level,
            "confidence": result["confidence"],
            "summary": result["summary"],
        }
    )
    history[language_code] = entries[-12:]
    profile["placement_history"] = history
    save_profile(profile, user_id)


def assess_level(
    language_code: str,
    learner_text: str,
    modality: str,
    *,
    user_id: str | None = None,
    transcript_source: str | None = None,
) -> dict[str, Any]:
    uid = user_id or current_user_id()
    text = str(learner_text or "").strip()
    if not text:
        raise PlacementServiceError("Não há uma amostra para avaliar.")
    if modality not in {"writing", "speaking"}:
        raise PlacementServiceError("Placement modality must be writing or speaking.")

    language = _language(language_code, uid)
    profile = load_profile(uid)
    name = str(language.get("name") or language_code)
    variety = str(language.get("target_variety") or language_code)

    system = f"""
You are Focuslyra's practical placement evaluator.
Evaluate one learner sample in {name} ({variety}).
The learner's native language is {profile.get('native_language', 'pt-BR')}.
Modality: {modality}.

Estimate a practical CEFR-like range from this sample only. This is NOT a certified exam.
Use exactly one of: pre-A1, A1, A2, B1, B2, C1, C2.
Judge what the learner can spontaneously understand/produce from the evidence present.
For a speech transcript, do not invent pronunciation or accent conclusions from text alone.
Do not inflate the level because Portuguese/Spanish/Italian cognates make a short sample look sophisticated.
If the sample is too short or heavily memorised-looking, lower confidence rather than inventing evidence.
A2 should mean the learner can combine simple sentences about familiar matters, not merely repeat fixed phrases.
B1 should require connected language across past/present/future with usable independent communication.
B2+ requires clear evidence of flexible, detailed and relatively automatic language.

Return ONLY JSON:
{{
  "cefr_estimate": "A1",
  "confidence": "low|medium|high",
  "summary": "short explanation in Brazilian Portuguese",
  "strengths": ["..."],
  "gaps": ["..."],
  "next_step": "one practical recommendation in Brazilian Portuguese",
  "evidence": ["specific features in the sample that justify the estimate"]
}}
""".strip()

    payload = {
        "learner": profile.get("learner_name"),
        "current_state_before_test": language.get("current_state"),
        "sample": text,
        "transcript_source": transcript_source,
    }
    try:
        raw = ollama_json(system, json.dumps(payload, ensure_ascii=False), timeout=120.0)
    except AIProviderError as exc:
        raise PlacementServiceError(str(exc)) from exc

    result = _clean_result(raw)
    session_id = save_session(
        {
            "language_code": language_code,
            "mode": f"placement-{modality}",
            "writing": text if modality == "writing" else None,
            "metadata": {
                "placement": True,
                "cefr_estimate": result["cefr_estimate"],
                "confidence": result["confidence"],
                "transcript_source": transcript_source,
            },
        },
        user_id=uid,
    )
    evidence_analysis = {
        "provider": raw.get("provider"),
        "model": raw.get("model"),
        "summary": result["summary"],
        "strengths": result["strengths"],
        "corrections": [],
        "patterns_to_revisit": [{"item": item, "reason": "placement gap"} for item in result["gaps"][:5]],
        "scores": {"placement_level": CEFR_SCORE[result["cefr_estimate"]]},
    }
    save_learning_feedback(session_id, language_code, f"placement-{modality}", evidence_analysis, user_id=uid)
    _save_profile_level(language_code, result, modality, uid)

    return {
        "session_id": session_id,
        "language_code": language_code,
        "language_name": name,
        "modality": modality,
        **result,
        "certified": False,
    }
