---
name: flama-database-architecture
description: Review, investigate, analyze, and safely evolve the Flama MySQL database schema and data architecture. Use when evaluating entity boundaries, Field/Note/Template/Card modeling, scheduler and review persistence, marketplace release and clone overlay models, Flama Connect sync provenance, database migrations, or proposing safe schema refactors.
---

# Flama Database Architecture

## Mission

Investigate, analyze, and safely evolve Flama's database schema and data architecture. Flama is an OLTP language-learning platform using MySQL and SQLAlchemy. Its architecture spans note authoring, customizable card templating, spaced-repetition scheduling, distributed marketplace cloning/overlay synchronization, and external sync bridges (Flama Connect, AnkiConnect, Yomitan, MCP).

This skill enforces strict, evidence-grounded data-centric discipline: **follow the data, not the code structure.** Distinguish observed architecture from proposed redesigns, identify systems of record, trace end-to-end lifecycles, record uncertainties explicitly, and plan zero-data-loss migrations.

---

## Two Distinct Modes of Operation

You must determine whether the task is in **INVESTIGATE** mode or **DESIGN** mode. The two modes must remain strictly separated.

```
+-----------------------------------------------------------------------------------+
| INVESTIGATE Mode (Default)                                                        |
| Triggers: "investigate", "review", "audit", "trace", "explain", "analyze", "check" |
| Output: Observed schema, evidence, systems of record, concerns, unknowns.         |
| PROHIBITED: Proposing final schemas, refactoring code, altering migrations.        |
+-----------------------------------------------------------------------------------+
                                         |
                       (Explicit User Request to Redesign)
                                         v
+-----------------------------------------------------------------------------------+
| DESIGN Mode (Only on Explicit Request)                                            |
| Triggers: "design", "refactor", "propose schema", "evolve model", "migrate table" |
| Output: Invariants, target schema, alternatives, MySQL trade-offs, migration plan.|
| REQUIRED: Grounded in completed investigation, zero data loss, compatibility.    |
+-----------------------------------------------------------------------------------+
```

### 1. INVESTIGATE Mode (Default)
Use when the prompt asks to investigate, understand, trace, audit, review, or explain the current database architecture.
- **Inspect** real repository artifacts (migrations, ORM models, constraints, repository/service writes and reads).
- **Reconstruct** the schema as it actually exists, including implicit couplings and data in motion.
- **Identify** authoritative systems of record vs snapshots, caches, or derived data.
- **Record** architectural findings using the standard finding format (Observed, Evidence, Potential concern, Impact, Unknowns).
- **Record** unknowns and assumptions under *Open Questions / Needs Verification* rather than inventing behavior.
- **NEVER** modify application code, alter migrations, invent unverified foreign keys, propose target redesigns, or declare an architecture "wrong" without concrete evidence.

### 2. DESIGN Mode (Explicit Request Only)
Use ONLY when explicitly instructed to design, improve, refactor, evolve, or propose a new schema or database architecture.
- **Prerequisite**: Must start from a completed, evidence-grounded investigation of the current state.
- **Define Invariants First**: State domain invariants and boundaries before writing table DDL.
- **Compare Alternatives**: Evaluate at least 2 viable modeling approaches against MySQL OLTP semantics.
- **Explain Trade-offs**: Address normalization vs JSON, row growth, read/write amplification, locking, and SQLAlchemy/Alembic ergonomics.
- **Produce Staged Migration Strategy**: Break changes into backward-compatible, zero-downtime phases (Expand -> Backfill -> Cutover -> Contract).
- **Preserve Compatibility**: Maintain support for existing clone overlays, scheduler replays, and sync streams without data loss.

---

## Evidence Hierarchy & Grounding Rules

When determining facts about the database, prioritize evidence in this strict order:

```
1. Database Migrations (migrations/versions/*.py)         [Highest schema truth]
2. Database Models (models/*.py)                          [Declared ORM mapping]
3. Table Constraints & Keys (__table_args__, PK, FK, UQ)  [Enforced relational rules]
4. Repository/Service Writes (db.session.add/commit)      [Authoritative mutators]
5. Repository/Service Reads (queries, joined loads)       [Access patterns & consumers]
6. API Handlers & Validators (app/api/*, app/validators/*)[Input/output contracts]
7. Test Assertions (tests/test_*.py)                      [Verified runtime expectations]
8. Import/Export & External Sync (Connect, Yomitan, Anki) [Cross-boundary mappings]
9. Background Maintenance & CLI (app/startup.py, cli.py)  [Repairs, seeds, cutovers]
10. Frontend Client State (frontend/src/*)                [Rendering & study consumption]
11. Documentation (docs/*, AGENTS.md, docstrings)         [Intent; verify against code]
```

