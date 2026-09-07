from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from functools import lru_cache
from typing import Any

from .concept_service import save_concept
from .db import connection
from .profile_service import load_profile
from .providers import AIProviderError, ollama_json
from .runtime import current_user_id


class JapaneseServiceError(RuntimeError):
    pass


_JAPANESE_RE = re.compile(r"[\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")
_KANJI_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")
_SPACE_BEFORE_PUNCT = re.compile(r"\s+([、。！？!?.,:;])")
_SPACE_AFTER_OPEN = re.compile(r"([「『（(【［])\s+")
_SPACE_BEFORE_CLOSE = re.compile(r"\s+([」』）)】］])")

# Small offline safety net. Contextual conversion is delegated to local Qwen
# when available, but beginner words remain usable with no model response.
_FALLBACK_WORDS: dict[str, tuple[str, str]] = {
    "にほんご": ("日本語", "japonês"),
    "にほん": ("日本", "Japão"),
    "がっこう": ("学校", "escola"),
    "せんせい": ("先生", "professor(a)"),
    "がくせい": ("学生", "estudante"),
    "でんしゃ": ("電車", "comboio/trem"),
    "じかん": ("時間", "tempo / hora"),
    "きょう": ("今日", "hoje"),
    "あした": ("明日", "amanhã"),
    "きのう": ("昨日", "ontem"),
    "わたし": ("私", "eu"),
    "かたな": ("刀", "espada japonesa / katana"),
    "くるま": ("車", "carro"),
    "みず": ("水", "água"),
    "やま": ("山", "montanha"),
    "かわ": ("川", "rio"),
    "ひと": ("人", "pessoa"),
    "ねこ": ("猫", "gato"),
    "いぬ": ("犬", "cão"),
    "たべる": ("食べる", "comer"),
    "のむ": ("飲む", "beber"),
    "みる": ("見る", "ver"),
    "いく": ("行く", "ir"),
    "くる": ("来る", "vir"),
    "かえる": ("帰る", "voltar para casa"),
    "きく": ("聞く", "ouvir / perguntar"),
    "はなす": ("話す", "falar"),
    "よむ": ("読む", "ler"),
    "かく": ("書く", "escrever"),
    "かう": ("買う", "comprar"),
    "おおきい": ("大きい", "grande"),
    "ちいさい": ("小さい", "pequeno"),
    "すき": ("好き", "gostar / favorito"),
}


@lru_cache(maxsize=1)
def _kakasi():
    try:
        import pykakasi
    except ImportError as exc:
        raise JapaneseServiceError(
            "Japanese romaji support is missing. Restart Focuslyra after installing the updated requirements."
        ) from exc
    return pykakasi.kakasi()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def contains_japanese(text: str) -> bool:
    return bool(_JAPANESE_RE.search(text or ""))


def contains_kanji(text: str) -> bool:
    return bool(_KANJI_RE.search(text or ""))


def romanise_japanese(text: str) -> str:
    clean = str(text or "").strip()
    if not clean:
        return ""
    if not contains_japanese(clean):
        return clean

    try:
        converted = _kakasi().convert(clean)
    except Exception as exc:
        raise JapaneseServiceError(f"Could not convert Japanese text to romaji: {exc}") from exc

    pieces: list[str] = []
    for item in converted:
        if not isinstance(item, dict):
            continue
        original = str(item.get("orig") or "")
        hepburn = str(item.get("hepburn") or original)
        pieces.append(hepburn if contains_japanese(original) else original)

    romaji = " ".join(piece.strip() for piece in pieces if piece.strip())
    romaji = _SPACE_BEFORE_PUNCT.sub(r"\1", romaji)
    romaji = _SPACE_AFTER_OPEN.sub(r"\1", romaji)
    romaji = _SPACE_BEFORE_CLOSE.sub(r"\1", romaji)
    return re.sub(r"\s{2,}", " ", romaji).strip()


def _clean_kanji_item(item: Any) -> dict[str, str] | None:
    if not isinstance(item, dict):
        return None
    surface = str(item.get("surface") or "").strip()[:80]
    reading = str(item.get("reading") or "").strip()[:120]
    meaning = str(item.get("meaning") or "").strip()[:200]
    kana_source = str(item.get("kana_source") or "").strip()[:120]
    if not surface or not contains_kanji(surface):
        return None
    return {
        "surface": surface,
        "reading": reading,
        "meaning": meaning,
        "kana_source": kana_source,
    }


