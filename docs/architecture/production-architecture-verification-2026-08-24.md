# Production Architecture Verification — 2026-08-24

Status: read-only production evidence snapshot. This document records observed deployment/schema/data facts; it does not authorize implementation or production mutation.

Related architecture documents:

- [`database-architecture-investigation.md`](./database-architecture-investigation.md)
- [`template-notetype-decoupling-investigation.md`](./template-notetype-decoupling-investigation.md)
- [`study-interaction-trigger-algorithm-plan.md`](./study-interaction-trigger-algorithm-plan.md)

## 1. Scope and safety

Production was inspected through the configured SSH alias `chung_hostinger_vps` at the user's direction.

Only read-only operations were used:

- deployment/service metadata inspection;
- source inspection in the active release;
- MySQL `SELECT`, `SHOW`, `SHOW CREATE TABLE`, and `information_schema` queries;
- aggregate counts, distributions, integrity checks, and age buckets.

The audit did **not**:

- run Flask or import the application factory;
- run Alembic upgrade/downgrade/stamp;
- execute DDL or DML;
- start, stop, reload, or restart services;
- run startup maintenance, seed, repair, or clone cutover;
- print credentials, secret environment values, user identities, Note values, or raw payloads;
- modify production or workspace files.

All timestamps and retention buckets in this report use the production UTC clock at observation time. Counts are a point-in-time snapshot, not permanent domain invariants.

## 2. Executive production answers

| Question | Production answer |
|---|---|
| Current MySQL/Alembic state | MySQL 8.0.46; exactly one Alembic head row at `20260821_000020`, matching the deployed migration head |
| Original core-schema baseline | The core schema predates and is outside the checked-in Alembic chain; its exact original bootstrap mechanism cannot be proven from the current DB/release |
| Startup schema mutation | Disabled in normal production boot; only the database connectivity check is enabled |
| SchedulerPreset production data/use | 0 preset rows, 0 user scheduler-setting rows, 0 Deck references; production uses defaults/imported state; an out-of-repository management tool cannot be ruled out |
| Native FSRS use | 0% by settings, progress mode, event mode, FSRS state, and preset data |
| Failed Field rename history | 0 failed jobs; the only job completed with zero Notes processed |
| Mixed-NoteType Decks | Physical SQL shows no individual Deck row with direct Notes from multiple NoteTypes; one recursive Deck study scope spans two NoteTypes; logical overlay resolution was not fully reproduced |
| Multi-Template / multi-Card data | Every current NoteType has one Template and every Note has one Card |
| Note-level progress consolidation | No current `(user, Note)` group contains multiple CardProgress rows; the present migration is low-conflict but code must still handle future/pre-production multi-Card data |
| Session retention baseline | No session/detail rows are older than 30 days; 39 rows still marked `open` are all already expired |
| SharedImage relational schema | No FK or relational association to Note, FieldDef, or MediaAsset; 11 independent assets exist; free-text URL/key usage was not measured |

## 3. Deployment topology and release fingerprint

**Observed:** production is host-native rather than Docker-managed at runtime.

- `flama.service`: Gunicorn application, working directory `/opt/flama/current`, port 4789.
- `flama-connect.service`: Gunicorn Connect service from the same release, loopback port 4790.
- MySQL and nginx are host services.
- The active release symlink resolved to release `873de2d…` during the audit.
- The service environment is supplied through a protected environment file; secret values were not read or reported.

This fingerprint matters because repository `HEAD`, a release directory, and production schema can advance independently. Findings in this document describe that deployed release and database snapshot, not every branch/worktree state.

## 4. Alembic and original baseline provenance

### 4.1 Confirmed current migration state

- `alembic_version` contains one row: `20260821_000020`.
- The deployed graph has two branches after `20260811_000015`, merged at `20260820_000019`, followed by `20260821_000020`.
- The current deployment workflow upgrades the new release before switching the active symlink.
- Application-release rollback does not imply a database downgrade.

### 4.2 Confirmed baseline gap

The current Alembic chain is not a full clean-install baseline for the core learning schema:

