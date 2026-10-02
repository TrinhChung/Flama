# Flama Architectural Investigation & Review Checklists

Use these focused checklists during **INVESTIGATE** and **DESIGN** tasks to audit entity boundaries, evaluate schema tensions, and prevent common architectural regressions.

---

## 1. Field Architecture Audit & Evolution Checklist

Fields are the primary data-modeling hotspot in Flama due to the dual existence of stable `FieldDef.id` (UUID) and runtime `FieldDef.name` (String).

### Investigation Questions
- [ ] **Identity Scope**: Is field identity tracked by immutable UUID (`field_defs.id`) or mutable name (`field_defs.name`) in this subsystem?
- [ ] **Content Storage**: How are note values stored in `notes.field_values` (JSON dict keyed by name, JSON dict keyed by ID, or normalized rows)?
- [ ] **Rename Blast Radius**: When a field is renamed via `update_field`:
  - Does it rewrite `notes.field_values` synchronously or asynchronously?
  - Does it update `Template.front_html` / `back_html` placeholders `{{Field}}`?
  - Does it update `MediaAsset.field_name` rows?
  - Does it update `DeckCloneNoteFieldOverride.field_name`?
  - Does it update file import column mappings or Yomitan/AnkiConnect configurations?
- [ ] **Clone Override Dual Keying**: Does `DeckCloneNoteFieldOverride` maintain dual constraints on `(deck_install_id, source_note_id, source_field_def_id)` and `(deck_install_id, source_note_id, field_name)`?
- [ ] **Structured & Dynamic Values**: Can a field store rich text, markdown, audio UUIDs, image URLs, or interactive options without breaking template interpolation?

### Design & Evolution Rules
- **Stable ID as Canonical Anchor**: In target designs, all internal references (overrides, release diffs, template bindings, media associations) MUST be anchored to `FieldDef.id`.
- **Presentation Projection**: Field names should be treated as mutable display labels resolved at serialization/render boundaries.
- **Fail-Safe Renames**: A rename transaction must never commit partial note JSON rewrites alongside a renamed schema definition.

---

## 2. NoteType / Note / Template / Card Layer Separation Checklist

Flama supports flashcards today and is designed to support rich interactive study modes (multiple choice, matching, listening, typing, interactive diagrams) without creating hardcoded domain tables.

### Investigation Questions
- [ ] **Layer Responsibilities**:
  - `NoteType`: Does it contain only schema rules, field definitions, template definitions, and marketplace metadata?
  - `Note`: Does it contain only structured content values and tags, without baking in rendering HTML or study progress?
  - `Template`: Does it define only presentation and interaction markup, without hardcoding content?
  - `Card`: Is it strictly a lightweight projection `(note_id, template_id)` with `uq_cards_note_template`?
- [ ] **Rendering Leakage**: Does `Note.field_values` contain raw HTML wrappers, rendered sound tags, or hardcoded UI CSS that belongs in `Template`?
- [ ] **Deck-to-NoteType Consistency**:
  - Is `decks.note_type_id` treated as a strict constraint or an optional default?
  - Does the codebase correctly handle mixed NoteTypes in a single deck (e.g., imported Anki decks)?
- [ ] **Multi-Interaction Extensibility**: Can a new study interaction (e.g., Japanese pitch accent matching or listening audio quiz) be expressed via a `Template` without adding new entity tables?

### Design & Evolution Rules
- **Preserve Projection Purity**: Never store learner progress or review stats on `Note` or `Card`. `Card` must remain a deterministic projection of `(Note, Template)`.
- **Generic Interaction Model**: Model custom interactions using structured FieldDefs (e.g., `options`, `correct_answer_indices`, `audio_prompt`) paired with interactive sandbox Templates (`<iframe sandbox="...">`).

---

## 3. Scheduler State & Multi-Algorithm Extensibility Checklist

Spaced-repetition state must support multiple scheduling engines (Legacy Anki SM-2, FSRS v4/v5, Flama Custom) without polluting generic domain entities.

### Investigation Questions
- [ ] **Generic vs Algorithm-Specific State**:
  - Are generic fields (`queue`, `due_at`, `due_day`, `interval_days`, `reps`, `lapses`) separated from algorithm-specific fields (`ease_factor` for SM-2, `memory_stability` / `memory_difficulty` for FSRS)?