def _fallback_kanji(text: str) -> dict[str, Any]:
    converted = text
    items: list[dict[str, str]] = []
    for kana, (surface, meaning) in sorted(_FALLBACK_WORDS.items(), key=lambda pair: len(pair[0]), reverse=True):
        if kana not in converted:
            continue
        converted = converted.replace(kana, surface)
        items.append({
            "surface": surface,
            "reading": kana,
            "meaning": meaning,
            "kana_source": kana,
        })
    return {
        "converted_text": converted,
        "kanji": items,
        "note": "Basic local dictionary suggestion. Qwen can provide richer contextual conversion when available.",
        "provider": "focuslyra-japanese-rules",
        "model": "beginner-kanji-v1",
    }


def suggest_kanji(text: str, user_id: str | None = None) -> dict[str, Any]:
    uid = user_id or current_user_id()
    clean = str(text or "").strip()
    if not clean:
        raise JapaneseServiceError("Write some Japanese kana first.")
    if len(clean) > 1200:
        raise JapaneseServiceError("Kanji Assist currently accepts up to 1200 characters at a time.")

    native_language = str(load_profile(uid).get("native_language") or "pt-BR")
    system = f"""
You are the Japanese IME-assist layer inside Focuslyra, not a translator.
The learner writes Japanese using kana. Convert kana words to the kanji that a contemporary Japanese writer would naturally choose IN THIS CONTEXT.
Keep particles, endings and words normally written in kana as kana. Preserve punctuation and meaning. Never rewrite the sentence into a different sentence.
The learner is a beginner in kanji, so expose every kanji expression you introduce with its kana reading and a short meaning in {native_language}.
If a reading is genuinely ambiguous, prefer the most ordinary interpretation from the sentence and mention uncertainty briefly in note.

Return ONLY JSON:
{{
  "converted_text": "natural Japanese with appropriate kanji",
  "kanji": [
    {{"surface": "刀", "reading": "かたな", "meaning": "espada japonesa", "kana_source": "かたな"}}
  ],
  "note": "short learner-facing note or empty string"
}}
Do not include kanji in the list unless that kanji actually appears in converted_text.
""".strip()

    try:
        result = ollama_json(system, json.dumps({"kana_text": clean}, ensure_ascii=False), timeout=45.0)
        converted = str(result.get("converted_text") or "").strip()
        if not converted:
            raise AIProviderError("Local model returned no Japanese conversion.")
        items: list[dict[str, str]] = []
        seen: set[tuple[str, str]] = set()
        for raw in result.get("kanji") or []:
            item = _clean_kanji_item(raw)
            if not item:
                continue
            key = (item["surface"], item["reading"])
            if key in seen:
                continue
            seen.add(key)
            items.append(item)
        return {
            "converted_text": converted,
            "kanji": items[:24],
            "note": str(result.get("note") or "").strip()[:500],
            "provider": "ollama",
            "model": "qwen-local",
        }
    except AIProviderError:
        return _fallback_kanji(clean)


def learn_kanji(
    surface: str,
    reading: str,
    meaning: str,
    source_text: str | None = None,
    user_id: str | None = None,
) -> dict[str, Any]:
    uid = user_id or current_user_id()
    surface = str(surface or "").strip()[:80]
    reading = str(reading or "").strip()[:120]
    meaning = str(meaning or "").strip()[:200]
    if not surface or not contains_kanji(surface):
        raise JapaneseServiceError("Choose a kanji expression first.")
    if not reading:
        raise JapaneseServiceError("A kana reading is required before this kanji can enter Review.")

    codepoints = "-".join(f"{ord(ch):x}" for ch in surface)
    concept = save_concept(
        {
            "concept_key": f"ja-kanji-{codepoints}"[:120],
            "label": meaning or surface,
            "visual": "",
            "visual_kind": "none",
            "senses": [meaning] if meaning else [],
            "expressions": {
                "ja-JP": {
                    "text": surface,
                    "reading": reading,
                }
            },
            "notes": "Added from Japanese Input → Kanji Assist. Recognition and production should be tested separately.",
        },
        uid,
    )

    review_answer = reading + (f" · {meaning}" if meaning else "")
    payload = {
        "reason": "Recall this kanji expression without relying on romaji.",
        "review_prompt": f"{surface} — what is the reading and meaning?",
        "review_answer": review_answer,
        "surface": surface,
        "reading": reading,
        "meaning": meaning,
        "source_text": str(source_text or "")[:1000],
        "source": "japanese-input",
    }
    with connection() as conn:
        conn.execute(
            """
            INSERT INTO evidence_events(
                user_id, session_id, language_code, item_id, modality,
                event_type, score, payload_json, created_at
            ) VALUES (?, NULL, 'ja-JP', ?, 'reading', 'review_target', NULL, ?, ?)
            """,
            (uid, surface, json.dumps(payload, ensure_ascii=False), _now()),
        )
        conn.commit()

    return {
        "surface": surface,
        "reading": reading,
        "meaning": meaning,
        "concept": concept,
        "review_added": True,
    }
