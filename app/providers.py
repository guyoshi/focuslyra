from __future__ import annotations

import os
from dataclasses import dataclass, asdict


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


def get_provider_statuses() -> list[dict]:
    paid = paid_ai_allowed()
    providers = [
        ProviderStatus(
            id="ollama",
            label="Ollama",
            kind="text/local",
            configured=bool(os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")),
            potentially_paid=False,
            enabled=True,
            note="Local model provider. No per-token bill.",
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
