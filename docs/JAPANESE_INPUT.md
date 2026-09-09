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

## Pedagogical rule

Focuslyra should help the learner *produce* Japanese without a Japanese keyboard, but it should not turn kanji into invisible autocomplete. Kana conversion can be automatic because it is an input method. Kanji remains a lexical/orthographic learning decision, so suggestions require learner confirmation.
