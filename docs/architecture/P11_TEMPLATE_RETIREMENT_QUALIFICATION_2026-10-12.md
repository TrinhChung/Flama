# P11 and Template origin retirement qualification

Date: 2026-10-12. Mode: DESIGN/implementation. Workspace: isolated
`D:/Project/nihongo-legacy-retirement`. This report records focused SQLite
qualification; it does not certify MySQL deployment or the whole application.

## Invariants and resulting architecture

- Learner progress stays on `StudyProgressSubject`; presentation retirement
  never restores or rewrites the frozen CardProgress projection.
- Physical `cards` rows are replaced by derived Note/application presentations.
  `PresentationAlias` archives the exact original UUID, Note, application,
  Template and timestamps without content foreign keys. Archived aliases are
  immutable through ORM writers and survive content removal.
- Original Note/application ID sets distinguish pre-cutover missing pairs from
  new content. An absent old pair is not regenerated. Imported new Notes can
  retain historical timestamps without being mistaken for original Notes.
- Old wire UUIDs remain exact through `CardWireIdentity.id`; internal pair
  identity is `.key`. Session, event, Connect and receipt IDs are not rewritten.
  `Card.order_key` preserves the old UUID when creation/due anchors tie; the
  modern wire identity remains the pair key. Both pristine and stateful
  availability readers retain this archived tie anchor.
- Owned discovery uses active applications. Installed source discovery honors
  initialized release pins, including retired applications, and release Note
  membership sequences. Legacy timestamp fallback uses the exact archived
  per-Note Card timestamp.
- Template definitions belong to an explicit author and outlive any one
  NoteType. Applications own occurrence, position, default, ordinal and
  bindings. There is no `Template.note_type_id`, `Template.note_type`,
  `NoteType.templates` or implicit Template-creation attachment listener.

## Alternatives and storage cost

A timestamp-only cutoff is insufficient: historical imports and per-Note Card
creation/deletion are not recoverable from application timestamps. Storing a
tombstone for every absent historical cross-product pair could grow faster
than content. The chosen fixed alias archive plus original entity sets keeps
evidence proportional to the old rows and entities; new Notes/applications do
not create additional materialized presentation rows.

Inferring Template ownership from a remaining attachment would conflate
authorship with usage. Migration 60 backfills only a missing owner from its
actual historical origin, requires a verified external archive, and refuses
unknown authors or unconverted origin attachments. Typed live input metadata
is frozen before origin contraction; source, timestamps, published versions,
history, pins and application identities are preserved.

## Focused evidence

| Test file | Result | Scope |
| --- | --- | --- |
| `tests/test_derived_card_retirement_migration.py` | 10 PASS | Exact archive equality, unchanged frozen progress and wire IDs, width expansion, refusal gates, idempotence, safe downgrade refusal |
| `tests/test_derived_card_retirement_scope.py` | 17 PASS | Old UUID lookup/fence and tie ordering, deleted-pair suppression, exact timestamp cutoff, pinned retired/empty releases, local-added Notes, set-wise visibility |
| `tests/test_template_origin_retirement.py` | 12 PASS | Independent ownership/lifetime, atomic explicit attachment, MCP read/update scope, repeated occurrences, binding remap, scoped order/default |
| `tests/test_template_origin_retirement_migration.py` | 6 PASS | Actual archive/restore verification, ownership and typed metadata, unchanged source/history/application rows, refusal gates and rerun |
| `tests/test_template_library.py` | 13 PASS | Real REST library ownership, cross-scope/repeated attachments, lifecycle, bindings, no per-Note attachment writes |
| `tests/test_template_versions.py` | 12 PASS | Actual REST history, restore, atomic flush/savepoint behavior and source hashes |
| `tests/test_template_attachment_writers.py` | 14 PASS | REST, CSV, MCP and Connect writers follow explicit applications and preserve independent definitions/canonical subjects |
| `tests/test_template_pinned_new_install.py` | 6 PASS | New flat/modular installs hydrate retired release pins; initialized empty manifests remain empty; NULL unrelated scopes cannot grant private Template access |

These eight suites contain **90 passing tests**. Fixtures explicitly enroll
new users in NOTE and create applications; they do not reintroduce compatibility
properties or legacy ORM writers.

Factory, mapper configuration and SQLite `db.create_all()` passed. Runtime
metadata contains no physical `cards` or retired CardProgress table. `git diff
--check` passed for these changes.

## Remaining release gates

The root task must verify complete consumer cutover, old session/receipt replay
suites, historical migration chain, MySQL DDL and backup/restore rehearsal,
then local-first deployment before VPS. The real REST/Connect suites above
passed after origin readers/writers and obsolete fixtures were migrated;
earlier transient failures are not used as release evidence. No real local or
VPS data was changed by this subtask. Root MySQL/deployment evidence belongs
in its deployment report, independently of these SQLite proofs.
