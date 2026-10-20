# Flama Entity Landscape & Domain Reference

This reference provides a comprehensive inventory of Flama's 10 core entity clusters, their declared models, primary keys, relationships, systems of record, and observed invariants.

---

## 1. Core Content & Schema

| Entity | Model File | Table Name | PK | Key Columns / JSON | Responsibilities & Invariants |
|---|---|---|---|---|---|
| **NoteType** | `models/note_type.py` | `note_types` | `id` (UUID String(36)) | `user_id`, `name`, `tags` (JSON), `taxonomy_metadata` (JSON), `pricing_mode`, `publish_status`, `version` | Schema definition container + Marketplace publishing root. Unique constraint `(user_id, name)`. |
| **FieldDef** | `models/field_def.py` | `field_defs` | `id` (UUID String(36)) | `note_type_id` (FK), `name`, `field_type` (Enum), `position`, `required`, `identity_role` | Stable schema definition for a field. Unique constraints on `(note_type_id, name)` and `(note_type_id, identity_role)`. |
| **Template** | `models/template.py` | `templates` | `id` (UUID String(36)) | `note_type_id` (FK), `name`, `front_html`, `back_html`, `shared_css`, `position`, `is_default` | Presentation template for card generation. Contains Mustache placeholders referencing field names. |
| **Note** | `models/note.py` | `notes` | `id` (UUID String(36)) | `user_id` (FK), `note_type_id` (FK), `deck_id` (FK nullable), `field_values` (JSON), `tags` (JSON) | Authoritative content record. `field_values` is a dictionary keyed by field names. |
| **Card** | `models/card.py` | `cards` | `id` (UUID String(36)) | `note_id` (FK), `template_id` (FK) | 1:1 projection of `(note, template)`. Enforced by `uq_cards_note_template`. |
| **MediaAsset** | `models/media_asset.py` | `media_assets` | `id` (UUID String(36)) | `note_id` (FK), `field_name`, `filename`, `mime_type`, `storage_path`, `sha256`, `size_bytes` | Physical media file attached to a Note. Unique by `(note_id, sha256, field_name)`. |
| **FieldRenameJob** | `models/field_rename_job.py` | `field_rename_jobs` | `id` (UUID String(36)) | `note_type_id` (FK), `field_def_id` (FK), `old_name`, `new_name`, `status`, `total_notes`, `processed_notes` | Progress/audit record for synchronous field key renames in `notes.field_values`. |

---

## 2. Organization & Deck Hierarchy

| Entity | Model File | Table Name | PK | Key Columns | Responsibilities & Invariants |
|---|---|---|---|---|---|
| **Deck** | `models/deck.py` | `decks` | `id` (Integer) | `parent_id` (FK self), `owner_user_id` (FK), `note_type_id` (FK nullable), `scheduler_preset_id` (FK nullable), `name`, `deleted_at` | Hierarchical deck tree. `note_type_id` is an optional default/binding. `parent_id` supports self-referential adjacency lists. |

---

## 3. Scheduler, Progress & Review Persistence