- [ ] **Configuration Isolation**:
  - Are algorithm parameters stored in `SchedulerPreset` (`fsrs_parameters_json`, `learning_steps_json`) rather than hardcoded in Python services?
- [ ] **ReviewEvent Fact Immutability**:
  - Is `ReviewEvent` written as an immutable append-only fact?
  - Does `ReviewEvent` record both before and after transition states?
  - Are foreign keys on `deck_id` and `note_type_id` intentionally omitted to permit entity purging without deleting historical study analytics?
- [ ] **Batch Session Replay & Optimistic Concurrency**:
  - Does `StudySession` freeze configuration hashes (`scheduler_config_hash`) and initial card progress?
  - Does session commit verify transitions via server-side replay using `CardProgress.revision`?

### Design & Evolution Rules
- **Pluggable Algorithm Interface**: New schedulers must accept generic `CardState` + resolved options, output the next state, and record algorithm metadata in `ReviewEvent`.
- **No Direct Table Pollution**: Avoid adding new columns to `card_progress` for every experimental parameter; use structured algorithm state payloads if state is transient or experimental.

---

## 4. Marketplace / Release / Clone Overlay Integrity Checklist

Flama's overlay clone model allows distributed deck sharing, personalization, upstream updating, and community contribution without duplicating content rows.

### Investigation Questions
- [ ] **Overlay Purity**:
  - Does installing a shared deck (`DeckInstall`) create pointers and overlay records without duplicating source `notes` or `cards`?
  - Are local edits stored in `deck_clone_note_field_overrides`, `deck_clone_added_notes`, and `deck_clone_field_def_overrides`?
- [ ] **Release Immutability**:
  - Are `DeckRelease` and `DeckReleaseChange` rows strictly immutable once published?
  - Does release reconstruction correctly resolve historical field names and membership intervals?
- [ ] **3-Way Merge Integrity (Rebase)**:
  - When an installer updates to a new release (`DeckInstallRebase`), does the 3-way merge correctly compare `(base_release, target_release, local_overlay)`?
  - Are conflict resolutions (`keep_mine`, `keep_upstream`, `manual`) persisted with full auditability?
- [ ] **Change Request Synchronization**:
  - When a learner submits a `DeckChangeRequest`, is the fingerprint generated from local overlays?
  - Does merging a change request cleanly clear the contributor's overlay rows and stage release changes?

### Design & Evolution Rules
- **Zero Source Mutation**: Clone operations must NEVER modify source `Note` or `Card` records.
- **Stable Foreign Keys Across Releases**: Overlays and change requests must reference immutable `FieldDef.id` and `Note.id` to survive upstream renames.

---

## 5. Flama Connect & External Sync Provenance Checklist

Bridges Yomitan, AnkiConnect, and desktop companion processes with local database entities.

### Investigation Questions
- [ ] **External Reference Mapping**:
  - Does every external entity map to a local entity via `ConnectSource*Ref` tables (`ConnectSourceNoteRef`, `ConnectSourceDeckRef`, `ConnectSourceCardRef`)?
  - Are mappings scoped to `user_id` and `source_key` with unique constraints?
- [ ] **Media Staging & Materialization**:
  - Are temporary media uploads staged in `ConnectPendingMedia` or `ConnectImportMedia` before note creation?
  - Does materialization correctly calculate SHA-256 and clean up staging records after transaction commit?
- [ ] **Content Hash Idempotency**:
  - Does `ConnectSourceNoteRef.content_hash` prevent unnecessary updates and duplicates during repeated sync cycles?

---

## 6. MySQL OLTP Architectural Decision Checklist

### Investigation Questions
- [ ] **Integrity vs Cascade**: Are foreign key constraints configured with appropriate `ON DELETE CASCADE` or `ON DELETE SET NULL` actions?
- [ ] **Concurrency Control**: Are concurrent writes to shared entities protected by optimistic locking (`revision` counters) or tight transaction boundaries?
- [ ] **Index Coverage for Hot Access**:
  - Are composite indexes present for high-frequency queries (e.g., `(user_id, queue, due_day)` on `card_progress`)?
  - Do indexes avoid redundant prefixes?
- [ ] **Row Growth & JSON Bloat**:
  - Are large text payloads (e.g., changelogs, payloads, snapshots) stored efficiently without causing excessive table fragmentation?
