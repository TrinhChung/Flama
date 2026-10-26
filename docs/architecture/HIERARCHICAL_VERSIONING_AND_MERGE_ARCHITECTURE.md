# Hierarchical Versioning, Conflict Resolution & Cascading Merge Architecture

**Document Type**: Architectural Standard & Data Contract Specification (R1, R2, R3, R4, R5)  
**System**: Flama Spaced Repetition Learning Platform (`nihongo`)  
**Scope**: Triad Versioning (`Deck` $\to$ `NoteType` $\to$ `CardTemplate`), High-Volume Merge UI (1,000+ Cards), 1-Click Cascading Sync, and SRS Progress Immutability  
**Status**: APPROVED ARCHITECTURAL SPECIFICATION  
**Author**: Flama Architecture Team (`teamwork_preview_worker_26_m1`)  
**Date**: 2026-10-26  
**Target Codebase**: `models/`, `app/services/`, `app/api/v1/`, `frontend/src/`  

---

## Table of Contents
1. [Executive Summary & System Vision](#1-executive-summary--system-vision)
   - 1.1 Context & Motivation
   - 1.2 The Triad Hierarchy: Deck, Note Type, and Card Template
   - 1.3 Key Architectural Tenets
2. [Entity & State Lifecycle Models](#2-entity--state-lifecycle-models)
   - 2.1 Entity Inventory & Relational Schema
   - 2.2 The Quad-State Lifecycle (`Draft`, `Published`, `Pinned`, `Deprecated`)
   - 2.3 Mathematical Immutability & Event Protection
   - 2.4 Virtual Card Presentation Architecture (ADR P11)
   - 2.5 Absolute Immutability of Study Progress (`CardProgress`)
3. [REST API Contracts & Data Transfer Objects (DTOs)](#3-rest-api-contracts--data-transfer-objects-dtos)
   - 3.1 Endpoint 1: Deck Structural Dependencies Overview
   - 3.2 Endpoint 2: Note Type Dependency Coherence & Warning Inspection
   - 3.3 Endpoint 3: High-Volume Grouped Diff Feed (Cursor-Paginated)
   - 3.4 Endpoint 4: High-Volume Batch Review & Cherry-Pick Action
   - 3.5 Endpoint 5: 1-Click Cascading Consumer Update Execution
4. [Conflict Resolution Algebra & Data Safety Invariants](#4-conflict-resolution-algebra--data-safety-invariants)
   - 4.1 Three-Way Merge Mathematical Algebra
   - 4.2 Conflict Resolution Modes (`keep_mine`, `keep_upstream`, `manual`)
   - 4.3 Native Array JSON Preservation & Bracket-Shielding Rules
   - 4.4 Non-Destructive Tombstoning & Schema Evolution Invariants
5. [Frontend UI/UX Architecture & FSD Layout](#5-frontend-uiux-architecture--fsd-layout)
   - 5.1 Pragmatic Feature-Sliced Design (FSD) Slicing
   - 5.2 Windowed Virtualization Engine (`useVirtualDiffList`)
   - 5.3 Ergonomic High-Volume Review Workspace Design
   - 5.4 Zero Visual Regression & Design System Conformance
6. [4-Tier Verification & Test Strategy](#6-4-tier-verification--test-strategy)
   - 6.1 Tier 1: Unit & Merge Algebra Verification
   - 6.2 Tier 2: MySQL 8.0 Transactional & Constraint Integration
   - 6.3 Tier 3: Scalability Stress & DOM Node Virtualization Benchmarks
   - 6.4 Tier 4: Concurrent Cascading Sync Race Condition Verification
7. [Database Migration & Schema Evolution Plan](#7-database-migration--schema-evolution-plan)
   - 7.1 Proposed Schema Extension (`deck_release_note_type_pins`)
   - 7.2 Alembic Migration Blueprint
8. [Production Implementation Matrix & Quality Gates](#8-production-implementation-matrix--quality-gates)

---

## 1. Executive Summary & System Vision

### 1.1 Context & Motivation
The Flama platform operates as a modern spaced repetition (SRS) web application built upon a decoupled React 19 Single Page Application (SPA) and a high-performance Flask/MySQL 8.0 InnoDB backend. Over multiple architectural iterations (Flashcard v2 cutover, ADR P11 derived card presentation, and the Logical Overlay cloner model), physical card duplication has been eliminated. In this system:
- A **Card** is not an independently persisted database record; rather, it is dynamically computed at query time via a Cartesian subquery:
  $$\text{Card} = \text{Note} \times \text{StudyApplication}_{(\text{status\_code}=\text{'ACTIVE'})}$$
- A **Learner's Personal Study Sandbox** is stored through non-destructive overlay records (`DeckCloneNoteFieldOverride`), ensuring that learning progress (`CardProgress` and `StudyProgressSubject`) is completely decoupled from content updates.

However, as creators collaborate on large-scale educational decks (often containing 1,000 to 5,000+ notes) and share reusable note types and card templates across the community marketplace, three critical challenges emerge:
1. **Entangled Structural & Content Releases**: Publishing a deck release currently conflates note content edits, field definition alterations, and template styling into a single flat change stream. Creators editing vocabulary notes are overwhelmed by template markup diffs, while template designers have no safe way to publish styling revisions without risking breakage across downstream decks.
2. **Visual & Memory Collapse in High-Volume Reviews**: When evaluating change requests or version upgrades involving thousands of cards, standard unvirtualized DOM trees crash browser tabs, lack note-type organization, and fail to provide bulk decision-making tools (e.g. batch approving an entire grammar note type).
3. **Fragmented Consumer Sync Workflows**: When a deck author publishes an upgrade containing new vocabulary, an added audio field, and an updated card template layout, the subscriber must manually navigate between deck update pages and template distribution screens to synchronize each layer.

### 1.2 The Triad Hierarchy: Deck, Note Type, and Card Template
To resolve these architectural tensions, this specification formalizes the **Triad Versioning Hierarchy**:

```
+----------------------------------------------------------------------------------------------------+
|                                    FLAMA TRIAD VERSIONING HIERARCHY                                |
+----------------------------------------------------------------------------------------------------+
|                                                                                                    |
|    LEVEL 1: DECK RELEASE (Container & Content Snapshot)                                           |
|    - Immutable manifest of note memberships and content revisions.                                 |
|    - Freezes exact semantic release versions of all utilized Note Types and Templates.            |
|    - Governs what notes belong to the study curriculum.                                            |
|                                     │                                                              |
|                     ┌───────────────┴───────────────┐                                              |
|                     ▼                               ▼                                              |
|    LEVEL 2: NOTE TYPE RELEASE                      LEVEL 3: CARD TEMPLATE RELEASE                  |
|    (Data Schema & Semantic Contract)               (Visual Presentation & Markup Engine)           |
|    - Immutable snapshot of `FieldDef`s.            - Immutable snapshot of HTML/CSS/Mustache AST.  |
|    - Defines semantic roles, required flags,        - Defines visual layout, responsive styles,     |
|      and native array specifications.                and input schema requirements.                |
|    - Binds `StudyApplication` occurrences to       - Reusable across multiple Note Types.          |
|      exact Template Release pins.                  - Completely decoupled from note data.          |
|                                                                                                    |
+----------------------------------------------------------------------------------------------------+
```

### 1.3 Key Architectural Tenets
1. **Separation of Concerns (Zero Diff Leakage)**: The deck release overview displays high-level structural status badges and deep-link call-to-actions (CTAs) directing authors to specialized Note Type or Template editors. Raw HTML/CSS or JSON schema diffs are strictly prohibited from polluting the deck versioning UI.
2. **Proactive Dependency Coherence**: Note Types actively monitor attached templates. If a template evolves or has uncommitted drafts, the Note Type surfaces actionable coherence warnings before schema publishing occurs.
3. **In-Flow Windowed Virtualization**: Diff reviews for 1,000+ cards must sustain a stable DOM count of fewer than 150 nodes, running at 60 frames per second on mid-tier mobile and desktop devices.
4. **1-Click Cascading Atomicity**: When a consumer updates an installed deck, a single atomic transaction synchronizes `DeckInstall`, `NoteTypeInstall`, and `TemplateSubscription` to their pinned releases, rebases local field overrides, and guarantees zero loss of spaced repetition history.
5. **Native Array Preservation**: Array-type fields are stored and manipulated as pure JSON lists. String flattening or Anki newline degeneration is strictly prohibited across all merge and synchronization layers.

---

## 2. Entity & State Lifecycle Models

### 2.1 Entity Inventory & Relational Schema
The versioning and cascading sync engine is governed by five primary entities and their relational pin junctions:

```
+----------------------------------------------------------------------------------------------------+
|                                      RELATIONAL ENTITY MAP                                         |
+----------------------------------------------------------------------------------------------------+
|                                                                                                    |
|   ┌────────────────────────┐                   ┌────────────────────────┐                          |
|   │       decks            │ 1               * │   deck_marketplace_    │                          |
|   │ (Local Tree Workspace) ├───────────────────┤         items          │                          |
|   └────────────────────────┘                   └───────────┬────────────┘                          |
|                                                            │ 1                                     |
|                                                            ▼ *                                     |
|                                                ┌────────────────────────┐                          |
|                                                │     deck_releases      │                          |
|                                                │  (Immutable Milestones)│                          |
|                                                └─────┬────────────┬─────┘                          |
|                                                    1 │            │ 1                              |
|                         ┌────────────────────────────┘            └────────────────────┐           |
|                         ▼ *                                                          * ▼           |
|           ┌───────────────────────────┐                              ┌───────────────────────────┐ |
|           │deck_release_note_type_pins│                              │deck_release_template_pins │ |
|           │  (Frozen Schema Binding)  │                              │(Frozen Presentation Pin)  │ |
|           └─────────────┬─────────────┘                              └─────────────┬─────────────┘ |
|                       * │                                                        * │               |
|                         ▼ 1                                                        ▼ 1             |
|           ┌───────────────────────────┐                              ┌───────────────────────────┐ |
|           │    note_type_releases     │                              │     template_releases     │ |
|           │(Manifest & FieldDef Hash) │                              │ (Immutable Code Snapshot) │ |
|           └─────────────▲─────────────┘                              └─────────────▲─────────────┘ |
|                       1 │                                                        1 │               |
|                         │ *                                                        │ *             |
|           ┌─────────────┴─────────────┐                              ┌─────────────┴─────────────┐ |
|           │        note_types         │                              │         templates         │ |
|           │   (Mutable Author Draft)  │                              │   (Author Markup Draft)   │ |
|           └───────────────────────────┘                              └───────────────────────────┘ |
|                                                                                                    |
+----------------------------------------------------------------------------------------------------+
```

#### Detailed Entity Specifications:
1. **`DeckRelease` (`models/deck_release.py`)**:
   - Primary identifier: `id` (UUIDv4 string).
   - Foreign key: `deck_item_id` referencing `deck_marketplace_items.id`.
   - Sequence: `sequence_no` (monotonically increasing integer) and `version_label` (SemVer string).
   - Checkpoints: `manifest_hash` (SHA-256 digest of note memberships and contents), `parent_release_id`.
   - Counters: `change_count`, `entity_count`, `added_count`, `modified_count`, `removed_count`.
2. **`NoteTypeRelease` (`models/note_type_release.py`)**:
   - Primary identifier: `id` (UUIDv4 string).
   - Foreign key: `note_type_id` referencing `note_types.id`.
   - Manifest: `manifest_json` (complete JSON serialization of `fields`, `applications`, and pinned `template_release_id`s).
   - Checksum: `content_hash` (tamper-evident SHA-256 of `manifest_json`).
3. **`TemplateRelease` (`models/template_release.py`)**:
   - Primary identifier: `id` (UUIDv4 string).
   - Foreign key: `template_id` referencing `templates.id`.
   - Version reference: `version_id` referencing immutable snapshot row in `template_versions`.
   - Milestone: `version_label`, `sequence_no`, `change_note`, `publish_mode` (`'public'` | `'unlisted'`).
4. **`DeckReleaseTemplatePin` (`models/deck_release_template_pin.py`)**:
   - Junction binding `deck_release_id` to `source_template_id` and exact `template_release_id`.
   - Serialized presentation: `applications_json` (freezes occurrence keys, display names, and input bindings).
5. **`DeckReleaseNoteTypePin` (New Architectural Entity: `deck_release_note_type_pins`)**:
   - Junction binding `deck_release_id` to `note_type_id` and exact `note_type_release_id`.
   - Guarantees that multi-note-type decks freeze the complete schema of every note type utilized.

---

### 2.2 The Quad-State Lifecycle (`Draft`, `Published`, `Pinned`, `Deprecated`)

Every versioned asset progresses through an explicit finite-state machine (FSM):

```
+----------------------------------------------------------------------------------------------------+
|                                    QUAD-STATE FINITE STATE MACHINE                                 |
+----------------------------------------------------------------------------------------------------+
|                                                                                                    |
|    [ DRAFT ]  ──(Validate & Publish)──>  [ PUBLISHED ]  ──(Bind to Deck/Install)──>  [ PINNED ]     |
|        │                                       │                                          │        |
|        │ Discard                               │ Superseded                               │ Release|
|        │ Modifications                         │ by Newer                                 │ Retired|
|        ▼                                       ▼                                          ▼        |
|    [ CLEAN ]                             [ DEPRECATED ]                            [ DEPRECATED ]  |
|                                                                                                    |
+----------------------------------------------------------------------------------------------------+
```

#### State Definitions & Operational Rules:
1. **`DRAFT` (Working Tree)**:
   - *Characteristics*: Mutable state where creators perform day-to-day additions, edits, and reorderings.
   - *Isolation*: Draft modifications in `Note`, `NoteType`, or `Template` are completely invisible to consumers. Learner clones only read from the immutable release pointed to by `DeckInstall.applied_release_id`.
   - *Tracking*: Decks track dirty state in `deck_working_dirty_entities`; Note Types track modifications via `field_schema_revision`.
2. **`PUBLISHED` (Immutable Release Milestone)**:
   - *Characteristics*: Read-only snapshot of the entity at a discrete point in time, accompanied by a SemVer label (`x.y.z`) and SHA-256 integrity hash.
   - *Invariants*: Content rows (`deck_release_changes`, `note_type_releases`, `template_versions`) cannot be modified or updated under any circumstances.
3. **`PINNED` (Frozen Relational Binding)**:
   - *Characteristics*: A `Published` release referenced by a parent container or consumer installation.
   - *Operational Rule*: Even if the upstream author subsequently modifies the draft or publishes a newer release, the pinned consumer environment remains 100% frozen until an explicit update is executed.
4. **`DEPRECATED` (Historical Archive / Tombstone)**:
   - *Characteristics*: Older releases superseded by subsequent versions or unlisted from the public marketplace.
   - *Retention Invariant*: Deprecated releases are **never deleted from the database**. They are retained permanently to ensure auditability, preserve historical review events, and allow learners to revert updates without data corruption.

---

### 2.3 Mathematical Immutability & Event Protection

To prevent accidental modification or database-level tampering with published milestones, the backend enforces mathematical immutability through SQLAlchemy event listeners:

```python
# Enforcement Pattern: app/services/release_core/immutability_listener.py
from sqlalchemy import event
from sqlalchemy.orm import Mapper
from models.note_type_release import NoteTypeRelease
from models.deck_release import DeckRelease
from models.template_release import TemplateRelease

class ImmutableReleaseViolation(Exception):
    """Raised when an attempt is made to mutate or delete a published release."""
    pass

def _block_release_mutation(mapper: Mapper, connection, target):
    raise ImmutableReleaseViolation(
        f"Security violation: Entity {target.__class__.__name__} (ID: {target.id}) "
        "is an immutable published release and cannot be modified."
    )

def _block_release_deletion(mapper: Mapper, connection, target):
    raise ImmutableReleaseViolation(
        f"Security violation: Entity {target.__class__.__name__} (ID: {target.id}) "
        "is an immutable published release and cannot be deleted."
    )

for model in [DeckRelease, NoteTypeRelease, TemplateRelease]:
    event.listen(model, "before_update", _block_release_mutation)
    event.listen(model, "before_delete", _block_release_deletion)
```

---

### 2.4 Virtual Card Presentation Architecture (ADR P11)

Under Architectural Decision Record (ADR) P11, Flama eliminated physical card records in the database. Cards are derived dynamically using the SQL presentation view:

$$\text{Card} = \text{Note} \Join_{\text{note\_type\_id}} \text{StudyApplication}_{(\text{status\_code}=\text{'ACTIVE'})}$$

#### Key Presentation Properties:
1. **Deterministic Identity**: The virtual card ID is generated as:
   $$\text{Card.id} = \text{f"}\{\text{note\_id}\}.\{\text{application\_id}\}\text{"}$$
2. **Zero Row Duplication**: Adding a second study application (for example, generating a "Reverse Recognition" or "Audio Typing" card from an existing vocabulary note) creates exactly one row in `study_applications`. The database instantly presents cards for all 10,000 notes linked to that Note Type without inserting 10,000 new card rows.
3. **Write Protection**: Any ORM `INSERT`, `UPDATE`, or `DELETE` directed at `models.Card` is intercepted by SQLAlchemy session hooks (`before_flush` and `do_orm_execute`) and immediately raises a `TypeError` (`models/card.py:215-229`).

---

### 2.5 Absolute Immutability of Study Progress (`CardProgress`)

Spaced repetition parameters and learning histories are stored in `StudyProgressSubject` (`models/study_progress_subject.py`) and indexed strictly by:
$$(\text{user\_id}, \text{logical\_note\_key})$$
where `logical_note_key` maps directly to the stable note identifier.

#### Mathematical Invariant of Cascading Sync:
When a learner synchronizes a deck containing structural updates (e.g. Note Type fields added, CSS styles upgraded, HTML templates restructured), the following invariants are mathematically preserved:

$$\Delta(\text{CardProgress.due\_day}) = 0$$
$$\Delta(\text{CardProgress.stability}) = 0$$
$$\Delta(\text{CardProgress.difficulty}) = 0$$
$$\Delta(\text{CardProgress.reps}) = 0$$
$$\Delta(\text{CardProgress.lapses}) = 0$$
$$\Delta(\text{ReviewEvent.count}) = 0$$

Because `Note.id` and `StudyApplication.id` remain constant during template and schema rebases, spaced repetition memory traces are completely immune to presentation styling and layout refactoring.

---

## 3. REST API Contracts & Data Transfer Objects (DTOs)

All endpoints conform to the following global conventions:
- Base path: `/api/`
- Authentication: Handled via session cookie (`@login_required`) or bearer token.
- Content Type: `application/json; charset=utf-8`
- Error format: Standard error envelope `{ "error": string, "message": string, "status": number, "field": string | null }`
- Idempotency: Mutation endpoints require the `Idempotency-Key: <uuid>` header.

---

### 3.1 Endpoint 1: Deck Structural Dependencies Overview
- **Method & Route**: `GET /api/marketplace/decks/<deck_item_id>/structural-dependencies`
- **Purpose**: Provides a high-level summary of all Note Types and Templates utilized within a deck, comparing currently pinned versions against author drafts and latest published releases. Displays status badges and direct navigation CTAs without dumping raw code/JSON diffs.

#### Request Parameters:
- Path parameter: `deck_item_id` (string, UUIDv4 of the marketplace deck item).

#### Response Schema (`DeckStructuralDependenciesResponseDto`):
```json
{
  "deckItemId": "c3a7e4b2-8f19-4d32-9c10-2b5e7a9f81d4",
  "deckTitle": "Tiếng Nhật Trung cấp N3 - Soumatome",
  "currentRelease": {
    "id": "rel_deck_102",
    "versionLabel": "1.2.0",
    "sequenceNo": 2,
    "publishedAt": "2026-08-15T09:30:00Z"
  },
  "contentChanges": {
    "hasUnpublishedChanges": true,
    "workingRevision": 142,
    "addedNotes": 15,
    "modifiedNotes": 42,
    "removedNotes": 2,
    "totalChangedProperties": 128
  },
  "noteTypes": [
    {
      "noteTypeId": "nt_vocab_n3",
      "name": "Từ vựng N3 Chuẩn",
      "noteCount": 1420,
      "pinnedRelease": {
        "id": "rel_nt_201",
        "versionLabel": "1.0.0",
        "publishedAt": "2026-07-01T12:00:00Z"
      },
      "latestRelease": {
        "id": "rel_nt_202",
        "versionLabel": "1.1.0",
        "publishedAt": "2026-10-20T14:15:00Z"
      },
      "status": "update_available",
      "hasDraftChanges": false,
      "editorUrl": "/note-types/nt_vocab_n3",
      "templates": [
        {
          "templateId": "tmpl_vocab_card_front",
          "name": "Thẻ Từ vựng - Nhận diện",
          "occurrenceKey": "occ_main",
          "pinnedRelease": {
            "id": "rel_tmpl_301",
            "versionLabel": "2.0.0"
          },
          "latestRelease": {
            "id": "rel_tmpl_302",
            "versionLabel": "2.1.0"
          },
          "status": "draft_changes",
          "hasDraftChanges": true,
          "editorUrl": "/card-templates/tmpl_vocab_card_front"
        }
      ]
    }
  ],
  "canPublishContent": true,
  "blockingReasons": []
}
```

---

### 3.2 Endpoint 2: Note Type Dependency Coherence & Warning Inspection
- **Method & Route**: `GET /api/note-types/<note_type_id>/dependency-coherence`
- **Purpose**: Verifies that active `StudyApplication`s linked to a Note Type reference synchronized, compatible template releases. Detects uncommitted drafts, outdated pins, or unmapped input bindings.

#### Request Parameters:
- Path parameter: `note_type_id` (string, UUIDv4).

#### Response Schema (`NoteTypeDependencyCoherenceDto`):
```json
{
  "noteTypeId": "nt_vocab_n3",
  "name": "Từ vựng N3 Chuẩn",
  "isCoherent": false,
  "currentRelease": {
    "id": "rel_nt_201",
    "versionLabel": "1.0.0",
    "sequenceNo": 1
  },
  "suggestedVersion": "1.1.0",
  "warnings": [
    {
      "templateId": "tmpl_vocab_card_front",
      "templateName": "Thẻ Từ vựng - Nhận diện",
      "applicationId": "app_recognition_card",
      "pinnedRelease": "2.0.0",
      "latestRelease": "2.1.0",
      "warningType": "OUTDATED_PIN",
      "message": "Mẫu thẻ 'Thẻ Từ vựng - Nhận diện' đã phát hành bản v2.1.0 mới hơn bản đang ghim (v2.0.0).",
      "actionRecommendation": "Cập nhật phiên bản ghim sang v2.1.0 trước khi phát hành Note Type."
    },
    {
      "templateId": "tmpl_vocab_card_front",
      "templateName": "Thẻ Từ vựng - Nhận diện",
      "applicationId": "app_recognition_card",
      "pinnedRelease": "2.0.0",
      "latestRelease": "2.1.0",
      "warningType": "UNCOMMITTED_DRAFT",
      "message": "Mẫu thẻ có bản nháp chưa công bố trên Marketplace.",
      "actionRecommendation": "Mở trang Mẫu thẻ để phát hành bản nháp thành Release trước."
    }
  ],
  "templateAttachments": [
    {
      "applicationId": "app_recognition_card",
      "templateId": "tmpl_vocab_card_front",
      "templateName": "Thẻ Từ vựng - Nhận diện",
      "occurrenceKey": "occ_main",
      "pinnedReleaseId": "rel_tmpl_301",
      "pinnedVersionLabel": "2.0.0",
      "latestReleaseId": "rel_tmpl_302",
      "latestVersionLabel": "2.1.0",
      "hasUnpublishedDraft": true,
      "unboundRequiredInputs": []
    }
  ]
}
```

---

### 3.3 Endpoint 3: High-Volume Grouped Diff Feed (Cursor-Paginated)
- **Method & Route**: `GET /api/marketplace/decks/<deck_item_id>/change-reviews/<request_id>`
- **Purpose**: High-volume, cursor-paginated diff feed engineered for 1,000+ to 10,000+ card changes. Returns hierarchical groupings aggregated by Note Type and change type (`added`, `modified`, `removed`), eliminating payload bloat and UI lockup.

#### Query Parameters:
- `cursor`: Base64 encoded keyset cursor (containing `sort_key` and `note_id`).
- `limit`: Number of note diff items per page (default `100`, max `250`).
- `noteTypeId`: Optional filter for a specific Note Type ID.
- `changeType`: Filter by `'all'` | `'added'` | `'modified'` | `'removed'`.
- `search`: Substring search query matching note vocabulary or field values (max 200 chars).

#### Response Schema (`HighVolumeDiffEnvelopeDto`):
```json
{
  "summary": {
    "totalNotes": 1250,
    "addedCount": 800,
    "modifiedCount": 400,
    "removedCount": 50,
    "conflictCount": 0,
    "noteTypes": [
      {
        "id": "nt_vocab_n3",
        "name": "Từ vựng N3 Chuẩn",
        "count": 1150
      },
      {
        "id": "nt_kanji_n3",
        "name": "Kanji N3",
        "count": 100
      }
    ]
  },
  "notesPage": [
    {
      "noteId": "note_uuid_84719",
      "noteTypeId": "nt_vocab_n3",
      "noteTypeName": "Từ vựng N3 Chuẩn",
      "changeType": "modified",
      "primaryText": "準備 (じゅんび)",
      "secondaryText": "Chuẩn bị",
      "fieldDiffs": [
        {
          "fieldDefId": "fdef_example_vi",
          "fieldName": "Example_VI",
          "fieldType": "text",
          "before": "Tôi đang chuẩn bị.",
          "after": "Tôi đang chuẩn bị cho kỳ thi tiếng Nhật JLPT N3.",
          "isConflict": false
        }
      ],
      "status": "pending"
    }
  ],
  "nextCursor": "ZXlKaGJHY2lPaUpTVXpVeE1pSXNJbXRwT2lKd1lXUm5kV2x1..."
}
```

---

### 3.4 Endpoint 4: High-Volume Batch Review & Cherry-Pick Action
- **Method & Route**: `POST /api/marketplace/decks/<deck_item_id>/change-requests/<request_id>/batch-action`
- **Purpose**: Executes bulk approval, rejection, or cherry-picking across hundreds or thousands of card diffs in a single database roundtrip.

#### Request Schema (`BatchReviewActionRequestDto`):
```json
{
  "action": "batch_approve",
  "selection": {
    "mode": "by_note_type",
    "noteTypeId": "nt_vocab_n3",
    "filterOperation": "modified",
    "excludedNoteIds": ["note_uuid_84719"]
  },
  "resolutionMode": "keep_mine",
  "expectedRevision": 14
}
```

#### Response Schema (`BatchActionResultDto`):
```json
{
  "status": "success",
  "action": "batch_approve",
  "processedCount": 399,
  "remainingPendingCount": 851,
  "remainingConflictCount": 0,
  "updatedRevision": 15
}
```

---

### 3.5 Endpoint 5: 1-Click Cascading Consumer Update Execution
- **Method & Route**: `POST /api/marketplace/installations/<install_id>/updates/<release_id>/apply`
- **Purpose**: Applies an author's new deck release to an installed clone deck. In a single atomic transaction, cascades updates to `DeckRelease`, `NoteTypeInstall`, and `TemplateSubscription`, reconciles local card overrides, and returns a detailed sync receipt.

#### Request Headers:
- `Idempotency-Key: <uuid>` (mandatory)

#### Request Schema (`ApplyCascadingUpdateRequestDto`):
```json
{
  "expectedAppliedReleaseId": "rel_deck_102",
  "expectedOverlayRevision": 8,
  "cascadeOptions": {
    "autoAcceptCompatibleStructuralUpdates": true,
    "conflictResolutionDefault": "keep_mine"
  }
}
```

#### Response Schema (`CascadingSyncResultDto`):
```json
{
  "success": true,
  "deckInstallId": "inst_deck_9821",
  "newReleaseVersion": "1.3.0",
  "synchronizedComponents": {
    "cardsUpdated": 1250,
    "noteTypesSynchronized": [
      {
        "id": "nt_vocab_n3",
        "name": "Từ vựng N3 Chuẩn",
        "version": "1.1.0",
        "fieldsAdded": ["Audio_Sentence"],
        "fieldsModified": []
      }
    ],
    "templatesSynchronized": [
      {
        "id": "tmpl_vocab_card_front",
        "name": "Thẻ Từ vựng - Nhận diện",
        "fromVersion": "2.0.0",
        "toVersion": "2.1.0"
      }
    ]
  },
  "srsSafetyAttestation": "100% of study progress and review history preserved",
  "studyProgressIntegrity": {
    "cardsRetainedWithHistory": 1835,
    "retainedReviewEvents": 14280,
    "srsZeroLossVerified": true
  }
}
```

---

## 4. Conflict Resolution Algebra & Data Safety Invariants

### 4.1 Three-Way Merge Mathematical Algebra
When a consumer synchronizes an installed deck with upstream changes, every note property atom is reconciled using formal 3-way merge algebra (`app/services/release_core/__init__.py`):
- Let $B$ = Value at `base_release` (state when the consumer previously installed or updated).
- Let $U$ = Value at `upstream` (new author release state).
- Let $L$ = Value at `local` (learner's personal override state in `DeckCloneNoteFieldOverride`).

$$\text{MergeAction}(B, U, L) = \begin{cases}
\text{CLEAR} \implies U & \text{if } L = U \lor L = B \quad \text{(No local edit, or local reached same target)} \\
\text{KEEP} \implies L & \text{if } U = B \land L \neq B \quad \text{(Author did not modify; retain learner's custom note)} \\
\text{CONFLICT} & \text{if } L \neq B \land U \neq B \land L \neq U \quad \text{(Both sides made divergent modifications)}
\end{cases}$$

---

### 4.2 Conflict Resolution Modes (`keep_mine`, `keep_upstream`, `manual`)
When $\text{MergeAction} = \text{CONFLICT}$, automatic rebase pauses for that field, and the learner chooses one of three deterministic resolution pathways:
1. **`keep_mine`**:
   - The learner's custom override $L$ is retained.
   - The base snapshot pointer in the conflict record is updated to $U$ ($B \leftarrow U$).
   - The learner is not prompted again until $U$ changes in a subsequent release.
2. **`keep_upstream`**:
   - The learner's override is deleted from `DeckCloneNoteFieldOverride`.
   - The card dynamically projects the author's upstream value $U$.
3. **`manual`**:
   - The learner enters a custom reconciled value $M$.
   - If $M = U$, the override is cleared; otherwise, $M$ is saved as the new override with base $B \leftarrow U$.

---

### 4.3 Native Array JSON Preservation & Bracket-Shielding Rules
Flama strictly enforces native JSON lists for array-type fields (e.g. synonyms, definitions, grammar points). Anki newline concatenation (`\n`) or delimiter degeneration (`$`) is prohibited.

#### Bracket-Shielding Algorithm:
During normalization or import, commas inside parentheses or grammatical annotations must **never** be split:
```python
# Pure Function: app/services/release_core/array_bracket_shield.py
import re

def parse_bracket_shielded_array(raw_text: str) -> list[str]:
    """
    Splits text by commas only when the comma is outside parentheses.
    Preserves annotations like '(noun, verb)' as a single unit.
    """
    if not raw_text or not raw_text.strip():
        return []
    
    # Match commas not enclosed within balanced parentheses
    pattern = r',\s*(?![^()]*\))'
    parts = re.split(pattern, raw_text.strip())
    
    # Strip whitespace and omit empty elements
    return [p.strip() for p in parts if p.strip()]
```

#### Array Scalar Immunity Invariant:
Fields categorized as phonetic or scalar identity (`reading`, `Phiên âm`, `Âm Hán Tự`, `hanviet`) are immune to array conversion and are guaranteed to remain scalar text (`str`).

---

### 4.4 Non-Destructive Tombstoning & Schema Evolution Invariants

#### Invariant 1: Non-Destructive Field Deletion
- When an author removes a field (`FieldDef`) in Note Type v2.0:
  1. The field definition is omitted from `NoteTypeRelease.manifest_json["fields"]`.
  2. In the database, existing `notes.field_values_by_id` retains the data for that field key.
  3. Learner overrides for that field are marked dormant but are **never deleted**.
  4. The template stops rendering `{{FieldName}}`. If the author or learner restores the field in a future version, all historical data reappears instantly without loss.

#### Invariant 2: Graceful Fallback on Added Mandatory Fields
- When an author introduces a new field with `required = True`:
  1. Authoring validation enforces a fallback default value (e.g. empty string `""` or placeholder).
  2. In learner notes, missing fields evaluate safely as empty in client-side Mustache rendering (`{{#NewField}}...{{/NewField}}` is cleanly skipped).
  3. The runtime emits an informational `TemplateBindingWarning(code='INPUT_UNBOUND')` rather than terminating with an execution error.

---

## 5. Frontend UI/UX Architecture & FSD Layout

### 5.1 Pragmatic Feature-Sliced Design (FSD) Slicing
In compliance with repository guardrails, all frontend components are organized strictly into the canonical FSD hierarchy:
$$\text{app} \longrightarrow \text{pages} \longrightarrow \text{widgets} \longrightarrow \text{features} \longrightarrow \text{entities} \longrightarrow \text{shared}$$

```
frontend/src/
├── entities/
│   ├── deck-version/                     # Domain models for deck releases, structural pins, DTOs
│   │   ├── api/deckVersionApi.ts         # Query & mutation functions
│   │   ├── model/types.ts                # TypeScript DTO interfaces
│   │   ├── model/queryKeys.ts            # TanStack Query key factories
│   │   └── index.ts                      # Public API
│   └── card-diff/                        # Domain models for diff items, groupings, cherry-pick
│       ├── model/types.ts
│       └── index.ts
├── features/
│   ├── deck-versioning/                  # Creator version management & structural overview
│   │   ├── ui/
│   │   │   ├── DeckStructuralDependenciesCard.tsx
│   │   │   ├── NoteTypeDependencyAlert.tsx
│   │   │   └── TemplatePinStatusBadge.tsx
│   │   ├── hooks/useDeckStructuralDependencies.ts
│   │   └── index.ts
│   ├── deck-review-merge/                # High-volume diff workspace (virtualized 1,000+ cards)
│   │   ├── ui/
│   │   │   ├── HighVolumeDiffWorkspace.tsx
│   │   │   ├── DiffGroupAccordion.tsx
│   │   │   ├── DiffRowVirtualized.tsx
│   │   │   ├── DiffBatchActionBar.tsx
│   │   │   └── DiffFilterToolbar.tsx
│   │   ├── hooks/
│   │   │   ├── useVirtualDiffList.ts     # In-flow windowed virtualization engine
│   │   │   └── useDiffSelection.ts       # Cherry-pick & Shift+Click range state machine
│   │   └── index.ts
│   ├── cascading-sync/                   # Consumer 1-click update & sync receipt
│   │   ├── ui/
│   │   │   ├── CascadingSyncButton.tsx
│   │   │   └── CascadingSyncSummaryModal.tsx
│   │   ├── hooks/useCascadingDeckUpdate.ts
│   │   └── index.ts
│   └── note-types/
│       └── components/TemplateCoherenceBanner.tsx
└── shared/
    └── ui/
        └── VirtualList/                  # Reusable virtual window container primitive
```

#### FSD Import Rules:
1. `entities/` may never import from `features/`, `pages/`, or `app/`.
2. Cross-feature imports are prohibited (e.g. `features/deck-versioning` cannot import from `features/deck-review-merge`). Shared concepts are housed in `entities/deck-version` or `entities/card-diff`.
3. External consumers access slices exclusively through public `index.ts` barrels.

---

### 5.2 Windowed Virtualization Engine (`useVirtualDiffList`)
To achieve high performance across thousands of cards without introducing heavy external dependencies, Flama adapts its proven in-house windowing hook (`useWindowedRows.ts`):

```typescript
// Location: frontend/src/features/deck-review-merge/hooks/useVirtualDiffList.ts
import { useState, useEffect, useCallback, type RefObject } from 'react'

export type VirtualRow = {
  index: number
  start: number
  size: number
}

export type VirtualDiffListOptions = {
  count: number
  containerRef: RefObject<HTMLElement | null>
  estimateHeight?: number
  overscan?: number
}

export function useVirtualDiffList({
  count,
  containerRef,
  estimateHeight = 68,
  overscan = 8,
}: VirtualDiffListOptions) {
  const [scrollTop, setScrollTop] = useState(0)
  const [viewportHeight, setViewportHeight] = useState(600)
  const [showAllForSearch, setShowAllForSearch] = useState(false)

  // Native in-page search bypass (Ctrl+F / Cmd+F / F3)
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'f') {
        setShowAllForSearch(true)
      } else if (e.key === 'F3') {
        setShowAllForSearch(true)
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [])

  // Throttled scroll listener
  useEffect(() => {
    const el = containerRef.current
    if (!el) return

    let rafId: number
    const onScroll = () => {
      cancelAnimationFrame(rafId)
      rafId = requestAnimationFrame(() => {
        setScrollTop(el.scrollTop)
        setViewportHeight(el.clientHeight)
      })
    }

    el.addEventListener('scroll', onScroll, { passive: true })
    setViewportHeight(el.clientHeight)
    return () => {
      el.removeEventListener('scroll', onScroll)
      cancelAnimationFrame(rafId)
    }
  }, [containerRef])

  const totalHeight = count * estimateHeight

  // Compute visible rows
  const virtualRows: VirtualRow[] = []
  if (showAllForSearch) {
    for (let i = 0; i < count; i++) {
      virtualRows.push({ index: i, start: i * estimateHeight, size: estimateHeight })
    }
  } else {
    const startIndex = Math.max(0, Math.floor(scrollTop / estimateHeight) - overscan)
    const endIndex = Math.min(count - 1, Math.ceil((scrollTop + viewportHeight) / estimateHeight) + overscan)

    for (let i = startIndex; i <= endIndex; i++) {
      virtualRows.push({
        index: i,
        start: i * estimateHeight,
        size: estimateHeight,
      })
    }
  }

  return {
    virtualRows,
    totalHeight,
    isVirtualized: !showAllForSearch,
    resetSearchBypass: () => setShowAllForSearch(false),
  }
}
```

#### DOM Element Bound:
With `overscan = 8` and `estimateHeight = 68px`, a 600px viewport renders approximately $10 + 16 = 26$ visible items. Even on 4K monitors, total rendered rows never exceed **60 to 90 DOM nodes**, satisfying the requirement of remaining strictly below 150 nodes.

---

### 5.3 Ergonomic High-Volume Review Workspace Design

```
+----------------------------------------------------------------------------------------------------+
|                                HIGH-VOLUME CHANGE REVIEW WORKSPACE                                 |
+----------------------------------------------------------------------------------------------------+
|                                                                                                    |
|  [Search: "じゅんび"    ] [Filter: All (1,250) v] [Group: By Note Type v]   [Chọn tất cả (1,250)]  |
|                                                                                                    |
|  ▼ [v] Note Type: Từ vựng N3 Chuẩn (1,150 mục)         [Chấp nhận cả nhóm] [Từ chối cả nhóm]       |
|  ┌──────────────────────────────────────────────────────────────────────────────────────────────┐  |
|  │ [x] 準備 (じゅんび) · Example_VI          [Modified]               [Xem chi tiết thay đổi]   │  |
|  │     - Tôi đang chuẩn bị.                                                                     │  |
|  │     + Tôi đang chuẩn bị cho kỳ thi tiếng Nhật JLPT N3.                                       │  |
|  ├──────────────────────────────────────────────────────────────────────────────────────────────┤  |
|  │ [x] 卒業 (そつぎょう) · Meaning_VI        [Modified]               [Xem chi tiết thay đổi]   │  |
|  ├──────────────────────────────────────────────────────────────────────────────────────────────┤  |
|  │ [ ] 合格 (ごうかく) · 6 fields            [Added]                  [Xem chi tiết thay đổi]   │  |
|  └──────────────────────────────────────────────────────────────────────────────────────────────┘  |
|                                                                                                    |
|  ▶ [>] Note Type: Kanji N3 (100 mục)                   [Chấp nhận cả nhóm] [Từ chối cả nhóm]       |
|                                                                                                    |
|  ================================================================================================  |
|  Sticky Batch Action Bar: Đã chọn 1,149 / 1,250 mục   [Chấp nhận đã chọn] [Từ chối đã chọn] [Hủy]  |
+----------------------------------------------------------------------------------------------------+
```

---

### 5.4 Zero Visual Regression & Design System Conformance
All new components adhere strictly to Flama's design tokens:
- **Typography**: Geist Sans font hierarchy with tight letter tracking (`tracking-tight`).
- **Color Palette**: OKLCH warm light/dark values with matching semantic badges:
  - Added: `text-emerald-700 bg-emerald-500/10 border-emerald-500/20`
  - Modified: `text-blue-700 bg-blue-500/10 border-blue-500/20`
  - Removed / Warning: `text-amber-700 bg-amber-500/10 border-amber-500/20`
  - Conflict: `text-red-700 bg-red-500/10 border-red-500/20`
- **Border Radii**: Strict usage of `rounded-xl` (12px) for cards and `rounded-2xl` (16px) for master containers.
- **Fluid Layout**: Fluid clamp containers (`max-w-6xl mx-auto px-4 sm:px-6 lg:px-8`).

---

## 6. 4-Tier Verification & Test Strategy

```
+----------------------------------------------------------------------------------------------------+
|                                     4-TIER TEST PYRAMID MATRIX                                     |
+----------------------------------------------------------------------------------------------------+
|                                                                                                    |
|      ▲                                                                                             |
|     / \     TIER 4: Cascading Sync Concurrency & SRS Permanence (MySQL 8.0 Locks, Zero Loss)       |
|    /---\                                                                                           |
|   /     \   TIER 3: Scalability Stress & DOM Virtualization (50,000 Cards, Keyset SQL, <150 DOM)   |
|  /-------\                                                                                         |
| /         \ TIER 2: MySQL 8.0 Transactions & DTO Contracts (Integration, Alembic, Idempotency)    |
|/-----------\                                                                                       |
|   TIER 1    TIER 1: Unit Merge Algebra, Bracket Shielding & SemVer Progression (Pure Isolated)    |
+----------------------------------------------------------------------------------------------------+
```

### 6.1 Tier 1: Unit & Merge Algebra Verification
- **Target**: Pure Python unit tests and Vitest suites. Execution time $< 100\text{ms}$.
- **Test Matrix**:
  1. `test_three_way_merge_algebra_all_permutations`: Evaluates all 8 permutations of $(B, U, L)$. Verifies that `CLEAR`, `KEEP`, and `CONFLICT` match mathematical specifications.
  2. `test_semver_monotonic_progression`: Validates automated version bump logic (`1.0.0` $\to$ `1.0.1`, `1.2.0` $\to$ `2.0.0`) and duplicate prevention.
  3. `test_bracket_shielding_regex`: Verifies that `parse_bracket_shielded_array("học, tập (noun, verb), thi")` yields exactly three elements, shielding the comma inside parentheses.
  4. `test_ast_unclosed_tag_rejection`: Card template validator detects unclosed `<div>`, `<span>`, or unmatched Mustache `{{#tag}}` blocks and rejects publication.

---

### 6.2 Tier 2: MySQL 8.0 Transactional & Constraint Integration
- **Target**: Executed against local MySQL 8.0 InnoDB instances (`python scripts/run_tests.py --module flashcards,marketplace --jobs 1`).
- **Test Matrix**:
  1. `test_publication_overview_dto_integrity`: Calls `GET /api/marketplace/decks/<id>/structural-dependencies` and verifies that card counts match live notes while accurately returning Note Type and Template release pins.
  2. `test_scoped_publish_content_only_leaves_templates_frozen`: Asserts that publishing with `scope='content_only'` captures current pins without pulling uncommitted template drafts into the release.
  3. `test_immutable_release_database_protection`: Proves that running `UPDATE` or `DELETE` on a `DeckRelease` or `NoteTypeRelease` raises an `ImmutableReleaseViolation`.
  4. `test_idempotency_key_replay_behavior`: Sending duplicate POST requests with identical `Idempotency-Key` headers returns HTTP 200 with an identical payload and does not create duplicate rows.

---

### 6.3 Tier 3: Scalability Stress & DOM Node Virtualization Benchmarks
- **Target**: Synthetic high-volume datasets (1,000 to 50,000 cards) under Playwright and pytest benchmarks.
- **Test Matrix**:
  1. `test_keyset_pagination_latency_50k_cards`: Measures SQL execution for a 50,000-change deck. Asserts that keyset pagination queries run in $O(1)$ constant time with $p95 < 350\text{ms}$.
  2. `test_virtual_diff_list_dom_node_count_under_stress`: Mounts a 10,000-item diff list in the React test harness. Asserts that rendered DOM element count remains $< 150$ regardless of scroll position.
  3. `test_batch_action_atomic_execution`: Executes `batch_approve` on 2,500 cards in a single request. Verifies that execution completes in $< 1.2\text{s}$ using set-based SQL.
  4. `test_response_envelope_payload_cap`: Validates that a 100-item diff page payload never exceeds $1\text{MB}$.

---

### 6.4 Tier 4: Concurrent Cascading Sync Race Condition Verification
- **Target**: Multi-threaded concurrent execution against MySQL 8.0 with InnoDB row-level locking.
- **Test Matrix**:
  1. `test_1click_cascading_sync_atomic_commit`: Executes `/updates/<id>/apply`. Asserts that `DeckInstall.applied_release_id`, `NoteTypeInstall.applied_release_id`, and `TemplateSubscription.applied_release_id` advance simultaneously.
  2. `test_concurrent_publish_row_locking`: Fires two simultaneous publish requests against the same deck. Verifies that `SELECT ... FOR UPDATE` serializes requests: one succeeds and the other receives HTTP 409 `RELEASE_HEAD_STALE`.
  3. `test_srs_study_progress_permanence`: Conducts reviews on 200 cards to generate active `CardProgress` and `ReviewEvent` rows. Executes a cascading structural deck update. Formally proves that:
     $$\Delta(\text{CardProgress.due\_day}) = 0 \quad \text{and} \quad \Delta(\text{CardProgress.reps}) = 0$$
  4. `test_cloner_overlay_three_way_rebase`: Confirms that learner field overrides are cleanly preserved while unconflicted upstream changes are seamlessly integrated.

---

## 7. Database Migration & Schema Evolution Plan

### 7.1 Proposed Schema Extension (`deck_release_note_type_pins`)
To resolve the structural gap where `DeckRelease` previously lacked explicit `NoteTypeRelease` pins, a dedicated relational junction table is introduced:

```sql
-- Table: deck_release_note_type_pins
CREATE TABLE `deck_release_note_type_pins` (
    `id` VARCHAR(36) NOT NULL,
    `deck_release_id` VARCHAR(36) NOT NULL,
    `source_note_type_id` VARCHAR(36) NOT NULL,
    `note_type_release_id` VARCHAR(36) NOT NULL,
    `schema_manifest_hash` VARCHAR(64) NOT NULL,
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    UNIQUE KEY `uq_deck_release_note_type` (`deck_release_id`, `source_note_type_id`),
    KEY `idx_pins_note_type_release` (`note_type_release_id`),
    CONSTRAINT `fk_pins_deck_release` FOREIGN KEY (`deck_release_id`) 
        REFERENCES `deck_releases` (`id`) ON DELETE CASCADE,
    CONSTRAINT `fk_pins_note_type` FOREIGN KEY (`source_note_type_id`) 
        REFERENCES `note_types` (`id`) ON DELETE CASCADE,
    CONSTRAINT `fk_pins_note_type_release` FOREIGN KEY (`note_type_release_id`) 
        REFERENCES `note_type_releases` (`id`) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
```

---

### 7.2 Alembic Migration Blueprint

```python
"""Add deck_release_note_type_pins table

Revision ID: rev_deck_release_nt_pins_20261026
Revises: rev_previous_head
Create Date: 2026-10-26 11:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = 'rev_deck_release_nt_pins_20261026'
down_revision = 'rev_previous_head'
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        'deck_release_note_type_pins',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('deck_release_id', sa.String(length=36), nullable=False),
        sa.Column('source_note_type_id', sa.String(length=36), nullable=False),
        sa.Column('note_type_release_id', sa.String(length=36), nullable=False),
        sa.Column('schema_manifest_hash', sa.String(length=64), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('deck_release_id', 'source_note_type_id', name='uq_deck_release_note_type')
    )
    op.create_index('idx_pins_note_type_release', 'deck_release_note_type_pins', ['note_type_release_id'])
    op.create_foreign_key(
        'fk_pins_deck_release', 'deck_release_note_type_pins', 'deck_releases',
        ['deck_release_id'], ['id'], ondelete='CASCADE'
    )
    op.create_foreign_key(
        'fk_pins_note_type', 'deck_release_note_type_pins', 'note_types',
        ['source_note_type_id'], ['id'], ondelete='CASCADE'
    )
    op.create_foreign_key(
        'fk_pins_note_type_release', 'deck_release_note_type_pins', 'note_type_releases',
        ['note_type_release_id'], ['id'], ondelete='RESTRICT'
    )

def downgrade():
    op.drop_table('deck_release_note_type_pins')
```

---

## 8. Production Implementation Matrix & Quality Gates

| Milestone | Subsystem & Task | Deliverable Artifacts | Acceptance Gate |
|---|---|---|---|
| **M1** | **Master Architecture & Contracts** | `docs/architecture/HIERARCHICAL_VERSIONING_AND_MERGE_ARCHITECTURE.md` | Complete coverage of R1–R5, formal merge algebra, FSD blueprints, and 4-tier test strategy. |
| **M2** | **High-Volume Virtualized Merge UI (R3)** | `features/deck-review-merge/`, `useVirtualDiffList.ts`, `HighVolumeDiffWorkspace.tsx` | Smooth scrolling for 1,000+ cards with $< 150$ DOM nodes; batch approve/reject bar fully operational. |
| **M3** | **Deck Versioning & 1-Click Sync (R1, R2, R4)** | `features/deck-versioning/`, `features/cascading-sync/`, `TemplateCoherenceBanner.tsx` | Deck screen displays clean structural pins without raw diffs; 1-click update cascades across Deck, Note Type, and Template. |
| **M4** | **Dual-Track Verification & Integrity Audit** | Comprehensive unit, integration, stress, and race tests | 100% test pass on MySQL 8.0 local database; independent victory audit approved. |

---

## Appendix: Glossary & Cross-Reference Mapping

| Term | Architectural Definition | Primary Code Location |
|---|---|---|
| **ADR P11** | Derived Virtual Card Presentation: $\text{Card} = \text{Note} \times \text{StudyApplication}$. Physical card table eliminated. | `models/card.py:165-189` |
| **Logical Overlay** | Non-destructive cloner model storing personal edits in `DeckCloneNoteFieldOverride` without mutating source author notes. | `models/deck_install.py`, `models/deck_clone_*.py` |
| **StudyProgressSubject** | True authority for SM-2/FSRS spaced repetition progress, keyed by `(user_id, logical_note_key)`. | `models/study_progress_subject.py` |
| **3-Way Merge** | Reconciliation algorithm comparing Base ($B$), Upstream ($U$), and Local ($L$) property states. | `app/services/release_core/__init__.py` |
| **In-Flow Windowing** | Virtualization rendering only visible items + overscan rows while maintaining native window scrollbars. | `features/deck-review-merge/hooks/useVirtualDiffList.ts` |
| **Pragmatic FSD** | Feature-Sliced Design enforcing strict layer boundaries: `app -> pages -> widgets -> features -> entities -> shared`. | `frontend/src/` |

---
*End of Master Architecture Specification.*