| Entity | Model File | Table Name | PK | Key Columns | Responsibilities & Invariants |
|---|---|---|---|---|---|
| **CardProgress** | `models/card_progress.py` | `card_progress` | `id` (Integer) | `user_id` (FK), `card_id` (FK), `queue`, `due_at`, `due_day`, `interval_days`, `interval_days_raw`, `ease_factor`, `memory_stability`, `memory_difficulty`, `revision`, `last_review_event_id` (FK) | Mutable spaced-repetition state per learner. Unique on `(user_id, card_id)`. `revision` enables optimistic concurrency. |
| **SchedulerPreset** | `models/scheduler_preset.py` | `scheduler_presets` | `id` (Integer) | `user_id` (FK), `name`, `learning_steps_json`, `relearning_steps_json`, `fsrs_parameters_json`, interval multipliers, leech parameters | User-configurable scheduler parameter profiles. Unique on `(user_id, name)`. |
| **UserSchedulerSettings** | `models/user_scheduler_settings.py` | `user_scheduler_settings` | `id` (Integer) | `user_id` (FK), `scheduler_mode` (`legacy` vs `fsrs`), `rollover_hour`, `learn_ahead_minutes` | Global scheduling preferences per user. Unique on `(user_id)`. |
| **ReviewEvent** | `models/review_event.py` | `review_events` | `id` (Integer) | `user_id` (FK), `card_id` (detached String), `deck_id` (detached Int), `note_type_id` (detached String), `rating`, `mode`, `scheduler_mode`, `reviewed_at`, `duration_ms`, before/after intervals & states, `payload_json` | Immutable learning analytics and audit log. Intentionally omits FKs on `card_id`, `deck_id`, `note_type_id` to allow safe entity purging while preserving history. |
| **StudySession** | `models/study_session.py` | `study_sessions` | `id` (UUID String(36)) | `user_id` (FK), `status`, `scheduler_algorithm`, `algorithm_version`, `config_snapshot_json`, `started_at`, `completed_at` | Bounded study session instance. Freezes configuration and initial card states for client-side execution. |
| **StudySessionCard** | `models/study_session_card.py` | `study_session_cards` | `id` (UUID String(36)) | `study_session_id` (FK), `card_id` (FK), `initial_progress_json`, `scheduler_config_hash` | Per-card snapshot and config hash frozen when a study session is opened. |
| **StudySessionCommit** | `models/study_session_commit.py` | `study_session_commits` | `id` (UUID String(36)) | `study_session_id` (FK), `idempotency_key`, `committed_cards_count`, `commit_receipt_json` | Idempotency receipt recorded when a completed study session batch is verified and applied atomically. |

---

## 4. Marketplace & Distribution

| Entity | Model File | Table Name | PK | Key Columns | Responsibilities & Invariants |
|---|---|---|---|---|---|
| **DeckMarketplaceItem** | `models/deck_marketplace_item.py` | `deck_marketplace_items` | `id` (UUID String(36)) | `source_deck_id` (FK), `owner_user_id` (FK), `source_note_type_id` (FK), `title`, `pricing_mode`, `publish_status`, `working_revision` | Marketplace catalog entry for a shared deck tree. Unique on `source_deck_id`. |
| **NoteTypeInstall** | `models/note_type_install.py` | `note_type_installs` | `id` (UUID String(36)) | `source_note_type_id` (FK), `user_id` (FK), `installed_note_type_id` (FK), `install_version` | Provenance record for installed NoteTypes (NoteType installation is a full schema copy). |
| **DeckReview** / **NoteTypeReview** | `models/deck_review.py`, `models/note_type_review.py` | `deck_reviews`, `note_type_reviews` | `id` (UUID String(36)) | `item_id` (FK), `user_id` (FK), `rating`, `review_text` | User ratings and reviews for marketplace items. Unique on `(item_id, user_id)`. |

---

## 5. Releases & Versioning

| Entity | Model File | Table Name | PK | Key Columns | Responsibilities & Invariants |
|---|---|---|---|---|---|
| **DeckRelease** | `models/deck_release.py` | `deck_releases` | `id` (UUID String(36)) | `marketplace_item_id` (FK), `parent_release_id` (FK self), `sequence_number`, `version_label`, `manifest_hash`, `notes_count` | Immutable release commit node in a deck's version DAG. Unique on `(marketplace_item_id, sequence_number)`. |
| **DeckReleaseChange** | `models/deck_release_change.py` | `deck_release_changes` | `id` (UUID String(36)) | `release_id` (FK), `change_type`, `entity_kind`, `entity_id`, `field_def_id` (FK nullable), `property_key`, `before_value_json`, `after_value_json` | Atomic entity/field deltas recorded in a release. Polymorphic entity addressing. |
| **DeckReleaseNoteCheckpoint** | `models/deck_release_note_checkpoint.py` | `deck_release_note_checkpoints` | `id` (UUID String(36)) | `release_id` (FK), `source_note_id` (FK), `field_values_json`, `tags_json`, `state_hash` | Full content snapshot of a Note at a specific release sequence. |
| **DeckReleaseEntityMembership** | `models/deck_release_entity_membership.py` | `deck_release_entity_membership` | `id` (UUID String(36)) | `marketplace_item_id` (FK), `entity_kind`, `entity_id`, `created_in_release_id` (FK), `deleted_in_release_id` (FK nullable) | Interval-based membership tracking for Notes and FieldDefs across release sequences. |
| **DeckWorkingDirtyEntity** | `models/deck_working_dirty_entity.py` | `deck_working_dirty_entity` | `id` (UUID String(36)) | `marketplace_item_id` (FK), `entity_kind`, `entity_id`, `dirty_state`, `working_revision` | Journal tracking unreleased working-tree mutations for fast release preview. |

