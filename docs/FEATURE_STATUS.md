# Feature Status

This file is the source of truth for what the current MVP actually does. UI existence does not mean a feature is complete.

Legend:

- ✅ functional: real end-to-end behaviour exists after its stated local setup;
- 🟡 partial: useful implementation exists, with known limits;
- ⬜ planned: not yet a real feature.

## Current milestone — adaptive learning core + memory/review/diagnostic

Core blocks 1–11 are now connected at a usable personal-MVP level:

1. learner-owned language settings;
2. adaptive daily Session Planner;
3. dynamic multimodal Study;
4. local Whisper + Kokoro audio path;
5. controlled-reference Pronunciation Engine v1;
6. adaptive spaced Review;
7. persistent multilingual Concepts;
8. local Git-source indexing/retrieval for interest memory;
9. evidence-derived Progress;
10. Session Planner → Google Calendar scheduling;
11. in-app English diagnostic.

The free local stack can be configured with `finish_local_setup.bat` after the base Python setup exists.

## Learn

### Dashboard — ✅ v1

Functional:
- learner-scoped language profiles;
- normal and minimum-day entry points;
- lightweight plan preview that does not invoke Qwen;
- suggested rhythm calculated from the actual Session Planner;
- language progress bars replaced by real evidence summaries;
- evidence confidence shown separately so a small sample is not presented as certainty.

### Session Planner — ✅ v1

Uses:
- learner-specific priority/status;
- active vs maintenance languages;
- session recency/frequency;
- review targets;
- recent skill evidence;
- normal/minimum-day duration;
- learner goals.

Review is an intention/target, not a ghost Study modality. Due retrieval targets are hidden inside suitable Speak/Listen/Write/Read/Pronounce activities while the dedicated Review screen handles explicit spaced repetition.

### Study — ✅/🟡

The daily plan drives a generated activity sequence. Attempts feed evidence back into later plans.

#### Speak — ✅ v1
- adaptive prompt;
- microphone recording;
- original audio preserved;
- local Whisper transcription;
- Qwen language assessment;
- corrections/scores/retrieval targets persisted.

Not yet implemented: true low-latency realtime AI voice conversation.

#### Write — ✅ v1
- adaptive prompt;
- original response preserved;
- local assessment;
- evidence/retrieval targets saved.

#### Listen — ✅ v1 where a voice engine is available
- generated target-language listening passage;
- transcript hidden before attempt;
- Kokoro persistent WAV/cache for supported languages;
- configured listening voice;
- browser/system fallback;
- comprehension answer assessed;
- transcript reveal.

German/Arabic currently depend on browser/system speech until another persistent local TTS engine is added.

#### Read — ✅ v1
- generated target-language passage;
- comprehension response and assessment;
- RTL support from language metadata.

#### Pronounce — ✅/🟡 v1
Controlled-reference practice measures real audio signals:
- sentence intelligibility from local transcription;
- duration/timing;
- voiced/quiet-frame rhythm;
- broad pitch/prosody shape;
- comparison with locally generated reference audio;
- longitudinal evidence storage.

Important limit: exact phoneme accuracy remains deliberately unavailable until forced alignment and target-accent calibration are implemented. `practice_similarity` is not a native-accent percentage.

### Review — ✅ v1

The dedicated Review screen now:
- materialises real `review_target` evidence into persistent review items;
- shows only due items;
- requires retrieval before reveal;
- accepts Again / Hard / Good / Easy;
- changes interval/ease/repetition state;
- stores each review result back as learner evidence;
- is user-scoped.

This is a lightweight SM-2-style scheduler. It is intentionally simpler than a future richer mastery model that distinguishes every concept/sense/modal evidence stream.

### Progress — ✅ v1

Computed from real learner records:
- session totals and recency;
- recent skill evidence;
- modality averages;
- overall evidence score;
- evidence confidence/sample depth;
- review activity;
- concept/session totals.

Scores are Focuslyra evidence summaries, not certified CEFR ratings.

### English deep diagnostic — ✅/🟡 v1

Lives inside Progress and includes six sections:
1. spontaneous speech;
2. circumlocution/lexical retrieval;
3. grammar automaticity;
4. spontaneous writing;
5. blind RP listening;
6. controlled RP pronunciation baseline.

Responses are preserved and analysed through the same local evidence stack. The final map synthesises:
- spontaneous fluency;
- grammar automaticity;
- active vocabulary;
- lexical retrieval;
- native-speed listening;
- RP sound perception where evidence supports it;
- RP pronunciation/prosody;
- writing control.

It does not claim a certified CEFR level or unsupported phoneme precision.

## Memory

### Concepts — ✅/🟡 v1

Persistent, user-scoped concept store supports:
- concept key/meaning;
- emoji/visual field;
- multiple senses;
- expressions per language;
- readings/transliterations where useful;
- notes;
- Qwen enrichment across configured languages.

Concepts model meaning rather than forcing one-to-one word translation. Audio can use the existing language TTS/voice layer; richer concept-specific recognition/production mastery remains a later refinement.

### Sources / interest memory — ✅/🟡 v1

Functional:
- configured read-only Git sources;
- local clone/sync;
- include/exclude rules;
- chunking/indexing of text source files;
- local weighted lexical retrieval;
- source/path/commit provenance retained;
- test search in Memory UI;
- relevant source excerpts passed to adaptive activity generation;
- prompts explicitly protect source canon and forbid generated exercises from becoming canon.

Current retrieval is lightweight local lexical retrieval, not embedding/vector semantic search. It can be upgraded behind the same interface later.

## Settings

### Learner profile — ✅
User-scoped learner profile, durations, focus, attention strategy and accent importance.

### Languages — ✅ v1
Global catalogue remains separate from learner priority/status/current state/goals.

### Google Calendar — ✅/🟡
Existing OAuth/free-busy/Focuslyra calendar behaviour remains functional.

New adaptive scheduling:
- uses the actual Session Planner duration;
- finds the earliest free slot in the learner's configured window;
- prevents duplicate Focuslyra plan events for the same date;
- supports normal/minimum plan mode;
- supports optional auto-schedule-on-app-open for today + configured days ahead.

Important limitation: this is not a background daemon. If Focuslyra is closed, it does not wake the PC to create new future events. Once an event is created, Google Calendar and phone notifications work independently of Focuslyra.

### Voices — ✅/🟡
Per-language engine/reference/conversation/listening/default voice + speed, local Kokoro and system fallback.

### AI — 🟡
Ollama/Qwen local generation and assessment are functional. Paid AI remains opt-in/off. External free-provider failover is not yet end-to-end.

## Core infrastructure

### Learner memory/evidence — ✅ foundation
User-scoped SQLite sessions, responses, feedback, evidence, review state, concepts and diagnostic attempts.

### Commercial-ready seams — ✅ foundation
Deployment/user/provider/storage boundaries remain preserved. See `COMMERCIAL_FOUNDATIONS.md`.

## What "usable" means now

After local setup, Focuslyra can support a real personal daily loop:

`planner → activity → response → local analysis → evidence → spaced review → progress → next plan`

It can also index configured interest repositories, personalise generated activities from those sources, run the English diagnostic and schedule the calculated study duration into Google Calendar.

Still outside this milestone:
- exact phoneme/forced-alignment pronunciation layer;
- realtime voice conversation;
- richer concept mastery/sense scheduling;
- embedding/vector RAG;
- cloud sync/authentication;
- PWA/mobile access;
- commercial billing/hosted infrastructure.
