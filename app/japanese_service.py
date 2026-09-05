from __future__ import annotations

import re
from functools import lru_cache


class JapaneseServiceError(RuntimeError):
    pass


_JAPANESE_RE = re.compile(r"[\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")
_SPACE_BEFORE_PUNCT = re.compile(r"\s+([、。！？!?.,:;])")
_SPACE_AFTER_OPEN = re.compile(r"([「『（(【［])\s+")
_SPACE_BEFORE_CLOSE = re.compile(r"\s+([」』）)】］])")


@lru_cache(maxsize=1)
def _kakasi():
    try:
        import pykakasi
    except ImportError as exc:
        raise JapaneseServiceError(
            "Japanese romaji support is missing. Restart Focuslyra after installing the updated requirements."
        ) from exc
    return pykakasi.kakasi()


def contains_japanese(text: str) -> bool:
    return bool(_JAPANESE_RE.search(text or ""))


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
