# Array field cutover — 2026-10-11

## Scope and storage

Based on Gemini's local production-dump analysis and the independent
[audit](../architecture/array-field-migration-review-2026-10-11.md). The original
long reports, unsafe chunk-commit script and generated test exports were archived
under ignored `output/typing-templates/array-source-archive/`; private dumps are
not release artifacts.

`scripts/migrations/array_manifest_20261011.json` identifies exactly 20 FieldDefs
across five NoteTypes, including the owners of the two installed types with own
notes. It does not match NoteTypes by name or change 50 empty installed schemas.
Release-pinned clone schema/content and learner overlays remain pinned.

Flama's native `array` value is a **string with one item per line**, not a JSON
list. Reading separators, `$` in short Vietnamese translations, semicolons in
English lists and commas in Kanji_N3 meanings follow the reviewed parsers.
Bracketed prose is preserved. Missing/null keys, non-target fields, media,
identity, tags, cards and review progress are retained. Already-array fields are
validated without splitting their punctuation again.

Production preflight: 41,199 scanned notes; 21,244 need content changes; 19,955
already have the same one-item result. 308 other notes remain out of scope.
139 repeated field values are preserved. Existing pair-length mismatches total
165 occurrences in **113 distinct notes** (Collocation 1, Synonym 64, Antonym 100);
the migration does not invent missing translations or deduplicate paired columns.

## Template and editor checks

- English pairs read rendered `<br>` boundaries in template JS. An item containing
  `;` remains one item; duplicate translations retain their index. Missing paired
  values render an empty cell rather than discarding the other column.
- Default reading/translation and English meanings use block text layout. Array
  lines have no added `<p>`/`<div>` wrapper, margin or padding. Existing grid row
  gap remains 3 px. Chrome checks covered 1280, 390 and 320 px plus natural wrapping.
- Prose fields not in the migration retain their existing formatting. The two
  customized template copies retain their image/audio markup and layout.
- Editor normalization and conversion validation preserve repeated array items.
  The server validates plain lines; it does not split template fields.
- Four reviewed typing definitions install into user 1's template library. Existing
  definitions update through ORM history; historical versions are not rewritten.

## Plan and apply

Run from the reviewed release with `/etc/flama/flama.env` supplied by systemd.
The factory runs in `audit_mode=True`; no startup schema repair executes.

```sh
/opt/flama/venv/bin/python scripts/migrations/array_cutover.py plan \
  --plan /var/backups/flama/array-20261011/cutover.json \
  --expect-database flama --expect-server chung
```

Before apply: stop HTTP, Connect and Study worker writers; verify they stopped;
take a fresh `mysqldump --single-transaction` backup and validate its gzip. Review
the plan summary/checksum. Plans contain original values and must stay mode 0600
outside git. Generate the final plan after writers stop.

```sh
/opt/flama/venv/bin/python scripts/migrations/array_cutover.py apply \
  --plan /var/backups/flama/array-20261011/cutover.json \
  --expect-database flama --expect-server chung --writers-stopped \
  --receipt /var/backups/flama/array-20261011/applied.json
```

Schema, content, template versions, audit and marketplace dirty atoms commit in
one transaction. Row locks plus whole-note hashes reject stale edits, including
notes whose preflight values did not require transformation. Note counts reject
membership changes. Chunked flushes do not commit partial data. Auto-publication
is suppressed for this cutover, including the presentation before-commit queue;
configured flags and historical releases/install pointers are retained. Dirty
atoms and revisions make a later normal release detect the backfill.

Verify every post-image hash, scoped field types, unchanged note/card/media counts,
new template heads, original historical versions/releases/install pointers,
working-tree atoms, renderer output, HTTP health and Study worker readiness.
An immediate new plan must report zero content/schema/template mutations.

## Restore

Keep writers stopped, or stop them again before restoration. This checks the
post-image hashes before replacing target values and types. Unrelated later edits
cause a refusal rather than an overwrite. Template restore creates a new history
version; newly installed definitions archive rather than deleting attachments.

```sh
/opt/flama/venv/bin/python scripts/migrations/array_cutover.py restore \
  --plan /var/backups/flama/array-20261011/cutover.json \
  --expect-database flama --expect-server chung --writers-stopped \
  --receipt /var/backups/flama/array-20261011/restored.json
```

Use the full SQL backup only under a stopped-writer recovery procedure. It is not
a routine rollback after new user writes. Follow the Study code-rollback gate
before selecting an older application release.

## Validation evidence

51 focused backend tests and 46 frontend tests passed; frontend lint, typecheck
and production build passed. Isolated MySQL rehearsal uses a full production
backup, injects failure after the first batch, checks rollback, performs the full
apply, checks idempotency and release previews, then restores all target values.
Rehearsal passed injected rollback, full restore and idempotency; 22 historical
releases and all install pointers/overlay revisions stayed unchanged. It created
22,596 additional dirty atoms, and real release previews detected the backfill.
Deployment results are recorded after activation and production verification.
