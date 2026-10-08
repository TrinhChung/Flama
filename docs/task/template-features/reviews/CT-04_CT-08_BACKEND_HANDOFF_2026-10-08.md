# Template backend completion and Gemini FE handoff — 2026-10-08

Scope: finish the remaining Codex/Claude template backend work after the local build audit, then prepare Gemini FE phases. Branch: `refactor/frontend-fsd-renderer-boundary`. The shared workspace also contains concurrent i18n/marketplace/SEO/MCP work; those changes are not template implementation evidence. Foundation commits appeared in branch history during this audit. Codex did not commit, push, reset or launch Gemini in this task.

## Completed backend

| Task | Implemented behavior |
|---|---|
| CT-04 | Effective owned/installed/local-added template resolution, canonical user copy or immutable pin, projected attachment fields and binding |
| CT-06 | Independent template library and ACTIVE occurrences; group/usage/count queries, standalone draft preview, stable field IDs, safe retirement; migration 54 |
| CT-07 | Shared `release_core` used by deck/template adapters; immutable template releases and deck pins; presentation-only deck releases and working-state/auto-publication hooks; migration 55 |
| CT-05 | One copy per user/source across installs, paid entitlement reuse, source lineage republish/duplication guards, upstream release reads through owned copies, update/conflict/reset |
| CT-08 | Opt-in study preparation, personal preset, strict transient input validation, effective clone schema, frozen runtime projection, restore/content patch and quick-edit compatibility |

Template version/history CT-02/03, GT-10A and GT-15A were already present. Their focused contracts were rerun; they should not be assigned again. The real local schema was observed at `20261007_000055` with 24 templates/24 versions. This audit did not migrate or write application data in that database. Earlier migration-52 observations are historical and no longer describe its current state.

## Bugs closed during audit

- Library lacked the FE group/usage contract and standalone draft preview. Added strict validation, owner scope, batched ACTIVE usage and preview using the existing safe renderer without source/history writes.
- NoteType reads and publication eligibility still used `Template.note_type_id`/`.templates` in several paths. Active attachment reads now include independent definitions and received copies; retired occurrences remain excluded. Note counts are distinct and scoped to the requested NoteType.
- Source listing/preview could reveal unpublished code, and received copies could not read upstream releases via their owned identity. Marketplace reads use the published immutable template snapshot; recipient release reads resolve through subscription ownership.
- A paid NoteType/deck receipt could make redundant copies or preserve the wrong provenance. Fresh installs use the canonical subscription copy; legacy compatibility retains market lineage and existing IDs. Publish guards cover attached market templates as well as legacy definitions.
- Template/binding-only edits could fail to produce a deck release or advance its working revision. Presentation atoms compare immutable pins to current content/schema/ACTIVE applications; deck atoms contain hashes/schema/application metadata, not HTML/CSS. Rebase does not treat these atoms as note/field conflicts and preserves personal copies.
- Automatic deck publication from an independent ORM `Session` accidentally used the Flask-scoped session. The synchronous adapter binds the existing pipeline to the writer for the call and restores the previous scope in `finally`. Source, history, deck/template release and subscriber writes remain in the same caller transaction. Commit and forced outer rollback tests cover this seam.
- Archived definitions with auto publish enabled could no longer save content. Their history saves now succeed while standalone automatic publication is skipped. Explicit standalone publish remains blocked; existing ACTIVE deck use can still capture the definition.
- Session-only bindings bypassed preset validation; clone overrides/added/disabled fields were incomplete. All overrides now validate against the effective schema before opening a lease.
- Content patch/quick edit could leave alias values stale or show aliases as source note fields. Optional frozen `binding_projection` snapshots source fields and ID targets, protects restore with a canonical fingerprint, and updates aliases/media helpers. Identity artifacts keep their old shape/hash.
- Existing scaling/effective-template tests had outdated fixture assumptions. Corrections retain identity/uniqueness/lookup assertions instead of weakening runtime invariants.

## Validation

