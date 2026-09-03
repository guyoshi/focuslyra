# Feature Status

This file is the source of truth for what the current MVP actually does. UI existence does not mean a feature is complete.

Legend:

- ✅ functional: real end-to-end behaviour exists after its stated local setup;
- 🟡 partial: useful foundation exists, but important behaviour is still incomplete;
- ⬜ planned: shell/design exists, but it is not yet a real learning feature.

## Current milestone — 0.6 adaptive study

The first five core blocks are now connected:

1. learner-owned language settings;
2. adaptive daily Session Planner;
3. dynamic Speak/Write and generated activities;
4. local Whisper + Kokoro audio path;
5. controlled-reference Pronunciation Engine v1.

The free local stack can be configured with `finish_local_setup.bat` after the base Python setup exists.

## Learn

### Dashboard — ✅/🟡

Functional:
- renders learner-scoped language profiles;
- normal and minimum-day entry points;
- the daily planner uses real priorities, study recency and stored evidence;
- study plan allocation is generated from learner data.

Still incomplete:
- overall progress percentages shown on language cards are still prototype values;
- dashboard plan preview currently shares the Study endpoint and should later use a lightweight plan-only endpoint.

### Session Planner — ✅ v1

Functional:
- learner-specific priority/status;
- active vs maintenance languages;
- recent session frequency;
- days since last practice;
- recent review targets;
- recent skill evidence;
- normal and minimum-day session durations;
- distribution across Speak, Listen, Write, Read and Pronounce;
- planner remains deterministic and usable even if the LLM is temporarily unavailable.

The planner decides **what needs practice**. The Activity Engine decides **how to present it**.

### Study — ✅/🟡

Pressing `Start today's session` now creates a real plan and generated activity sequence. Activities advance through the plan and save evidence after analysed attempts.

A learner can also request another activity wrapper without discarding the current learning target.

#### Speak — ✅ v1

After Qwen + Whisper local setup:
- activity generated for the selected language/current learner state;
- browser microphone recording;
- original recording preserved locally;
- Whisper local transcription;
- Qwen local language assessment;
- corrections/scores/retrieval targets stored as learner evidence;
- continue to the next planned activity.

Not implemented:
- true low-latency realtime AI voice conversation.

#### Write — ✅ v1

After Qwen setup:
- dynamic prompt per language;
- original learner response preserved;
- local AI assessment;
- corrections/scores/retrieval targets stored;
- no Spanish-specific hard-coded analysis path.

#### Listen — ✅ v1 where a voice engine is available

Functional:
- adaptive listening passage generation;
- target passage hidden before the attempt;
- Kokoro persistent local WAV generation/caching for supported languages;
- configured listening voice profile;
- browser/system voice fallback;
- learner comprehension response analysed by Qwen;
- transcript reveal after the attempt.

Limitations:
- Kokoro does not cover every language currently configured in Focuslyra;
- German/Arabic can use browser/system speech until another persistent local TTS engine such as Piper is added.

#### Read — ✅ v1

Functional:
- adaptive target-language passage generation;
- learner comprehension response;
- Qwen assessment aware that the modality is reading comprehension;
- RTL direction support is available from the language catalogue.

The richer vocabulary/concept-aware reading generator is a later milestone.

#### Pronounce — ✅/🟡 v1

Controlled-reference pronunciation practice is now functional after Whisper + Kokoro + pronunciation setup.

V1 measures real signals rather than asking a text model to guess pronunciation:
- learner original audio;
- Whisper controlled-sentence intelligibility;
- duration/timing similarity;
- voiced/quiet-frame rhythm similarity;
- broad pitch-contour/prosody-shape similarity;
- local reference WAV generated through the selected reference voice;
- results stored as learner evidence over time.

Important limitation:
- `practice_similarity` is **not** a native-accent percentage;
- exact sound/phoneme accuracy is deliberately `null` until forced alignment and language/accent-specific calibration ranges are implemented;
- therefore Focuslyra v1 must not claim that a specific `/θ/`, vowel or consonant is correct/incorrect from the global score alone.

### Review — ⬜ planned shell

Evidence/review targets already exist and the Session Planner can feed them back into future activities, but the dedicated Review screen does not yet run the real spaced-repetition scheduler.

### Progress — ⬜ planned shell

Evidence is real; the visible Progress dashboard is not yet computed from that evidence. Current progress numbers are prototype values.

## Memory

### Concepts — ⬜ planned shell

The multilingual concept architecture is designed, including:
- one concept across languages;
- recognition vs production evidence;
- emoji-first visual policy;
- reusable global image/audio assets.

The displayed example is still static. Persistent concept CRUD/scheduler integration is pending.

### Sources — 🟡 partial

Functional backend foundation:
- configured read-only Git sources;
- Git source sync service.

Missing:
- full source-management UI;
- indexing/chunking;
- semantic retrieval/RAG;
- automatic interest-memory use during activity generation.

## Settings

### Learner profile — ✅

- learner-scoped profile;
- native language;
- normal/minimum session duration;
- learning focus;
- attention strategy;
- accent importance.

### Languages — ✅ v1

The global `data/languages.json` is now a learner-neutral catalogue.
Learner-specific fields live in the learner profile:
- priority;
- active/maintenance/parked state;
- target variety/accent;
- current learner state;
- goals.

This prevents one future user's priorities from modifying another user's language catalogue.

### Google Calendar — ✅ after OAuth configuration

Implemented:
- local OAuth credential storage;
- Google account connection;
- Focuslyra-owned calendar;
- availability calendar selection;
- free-slot search;
- earliest-slot scheduling;
- study reminders;
- upcoming Focuslyra events.

Still pending:
- automatic scheduling directly from the new daily Session Planner without user action.

### Voices — ✅/🟡

Implemented:
- voice profile per language;
- default/reference/conversation/listening roles;
- engine and speed selection;
- browser/system voices;
- Kokoro local voice discovery;
- persistent local WAV cache for supported languages.

More local engines can be added through the provider/router architecture.

### AI — 🟡

Functional:
- Ollama/Qwen local activity generation and assessment;
- paid AI remains disabled by default;
- rule-based multilingual activity fallback when Ollama cannot answer.

Still not implemented end-to-end:
- Gemini free fallback;
- Groq free fallback;
- Claude/OpenAI routing;
- task/cost/quality-aware provider orchestration.

## Core infrastructure

### Learner memory/evidence — ✅ foundation

- user-scoped SQLite sessions;
- writings/responses;
- AI feedback;
- evidence events;
- recent evidence fed into later assessments;
- retrieval targets fed into later planned activities.

A formal spaced-repetition/mastery scheduler is the next major memory milestone.

### Commercial-ready seams — ✅ foundation

- deployment mode configuration;
- current-user abstraction;
- user-scoped DB records;
- user-scoped profile/language/voice/media data;
- configurable data/private/media roots;
- replaceable AI/TTS direction;
- secrets/private media excluded from Git.

See `COMMERCIAL_FOUNDATIONS.md`.

## What "usable" means now

After running the free local setup, Focuslyra 0.6 can already be used as a daily adaptive study loop:

`planner → generated activity → learner speaks/writes/listens/reads/pronounces → local analysis → evidence → next planned activity`

It is **not yet the complete Focuslyra product**. Review, real Progress, Concepts/visual vocabulary, Memory RAG, automatic Calendar scheduling and mobile/PWA remain later milestones.
