# Project State

Last updated: 2026-09-03

## Product

Name: **Focuslyra**

Focuslyra is a local-first language learning workspace with adaptive study, learner-owned memory, multimodal evidence and replaceable AI providers.

## Implemented foundation

- FastAPI local backend.
- Browser frontend with Dashboard, Study, Concepts, Review, Memory, Progress and AI pages.
- Learner profile and seven initial language profiles.
- Browser microphone recording.
- Local recording persistence under `media/recordings/YYYY-MM-DD/` with JSON metadata.
- Writing/session persistence in SQLite.
- Provider status layer with paid AI disabled by default.
- Read-only Git source sync service foundation.
- Tinkos and Dimensoes Infinitas configured as interest-memory sources.
- Windows and Unix setup/launch scripts.
- GitHub smoke-test workflow.

## Not yet implemented

- Actual AI text generation/correction.
- Automatic Ollama installation/model selection.
- Gemini/Groq/OpenAI/Claude API calls.
- Speech transcription.
- Generated listening audio.
- AI pronunciation assessment.
- Local acoustic analysis.
- Evidence-event scoring and review scheduling.
- Repository indexing/retrieval.
- Dynamic concept database/UI.
- English diagnostic inside the app.

## Non-negotiable rules

1. Paid AI is opt-in and off by default.
2. Focuslyra remains usable without paid providers.
3. Learner data belongs to Focuslyra/the learner, not an AI vendor.
4. External repositories are read-only learning context by default.
5. Generated exercises based on books/game projects are non-canon.
6. Speaking/listening are currently the primary learning goals.
7. Recognition and production are tracked separately.
8. Concept visuals prefer emoji/reuse before image generation.
9. Adding a new language should be primarily configuration/data, not a code rewrite.

## Immediate next milestone

Run the MVP on Gui's Windows PC and verify:

- setup script;
- server launch;
- frontend navigation;
- microphone permission;
- recording save;
- writing save;
- provider status;
- Git source authentication/sync behaviour.

After this smoke test, implement the learning engine and first real AI provider.
