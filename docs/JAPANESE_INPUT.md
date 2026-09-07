# Japanese Input

Focuslyra provides its own Japanese writing helper so a learner does not need a Japanese OS keyboard for Study.

## Romaji → kana

Japanese Study textareas automatically receive a small input toolbar.

- **Romaji → kana** is enabled by default.
- Choose **ひらがな** or **カタカナ** for new romaji input.
- Conversion is performed locally in the browser and does not require Qwen or an internet connection.
- Common IME behaviours are supported, including doubled consonants (`gakkou` → `がっこう`), syllabic `n`, and combinations such as `kyo`, `sha`, `cha`, `ryo`, etc.
- A trailing `n` is finalised as `ん` when leaving/submitting the field, so typing remains natural while the learner is still composing `na/ni/nu/ne/no`.

Examples:

- `katana` → `かたな`
- Katakana mode: `katana` → `カタナ`
- `konnichiwa` → `こんにちは`
- `gakkou` → `がっこう`

The existing **Show romaji** helper for reading Japanese remains separate and unchanged.

## Kanji Assist

Kanji conversion is deliberately **assisted rather than silently automatic**.

When **Kanji Assist** is enabled, Focuslyra waits briefly after typing and proposes a natural contextual conversion. Local Qwen is used when available. A small beginner dictionary provides a fallback for common words.

Example:

`かたな` → suggestion `刀`

The learner must press **Use suggestion** before Focuslyra changes the written answer. This prevents an IME from hiding kanji the learner does not actually recognise.

Every introduced kanji expression is shown with:

- its kanji form;
- kana reading;
- short meaning in the learner's native language when available.

## Learn this

Pressing **Learn this** on a kanji suggestion:

1. stores the expression in the learner's multilingual Concepts memory;
2. stores the kana reading;
3. creates a Japanese Review target;
4. makes the item eligible to return in later retrieval practice.

For example, learning `刀` creates a later review such as:

`刀 — what is the reading and meaning?`

with the hidden answer containing the reading and meaning.

## When the learner writes something wrong

Japanese submission feedback must distinguish the kind of problem instead of treating every mismatch as the same error:

- **typo** — an accidental surface slip with little evidence of a knowledge gap;
- **romaji** — an input/romanisation problem only when the submitted evidence actually contains romaji;
- **kana** — wrong or missing hiragana/katakana knowledge, spelling or script choice;
- **kanji** — a wrong character, kanji choice or reading-linked orthographic problem;
- **grammar** — particles, conjugation, syntax or grammatical form;
- **vocabulary / naturalness** — lexical choice, collocation or an unnatural Japanese expression.

After the learner finishes the current thought, useful corrections show the untouched learner form, the corrected/natural form, the meaning in Brazilian Portuguese, a brief explanation and one short example when it helps. Meaning questions are answered before correction details. Short correction drills may correct immediately.

A first error is evidence, not automatically a permanent weakness. Focuslyra decides whether it deserves later practice based on importance, the learner's current level, whether the concept has already been taught, and whether the same error recurs. A harmless one-off typo can be discarded.

Meaningful errors enter **Mistake Memory** with a stable key, modality, occurrence count and a future retest date. Recurring errors are explicitly pointed out and receive more planning weight. Later activities should test the same underlying target in a new context or modality rather than merely asking the learner to copy the correction again.

For beginners, an error may reveal knowledge that has not been taught yet. In that case Focuslyra teaches the concept, script rule, vocabulary or sound first, then moves to guided practice and only later to independent retrieval. The system must not score missing untaught knowledge as if it were a careless failure.

## Pedagogical rule

Focuslyra should help the learner *produce* Japanese without a Japanese keyboard, but it should not turn kanji into invisible autocomplete. Kana conversion can be automatic because it is an input method. Kanji remains a lexical/orthographic learning decision, so suggestions require learner confirmation.
