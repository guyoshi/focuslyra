# Data Model

## Learner profile

Stores global preferences and goals that affect all languages.

Examples:

- normal/minimum session duration;
- speaking/listening priority;
- accent importance;
- ADHD-friendly behaviour;
- paid-AI permission;
- preferred content interests.

## Language profile

Each language is independent and data-driven.

Suggested fields:

```json
{
  "code": "en-GB",
  "name": "English",
  "priority": 1,
  "status": "active",
  "target_variety": "Contemporary RP / modern standard southern British",
  "goals": ["advanced fluency", "RP listening", "RP pronunciation"]
}
```

## Concept

A concept represents meaning independently from a language.

```json
{
  "id": "concept_dog",
  "gloss": "dog",
  "visual": {"type": "emoji", "value": "🐕"},
  "senses": ["domestic canine"]
}
```

Language expressions attach to a concept/sense instead of forming translation pairs.

## Language expression

Possible fields:

- language code;
- written form;
- reading/romanisation;
- part of speech;
- grammatical features;
- pronunciation reference;
- example chunks;
- concept/sense ID.

## Learning item

A learning item can be a concept expression, phrase/chunk, grammar pattern, sound contrast, script symbol, listening feature or other skill target.

It accumulates evidence rather than a binary learned flag.

## Evidence event

Examples:

- recognised in reading;
- recognised in listening;
- produced with prompt;
- produced spontaneously;
- pronunciation judged intelligible;
- minimal-pair perception correct;
- recurring grammar error;
- successful reformulation.

Evidence events should include timestamp, modality, language, item ID, activity/session ID and confidence/source.

## Session

Each session records:

- planned targets;
- completed activities;
- original user writing;
- recording references;
- transcripts;
- important feedback;
- evidence events;
- newly introduced items;
- next-review decisions.

## Memory source

External project/book repositories remain separate from Focuslyra.

```json
{
  "id": "tinkos",
  "type": "git",
  "repository": "guyoshi/Tinkos",
  "branch": "main",
  "mode": "read_only",
  "include": ["Documentation/**"],
  "last_indexed_commit": null
}
```

## Visual reuse hierarchy

For a concept visual, prefer:

1. emoji when semantically sufficient;
2. existing reusable Focuslyra asset;
3. permissively usable icon/reference asset if explicitly supported;
4. generated image.

Generated images are global concept assets and should be reused across every language.
