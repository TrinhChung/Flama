# Single Published Base: implementation and migration ADR

Date: 2026-10-29. Contract: [#263](https://github.com/TrinhChung/Flama/issues/263),
[approved plan](NOTE_LEVEL_VERSIONING_PLAN_2026-10-28.md).

Status: implementation behind `NOTE_PUBLISHED_BASE_ENABLED=false` by default.
Production has not been migrated. P4 deployment and P6 removal of historical
tables/code remain separate operational steps after the reviewed cutover and soak.
The [30 October review response](NOTE_PUBLISHED_BASE_REVIEW_RESPONSE_2026-10-30.md)
supersedes the initial performance/route qualification with ownership guards,
transaction-local caches, narrow publication fences and full static-route captures.
The deployment pipeline accepts the optional GitHub Environment flag and preserves
an operator-set value when it is unset. The read-only code rollback guard checks
for a `base_cutover` release and rejects a binary without the declared Published
Base capability, even when it already supports Field ID storage.

## Decision and storage

`notes` holds the single Published Base. Published Notes have `published_at`;
unpublished Notes are edited in place and never enter learner/public scopes.
One `note_drafts` row per published Note stores sparse author changes. The existing
field identity codec and `content_revision` are retained. Draft saves do not change
the Base revision; publication does. A later draft save wins.

Draft JSON uses stable Field UUIDs with `{op: "set", value: ...}` or `{op: "remove"}`.
Presence, JSON null and native/nested arrays remain distinct. Undeclared labels use
the existing `extra:<hash>` identities and a captured `label`. `meta:deck_id` allows
an explicit move to no deck; nullable `tags`/`deck_id` otherwise mean unchanged.
Restoring all values/metadata to Base removes the draft.

Migration `20261029_000076` adds only the approved columns and PK-only draft table:
`notes.published_at/deleted_at`, `field_defs.deleted_at`,
`deck_marketplace_items.published_schema_json`, and override `base_hash`.
No secondary index is added. The MySQL draft FK inherits the actual referenced
column's collation. The migration backfills publication membership and frozen
schema from legacy release data; it does not activate the new runtime.

The alternative sparse old-value Base was rejected in the approved plan: a missed
learner adapter could expose an author's unpublished value. With the chosen model,
the stored Note remains published content. Full immutable history and per-install
rebase are deliberately retired; templates retain their separate published pins.

## Reader/writer inventory and authority

The existing `maintain_field_identity` flush hook remains the single ORM write
adapter. It encodes names to stable IDs, redirects published edits into drafts and
restores stored Base columns before SQL is emitted. Bulk/raw writes remain fenced.
`published_base_write` permits publication and `base_maintenance(reason)` records
explicit technical maintenance. These contexts do not commit and require flushing
inside the context. Maintenance callers must intentionally choose that authority;
an ordinary normalizer call follows the author draft path.

HTTP actor checks are also enforced at the property/flush boundary: an anonymous
or foreign reader sees Base, and a foreign writer cannot replace a published
Note's draft. Admin views of another owner's Note use Base as well. Trusted
Connect bearer identities are carried to final transaction flush; jobs should
select `note_author_view(owner_id)` explicitly when reading private drafts.
Draft caches and schema lookups are transaction-local, never process caches.

Normal publication validates the locked head against its read snapshot, discovers
sparse Draft IDs, locks only those Note/Draft PKs and reads new Notes through the
existing owner/deck index. Shared field locks and the covering listing fence
protect schema without blocking a sibling's ordinary Note save. A pre-existing
stale snapshot retains a conservative serialized current-read fallback. Late
scope discovery uses NOWAIT to avoid waiting in reversed head/Note lock order;
deck reparenting fences the affected ancestor listings. These paths retain the
same caller-owned transaction and preserve explicit Base-write authority.

| Boundary | Concrete consumers | New behavior |
|---|---|---|
| Author values | Content API, Browse editor, MCP Note tools, Connect/import/sync, TTS/media/crawl/strokes, array conversion | Existing `note.field_values` property and flush adapter preserve draft isolation |
| Author metadata | Content serializer, Browse repositories, MCP edit/tag paths, Study quick editor | `effective_note_metadata` / `author_note_column`; explicit metadata intent also allows reverting a draft to Base |
| Technical maintenance | `anki_content_normalizer`, `flashcard_media_normalizer` and rollback, offline migration tools | Explicit audited Base authority when intended; no implicit bypass for scripts |
| Learner values/schema | `share/overlay`, Browse page/detail/search/sort, Study artifacts, Connect identity lookup | Raw published values plus sparse override; schema from the listing snapshot |
| Public values | Marketplace sample cache, public MCP previews, shared-note MCP listing/search | Published Notes/labels only; no unreleased fallback in Base mode |
| Scope/counts | `flashcards_share_repository`, Note analytics/stats, deck aggregation, count/forecast vectors | Published/deleted predicates and current listing head |
| Template selection | Effective templates, Study sessions and template presets | Current listing template pin, regardless of old install pin |
| Contribution merge | `change_request/{preview,lifecycle,helpers,merge}` | Current Base comparison, author edits become drafts, personal overlays remain |
| Deletion | Content API, Browse, MCP batch, seeding | Published delete is a draft before progress/media cleanup; bulk bypass is rejected |

An AST scan during implementation found assignments in the following existing
content writers (constructor-only writers are additional): `anki_content_normalizer`,
`browse_card_service`, `browse_voicevox_service`, `field_array_conversion_service`,
`flama_connect_media_service`, `flashcard_content_service`, `flashcard_import`,
`flashcard_media_api_service`, `flashcard_media_normalizer`, `image_crawl_service`,
`note_management_service`, `note_sync_service`, `study_card_editor_service`,
`change_request/merge`, `connect/actions`, `connect/import_cards`, `mcp/note_tools`,
and `strokes/stroke_service`. Shared identity hooks/runtime provide the common
adapter. The AST inventory is evidence of assignments, not proof of caller coverage.

The learner adapter batch-loads only requested identities; no process-global
personalized deck cache is introduced. Search/count/sort resolve effective values
before pagination. Source branches added after install map to the nearest mapped
ancestor; reads create no learner folders. Local added Notes/Fields remain visible.
Soft-deleted source Notes stay hidden even if an override exists.
Author draft saves invalidate the author's count-cache vectors for old/new deck
scopes, including staged deletion, without invalidating other learners or bumping
the Published Base's Note revision. Actual publication invalidates shared content.

## Publish, concurrency and retention

The service locks listing, NoteType, then pending Notes/drafts. Author flushes use
the same order; learner overlay writes lock NoteType before source Note. Publication
updates pending Notes, captures the schema and template pins, appends metadata,
updates the current head and bumps content count revisions in one transaction.
It writes no content atoms/checkpoints and queries no subscriber installs.
The existing idempotency key/head/revision contract is retained.
Schema, source branches, pending Notes, release sequence and template source/pin
reads are current locking reads during publication. Authentication may already
have established an older REPEATABLE READ snapshot; it must not become the new Base.
The committing publisher retries MySQL deadlock 1213 through the existing bounded
retry helper. Tests cover source schema/branch and template commits after that snapshot.

`note-base-publish-note-type` implements the E6 owner operation for listings sharing
a NoteType. It defaults to preview and publishes each listing atomically with its
own head/revision and derived idempotency key. The batch explicitly reports partial
completion; a later failure does not undo an earlier committed listing.

Reference checks before hard deletion are current locking reads. An older InnoDB
REPEATABLE READ snapshot must not miss a learner override committed before the
publisher acquired the Note lock. Referenced Notes become tombstones; unreferenced
Notes are deleted at publish. Tests exercise this specific interleaving and an
independent reader retaining a consistent snapshot during publication.

`flask note-base-retention` is a bounded dry run; `--apply` removes eligible
90-day tombstones/expired overrides. It retains Note identities with progress or
other references and Fields referenced by snapshots, drafts or canonical override
identity (including overrides whose nullable advisory FK is absent). The operation
uses the publication lock order and rechecks candidates with current reads.
Expired overrides on deleted Fields are eligible even while their Note stays live.
The returned `next_cursor` / CLI `--after` advances past retained references, so
the first referenced tombstone cannot starve later eligible identities.
Removing media from a field retains the asset/file. Unused-file GC remains deferred
as decided in the plan. Shared deck deletion archives existing published content;
an admin purge cannot bypass published retirement.

## HTTP and UI transition

- Publish preview/publish retain their existing endpoints and envelopes. Preview
  includes `content_model: "published_base"`.
- `GET /api/marketplace/installations/<id>/base-overrides` (and the old `/updates` status URL)
  returns a bounded private comparison page, current content/overlay revisions and
  an opaque next cursor. Only the install owner can read it.
- `DELETE /api/marketplace/installations/<id>/overrides/<override_id>` requires
  `expected_overlay_revision`. It deletes the sparse row, reverting to latest Base;
  a stored override with operation `remove` continues to mean removal of the value.
- `POST /api/marketplace/installations/<id>/overrides/<override_id>/keep` requires
  both the overlay revision and `current_base_hash` shown in the comparison. It
  acknowledges that exact Base, preserves the personal value and clears the marker.
  A concurrent Base change returns 409 and requires a refresh. Browse displays the
  marker only when the Base changed and the personal operation still differs.
- In Base mode, legacy diff/prepare/apply/conflict and auto-publish/update settings
  writes return 410. Existing authentication requirements remain in place.
- Installed deck cards open the personal comparison. Old update links select the
  comparison after cutover, without mounting the legacy rebase hook. Flag-off UI
  keeps the old behavior. Deck auto-publish controls are hidden in Base mode;
  independent Template publication is unchanged.
- Touched React workflows use slice public APIs, page composition under `pages`,
  shared deck display under `entities/marketplace-deck`, and publication contracts
  under `entities/deck-publication`. Existing route entry shims preserve callers.

## Validation and remaining delivery gates

See [rehearsal and measurements](NOTE_PUBLISHED_BASE_REHEARSAL_2026-10-29.md) and
the [cutover runbook](../runbooks/NOTE_PUBLISHED_BASE_CUTOVER_20261029.md).
The worktree preserves the original checkout and its unrelated edits.

P6 history removal is intentionally not applied while rollback still depends on
the old atoms/checkpoints/membership/journal. Do not deploy a contract migration
or delete those models before the production soak has ended. The full load matrix
at other buffer pool sizes needs separate isolated instances or explicit operational
coordination; this change never resizes the shared local MySQL buffer pool.
