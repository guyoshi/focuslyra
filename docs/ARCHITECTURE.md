# Architecture

## Product shape

Focuslyra is a local-first web application running on the learner's computer.

The browser provides the interface and microphone access. A small local Python service manages persistence, learning logic, provider calls and repository memory.

## High-level architecture

```text
Browser UI
   |
   v
Local FastAPI service
   |
   +-- Learning Engine
   |     +-- session planner
   |     +-- review scheduler
   |     +-- evidence aggregator
   |
   +-- Memory Engine
   |     +-- learner history
   |     +-- concept library
   |     +-- external Git sources
   |
   +-- Media Engine
   |     +-- recordings
   |     +-- generated audio
   |     +-- concept visuals
   |
   +-- AI Orchestrator
         +-- TextProvider
         +-- AudioProvider
         +-- ImageProvider
```

## Storage

Human-readable project data remains the durable source of truth where practical. SQLite can provide fast indexing/querying and later become the operational store for evidence/events.

External source repositories live under `sources/` as local read-only clones and are excluded from Focuslyra Git history.

Large learner recordings are local by default. A future opt-in sync layer may use Git LFS or another media store.

## Language independence

Core code must not hard-code the current seven languages.

A language profile supplies configuration such as:

- BCP-47 code;
- display name;
- scripts;
- writing direction;
- target regional variety/accent;
- romanisation/transliteration conventions where relevant;
- language-specific pronunciation notes;
- current learner priority and goals.

Adding another language should primarily be a data/configuration operation.

## Memory sources

A source definition contains:

- repository URL or local path;
- branch/ref;
- included/excluded paths;
- last indexed commit;
- permissions;
- source-specific instructions.

Focuslyra must prefer links/clones over copied canonical files.

## Security

- Secrets live in `.env`, never Git.
- Paid AI is disabled by default.
- External learning-memory repositories are read-only by default.
- The app should bind to localhost by default.
- Persistent AI updates are validated by local code.

## MVP technology

- Python 3.11+
- FastAPI + Uvicorn
- browser-native HTML/CSS/JavaScript
- SQLite via Python standard library
- browser `MediaRecorder` for initial recording

The low-dependency frontend is intentional. Frameworks may be introduced later only when the product needs them.
