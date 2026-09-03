# Privacy and Sync

## Current repository visibility

At project creation time, `guyoshi/focuslyra` is a public repository.

Because Focuslyra stores personal learning data, the current safe default is:

- source code and documentation: tracked by Git;
- learner SQLite database: local only;
- microphone recordings: local only;
- external private repository clones: local only;
- API keys and `.env`: local only;
- Google OAuth client credentials and tokens: local only under `private/`.

These paths are protected by `.gitignore`.

## Google Calendar

Focuslyra must never commit Google OAuth credentials, access tokens or refresh tokens. Calendar credentials are stored under `private/google_calendar/`.

The calendar integration follows least-privilege rules:

- existing calendars are used only for list/free-busy availability checks;
- Focuslyra creates its own secondary Google calendar;
- study events are written only to the Focuslyra-created calendar;
- disconnecting removes the local OAuth token but leaves the Google calendar intact unless the learner explicitly deletes it in Google Calendar.

## If the repository becomes private

A future opt-in sync mode may version selected learner data. Audio should use Git LFS or another private media store rather than normal Git blobs.

Even in a private repository, secrets such as API keys and OAuth tokens must never be committed.

## External repositories

Tinkos, books and other interest sources are cloned into `sources/` and are excluded from Focuslyra Git history. Focuslyra must not copy their canonical files into its own tracked source tree.

## Principle

A `git push` must never accidentally publish personal recordings, learner history or credentials. Sync of personal learning media must be explicit.