---

## 6. Clone Overlays & Local Personalization

| Entity | Model File | Table Name | PK | Key Columns | Responsibilities & Invariants |
|---|---|---|---|---|---|
| **DeckInstall** | `models/deck_install.py` | `deck_installs` | `id` (UUID String(36)) | `deck_item_id` (FK), `user_id` (FK), `local_deck_id` (FK), `source_deck_id` (FK), `applied_release_id` (FK), `overlay_revision`, `clone_mode` | Root of a logical overlay deck installation. Unique on `(deck_item_id, user_id)`. |
| **DeckCloneDeckMap** | `models/deck_clone_deck_map.py` | `deck_clone_deck_maps` | `id` (UUID String(36)) | `deck_install_id` (FK), `source_deck_id` (FK), `local_deck_id` (FK) | 1:1 mapping between source deck subtree nodes and local installer deck nodes. |
| **DeckCloneFieldDefOverride** | `models/deck_clone_field_def_override.py` | `deck_clone_field_def_overrides` | `id` (UUID String(36)) | `deck_install_id` (FK), `source_field_def_id` (FK), `name`, `field_type`, `required` | Local customizations to a shared field's schema definition. |
| **DeckCloneAddedFieldDef** | `models/deck_clone_added_field_def.py` | `deck_clone_added_field_defs` | `id` (UUID String(36)) | `deck_install_id` (FK), `name`, `field_type`, `position`, `required` | Learner-created custom fields added exclusively to their local overlay. |
| **DeckCloneFieldOrderOverride** | `models/deck_clone_field_order_override.py` | `deck_clone_field_order_overrides` | `id` (UUID String(36)) | `deck_install_id` (FK), `ordered_def_ids` (JSON) | Custom field ordering array combining source FieldDef IDs and added FieldDef IDs. Unique per install. |
| **DeckCloneNoteFieldOverride** | `models/deck_clone_note_field_override.py` | `deck_clone_note_field_overrides` | `id` (UUID String(36)) | `deck_install_id` (FK), `source_note_id` (FK), `source_field_def_id` (FK nullable), `field_name`, `operation`, `value` (JSON) | Learner edits to specific fields of a source Note. Dual unique constraints on name and field_def_id. |
| **DeckCloneAddedNote** | `models/deck_clone_added_note.py` | `deck_clone_added_notes` | `id` (UUID String(36)) | `deck_install_id` (FK), `note_id` (FK), `local_deck_id` (FK) | Learner-created custom Notes added to an installed deck. |

---

## 7. Rebase & Change Requests

| Entity | Model File | Table Name | PK | Key Columns | Responsibilities & Invariants |
|---|---|---|---|---|---|
| **DeckInstallRebase** | `models/deck_install_rebase.py` | `deck_install_rebases` | `id` (UUID String(36)) | `deck_install_id` (FK), `base_release_id` (FK), `target_release_id` (FK), `status`, `conflict_count` | Represents a 3-way rebase update from a base release to a target upstream release. |
| **DeckInstallRebaseConflict** | `models/deck_install_rebase_conflict.py` | `deck_install_rebase_conflicts` | `id` (UUID String(36)) | `rebase_id` (FK), `entity_kind`, `entity_id`, `field_def_id` (FK nullable), `conflict_type`, `resolution`, `resolved_value_json` | Conflict item requiring learner resolution during an upstream deck update. |
| **DeckChangeRequest** | `models/deck_change_request.py` | `deck_change_requests` | `id` (UUID String(36)) | `deck_install_id` (FK), `marketplace_item_id` (FK), `status`, `title`, `base_release_id` (FK) | Learner contribution PR submitted to the deck author. |
| **DeckChangeRequestItem** | `models/deck_change_request_item.py` | `deck_change_request_items` | `id` (UUID String(36)) | `change_request_id` (FK), `entity_kind`, `entity_id`, `field_def_id` (FK nullable), `change_type`, `suggested_value_json` | Individual proposed change item within a contribution request. |
| **DeckChangeRequestConflict** | `models/deck_change_request_conflict.py` | `deck_change_request_conflicts` | `id` (UUID String(36)) | `change_request_id` (FK), `item_id` (FK), `conflict_type`, `resolution` | Upstream vs contributor conflict detected when syncing a change request against live author state. |