### Critical Grounding Rules
- **No Fabricated Relations**: Never assume a foreign key or unique constraint exists unless found in `models/` or `migrations/`. Note when relationships are maintained only in application logic.
- **Documentation Discrepancies**: If documentation conflicts with ORM code or migrations, document the conflict explicitly. The implementation is the runtime truth.
- **Unverified Production State**: Clearly label data distributions, row counts, and deployment-specific flags as *Needs Verification*.

---

## Schema Review Order (The 10-Step Lens)

When reviewing any Flama subsystem, always evaluate architectural decisions in this priority sequence:

```
1. Entity Identity    -> How is the entity uniquely identified (UUID vs Integer vs Name vs External Key)?
2. Ownership          -> Who owns this row (User, Deck, NoteType, Session)? What are the cascade rules?
3. Relationships      -> What are the exact cardinalities (1:1, 1:N, N:M)? Are FKs explicit or implicit?
4. Source of Truth    -> Is this table authoritative, a snapshot, an overlay delta, or a derived cache?
5. Invariants         -> What integrity rules must always hold? Are they database-enforced or app-enforced?
6. Lifecycle          -> How is the row created, updated, versioned, synchronized, soft/hard deleted, or purged?
7. Extensibility      -> Can new types/algorithms/interactions be added without DDL churn or table bloat?
8. Compatibility      -> How does this interact with clone overlays, legacy snapshots, and external sync?
9. Migration Safety   -> Can this schema evolve without data loss, lock contention, or downtime?
10. Indexing & Access -> What are the composite index needs for hot query paths? (Address only when impactful)
```

> [!IMPORTANT]
> **Priority Rule**: Focus on steps 1–9. Do not get sidetracked by micro-optimizations, query tuning, or buffer pool settings unless they directly dictate an architectural decision.

---

## High-Priority Flama Architectural Areas

### 1. Field Architecture (`field_defs`, `notes.field_values`, Overrides)
- **Identity Tension**: `FieldDef.id` (UUID) is the stable schema ID; `FieldDef.name` (String) is the runtime key in `Note.field_values` JSON.
- **Rename Mechanics**: Synchronous `FieldRenameJob` rewrites JSON keys across all notes. Check if template placeholders `{{Field}}`, `MediaAsset.field_name`, clone overrides, and import mappings survive renames.
- **Values & Typing**: `Note.field_values` stores a JSON dict. Evaluate typed storage, dynamic values, rich text, audio scan references, and custom interactions (MCQ, matching, typing).
- **Clone Overrides**: `DeckCloneNoteFieldOverride` uses dual identity (`source_field_def_id` and `field_name`) with dual unique constraints.
- *Detailed reference*: Inspect `references/architectural_checklists.md#1-field-architecture-audit--evolution-checklist`.

### 2. NoteType / Note / Template / Card Layering
- **Responsibility Boundaries**:
  - `NoteType`: Schema container (FieldDefs, Templates) + Marketplace metadata.
  - `Note`: Content instance `(user_id, note_type_id, deck_id, field_values, tags)`.
  - `Template`: Presentation rules (`front_html`, `back_html`, `shared_css`, display order).
  - `Card`: Generated projection `(note_id, template_id)` with `uq_cards_note_template`.
- **Leakage Traps**: Check if interaction-specific structure leaks into generic notes, or if rendering logic pollutes stored content.
- **Custom Interactions**: Support flashcards, multiple choice, matching, listening, typing, and future drill types without creating hardcoded domain tables.
- *Detailed reference*: Inspect `references/architectural_checklists.md#2-notetype--note--template--card-layer-separation-checklist`.