- its base revision is a payment-domain migration with `down_revision = None`;
- that base already references a pre-existing `users` table;
- no checked-in revision creates the original `note_types`, `field_defs`, `notes`, `templates`, `cards`, `card_progress`, `scheduler_presets`, or `field_rename_jobs` tables.

Production metadata indicates the core tables existed before the production `alembic_version` table was created. MySQL `CREATE_TIME` is supporting evidence only because table rebuilds can change it.

**Conclusion:** describe production as having a **pre-existing core-schema baseline outside the current Alembic chain**. The present evidence cannot distinguish whether that baseline originated from an older absent migration history, `db.create_all()`, compatibility DDL, a dump/bootstrap script, or manual operations.

This remains an operational documentation gap. It does not mean production is behind: production is at the current checked-in head.

## 5. Startup maintenance and schema authority

### 5.1 Effective production flags

The production environment is `production`; no `STARTUP_*` override keys are present. Under the deployed `app/settings.py` defaults:

| Setting | Effective value |
|---|---:|
| `STARTUP_CHECK_DB_CONNECTIVITY` | `True` |
| `STARTUP_RUN_MAINTENANCE` | `False` |
| `STARTUP_RUN_DB_CREATE_ALL` | `False` |
| `STARTUP_RUN_USER_MANAGEMENT_SCHEMA` | `False` |
| `STARTUP_RUN_BACKWARD_COMPAT_SCHEMA` | `False` |
| `STARTUP_RUN_DEFAULT_USER_ROLE_SEED` | `False` |
| `STARTUP_RUN_DEFAULT_TTS_PROVIDER_SEED` | `False` |
| `STARTUP_RUN_CLONE_CUTOVER` | `False` |

**Observed runtime result:** normal production boot performs a `SELECT 1` connectivity check and returns before `db.create_all()`, schema compatibility helpers, seeders, or clone cutover.

An explicit startup-maintenance CLI exists, but it was not run during this audit. Normal deployment schema authority is Alembic.

### 5.2 Legacy flags

- `USE_NEW_CARD_MODEL` is present in the environment, but no active application consumer was found; it is currently inert configuration.
- A legacy clone-cutover strictness flag exists, but it only matters if clone cutover is explicitly enabled. It does not enable cutover by itself.

## 6. Relevant production schema

### 6.1 Field, Note, Template, and Card

- `field_defs.id` is the UUID primary key.
- `field_defs.note_type_id` is required and cascades on NoteType deletion.
- FieldDef has unique `(note_type_id, name)` and `(note_type_id, identity_role)` constraints.
- `notes.field_values` remains `JSON NOT NULL`; no normalized NoteFieldValue table exists.
- `templates.note_type_id` is a required cascading FK; Template remains structurally owned by one NoteType.
- The Template DDL does not enforce unique `(note_type_id, name)` or exactly one default Template; current default/name anomalies were not data-audited.
- `cards.note_id` and `cards.template_id` are required cascading FKs.
- Card remains unique by `(note_id, template_id)`.

### 6.2 Progress, history, and sessions

- `card_progress.card_id` remains nullable at the DDL level and cascades from Card.
- `(user_id, card_id)` is unique, subject to MySQL's multiple-NULL behavior.
- CardProgress contains fixed queue/step/due/interval/ease/leech fields plus FSRS stability/difficulty.
- `review_events` intentionally has no FK to Card, Deck, or NoteType; it has user/preset FKs and a nullable session FK with `SET NULL`.
- `study_session_cards` is unique by `(session_id, card_id)` and cascades from both Session and Card.
- `study_session_commits` is unique by both `(session_id, idempotency_key)` and `session_id`, allowing one successful commit receipt per session.

### 6.3 Rename and media identity

- `field_rename_jobs` records FieldDef/User/NoteType, old/new names, status, counts, and an error field.
- `media_assets` belongs to Note, but its Field association is the mutable string `field_name`.
- `shared_image_assets.image_key` is unique and its only FKs are optional creator/updater User references.
- There is no SharedImage-to-Note, SharedImage-to-FieldDef, or SharedImage-to-MediaAsset FK.

