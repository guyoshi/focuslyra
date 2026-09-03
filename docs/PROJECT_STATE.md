# Project State

Last updated: 2026-09-03

## Product

Name: **Focuslyra**

Focuslyra is a local-first language-learning workspace with adaptive study, learner-owned memory, multimodal evidence and replaceable AI/audio providers.

Current milestone: **core learning system through blocks 1–11**.

## Implemented

### Application / architecture
- FastAPI local backend + browser frontend.
- Windows setup/run scripts and `finish_local_setup.bat`.
- GitHub smoke-test workflow.
- paid AI disabled by default.
- current-user/deployment seam for future hosted/authenticated use.
- user-scoped learner data/media/preferences.
- global language catalogue separate from learner state.

### Adaptive daily learning
- Session Planner v1 based on priorities, active/maintenance state, recency, frequency, review targets, goals and skill evidence.
- normal/minimum-day plans.
- lightweight plan-only endpoint for Dashboard/Calendar.
- dynamic Speak, Listen, Write, Read and Pronounce activities.
- Qwen/Ollama generation with multilingual rule fallback.
- Whisper transcription and Qwen assessment.
- Kokoro WAV generation/cache + system TTS fallback.
- evidence persists and influences later plans.

### Pronunciation v1
- original audio preservation;
- controlled reference sentence;
- local reference TTS;
- Whisper intelligibility;
- timing/rhythm/broad prosody comparison with Praat/Parselmouth;
- evidence history.

Exact phoneme judgement remains intentionally pending forced alignment/calibration.

### Review v1
- persistent user-scoped review items derived from real retrieval targets;
- due queue;
- reveal-after-retrieval UI;
- Again/Hard/Good/Easy grading;
- adaptive interval/ease/repetition state;
- review results return to the evidence stream.

### Concepts v1
- persistent user concepts;
- meaning/key + visual/emoji;
- senses;
- expressions across languages;
- reading/transliteration fields;
- local Qwen enrichment.

### Interest Memory / RAG v1
- read-only Git source sync;
- include/exclude paths;
- local chunk index with source/path/commit provenance;
- weighted lexical retrieval;
- Memory UI indexing/retrieval test;
- relevant excerpts automatically available to the Activity Engine;
- source canon is explicitly protected from generated exercise content.

### Progress v1
- real sessions/recency;
- skill and modality evidence;
- evidence confidence/sample depth;
- review/concept totals;
- Dashboard and Progress no longer need prototype ability percentages.

### Calendar
- Google OAuth, Focuslyra-owned calendar and free/busy selection;
- manual earliest-slot scheduling;
- adaptive plan scheduling uses the Session Planner's actual duration;
- duplicate-date protection;
- optional auto-schedule-on-app-open for today/future configured days;
- Google phone reminders remain independent after event creation.

### English diagnostic v1
Six in-app sections:
1. spontaneous speech;
2. circumlocution/lexical retrieval;
3. grammar automaticity;
4. spontaneous writing;
5. blind RP listening;
6. controlled RP pronunciation baseline.

Final synthesis produces an ability map without claiming certified CEFR or unsupported phoneme precision.

### Voices
- per-language engine and default/reference/conversation/listening voice roles;
- speed;
- Kokoro discovery/cache;
- system fallback.

## Known limits / future refinements
- exact phoneme forced alignment + accent-specific calibration;
- realtime low-latency AI voice conversation;
- richer concept recognition/production/sense mastery;
- vector/embedding semantic RAG beyond the current lexical local retrieval;
- background Calendar scheduling while Focuslyra/PC is closed;
- external free-provider fallback routing (Gemini/Groq);
- mobile/PWA and secure PC↔phone access;
- cloud sync/authentication for a future hosted/commercial version.

See `FEATURE_STATUS.md` for the detailed truth table.

## Local setup
1. `git pull`
2. run `finish_local_setup.bat` once if the full local stack is not ready;
3. run `run.bat` for normal use;
4. connect Google OAuth only if Calendar is desired;
5. under Memory → Sources, index each repository once before expecting source-based personalisation.

## Non-negotiable rules
1. Paid AI is opt-in and off by default.
2. Focuslyra remains useful without paid providers.
3. Learner data belongs to the learner.
4. Durable personal records are user-scoped.
5. External repositories are read-only learning context by default.
6. Generated exercises based on source projects are non-canon.
7. Speaking/listening remain primary learning goals.
8. Recognition and production are separate evidence dimensions.
9. Concept visuals prefer emoji/reuse before generation.
10. Adding a language should mainly be configuration/data.
11. Mobile/hosted versions reuse the same learning contracts, not a second product.
12. Cloud/billing infrastructure is deferred until actually required.

## Next milestone

**PWA/mobile access using the same API and learning engine**, while preserving local-first processing on the PC when available.