| Command/check | Result |
|---|---|
| `python scripts/run_tests.py --module templates --backend-only` | PASS: 193 tests, 17 files |
| `python scripts/run_tests.py --module templates --frontend-only` | PASS: 175 tests, 12 files |
| Deck auto publish/update, install rebase, release API and route-map focused files | PASS: 32 tests, 4 files |
| NoteType template list/count, library FE contract, REST and flashcard integration after the final compatibility-list fix | PASS: 113 tests, 4 files |
| Modular runner/catalog focused files | PASS: 27 tests, 2 files |
| `verify_template_versions_mysql.py --runtime` | PASS MySQL 8.0.40: exact sources/IDs, idempotence, downgrade guard/reupgrade, current ORM schema parity, concurrent initial versions and stale repeatable-read editors retaining both changes |
| `verify_template_attachments_mysql.py` | PASS MySQL 8.0.40: 53→54→55, stable/scoped bindings, source/history/progress identity, historical fallback, distribution downgrade/reupgrade guards |
| Both MySQL probe cleanup checks | PASS: generated disposable schemas removed |
| Real `wsgi.py` import with startup maintenance disabled; read-only loopback DB query | PASS: schema 55, SPA `/note-types` 200, unauthenticated library 401 |
| `npm --prefix frontend run build` | PASS: TypeScript and Vite production build, 3082 modules, 2.62s Vite build |
| Marketplace DeckCard/PublishDeckTree/PublishNoteTypeSelector focused tests | PASS: 10 tests, 3 files |
| Frontend lint | PASS exit 0; existing warnings remain |
| Task-file `git diff --check`, documentation links and U1–U8 preservation | PASS; 26 contract/spec/prompt files decoded as UTF-8 and local links resolved |

The new `templates` modular catalog prevents unmapped template/release-core sources from silently selecting the entire suite. Shared core selects deck and template parity. Study catalog also includes preset/application and content-patch tests. Small SEO/MCP catalog entries cover new files present from concurrent work; their behavior was not changed by this template audit.

The first final build saw concurrent marketplace/i18n type errors. By the later check, other workspace changes had corrected unused props and mismatched product/error props. Codex corrected translation helper signatures in DeckCard, PublishDeckTree and PublishNoteTypeSelector to the namespace's `TFunction` type, retaining runtime labels and DOM/classes. The dynamic sync-status key uses the corresponding `ParseKeys` subset. These local compatibility edits require no dependency change.

The compatibility NoteType template-list DTO retains its previous keys, including `note_count`; input schema/bindings remain on library/application APIs. A temporary additive-key regression was caught by the existing unchanged-keys test and corrected before the final 113-test pass. Contextual membership/order/defaults use ACTIVE occurrences, while note counts stay scoped to the owned NoteType.

## Gemini handoff

The current contracts and prompts are linked from [tracker](../README.md). Start **GT-12A**, then **GT-10B**, and continue GT-12B/C/D/E → GT-13A/B/C/D → GT-11A/B/C → GT-18A/B/C/D after each listed dependency. Use one phase per assignment and its exact whitelist. The common page is `TemplateDetailPage`; history/distribution compose into it. Shared entity/index/routes/page changes require sequential ownership.

The v1 per-install fork, token rewrite, copied definition/apply and required-input hard failure tables are superseded. GT-15D/E backend invariants are covered by current suites. GT-16/17 raw candidates remain historical unaccepted inventories and no longer block the current handoff.

New library/history/distribution/preparation UI has **not** been implemented or browser-accepted by this audit. CT-R2 mobile/dark/browser review and GT-14 user guide wait for those actual screens. Use an isolated Chrome profile. The guide must describe published reset and retained user copy/history, stable bindings and advisory empty inputs.

Standalone template marketplace catalog (N5) and list-of-fields inputs (N6) remain excluded. Scheduler policies and source-note clone semantics were not expanded. An active quick edit after a concurrent FieldDef rename still uses the existing name-based update payload; new sessions resolve by stable IDs. This pre-existing seam does not permit replacing a frozen session's projection.