The SharedImage schema already matches the approved product boundary: shared images are independent catalog assets, and a Note may carry a URL/key as ordinary field content without relational ownership or cascade.

## 7. Aggregate production inventory

| Entity | Rows |
|---|---:|
| Users | 4 |
| Active Decks | 965 |
| NoteTypes | 10 |
| FieldDefs | 135 |
| Notes | 17,532 |
| Templates | 10 |
| Cards | 17,532 |
| CardProgress | 15,209 |
| ReviewEvents | 113,580 |
| StudySessions | 133 |
| StudySessionCards | 4,315 |
| StudySessionCommits | 94 |
| SchedulerPresets | 0 |
| UserSchedulerSettings | 0 |
| FieldRenameJobs | 1 |
| SharedImageAssets | 11 |

### 7.1 Current field-data consistency

- 291,862 JSON key occurrences were checked in aggregate.
- 0 exact/binary-name JSON keys lack a matching FieldDef.
- 17,572 required-field slots were checked; 0 are missing.
- Notes currently have 4–19 JSON keys, average 16.6474.
- 33,434 MediaAsset rows exist; 0 current `field_name` values lack a matching FieldDef name.

These results show current production consistency. They do not remove the architectural rename coupling: values and media references are still name-keyed.

## 8. Scheduler, preset, and FSRS reality

### 8.1 Presets/settings are unused in current production data

- `scheduler_presets`: 0 rows.
- `user_scheduler_settings`: 0 rows for 4 users.
- All 965 active Decks have `scheduler_preset_id IS NULL`.
- No ReviewEvent or StudySessionCard references a preset.

The repository contains read/resolution paths but no checked-in mutation UI/API/CLI for these settings. The database confirms non-use; it cannot prove whether an external operational tool ever existed.

### 8.2 FSRS usage is zero

CardProgress distribution:

| `scheduler_mode` | Rows | Share |
|---|---:|---:|
| `anki` | 14,591 | 95.94% |
| `legacy` | 618 | 4.06% |
| `fsrs` | 0 | 0% |

Additional checks:

- 0 progress rows have stability or difficulty populated, including partial pairs.
- 0 ReviewEvents are FSRS-labelled or contain populated FSRS after-state.
- 0 presets contain FSRS configuration because no presets exist.
- 0 user settings select FSRS because no settings rows exist.

ReviewEvent Algorithm/version distribution is 111,588 imported `anki/revlog-v1` rows, 1,988 native `legacy-anki/1.0.0` rows, and 4 legacy rows without an Algorithm/version label. None is FSRS-labelled.

The dominant `anki` state came from external synchronization/import provenance; it is not native FSRS execution.

**Migration implication:** there is no live native FSRS state to preserve today. Nevertheless, migration must not turn this point-in-time fact into a schema invariant or infer Algorithm identity from `scheduler_mode` alone.

## 9. Rename-job history

The sole `FieldRenameJob` is:

- status `completed`;
- zero target/processed Notes;
- no error recorded;
- no pending, running, failed, or stale job exists.

No old/new Field names or error contents were selected.

This confirms no recorded failure in the canonical rename-job path. It does **not** validate rewriting under real data volume, and it does not cover mutation paths such as broad MCP NoteType updates that can bypass this job model.

## 10. Deck and NoteType distribution

Two definitions matter.

### 10.1 Direct physical Deck contents

For Notes whose `notes.deck_id` equals the Deck row directly:

- 582 active Decks contain no direct Notes/NoteTypes;
- 383 contain exactly one direct NoteType;
- 0 contain more than one direct NoteType;
- 17,532 Notes are deck-attached; none is deckless;
- 80 of the 383 Decks with Notes have `decks.note_type_id IS NULL`;
- when a Deck default is non-null, 0 resident Notes disagree with it.

Therefore `decks.note_type_id` is not sufficient by itself to discover the schema for every populated Deck.

### 10.2 Recursive study scope

When each active Deck is treated as a study root and descendant Decks are included, matching the current subtree collector:

- 561 scopes contain no NoteType;
- 403 scopes contain one NoteType;
- **1 scope contains two NoteTypes**.

The recursive count classifies scopes and intentionally does not sum Note rows across roots, because a descendant is visible from multiple ancestors. Logical-overlay install scopes require application resolution and are not fully represented by this physical SQL query.

**Architecture implication:** the approved “show attached Templates when Study is clicked” flow still needs a policy for the real mixed-NoteType recursive scope: group by NoteType, ask for NoteType first, or restrict the selected scope.

## 11. Note/Card/progress shape

- Every current NoteType has exactly one Template.
- Every current Note has exactly one Card; no Note has multiple Cards.
- All 15,209 `(user, Note)` progress groups contain exactly one CardProgress row.
- No per-Note group contains divergent Card states requiring consolidation.
- All 14,758 `(user, Note)` review-history groups reference only one Card ID.
- CardProgress has 0 NULL Card IDs and 0 non-NULL orphan Card references.

This distribution materially lowers the risk of the approved Note-level progress backfill. It does not prove that one Card per Note is a valid long-term invariant: the current code supports multi-Template fanout, imports can evolve, and other environments may already contain multiple Cards.

## 12. Study-session retention baseline

### 12.1 Current age/status

| Session state | 0–1 day | 1–7 days | 7–30 days | >30 days | Total |
|---|---:|---:|---:|---:|---:|
| committed | 3 | 35 | 56 | 0 | 94 |
| open | 0 | 12 | 27 | 0 | 39 |

- All 39 rows still marked `open` are already past `expires_at`.
- 37 have been expired for more than one day; 16 for more than seven days.
- No StudySession, StudySessionCard, StudySessionCommit, or session-linked ReviewEvent row is older than 30 days by `created_at`.
- All 94 committed sessions have exactly one receipt; no orphan commit or session-card row was found.

Approximate current payload totals:

- commit response JSON: 586,503 bytes;
- session-card initial-state JSON: 1,284,469 bytes;
- session configuration snapshots: 100,651 bytes.

The feature/data is younger than 30 days, so production cannot yet demonstrate cleanup volume or validate a 30-day aggregation pipeline.

### 12.2 Retention semantics that must be explicit

- StudySession deletion cascades its SessionCards and Commit receipt.
- ReviewEvent retains history and has its session reference set to NULL.
- `created_at` is ingestion/storage age; `reviewed_at` is learning-event time.
- ReviewEvent `reviewed_at` reaches back to 2025-01-20 even though these rows were created recently, consistent with imported/backfilled history.

A 30-day retention job must choose its clock per record class. Purging imported history based on historical `reviewed_at` immediately after ingestion would be incorrect unless explicitly intended.

No durable daily aggregate table was found. Current analytics reads raw ReviewEvents. “Aggregate then purge” therefore requires an aggregate system of record and reconciliation gate before any detail deletion.

## 13. Production implications for approved product decisions

### 13.1 One progress per learner/Note

Production currently has a collision-free one-Card-per-Note shape, so `(learner_user_id, note_id)` can be backfilled without merging divergent CardProgress rows in this snapshot. Migration still needs a deterministic fan-in policy and a hard audit gate for environments or new data with more than one Card per Note.

### 13.2 Template-independent progress

Existing Card IDs must remain available during compatibility for StudySession membership, ReviewEvent attribution, Connect/Anki ordinals, and clone resolution. Progress authority can move to the Note learning subject without deleting/regenerating Cards.

### 13.3 History-based Algorithm switching

Production history is predominantly imported Anki data. Current ReviewEvent plus progress snapshots are not a complete reconstructive event stream. A new Algorithm initializer needs:

- a completeness/provenance marker;
- chronological canonical history where available;
- an explicit fallback when history is partial;
- no assumption that imported `anki` or legacy-labelled rows are native FSRS state.

### 13.4 Template selection at study start

Production has only one Template per NoteType today, so the new selector initially has one option in every current schema. The one mixed-NoteType recursive Deck scope is the production case that prevents assuming every Deck study root maps to exactly one NoteType.

