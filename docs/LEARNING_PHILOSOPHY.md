# Learning Philosophy

Focuslyra is not a course-completion system. It is an ability-building system.

## Primary objective

The first objective in a language is useful spoken interaction and listening comprehension. Reading and writing support that objective and can later become independent mastery goals.

## Core learning loop

1. Hear or encounter meaningful language.
2. Understand the intended meaning.
3. Notice a reusable pattern.
4. Reproduce it.
5. Modify the pattern with new vocabulary or context.
6. Use it spontaneously.
7. Encounter it again later through a different modality.

## Evidence instead of lesson completion

A word, structure or sound is not simply `learnt=true`.

Focuslyra records separate evidence for:

- reading recognition;
- listening recognition;
- written production;
- spoken production;
- spontaneous use;
- pronunciation/perception when relevant.

Understanding an item does not imply that the learner can produce it.

## Level memory and teaching before testing

Each language has its own learner state. Placement evidence, recent performance and saved learning history tell the engine what can reasonably be expected in that language.

A beginner is not merely an advanced learner receiving easier sentences. If a learner has not yet been taught a concept, sound, script rule or useful chunk, Focuslyra should introduce and explain it before demanding independent retrieval. Missing untaught knowledge is a teaching signal, not automatically a careless failure.

As knowledge grows, scaffolding should fade roughly through:

introduction → guided imitation → controlled variation → retrieval → spontaneous use → delayed retest.

Placement is therefore working memory for the teaching engine, not just a CEFR label shown on a profile. It influences explanations, vocabulary load, prompt complexity, how much support is visible, and what counts as meaningful evidence.

## Mistake Memory

A single error is evidence, not a permanent weakness.

Focuslyra distinguishes low-value slips from learning gaps. A harmless one-off typo can disappear after feedback. Errors become durable **Mistake Memory** targets when they are important to communication, part of a current learning goal, likely to fossilise, or repeated.

A stored mistake contains a stable semantic key plus evidence such as language, modality, learning target, category, occurrence count, correction/explanation and a future retest time. Recurrence increases planning weight.

The learner must be told when an error is recurring. Feedback should be neutral and useful, for example that the same pattern has appeared before and will return in later practice.

Retesting should normally happen later and in a changed context or modality. The goal is not to make the learner copy the correction repeatedly while it is still in working memory.

A mistake is not resolved after one lucky success. Focuslyra currently requires repeated successful retest evidence before moving it out of active mistake state. A later failure can reactivate it.

## Vocabulary

Prefer concepts and chunks over isolated translation pairs.

Example:

`DOG` is a shared concept. Its language-specific expressions may include `dog`, `cão`, `perro`, `chien`, `cane`, `Hund`, `犬`, and `كلب`.

The same visual can be reused across languages. Prefer existing emoji or reusable assets before generating new images.

For grammar and vocabulary, prefer reusable sentence engines such as `I would + VERB` rather than memorising disconnected rules.

## Speaking sessions

Conversation should normally continue despite small errors. Corrections are prioritised after the learner finishes the thought.

Focuslyra should focus on errors that:

- block communication;
- recur frequently;
- concern a current learning target;
- are likely to fossilise;
- strongly reduce naturalness at the learner's current level.

## Listening

Listening should frequently begin without text. Text/transcription may appear after the learner attempts comprehension.

Difficulty may vary through speed, accent, speaker count, background noise, vocabulary novelty and grammatical complexity.

## Pronunciation

Pronunciation development follows roughly:

perception → articulation → controlled production → sentence production → connected speech → spontaneous speech.

Accent goals are language-profile-specific. For English, the current target is contemporary RP / modern standard southern British pronunciation rather than an exaggerated historic prestige accent.

Scores must not pretend to scientific precision when only an AI judgement exists. Acoustic measurements and repeated samples should support fine-grained pronunciation metrics where possible.

A weak controlled-pronunciation sample can become a later Mistake Memory target when real acoustic/intelligibility evidence is below the practice threshold. Until forced alignment and language-specific calibration exist, Focuslyra must describe this as weak evidence while practising a feature, not claim that a specific phoneme was definitely wrong.

## ADHD-friendly behaviour

The system supports three gears:

- Minimum day: a small session that preserves continuity without creating backlog.
- Normal day: several short varied activities.
- Hyperfocus day: optional longer exploration that does not increase tomorrow's obligation.

When attention drops, change the activity while preserving the learning target.

The application should minimise planning decisions. The learner can simply press Start and let the learning engine choose the work.