### 3. Scheduler & Spaced-Repetition Architecture
- **State Separation**:
  - `CardProgress`: Mutable learning state (`queue`, `due_at`, `due_day`, `interval_days`, `interval_days_raw`, `ease_factor`, `memory_stability`, `memory_difficulty`, `revision`).
  - `SchedulerPreset`: Config presets (`learning_steps_json`, `relearning_steps_json`, `fsrs_parameters_json`, modifiers, leech settings).
  - `ReviewEvent`: Immutable audit/analytics fact. Contains before/after transition deltas (`payload_json`, `ConnectReviewEventRef`). Has NO foreign keys to `deck_id` or `note_type_id` to allow safe entity purging.
  - `StudySession`: Batch study execution, frozen config snapshots (`scheduler_config_hash`), client replaying, and optimistic locking (`CardProgress.revision`).
- **Multi-Algorithm Extensibility**: Evaluate support for Legacy Anki (SM-2), FSRS v4/v5, and custom Flama algorithms without polluting generic progress tables.
- *Detailed reference*: Inspect `references/architectural_checklists.md#3-scheduler-state--multi-algorithm-extensibility-checklist`.

### 4. Marketplace, Releases & Clone Overlay Architecture
- **Overlay Model**: Flama uses a **pointer/overlay clone model** (`DeckInstall`, `clone_mode="logical_overlay"`). Installing a deck copies the deck tree and NoteType, but does NOT copy source Notes or Cards.
- **Delta Layers**:
  - Schema deltas: `DeckCloneFieldDefOverride`, `DeckCloneAddedFieldDef`, `DeckCloneFieldOrderOverride`.
  - Content deltas: `DeckCloneNoteFieldOverride`, `DeckCloneAddedNote`.
- **Rebase & Change Requests**:
  - Upstream updates: `DeckInstallRebase` executes a 3-way merge `(base_release, target_release, local_overlay)` with conflict resolution (`keep_mine`, `keep_upstream`, `manual`).
  - Contributions: `DeckChangeRequest` computes overlay fingerprints and merges approved learner changes back into the source repository.
- *Detailed reference*: Inspect `references/architectural_checklists.md#4-marketplace--release--clone-overlay-integrity-checklist`.

### 5. Flama Connect & External Sync Provenance
- **External Identity Bridges**: `ConnectSourceDeckRef`, `ConnectSourceNoteRef`, `ConnectSourceCardRef`, `ConnectSourceNoteTypeRef`, `ConnectReviewEventRef`.
- **Media Staging**: `ConnectPendingMedia` (Yomitan MP3 staging) and `ConnectImportMedia` (Anki package media staging).
- **Idempotency**: All sync streams use content hashes (`content_hash`) and external IDs to guarantee idempotent bidirectional imports.
- *Detailed reference*: Inspect `references/architectural_checklists.md#5-flama-connect--external-sync-provenance-checklist`.

---

## Architectural Review Findings Format

Every finding recorded during investigation or design must follow this structured schema:

```markdown
### [Finding Title: e.g., Dual Identity in Clone Note Overrides]

- **Observed**: [Concrete behavior observed in the codebase]
- **Evidence**: [Exact file paths, model classes, migration names, line numbers, or test names]
- **Potential concern**: [Architectural tension, risk of drift, coupling, or boundary violation]
- **Impact**: [What happens when this breaks: data loss, stale cache, sync conflict, migration blocker]
- **Unknowns**: [What cannot be confirmed from the repo: production data distribution, traffic patterns, etc.]

<!-- ONLY INCLUDE BELOW IN DESIGN MODE -->
- **Alternatives Considered**:
  1. [Option A: e.g., Migrate Note.field_values to UUID keys]
  2. [Option B: e.g., Relational field_values EAV table]
- **Trade-offs**: [MySQL storage, JSON search capability, migration complexity, locking impact]
- **Recommendation**: [Clear architectural choice with justification]
- **Migration Implications**: [Zero-downtime transition plan with backward-compatibility gates]
```

---

## MySQL OLTP Decision Framework

When evaluating schema designs in Flama, reason using explicit MySQL and SQLAlchemy mechanics:

