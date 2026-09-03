# Focuslyra

Focuslyra is a local-first, AI-assisted language learning workspace built around real ability rather than lesson completion.

The learner owns the data: recordings, writing, vocabulary evidence, progress, concepts and linked memory sources. AI providers are replaceable and paid providers are optional.

## Core principles

- Speaking and listening first.
- Evidence-based progress: recognition and production are tracked separately.
- Adaptive sessions from real weaknesses and goals.
- Concepts are language-agnostic and can reuse the same emoji/image across languages.
- Interest memory can link external repositories such as books or game projects without duplicating their source files.
- The system must remain useful with paid AI disabled.
- AI providers are interchangeable; audio can use OpenAI while text can use local/free providers.

## Current MVP

The first MVP includes:

- Local web interface.
- Dashboard and adaptive-session shell.
- Browser microphone recording and playback.
- Writing workspace.
- Concept vocabulary prototype.
- Review and progress views.
- Memory-source configuration.
- Python/FastAPI backend foundation.
- SQLite-ready local data layer.
- Provider abstractions for text, audio and images.

## Run locally

Windows:

```bat
setup.bat
run.bat
```

macOS/Linux:

```bash
chmod +x setup.sh run.sh
./setup.sh
./run.sh
```

Then open `http://127.0.0.1:8765`.

## Repository structure

```text
focuslyra/
├── app/                 # Python backend
├── static/              # Front-end
├── data/                # Local-first learner/project data
├── docs/                # Product and learning rules
├── sources/             # Local read-only clones (gitignored)
├── media/               # Local recordings/generated media (gitignored by default)
├── .env.example
├── requirements.txt
├── setup.bat / setup.sh
└── run.bat / run.sh
```

## Status

Early MVP / architecture phase.
