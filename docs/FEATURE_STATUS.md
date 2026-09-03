# Feature Status

This file is the source of truth for what the current MVP actually does. UI existence does not mean a feature is complete.

Legend:

- ✅ functional: real end-to-end behaviour exists after its stated local setup;
- 🟡 partial: useful foundation exists, but important behaviour is still prototype/static;
- ⬜ planned: shell or design exists, but it is not yet a real learning feature.

## Learn

### Dashboard — 🟡 partial

Functional:
- renders configured language profiles;
- opens Study and 10-minute mode.

Still prototype:
- today's minutes/language allocation is static;
- progress numbers are not yet calculated from evidence;
- adaptive daily planner is not yet choosing the session.

### Study — 🟡 partial, with real working components

#### Speak — ✅/🟡

Functional after local audio + Ollama setup:
- browser microphone recording;
- local recording persistence;
- Whisper local transcription;
- Qwen/Ollama language analysis;
- feedback/evidence persistence;
- original audio is preserved for later pronunciation analysis.

Still prototype:
- the displayed Spanish hotel task is hard-coded;
- the next generated activity is not yet driving the whole Study UI automatically;
- real-time AI conversation is not implemented.

#### Write — ✅/🟡

Functional after Ollama setup:
- preserves learner response;
- local AI analysis;
- scores/corrections/review targets;
- evidence persistence;
- next-activity payload.

Still prototype:
- the visible Spanish prompt is hard-coded;
- curriculum/session generation is not yet dynamic.

#### Listen — ⬜ planned shell

Current button demonstrates the intended flow only.

Local persistent TTS/cached WAV infrastructure exists separately, but listening exercises are not yet generated, scored and scheduled end-to-end.

#### Read — ⬜ planned shell

Current Japanese text is static. Adaptive reading generation from learner vocabulary/memory is not implemented yet.

#### Pronounce — 🟡 partial

Available/being configured:
- local acoustic measurements through Praat/Parselmouth;
- local TTS reference voice calibration infrastructure;
- persistent WAV generation/caching;
- configurable voice profile per language.

Not complete:
- phoneme alignment;
- sound-by-sound target ranges;
- reliable accent/phoneme scoring;
- longitudinal pronunciation dashboard.

### Review — ⬜ planned shell

The UI exists, but the buttons do not yet run the real spaced-repetition/evidence scheduler.

### Progress — ⬜ planned shell

The UI exists. Current scores are prototype values, not learner-derived measurements.

## Library

### Concepts — ⬜ planned shell

The multilingual concept model is designed, including emoji-first visuals, but the displayed DOG concept is static.

Needed:
- persistent concept store;
- language expressions/senses;
- recognition vs production evidence;
- scheduler integration;
- reusable global images/audio.

### Memory — 🟡 partial

Functional backend foundation:
- configured read-only Git sources;
- source sync service exists.

Still missing:
- user-facing source configuration;
- indexing/chunking;
- semantic retrieval/RAG;
- automatic use in exercise generation.

## Settings

### Google Calendar — ✅ after OAuth configuration

Implemented:
- local OAuth credential storage;
- Google account connection;
- Focuslyra-owned calendar;
- availability calendar selection;
- free-slot search;
- smart earliest-slot scheduling;
- reminders on study events;
- upcoming Focuslyra events.

Not yet automatic:
- Learning Engine does not yet calculate the required session and schedule it without user action.

### Voices — ✅/🟡 after local TTS configuration

Implemented:
- per-language voice profiles;
- engine choice;
- default/reference/conversation/listening voice choices;
- speed choice;
- browser/system voice discovery;
- local Kokoro voice discovery;
- preview;
- user-scoped persistence.

Coverage depends on installed voice engines. Additional TTS engines can be added later through the provider/router layer.

### AI — 🟡

Functional:
- detects local Ollama/provider status;
- Qwen local is used by the Learning Engine;
- paid AI remains disabled by default.

Not implemented end-to-end:
- Gemini free fallback;
- Groq free fallback;
- Claude/OpenAI provider calls;
- automatic provider routing based on task/cost/quality.

## Core infrastructure

### Learner memory/evidence — ✅ foundation

- SQLite sessions;
- writings;
- AI feedback;
- evidence events;
- recent evidence fed back into later local AI analysis;
- records are now user-scoped through `user_id`.

The actual spaced repetition/mastery algorithm is still pending.

### Commercial-ready seams — ✅ foundation

- deployment mode configuration;
- current-user context abstraction;
- user-scoped database records;
- user-scoped voice preferences;
- configurable data/private/media roots;
- replaceable AI/TTS direction;
- private secrets/media excluded from Git.

See `COMMERCIAL_FOUNDATIONS.md`.

## What "usable" means today

Once Qwen/Ollama and Whisper are configured, Focuslyra can already be used to record or write a response, analyse the language locally, save evidence and receive feedback/next-task guidance.

It is **not yet a complete adaptive language course**. The next major product milestone is to make the Study screen dynamically choose activities from learner evidence and to make Review/Progress/Concepts consume that same evidence instead of showing prototype content.