| Decision Area | Trade-off / Considerations | Flama Rule of Thumb |
|---|---|---|
| **JSON vs Normalized Columns** | JSON allows dynamic schemas and fast full-note loads; normalized tables allow relational integrity, FK cascades, and indexed filtering. | Use JSON for unstructured note values if field count is dynamic, but ensure stable FieldDef IDs drive renames and schema diffs. |
| **Foreign Keys vs Application Integrity** | Database FKs guarantee relational integrity and cascade deletes; detached IDs allow immutable audit logging and cross-boundary purging. | Core content (Deck, Note, Card) MUST use strict DB FKs. Long-lived analytics (ReviewEvent) deliberately omit FKs to survive deck/card deletion. |
| **Concurrency & Optimistic Locking** | Pessimistic `SELECT FOR UPDATE` locks rows; optimistic `revision` counters avoid lock contention in distributed study sessions. | Study commits and clone rebases MUST use optimistic locking (`CardProgress.revision`, `DeckInstall.overlay_revision`). |
| **Identity Types (UUID vs Integer)** | UUID (String(36)) enables decentralized ID generation (Connect, client sync, offline creation); Auto-increment Integer offers smaller B-Tree footprint. | Use UUID for distributed entities (Note, Card, FieldDef, Media, Install, Release); use Integer for local sequential sequences (Deck, User, Progress, Preset). |
| **Transaction Boundaries** | Long transactions hold locks and increase deadlock risk; fine-grained commits risk partial state on error. | Service operations (create note + cards + dirty flag) MUST commit atomically in one unit of work. Background jobs must batch in small transaction chunks. |

---

## Standard Output Artifacts

Write findings directly into repository documentation under `docs/architecture/`. Never leave comprehensive architecture analysis solely in the agent chat.

- **Investigation Output**: `docs/architecture/database-architecture-investigation.md` (or specific domain files like `docs/architecture/field-architecture-investigation.md`).
- **Design Output**: `docs/architecture/database-architecture-design.md` (or `docs/architecture/field-architecture-design.md`).

### Document Skeleton for Architecture Reports

```markdown
# <Topic / Subsystem> - Database Architecture <Investigation | Design>

> Date: <YYYY-MM-DD> | Mode: <INVESTIGATE | DESIGN> | Engine: MySQL 8.0 (OLTP)
> Primary Repositories: models/, app/services/, app/repositories/, migrations/

## 1. Executive Summary & Landscape Map
- Core domain responsibility and system classification.
- Mermaid Entity-Relationship or Dataflow diagram.

## 2. Systems of Record & Ownership Inventory
| Entity / Table | Authoritative Store | Written By | Read By | Ownership / Cascade |
|---|---|---|---|---|

## 3. End-to-End Lineage & Dataflow Traces
- Detailed sequence diagram of key operations (e.g., Note Creation -> Card Generation -> Study Session -> Commit -> ReviewEvent).

## 4. Architectural Findings & Tension Points
- Structured findings using the Observed / Evidence / Concern / Impact / Unknowns format.

## 5. MySQL OLTP Physical Evaluation
- Key constraints, indexes, JSON column evaluation, transaction boundaries, and concurrency controls.

## 6. Open Questions & External Assumptions
- Everything that requires verification against production environments.

<!-- SECTIONS 7-9 ONLY IN DESIGN MODE -->
## 7. Invariants & Target Architecture
- Domain invariants, proposed ERD, normalized entity definitions.

## 8. Evaluated Alternatives & Trade-offs Matrix
- Comparison of alternative designs against MySQL performance, developer ergonomics, and migration safety.

## 9. Zero-Downtime Migration & Cutover Strategy
- Phased rollout plan (Expand -> Backfill -> Dual-write/Read -> Cutover -> Contract).
```

---

## Quality Checklist Before Completing an Architecture Task

- [ ] **Mode Compliance**: If the prompt was an investigation, did you strictly avoid proposing a final redesign or altering code?
- [ ] **Evidence Grounding**: Is every table, column, constraint, and dataflow linked to exact files in `models/`, `migrations/`, `app/services/`, or `tests/`?
- [ ] **System of Record Identified**: Is the authoritative source of truth identified for every piece of state, distinguishing derived/cached/snapshot data?
- [ ] **Tensions Explored**: Were dual identities (name vs ID), clone overlay boundaries, and scheduler generic/specific state investigated?
- [ ] **MySQL OLTP Reasoning**: Are conclusions evaluated against MySQL transactional, locking, and JSON semantics?
- [ ] **Mermaid Diagram Validity**: Are all Mermaid blocks (`erDiagram`, `flowchart LR`, `sequenceDiagram`) valid syntax with properly quoted identifiers?
- [ ] **Uncertainty Captured**: Are unverified production assumptions placed in *Open Questions / Needs Verification* rather than assumed as fact?
- [ ] **Design Migration Safety**: If in DESIGN mode, is there an incremental, zero-data-loss migration strategy with backward-compatibility gates?
