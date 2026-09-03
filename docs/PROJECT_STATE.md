# Project State

Last updated: 2026-09-03

## Product

Name: **Focuslyra**

Focuslyra is a local-first language-learning workspace with adaptive study, learner-owned memory, multimodal evidence and replaceable AI/audio providers.

Current milestone: **0.6 adaptive Study**.

## Implemented

### Application / architecture

- FastAPI local backend and browser frontend.
- Windows setup/run scripts with dependency-change detection.
- `finish_local_setup.bat` for the complete free local learning stack.
- GitHub smoke-test workflow.
- Paid AI disabled by default.
- Current-user/deployment seam for future hosted/authenticated use.
- User-scoped DB, profile, language settings, voice preferences and media.
- Global language catalogue separated from learner-specific priorities/goals/target varieties.

### Adaptive learning loop

- Session Planner v1 uses learner priority, active/maintenance state, recency, recent practice frequency, review targets and recent skill evidence.
- Normal and minimum-day plans.
- Dynamic Activity Engine for Speak, Listen, Write, Read and Pronounce.
- Qwen/Ollama local activity generation with multilingual rule-based fallback.
- Hidden retrieval targets can return in later activities without being revealed first.
- Study advances through a planned sequence and stores new evidence after attempts.

### Speaking / writing / reading / listening

- Dynamic speaking prompts in the selected language.
- Browser microphone recording and original-audio persistence.
- Faster-Whisper local transcription.
- Qwen local assessment of spoken transcripts.
- Dynamic writing prompts and local assessment.
- Dynamic reading passages with comprehension assessment.
- Dynamic listening passages with transcript hidden before the attempt.
- Local Kokoro persistent WAV generation/cache for supported languages.
- Browser/system TTS fallback for languages not covered by the current local TTS provider.

### Pronunciation v1

- Local Praat/Parselmouth acoustic analysis.
- Controlled sentence practice against a known local TTS reference.
- Whisper intelligibility comparison.
- Timing similarity.
- voiced/quiet rhythm similarity.
- broad pitch-contour/prosody-shape similarity.
- pronunciation evidence saved to the learner history.

Important: exact phoneme-by-phoneme accuracy is intentionally not claimed yet. Forced alignment and target-specific calibration remain future work.

### Voices

- Per-language voice profiles.
- default/reference/conversation/listening voice roles.
- speed and engine choice.
- local Kokoro voice discovery.
- browser/system fallback.
- persistent generated-audio cache.

### Calendar

- Google Calendar OAuth integration.
- Focuslyra-owned study calendar.
- availability calendar selection.
- free-slot search and earliest-slot scheduling.
- reminders and upcoming events.

### Memory/data foundation

- sessions, writings/responses, AI feedback and evidence events in SQLite.
- recent learner evidence feeds later assessment/planning.
- read-only Git source sync foundation.
- Tinkos/book sources configured as interest-memory candidates.

## Still incomplete

These remain later milestones rather than part of 0.6:

- dedicated spaced-repetition Review engine/UI;
- evidence-derived Progress dashboard;
- persistent Concepts/visual-vocabulary database;
- Memory source indexing/chunking/RAG and automatic use in activity generation;
- automatic Calendar scheduling directly from the Session Planner;
- English diagnostic inside Focuslyra;
- phoneme alignment and language/accent-specific pronunciation calibration;
- mobile/PWA access and PC↔phone secure connection/sync;
- external free-provider fallbacks such as Gemini/Groq;
- realtime low-latency AI voice conversation.

See `FEATURE_STATUS.md` for the detailed truth table.

## Local setup

For the currently implemented free local learning loop:

1. `git pull`
2. run `finish_local_setup.bat` once;
3. run `run.bat` for normal use;
4. Google OAuth is only required if Calendar integration is desired.

The unified setup prepares/validates:

- Ollama + Qwen3 4B;
- Faster-Whisper;
- Kokoro ONNX;
- Praat/Parselmouth pronunciation dependencies.

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
10. Adding a language should primarily be configuration/data, not a core rewrite.
11. Mobile/hosted versions must reuse the same learning domain/backend contracts.
12. Do not build billing/cloud infrastructure before needed; preserve interfaces now instead.

## Next milestone

Build the memory layer around the now-functional adaptive Study loop:

```text
Review scheduler
      +
Concept vocabulary
      +
Memory/RAG
      +
Evidence-derived Progress
      +
Calendar automation
```

After that, package the same backend contracts into the first Focuslyra PWA/mobile client.