### 13.5 Client evaluation and server verification

Current session infrastructure already supports optimistic client transitions and server replay for four ratings. Interactive evaluation additionally requires the batch to retain raw response, evaluator/contract version, resolved-input/content identity, and enough deterministic context for server verification.

### 13.6 Thirty-day detail retention and active-lease replay

Algorithm implementation replay is required only through the active session lease. Retaining session rows for 30 days does not require retaining an executable old Algorithm for all 30 days.

However, history-based Algorithm switching and deletion of all detailed ReviewEvents after 30 days are incompatible unless one of the following becomes authoritative:

1. a compact canonical per-Note review history retained beyond 30 days; or
2. an Algorithm-neutral scheduler-history summary contract sufficient to initialize every supported Algorithm.

Ordinary aggregate analytics counts are not sufficient for this purpose. This is the main remaining reconciliation needed between the approved decisions.

### 13.7 Independent SharedImage assets

The current production schema already satisfies this boundary. Target normalized NoteFieldValue data should continue treating shared image URL/key values as generic content and must not introduce a Note-to-SharedImage FK or cascade. Note-owned MediaAsset remains a separate lifecycle.

## 14. Remaining verification limits

- The original pre-Alembic core baseline mechanism cannot be proven from the current production DB/release.
- Production has not exercised multi-Template NoteTypes or multiple Cards/progress rows per Note.
- Exact cross-NoteType Card pairing and Template default/name/position anomalies were not queried in the original 2026-08-24 snapshot. The 2026-08-27 follow-up in section 15 closed this specific evidence gap for the then-current production state.
- The only rename job processed zero Notes, so production history does not validate bulk rename failure/recovery.
- No production row is old enough to demonstrate 30-day session aggregation/cleanup.
- Aggregate SQL does not fully reproduce logical-overlay clone study resolution.
- Note JSON was intentionally not scanned for actual SharedImage URL/key usage; only the approved relational independence was verified.
- DB data confirms presets/settings are unused but cannot prove whether an out-of-repository management tool ever existed.

These limits should remain explicit rather than being converted into assumptions.

## 15. Follow-up read-only verification — 2026-08-27

This follow-up was performed through the configured SSH alias `chung_hostinger_vps` after the first study-runtime compatibility slice. It used aggregate SQL through a standalone SQLAlchemy connection and did not import the Flask application, run a migration, invoke startup maintenance, or modify production.

The active release had advanced since the original snapshot, and production Alembic contained one head row at `20260826_000021`.

| Gate | Result |
|---|---:|
| NoteTypes without a Template | 0 |
| NoteTypes with multiple Templates | 0 |
| NoteTypes whose default-Template count is not exactly one | 0 |
| Duplicate `(NoteType, Template.name)` groups | 0 |
| Duplicate `(NoteType, Template.position)` groups | 0 |
| Cards whose Note and Template belong to different NoteTypes | 0 |
| Notes without Cards | 0 |
| Notes with multiple Cards | 0 |
| CardProgress rows with NULL Card ID | 0 |
| CardProgress rows with a non-NULL missing Card | 0 |
| `(learner, Note)` groups fed by multiple CardProgress rows | 0 |
| `(learner, Note)` history groups containing multiple Card IDs | 0 |
| `open` StudySessions already past `expires_at` | 41 |
| StudySessions older than 30 days by `created_at` | 0 |

### Interpretation

- The additive learner/Note progress migration remains collision-free in this production snapshot, but the future migration must still quarantine rather than silently merge collisions found in another environment or created before cutover.
- Template/Card structural anomaly gates are currently clean. They are point-in-time data evidence, not database constraints and not proof that multi-Template behavior is implemented.
- Expired sessions increased from 39 in the 2026-08-24 snapshot to 41. This confirms the missing expired-session lifecycle remains active; no rows were closed or deleted during verification.
- No row is old enough to validate the approved 30-day aggregation and cleanup process. That process remains unimplemented.
- These physical-table checks do not reproduce every logical-overlay clone resolution path. Overlay compatibility still requires service-level acceptance tests and migration reconciliation.
