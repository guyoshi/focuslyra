from __future__ import annotations

import json
import os
from dataclasses import dataclass, asdict
from urllib.error import URLError
from urllib.request import Request, urlopen


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


def _ollama_status() -> tuple[bool, str]:
    base_url = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")
    requested_model = os.getenv("OLLAMA_MODEL", "").strip()

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
        # Ollama may return a fully qualified tag such as qwen3:4b even if the
        # configured value omitted a tag. A prefix match keeps this friendly.
        if not any(name == requested_model or name.startswith(f"{requested_model}:") for name in names):
            return False, f"Ollama is running, but the configured model '{requested_model}' is not installed."

    active_model = requested_model or sorted(names)[0]
    return True, f"Local model ready: {active_model}. No per-token bill."


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
