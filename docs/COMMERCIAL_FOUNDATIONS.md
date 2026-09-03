# Commercial Foundations

Focuslyra is currently a personal/local-first MVP. This document defines the small set of architectural rules that must be respected now so that a future commercial version does not require a rewrite.

This is not a plan to build billing, cloud infrastructure or account management today. It is a guardrail for current development.

## Non-negotiable seams from now on

### 1. User-scoped learner data

Every durable learner-owned record must be attributable to a `user_id`.

Current local mode uses:

```text
FOCUSLYRA_USER_ID=local-owner
```

The database already scopes sessions, writings, evidence and AI feedback by user. A future authentication middleware can replace the local user context without changing the learning engine.

New personal-data tables must include `user_id` from their first migration.

### 2. Deployment mode is configuration, not a fork

Current mode:

```text
FOCUSLYRA_MODE=personal
```

Future examples may include `hosted` or `self-hosted`. Business logic must not branch into separate products unnecessarily.

### 3. Storage must remain replaceable

Current storage is local filesystem + SQLite.

Do not make learning logic depend directly on a future cloud provider. Media/database access should remain capable of moving behind storage/repository interfaces when hosted sync is implemented.

Configurable roots already exist for data, private material and media.

### 4. AI providers are replaceable

No learning feature may require one proprietary AI vendor unless the feature is explicitly provider-specific.

- text provider: replaceable;
- speech-to-text provider: replaceable;
- TTS provider: replaceable;
- image provider: replaceable;
- acoustic pronunciation analysis: preferably local/provider-independent.

Paid services remain opt-in.

### 5. User content and product content are different

Do not commit learner recordings, OAuth tokens, API keys, private repositories or personal preferences into the distributable application.

Product defaults/examples can live in Git. Learner state belongs in user-scoped private/data/media storage.

### 6. External memory has permissions

Books, games, repositories and other memory sources are references, not copied canonical truth.

Each source needs explicit permissions such as:

- read/index;
- use for exercises;
- use characters/locations;
- write access (off by default).

Generated learning material derived from a source is not canon/source truth.

### 7. Feature capabilities, not hard-coded editions

Future Free/Pro/School/etc. editions should be implemented through capability/feature flags rather than duplicate codebases.

Do not add subscription checks deep inside learning logic. A future entitlement service should answer questions such as `can_use_cloud_sync` or `can_use_premium_audio`.

No billing implementation is required now.

### 8. Authentication is a boundary

The current personal version intentionally has no login.

Code must obtain the learner identity through the Focuslyra user context, not by assuming a specific name/email. Future authentication can set that context per request.

### 9. Privacy/export/delete must stay possible

Learner-owned data should remain enumerable by user so a future product can implement:

- export my data;
- delete my account/data;
- sync selected data;
- retention controls.

Avoid storing personal data in opaque logs or unrelated global files.

### 10. Third-party licences must be auditable

Before Focuslyra is sold/distributed, every bundled model, voice, library, dataset, icon and generated-asset source needs a commercial-use licence audit.

During MVP development:

- record which external component supplies a feature;
- do not assume every model/voice can be redistributed commercially;
- prefer components with clear licences;
- keep downloaded model files outside Git/distribution unless redistribution rights are verified.

The current repository should not receive an open-source licence casually if the intended commercial strategy has not been decided.

### 11. Public repository warning

The current GitHub repository is public. Personal secrets/media are gitignored, but source code and product design are visible.

Before proprietary commercial development becomes important, decide deliberately whether the repository should become private. Do this before adding confidential business logic, private assets, paid-provider credentials or proprietary datasets.

### 12. Mobile/web is another client, not another learning engine

A future mobile/PWA application should consume the same learning concepts/services rather than implementing a separate curriculum.

The local desktop server can remain one deployment target; hosted and mobile clients can be added later around the same domain model.

## Explicitly NOT required now

Do not build these merely for hypothetical future sales:

- payments/subscriptions;
- Stripe;
- production login/signup;
- cloud database;
- Kubernetes/container fleet;
- admin dashboard;
- analytics/marketing stack;
- app-store packaging;
- multi-region infrastructure.

Add them only when there is a real product need.

## Rule for every future feature

Before merging a durable learner feature, ask:

1. Is its data scoped to a learner?
2. Is any vendor/provider replaceable where reasonable?
3. Is private data kept outside distributable Git content?
4. Can it work in personal/local mode?
5. Does it preserve a path to hosted/mobile use without duplicating the learning engine?

If the answer to one is no, document why before proceeding.
