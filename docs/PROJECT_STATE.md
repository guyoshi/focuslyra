# Project State

Last updated: 2026-09-03

## Product

Name: **Focuslyra**

Focuslyra is a local-first language-learning workspace with adaptive study, learner-owned memory, multimodal evidence and replaceable AI/audio providers.

The current priority is proving the learning loop locally before building cloud/commercial infrastructure.

## Implemented foundation

### Application

- FastAPI local backend.
- Browser frontend.
- Windows setup/run scripts with dependency-change detection.
- GitHub smoke-test workflow.
- Paid AI disabled by default.

### Local learning intelligence

- Ollama/Qwen local assessment path.
- Writing analysis with structured feedback.
- Browser microphone recording.
- Local recording persistence.
- Faster-Whisper local transcription path.
- Speech transcript -> Qwen learning analysis path.
- AI feedback and evidence-event persistence in SQLite.
- Recent learner evidence fed back into later analysis.

### Audio/pronunciation foundation

- Local Kokoro ONNX TTS service.
- Persistent WAV cache.
- TTS provider/routing foundation.
- Per-language configurable voice profiles.
- Separate reference/conversation/listening/default voice purposes.
- Browser/system TTS fallback.
- RP candidate calibration infrastructure.
- Praat/Parselmouth acoustic baseline service.

### Calendar

- Google Calendar OAuth integration.
- Focuslyra-owned study calendar.
- Read-only availability selection.
- Free-slot search.
- Smart earliest-slot scheduling.
- Calendar reminders.

### Memory/data

- Learner profile and initial language profiles.
- User-scoped database records (`user_id`).
- User context/deployment seam for future authenticated/hosted mode.
- User-scoped voice preferences.
- Configurable local data/private/media roots.
- Read-only Git source sync foundation.
- Tinkos and book repositories configured as interest-memory sources.

### Product architecture

- Commercial-readiness guardrails documented.
- Main navigation grouped into Learn / Library / Settings.
- AI providers intended to remain replaceable.
- Learner/private data separated from distributable Git content.

## Still incomplete

The following visible areas are not yet complete learning features:

- adaptive daily planner on Dashboard;
- dynamic Study activity generation/orchestration;
- end-to-end Listening exercises;
- adaptive Reading exercises;
- reliable phoneme/accent scoring and alignment;
- real spaced-repetition Review engine;
- evidence-derived Progress dashboard;
- persistent dynamic Concept database;
- Git source indexing/retrieval/RAG;
- automatic use of interest memory in lessons;
- English diagnostic inside the app;
- mobile/PWA access;
- external free-provider fallbacks (Gemini/Groq) in the learning flow.

See `FEATURE_STATUS.md` for the detailed truth table.

## Current local setup dependencies

For the complete currently implemented local loop, the machine needs:

1. Python environment via `run.bat` / `setup.bat`;
2. Ollama + Qwen via `configure_free_ai.bat`;
3. Whisper via `configure_free_audio.bat`;
4. Kokoro local TTS via `configure_local_tts.bat` (optional until voice/listening work);
5. pronunciation acoustic dependencies via `configure_pronunciation.bat` (optional until pronunciation work);
6. Google OAuth credentials only if Calendar integration is desired.

## Non-negotiable rules

1. Paid AI is opt-in and off by default.
2. Focuslyra remains useful without paid providers.
3. Learner data belongs to the learner, not an AI vendor.
4. Durable personal records must be user-scoped.
5. External repositories are read-only learning context by default.
6. Generated exercises based on books/game projects are non-canon.
7. Speaking/listening are the primary learning goals.
8. Recognition and production are tracked separately.
9. Concept visuals prefer emoji/reuse before image generation.
10. Adding a new language should primarily be configuration/data, not a code rewrite.
11. Mobile/hosted versions must reuse the same learning domain rather than becoming separate products.
12. Do not build billing/cloud infrastructure before it is actually needed; preserve interfaces now instead.

## Immediate next product milestone

Finish the local audio stack on Gui's PC, then make **Study dynamic**:

```text
learner evidence + goals + due review items
            ↓
       session planner
            ↓
  selected activity / language
            ↓
 speak/listen/write/read/pronounce
            ↓
         evidence
            ↓
       next session
```

After this loop is real, Review, Progress, Concepts and Calendar scheduling can all consume the same planner/evidence model instead of static prototype values.