---

## 8. External Synchronization & Flama Connect

| Entity | Model File | Table Name | PK | Key Columns | Responsibilities & Invariants |
|---|---|---|---|---|---|
| **ConnectSourceDeckRef** | `models/connect_source_deck_ref.py` | `connect_source_deck_refs` | `id` (UUID String(36)) | `user_id` (FK), `source_key`, `external_deck_id`, `deck_id` (FK) | Mapping between external deck ID/path and local Deck entity. |
| **ConnectSourceNoteRef** | `models/connect_source_note_ref.py` | `connect_source_note_refs` | `id` (UUID String(36)) | `user_id` (FK), `source_key`, `external_note_id`, `note_id` (FK), `content_hash` | Mapping between external note ID (Anki/Yomitan) and local Note entity. Unique on `(user_id, source_key, external_note_id)`. |
| **ConnectSourceCardRef** | `models/connect_source_card_ref.py` | `connect_source_card_refs` | `id` (UUID String(36)) | `user_id` (FK), `source_key`, `external_card_id`, `card_id` (FK) | Mapping between external card ID (Anki card ID) and local Card entity. |
| **ConnectReviewEventRef** | `models/connect_review_event_ref.py` | `connect_review_event_refs` | `id` (UUID String(36)) | `user_id` (FK), `source_key`, `external_review_id`, `review_event_id` (FK) | Deduplication bridge mapping Anki revlog timestamps to local ReviewEvent records. |
| **ConnectPendingMedia** | `models/connect_pending_media.py` | `connect_pending_media` | `id` (UUID String(36)) | `user_id` (FK), `filename`, `sha256`, `storage_path`, `expires_at` | Staging table for audio files uploaded via Yomitan before note creation. |
| **ConnectImportSession** | `models/connect_import_session.py` | `connect_import_sessions` | `id` (UUID String(36)) | `user_id` (FK), `source_type`, `status`, `manifest_json`, `stats_json` | Lifecycle tracking for multi-file Anki `.apkg` or `.colpkg` import jobs. |
| **ConnectImportMedia** | `models/connect_import_media.py` | `connect_import_media` | `id` (UUID String(36)) | `session_id` (FK), `filename`, `sha256`, `storage_path`, `size_bytes` | Media files extracted from an import package awaiting attachment to Notes. |

---

## 9. Identity, Roles & MCP Tokens

| Entity | Model File | Table Name | PK | Key Columns | Responsibilities & Invariants |
|---|---|---|---|---|---|
| **User** | `models/user.py` | `users` | `id` (Integer) | `email`, `username`, `password_hash`, `is_admin`, `is_active` | Core user identity. |
| **UserRole** | `models/user_role.py` | `user_roles` | `id` (Integer) | `user_id` (FK), `role_name` (`admin`, `editor`, `learner`) | Role-based authorization mapping. |
| **OAuthClient** / **McpAccessToken** | `models/oauth_client.py`, `models/mcp_access_token.py` | `oauth_clients`, `mcp_access_tokens` | `id` (UUID String(36)) | `client_id`, `user_id` (FK), `token_hash`, `scopes`, `expires_at` | Protocol access tokens for Model Context Protocol (MCP) clients. |

---

## 10. Operational, Payments & Media Catalogs

| Entity | Model File | Table Name | PK | Key Columns | Responsibilities & Invariants |
|---|---|---|---|---|---|
| **SharedImageAsset** | `models/shared_image_asset.py` | `shared_image_assets` | `id` (UUID String(36)) | `image_key` (Unique String), `storage_path`, `sha256`, `tags` (JSON), `is_enabled` | Global, reusable image catalog independent of individual user notes. |
| **PaymentOrder** | `models/payment_order.py` | `payment_orders` | `id` (UUID String(36)) | `user_id` (FK), `order_code` (BigInt), `amount`, `status`, `provider` (`payos`) | Transaction record for payOS checkout sessions. |
| **AuditLog** | `models/audit_log.py` | `audit_logs` | `id` (Integer) | `user_id` (FK nullable), `entity_type`, `entity_id`, `action`, `payload_json`, `created_at` | General-purpose operational audit trail. |
