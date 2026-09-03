# AI Rules

## Provider independence

Focuslyra must never depend on one model vendor for its core data or learning logic.

Use provider interfaces for:

- text/reasoning;
- speech-to-text;
- text-to-speech/realtime audio;
- image generation;
- embeddings/retrieval where needed.

The learner's history, vocabulary, concepts, recordings and progress belong to Focuslyra, not to an AI provider.

## Cost rule

`ALLOW_PAID_AI=false` is the default.

When paid AI is disabled:

- no paid-provider request may be sent;
- local/free-tier providers may be used;
- if no free provider is available, the application must degrade gracefully instead of charging money.

A future UI must show provider status and clearly distinguish free/local from potentially paid requests.

## Recommended initial routing

- deterministic learning logic: local code;
- scheduling and evidence aggregation: local code;
- simple text generation/correction: local model or free-tier text provider;
- advanced text reasoning: selectable provider;
- audio recording: local browser/device;
- speech transcription: local/free provider first;
- advanced audio/voice: OpenAI provider when explicitly enabled;
- pronunciation acoustic features: local analysis where possible;
- generated concept images: only when no reusable emoji/image/icon exists.

## Context discipline

Do not send the entire learner memory or external repositories to a model.

Use retrieval:

1. determine the task;
2. retrieve only relevant learner evidence;
3. retrieve only relevant interest-memory passages;
4. send a concise context package;
5. store structured results back into Focuslyra.

## External memory sources

External Git repositories are read-only context by default.

Generated exercises inspired by books or game documentation are never canon and must never modify those repositories unless the user explicitly performs a separate authorised editing workflow.

## Feedback behaviour

AI feedback should prioritise useful corrections instead of correcting every surface error.

For speaking:

- preserve conversation flow;
- distinguish intelligibility, grammar, vocabulary retrieval, naturalness and pronunciation;
- identify recurring errors against learner history;
- avoid fabricated acoustic precision.

For writing:

- always preserve the untouched original;
- provide a natural corrected version separately;
- record only meaningful learning targets.

## Structured outputs

Where practical, provider responses should be converted into validated structured data before updating learner state. Free-form AI prose must not directly mutate persistent progress metrics.
