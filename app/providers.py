from __future__ import annotations

import json
import os
from dataclasses import dataclass, asdict
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class AIProviderError(RuntimeError):
    pass


@dataclass
class ProviderStatus:
    id: str
    label: str
    kind: str
    configured: bool
    potentially_paid: bool
    enabled: bool
    note: str


def paid_ai_allowed() -> bool:
    return os.getenv("ALLOW_PAID_AI", "false").strip().lower() in {"1", "true", "yes", "on"}


def _bool_env(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _int_env(name: str, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(os.getenv(name, str(default)) or default)
    except (TypeError, ValueError):
        value = default
    return max(minimum, min(maximum, value))


def _ollama_config() -> tuple[str, str]:
    base_url = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")
    model = os.getenv("OLLAMA_MODEL", "qwen3:4b").strip() or "qwen3:4b"
    return base_url, model


def _ollama_status() -> tuple[bool, str]:
    base_url, requested_model = _ollama_config()

    try:
        request = Request(f"{base_url}/api/tags", headers={"Accept": "application/json"})
        with urlopen(request, timeout=1.5) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (OSError, URLError, ValueError, json.JSONDecodeError):
        return False, "Ollama is configured locally, but the server is not reachable yet."

    models = payload.get("models") or []
    names = {
        str(model.get("name", "")).strip()
        for model in models
        if isinstance(model, dict) and model.get("name")
    }

    if not names:
        return False, "Ollama is running, but no local language model is installed yet."

    if requested_model and requested_model not in names:
        if not any(name == requested_model or name.startswith(f"{requested_model}:") for name in names):
            return False, f"Ollama is running, but the configured model '{requested_model}' is not installed."

    return True, f"Local model ready: {requested_model}. No per-token bill."


def _post_ollama(base_url: str, payload: dict[str, Any], timeout: float) -> dict[str, Any]:
    request = Request(
        f"{base_url}/api/chat",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    with urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def ollama_json(system_prompt: str, user_prompt: str, *, timeout: float = 120.0) -> dict[str, Any]:
    """Ask the configured local Ollama model for strict JSON.

    Focuslyra uses Qwen mainly for short structured generation and assessment.
    Qwen 3 can spend a large amount of time in its reasoning mode before it
    emits the small JSON object we actually need, especially on CPU-only
    machines.  Reasoning is therefore disabled by default for this path.  This
    keeps the local-first experience responsive without changing the model or
    sending learner data to a cloud API.
    """
    ready, note = _ollama_status()
    if not ready:
        raise AIProviderError(note)

    base_url, model = _ollama_config()
    think = _bool_env("OLLAMA_THINK", False)
    keep_alive = (os.getenv("OLLAMA_KEEP_ALIVE", "30m") or "30m").strip()
    num_predict = _int_env("OLLAMA_NUM_PREDICT", 900, 128, 4096)
    num_ctx = _int_env("OLLAMA_NUM_CTX", 4096, 2048, 32768)

    payload: dict[str, Any] = {
        "model": model,
        "stream": False,
        "format": "json",
        "think": think,
        "keep_alive": keep_alive,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "options": {
            "temperature": 0.15,
            "num_predict": num_predict,
            "num_ctx": num_ctx,
        },
    }

    try:
        result = _post_ollama(base_url, payload, timeout)
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        # Older Ollama builds did not understand the top-level `think` field.
        # Retry once without it so an older local install keeps working.
        if exc.code == 400 and "think" in detail.lower():
            compatibility_payload = dict(payload)
            compatibility_payload.pop("think", None)
            try:
                result = _post_ollama(base_url, compatibility_payload, timeout)
            except HTTPError as retry_exc:
                retry_detail = retry_exc.read().decode("utf-8", errors="replace")
                raise AIProviderError(f"Ollama returned HTTP {retry_exc.code}: {retry_detail[:300]}") from retry_exc
            except (OSError, URLError, TimeoutError) as retry_exc:
                raise AIProviderError(f"Could not reach the local Ollama model: {retry_exc}") from retry_exc
            except json.JSONDecodeError as retry_exc:
                raise AIProviderError("Ollama returned an invalid server response.") from retry_exc
        else:
            raise AIProviderError(f"Ollama returned HTTP {exc.code}: {detail[:300]}") from exc
    except (OSError, URLError, TimeoutError) as exc:
        raise AIProviderError(f"Could not reach the local Ollama model: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise AIProviderError("Ollama returned an invalid server response.") from exc

    content = ((result.get("message") or {}).get("content") or "").strip()
    if not content:
        raise AIProviderError("Ollama returned an empty answer.")
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError as exc:
        raise AIProviderError("The local model did not return valid structured JSON.") from exc
    if not isinstance(parsed, dict):
        raise AIProviderError("The local model returned the wrong JSON shape.")
    parsed.setdefault("provider", "ollama")
    parsed.setdefault("model", model)
    return parsed


def get_provider_statuses() -> list[dict]:
    paid = paid_ai_allowed()
    ollama_ready, ollama_note = _ollama_status()

    providers = [
        ProviderStatus(
            id="ollama",
            label="Ollama",
            kind="text/local",
            configured=ollama_ready,
            potentially_paid=False,
            enabled=ollama_ready,
            note=ollama_note,
        ),
        ProviderStatus(
            id="gemini",
            label="Gemini",
            kind="text",
            configured=bool(os.getenv("GEMINI_API_KEY")),
            potentially_paid=False,
            enabled=bool(os.getenv("GEMINI_API_KEY")),
            note="Intended for a free-tier text provider configuration.",
        ),
        ProviderStatus(
            id="groq",
            label="Groq",
            kind="text/stt",
            configured=bool(os.getenv("GROQ_API_KEY")),
            potentially_paid=False,
            enabled=bool(os.getenv("GROQ_API_KEY")),
            note="Free-tier/fallback provider when configured.",
        ),
        ProviderStatus(
            id="openai",
            label="OpenAI",
            kind="text/audio/image",
            configured=bool(os.getenv("OPENAI_API_KEY")),
            potentially_paid=True,
            enabled=paid and bool(os.getenv("OPENAI_API_KEY")),
            note="Premium provider. Disabled unless ALLOW_PAID_AI=true.",
        ),
        ProviderStatus(
            id="anthropic",
            label="Claude / Anthropic",
            kind="text",
            configured=bool(os.getenv("ANTHROPIC_API_KEY")),
            potentially_paid=True,
            enabled=paid and bool(os.getenv("ANTHROPIC_API_KEY")),
            note="Optional text provider. Disabled unless paid AI is explicitly allowed.",
        ),
    ]
    return [asdict(provider) for provider in providers]
