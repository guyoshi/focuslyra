# Roadmap

## Phase 0 — Foundation

- [x] Repository created/initialised.
- [x] Product name: Focuslyra.
- [x] Learning philosophy documented.
- [x] AI/cost rules documented.
- [x] Data model documented.
- [x] Local-first architecture documented.
- [x] Privacy and sync defaults documented.

## Phase 1 — Working local MVP

- [x] Local FastAPI server.
- [x] Dashboard.
- [x] Study modes: Speak, Listen, Write, Read, Pronounce.
- [x] Browser microphone recording and playback.
- [x] Local recording persistence.
- [x] Local session save endpoint.
- [x] SQLite database bootstrap.
- [x] Concept library prototype.
- [x] Language profile data.
- [x] Memory-source configuration UI.
- [x] Provider status page.
- [x] Windows/Unix setup and launch scripts.
- [x] GitHub smoke-test workflow.
- [x] Google Calendar OAuth foundation.
- [x] Separate Focuslyra Google calendar creation.
- [x] Free/busy availability lookup.
- [x] Manual free-slot selection and study-event creation.
- [x] Earliest-free-slot smart scheduling.
- [x] Google Calendar reminders for scheduled study events.

## Phase 2 — Learning engine

- [x] Evidence-event persistence foundation.
- [x] AI feedback persistence.
- [x] Recent evidence fed back into later local analyses.
- [ ] Recognition vs production aggregation.
- [ ] Review scheduling.
- [ ] Daily session planner.
- [ ] Minimum-day planning logic.
- [x] AI-generated hidden retrieval target for the next activity.
- [ ] Progress radar from real evidence by skill.
- [ ] Let the learning engine request calendar duration based on the day's study plan.
- [ ] Optional user-approved automatic rescheduling policy.

## Phase 3 — Free/local AI

- [x] Ollama local text generation through localhost API.
- [x] Qwen3 local structured analysis.
- [x] Writing → local AI → feedback → evidence → next activity pipeline.
- [x] Speech transcript → local AI → feedback → evidence → next activity pipeline.
- [ ] General provider interface/orchestrator beyond the Ollama MVP.
- [ ] Free-tier cloud text provider integration.
- [x] Structured writing feedback.
- [ ] Dynamic exercise generation for all study modes.
- [ ] Multi-turn conversation engine.
- [x] Retrieval from recent learner evidence.

## Phase 4 — Speech and pronunciation

- [x] Optional free local Whisper transcription setup.
- [x] Saved recording → local transcript → Learning Engine pipeline.
- [x] Free browser TTS for generated practice utterances.
- [ ] OpenAI audio provider as optional premium provider.
- [ ] Persistent listening audio generation/cache beyond browser TTS.
- [ ] Acoustic pronunciation analysis from original recordings.
- [ ] Sound map per language/accent.
- [ ] Longitudinal recording comparison.

## Phase 5 — Interest memory

- [x] Read-only Git repository source sync foundation.
- [x] Path include/exclude rules in source configuration.
- [ ] Last indexed commit tracking.
- [ ] Local semantic/search index.
- [x] Tinkos configured as a project source.
- [x] Dimensoes Infinitas/books configured as a literary source.
- [x] Canon protection rule: generated exercises never mutate source repositories.

## Phase 6 — Multilingual concept library

- [x] Emoji-first visual policy and concept UI prototype.
- [ ] Persistent dynamic concept database.
- [ ] Shared generated images.
- [ ] Multiple senses per concept.
- [ ] Language-specific expressions in persistent storage.
- [ ] Listening/reading/speaking/writing evidence per expression.

## Phase 7 — Productisation

- [ ] One-click setup/update beyond development scripts.
- [ ] Optional encrypted/synchronised learner media.
- [ ] Multi-user architecture investigation.
- [ ] Google OAuth production/verification path for public distribution.
- [ ] Installable PWA/mobile client.
- [ ] Secure PC-as-home-server access for phone use.
- [ ] Fully independent mobile/cloud backend option investigation.
- [ ] Branding/domain/trademark review.
