# Applied Composition and Binding Contract

> Status: Accepted; Phase 3 compatibility projection implemented
>
> Decision date: 2026-09-09
>
> Scope: logical identity and lifecycle contract; physical reusable-definition schema deferred

## Decision summary

An applied composition is the immutable effective choice that connects a presentation definition/version, a NoteType-scoped application occurrence, concrete input bindings, the built-in Interaction/Trigger contract, and an exact Algorithm version. It is not synonymous with a current `Template` row, a `Card`, a NoteType, or progress.

Phase 3 implements this contract as a compatibility projection over existing Template/Card/FieldDef rows and freezes the projection in existing StudySession JSON. It does not add models, foreign keys, migrations, duplicate Cards, or another progress store.

## Responsibility boundaries

| Concept | Current Phase 3 authority | Future responsibility |
|---|---|---|
| Note content/schema | `Note`, `NoteType`, `FieldDef` | Remains Note/NoteType-owned. |
| Presentation executable | Versioned Template artifact built from `Template` | Immutable reusable definition version. |
| Application occurrence | One compatibility application per effective Template/context | Distinct stable occurrence ID, including repeated application of one definition to one NoteType. |
| Input binding | Direct binding to the Template NoteType's stable `FieldDef.id` | Validated application-owned mapping from abstract inputs to compatible FieldDefs. |
| Queue item | Existing `Card` | References an application without redefining learner progress. |
| Learner progress/history | `CardProgress` and `ReviewEvent` | Remains the sole progress/history authority through this phase. |
| Installed context | `DeckInstall` logical overlay plus source/local scope maps | Pins a definition version; local edit forks copy-on-write. |

## Identity contract

The logical target model has separate identities for definition, immutable definition version, abstract input, application occurrence, and binding. Reapplying one definition twice to the same NoteType must create two application occurrence identities even when definition version and bindings happen to match. It must not manufacture duplicate progress merely to express the occurrence.

The current compatibility projection is:

```text
definition_id = legacy-template:{template_id}
owned application/composition_id = comp:notetype:{note_type_id}:template:{template_id}
installed source = comp:install:{install_id}:source:notetype:{note_type_id}:template:{template_id}
installed local  = comp:install:{install_id}:local:notetype:{note_type_id}:template:{template_id}
application_id = composition_id
```

`application_id = composition_id` is a Phase 3 compatibility fact, not the future repeated-application storage design. A future physical design must introduce occurrence identity explicitly and preserve these compatibility IDs for old Cards/sessions.

## Binding contract

Phase 3 compiles each current Template application into `study-composition-binding.v1`:

- `composition_id` and `application_id` identify the effective occurrence;
- `definition_id` and Template artifact `definition_version` pin the presentation executable;
- `binding_kind` is `legacy-fielddef-direct`;
- every binding has a logical input ID and stable `field_def_id` plus field name/type/required metadata;
- `binding_fingerprint` is the canonical SHA-256 digest of the binding material before the fingerprint field is added.

Field names remain authoring labels and legacy template syntax; they are not binding identity. The future compiler must fail closed on a missing/deleted FieldDef, wrong NoteType, duplicate required binding, incompatible type, or unresolved legacy name. Optional unbound inputs may only be accepted when the definition declares them optional. Phase 3 does not invent transformations or cross-NoteType field coercion.

| Binding condition | Required result |
|---|---|
| Required input has no binding | Reject application as incomplete. |
| Binding points to a deleted/missing FieldDef | Reject as stale; never fall back by name. |
| FieldDef belongs to another NoteType | Reject as out of application scope. |
| One single-cardinality input has multiple bindings | Reject as ambiguous. |
| Field type is incompatible | Reject unless a separately versioned transformation contract exists. |
| Legacy field name cannot resolve uniquely to one FieldDef ID | Reject compile/import and require repair. |
| Optional input is unbound | Accept only when the pinned definition version declares it optional. |

## Session freeze contract

New sessions freeze the following in both the self-contained snapshot and the versioned `study-session-config.v2` stored in the existing `config_snapshot_json` column:

- `composition_contract_version = applied-composition.compat.v1`;
- `selected_composition_id` and full `selected_composition`;
- selection resolution source;
- `study-composition-binding.v1` material and fingerprint;
- existing Template/content artifacts;
- per-card composition reference;
- existing Interaction, Trigger, Algorithm, policy/config and queue contract versions.

All selected Cards must resolve to the same frozen composition and binding. Commit/batch payloads may repeat `composition_id`; if present, it must equal the frozen value. Restore quarantines partial or contradictory new composition material with `COMPOSITION_CONTRACT_MISMATCH`. Supported legacy v2/v3 sessions without any Phase 3 composition fields remain readable and are not rewritten into a fabricated application.

An active lease executes frozen artifacts and does not rediscover a newer live definition. A live Template edit, delete, or unpublish may affect later discovery but cannot silently switch an existing lease. Missing or contradictory frozen executable material fails closed.

## Lifecycle rules

- Create/apply: validate input cardinality and FieldDef identity before making an application discoverable.
- Pin/install: an installed application remains tied to its selected release/definition version.
- Edit installed content: create or use a private local fork; never mutate the source definition/Note/Card.
- Reapply: create a new application occurrence, not new learner progress.
- Unpublish/detach/delete: stop new discovery as appropriate while preserving active/historical snapshot meaning and progress/history.
- Import/Connect: preserve current Template/Card IDs and ordinals through the compatibility projection; do not regenerate Cards in Phase 3.

## Alternatives rejected

1. Treat `Template` as the permanent reusable definition and application simultaneously. This cannot represent repeated application with different bindings and leaks current mutable NoteType ownership into the target contract.
2. Use field names as durable binding keys. Renames and same-label imports would silently retarget execution; stable `FieldDef.id` is already the safer overlay identity.
3. Duplicate Cards/progress per application. This violates the approved single progress authority and changes scheduling semantics merely to model presentation reuse.
4. Resolve the latest live Template on every restore. This makes an active lease non-replayable and lets edit/unpublish operations change in-flight behavior.

## Deferred physical design

Phase 4 or later must decide table names/layout, foreign keys, uniqueness and ordering constraints, release pinning, backfill/collision handling, retention, reusable-definition sharing permissions, and migration rollback. It must also specify how future repeated applications map to Cards without splitting the approved learner progress identity. None of those decisions is implied by the Phase 3 JSON projection.

## Verification

- Snapshot, binding fingerprint, commit mismatch, and no-migration behavior: `tests/test_study_session_api.py`.
- Strict client restore/quarantine with legacy compatibility: `frontend/src/features/study/session/sessionRestore.test.ts`.
- Installed source/local context and zero-copy proof: `tests/test_study_behavior_acceptance_baseline.py`.
- Session config dual reader is used by synchronous commit, batch admission, worker execution, and architecture audit.
